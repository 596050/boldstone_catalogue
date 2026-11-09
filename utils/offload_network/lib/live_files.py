"""Best-effort byte accounting for live writers, never immutable verification."""

import os
import stat
from pathlib import Path


def live_tree_bytes(root, *, exclude_root_dirs=()):
    """Ignore only disappearing live entries, not permissions or a missing root.

Atomic writers rename/unlink temporary files between directory enumeration and
metadata lookup. One lstat avoids the old is_file/stat race and never follows file
symlinks. A later polling pass sees new/renamed files. Immutable manifest/source
verification must remain strict and must not use this observational helper.
"""
    root = Path(root)
    if not stat.S_ISDIR(root.lstat().st_mode):
        raise OSError("live accounting root must be an existing regular directory")

    def error(exc):
        if not isinstance(exc, FileNotFoundError):
            raise exc

    size = 0
    for parent, directories, files in os.walk(root, followlinks=False, onerror=error):
        if Path(parent) == root:
            directories[:] = [d for d in directories if d not in exclude_root_dirs]
        for filename in files:
            try:
                info = (Path(parent) / filename).lstat()
            except FileNotFoundError:
                continue
            if stat.S_ISREG(info.st_mode):
                size += info.st_size
    return size
