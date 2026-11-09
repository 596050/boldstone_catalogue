#!/usr/bin/env python3
"""Deprecated compatibility view of the root-level data path registry."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from utils.data_paths import (
    CONFIG_PATH,
    CONFIGURED_DATA_ROOT,
    audit_data_paths,
    load_data_paths,
    resolve_data_path,
)


MANIFEST_PATH = CONFIG_PATH
DEFAULT_SCAN_ROOTS = ("data",)


@dataclass(frozen=True)
class ManifestEntry:
    repo_path: str
    external_target: str
    target_exists: bool

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def generate_manifest(
    scan_roots: tuple[str, ...] = DEFAULT_SCAN_ROOTS,
    external_root: str | Path | None = None,
) -> list[ManifestEntry]:
    del scan_roots
    if external_root is not None and Path(external_root) != CONFIGURED_DATA_ROOT.parent:
        raise RuntimeError("external root overrides are disabled")
    entries = []
    for _key, value in load_data_paths()["datasets"].items():
        logical = Path(value["path"])
        physical = resolve_data_path(logical)
        entries.append(
            ManifestEntry(
                repo_path=logical.as_posix(),
                external_target=str(physical),
                target_exists=physical.is_dir(),
            )
        )
    return sorted(entries, key=lambda entry: entry.repo_path)


def write_manifest(
    entries: list[ManifestEntry], external_root: str | Path | None = None
) -> None:
    del entries, external_root
    raise RuntimeError(
        "the legacy external-storage manifest is retired; data_paths.json is authoritative"
    )


def load_manifest() -> dict[str, Any]:
    entries = generate_manifest()
    return {
        "schema": "marketmaker_external_storage_manifest_compat.v2",
        "authority": str(CONFIG_PATH),
        "external_root": str(CONFIGURED_DATA_ROOT),
        "count": len(entries),
        "entries": [entry.as_dict() for entry in entries],
    }


def is_externalized(repo_path: str | Path) -> bool:
    candidate = Path(repo_path)
    if not candidate.parts or candidate.parts[0] != "data":
        return False
    return resolve_data_path(candidate).exists()


def verify_manifest() -> dict[str, Any]:
    audit = audit_data_paths()
    return {
        "checked": audit["registered_datasets"],
        "broken": [
            *({"problem": "symlink", "path": path} for path in audit["symlinks"]),
            *({"problem": "missing", "path": path} for path in audit["missing_local"]),
            *(
                {"problem": "unexpected_present", "path": path}
                for path in audit["unexpected_present"]
            ),
        ],
        "ok": audit["ok"],
        "authority": str(CONFIG_PATH),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--generate", action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args(argv)
    if args.generate:
        print("legacy manifest generation is retired; data_paths.json is authoritative")
        return 2
    result = verify_manifest()
    print(f"checked {result['checked']} entries, {len(result['broken'])} broken")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
