"""Dated per-component channel tasks, independent of product/image review choices.

The live app reads a bounded, atomically imported evidence snapshot from its
private data directory. A previous publication is never treated as proof that a
later catalogue edit has reached a platform. No network or platform writes occur.
"""
from copy import deepcopy
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path

SCHEMA = 'boldstone-platform-tasks/v1'
PLATFORMS = (
    ('website', 'Website'), ('google_merchant', 'Google Merchant'),
    ('google_manufacturer', 'Google Manufacturer'), ('microsoft_merchant', 'Microsoft'),
    ('pinterest', 'Pinterest'), ('meta_commerce', 'Meta Commerce'),
    ('instagram', 'Instagram'), ('facebook', 'Facebook'), ('linkedin', 'LinkedIn'),
    ('brandboom', 'Brandboom'), ('faire', 'Faire'), ('furnitures', 'Furnitures'),
    ('chairish', 'Chairish'), ('saatchi_art', 'Saatchi Art'), ('wescover', 'Wescover'),
    ('ebay_sapr_2972', 'eBay sapr_2972'), ('ebay_in6192', 'eBay in6192'),
    ('tiktok', 'TikTok'), ('gumtree', 'Gumtree'), ('bonanza', 'Bonanza'),
)
STATES = {'action', 'waiting', 'verified', 'unknown', 'not_targeted'}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')).encode()).hexdigest()


def fingerprints(product, photos):
    """Only publishable content/selection changes invalidate an external check."""
    fields = {f['key']: f.get('value') for f in product.get('fields', []) + product.get('listing_fields', [])}
    primary = photos.get('primary_listing', {}).get('image_id')
    previews = photos.get('photos', product.get('photos', {})).get('listing', {}).get('images', [])
    original = next((a.get('original', {}) for a in previews if a['id'] == primary), {})
    # Coverage is the complete ordered selection; specification previews contain
    # only six. Keep every selected file's hash so replacing a secondary image
    # or changing the carousel order also invalidates a recorded platform check.
    media = {'primary': primary, 'primary_hash': photos.get('primary_content_hash') or original.get('dropbox_content_hash') or original.get('sha256'),
             'listing': photos.get('listing', {}).get('image_ids', []),
             'in_situ': sorted(photos.get('in_situ', {}).get('image_ids', []))}
    if 'content_hashes' in photos:
        selected = set(media['listing']) | set(media['in_situ'])
        media['content_hashes'] = {aid: photos['content_hashes'].get(aid) for aid in selected}
    return {'fields': digest({'fields': fields, 'listing_decision': product.get('listing_decision')}),
            'photos': digest(media)}


def validate_snapshot(data):
    if not isinstance(data, dict) or data.get('schema') != SCHEMA:
        raise ValueError('Unsupported platform task snapshot')
    products = data.get('products')
    if not isinstance(products, dict) or len(products) > 2000:
        raise ValueError('Invalid platform product map')
    labels = dict(PLATFORMS)
    for pid, product in products.items():
        if not isinstance(pid, str) or not isinstance(product, dict):
            raise ValueError('Invalid platform product')
        platforms = product.get('platforms', {})
        if not isinstance(platforms, dict) or set(platforms) - set(labels):
            raise ValueError('Unknown platform')
        fp = product.get('fingerprints', {})
        if not isinstance(fp, dict) or set(fp) != {'fields', 'photos'} or any(not isinstance(v, str) or len(v) != 64 for v in fp.values()):
            raise ValueError('Invalid catalogue fingerprint')
        for code, entry in platforms.items():
            if (not isinstance(entry, dict) or not isinstance(entry.get('state'), str)
                    or entry['state'] not in STATES):
                raise ValueError('Invalid platform state')
            checked = entry.get('checked_at', '')
            if not isinstance(checked, str):
                raise ValueError('Invalid platform check date')
            if entry['state'] != 'unknown':
                at = datetime.fromisoformat(checked.replace('Z', '+00:00'))
                if at.tzinfo is None:
                    raise ValueError('A platform check needs a dated observation')
            tasks = entry.get('tasks', [])
            if not isinstance(tasks, list) or len(tasks) > 30:
                raise ValueError('Invalid platform tasks')
            ids = set()
            for task in tasks:
                if (not isinstance(task, dict) or not isinstance(task.get('state'), str)
                        or task['state'] not in STATES):
                    raise ValueError('Invalid task state')
                for key in ['id', 'title', 'detail']:
                    if not isinstance(task.get(key), str) or len(task[key]) > 6000:
                        raise ValueError('Invalid task text')
                if task['id'] in ids:
                    raise ValueError('Duplicate task ID')
                ids.add(task['id'])
                if task.get('scope', 'external') not in ('fields', 'photos', 'external', 'account'):
                    raise ValueError('Invalid task scope')
                if not isinstance(task.get('url', ''), str) or len(task.get('url', '')) > 2000:
                    raise ValueError('Invalid task link')
    return data


