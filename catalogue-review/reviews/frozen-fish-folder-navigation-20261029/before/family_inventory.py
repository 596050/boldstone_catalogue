"""Match catalogue families to native folders using recorded containing paths."""
from urllib.parse import unquote, urlsplit, quote
from collections import defaultdict

ROOT = '/BOLDSTONE MASTER/Products/01 Wall Sculptures'


def root_folder(value):
    path = unquote(urlsplit(value or '').path) if '://' in (value or '') else (value or '')
    if path.startswith('ns:202238505/'):
        path = '/' + path[len('ns:202238505/'):].lstrip('/')
    for prefix in ('/home', '/preview'):
        if path.casefold().startswith((prefix + ROOT + '/').casefold()):
            path = path[len(prefix):]
    if not path.casefold().startswith((ROOT + '/').casefold()):
        return ''
    return ROOT + '/' + path[len(ROOT) + 1:].split('/')[0]


def family_inventory(cat, deleted=()):
    folders = {f['path'].casefold(): {**f, 'product_ids': [], 'registered_families': [], 'image_count': 0}
               for f in getattr(cat, 'native_root_folders', [])}
    linked = defaultdict(set)
    for pid, p in cat.products.items():
        path = root_folder(p.get('folder_url'))
        if path:
            linked[p['family']].add(path.casefold())
            if path.casefold() in folders:
                f = folders[path.casefold()]
                f['product_ids'].append(pid)
                f['registered_families'].append(p['family'])
    counted = set()
    for aid, a in getattr(cat, 'assets', {}).items():
        canonical = getattr(cat, 'canonical_assets', {}).get(aid, aid)
        if a.get('source') != 'Dropbox' or a.get('source_unavailable') or canonical in deleted or aid in deleted:
            continue
        path = root_folder(a.get('provenance', {}).get('path') or a.get('folder_url')).casefold()
        if path in folders and (path, canonical) not in counted:
            folders[path]['image_count'] += 1
            counted.add((path, canonical))
    for f in folders.values():
        f['registered_families'] = sorted(set(f['registered_families']))
        f['url'] = 'https://www.dropbox.com/home' + quote(f['path'], safe='/')
        f['status'] = 'components_recorded' if f['product_ids'] else 'images_only'
    rows = sorted(folders.values(), key=lambda f: f['name'].casefold())
    return {'registered_family_count': len({p['family'] for p in cat.products.values()}),
            'dropbox_folder_count': len(rows) if hasattr(cat, 'native_root_folders') else None,
            'checked_at': cat.source.get('live_dropbox', {}).get('checked_utc'), 'folders': rows,
            'image_only_folders': [f for f in rows if not f['product_ids']],
            'family_paths': {k: sorted(v) for k, v in linked.items()}}


def belongs_to_family(asset, family, inventory):
    path = root_folder(asset.get('provenance', {}).get('path') or asset.get('folder_url')).casefold()
    paths = set(inventory['family_paths'].get(family, []))
    paths.update(f['path'].casefold() for f in inventory['folders'] if f['name'] == family)
    if asset.get('source') == 'Dropbox' and path:
        # Native location is authoritative. A published image can already have
        # its new path while still carrying the family label from before a move.
        # Keep registered folder aliases, but do not show it in its old family.
        return path in paths or path.rsplit('/', 1)[-1] == family.casefold()
    return asset.get('family') == family or bool(path and path in paths)
