#!/usr/bin/env python3
"""Fail-closed resolution for the project data root.

The repository-root :file:`data_paths.json` is the sole path authority.  Its
logical paths remain ``data/...`` for stable manifests, while their physical
location is the verified external Toshiba volume.  There is deliberately no
environment-variable override and no local fallback: a missing, read-only, or
wrongly mounted volume raises before a caller can create a shadow ``data``
tree on the internal disk.
"""

from __future__ import annotations

import errno
import json
import os
import plistlib
import subprocess
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO_ROOT / "data_paths.json"
CONFIG_SCHEMA = "marketmaker_data_paths.v3"
IDENTITY_SCHEMA = "marketmaker_external_data_volume.v1"


class DataPathError(RuntimeError):
    """Base class for central data path policy failures."""


class DataPathConfigError(DataPathError):
    """The root path registry is missing, malformed, or unsafe."""


class ExternalDataVolumeError(DataPathError):
    """The configured external volume is absent, wrong, or unsafe to use."""


class UnregisteredDataPathError(DataPathError, KeyError):
    """A caller requested a dataset not declared in ``data_paths.json``."""


class MissingDataPathError(DataPathError, FileNotFoundError):
    """A registered dataset is not currently present on the data volume."""


class DataSymlinkError(DataPathError):
    """A configured path traverses a symlink, which policy forbids."""


_cache: dict[str, Any] | None = None
_verified_storage: dict[str, Any] | None = None
_cache_signature: tuple[int, int] | None = None


