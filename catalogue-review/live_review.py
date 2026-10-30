"""Prepared effective catalogue snapshots. This is not a canonical/native writer.

Consumers must explicitly register this source before it becomes authoritative.
The CLI is deliberately opt-in; the live HTTP server does not call it yet.
"""
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import argparse
import fcntl
import hashlib
import json
import os
import shutil
import tempfile

from catalogue import Catalogue, digest
from projection import Projection
from presentation import listing_value
from store import ReviewStore

SCHEMA = 'boldstone-effective-review/v1'
SOURCE_KEYS = ('register_sha256', 'gallery_sha256')


class SourceConflict(Exception):
    pass


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n').encode()


def effective_document(cat, snapshot):
    """Preserve source facts and qualifications alongside explicit review choices."""
    from costing import product_cost, settings as cost_settings
    view = Projection(cat, snapshot['reviews'])
    rates = cost_settings(view.reviews)
    conflicts = []
    for r in snapshot['reviews']:
        key = [r['kind'], r['product_id'], r['item_id']]
        if r['kind'] != 'cost_settings' and r['source_hash'] != cat.source['register_sha256']:
            conflicts.append({'key': key, 'reason': 'Review belongs to another source register'})
        if r['kind'] not in ('asset', 'deletion', 'cost_settings') and r['product_id'] != '__library__' and r['product_id'] not in cat.products:
            conflicts.append({'key': key, 'reason': 'Unknown or retired product'})
        if r['kind'] in ('image', 'asset', 'assignment') and r['item_id'] not in cat.assets:
            conflicts.append({'key': key, 'reason': 'Asset absent from source inventory'})
        if r['kind'] == 'field' and r['product_id'] in cat.products:
            if r['item_id'] not in {f['key'] for f in cat.products[r['product_id']]['fields']}:
                conflicts.append({'key': key, 'reason': 'Field absent from source product'})

    assets = {}
    for aid, a in cat.assets.items():
        if view.cid(aid) != aid:
            continue
        review = view.record('asset', '', aid)
        choice = review['data']
        assets[aid] = {
            'original': deepcopy(a),
            'alias_ids': view.member_ids(aid),
            'aliases': {i: deepcopy(cat.assets[i]) for i in view.member_ids(aid) if i != aid},
            'review': review,
            'effective': {k: deepcopy(choice.get(k, a.get(k, [] if k in ('types', 'tags') else '')))
                          for k in ('types', 'tags', 'collection', 'rights', 'notes')},
            'conflicts': review.get('duplicate_conflicts', []),
            'native_deletion': view.deleted.get(aid),
        }

    products = {}
    for pid, p in cat.products.items():
        review = view.record('product', pid)
        fields = {}
        for f in p['fields']:
            record = view.record('field', pid, f['key'])
            choice = record['data']
            action, certainty = choice.get('decision', 'pending'), choice.get('certainty', 'retain')
            value = listing_value(f, choice)
            fields[f['key']] = {'original': deepcopy(f), 'review': record,
                                'effective_value': value, 'included': action != 'exclude',
                                'certainty': certainty, 'source_qualification': f.get('qualification', ''),
                                'evidence': choice.get('evidence', ''),
                                'state': 'pending' if action == 'pending' else 'reviewed'}
        images, listing = {}, []
        for aid, edge in {**view.edges[pid], **view.removed[pid]}.items():
            record = view.record('image', pid, aid)
            choice = record['data']
            removed = aid in view.removed[pid]
            selected = list(choice.get('uses', [])) if choice.get('decision') == 'reviewed' else []
            reasons = list(record.get('duplicate_conflicts', [])) + assets[aid]['conflicts']
            if removed:
                reasons.append('Association removed from this product')
            if assets[aid]['effective'].get('rights') == 'restricted':
                reasons.append('Restricted rights')
            if choice.get('edit_notes', '').strip():
                reasons.append('Image edit requested and not completed')
            eligible = [] if reasons else selected
            image = {
                'asset_id': aid, 'original_associations': {i: cat.edges.get(pid, {}).get(i)
                                                        for i in view.member_ids(aid)
                                                        if i in cat.edges.get(pid, {})},
                'association': edge, 'assignment_review': view.record('assignment', pid, aid),
                'review': record, 'decision': choice.get('decision', 'pending'),
                'selected_uses': selected, 'eligible_uses': eligible,
                'primary_selected': bool(choice.get('primary')),
                'primary_eligible': bool(choice.get('primary')) and 'listing' in eligible,
                'withheld_reasons': reasons,
            }
            images[aid] = image
            if 'listing' in eligible:
                listing.append((not image['primary_eligible'], choice.get('order', 0), aid))
        primary = [aid for aid, im in images.items() if im['primary_eligible']]
        if len(primary) > 1:
            conflicts.append({'key': ['product', pid], 'reason': 'Multiple primary listing images'})
        products[pid] = {
            'original': deepcopy(p), 'review': review, 'fields': fields, 'images': images,
            'manufacturing_cost': product_cost({**p, 'id': pid}, view.reviews, rates),
            'listing_decision': review['data'].get('decision', 'pending'),
            'review_status': review['data'].get('status', 'unreviewed'),
            'name': fields.get('Name', {}).get('effective_value', p['name']),
            'family': fields.get('Family', {}).get('effective_value', p['family']),
            'selected_listing_image_ids': [aid for _, _, aid in sorted(listing)],
            'effective_primary_id': primary[0] if len(primary) == 1 else None,
            'primary_state': 'selected' if len(primary) == 1 else 'conflict' if primary else 'not_selected',
            'source_reference_primary_id': p.get('primary_id'),
        }
    return {
        'schema': SCHEMA, 'source': deepcopy(cat.source), 'review_snapshot': snapshot,
        'cost_settings': rates[0], 'cost_settings_version': rates[1],
        'products': products, 'assets': assets, 'conflicts': conflicts,
        'canonical_or_native_changes': False,
        'semantics': {
            'primary': 'Only an explicit, eligible selection is a listing primary; source references remain separate.',
            'exclusion': 'Per-product use choice; original file and other products are retained.',
            'status': 'Prepared projection only. No existing workbook, raw export or canonical record has changed.',
            'qualification': 'Source claims, estimates and user evidence are retained; no physical verification is inferred.',
        },
    }


