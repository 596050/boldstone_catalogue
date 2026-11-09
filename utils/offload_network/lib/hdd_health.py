"""lib/hdd_health.py — pre-flight checks before writing to the external
HDD, so a missing/full/unstable drive surfaces as a clear, recoverable
error instead of a partial write or a write to a stale mountpoint.

USE THIS BEFORE EVERY rsync / file write into /Volumes/Untitled/.
Cheap (~ms) — caches results for 10s to avoid hammering during a
multi-step operation.

Key checks:
  - HDD mounted at the expected path
  - mount target writable (round-trip a tiny test file)
  - has at least N bytes of free space
  - if a UUID/label is supplied, matches what we expect
    (defense against "user plugged in a similarly-mounted disk")
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import time
from typing import Optional

DEFAULT_MOUNT = pathlib.Path("/Volumes/Untitled")
DEFAULT_BASE  = DEFAULT_MOUNT / "offload_data"
# Where we sentinel-touch to prove the disk is real and writable
_SENTINEL_DIR = DEFAULT_BASE / ".fleet_hdd_probe"

_CACHE: dict[str, tuple[float, dict]] = {}
_CACHE_TTL_S = 10.0


class HDDError(Exception):
    """Raised when the HDD is unusable for our intended write."""


def _statvfs(path: pathlib.Path) -> Optional[os.statvfs_result]:
    try:
        return os.statvfs(path)
    except (FileNotFoundError, PermissionError, OSError):
        return None


def _mac_diskutil_info(mount: pathlib.Path) -> dict:
    """Best-effort `diskutil info -plist <mount>` parsing for the UUID +
    label. Used to detect 'same path, different disk' situations."""
    try:
        r = subprocess.run(
            ["diskutil", "info", "-plist", str(mount)],
            capture_output=True, timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return {}
    if r.returncode != 0:
        return {}
    # Parse just the keys we care about — avoid plistlib dep
    text = r.stdout.decode(errors="replace")
    out = {}
    for key in ("VolumeUUID", "VolumeName", "FilesystemType", "DeviceIdentifier"):
        marker = f"<key>{key}</key>"
        idx = text.find(marker)
        if idx < 0:
            continue
        # Next <string> tag
        s = text.find("<string>", idx)
        e = text.find("</string>", s) if s >= 0 else -1
        if s >= 0 and e >= 0:
            out[key] = text[s + len("<string>"):e].strip()
    return out


def probe_hdd(mount: pathlib.Path = DEFAULT_MOUNT,
              required_free_bytes: int = 0,
              expected_uuid: Optional[str] = None,
              expected_label: Optional[str] = None,
              *, force: bool = False) -> dict:
    """Run the full pre-flight battery on the HDD.

    Returns a dict like::

        {"ok": True/False,
         "mounted": True/False,
         "writable": True/False,
         "free_bytes": <int>,
         "free_gb": <float>,
         "uuid": "...", "label": "...",
         "errors": [<str>, ...],
         "checked_at": <unix_ts>}

    Cached for ``_CACHE_TTL_S`` seconds keyed on ``mount``. Pass
    ``force=True`` to bypass the cache (e.g. after an action that may
    have changed mount state).

    Does NOT raise — callers inspect ``result["ok"]`` and decide.
    """
    key = str(mount)
    if not force and key in _CACHE:
        ts, cached = _CACHE[key]
        if time.time() - ts < _CACHE_TTL_S:
            return cached

    result = {
        "mount": str(mount), "mounted": False, "writable": False,
        "free_bytes": 0, "free_gb": 0.0,
        "uuid": None, "label": None, "filesystem": None,
        "errors": [], "checked_at": time.time(),
    }
    if not mount.exists() or not mount.is_dir():
        result["errors"].append(f"mount point {mount} does not exist")
        result["ok"] = False
        _CACHE[key] = (time.time(), result)
        return result
    result["mounted"] = True

    # Free space
    vfs = _statvfs(mount)
    if vfs:
        free = vfs.f_bavail * vfs.f_frsize
        result["free_bytes"] = free
        result["free_gb"] = round(free / 1e9, 2)
        if free < required_free_bytes:
            result["errors"].append(
                f"insufficient free space: {free} < required {required_free_bytes}"
            )

    # diskutil info for UUID + label (macOS only; no-op on Linux)
    info = _mac_diskutil_info(mount)
    if info:
        result["uuid"] = info.get("VolumeUUID")
        result["label"] = info.get("VolumeName")
        result["filesystem"] = info.get("FilesystemType")
        if expected_uuid and result["uuid"] and result["uuid"] != expected_uuid:
            result["errors"].append(
                f"UUID mismatch: got {result['uuid']} expected {expected_uuid}"
            )
        if expected_label and result["label"] and result["label"] != expected_label:
            result["errors"].append(
                f"label mismatch: got {result['label']} expected {expected_label}"
            )

    # Writability round-trip. NB: macOS TCC / sandboxing blocks direct
    # Python writes to removable volumes even when the same user's rsync
    # CAN write (observed 2026-06-06). We try the probe, but treat EPERM
    # / EACCES as ambiguous ("rsync will be the real verdict") rather
    # than a hard fail — false-positives would refuse perfectly valid
    # collects. Only ENOSPC / ENOENT / EIO are treated as fatal here.
    try:
        _SENTINEL_DIR.mkdir(parents=True, exist_ok=True)
        probe_file = _SENTINEL_DIR / f"probe_{os.getpid()}_{int(time.time()*1000)}.tmp"
        probe_file.write_text(f"probe at {time.time()}\n")
        probe_file.unlink()
        result["writable"] = True
    except PermissionError as e:
        # TCC-style block — known false positive on macOS removable vols.
        # Don't add to errors; just mark as "ambiguous" so callers see it.
        result["writable"] = "ambiguous_tcc"
        result["tcc_warning"] = (
            f"direct Python write probe blocked by macOS TCC ({e}); "
            f"rsync will still work — proceeding"
        )
    except OSError as e:
        # ENOSPC, ENOENT, EIO etc. are real
        result["errors"].append(f"write probe failed: {type(e).__name__}: {e}")

    # "ok" = mounted + (writable OR ambiguous-only-due-to-TCC) + no real errors
    result["ok"] = (
        result["mounted"]
        and result["writable"] is not False
        and not result["errors"]
    )
    _CACHE[key] = (time.time(), result)
    return result


def require_hdd(mount: pathlib.Path = DEFAULT_MOUNT,
                required_free_bytes: int = 0,
                expected_uuid: Optional[str] = None,
                expected_label: Optional[str] = None) -> dict:
    """Like probe_hdd but RAISES ``HDDError`` if ok is False. Use this
    as a gate at the top of any write-to-HDD operation."""
    result = probe_hdd(mount, required_free_bytes,
                        expected_uuid, expected_label)
    if not result["ok"]:
        raise HDDError(
            f"HDD pre-flight failed for {mount}: {result['errors']} "
            f"(mounted={result['mounted']} writable={result['writable']} "
            f"free_gb={result['free_gb']})"
        )
    return result


def wait_for_mount(mount: pathlib.Path = DEFAULT_MOUNT,
                   timeout_s: float = 60.0,
                   poll_s: float = 2.0) -> bool:
    """Block until the mount point is up + writable, or timeout.
    Returns True on success, False on timeout. Useful after a manual
    re-attach (cable replug, eject+remount, etc.)."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        r = probe_hdd(mount, force=True)
        if r["ok"]:
            return True
        time.sleep(poll_s)
    return False


def invalidate_cache():
    """Force the next probe to rebuild fresh (call after eject/remount)."""
    _CACHE.clear()
