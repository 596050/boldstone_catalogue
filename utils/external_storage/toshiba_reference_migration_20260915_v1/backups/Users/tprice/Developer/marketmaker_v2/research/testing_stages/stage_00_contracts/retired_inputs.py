"""Reject retired short-history data by location and by content identity.

The registry is part of every experiment identity. It does not ban calendar
observations within a longer source, and never edits a raw price file.
"""
import json
from functools import lru_cache
from pathlib import Path

REGISTRY = Path(__file__).resolve().parents[1] / 'configs/RETIRED_INPUTS.json'


@lru_cache(maxsize=4)
def _read(path, modified, size):
    value = json.loads(Path(path).read_text())
    if value.get('schema') != 'marketmaker.retired_backtest_inputs.v1':
        raise ValueError('invalid retired input registry')
    return value


def registry():
    stat = REGISTRY.stat()
    return _read(str(REGISTRY), stat.st_mtime_ns, stat.st_size)


def require_path(path):
    resolved = Path(path).resolve()
    for prefix in registry()['path_prefixes']:
        p = Path(prefix).resolve()
        if resolved == p or p in resolved.parents:
            raise ValueError('RETIRED_BACKTEST_INPUT: shortened-history input is disabled: ' + str(path))


def require_hash(value):
    if value in registry()['sha256']:
        raise ValueError('RETIRED_BACKTEST_INPUT: retired input content cannot be reused under another name')
