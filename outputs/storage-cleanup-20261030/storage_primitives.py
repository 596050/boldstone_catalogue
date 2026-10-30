"""Audited, byte-preserving APFS deduplication of local Boldstone media.

No Dropbox operations, pathname removals, hard links, or unique-content retirement.
The apply command replaces only exact duplicate media with independent COW clones.
"""
import argparse
import collections
import ctypes
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import uuid

HERE = Path(__file__).resolve().parent
MEDIA = {'.original', '.bin', '.source', '.bmp', '.jpg', '.jpeg', '.image',
         '.png', '.webp', '.tif', '.tiff', '.psd', '.gif'}
LIB = ctypes.CDLL('/usr/lib/libSystem.B.dylib', use_errno=True)
LIB.clonefile.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int]
LIB.clonefile.restype = ctypes.c_int
LIB.copyfile.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_void_p, ctypes.c_uint32]
LIB.copyfile.restype = ctypes.c_int
LIB.renamex_np.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
LIB.renamex_np.restype = ctypes.c_int
LIB.acl_get_file.argtypes = [ctypes.c_char_p, ctypes.c_int]
LIB.acl_get_file.restype = ctypes.c_void_p
LIB.acl_to_text.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ssize_t)]
LIB.acl_to_text.restype = ctypes.c_void_p
LIB.acl_free.argtypes = [ctypes.c_void_p]
LIB.acl_free.restype = ctypes.c_int
LIB.listxattr.argtypes = [ctypes.c_char_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int]
LIB.listxattr.restype = ctypes.c_ssize_t
LIB.getxattr.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_void_p,
                         ctypes.c_size_t, ctypes.c_uint32, ctypes.c_int]
LIB.getxattr.restype = ctypes.c_ssize_t
LIB.setxattr.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_void_p,
                         ctypes.c_size_t, ctypes.c_uint32, ctypes.c_int]
LIB.setxattr.restype = ctypes.c_int
LIB.removexattr.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int]
LIB.removexattr.restype = ctypes.c_int


class AttrList(ctypes.Structure):
    _fields_ = [('bitmapcount', ctypes.c_uint16), ('reserved', ctypes.c_uint16),
                ('commonattr', ctypes.c_uint32), ('volattr', ctypes.c_uint32),
                ('dirattr', ctypes.c_uint32), ('fileattr', ctypes.c_uint32),
                ('forkattr', ctypes.c_uint32)]


class TimeSpec(ctypes.Structure):
    _fields_ = [('seconds', ctypes.c_int64), ('nanoseconds', ctypes.c_int64)]


LIB.getattrlist.argtypes = [ctypes.c_char_p, ctypes.POINTER(AttrList),
                           ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint]
LIB.getattrlist.restype = ctypes.c_int
LIB.setattrlist.argtypes = LIB.getattrlist.argtypes
LIB.setattrlist.restype = ctypes.c_int


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def emit(data):
    print(json.dumps(data, sort_keys=True), flush=True)


def write_json(name, data):
    p = HERE / name
    with p.open('x') as out:
        json.dump(data, out, indent=2, sort_keys=True)
        out.write('\n')
        out.flush()
        os.fsync(out.fileno())
    return p


def identity(s):
    return [s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns,
            s.st_mode, s.st_uid, s.st_gid, s.st_nlink, s.st_flags]


def digest(path):
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode):
        raise RuntimeError(f'Not a regular file: {path}')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as stream:
        if identity(os.fstat(stream.fileno())) != identity(before):
            raise RuntimeError(f'Changed before read: {path}')
        h = hashlib.file_digest(stream, 'sha256').hexdigest()
        if identity(os.fstat(stream.fileno())) != identity(before):
            raise RuntimeError(f'Changed during read: {path}')
    if identity(path.lstat()) != identity(before):
        raise RuntimeError(f'Changed after read: {path}')
    return h


