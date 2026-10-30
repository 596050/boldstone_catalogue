from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .errors import Blocked, BoldstoneError, IntegrityError
from .util import check_no_symlinks, digest, json_write, private_directory

READ_SCOPES = ("account_info.read", "files.metadata.read", "files.content.read", "sharing.read")
EXECUTOR_SCOPES = (*READ_SCOPES, "files.content.write")
DEFAULT_RUNTIME = Path.home() / "Library/Application Support/BoldstoneLocal"
DEFAULT_CONFIG = DEFAULT_RUNTIME / "config.json"


def sync_roots():
    info = Path.home() / ".dropbox/info.json"
    if not info.exists():
        return []
    try:
        return [
            Path(v["path"]).expanduser().resolve()
            for v in json.loads(info.read_text()).values()
            if isinstance(v, dict) and v.get("path")
        ]
    except (ValueError, KeyError, OSError) as exc:
        raise Blocked("Cannot establish configured Dropbox desktop sync paths") from exc


@dataclass(frozen=True)
class Config:
    path: Path
    data: dict

    @property
    def pack(self):
        return Path(self.data["pack_directory"])

    @property
    def database(self):
        return Path(self.data["local_paths"]["state_database"])

    def directory(self, name):
        return Path(self.data["local_paths"][name + "_directory"])

    @property
    def dropbox(self):
        return self.data["dropbox"]

    @property
    def checksum(self):
        return digest(self.data)

    def with_dropbox(self, **values):
        data = json.loads(json.dumps(self.data))
        data["dropbox"].update(values)
        return Config(self.path, data)

    def save(self, *, exclusive=False):
        json_write(self.path, self.data, exclusive=exclusive)

    def validate(self):
        if self.data.get("schema_version") != 1 or self.data.get("mode") != "read_only":
            raise BoldstoneError("Only schema version 1 and read_only mode are supported")
        if self.data.get("execute_enabled") is not False:
            raise Blocked("This release cannot enable Dropbox content writes")
        if self.data.get("external_image_transmission") is not False:
            raise Blocked("External image transmission is not supported")
        if tuple(self.dropbox.get("read_scopes", ())) != READ_SCOPES:
            raise Blocked("Only the four specified audit scopes may be requested")
        if any(key in self.dropbox for key in ("access_token", "refresh_token", "app_secret")):
            raise IntegrityError("Credentials must be stored in the OS credential store")
        check_no_symlinks(self.path)
        pack = check_no_symlinks(self.pack)
        locations = [
            self.database,
            self.path,
            *[Path(v) for k, v in self.data["local_paths"].items() if k.endswith("_directory")],
        ]
        for location in locations:
            check_no_symlinks(location)
            if location.is_relative_to(pack):
                raise IntegrityError("Working state may not be placed inside the historical pack")
            if any(location.is_relative_to(root) for root in sync_roots()):
                raise IntegrityError("Working state may not be placed inside Dropbox sync")
        directories = [
            self.directory(k)
            for k in ("cache", "evidence", "backup", "reports", "previews", "approvals")
        ]
        if len(set(directories)) != len(directories):
            raise IntegrityError(
                "Cache, evidence, backup, previews, approvals and reports must differ"
            )
        return self


def load_config(path=DEFAULT_CONFIG):
    path = check_no_symlinks(Path(path).expanduser().absolute())
    if not path.is_file():
        raise Blocked("Local configuration is missing; run 'boldstone config init' first")
    try:
        return Config(path, json.loads(path.read_text(encoding="utf-8"))).validate()
    except (KeyError, TypeError, ValueError) as exc:
        raise BoldstoneError("Malformed local configuration") from exc


def initialize_config(pack, runtime=DEFAULT_RUNTIME, path=None):
    pack = check_no_symlinks(Path(pack).expanduser().absolute())
    runtime = check_no_symlinks(Path(runtime).expanduser().absolute())
    config_path = (
        check_no_symlinks(Path(path).expanduser().absolute()) if path else runtime / "config.json"
    )
    data = {
        "schema_version": 1,
        "mode": "read_only",
        "execute_enabled": False,
        "external_image_transmission": False,
        "pack_directory": str(pack),
        "local_paths": {
            "state_database": str(runtime / "state/boldstone-state.sqlite3"),
            **{
                f"{name}_directory": str(runtime / folder)
                for name, folder in (
                    ("cache", "cache"),
                    ("evidence", "evidence"),
                    ("backup", "backups"),
                    ("reports", "reports"),
                    ("previews", "previews"),
                    ("approvals", "approvals"),
                )
            },
        },
        "dropbox": {
            "app_key": None,
            "credential_store_reference": "boldstone/dropbox/audit",
            "read_scopes": list(READ_SCOPES),
            "expected_account_id": None,
            "verified_namespace_id": None,
            "verified_root_folder_id": None,
            "known_file_ids": [],
            "historical_display_path_hint": "/BOLDSTONE MASTER/Products/01 Wall Sculptures",
        },
        "read_policy": {
            "max_attempts": 4,
            "max_retry_wait_seconds": 30,
            "max_download_bytes": 512 * 1024 * 1024,
            "max_frames": 250,
        },
    }
    config = Config(config_path, data).validate()
    private_directory(runtime)
    private_directory(config.database.parent)
    for key in data["local_paths"]:
        if key.endswith("_directory"):
            private_directory(Path(data["local_paths"][key]))
    config.save(exclusive=True)
    return config
