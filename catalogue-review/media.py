"""Byte identity and image headers, with no image decoding or pixel changes.

Dropbox content hashes are SHA256 over concatenated SHA256 digests of 4 MiB
blocks. They must never be compared directly with ordinary file SHA256 values.
Cached thumbnails never establish the identity or dimensions of an original.
"""
from collections import defaultdict
from pathlib import Path
import hashlib
import json
import re
import struct


TYPES = {'product': 'Product / individual', 'in_situ': 'In situ / installation',
         'detail': 'Detail / close-up', 'group': 'Group / arrangement', 'rear': 'Rear / fixings',
         'workshop': 'Workshop / process', 'design_reference': 'Design / finish reference',
         'mockup': 'Mock-up / generated', 'packaging': 'Packaging', 'other': 'Other'}
ROLE_TYPES = {'individual': ['product'], 'installation': ['in_situ'], 'detail': ['detail'],
              'group_context': ['group'], 'group': ['group'], 'group_detail': ['group', 'detail'],
              'rear': ['rear']}


def is_preview(representation):
    return any(x in representation.lower() for x in ('preview', 'thumbnail'))


def dimensions(path):
    """Read encoded pixel width/height, never substitute preview dimensions."""
    try:
        with Path(path).open('rb') as f:
            h = f.read(32)
            if h.startswith(b'\x89PNG\r\n\x1a\n'):
                return list(struct.unpack('>II', h[16:24]))
            if h[:6] in (b'GIF87a', b'GIF89a'):
                return list(struct.unpack('<HH', h[6:10]))
            if h[:2] == b'BM':
                return [abs(x) for x in struct.unpack('<ii', h[18:26])]
            if h[:4] == b'RIFF' and h[8:12] == b'WEBP':
                if h[12:16] == b'VP8X':
                    return [1 + int.from_bytes(h[24:27], 'little'), 1 + int.from_bytes(h[27:30], 'little')]
                if h[12:16] == b'VP8 ' and h[23:26] == b'\x9d\x01\x2a':
                    return [int.from_bytes(h[26:28], 'little') & 0x3fff, int.from_bytes(h[28:30], 'little') & 0x3fff]
                if h[12:16] == b'VP8L' and h[20] == 0x2f:
                    bits = int.from_bytes(h[21:25], 'little')
                    return [(bits & 0x3fff) + 1, ((bits >> 14) & 0x3fff) + 1]
            if h[:2] == b'\xff\xd8':
                f.seek(2)
                while f.tell() < 4 * 1024 * 1024:
                    b = f.read(1)
                    if not b:
                        break
                    if b != b'\xff':
                        continue
                    while b == b'\xff':
                        b = f.read(1)
                    if not b or b in (b'\xda', b'\xd9'):
                        break
                    if b[0] in (0, 1, *range(0xd0, 0xd9)):
                        continue
                    length = int.from_bytes(f.read(2), 'big')
                    if length < 2:
                        break
                    if b[0] in (0xc0, 0xc1, 0xc2, 0xc3, 0xc5, 0xc6, 0xc7, 0xc9, 0xca, 0xcb, 0xcd, 0xce, 0xcf):
                        d = f.read(5)
                        return [int.from_bytes(d[3:5], 'big'), int.from_bytes(d[1:3], 'big')]
                    f.seek(length - 2, 1)
            if h[:4] in (b'II*\x00', b'MM\x00*'):
                endian = 'little' if h[:2] == b'II' else 'big'
                f.seek(int.from_bytes(h[4:8], endian))
                count = int.from_bytes(f.read(2), endian)
                found = {}
                for _ in range(min(count, 4096)):
                    entry = f.read(12)
                    tag = int.from_bytes(entry[:2], endian)
                    typ = int.from_bytes(entry[2:4], endian)
                    if tag in (256, 257) and typ in (3, 4) and int.from_bytes(entry[4:8], endian) == 1:
                        found[tag] = int.from_bytes(entry[8:10 if typ == 3 else 12], endian)
                if len(found) == 2:
                    return [found[256], found[257]]
    except (OSError, ValueError, struct.error, IndexError):
        pass
    return None


