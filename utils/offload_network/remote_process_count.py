#!/usr/bin/env python3
"""Count remote Windows processes whose command line matches a wildcard.

This is a small helper for offload waiters. A naive PowerShell command such as:

    Get-CimInstance Win32_Process | ? CommandLine -like "*needle*"

can count its own query process because the wildcard appears in the query's
CommandLine. This helper builds an encoded PowerShell command and filters out
the current PowerShell process plus command lines containing the query text.
"""
from __future__ import annotations

import argparse
import base64
import subprocess
import sys


def _ps_single_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _encoded_powershell(
    pattern: str,
    list_rows: bool,
    name_like: str | None = None,
) -> str:
    pattern_literal = _ps_single_quote(pattern)
    name_filter = ""
    if name_like:
        name_filter = f"\n    $_.Name -like {_ps_single_quote(name_like)} -and"
    if list_rows:
        output = (
            "$rows | Select-Object ProcessId,Name,CommandLine | "
            "ConvertTo-Json -Depth 3"
        )
    else:
        output = "($rows | Measure-Object).Count"
    command = f"""
$pattern = {pattern_literal}
$rows = Get-CimInstance Win32_Process | Where-Object {{
    {name_filter}
    $_.CommandLine -like $pattern -and
    $_.ProcessId -ne $PID -and
    $_.CommandLine -notlike '*Get-CimInstance Win32_Process*' -and
    $_.CommandLine -notlike '*remote_process_count*'
}}
{output}
"""
    return base64.b64encode(command.encode("utf-16le")).decode("ascii")


def count_remote_processes(
    host: str,
    pattern: str,
    list_rows: bool = False,
    name_like: str | None = None,
) -> int:
    encoded = _encoded_powershell(pattern, list_rows=list_rows, name_like=name_like)
    proc = subprocess.run(
        ["ssh", host, "powershell.exe", "-NoProfile", "-EncodedCommand", encoded],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
        raise SystemExit(proc.returncode)
    if list_rows:
        print(proc.stdout.rstrip())
        return 0
    text = proc.stdout.strip()
    return int(text or "0")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("host")
    parser.add_argument("pattern", help="PowerShell -like wildcard pattern")
    parser.add_argument("--list", action="store_true", help="print matching rows as JSON")
    parser.add_argument(
        "--name-like",
        help=(
            "Optional Win32_Process.Name wildcard, e.g. 'python*'. This avoids "
            "counting PowerShell/cmd wrappers when only the worker process matters."
        ),
    )
    args = parser.parse_args(argv)

    count = count_remote_processes(
        args.host,
        args.pattern,
        list_rows=args.list,
        name_like=args.name_like,
    )
    if not args.list:
        print(count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
