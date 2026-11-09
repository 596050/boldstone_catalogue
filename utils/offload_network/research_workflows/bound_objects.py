"""Seal explicitly hash-bound files with one source read and no expanded copy.

This is for an already declared immutable file manifest. Unknown source trees
still need ordinary snapshot discovery. Every byte delivered to tar is hashed;
file metadata alone never authorizes a source or establishes a successful seal.
"""
from copy import deepcopy
import gzip
import hashlib
import io
import os
from pathlib import Path
import stat
import tarfile

from .common import canonical, fields, hash_id, no_links, positive, rel, sha
from .objects import CHUNK, SCHEMA


def _stamp(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _open_source(path):
    return path.open('rb', buffering=CHUNK)


class _VerifiedReader:
    def __init__(self, source, expected):
        self.source, self.expected = source, expected
        self.count, self.digest = 0, hashlib.sha256()

    def read(self, size=-1):
        remaining = self.expected['bytes'] - self.count
        block = self.source.read(remaining if size < 0 else min(size, remaining))
        self.count += len(block); self.digest.update(block)
        return block

    def verify(self):
        if self.count != self.expected['bytes'] or self.digest.hexdigest() != self.expected['sha256']:
            raise ValueError('streamed source bytes differ from the declared file identity')


class _BoundedOutput:
    def __init__(self, output, limit):
        self.output, self.limit, self.count = output, limit, 0

    def write(self, data):
        if self.count + len(data) > self.limit:
            raise ValueError('compressed object exceeds its declared archive budget')
        written = self.output.write(data); self.count += written
        return written

    def flush(self):
        return self.output.flush()


def pack(source, destination, expected_files, *, max_bytes=1 << 30, max_files=100000,
         progress=None):
    """Produce the ordinary v1 archive, verifying explicit identities in-stream.

    Only manifest-selected files are read. Failed partial archives are retained,
    never returned as sealed objects. The receiver still verifies archive and
    expanded-file hashes before admission; this does not bypass that boundary.
    """
    positive(max_bytes, 1048576 << 20); positive(max_files, 10000000)
    source, destination = Path(source).absolute(), Path(destination).absolute()
    if source.is_symlink() or not source.is_dir():
        raise ValueError('bound source must be a regular directory')
    source = source.resolve()
    if destination.is_relative_to(source) or destination.resolve().is_relative_to(source):
        raise ValueError('object output cannot be inside its source')
    files = deepcopy(expected_files)
    if not isinstance(files, dict) or not 0 < len(files) <= max_files:
        raise ValueError('nonempty bounded file manifest required')
    names, coordinates, total = {}, {}, 0
    for relative, reference in files.items():
        relative = rel(relative)
        fields(reference, {'bytes', 'sha256'}, {'bytes', 'sha256'})
        hash_id(reference['sha256'])
        if type(reference['bytes']) is not int or reference['bytes'] < 0:
            raise ValueError('declared file size must be a nonnegative integer')
        total += reference['bytes']
        if total > max_bytes:
            raise ValueError('declared source exceeds its byte budget before reading')
        parts = relative.split('/')
        for end in range(1, len(parts)+1):
            coordinate = '/'.join(parts[:end]); key = coordinate.casefold()
            if key in names and names[key] != coordinate:
                raise ValueError('case-colliding manifest paths')
            names[key] = coordinate
        path = no_links(source / relative, source)
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size != reference['bytes']:
            raise ValueError('declared source is not an independent regular file of the expected size')
        coordinates[relative] = (path, _stamp(info))
    manifest = {'schema': SCHEMA, 'files': files}
    encoded = (canonical(manifest)+'\n').encode()
    if len(encoded) > 8 << 20:
        raise ValueError('object file manifest exceeds 8 MiB')
    destination.parent.mkdir(parents=True, exist_ok=True)
    completed_bytes = 0
    with destination.open('xb') as raw:
        output = _BoundedOutput(raw, max_bytes)
        with gzip.GzipFile(fileobj=output, mode='wb', filename='', mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode='w|') as archive:
                header = tarfile.TarInfo('OBJECT.json'); header.size, header.mode = len(encoded), 0o644
                archive.addfile(header, io.BytesIO(encoded))
                for index, (relative, reference) in enumerate(sorted(files.items()), 1):
                    path, before = coordinates[relative]
                    no_links(path, source)
                    with _open_source(path) as stream:
                        if _stamp(os.fstat(stream.fileno())) != before:
                            raise ValueError('source changed after manifest preflight')
                        reader = _VerifiedReader(stream, reference)
                        member = tarfile.TarInfo('data/'+relative)
                        member.size, member.mode = reference['bytes'], 0o644
                        archive.addfile(member, reader)
                        reader.verify()
                        if _stamp(os.fstat(stream.fileno())) != before or _stamp(path.lstat()) != before:
                            raise ValueError('source changed during bound capture')
                    completed_bytes += reference['bytes']
                    if progress is not None:
                        progress(index, relative, completed_bytes)
        raw.flush(); os.fsync(raw.fileno())
    return {'object_sha256': sha(destination), 'archive_bytes': destination.stat().st_size,
            'content_manifest': manifest}
