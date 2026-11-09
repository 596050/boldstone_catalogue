"""Copy an archive into an owned, new path; use independent APFS data clones.

Cloning is an I/O optimization, never verification. Callers must still check the
copied archive hash and retain their normal storage budgets and durability sync.
"""
import ctypes
import errno
import os
from pathlib import Path
import shutil
import stat
import sys


def _clone(source, destination):
    if sys.platform != "darwin":
        return False
    try:
        library = ctypes.CDLL("/usr/lib/libSystem.B.dylib", use_errno=True)
        clone = library.clonefile
    except (OSError, AttributeError):
        return False
    clone.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint32]
    clone.restype = ctypes.c_int
    # clonefile(2): source symlinks are not followed, destination must be new,
    # and writes to the two regular files remain independent (copy-on-write).
    # CLONE_NOFOLLOW | CLONE_NOOWNERCOPY, from the platform sys/clonefile.h.
    if clone(os.fsencode(source), os.fsencode(destination), 0x0001 | 0x0002) == 0:
        return True
    error = ctypes.get_errno()
    if error in {errno.ENOTSUP, errno.EOPNOTSUPP, errno.ENOSYS, errno.EXDEV, errno.EINVAL}:
        return False
    raise OSError(error, os.strerror(error), str(destination))


def copy(source, destination):
    source, destination = Path(source), Path(destination)
    if not stat.S_ISREG(source.lstat().st_mode):
        raise ValueError("archive copy source must be a regular file")
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(destination)
    cloned = _clone(source, destination)
    if not cloned:
        # Native cloning is atomic on failure. Never overwrite an unexpected
        # destination left by another writer or an inconsistent implementation.
        if destination.exists() or destination.is_symlink():
            raise FileExistsError(destination)
        shutil.copyfile(source, destination)
    if not stat.S_ISREG(destination.lstat().st_mode):
        raise ValueError("archive copy destination must be a regular file")
    if os.path.samefile(source, destination):
        raise ValueError("archive copy must not share a file identity")
    return "clone" if cloned else "copy"