class PlatformTasks:
    def __init__(self, root):
        self.path = Path(root) / 'platform-tasks.json'
        self._stamp = None
        self._data = None
        self.source_error = ''

    def snapshot(self):
        try:
            stat = self.path.stat()
            if stat.st_size > 8 * 1024 * 1024:
                raise ValueError('Platform task snapshot exceeds its size limit')
            stamp = (stat.st_mtime_ns, stat.st_size, stat.st_ino)
            if stamp != self._stamp:
                self._data = validate_snapshot(json.loads(self.path.read_text()))
                self._stamp = stamp
            self.source_error = ''
        except FileNotFoundError:
            self._data = None
            self._stamp = None
            self.source_error = 'No platform audit has been imported yet.'
        except (ValueError, TypeError, OSError):
            # Fail visibly. Never show an old green result over unreadable evidence.
            self._data = None
            self._stamp = None
            self.source_error = 'Platform audit could not be read. Re-import its verified evidence.'
        return self._data or {'schema': SCHEMA, 'products': {}}

    def product(self, product, photos, now=None, snapshot=None):
        data = self.snapshot() if snapshot is None else snapshot
        current = fingerprints(product, photos)
        saved = data['products'].get(product['id'], {})
        old = saved.get('fingerprints', {})
        changed = {scope for scope in ('fields', 'photos') if old.get(scope) and old[scope] != current[scope]}
        now = now or datetime.now(timezone.utc)
        platforms = []
        for code, label in PLATFORMS:
            entry = deepcopy(saved.get('platforms', {}).get(code, {}))
            state = entry.get('state', 'unknown')
            tasks = entry.get('tasks', [])
            checked = entry.get('checked_at', '')
            if not entry:
                tasks = [dict(id='not_checked', state='unknown', title='Check this product on '+label,
                              detail='No current per-product platform evidence is loaded. Verify the existing listing, current price and selected images before marking it complete.', scope='external')]
            if state != 'not_targeted' and changed:
                tasks = [t for t in tasks if t.get('scope', 'external') not in changed]
                tasks.append(dict(id='catalogue_changed', state='action', title='Recheck catalogue changes on '+label,
                                  detail='The '+('details and photo selections' if len(changed) == 2 else 'details' if 'fields' in changed else 'photo selections')+' changed after the recorded platform check. Sync the existing product and verify its saved result.', scope='external', url=entry.get('url', '')))
            elif state == 'not_targeted' and 'fields' in changed:
                tasks.append(dict(id='inclusion_changed', state='action', title='Review publication scope', detail='Catalogue details or the listing choice changed after this product was excluded or held. Confirm whether to add it to this platform.', scope='external'))
            if self.source_error:
                tasks.append(dict(id='evidence_unavailable', state='unknown', title='Refresh platform evidence', detail=self.source_error, scope='external'))
            elif checked and state != 'not_targeted':
                try:
                    at = datetime.fromisoformat(checked.replace('Z', '+00:00'))
                    if at.tzinfo is None:
                        raise ValueError('Missing timezone')
                    if now - at > timedelta(days=7):
                        tasks.append(dict(id='audit_stale', state='action', title='Refresh this platform check', detail='The recorded observation is more than seven days old. Verify current product data, availability and platform status.', scope='external', url=entry.get('url', '')))
                except ValueError:
                    tasks.append(dict(id='date_unknown', state='unknown', title='Verify the check date', detail='The saved platform observation has no valid dated check.', scope='external'))
            states = {t['state'] for t in tasks}
            effective = ('action' if 'action' in states else 'unknown' if 'unknown' in states else
                         'waiting' if 'waiting' in states else state)
            platforms.append({**entry, 'id': code, 'label': label, 'state': effective, 'tasks': tasks,
                              'checked_at': checked,
                              'open_count': sum(t['state'] in ('action', 'waiting', 'unknown') for t in tasks)})
        result = {'platforms': platforms, 'fingerprints': current, 'source_error': self.source_error,
                  'catalogue_changed_since_check': bool(changed),
                  'open_count': sum(p['open_count'] for p in platforms),
                  'action_platforms': sum(p['state'] in ('action', 'unknown') for p in platforms),
                  'waiting_platforms': sum(p['state'] == 'waiting' for p in platforms)}
        result['revision'] = digest(result)
        return result

    def attach(self, products, photos):
        snapshot = self.snapshot()
        for product in products:
            product['platform_tasks'] = self.product(product, photos.get(product['id'], {}), snapshot=snapshot)
        return {'platforms': [{'id': key, 'label': label} for key, label in PLATFORMS],
                'source_error': self.source_error, 'snapshot_checked_at': snapshot.get('checked_at', ''),
                'revision': digest([p['platform_tasks']['revision'] for p in products])}
