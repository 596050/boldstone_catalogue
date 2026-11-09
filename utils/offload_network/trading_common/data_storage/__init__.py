"""External-drive storage helpers.

Single point of truth for the external-drive layout used by the
multi-strategy harness:

    /Volumes/Untitled/famous_model/live_data/
    ├── iqfeed_data/<inst>_ig_production/  — raw 1-min bar files
    └── c_emd/results/incremental_emd_caches/<full>.h5 — HDF5 EMD caches

Public surface:
    from trading_common.data_storage import (
        EXTERNAL_DRIVE, IQFEED_BARS_DIR, EMD_CACHE_DIR,
        external_drive_mounted, sync_bars_to_external,
        sync_emd_cache_to_external, sync_from_external,
        atomic_publish_file, staged_publish_directory,
    )
"""
from .layout import (  # noqa: F401
    DataLayout,
    configured_data_root,
    configured_work_root,
    generation_id,
)
from .mount_health import (  # noqa: F401
    DataRootHealth,
    MountInfo,
    ProcessSnapshot,
    assess_data_root,
    external_health_payload,
    format_health,
    mount_for_path,
    parse_mount_output,
    process_snapshot_for_path,
)

__all__ = [
    "DataLayout",
    "configured_data_root",
    "configured_work_root",
    "generation_id",
    "DataRootHealth",
    "MountInfo",
    "ProcessSnapshot",
    "assess_data_root",
    "external_health_payload",
    "format_health",
    "mount_for_path",
    "parse_mount_output",
    "process_snapshot_for_path",
    "EMD_CACHE_DIR",
    "EXTERNAL_DRIVE",
    "IQFEED_BARS_DIR",
    "external_drive_mounted",
    "sync_bars_to_external",
    "sync_emd_cache_to_external",
    "sync_from_external",
    "atomic_publish_file",
    "staged_publish_directory",
]

_EXTERNAL_DRIVE_EXPORTS = {
    "EMD_CACHE_DIR",
    "EXTERNAL_DRIVE",
    "IQFEED_BARS_DIR",
    "external_drive_mounted",
    "sync_bars_to_external",
    "sync_emd_cache_to_external",
    "sync_from_external",
}
_PUBLISH_EXPORTS = {"atomic_publish_file", "staged_publish_directory"}


def __getattr__(name: str):
    from importlib import import_module

    if name in _EXTERNAL_DRIVE_EXPORTS:
        external_drive = import_module(".external_drive", __name__)
        value = getattr(external_drive, name)
        globals()[name] = value
        return value
    if name in _PUBLISH_EXPORTS:
        publish = import_module(".publish", __name__)
        value = getattr(publish, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
