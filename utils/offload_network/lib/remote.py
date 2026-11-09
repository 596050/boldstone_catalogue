"""Safe SSH-to-Windows helpers.

Captures lessons learned the hard way during the 2026-06-02 cluster build-out:

  * Em-dashes / smart-quotes / control characters get mangled across the
    ssh+scp+powershell chain. ASCII-only payloads survive.
  * `ssh host 'mkdir foo'` fails on Windows OpenSSH unless quoted in a way
    PowerShell understands. Backslashes in paths need escaping too.
  * PowerShell command-line parsing eats quotes inconsistently. Encoding the
    full command with -EncodedCommand (UTF-16-LE base64) is far more reliable
    than building command strings.
  * sshd on Windows caches the environment at service start; long-running
    Mac-side ControlMaster sessions cache their own PATH too. After any
    PATH/env change on the remote, you have to BOTH restart sshd AND drop
    the Mac-side ControlMaster (`ssh -O exit <host>`).
"""
from __future__ import annotations

import base64
import os
import shlex
import subprocess
from pathlib import Path
from typing import Sequence


def encode_ps(script: str) -> str:
    """Encode a PowerShell script as UTF-16-LE base64.

    Pass the result with `powershell -NoProfile -EncodedCommand <result>` and
    you don't need to worry about quoting, em-dashes, or PowerShell-eating-
    your-backslashes. This is what fixed the cdec mkdir + cluster_status.py
    quoting bugs.
    """
    return base64.b64encode(script.encode("utf-16-le")).decode("ascii")


def ps(host: str, script: str, *, timeout: int = 45, capture: bool = True,
       silence_progress: bool = True,
       identity: str | None = None, user: str | None = None,
       connect_timeout: int = 8,
       no_control_master: bool = False,
       text: bool = True) -> subprocess.CompletedProcess:
    """Run a PowerShell script on a remote Windows host via SSH.

    Args:
        host: SSH alias OR full hostname/IP. If alias, must be in
              ~/.ssh/config (typical use). If hostname/IP, supply ``identity``
              and ``user`` explicitly.
        script: PowerShell script as a string. ASCII recommended; UTF-16 will
                be applied automatically via -EncodedCommand.
        timeout: subprocess timeout in seconds.
        capture: if False, stream output to the parent stdout/stderr.
        silence_progress: prepend `$ProgressPreference = 'SilentlyContinue'`
                so PowerShell doesn't dump CLIXML progress-record noise into
                stdout. On by default; set False if you actually want progress.
        identity: optional path to an SSH identity file. When passed, the
                  SSH command uses `-i <identity>` and prefixes the host with
                  ``user@`` if also provided. Lets callers reach hosts that
                  aren't in ~/.ssh/config.
        user:     optional SSH user. If both ``user`` and ``identity`` are
                  set, the SSH target becomes ``user@host``.
        connect_timeout: ConnectTimeout for SSH (default 8s; raise to 15-20s
                  for slow links like cdec WAN).
        no_control_master: if True, pass -o ControlPath=none to bypass any
                  ControlMaster session — useful when multi-second multiplex
                  saturation is causing timeouts.
        text:    if True (default), return text-mode (utf-8) stdout/stderr.
                 If False, return raw bytes (use this when remote output may
                 contain non-utf-8 like CLIXML progress runs).

    Returns the CompletedProcess. Caller checks .returncode + .stdout/.stderr.
    """
    if silence_progress:
        script = "$ProgressPreference = 'SilentlyContinue'; " + script
    encoded = encode_ps(script)
    ssh_opts = [
        "ssh",
        "-o", f"ConnectTimeout={connect_timeout}",
        "-o", "BatchMode=yes",
        "-o", "ServerAliveInterval=15",
    ]
    if no_control_master:
        ssh_opts += ["-o", "ControlPath=none"]
    # LAN-first routing (config-driven; Tailscale backup). No-op for raw IPs or
    # hosts without a reachable lan_host in hosts.json. See lib/routing.py.
    try:
        from lib import routing as _routing
        ssh_opts = ssh_opts + _routing.ssh_route_opts(host)
    except Exception:
        pass
    if identity:
        ssh_opts += ["-i", str(Path(identity).expanduser())]
    target = f"{user}@{host}" if (user and identity) else host
    args = ssh_opts + [
        target,
        "powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded,
    ]
    if capture:
        return subprocess.run(args, capture_output=True, text=text, timeout=timeout)
    return subprocess.run(args, timeout=timeout)


