#!/usr/bin/env python3
"""Cross-platform, dependency-free SSH tunnel supervisor.

The external machine publishes one of its local TCP services to a loopback-only
port on an SSH relay.  The source machine then forwards that relay port to its
own loopback interface.  No service is exposed directly to the public internet.
"""

from __future__ import annotations

import argparse
import os
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class Settings:
    role: str
    relay: str
    relay_port: int
    relay_bind_port: int
    local_port: int
    identity: Optional[Path]
    ssh: str
    reconnect_delay: float
    strict_host_key_checking: str


def port(value: str) -> int:
    number = int(value)
    if not 1 <= number <= 65535:
        raise argparse.ArgumentTypeError("port must be between 1 and 65535")
    return number


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Connect an external service and its source machine through an SSH relay."
    )
    parser.add_argument("role", choices=("external", "source"))
    parser.add_argument("--relay", required=True, metavar="[USER@]HOST")
    parser.add_argument("--relay-port", type=port, default=22)
    parser.add_argument(
        "--relay-bind-port", type=port, required=True,
        help="loopback port reserved on the relay (must be unique)",
    )
    parser.add_argument(
        "--local-port", type=port, required=True,
        help="external: service port; source: local port to create",
    )
    parser.add_argument("--identity", type=Path, help="SSH private-key file")
    parser.add_argument("--ssh", help="path to ssh executable")
    parser.add_argument("--reconnect-delay", type=float, default=5.0)
    parser.add_argument(
        "--strict-host-key-checking", choices=("yes", "accept-new"), default="yes",
        help="use accept-new only for first connection to a trusted relay",
    )
    parser.add_argument("--once", action="store_true", help="do not reconnect")
    parser.add_argument("--dry-run", action="store_true", help="print the SSH command and exit")
    return parser.parse_args(argv)


def resolve_ssh(requested: Optional[str]) -> str:
    if requested:
        candidate = Path(requested).expanduser()
        if not candidate.is_file():
            raise SystemExit(f"SSH executable not found: {candidate}")
        return str(candidate)
    found = shutil.which("ssh")
    if not found:
        raise SystemExit(
            "OpenSSH client was not found. Install it or pass --ssh PATH "
            "(Windows: enable the OpenSSH Client optional feature)."
        )
    return found


def settings_from(args: argparse.Namespace) -> Settings:
    identity = args.identity.expanduser().resolve() if args.identity else None
    if identity and not identity.is_file():
        raise SystemExit(f"SSH identity file not found: {identity}")
    if args.reconnect_delay < 0:
        raise SystemExit("--reconnect-delay cannot be negative")
    return Settings(
        role=args.role,
        relay=args.relay,
        relay_port=args.relay_port,
        relay_bind_port=args.relay_bind_port,
        local_port=args.local_port,
        identity=identity,
        ssh=resolve_ssh(args.ssh),
        reconnect_delay=args.reconnect_delay,
        strict_host_key_checking=args.strict_host_key_checking,
    )


def ssh_command(config: Settings) -> list[str]:
    common = [
        config.ssh,
        "-N",
        "-T",
        "-p", str(config.relay_port),
        "-o", "BatchMode=yes",
        "-o", "ExitOnForwardFailure=yes",
        "-o", "ServerAliveInterval=30",
        "-o", "ServerAliveCountMax=3",
        "-o", f"StrictHostKeyChecking={config.strict_host_key_checking}",
    ]
    if config.identity:
        common += ["-i", str(config.identity)]
    if config.role == "external":
        forwarding = f"127.0.0.1:{config.relay_bind_port}:127.0.0.1:{config.local_port}"
        common += ["-R", forwarding]
    else:
        forwarding = f"127.0.0.1:{config.local_port}:127.0.0.1:{config.relay_bind_port}"
        common += ["-L", forwarding]
    return common + [config.relay]


def printable(command: list[str]) -> str:
    return subprocess.list2cmdline(command) if os.name == "nt" else " ".join(
        "'" + item.replace("'", "'\"'\"'") + "'" if any(c.isspace() for c in item) else item
        for item in command
    )


def supervise(command: list[str], once: bool, reconnect_delay: float) -> int:
    stopping = False
    child: Optional[subprocess.Popen] = None

    def stop(_signum: int, _frame: object) -> None:
        nonlocal stopping
        stopping = True
        if child and child.poll() is None:
            child.terminate()

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    while not stopping:
        print(f"Starting: {printable(command)}", flush=True)
        child = subprocess.Popen(command)
        return_code = child.wait()
        if stopping:
            return 0
        print(f"SSH exited with status {return_code}.", file=sys.stderr, flush=True)
        if once:
            return return_code
        print(f"Reconnecting in {reconnect_delay:g}s...", file=sys.stderr, flush=True)
        time.sleep(reconnect_delay)
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    config = settings_from(args)
    command = ssh_command(config)
    if args.dry_run:
        print(printable(command))
        return 0
    return supervise(command, args.once, config.reconnect_delay)


if __name__ == "__main__":
    raise SystemExit(main())
