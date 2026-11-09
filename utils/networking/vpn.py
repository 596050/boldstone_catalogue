#!/usr/bin/env python3
"""
Generic OpenVPN rotation utility using ProtonVPN .ovpn configs.

Can be used as a library (context manager) or run directly from the CLI.

Library usage:
    from utils.networking.vpn import VPNRotator

    with VPNRotator(configs_dir="/path/to/ovpn/files") as vpn:
        print(vpn.ip)           # current VPN IP
        print(vpn.server)       # current config name
        do_work()
        vpn.rotate()            # switch to a new server
        do_more_work()
    # auto-disconnects and cleans up on exit, Ctrl+C, or crash

CLI usage:
    python -m utils.networking.vpn connect --configs /path/to/configs
    python -m utils.networking.vpn rotate  --configs /path/to/configs
    python -m utils.networking.vpn disconnect
    python -m utils.networking.vpn status
    python -m utils.networking.vpn list    --configs /path/to/configs
    python -m utils.networking.vpn shell   --configs /path/to/configs

Options:
    --configs DIR       Directory with .ovpn files (default: utils/networking/vpn_configs/)
    --auth FILE         OpenVPN auth file (default: /etc/protonvpn/auth.txt)
    --log-file FILE     Path to write IP log JSON (optional)
    --country CC        Prefer a specific country code (e.g. us, de, jp)
"""

from __future__ import annotations

import argparse
import atexit
import json
import os
import random
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

DEFAULT_CONFIGS_DIR = Path(__file__).resolve().parent / "vpn_configs"
DEFAULT_AUTH_FILE = Path("/etc/protonvpn/auth.txt")

# Resolve openvpn binary — sudo doesn't inherit user PATH on macOS
_OPENVPN_SEARCH_PATHS = [
    "/opt/homebrew/sbin/openvpn",
    "/opt/homebrew/opt/openvpn/sbin/openvpn",
    "/usr/local/sbin/openvpn",
    "/usr/local/opt/openvpn/sbin/openvpn",
    "/usr/sbin/openvpn",
    "/sbin/openvpn",
]


def _find_openvpn() -> str:
    """Find the openvpn binary, checking Homebrew and system paths."""
    # Check if it's on the current PATH first
    result = shutil.which("openvpn")
    if result:
        return result
    for p in _OPENVPN_SEARCH_PATHS:
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return "openvpn"  # fallback — will fail with a clear error from sudo


OPENVPN_BIN = _find_openvpn()


# ---------------------------------------------------------------------------
# Sudo keepalive — prevents sudo ticket from expiring during long runs
# ---------------------------------------------------------------------------

_sudo_keepalive_thread: threading.Thread | None = None
_sudo_keepalive_stop = threading.Event()


def start_sudo_keepalive(interval: int = 60) -> None:
    """Start a background thread that refreshes the sudo ticket every `interval` seconds."""
    import threading as _th
    global _sudo_keepalive_thread, _sudo_keepalive_stop

    if _sudo_keepalive_thread is not None and _sudo_keepalive_thread.is_alive():
        return

    _sudo_keepalive_stop.clear()

    def _keepalive() -> None:
        while not _sudo_keepalive_stop.wait(interval):
            try:
                subprocess.run(
                    ["sudo", "-n", "-v"],
                    capture_output=True, timeout=10,
                )
            except Exception:
                pass

    _sudo_keepalive_thread = _th.Thread(
        target=_keepalive,
        name="sudo-keepalive",
        daemon=True,
    )
    _sudo_keepalive_thread.start()


def stop_sudo_keepalive() -> None:
    """Stop the sudo keepalive thread."""
    global _sudo_keepalive_thread
    _sudo_keepalive_stop.set()
    if _sudo_keepalive_thread is not None:
        _sudo_keepalive_thread.join(timeout=5)
        _sudo_keepalive_thread = None


# ---------------------------------------------------------------------------
# IP helpers
# ---------------------------------------------------------------------------

IP_SERVICES = [
    "https://api.ipify.org",
    "https://ifconfig.me/ip",
    "https://icanhazip.com",
]


