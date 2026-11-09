"""Shared defaults for v2 orchestration paths."""
from __future__ import annotations

import os
from typing import Any


def _as_str(value: Any, *, fallback: str) -> str:
    return str(value if value is not None else fallback)


def remote_workdir_default(host_cfg: dict | None = None) -> str:
    """Return the configured base remote workdir for a host, with fallback."""
    cfg = host_cfg or {}
    platform = cfg.get("platform", "windows")
    platform_fallback = "/var/tmp/offload/jobs" if platform in {"linux", "macos"} else "C:/sealed/jobs"
    return _as_str(
        cfg.get("v2_remote_workdir"),
        fallback=os.environ.get("V2_REMOTE_WORKDIR", platform_fallback),
    ).rstrip("/\\")


def prestaged_cache_root(host_cfg: dict | None = None) -> str:
    """Return the configured root directory for pre-staged cache .mat files."""
    cfg = host_cfg or {}
    platform = cfg.get("platform", "windows")
    platform_fallback = (
        "/var/tmp/offload/prestaged_caches"
        if platform in {"linux", "macos"}
        else "C:/sealed/prestaged_caches"
    )
    return _as_str(
        cfg.get("v2_prestaged_cache_root"),
        fallback=os.environ.get(
            "V2_PRESTAGED_CACHE_ROOT",
            platform_fallback,
        ),
    ).rstrip("/\\")
