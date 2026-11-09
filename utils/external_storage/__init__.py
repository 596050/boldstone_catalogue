"""External storage utilities (cloud object storage + external-drive helpers)."""

from .external_data_storage import (
    DEFAULT_EXTERNAL_DATA_ROOT,
    EXTERNAL_DATA_ROOT_ENV,
    ExternalizeResult,
    external_drive_status,
    external_job_lock,
    external_target_for_repo_path,
    externalize_directory,
    resolve_external_data_root,
    write_json_atomic,
)
from .manifest import (
    MANIFEST_PATH,
    generate_manifest,
    is_externalized,
    load_manifest,
    verify_manifest,
    write_manifest,
)
from .data_paths import (
    REGISTRY_PATH,
    generate_registry,
    load_registry,
    resolve_data_dir,
    write_registry,
)

__all__ = [
    "DEFAULT_EXTERNAL_DATA_ROOT",
    "EXTERNAL_DATA_ROOT_ENV",
    "ExternalizeResult",
    "external_drive_status",
    "external_job_lock",
    "external_target_for_repo_path",
    "externalize_directory",
    "resolve_external_data_root",
    "write_json_atomic",
    "MANIFEST_PATH",
    "generate_manifest",
    "is_externalized",
    "load_manifest",
    "verify_manifest",
    "write_manifest",
    "REGISTRY_PATH",
    "generate_registry",
    "load_registry",
    "resolve_data_dir",
    "write_registry",
]