def get_public_ip() -> str | None:
    """Get current public IP via external services."""
    for svc in IP_SERVICES:
        try:
            result = subprocess.run(
                ["curl", "-s", "-m", "5", svc],
                capture_output=True, text=True, timeout=10,
            )
            ip = result.stdout.strip()
            if ip and ip.count(".") == 3:
                return ip
        except Exception:
            continue
    return None


def verify_ip(expected_ip: str) -> bool:
    """Confirm the current public IP matches expected via two services."""
    checks_ok = 0
    for name, url in [("ipify", IP_SERVICES[0]), ("ifconfig.me", IP_SERVICES[1])]:
        try:
            result = subprocess.run(
                ["curl", "-s", "-m", "8", url],
                capture_output=True, text=True, timeout=12,
            )
            actual = result.stdout.strip()
            if actual == expected_ip:
                checks_ok += 1
            else:
                print(f"  [vpn] WARNING: {name} reports {actual}, expected {expected_ip}")
                return False
        except Exception:
            pass
    return checks_ok >= 1


GEO_IP_SERVICES = [
    "https://ipinfo.io/{ip}/country",
    "https://ipapi.co/{ip}/country_code/",
]


def get_ip_country(ip: str) -> str | None:
    """Get the 2-letter country code for a public IP address."""
    for svc_template in GEO_IP_SERVICES:
        url = svc_template.format(ip=ip)
        try:
            result = subprocess.run(
                ["curl", "-s", "-m", "5", url],
                capture_output=True, text=True, timeout=10,
            )
            code = result.stdout.strip().upper()
            if len(code) == 2 and code.isalpha():
                return code
        except Exception:
            continue
    return None


# ---------------------------------------------------------------------------
# VPNRotator
# ---------------------------------------------------------------------------

