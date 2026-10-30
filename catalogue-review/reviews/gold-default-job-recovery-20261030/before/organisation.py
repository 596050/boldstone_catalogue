"""Plan a single original's location from exact component anchors and shared types."""
from pathlib import PurePosixPath
import re
import unicodedata

from component_links import normal, match_group, shown
from dropbox_sync import ROOT_PATH, folder_path, link
from organisation_scope import native_path, OUTSIDE_MESSAGE


class NeedsChoice(ValueError):
    pass


def slug(value):
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', '-', value.replace('&', ' and ')).strip('-')


def natural(value):
    return tuple((1, int(x)) if x.isdigit() else (0, x.casefold()) for x in re.split(r'(\d+)', value))


def strip_role(value):
    return re.sub(r'(?:[ _-]+(?:in[ _-]+situ|details?|rear|workshop|group|series|together))+$', '', value, flags=re.I)


def folder_for_components(products, ids, types):
    if not ids:
        raise NeedsChoice('Choose the component sculptures in this image using Components / uses.')
    anchors, paths = {}, {}
    for pid, p in products.items():
        if p.get('folder_link_only'):
            continue
        path = folder_path(p.get('folder_url'))
        relative = path[len(ROOT_PATH) + 1:].split('/') if path.startswith(ROOT_PATH + '/') else []
        if len(relative) == 2:
            family, label = relative
            label = strip_role(label)
            paths[pid] = (family, label)
            anchors.setdefault(family.casefold(), {}).setdefault(normal(label), set()).add(pid)
    if any(pid not in paths for pid in ids):
        raise NeedsChoice('A selected component needs a verified individual Dropbox folder in the catalogue.')
    families = {paths[pid][0].casefold() for pid in ids}
    if len(families) != 1:
        raise NeedsChoice('These components span different families. Choose one family before moving the original.')
    family = paths[sorted(ids)[0]][0]
    names = sorted({paths[pid][1] for pid in ids}, key=natural)
    if len(names) != len(ids) or any(len(anchors[family.casefold()][normal(name)]) != 1 for name in names):
        raise NeedsChoice('These component folder names are shared or ambiguous. Resolve their individual folder anchors first.')
    if len(names) == 1:
        label = names[0]
    else:
        # Share only a recognised finish suffix, never a size/component number.
        finishes = ['Pale Blue and White', 'Blue and White', 'Gold Leaf', 'Silver Leaf',
                    'Blue Wash Verdigris', 'White', 'Cream', 'Sandstone', 'Pewter',
                    'Verdigris', 'Bronze', 'Copper', 'Terracotta', 'Beige', 'Black', 'Silver']
        suffix = next((' ' + f for f in finishes if all(n.casefold().endswith(' ' + f.casefold()) for n in names)), '')
        label = ' and '.join(n[:-len(suffix)] if suffix else n for n in names) + suffix
        if set(match_group(label, anchors[family.casefold()])) != set(ids):
            raise NeedsChoice('The combined folder name does not identify these exact components unambiguously.')
    # One original, one physical location. Other types and uses remain tags.
    role = next((suffix for value, suffix in [('in_situ', ' In Situ'), ('detail', ' Details'),
                ('rear', ' Rear'), ('workshop', ' Workshop')] if value in types), '')
    label += role
    if len(label.encode()) > 200 or not slug(family) or not slug(label):
        raise NeedsChoice('The combined component name is too long for a clear Dropbox folder name.')
    return ROOT_PATH + '/' + family + '/' + label


def plan(view, aid):
    aid = view.cid(aid)
    if aid not in view.cat.assets or aid in view.deleted:
        raise NeedsChoice('The original is no longer available or is awaiting deletion verification.')
    asset = view.asset(aid)
    if asset['source'] != 'Dropbox' or not aid.startswith('id:'):
        raise NeedsChoice('Only a Dropbox original can be organised in Dropbox.')
    if view.record('asset', '', aid).get('duplicate_conflicts'):
        raise NeedsChoice('Resolve conflicting shared tags on identical copies before moving the original.')
    path = native_path(asset)
    if not path.casefold().startswith(ROOT_PATH.casefold() + '/'):
        raise NeedsChoice(OUTSIDE_MESSAGE)
    ids = sorted(pid for pid in view.cat.products if shown(view, pid, aid))
    types = view.decision('asset', '', aid).get('types', asset.get('types', []))
    target = folder_for_components(view.cat.products, ids, types)
    original = asset.get('original', {})
    if not original.get('dropbox_content_hash') or original.get('bytes') is None:
        raise NeedsChoice('Wait for Dropbox to verify this original before moving it.')
    return {'asset_id': aid, 'component_ids': ids, 'types': types,
            'binding': {'id': aid, 'content_hash': original['dropbox_content_hash'],
                        'bytes': original['bytes'], 'path': path},
            'destination_folder': target, 'source_folder': str(PurePosixPath(path).parent),
            'label': asset['name'], 'folder_url': link(target),
            'policy': 'One original per selected component set; In Situ takes precedence over other image types.'}


def apply_location(cat, result):
    """Immediate UI readback; native sync later supplies the full inventory."""
    row = result.get('file') or {}
    aid = row.get('id')
    if aid not in cat.assets or not row.get('path'):
        return
    asset = cat.assets[aid]
    if asset.get('original', {}).get('dropbox_content_hash') != row.get('content_hash'):
        return
    path = row['path']; parent = str(PurePosixPath(path).parent)
    asset.update(name=PurePosixPath(path).name, url=link(path, 'preview'), folder_url=link(parent),
                 folder_label=PurePosixPath(parent).name, folder_id=row.get('folder_id', asset.get('folder_id')))
    asset['provenance'] = {**asset.get('provenance', {}), 'path': path,
                           'revision': row.get('revision'), 'organisation_verified_at': result.get('checked_utc')}
    for product in cat.products.values():
        if product.get('primary_id') == aid:
            product['image_url'] = asset['url']
    if path.startswith(ROOT_PATH + '/'):
        asset['family'] = path[len(ROOT_PATH) + 1:].split('/')[0]