def acl_text(path):
    acl = LIB.acl_get_file(os.fsencode(path), 0x100)
    if not acl:
        code = ctypes.get_errno()
        # Darwin returns ENOENT for an existing object with no extended ACL.
        if code == 2 and path.is_file():
            return ''
        raise OSError(code, os.strerror(code), str(path))
    try:
        length = ctypes.c_ssize_t()
        text = LIB.acl_to_text(acl, ctypes.byref(length))
        if not text:
            raise OSError(ctypes.get_errno(), 'acl_to_text')
        try:
            return ctypes.string_at(text, length.value).decode('utf-8')
        finally:
            LIB.acl_free(text)
    finally:
        LIB.acl_free(acl)


def xattrs(path):
    size = LIB.listxattr(os.fsencode(path), None, 0, 1)
    if size < 0:
        raise OSError(ctypes.get_errno(), 'listxattr')
    names = ctypes.create_string_buffer(size)
    actual = LIB.listxattr(os.fsencode(path), names, size, 1)
    if actual < 0 or actual != size:
        raise RuntimeError('Extended attributes changed')
    values = {}
    for name in names.raw[:actual].split(b'\0'):
        if not name:
            continue
        size = LIB.getxattr(os.fsencode(path), name, None, 0, 0, 1)
        if not 0 <= size <= 16 * 1024 * 1024:
            raise RuntimeError('Unreadable or oversized extended attribute')
        data = ctypes.create_string_buffer(size)
        actual = LIB.getxattr(os.fsencode(path), name, data, size, 0, 1)
        if actual != size:
            raise RuntimeError('Extended attribute changed while reading')
        values[name] = data.raw[:actual]
    return values


def metadata(path):
    s = path.lstat()
    return {
        'mode': s.st_mode, 'uid': s.st_uid, 'gid': s.st_gid,
        'mtime_ns': s.st_mtime_ns, 'flags': s.st_flags,
        'birthtime_ns': creation_time(path),
        'acl': acl_text(path),
        'xattrs': {os.fsdecode(name): hashlib.sha256(value).hexdigest()
                   for name, value in sorted(xattrs(path).items())},
    }


def native(function, *args):
    if function(*args) != 0:
        code = ctypes.get_errno()
        raise OSError(code, os.strerror(code))


def creation_time(path, value=None):
    attributes = AttrList(5, 0, 0x200, 0, 0, 0, 0)
    if value is not None:
        seconds, nanoseconds = divmod(value, 10**9)
        timestamp = TimeSpec(seconds, nanoseconds)
        native(LIB.setattrlist, os.fsencode(path), ctypes.byref(attributes),
               ctypes.byref(timestamp), ctypes.sizeof(timestamp), 1)
        return value
    # getattrlist returns a four-byte length followed by a packed timespec.
    buffer = ctypes.create_string_buffer(20)
    native(LIB.getattrlist, os.fsencode(path), ctypes.byref(attributes), buffer, 20, 1)
    seconds = int.from_bytes(buffer.raw[4:12], sys.byteorder, signed=True)
    nanoseconds = int.from_bytes(buffer.raw[12:20], sys.byteorder, signed=True)
    return seconds * 10**9 + nanoseconds


def clone_with_metadata(keeper, destination, temporary):
    # clonefile guarantees COW independence; only file data are shared.
    native(LIB.clonefile, os.fsencode(keeper), os.fsencode(temporary), 1)
    # Replace keeper metadata with the destination's original ACL/stat/xattrs.
    for name in xattrs(temporary):
        native(LIB.removexattr, os.fsencode(temporary), name, 1)
    native(LIB.copyfile, os.fsencode(destination), os.fsencode(temporary), None, 7)
    # copyfile does not move a clone's creation time forward to a newer copy.
    creation_time(temporary, creation_time(destination))


def swap(a, b):
    native(LIB.renamex_np, os.fsencode(a), os.fsencode(b), 2)


def space():
    d = shutil.disk_usage('/System/Volumes/Data')
    v = os.statvfs('/System/Volumes/Data')
    return {'total_bytes': d.total, 'used_bytes': d.used, 'free_bytes': d.free,
            'available_bytes': v.f_bavail * v.f_frsize}