class MediaCache:
    def __init__(self, root):
        self.path = Path(root) / 'media-metadata-v1.json'
        try:
            self.entries = json.loads(self.path.read_text())
        except (OSError, ValueError):
            self.entries = {}

    def inspect(self, path, hashes=False):
        p = Path(path)
        st = p.stat()
        stamp = [st.st_size, st.st_mtime_ns, st.st_ctime_ns]
        old = self.entries.get(str(p), {})
        if old.get('stamp') == stamp and (not hashes or old.get('sha256')):
            return old
        value = {'stamp': stamp, 'bytes': st.st_size, 'dimensions': dimensions(p)}
        if hashes:
            sha, blocks = hashlib.sha256(), hashlib.sha256()
            with p.open('rb') as f:
                for b in iter(lambda: f.read(4 * 1024 * 1024), b''):
                    sha.update(b)
                    blocks.update(hashlib.sha256(b).digest())
            value.update(sha256=sha.hexdigest(), dropbox_content_hash=blocks.hexdigest())
        self.entries[str(p)] = value
        return value

    def flush(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix('.tmp')
        tmp.write_text(json.dumps(self.entries))
        tmp.replace(self.path)


def verified_original_metadata(root, content_hash, expected_bytes):
    """Retain byte-verified dimensions after an optional local download is evicted."""
    if not re.fullmatch('[a-f0-9]{64}', content_hash or ''):
        return None
    try:
        receipt = json.loads((Path(root) / 'originals' / (content_hash + '.json')).read_text())
        dims = receipt.get('dimensions')
        if (receipt.get('dropbox_content_hash') != content_hash or receipt.get('bytes') != expected_bytes or
                type(expected_bytes) is not int or expected_bytes <= 0 or
                not re.fullmatch('[a-f0-9]{64}', receipt.get('sha256') or '') or
                not isinstance(receipt.get('file_id'), str) or not receipt['file_id'].startswith('id:') or
                not isinstance(receipt.get('checked_utc'), str) or not receipt['checked_utc'] or
                not isinstance(dims, list) or len(dims) != 2 or
                any(type(d) is not int or d <= 0 for d in dims)):
            return None
        return receipt
    except (OSError, ValueError, TypeError, AttributeError):
        return None


def enrich(catalogue, root):
    cache = MediaCache(root)
    groups = defaultdict(list)
    platform_previews = []
    for aid, asset in catalogue.assets.items():
        native = asset.get('original', {})
        content_hash = native.get('dropbox_content_hash')
        if not re.fullmatch('[a-f0-9]{64}', content_hash or ''):
            content_hash = None
        original = {**native, 'dropbox_content_hash': content_hash, 'dimensions': None,
                    'dimension_basis': 'Original pixel dimensions not available locally', 'locally_verified': False}
        if aid in catalogue.paths:
            path, representation = catalogue.paths[aid]
            # Also hash platform thumbnails: they can match a known Dropbox original,
            # but two thumbnails alone are not proof of equal originals.
            info = cache.inspect(path, hashes=not is_preview(representation) or asset['source'] != 'Dropbox')
            asset['cached_file'] = info
            if asset['source'] == 'Dropbox':
                verified = bool(content_hash and info.get('dropbox_content_hash') == content_hash)
                if verified:
                    original.update(dimensions=info['dimensions'], bytes=info['bytes'], sha256=info['sha256'],
                                    dimension_basis='Cached original verified against the retained Dropbox content hash', locally_verified=True)
                elif not is_preview(representation):
                    # A full-looking path is not proof. Mark it as reference-only.
                    asset['representation'] = 'cached preview / original bytes not verified'
                    catalogue.paths[aid] = (path, asset['representation'])
            else:
                if not is_preview(representation):
                    original.update(dimensions=info['dimensions'], bytes=info['bytes'], sha256=info['sha256'],
                                    dropbox_content_hash=info['dropbox_content_hash'],
                                    dimension_basis='Retained platform source rendition; native upload size not certified', locally_verified=True)
                    content_hash = info['dropbox_content_hash']
                else:
                    platform_previews.append((aid, info.get('dropbox_content_hash')))
        if not original['dimensions'] and native.get('recorded_dimensions') and native.get('dimensions_hash') == content_hash and content_hash:
            original.update(dimensions=native['recorded_dimensions'], dimension_basis='Retained original metadata bound to the Dropbox content hash')
        if not original['dimensions'] and asset['source'] == 'Dropbox':
            receipt = verified_original_metadata(root, content_hash, native.get('bytes'))
            if receipt:
                original.update(dimensions=receipt['dimensions'], sha256=receipt['sha256'],
                                dimension_basis='Original dimensions byte-verified on ' + receipt['checked_utc'][:10] + '; download receipt retained')
        asset['original'] = original
        asset['types'] = list(dict.fromkeys([t for role in [asset['role'], *asset.get('secondary_roles', [])]
                                           for t in ROLE_TYPES.get(role, [])] + asset.get('folder_types', [])))
        if content_hash and not asset.get('source_unavailable'):
            groups[content_hash].append(aid)
    # A thumbnail equal to a Dropbox original is an exact byte match to that original.
    for aid, h in platform_previews:
        if not catalogue.assets[aid].get('source_unavailable') and h in groups and any(catalogue.assets[x]['source'] == 'Dropbox' for x in groups[h]):
            groups[h].append(aid)
    catalogue.canonical_assets = {aid: aid for aid in catalogue.assets}
    catalogue.duplicate_groups = []
    for h, ids in groups.items():
        if len(ids) < 2:
            continue
        def priority(aid):
            a = catalogue.assets[aid]
            return (a['source'] != 'Dropbox', a['inventory_status'] != 'CURRENT_NATIVE_FILE_AND_ACTUAL_PARENT_VERIFIED',
                    {'Dropbox': 0, 'Squarespace': 1, 'Shopify': 2}.get(a['source'], 3), aid)
        ids = sorted(set(ids), key=priority)
        canonical = ids[0]
        for aid in ids:
            catalogue.canonical_assets[aid] = canonical
        if not catalogue.assets[canonical]['original']['locally_verified']:
            for member in ids:
                a = catalogue.assets[member]
                if a['original']['locally_verified'] and member in catalogue.paths:
                    catalogue.paths[canonical] = catalogue.paths[member]
                    catalogue.assets[canonical].update(local_preview=True, representation=catalogue.paths[member][1])
                    catalogue.assets[canonical]['original'].update(
                        dimensions=a['original']['dimensions'], sha256=a['original'].get('sha256'),
                        locally_verified=True, dimension_basis='Verified original bytes available through an exact-hash duplicate')
                    break
        catalogue.duplicate_groups.append({'canonical_id': canonical, 'member_ids': ids,
                                           'algorithm': 'dropbox_content_hash', 'hash': h,
                                           'basis': 'Exact encoded bytes; no thumbnail-only or visual similarity matching'})
    catalogue.duplicate_members = {aid: [aid] for aid in catalogue.assets}
    for g in catalogue.duplicate_groups:
        for aid in g['member_ids']:
            catalogue.duplicate_members[aid] = g['member_ids']
    catalogue.source['dedupe'] = {
        'groups': len(catalogue.duplicate_groups),
        'hidden_records': sum(len(g['member_ids']) - 1 for g in catalogue.duplicate_groups),
        'non_dropbox_copies_filtered': sum(catalogue.assets[x]['source'] != 'Dropbox' and catalogue.assets[g['canonical_id']]['source'] == 'Dropbox'
                                          for g in catalogue.duplicate_groups for x in g['member_ids'][1:]),
        'policy': 'Exact byte identity; Dropbox preferred; original records and reviews retained',
        'original_dimensions_known': sum(bool(x['original']['dimensions']) for x in catalogue.assets.values()),
        'unhashed_records': sum(not a['original'].get('dropbox_content_hash') for a in catalogue.assets.values())}
    cache.flush()