def _safe_logical_path(value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        raise DataPathConfigError(f"logical data path must be relative: {value}")
    if not path.parts or path.parts[0] != "data":
        raise DataPathConfigError(f"logical data path must be below data/: {value}")
    if any(part in {"", ".", ".."} for part in path.parts):
        raise DataPathConfigError(f"logical data path contains unsafe component: {value}")
    return path


# Kept as a compatibility name for callers and tests written against v2.
_safe_repo_relative = _safe_logical_path


def _safe_relative(value: str | Path, *, field: str) -> Path:
    path = Path(value)
    if path.is_absolute() or not path.parts:
        raise DataPathConfigError(f"{field} must be a non-empty relative path: {value}")
    if any(part in {"", ".", ".."} for part in path.parts):
        raise DataPathConfigError(f"{field} contains an unsafe component: {value}")
    return path


def _assert_no_symlink_components(path: Path, *, start: Path | None = None) -> None:
    absolute = path if path.is_absolute() else REPO_ROOT / path
    anchor = start if start is not None else Path(absolute.anchor)
    try:
        relative = absolute.relative_to(anchor)
    except ValueError as exc:
        raise DataPathConfigError(f"path {absolute} is outside policy anchor {anchor}") from exc
    current = anchor
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise DataSymlinkError(f"configured data path traverses symlink: {current}")


def _diskutil_info(mount_point: Path) -> dict[str, Any]:
    process = subprocess.run(
        ["diskutil", "info", "-plist", str(mount_point)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if process.returncode != 0:
        detail = process.stderr.decode(errors="replace").strip()
        raise ExternalDataVolumeError(
            f"external data volume is not mounted at {mount_point}: {detail or 'diskutil failed'}"
        )
    try:
        payload = plistlib.loads(process.stdout)
    except Exception as exc:  # plistlib raises several parse exception types.
        raise ExternalDataVolumeError(f"cannot parse diskutil identity for {mount_point}") from exc
    if not isinstance(payload, dict):
        raise ExternalDataVolumeError(f"unexpected diskutil identity for {mount_point}")
    return payload


def _validate_external_storage(
    payload: dict[str, Any], *, force: bool = False
) -> dict[str, Any]:
    global _verified_storage
    if payload.get("organization", {}).get("state") == "MIGRATING":
        raise ExternalDataVolumeError("Toshiba organization is in progress; new data access is paused until the path registry is published")
    if _verified_storage is not None and not force:
        return _verified_storage

    storage = payload.get("external_storage")
    if not isinstance(storage, dict):
        raise DataPathConfigError("external_storage must be a JSON object")
    mount_point = Path(str(storage.get("mount_point", "")))
    if not mount_point.is_absolute() or mount_point.parent != Path("/Volumes"):
        raise DataPathConfigError("external_storage.mount_point must be directly below /Volumes")
    data_relative = _safe_relative(
        str(storage.get("data_root_relative", "")), field="external_storage.data_root_relative"
    )
    marker_relative = _safe_relative(
        str(storage.get("identity_file", "")), field="external_storage.identity_file"
    )
    configured_root = Path(str(payload.get("data_root", "")))
    if not configured_root.is_absolute():
        raise DataPathConfigError("data_root must be an absolute external path")
    expected_root = mount_point / data_relative
    if configured_root != expected_root:
        raise DataPathConfigError(
            f"data_root must equal mount_point/data_root_relative: {expected_root}"
        )
    if not os.path.ismount(mount_point):
        raise ExternalDataVolumeError(
            f"refusing local shadow path: {mount_point} is not a mounted filesystem"
        )
    _assert_no_symlink_components(mount_point)

    info = _diskutil_info(mount_point)
    expected_uuid = str(storage.get("volume_uuid", ""))
    actual_uuid = str(info.get("VolumeUUID", ""))
    if actual_uuid != expected_uuid:
        raise ExternalDataVolumeError(
            f"wrong external volume UUID at {mount_point}: expected {expected_uuid}, got {actual_uuid}"
        )
    expected_filesystem = str(storage.get("filesystem", "")).lower()
    actual_filesystem = str(info.get("FilesystemType", "")).lower()
    if actual_filesystem != expected_filesystem:
        raise ExternalDataVolumeError(
            f"wrong filesystem at {mount_point}: expected {expected_filesystem}, got {actual_filesystem}"
        )
    expected_size = storage.get("device_size_bytes")
    if not isinstance(expected_size, int) or int(info.get("IOKitSize", -1)) != expected_size:
        raise ExternalDataVolumeError(
            f"wrong external device size at {mount_point}: expected {expected_size}, "
            f"got {info.get('IOKitSize')}"
        )
    if info.get("MountPoint") != str(mount_point):
        raise ExternalDataVolumeError(
            f"volume is mounted at an unexpected path: {info.get('MountPoint')!r}"
        )
    if info.get("WritableVolume") is not True:
        raise ExternalDataVolumeError(f"external data volume is not writable: {mount_point}")

    marker_path = mount_point / marker_relative
    _assert_no_symlink_components(marker_path, start=mount_point)
    if not marker_path.is_file():
        raise ExternalDataVolumeError(f"missing external volume identity marker: {marker_path}")
    try:
        marker = json.loads(marker_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ExternalDataVolumeError(f"cannot read external identity marker: {marker_path}") from exc
    required_marker = {
        "schema": IDENTITY_SCHEMA,
        "identity_token": storage.get("identity_token"),
        "volume_uuid": expected_uuid,
        "usb_serial": storage.get("usb_serial"),
        "data_root_relative": data_relative.as_posix(),
    }
    for key, expected in required_marker.items():
        if marker.get(key) != expected:
            raise ExternalDataVolumeError(
                f"external identity marker mismatch for {key}: expected {expected!r}, "
                f"got {marker.get(key)!r}"
            )
    _assert_no_symlink_components(configured_root, start=mount_point)
    if not configured_root.is_dir():
        raise ExternalDataVolumeError(f"configured external data root is missing: {configured_root}")

    _verified_storage = {
        "mount_point": mount_point,
        "data_root": configured_root,
        "marker_path": marker_path,
        "device_identifier": str(info.get("DeviceIdentifier", "")),
        "parent_whole_disk": str(info.get("ParentWholeDisk", "")),
        "volume_uuid": actual_uuid,
        "filesystem": actual_filesystem,
        "writable": True,
    }
    return _verified_storage


def _validate_config(payload: dict[str, Any], *, verify_storage: bool = True) -> dict[str, Any]:
    if payload.get("schema") != CONFIG_SCHEMA:
        raise DataPathConfigError(
            f"expected schema {CONFIG_SCHEMA!r}, got {payload.get('schema')!r}"
        )
    policy = payload.get("path_policy", {})
    if policy.get("allow_absolute_paths") is not True:
        raise DataPathConfigError("path_policy.allow_absolute_paths must be true")
    if policy.get("allow_environment_override") is not False:
        raise DataPathConfigError("path_policy.allow_environment_override must be false")
    if policy.get("allow_symlinks") is not False:
        raise DataPathConfigError("path_policy.allow_symlinks must be false")

    roots = payload.get("roots")
    datasets = payload.get("datasets")
    if not isinstance(roots, dict) or not isinstance(datasets, dict):
        raise DataPathConfigError("roots and datasets must be JSON objects")
    for name, value in roots.items():
        if not isinstance(name, str) or not isinstance(value, str):
            raise DataPathConfigError("root names and paths must be strings")
        _safe_logical_path(value)
    for name, entry in datasets.items():
        if not isinstance(name, str) or not isinstance(entry, dict):
            raise DataPathConfigError("dataset entries must be named JSON objects")
        path = _safe_logical_path(entry.get("path", ""))
        expected = Path("data") / Path(name)
        if path != expected:
            raise DataPathConfigError(
                f"dataset {name!r} path must be {expected}, got {path}"
            )
        if entry.get("state") not in {"local_directory", "missing_external"}:
            raise DataPathConfigError(f"dataset {name!r} has invalid state {entry.get('state')!r}")
    locations = payload.get("source_locations", {})
    physical_locations = payload.get("physical_locations", {})
    if not isinstance(physical_locations, dict):
        raise DataPathConfigError("physical_locations must be a JSON object")
    for logical, relative in physical_locations.items():
        _safe_logical_path(logical)
        _safe_relative(relative, field=f"physical_locations.{logical}")
    containers = payload.get('container_relocations', {})
    if not isinstance(containers, dict):
        raise DataPathConfigError('container_relocations must be a JSON object')
    for old, new in containers.items():
        _safe_relative(old, field='container_relocations source')
        _safe_relative(new, field='container_relocations destination')
    relocations = payload.get("path_relocations", {})
    if not isinstance(relocations, dict):
        raise DataPathConfigError("path_relocations must be a JSON object")
    for old, new in relocations.items():
        _safe_relative(old, field="path_relocations source")
        _safe_relative(new, field="path_relocations destination")
    if not isinstance(locations, dict):
        raise DataPathConfigError("source_locations must be a JSON object")
    for name in locations:
        _source_location_path(payload, name)
    if verify_storage:
        _validate_external_storage(payload)
    return payload


def load_data_paths(
    *, force_reload: bool = False, verify_storage: bool = True
) -> dict[str, Any]:
    """Load the root registry and, by default, verify the physical volume."""
    global _cache, _verified_storage, _cache_signature
    try:
        config_stat = CONFIG_PATH.stat()
        signature = (config_stat.st_mtime_ns, config_stat.st_size)
    except FileNotFoundError as exc:
        raise DataPathConfigError(f"missing root data path config: {CONFIG_PATH}") from exc
    if signature != _cache_signature:
        force_reload = True
    if force_reload:
        _cache = None
        _verified_storage = None
    if _cache is not None:
        if verify_storage:
            _validate_external_storage(_cache)
        return _cache
    if not CONFIG_PATH.is_file():
        raise DataPathConfigError(f"missing root data path config: {CONFIG_PATH}")
    try:
        payload = json.loads(CONFIG_PATH.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise DataPathConfigError(f"cannot read {CONFIG_PATH}: {exc}") from exc
    _cache = _validate_config(payload, verify_storage=verify_storage)
    _cache_signature = signature
    return _cache


def ensure_external_storage(*, force: bool = False) -> dict[str, Any]:
    """Return verified volume identity or raise without falling back locally."""
    config = load_data_paths(force_reload=force, verify_storage=False)
    return dict(_validate_external_storage(config, force=force))


def configured_data_root(*, verify_storage: bool = True) -> Path:
    config = load_data_paths(verify_storage=verify_storage)
    return Path(config["data_root"])


def _mapped_physical_path(config: dict[str, Any], logical: Path) -> Path:
    """Resolve the most specific explicit storage mapping, without substituting data."""
    logical = _safe_logical_path(logical)
    mappings = config.get("physical_locations", {})
    for ancestor in (logical, *logical.parents):
        target = mappings.get(ancestor.as_posix())
        if target is not None:
            suffix = logical.relative_to(ancestor)
            relative = _safe_relative(target, field=f"physical_locations.{ancestor}")
            return Path(config["external_storage"]["mount_point"]) / relative / suffix
    return Path(config["data_root"]).joinpath(*logical.parts[1:])


def resolve_data_path(relative: str | Path, *, require_exists: bool = False) -> Path:
    """Resolve a logical data file/directory, including explicitly relocated sources."""
    path = Path(relative)
    logical = path if path.parts and path.parts[0] == "data" else Path("data") / path
    physical = _physical_from_logical(logical)
    if require_exists and not physical.exists():
        raise MissingDataPathError(f"configured data path is missing: {physical}")
    return physical


def resolve_relocated_path(path: str | Path, *, require_exists: bool = False) -> Path:
    """Translate a retained historical Toshiba path through the explicit move ledger.

    Historical receipts and sealed source bytes are not rewritten. This function
    never falls back to a different source and rejects recreated old-path shadows.
    """
    config = load_data_paths()
    mount = Path(config["external_storage"]["mount_point"])
    original = Path(path)
    absolute = original if original.is_absolute() else mount / _safe_relative(original, field="historical source")
    try:
        relative = absolute.relative_to(mount)
    except ValueError as exc:
        raise DataPathConfigError("historical source is outside the configured volume") from exc
    _safe_relative(relative, field="historical source")
    physical = absolute
    mappings = {**config.get('container_relocations', {}), **config.get('path_relocations', {})}
    for ancestor in (relative, *relative.parents):
        target = mappings.get(ancestor.as_posix())
        if target is not None:
            physical = mount / _safe_relative(target, field="relocated destination") / relative.relative_to(ancestor)
            if physical != absolute and absolute.exists():
                raise DataPathError(f"old source path was recreated after relocation: {absolute}")
            break
    _assert_no_symlink_components(physical, start=mount)
    if require_exists and not physical.exists():
        raise MissingDataPathError(f"relocated source is missing: {physical}")
    return physical


def resolve_storage_reference(path: str | Path, *, require_exists: bool = False) -> Path:
    """Resolve an explicit data reference; leave ordinary repository paths alone.

    This IO boundary preserves the original metadata and content checksums.
    Call it on the complete path, after joining any relative filename, so a
    source extracted from a larger directory receives its most specific mapping.
    """
    original = Path(path)
    config = load_data_paths(verify_storage=False)
    mount = Path(config['external_storage']['mount_point'])
    if original.is_absolute() and original.is_relative_to(mount):
        return resolve_relocated_path(original, require_exists=require_exists)
    if not original.is_absolute() and original.parts and original.parts[0] in {'marketmaker', 'marketmaker_v2', 'macroeconomics'}:
        return resolve_relocated_path(original, require_exists=require_exists)
    if not original.is_absolute() and original.parts and original.parts[0] == 'data':
        return resolve_data_path(original, require_exists=require_exists)
    for root in (REPO_ROOT, REPO_ROOT.parent / 'marketmaker', REPO_ROOT.parent / 'marketmaker_v2'):
        if original.is_absolute() and original.is_relative_to(root / 'data'):
            return resolve_data_path(original.relative_to(root), require_exists=require_exists)
    if require_exists and not original.exists():
        raise MissingDataPathError(f'referenced file is missing: {original}')
    return original


def resolve_manifest_reference(value: str | Path, manifest: str | Path) -> Path:
    """Resolve a manifest-relative filename across a directory split.

    Expand a relative reference in the manifest's original namespace before
    applying the forward relocation. Current manifest paths are reverse-mapped
    only through the verified move prefixes, without choosing another source.
    """
    reference, base = Path(value), Path(manifest)
    if reference.is_absolute():
        return resolve_storage_reference(reference)
    config = load_data_paths(verify_storage=False)
    mount = Path(config['external_storage']['mount_point'])
    if base.is_absolute() and base.is_relative_to(mount):
        relative = base.relative_to(mount)
        inverse = {}
        for old, new in config.get('path_relocations', {}).items():
            if new in inverse and inverse[new] != old:
                raise DataPathConfigError('ambiguous reverse relocation for manifest reference')
            inverse[new] = old
        for ancestor in (relative, *relative.parents):
            old = inverse.get(ancestor.as_posix())
            if old is not None:
                base = mount / old / relative.relative_to(ancestor)
                break
        joined = Path(os.path.normpath(base.parent / reference))
        if not joined.is_relative_to(mount):
            raise DataPathConfigError('manifest reference escapes the verified data volume')
        return resolve_storage_reference(joined)
    return resolve_storage_reference(base.parent / reference)


def _source_location_path(config: dict[str, Any], name: str) -> Path:
    """Resolve a registry identifier without IO; archive roots may be beside data/."""
    try:
        entry = config["source_locations"][name]
    except KeyError as exc:
        raise UnregisteredDataPathError(f"unregistered source location: {name}") from exc
    if not isinstance(name, str) or not name or not isinstance(entry, dict):
        raise DataPathConfigError("source locations require named JSON objects")
    if set(entry) == {"dataset"}:
        try:
            logical = _safe_logical_path(config["datasets"][entry["dataset"]]["path"])
        except (KeyError, TypeError) as exc:
            raise DataPathConfigError(f"unknown dataset for source location: {name}") from exc
        return _mapped_physical_path(config, logical)
    if set(entry) == {"root", "relative"}:
        try:
            logical = _safe_logical_path(config["roots"][entry["root"]])
        except (KeyError, TypeError) as exc:
            raise DataPathConfigError(f"unknown root for source location: {name}") from exc
        suffix = _safe_relative(entry["relative"], field=f"source_locations.{name}.relative")
        return _mapped_physical_path(config, logical / suffix)
    if set(entry) == {"mount_relative"}:
        suffix = _safe_relative(entry["mount_relative"], field=f"source_locations.{name}.mount_relative")
        return Path(config["external_storage"]["mount_point"]) / suffix
    raise DataPathConfigError(f"source location {name} requires dataset, root/relative, or mount_relative")


def resolve_source_location(name: str, *, require_exists: bool = False) -> Path:
    """Resolve a central source identifier on the verified external volume."""
    config = load_data_paths()
    physical = _source_location_path(config, name)
    mount = Path(config["external_storage"]["mount_point"])
    try:
        physical.relative_to(mount)
    except ValueError as exc:
        raise DataPathConfigError(f"source location is outside configured storage: {name}") from exc
    _assert_no_symlink_components(physical, start=mount)
    if require_exists and not physical.is_dir():
        raise MissingDataPathError(f"source location is missing: {name}: {physical}")
    return physical


def _physical_from_logical(logical: Path) -> Path:
    logical = _safe_logical_path(logical)
    physical = _mapped_physical_path(load_data_paths(), logical)
    _assert_no_symlink_components(physical, start=Path(load_data_paths()["external_storage"]["mount_point"]))
    return physical


def resolve_path(
    name: str,
    *,
    absolute: bool = True,
    create: bool = False,
    require_exists: bool = False,
) -> Path:
    """Resolve a named root to its verified physical external path.

    ``absolute`` remains accepted for compatibility, but v3 intentionally
    always returns an absolute path so no caller can silently write locally.
    """
    del absolute
    config = load_data_paths()
    try:
        logical = _safe_logical_path(config["roots"][name])
    except KeyError as exc:
        raise UnregisteredDataPathError(f"unregistered data root: {name}") from exc
    physical = _physical_from_logical(logical)
    if create:
        physical.mkdir(parents=True, exist_ok=True)
        _fsync_directory(physical.parent)
    if require_exists and not physical.is_dir():
        raise MissingDataPathError(f"configured data root is missing: {physical}")
    return physical


def dataset_entry(relative: str | Path) -> dict[str, Any]:
    """Return a copy of one registered dataset entry."""
    key_path = Path(relative)
    if key_path.parts and key_path.parts[0] == "data":
        key_path = Path(*key_path.parts[1:])
    key = key_path.as_posix()
    try:
        return dict(load_data_paths()["datasets"][key])
    except KeyError as exc:
        raise UnregisteredDataPathError(
            f"{key!r} is not registered in {CONFIG_PATH.name}"
        ) from exc


def resolve_data_dir(
    relative: str | Path,
    *,
    absolute: bool = True,
    require_exists: bool = False,
) -> Path:
    """Resolve one registered dataset directory on the verified volume."""
    del absolute
    entry = dataset_entry(relative)
    physical = _physical_from_logical(_safe_logical_path(entry["path"]))
    if require_exists and not physical.is_dir():
        state = entry.get("state", "unknown")
        raise MissingDataPathError(
            f"registered dataset is unavailable ({state}): {physical}"
        )
    return physical


def iter_registered_datasets() -> Iterator[tuple[str, dict[str, Any]]]:
    for key, entry in load_data_paths()["datasets"].items():
        yield key, dict(entry)


def audit_data_paths() -> dict[str, Any]:
    """Report config/filesystem agreement on the verified external root."""
    config = load_data_paths(force_reload=True)
    symlinks: list[str] = []
    missing_local: list[str] = []
    unexpected_present: list[str] = []
    for key, entry in config["datasets"].items():
        logical = _safe_logical_path(entry["path"])
        physical = _physical_from_logical(logical)
        if physical.is_symlink():
            symlinks.append(logical.as_posix())
        elif entry["state"] == "local_directory" and not physical.is_dir():
            missing_local.append(logical.as_posix())
        elif entry["state"] == "missing_external" and physical.exists():
            unexpected_present.append(logical.as_posix())
    storage = ensure_external_storage()
    return {
        "schema": "marketmaker_data_path_audit.v2",
        "config": str(CONFIG_PATH.relative_to(REPO_ROOT)),
        "physical_data_root": str(storage["data_root"]),
        "volume_uuid": storage["volume_uuid"],
        "registered_datasets": len(config["datasets"]),
        "symlinks": sorted(symlinks),
        "missing_local": sorted(missing_local),
        "unexpected_present": sorted(unexpected_present),
        "ok": not symlinks and not missing_local and not unexpected_present,
    }


def _fsync_directory(path: Path) -> None:
    try:
        descriptor = os.open(path, os.O_RDONLY)
    except OSError as exc:
        if exc.errno in {errno.EINVAL, errno.ENOTSUP, errno.EACCES}:
            return
        raise
    try:
        try:
            os.fsync(descriptor)
        except OSError as exc:
            if exc.errno not in {errno.EINVAL, errno.ENOTSUP, errno.EBADF}:
                raise
    finally:
        os.close(descriptor)


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    """Write JSON through a same-directory file, fsync, and atomic rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    encoded = (json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n").encode()
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    descriptor = os.open(temporary, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(descriptor)
    temporary.replace(path)
    _fsync_directory(path.parent)


@contextmanager
def local_job_lock(lock_path: str | Path, *, stale_seconds: int = 6 * 60 * 60) -> Iterator[None]:
    """Serialize data jobs using a lock below the verified external root."""
    lock = Path(lock_path)
    config = load_data_paths()
    data_root = configured_data_root()
    if not lock.is_absolute():
        logical = _safe_logical_path(lock)
        lock = _physical_from_logical(logical)
    mount = Path(config["external_storage"]["mount_point"])
    allowed = [data_root, *(mount / value for value in config.get("physical_locations", {}).values())]
    if not any(lock.is_relative_to(root) for root in allowed):
        raise DataPathError(f"job lock must be below a configured storage root: {lock}")
    _safe_relative(lock.relative_to(mount), field="job lock")
    _assert_no_symlink_components(
        lock, start=Path(load_data_paths()["external_storage"]["mount_point"])
    )
    lock.parent.mkdir(parents=True, exist_ok=True)
    now = time.time()
    if lock.exists():
        age = now - lock.stat().st_mtime
        if age > stale_seconds:
            lock.unlink()
        else:
            raise DataPathError(f"data job lock is active: {lock} age={age:.0f}s")
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w") as handle:
            handle.write(
                json.dumps(
                    {
                        "pid": os.getpid(),
                        "created_at_utc": datetime.now(timezone.utc).isoformat(),
                        "volume_uuid": load_data_paths()["external_storage"]["volume_uuid"],
                    }
                )
                + "\n"
            )
            handle.flush()
            os.fsync(handle.fileno())
        yield
    finally:
        try:
            lock.unlink()
            _fsync_directory(lock.parent)
        except FileNotFoundError:
            pass


# Active code imports this constant.  Importing it verifies the mount first,
# which prevents disconnected jobs from creating a look-alike /Volumes path.
CONFIGURED_DATA_ROOT = configured_data_root()


__all__ = [
    "CONFIG_PATH",
    "CONFIG_SCHEMA",
    "CONFIGURED_DATA_ROOT",
    "IDENTITY_SCHEMA",
    "REPO_ROOT",
    "DataPathError",
    "DataPathConfigError",
    "ExternalDataVolumeError",
    "UnregisteredDataPathError",
    "MissingDataPathError",
    "DataSymlinkError",
    "audit_data_paths",
    "configured_data_root",
    "dataset_entry",
    "ensure_external_storage",
    "iter_registered_datasets",
    "load_data_paths",
    "local_job_lock",
    "resolve_data_dir",
    "resolve_data_path",
    "resolve_path",
    "resolve_relocated_path",
    "resolve_storage_reference",
    "resolve_manifest_reference",
    "resolve_source_location",
    "write_json_atomic",
]
