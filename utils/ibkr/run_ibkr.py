#!/usr/bin/env python3
"""Non-routing legacy entrypoint after removal of automatic broker jobs."""

from __future__ import annotations

import sys


MESSAGE = (
    "The generic IBKR launcher is intentionally non-routing. "
    "Automatic broker jobs were removed. "
    "Manual provider startup utilities are under utils/ibkr in marketmaker_v2."
)


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
