"""Reconcile only filename changes backed by an independent PASS readback."""
from pathlib import Path, PurePosixPath
import hashlib
import json


def checked_json(path, digest):
    raw = Path(path).read_bytes()
    if not digest or hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError('The filename verification evidence changed.')
    return json.loads(raw)


def one_file(rows, fid):
    matches = [r for r in rows if r.get('id') == fid]
    if len(matches) != 1:
        raise ValueError('The reviewed image has no unique verified rename.')
    return matches[0]


def verified_rename(runtime, reviewed, current):
    pointer = json.loads((Path(runtime) / 'filename-readback.json').read_text())
    readback = checked_json(pointer['path'], pointer['sha256'])
    if readback.get('namespace_id') != '202238505':
        raise ValueError('The filename evidence belongs to another Dropbox namespace.')
    proof = checked_json(readback['verification'], readback['verification_sha256'])
    if proof.get('status') != 'PASS' or proof.get('errors'):
        raise ValueError('The filename pass has not passed independent verification.')
    manifest = checked_json(proof['manifest'], proof['manifest_sha256'])
    fid = reviewed['id']
    before = one_file([f for g in manifest['groups'] for f in g['files']], fid)
    after = one_file(readback['files'], fid)
    if not after.get('renamed') or not before.get('parent_id') or before['parent_id'] != after.get('parent_id'):
        raise ValueError('This was not a verified filename-only change.')
    for original, native in (('id', 'id'), ('path', 'path'), ('name', 'name'),
                             ('revision', 'rev'), ('content_hash', 'content_hash'), ('bytes', 'size')):
        if reviewed.get(original) != before.get(native) or current.get(original) != after.get(native):
            raise ValueError('The file does not match both sides of the verified rename.')
    if (after.get('source_path_before') != before['path'] or
            after.get('source_name_before') != before['name']):
        raise ValueError('The filename evidence does not connect to the original review.')
    old_path, new_path = PurePosixPath(reviewed['path']), PurePosixPath(current['path'])
    if old_path.parent != new_path.parent or old_path.suffix != new_path.suffix or old_path == new_path:
        raise ValueError('The file moved folders or changed file type after review.')
    if any(reviewed.get(k) != current.get(k) for k in ('id', 'content_hash', 'bytes', 'sharing_fingerprint')):
        raise ValueError('The file contents or sharing changed after review.')
    if not reviewed.get('content_hash') or not reviewed.get('sharing_fingerprint'):
        raise ValueError('The original review did not verify contents and sharing.')
    return {'kind': 'verified_filename_only', 'file_id': fid,
            'reviewed_name': reviewed['name'], 'reviewed_path': reviewed['path'],
            'reviewed_revision': reviewed['revision'], 'current_name': current['name'],
            'current_path': current['path'], 'current_revision': current['revision'],
            'readback': pointer['path'], 'readback_sha256': pointer['sha256'],
            'verification': readback['verification'], 'verification_sha256': readback['verification_sha256'],
            'checked_utc': current['checked_utc']}
