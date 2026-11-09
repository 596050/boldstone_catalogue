#!/usr/bin/env python3
"""remote_ps — run a PowerShell script on a remote Windows host without ANY of
the SSH/PowerShell/cmd quoting bugs (em-dashes, $_ getting eaten by zsh,
backslash escaping, smart-quotes, nested quotes).

Usage:
    remote_ps.py <host> '<powershell script>'
    cat script.ps1 | remote_ps.py <host>
    remote_ps.py <host> -f script.ps1
    remote_ps.py <host> --timeout 60 '<script>'

Examples:
    # Process liveness (the recurring $_ bug)
    remote_ps.py kenne 'Get-Process -Id 37792,11576 -ErrorAction SilentlyContinue
                        | Select-Object Id,ProcessName,CPU,StartTime
                        | Format-Table -AutoSize'

    # Stderr dump with ForEach-Object { $_... } (also the $_ bug)
    remote_ps.py kenne 'Get-ChildItem C:/path -Filter *.stderr.log
                        | ForEach-Object { Write-Host ("--- " + $_.Name); Get-Content $_.FullName }'

    # mkdir (the cdec malformed-mkdir bug)
    remote_ps.py kenne 'New-Item -ItemType Directory -Force -Path "C:/Users/Kenneth/Downloads/foo"'

How it works:
    Encodes the script as UTF-16-LE base64 and ships it via
    `powershell -EncodedCommand <b64>`. That single change skips every
    quoting layer (Mac shell, ssh, Windows command interpreter, PowerShell
    parser). What you write is what PowerShell sees.
"""
from __future__ import annotations
import argparse
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from lib import remote  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("host", help="SSH alias (must be in ~/.ssh/config)")
    p.add_argument("script", nargs="?", default=None,
                    help="PowerShell script (use single quotes on your shell side, "
                         "or pass -f / pipe via stdin)")
    p.add_argument("-f", "--file", default=None,
                    help="Read script from this file instead of arg/stdin")
    p.add_argument("--timeout", type=int, default=120, help="Seconds (default 120)")
    p.add_argument("--no-capture", action="store_true",
                    help="Stream output directly instead of capturing")
    args = p.parse_args()

    if args.file:
        script = pathlib.Path(args.file).read_text()
    elif args.script is not None:
        script = args.script
    elif not sys.stdin.isatty():
        script = sys.stdin.read()
    else:
        p.print_help(sys.stderr)
        return 2

    try:
        r = remote.ps(args.host, script, timeout=args.timeout, capture=not args.no_capture)
    except subprocess.TimeoutExpired:
        # The local ssh process is killed by subprocess on timeout, but the
        # remote PowerShell may STILL be executing (sshd doesn't see the
        # disconnect immediately, and even when it does, child processes can
        # be reparented). Make the recovery deterministic:
        #   1) Drop the Mac-side ControlMaster so the next call gets a fresh
        #      tunnel instead of inheriting a half-dead connection.
        #   2) Tell the operator EXACTLY how to check / kill on the remote.
        remote.invalidate_controlmaster(args.host)
        print(
            f"remote_ps: TIMEOUT after {args.timeout}s on {args.host}.\n"
            f"  Mac-side ControlMaster invalidated; next ssh will reconnect cleanly.\n"
            f"  The remote PowerShell process may STILL BE RUNNING. To check / kill:\n"
            f"    ./remote_ps.py {args.host} \\\n"
            f"        'Get-Process powershell,pwsh -ErrorAction SilentlyContinue | \\\n"
            f"           Select Id,StartTime,CPU,Path | Format-Table -AutoSize'\n"
            f"    ./remote_ps.py {args.host} 'Stop-Process -Id <PID> -Force'\n"
            f"  Bigger hammer (everything but the SSH daemon):\n"
            f"    ./remote_ps.py {args.host} \\\n"
            f"        'Get-Process powershell,pwsh,python | Stop-Process -Force'\n",
            file=sys.stderr,
        )
        return 124  # GNU `timeout`-style exit code

    if not args.no_capture:
        if r.stdout:
            sys.stdout.write(r.stdout)
        if r.stderr:
            sys.stderr.write(r.stderr)
    return r.returncode


if __name__ == "__main__":
    sys.exit(main())
