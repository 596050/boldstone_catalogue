"""Allow `python -m fleet` invocation.

Delegates to the legacy utils/offload_network/fleet.py entrypoint
(which still owns argparse + all subcommand dispatch). Once the per-command
modules under fleet.commands.* land, this will be rewritten to dispatch
directly.
"""
import pathlib
import runpy
import sys


def main() -> int:
    # Delegate to the legacy fleet.py script — runs it as __main__ with
    # the same argv. This preserves every existing subcommand without
    # duplicating argparse.
    legacy_fleet_py = pathlib.Path(__file__).resolve().parent.parent / "fleet.py"
    if not legacy_fleet_py.exists():
        print(f"fleet.py not found at {legacy_fleet_py}", file=sys.stderr)
        return 1
    runpy.run_path(str(legacy_fleet_py), run_name="__main__")
    return 0


if __name__ == "__main__":
    sys.exit(main())
