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
        f['status'] = ('components_recorded' if f['product_ids'] else
                       'catalogue_documents' if f['name'].casefold() == '_documents_catalogue' else 'images_only')
    rows = sorted(folders.values(), key=lambda f: f['name'].casefold())
    # Folder navigation comes only from the current native inventory. Catalogue
    # names and historical associations cannot create folders in this view.
    descendants = {}
    for f in getattr(cat, 'native_folders', []):
        path = f['path']
        root = root_folder(path)
        if not root or root.casefold() not in folders or root.casefold() == path.casefold():
            continue
        if folders[root.casefold()]['status'] == 'catalogue_documents':
            continue
        descendants[path.casefold()] = {**f, 'root_path': root,
            'relative_name': path[len(root) + 1:],
            'url': 'https://www.dropbox.com/home' + quote(path, safe='/'),
            'direct_image_count': 0, 'image_count': 0}
    seen = defaultdict(set)
    direct_seen = defaultdict(set)
    for aid, a in getattr(cat, 'assets', {}).items():
        canonical = getattr(cat, 'canonical_assets', {}).get(aid, aid)
        if a.get('source') != 'Dropbox' or a.get('source_unavailable') or canonical in deleted or aid in deleted:
            continue
        if canonical != aid and canonical in cat.assets:
            # The gallery displays the retained canonical file at its current
            # location, not a second card for each hidden byte-identical copy.
            continue
        path = a.get('provenance', {}).get('path') or ''
        if path.startswith('ns:202238505/'):
            path = '/' + path[len('ns:202238505/'):].lstrip('/')
        parent = path.rsplit('/', 1)[0].casefold()
        if parent in descendants:
            direct_seen[parent].add(canonical)
        while parent in descendants:
            seen[parent].add(canonical)
            parent = parent.rsplit('/', 1)[0]
    for path, f in descendants.items():
        f['direct_image_count'] = len(direct_seen[path])
        f['image_count'] = len(seen[path])
    child_rows = sorted(descendants.values(), key=lambda f: f['path'].casefold())
    family_folders = {}
    for family in set(linked) | {f['name'] for f in rows if f['status'] == 'images_only'}:
        roots = set(linked[family]) | {f['path'].casefold() for f in rows if f['name'] == family}
        family_folders[family] = [f for f in child_rows if f['root_path'].casefold() in roots]
    return {'registered_family_count': len({p['family'] for p in cat.products.values()}),
            'dropbox_folder_count': len(rows) if hasattr(cat, 'native_root_folders') else None,
            'checked_at': cat.source.get('live_dropbox', {}).get('checked_utc'), 'folders': rows,
            'image_only_folders': [f for f in rows if f['status'] == 'images_only'],
            'document_folders': [f for f in rows if f['status'] == 'catalogue_documents'],
            'family_paths': {k: sorted(v) for k, v in linked.items()},
            'family_folders': family_folders}


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
