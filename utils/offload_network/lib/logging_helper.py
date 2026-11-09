"""lib/logging_helper.py — unified ~/.fleet/logs/<YYYYMMDD>/<script>.log destinations.

P2 fix from the 2026-06-05 scripts audit: centralise logging so every
component writes to ``~/.fleet/logs/<YYYYMMDD>/<script-name>.log`` with
optional size-based rotation. Stops the scatter across /tmp/*.log + ad-hoc
per-script log paths.

Usage:

    from lib.logging_helper import get_log_path, setup_file_logger

    # Pure path resolver — write to it however you want:
    path = get_log_path("clean_kenne_chunks")
    # => ~/.fleet/logs/2026-06-05/clean_kenne_chunks.log

    # Or get a configured stdlib logger pointing at it:
    log = setup_file_logger("clean_kenne_chunks")
    log.info("cleanup started")
"""
from __future__ import annotations

import logging
import logging.handlers
import pathlib
from datetime import datetime, timezone

from fleet.paths import fleet_logs_dir as _fleet_logs_dir


def get_log_path(script_name: str,
                 *,
                 timestamp_subdir: bool = True,
                 ext: str = "log") -> pathlib.Path:
    """Resolve the canonical log path for a script.

    Args:
        script_name: Logical name (e.g. "fleet_collect", "auto_collect_watcher")
        timestamp_subdir: If True (default), place under YYYY-MM-DD subdir.
                          If False, write directly under fleet_logs_dir().
        ext: File extension without the dot (default "log").
    """
    base = _fleet_logs_dir()
    if timestamp_subdir:
        base = base / datetime.now(timezone.utc).strftime("%Y-%m-%d")
    base.mkdir(parents=True, exist_ok=True)
    return base / f"{script_name}.{ext}"


def setup_file_logger(script_name: str,
                      *,
                      level: int = logging.INFO,
                      max_bytes: int = 50 * 1024 * 1024,   # 50 MB
                      backup_count: int = 5,
                      fmt: str = "%(asctime)s %(levelname)s %(name)s — %(message)s",
                      ) -> logging.Logger:
    """Return a configured stdlib logger writing to the canonical path with
    size-based rotation. Safe to call multiple times — replaces existing
    file handlers for the same logger."""
    path = get_log_path(script_name)
    log = logging.getLogger(script_name)
    log.setLevel(level)
    # Remove any pre-existing file handlers for this name (idempotent setup)
    for h in list(log.handlers):
        if isinstance(h, logging.FileHandler):
            log.removeHandler(h)
    handler = logging.handlers.RotatingFileHandler(
        path, maxBytes=max_bytes, backupCount=backup_count,
    )
    handler.setFormatter(logging.Formatter(fmt))
    log.addHandler(handler)
    return log
