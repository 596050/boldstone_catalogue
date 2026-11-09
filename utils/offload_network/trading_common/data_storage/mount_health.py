"""Lightweight mount health checks for external data roots.

This module deliberately avoids directory walks. It only inspects the platform
mount table so callers can fail fast before starting expensive scans or writes
against an unsuitable external volume.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import subprocess
from typing import Any


@dataclass(frozen=True)
class MountInfo:
    device: str
    mount_point: Path
    fs_type: str
    options: tuple[str, ...]


@dataclass(frozen=True)
class DataRootHealth:
    root: Path
    mount: MountInfo | None
    ok_for_live_writes: bool
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class ProcessSnapshot:
    matched: int
    uninterruptible: int
    rsync: int
    broad_scans: int
    entries: tuple[dict[str, str], ...]


_MOUNT_RE = re.compile(r"^(?P<device>.+?) on (?P<mount>.+?) \((?P<detail>.+)\)$")


def parse_mount_output(output: str) -> list[MountInfo]:
    mounts: list[MountInfo] = []
    for line in output.splitlines():
        match = _MOUNT_RE.match(line.strip())
        if not match:
            continue
        details = tuple(item.strip() for item in match.group("detail").split(",") if item.strip())
        fs_type = details[0] if details else ""
        mounts.append(
            MountInfo(
                device=match.group("device"),
                mount_point=Path(match.group("mount")),
                fs_type=fs_type,
                options=details[1:] if details else (),
            )
        )
    return mounts


def _path_is_within(path: Path, parent: Path) -> bool:
    path_text = str(path)
    parent_text = str(parent)
    return path_text == parent_text or path_text.startswith(parent_text.rstrip("/") + "/")


def mount_for_path(path: Path, mounts: list[MountInfo]) -> MountInfo | None:
    path = path.expanduser()
    candidates = [mount for mount in mounts if _path_is_within(path, mount.mount_point)]
    if not candidates:
        return None
    return max(candidates, key=lambda mount: len(str(mount.mount_point)))


def current_mounts() -> list[MountInfo]:
    proc = subprocess.run(["mount"], check=True, capture_output=True, text=True)
    return parse_mount_output(proc.stdout)


def assess_data_root(root: Path, *, mounts: list[MountInfo] | None = None) -> DataRootHealth:
    mounts = current_mounts() if mounts is None else mounts
    mount = mount_for_path(root, mounts)
    warnings: list[str] = []
    ok = True
    if mount is None:
        warnings.append(f"data root {root} is not under a mounted filesystem")
        ok = False
    else:
        options = set(mount.options)
        fs_type = mount.fs_type.lower()
        if fs_type in {"exfat", "msdos", "fat", "fat32"}:
            warnings.append(
                f"{mount.mount_point} is {mount.fs_type}; use APFS/HFS+ for live data roots"
            )
            ok = False
        if "noowners" in options:
            warnings.append(
                f"{mount.mount_point} is mounted with noowners; chmod/chown cannot provide stable ownership"
            )
            ok = False
        macos_sealed_system_root = (
            fs_type == "apfs"
            and mount.mount_point == Path("/")
            and "sealed" in options
        )
        if ("read-only" in options or "ro" in options) and not macos_sealed_system_root:
            warnings.append(f"{mount.mount_point} is mounted read-only")
            ok = False
    return DataRootHealth(root=root, mount=mount, ok_for_live_writes=ok, warnings=tuple(warnings))


def format_health(health: DataRootHealth) -> str:
    if health.mount is None:
        mount = "mount=missing"
    else:
        opts = ",".join(health.mount.options)
        mount = f"mount={health.mount.mount_point} fs={health.mount.fs_type} opts={opts}"
    warnings = "; ".join(health.warnings) if health.warnings else "none"
    return f"root={health.root} {mount} ok_for_live_writes={health.ok_for_live_writes} warnings={warnings}"


def process_snapshot_for_path(path: Path, *, limit: int = 80) -> ProcessSnapshot:
    """Return a process-table snapshot for commands referencing ``path``.

    This intentionally does not touch the filesystem under ``path``. It is safe
    to run when the external drive is slow or stuck because it only invokes
    ``ps`` and filters command strings.
    """
    needle = str(path)
    proc = subprocess.run(
        ["ps", "-axo", "pid,ppid,stat,etime,command"],
        check=False,
        capture_output=True,
        text=True,
        errors="replace",
    )
    entries: list[dict[str, str]] = []
    uninterruptible = 0
    rsync = 0
    broad_scans = 0
    for line in proc.stdout.splitlines()[1:]:
        if needle not in line:
            continue
        parts = line.strip().split(None, 4)
        if len(parts) < 5:
            continue
        pid, ppid, stat, etime, command = parts
        if "U" in stat:
            uninterruptible += 1
        if "rsync" in command:
            rsync += 1
        command_base = command.split(None, 1)[0]
        if command_base.endswith(("find", "bfs", "ls", "du", "wc")) or " find " in command or " bfs " in command:
            broad_scans += 1
        if len(entries) < limit:
            entries.append(
                {
                    "pid": pid,
                    "ppid": ppid,
                    "stat": stat,
                    "etime": etime,
                    "command": command[:500],
                }
            )
    return ProcessSnapshot(
        matched=len(entries) if len(entries) < limit else sum(1 for line in proc.stdout.splitlines()[1:] if needle in line),
        uninterruptible=uninterruptible,
        rsync=rsync,
        broad_scans=broad_scans,
        entries=tuple(entries),
    )


def external_health_payload(root: Path) -> dict[str, Any]:
    health = assess_data_root(root)
    monitor_path = health.mount.mount_point if health.mount is not None else root
    processes = process_snapshot_for_path(monitor_path)
    mount = None
    if health.mount is not None:
        mount = {
            "device": health.mount.device,
            "mountPoint": str(health.mount.mount_point),
            "fsType": health.mount.fs_type,
            "options": list(health.mount.options),
        }
    warnings = list(health.warnings)
    if processes.uninterruptible:
        warnings.append(f"{processes.uninterruptible} process(es) in U state reference {monitor_path}")
    if processes.rsync:
        warnings.append(f"{processes.rsync} rsync process(es) reference {monitor_path}")
    if processes.broad_scans:
        warnings.append(f"{processes.broad_scans} broad scan process(es) reference {monitor_path}")
    return {
        "root": str(root),
        "monitorPath": str(monitor_path),
        "mount": mount,
        "okForLiveWrites": health.ok_for_live_writes,
        "warnings": warnings,
        "summary": format_health(health),
        "processes": {
            "matched": processes.matched,
            "uninterruptible": processes.uninterruptible,
            "rsync": processes.rsync,
            "broadScans": processes.broad_scans,
            "entries": list(processes.entries),
        },
    }