def mkdir_remote(host: str, *paths: str) -> None:
    """Create one or more directories on a remote Windows host.

    Uses PowerShell's New-Item -Force which is idempotent. Handles both
    forward- and back-slashed paths cleanly. Use this instead of:
        subprocess.run(["ssh", host, "mkdir", path])   # malformed on Windows
        subprocess.run(["ssh", host, "cmd /c mkdir foo"]) # quoting Russian roulette
    """
    if not paths:
        return
    lines = []
    for p in paths:
        # Normalize to forward slashes -- PowerShell accepts them on Windows
        normalized = p.replace("\\", "/")
        # Use single-quoted string in PowerShell to avoid all escaping
        lines.append(f"New-Item -ItemType Directory -Force -Path '{normalized}' | Out-Null")
    script = "; ".join(lines) + "; 'mkdir_remote: OK'"
    r = ps(host, script)
    if r.returncode != 0 or "mkdir_remote: OK" not in r.stdout:
        raise RuntimeError(
            f"mkdir_remote {host} {paths} failed: rc={r.returncode}\n"
            f"stderr: {r.stderr.strip()[:300]}\n"
            f"stdout: {r.stdout.strip()[:300]}"
        )


def file_exists_remote(host: str, path: str) -> bool:
    """Test whether a file or directory exists on a remote Windows host."""
    normalized = path.replace("\\", "/")
    r = ps(host, f"if (Test-Path '{normalized}') {{'YES'}} else {{'NO'}}")
    return r.returncode == 0 and "YES" in r.stdout


def scp_to(host: str, local: str | Path, remote: str) -> None:
    """scp a single file to a remote path. Creates parent dir on remote first."""
    remote_dir = remote.rsplit("/", 1)[0] if "/" in remote else remote.rsplit("\\", 1)[0]
    if remote_dir:
        mkdir_remote(host, remote_dir)
    r = subprocess.run(
        ["scp", "-q", str(local), f"{host}:{remote}"],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        raise RuntimeError(
            f"scp_to {host}:{remote} failed: rc={r.returncode}\n"
            f"stderr: {r.stderr.strip()[:300]}"
        )


def invalidate_controlmaster(host: str) -> None:
    """Drop the Mac-side SSH ControlMaster connection for `host`.

    Required after any PATH/env change on the remote -- otherwise the cached
    persistent connection keeps showing the old env. See `setup_windows_host`
    phase 3 + 8 for the matching remote-side fix (sshd restart).
    """
    subprocess.run(["ssh", "-O", "exit", host], capture_output=True)
    cm = Path.home() / ".ssh" / "cm"
    if cm.exists():
        for sock in cm.glob(f"*@{host}:*"):
            try:
                sock.unlink()
            except OSError:
                pass


def host_python_works(host: str) -> tuple[bool, str]:
    """Smoke-test that `python` is available on a remote Windows host SSH session.

    Returns (ok, diagnostic_string). If False, the diagnostic tells you which
    of the three Python-on-SSH lessons hasn't been applied (Store stub,
    machine-PATH, or sshd cache).
    """
    r = ps(host, r"""
$ErrorActionPreference = 'SilentlyContinue'
$py = (Get-Command python).Source
if (-not $py) { Write-Output 'NO_PYTHON'; return }
if ($py -like '*WindowsApps*') { Write-Output "STORE_STUB:$py"; return }
$v = (& python --version 2>&1 | Out-String).Trim()
Write-Output "OK|$py|$v"
""")
    lines = [l.strip() for l in (r.stdout or "").splitlines() if l.strip()]
    for line in lines:
        if line.startswith("OK|"):
            return True, line
        if line.startswith(("NO_PYTHON", "STORE_STUB:")):
            return False, line
    return False, (r.stderr.strip()[:200] or "no usable output")