def check_sources(cat):
    for path_key, hash_key in (('register', 'register_sha256'), ('gallery_database', 'gallery_sha256')):
        if digest(cat.source[path_key]) != cat.source[hash_key]:
            raise SourceConflict('Source bytes changed: ' + path_key)
    live = cat.source.get('live_dropbox')
    if live and digest(live['path']) != live['sha256']:
        raise SourceConflict('The live Dropbox image snapshot changed.')
    pointer_path = cat.project / 'sculpture-catalogue/current-master.json'
    pointer = json.loads(pointer_path.read_text())
    base = pointer_path.parent
    gallery = (base / pointer['current_published_gallery_projection']['path']).parent / 'complete-image-platform-register.sqlite'
    if (pointer['register_sha256'] != cat.source['register_sha256'] or
        (base / pointer['register']).resolve() != Path(cat.source['register']).resolve() or
        gallery.resolve() != Path(cat.source['gallery_database']).resolve()):
        raise SourceConflict('The catalogue publisher changed the active source; reload before projecting.')


def write_atomic(path, data):
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name + '-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def writer_lock(root):
    root.mkdir(parents=True, exist_ok=True)
    with (root / '.writer.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise SourceConflict('Another projection writer is running; retry after it finishes.') from exc
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def read_prepared(root, expected_source):
    """Verify one committed immutable generation, including source compatibility.

    This reader does not promote a projection into the canonical catalogue.
    """
    root = Path(root)
    pointer = json.loads((root / 'current.json').read_text())
    manifest_path = root / pointer['manifest']
    if manifest_path.resolve().parent.parent != (root / 'generations').resolve():
        raise ValueError('Invalid manifest location')
    raw = manifest_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != pointer['manifest_sha256']:
        raise ValueError('Projection manifest checksum mismatch')
    manifest = json.loads(raw)
    if manifest['schema'] != SCHEMA or manifest['status'] != 'prepared':
        raise ValueError('Projection is not a prepared compatible snapshot')
    if any(manifest['source'][k] != expected_source[k] for k in SOURCE_KEYS):
        raise SourceConflict('Projection and consumer source hashes differ')
    raw = (manifest_path.parent / 'data.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != manifest['data_sha256']:
        raise ValueError('Projection data checksum mismatch')
    data = json.loads(raw)
    if (data['schema'] != SCHEMA or data['conflicts'] or
        any(data['source'][k] != expected_source[k] for k in SOURCE_KEYS) or
        data['review_snapshot']['event_cutoff'] != manifest['event_cutoff']):
        raise SourceConflict('Projection data does not satisfy its manifest')
    return data, manifest


def prepare(cat, store, output):
    """Write an idempotent prepared generation; never mutate catalogue inputs."""
    root = Path(output).resolve()
    with writer_lock(root):
        cutoff = None
        try:
            check_sources(cat)
            snapshot = store.snapshot()
            cutoff = snapshot['event_cutoff']
            if (root / 'current.json').exists():
                previous, _ = read_prepared(root, cat.source)
                if previous['review_snapshot']['database'] != snapshot['database']:
                    raise SourceConflict('A different review database owns this projection output')
                if previous['review_snapshot']['event_cutoff'] > cutoff:
                    raise SourceConflict('Refusing to replace a newer committed review snapshot')
            doc = effective_document(cat, snapshot)
            if doc['conflicts']:
                raise SourceConflict(json.dumps(doc['conflicts'], ensure_ascii=False))
            content = encoded(doc)
            checksum = hashlib.sha256(content).hexdigest()
            generation = f'e{cutoff:012d}-{checksum[:16]}'
            directory = root / 'generations' / generation
            directory.parent.mkdir(exist_ok=True)
            if not directory.exists():
                staging = Path(tempfile.mkdtemp(prefix='.pending-', dir=directory.parent))
                try:
                    write_atomic(staging / 'data.json', content)
                    manifest = {
                        'schema': SCHEMA, 'status': 'prepared', 'authoritative': False,
                        'generation': generation, 'created_utc': datetime.now(timezone.utc).isoformat(),
                        'source': {k: cat.source[k] for k in SOURCE_KEYS},
                        'event_cutoff': cutoff, 'data_sha256': checksum,
                        'counts': {'products': len(doc['products']), 'assets': len(doc['assets']),
                                   'reviews': len(snapshot['reviews'])},
                    }
                    write_atomic(staging / 'manifest.json', encoded(manifest))
                    os.replace(staging, directory)
                finally:
                    if staging.exists():
                        shutil.rmtree(staging)
            if digest(directory / 'data.json') != checksum:
                raise SourceConflict('Existing immutable generation has changed')
            manifest = json.loads((directory / 'manifest.json').read_text())
            if manifest['data_sha256'] != checksum or manifest['event_cutoff'] != cutoff:
                raise SourceConflict('Existing generation manifest has changed')
            check_sources(cat)
            write_atomic(root / 'current.json', encoded({
                'manifest': str((directory / 'manifest.json').relative_to(root)),
                'manifest_sha256': digest(directory / 'manifest.json')}))
            # Independent reader checks bytes and semantics before reporting success.
            read_prepared(root, cat.source)
            status = {'status': 'prepared', 'authoritative': False, 'event_cutoff': cutoff,
                      'generation': generation, 'canonical_or_native_changes': False}
        except Exception as exc:
            write_atomic(root / 'status.json', encoded({
                'status': 'conflict' if isinstance(exc, SourceConflict) else 'failed',
                'event_cutoff': cutoff, 'authoritative': False, 'error': str(exc)}))
            raise
        write_atomic(root / 'status.json', encoded(status))
        return status


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument('--data-dir', type=Path, required=True, help='Consistent QA review database directory')
    parser.add_argument('--output', type=Path, required=True, help='Separate prepared-output directory')
    args = parser.parse_args()
    store = ReviewStore(args.data_dir)
    print(json.dumps(prepare(Catalogue(args.project, store.root), store, args.output)))
