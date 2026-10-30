"""Consume the independently verified filename pass without editing reviews."""
from pathlib import Path
import hashlib
import json

from organisation import apply_location


def apply_filename_overlay(cat, runtime, checked_at=None):
    pointer = Path(runtime) / 'filename-readback.json'
    if not pointer.exists():
        return
    config = json.loads(pointer.read_text())
    raw = Path(config['path']).read_bytes()
    if hashlib.sha256(raw).hexdigest() != config['sha256']:
        raise ValueError('The verified filename readback changed; it was not applied.')
    value = json.loads(raw)
    if value.get('namespace_id') != '202238505':
        raise ValueError('The filename readback belongs to a different Dropbox namespace.')
    verification = Path(value['verification']).read_bytes()
    if hashlib.sha256(verification).hexdigest() != value['verification_sha256'] or json.loads(verification)['status'] != 'PASS':
        raise ValueError('The filename pass has no matching independent verification.')
    checked_at = checked_at or cat.source.get('live_dropbox', {}).get('checked_utc', '')
    for row in value['files']:
        if not row['path'].startswith('/BOLDSTONE MASTER/'):
            raise ValueError('The filename readback contains an out-of-scope file.')
        # Newer Wall Sculptures inventories take precedence. Retained workshop
        # references are outside that collector's scope and use this receipt.
        if '/Products/01 Wall Sculptures/' in row['path'] and checked_at >= value['at']:
            continue
        asset = cat.assets.get(row['id'])
        if asset and asset.get('provenance', {}).get('organisation_verified_at', '') > value['at']:
            continue
        apply_location(cat, {'checked_utc': value['at'], 'file': {**row, 'folder_id': row['parent_id'], 'revision': row['rev']}})
    cat.source['filename_readback'] = {'path': config['path'], 'sha256': config['sha256'], 'checked_utc': value['at']}
