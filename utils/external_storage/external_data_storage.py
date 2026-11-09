#!/usr/bin/env python3
"""Compatibility wrappers for the root-level external data configuration.

The former implementation supported environment overrides and repository
symlinks. Both mechanisms are retired. New code should import
``utils.data_paths`` directly; these names remain only so frozen callers fail
closed or resolve through the same verified configuration.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from utils.data_paths import (
    CONFIGURED_DATA_ROOT,
    REPO_ROOT,
    ensure_external_storage,
    local_job_lock,
    resolve_data_path,
    write_json_atomic as _write_json_atomic,
)


EXTERNAL_DATA_ROOT_ENV = "MARKETMAKER_EXTERNAL_DATA_ROOT"
ALT_EXTERNAL_DATA_ROOT_ENV = "IB_GATEWAY_EXTERNAL_DATA_ROOT"
DEFAULT_EXTERNAL_DATA_ROOT = CONFIGURED_DATA_ROOT.parent


def resolve_external_data_root(value: str | Path | None = None) -> Path:
    """Return the configured external project root; reject every override."""
    configured = DEFAULT_EXTERNAL_DATA_ROOT
    candidates = [value, os.environ.get(EXTERNAL_DATA_ROOT_ENV), os.environ.get(ALT_EXTERNAL_DATA_ROOT_ENV)]
    for candidate in candidates:
        if candidate is not None and Path(candidate).expanduser() != configured:
            raise RuntimeError(
                f"external data root overrides are disabled; configured root is {configured}"
            )
    ensure_external_storage()
    return configured


def external_drive_status(root: str | Path | None = None) -> dict[str, Any]:
    resolved = resolve_external_data_root(root)
    storage = ensure_external_storage(force=True)
    return {
        "external_root": str(resolved),
        "data_root": str(storage["data_root"]),
        "volume_uuid": storage["volume_uuid"],
        "filesystem": storage["filesystem"],
        "root_exists": resolved.is_dir(),
        "root_is_symlink": resolved.is_symlink(),
        "root_writable": storage["writable"],
        "environment_overrides_allowed": False,
    }


def repo_relative(path: str | Path) -> Path:
    candidate = Path(path).expanduser()
    absolute = candidate if candidate.is_absolute() else (Path.cwd() / candidate)
    try:
        return absolute.absolute().relative_to(REPO_ROOT)
    except ValueError as exc:
        raise ValueError(f"path {path!s} is not inside repository root {REPO_ROOT}") from exc


def external_target_for_repo_path(
    repo_path: str | Path, external_root: str | Path | None = None
) -> Path:
    resolve_external_data_root(external_root)
    relative = repo_relative(repo_path)
    if not relative.parts or relative.parts[0] != "data":
        raise ValueError(f"only logical data/ paths are externally managed: {repo_path}")
    return resolve_data_path(relative)


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    _write_json_atomic(path, payload)


@dataclass(frozen=True)
class ExternalizeResult:
    repo_path: str
    external_target: str
    status: str
    actions: list[str]
    copied_files: int = 0
    backup_path: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "repo_path": self.repo_path,
            "external_target": self.external_target,
            "status": self.status,
            "actions": self.actions,
            "copied_files": int(self.copied_files),
            "backup_path": self.backup_path,
        }


def externalize_directory(
    repo_dir: str | Path,
    *,
    external_root: str | Path | None = None,
    move_existing: bool = False,
    dry_run: bool = False,
) -> ExternalizeResult:
    """Reject the retired copy-and-symlink workflow.

    The whole data root is already external. Per-directory externalization,
    local backups, environment roots, and symlink creation are forbidden.
    """
    del move_existing, dry_run
    target = external_target_for_repo_path(repo_dir, external_root)
    raise RuntimeError(
        "per-directory externalization is retired; use data_paths.json and "
        f"the configured target {target}"
    )


@contextmanager
def external_job_lock(
    lock_path: str | Path, *, stale_seconds: int = 6 * 60 * 60
) -> Iterator[None]:
    with local_job_lock(lock_path, stale_seconds=stale_seconds):
        yield
