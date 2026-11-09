"""Regular-file-only content-addressed report objects, with lossless path maps.

V1 inputs remain readable. V2 outputs encode each identical payload once while
retaining every original file's hash and logical size. No archive links execute.
Logical expansion limits still count every path, including duplicate content.
"""
import hashlib
import os
from pathlib import Path
import shutil
import tarfile

from .common import hash_id, no_links, parse, rel, sha

SCHEMA = 'marketmaker.offload_object.v2'


def payloads(manifest):
    result = {}
    for path, ref in sorted(manifest['files'].items()):
        identity = hash_id(ref['sha256'])
        if identity in result and result[identity]['bytes'] != ref['bytes']:
            raise ValueError('same payload hash has inconsistent lengths')
        result.setdefault(identity, {'bytes': ref['bytes'], 'paths': []})['paths'].append(rel(path))
    return result


def write_members(archive, source, manifest):
    for identity, ref in sorted(payloads(manifest).items()):
        member = tarfile.TarInfo('payloads/' + identity)
        member.size, member.mode = ref['bytes'], 0o644
        with (Path(source) / ref['paths'][0]).open('rb') as stream:
            archive.addfile(member, stream)


def verify(archive_path, manifest, *, max_bytes, max_members=100001):
    from .objects import _archive_metadata
    actual, _, members = _archive_metadata(archive_path, max_bytes=max_bytes)
    if actual != manifest or members > max_members:
        raise ValueError('deduplicated object manifest or logical member limit differs')
    expected = payloads(manifest)
    if sum(v['bytes'] for v in manifest['files'].values()) > max_bytes:
        raise ValueError('deduplicated object exceeds logical expansion budget')
    seen, header = set(), False
    with tarfile.open(archive_path, 'r|gz') as archive:
        for index, member in enumerate(archive):
            name = rel(member.name)
            if index >= max_members or not member.isreg() or member.issparse() or member.size < 0:
                raise ValueError('unsafe or excessive deduplicated object member')
            stream = archive.extractfile(member)
            if index == 0:
                if name != 'OBJECT.json' or member.size > min(8 << 20, max_bytes):
                    raise ValueError('bounded OBJECT.json must be first')
                if parse(stream.read()) != manifest or manifest.get('schema') != SCHEMA:
                    raise ValueError('deduplicated object manifest changed')
                header = True
                continue
            if not name.startswith('payloads/'):
                raise ValueError('unexpected deduplicated object member')
            identity = name.removeprefix('payloads/')
            if identity not in expected or identity in seen or member.size != expected[identity]['bytes']:
                raise ValueError('deduplicated object payload inventory differs')
            digest = hashlib.sha256()
            for block in iter(lambda: stream.read(1 << 20), b''):
                digest.update(block)
            if digest.hexdigest() != identity:
                raise ValueError('deduplicated object payload changed')
            seen.add(identity)
    if not header or seen != set(expected):
        raise ValueError('deduplicated object omitted a required payload')
    return {'logical_bytes': sum(v['bytes'] for v in manifest['files'].values()),
            'unique_payload_bytes': sum(v['bytes'] for v in expected.values()),
            'file_count': len(manifest['files']), 'payload_count': len(expected)}


def materialize(archive_path, destination, manifest, *, files=None, max_bytes, max_members=100001):
    """Write only requested original paths as independent regular files."""
    verify(archive_path, manifest, max_bytes=max_bytes, max_members=max_members)
    destination = Path(destination).absolute()
    if destination.is_symlink():
        raise ValueError('unsafe materialization destination')
    selected = manifest['files'] if files is None else files
    if any(manifest['files'].get(path) != ref for path, ref in selected.items()):
        raise ValueError('materialization selection differs from manifest')
    wanted = payloads({'files': selected})
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive_path, 'r|gz') as archive:
        for member in archive:
            identity = member.name.removeprefix('payloads/')
            if not member.name.startswith('payloads/') or identity not in wanted:
                continue
            paths = wanted[identity]['paths']
            first = no_links(destination / paths[0], destination)
            first.parent.mkdir(parents=True, exist_ok=True)
            with archive.extractfile(member) as incoming, first.open('xb') as output:
                shutil.copyfileobj(incoming, output, 1 << 20)
                output.flush(); os.fsync(output.fileno())
            if sha(first) != identity:
                raise ValueError('materialized payload changed')
            for name in paths[1:]:
                target = no_links(destination / name, destination)
                target.parent.mkdir(parents=True, exist_ok=True)
                with first.open('rb') as source, target.open('xb') as output:
                    shutil.copyfileobj(source, output, 1 << 20)
                if sha(target) != identity:
                    raise ValueError('materialized duplicate changed')
    return destination
