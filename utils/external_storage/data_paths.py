#!/usr/bin/env python3
"""Deprecated compatibility layer over :mod:`utils.data_paths`.

There is no second registry. The repository-root ``data_paths.json`` is the
only authority and all returned paths are verified absolute external paths.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from utils.data_paths import (
    CONFIG_PATH,
    iter_registered_datasets,
    load_data_paths,
    resolve_data_dir as _resolve_data_dir,
)


REGISTRY_PATH = CONFIG_PATH
DEFAULT_SCAN_ROOTS = tuple(load_data_paths()["dataset_scan_roots"])


def generate_registry(
    scan_roots: tuple[str, ...] = DEFAULT_SCAN_ROOTS,
) -> dict[str, dict[str, Any]]:
    del scan_roots
    return {
        entry["path"]: {
            "repo_path": entry["path"],
            "state": entry["state"],
            "externalized": entry["state"] == "local_directory",
        }
        for _key, entry in iter_registered_datasets()
    }


def write_registry(directories: dict[str, dict[str, Any]]) -> None:
    del directories
    raise RuntimeError(
        "the legacy data registry is retired; update data_paths.json with "
        "scripts/build_data_paths_config.py"
    )


def load_registry(*, force_reload: bool = False) -> dict[str, Any]:
    load_data_paths(force_reload=force_reload)
    directories = generate_registry()
    return {
        "schema": "marketmaker_data_directory_registry_compat.v2",
        "count": len(directories),
        "directories": directories,
        "authority": str(CONFIG_PATH),
    }


def resolve_data_dir(relative: str | Path) -> Path:
    return _resolve_data_dir(relative)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--generate", action="store_true")
    args = parser.parse_args(argv)
    if args.generate:
        print(
            "legacy registry generation is retired; "
            "run scripts/build_data_paths_config.py --check"
        )
        return 2
    registry = load_registry()
    print(f"{registry['count']} entries in {registry['authority']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