class VPNRotator:
    """Manages OpenVPN connections with automatic rotation and cleanup.

    Use as a context manager for guaranteed cleanup:

        with VPNRotator(configs_dir="path/to/ovpn") as vpn:
            print(vpn.ip)
            vpn.rotate()
    """

    def __init__(
        self,
        configs_dir: str | Path = DEFAULT_CONFIGS_DIR,
        auth_file: str | Path = DEFAULT_AUTH_FILE,
        log_file: str | Path | None = None,
        country: str | None = None,
        max_retries: int = 5,
        connect_timeout: int = 60,
        verbose: bool = True,
    ) -> None:
        self.configs_dir = Path(configs_dir)
        self.auth_file = Path(auth_file)
        self.log_file = Path(log_file) if log_file else None
        self.country = country.lower() if country else None
        self.max_retries = max_retries
        self.connect_timeout = connect_timeout
        self.verbose = verbose

        self._used_configs: set[str] = set()
        self._tmpdir = Path(tempfile.mkdtemp(prefix="vpn_rotator_"))
        self._pid_file = self._tmpdir / "openvpn.pid"
        self._log_file = self._tmpdir / "openvpn.log"
        self._connected = False
        self._bare_ip: str | None = None

        self.ip: str | None = None
        self.server: str | None = None

    # -- context manager -----------------------------------------------------

    def __enter__(self) -> VPNRotator:
        self._preflight()
        self._bare_ip = get_public_ip()
        self._install_signal_handlers()
        atexit.register(self._cleanup)
        self.connect()
        return self

    def __exit__(self, *exc) -> None:
        self.disconnect()
        self._cleanup_tmpdir()
        return False

    # -- public API ----------------------------------------------------------

    def list_configs(self) -> list[Path]:
        """List available .ovpn config files, optionally filtered by country."""
        configs = sorted(self.configs_dir.glob("*.ovpn"))
        if self.country:
            filtered = [c for c in configs if c.stem.startswith(self.country + ".")]
            if filtered:
                return filtered
            self._log(f"No configs for country '{self.country}', using all")
        return configs

    def connect(self, config: Path | None = None) -> str | None:
        """Connect to a VPN server. Picks a random unused config if none given.

        Returns the new public IP, or None on failure.
        """
        if self._connected:
            self.disconnect()

        all_configs = self.list_configs()
        if not all_configs:
            raise RuntimeError(f"No .ovpn files found in {self.configs_dir}")

        if config:
            candidates = [config]
        else:
            unused = [c for c in all_configs if c.stem not in self._used_configs]
            if not unused:
                self._log(f"All {len(all_configs)} configs used, clearing history")
                self._used_configs.clear()
                unused = list(all_configs)
            random.shuffle(unused)
            candidates = unused[: self.max_retries]

        for cfg in candidates:
            self._used_configs.add(cfg.stem)
            ip = self._openvpn_connect(cfg)
            if ip:
                if verify_ip(ip):
                    self._log(f"IP verified: {ip}")
                else:
                    self._log("WARNING: IP verification failed — traffic may not be through VPN")
                self._connected = True
                self.ip = ip
                self.server = cfg.stem
                self._log_ip(cfg.stem, ip, "connected")
                return ip
            self._openvpn_disconnect()

        raise RuntimeError(
            f"Failed to connect after trying {len(candidates)} configs"
        )

    def disconnect(self) -> None:
        """Disconnect the current VPN session."""
        if not self._connected:
            return
        old_ip = self.ip
        old_server = self.server
        self._openvpn_disconnect()
        self._connected = False
        if old_ip:
            self._log_ip(old_server, old_ip, "disconnected")
        self.ip = None
        self.server = None

    def rotate(self, reason: str = "rotation") -> str | None:
        """Disconnect from current server and connect to a new one.

        Returns the new public IP.
        """
        old_ip = self.ip
        old_server = self.server
        self._log(f"Rotating — reason: {reason}")

        self._openvpn_disconnect()
        self._connected = False
        if old_ip:
            self._log_ip(old_server, old_ip, f"disconnected — {reason}")

        self.ip = None
        self.server = None
        return self.connect()

    def status(self) -> dict:
        """Return current VPN status."""
        current_ip = get_public_ip()
        return {
            "connected": self._connected,
            "server": self.server,
            "vpn_ip": self.ip,
            "current_ip": current_ip,
            "bare_ip": self._bare_ip,
            "vpn_active": (
                current_ip is not None
                and self._bare_ip is not None
                and current_ip != self._bare_ip
            ),
            "configs_available": len(self.list_configs()),
            "configs_used": len(self._used_configs),
        }

    def check_alive(self) -> bool:
        """Check that the VPN tunnel is still active (IP hasn't reverted)."""
        if not self._connected:
            return False
        current_ip = get_public_ip()
        if current_ip and self._bare_ip and current_ip == self._bare_ip:
            self._log(f"WARNING: IP {current_ip} matches bare IP — VPN may have dropped")
            return False
        return True

    # -- internal ------------------------------------------------------------

    def _preflight(self) -> None:
        """Validate setup before connecting."""
        # Check openvpn is installed
        if OPENVPN_BIN == "openvpn" and not shutil.which("openvpn"):
            raise RuntimeError(
                "openvpn not found. Install with:\n"
                "  brew install openvpn"
            )
        configs = self.list_configs()
        if not configs:
            raise RuntimeError(
                f"No .ovpn files in {self.configs_dir}\n"
                f"Download from: https://account.protonvpn.com/downloads#openvpn-configuration-files"
            )
        if not self.auth_file.exists():
            raise RuntimeError(
                f"Auth file not found: {self.auth_file}\n"
                f"Create with: sudo tee {self.auth_file} <<< 'username\\npassword'"
            )
        # Check for conflicting ProtonVPN GUI
        try:
            gui_check = subprocess.run(
                ["pgrep", "-f", "ProtonVPN.app"],
                capture_output=True, timeout=5,
            )
            if gui_check.returncode == 0:
                raise RuntimeError(
                    "ProtonVPN GUI app is running. "
                    "Disconnect and quit it before using VPN rotation."
                )
        except subprocess.TimeoutExpired:
            pass

    def _openvpn_connect(self, config: Path) -> str | None:
        """Launch openvpn daemon with the given config. Returns public IP or None."""
        self._log(f"Connecting via {config.stem}...")
        old_ip = get_public_ip()

        for p in (self._log_file, self._pid_file):
            p.write_bytes(b"")

        result = subprocess.run(
            [
                "sudo", OPENVPN_BIN,
                "--config", str(config),
                "--auth-user-pass", str(self.auth_file),
                "--daemon", "openvpn-rotator",
                "--writepid", str(self._pid_file),
                "--log-append", str(self._log_file),
                "--connect-retry", "3",
                "--connect-timeout", "30",
            ],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode != 0:
            err = result.stderr.strip() or result.stdout.strip()
            self._log(f"openvpn launch failed: {err}")
            return None

        polls = self.connect_timeout // 3
        for wait in range(polls):
            time.sleep(3)
            try:
                log_text = self._log_file.read_text(errors="replace")
                if "Initialization Sequence Completed" in log_text:
                    new_ip = get_public_ip()
                    self._log(f"Connected — IP: {new_ip} (was {old_ip})")
                    return new_ip
                if "AUTH_FAILED" in log_text:
                    self._log(f"Authentication failed — check {self.auth_file}")
                    return None
                if "Connection refused" in log_text or "SIGTERM" in log_text:
                    self._log("Server rejected connection")
                    return None
            except OSError as e:
                if wait == 0:
                    self._log(f"Cannot read log: {e}")

            if self.verbose and wait % 3 == 2:
                log_size = self._log_file.stat().st_size if self._log_file.exists() else 0
                self._log(f"Waiting for tunnel... ({(wait + 1) * 3}s, log: {log_size} bytes)")

        # Debug: show last log lines
        try:
            for line in self._log_file.read_text(errors="replace").strip().splitlines()[-5:]:
                self._log(f"  {line}")
        except Exception:
            pass
        self._log(f"Connection timed out for {config.stem}")
        return None

    def _openvpn_disconnect(self) -> None:
        """Kill the openvpn daemon via PID file, fallback to killall."""
        if self._pid_file.exists():
            try:
                pid_text = self._pid_file.read_text().strip()
                if pid_text:
                    pid = int(pid_text)
                    self._log(f"Stopping openvpn (pid {pid})...")
                    subprocess.run(["sudo", "kill", str(pid)], capture_output=True, timeout=10)
                    for _ in range(10):
                        check = subprocess.run(
                            ["sudo", "kill", "-0", str(pid)],
                            capture_output=True, timeout=10,
                        )
                        if check.returncode != 0:
                            break
                        time.sleep(1)
            except (ValueError, OSError, subprocess.TimeoutExpired):
                pass
            self._pid_file.write_bytes(b"")

        try:
            subprocess.run(["sudo", "killall", "openvpn"], capture_output=True, timeout=10)
        except subprocess.TimeoutExpired:
            self._log("Warning: killall timed out")
        time.sleep(2)

    def _log_ip(self, server: str | None, ip: str | None, reason: str) -> None:
        """Append to the IP log JSON file."""
        if not self.log_file:
            return
        log: list[dict] = []
        if self.log_file.exists():
            try:
                log = json.loads(self.log_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        log.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "server": server,
            "ip": ip,
            "reason": reason,
        })
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self.log_file.write_text(json.dumps(log, indent=2), encoding="utf-8")

    def _log(self, msg: str) -> None:
        if self.verbose:
            print(f"  [vpn] {msg}")

    def _install_signal_handlers(self) -> None:
        """Ensure cleanup on SIGINT/SIGTERM."""
        prev_sigint = signal.getsignal(signal.SIGINT)
        prev_sigterm = signal.getsignal(signal.SIGTERM)

        def _handler(signum, frame):
            signame = "SIGINT" if signum == signal.SIGINT else "SIGTERM"
            print(f"\n  [vpn] Caught {signame}, disconnecting...")
            self.disconnect()
            self._cleanup_tmpdir()
            # Re-raise with original handler so caller sees the interrupt
            if signum == signal.SIGINT and callable(prev_sigint):
                prev_sigint(signum, frame)
            elif signum == signal.SIGTERM and callable(prev_sigterm):
                prev_sigterm(signum, frame)
            else:
                sys.exit(128 + signum)

        signal.signal(signal.SIGINT, _handler)
        signal.signal(signal.SIGTERM, _handler)

    def _cleanup(self) -> None:
        """atexit handler."""
        if self._connected:
            print("\n  [vpn] Cleaning up VPN connection...")
            self.disconnect()
        self._cleanup_tmpdir()

    def _cleanup_tmpdir(self) -> None:
        if self._tmpdir.exists():
            shutil.rmtree(self._tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Convenience context manager (functional style)
# ---------------------------------------------------------------------------

@contextmanager
def vpn_session(**kwargs) -> Iterator[VPNRotator]:
    """Shorthand context manager.

        with vpn_session(configs_dir="/path/to/configs") as vpn:
            print(vpn.ip)
    """
    rotator = VPNRotator(**kwargs)
    with rotator as vpn:
        yield vpn


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="OpenVPN rotation utility",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument(
        "command",
        choices=["connect", "disconnect", "rotate", "status", "list", "shell"],
        help="Action to perform",
    )
    ap.add_argument("--configs", type=Path, default=DEFAULT_CONFIGS_DIR, help="Directory with .ovpn files")
    ap.add_argument("--auth", type=Path, default=DEFAULT_AUTH_FILE, help="OpenVPN auth file")
    ap.add_argument("--log-file", type=Path, default=None, help="IP log JSON file")
    ap.add_argument("--country", type=str, default=None, help="Prefer country code (e.g. us, de)")
    ap.add_argument("--quiet", action="store_true", help="Suppress verbose output")
    return ap


def cli_main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    # Commands that don't need a configs dir
    if args.command == "status":
        ip = get_public_ip()
        print(f"Current public IP: {ip or 'unknown'}")
        try:
            result = subprocess.run(["pgrep", "-x", "openvpn"], capture_output=True, timeout=5)
            if result.returncode == 0:
                pids = result.stdout.decode().strip().split("\n")
                print(f"openvpn running: yes (pid {', '.join(pids)})")
            else:
                print("openvpn running: no")
        except Exception:
            pass
        return

    if args.command == "disconnect":
        # Create a temporary rotator just for disconnect
        tmpdir = Path(tempfile.mkdtemp(prefix="vpn_rotator_"))
        pid_file = tmpdir / "openvpn.pid"
        pid_file.write_bytes(b"")
        try:
            subprocess.run(["sudo", "killall", "openvpn"], capture_output=True, timeout=10)
        except subprocess.TimeoutExpired:
            print("Warning: killall timed out")
        time.sleep(2)
        shutil.rmtree(tmpdir, ignore_errors=True)
        print("Disconnected.")
        ip = get_public_ip()
        print(f"Current IP: {ip or 'unknown'}")
        return

    # Commands that require a configs dir
    if not args.configs:
        parser.error(f"--configs is required for '{args.command}'")

    vpn = VPNRotator(
        configs_dir=args.configs,
        auth_file=args.auth,
        log_file=args.log_file,
        country=args.country,
        verbose=not args.quiet,
    )

    if args.command == "list":
        configs = vpn.list_configs()
        print(f"{len(configs)} configs in {vpn.configs_dir}:")
        for c in configs:
            print(f"  {c.stem}")
        return

    if args.command == "connect":
        vpn._preflight()
        vpn._bare_ip = get_public_ip()
        atexit.register(vpn._cleanup)
        ip = vpn.connect()
        print(f"\nConnected — IP: {ip}, server: {vpn.server}")
        print("VPN will stay active. Use 'disconnect' command to stop.")
        return

    if args.command == "rotate":
        vpn._preflight()
        vpn._bare_ip = get_public_ip()
        vpn._openvpn_disconnect()
        ip = vpn.connect()
        print(f"\nRotated — IP: {ip}, server: {vpn.server}")
        return

    if args.command == "shell":
        vpn._preflight()
        vpn._bare_ip = get_public_ip()
        vpn._install_signal_handlers()
        atexit.register(vpn._cleanup)

        ip = vpn.connect()
        print(f"\nConnected — IP: {ip}, server: {vpn.server}")
        print(f"Dropping into subshell. Type 'exit' or Ctrl+D to disconnect.\n")

        shell = os.environ.get("SHELL", "/bin/zsh")
        env = os.environ.copy()
        env["VPN_IP"] = ip or ""
        env["VPN_SERVER"] = vpn.server or ""
        try:
            subprocess.run([shell], env=env)
        except KeyboardInterrupt:
            pass
        finally:
            print()
            vpn.disconnect()
            vpn._cleanup_tmpdir()
            ip = get_public_ip()
            print(f"Disconnected. Current IP: {ip or 'unknown'}")
        return


if __name__ == "__main__":
    cli_main()
