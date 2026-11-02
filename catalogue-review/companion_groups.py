"""Companion copy from recorded group photos and unambiguous folder groups.

Relationships describe a coordinating composition, not a bundled sale. Finishes
of one design are never treated as separate companion components.
"""
from collections import defaultdict
import re
from component_links import folder_name, match_group, normal, strip_role


def design_key(product):
    title = product.get('retail_name') or product['name']
    return (product['family'], title.rsplit(' - ', 1)[0])


def companion_notes(snapshot):
    products = {p['id']: p for p in snapshot['products'] if p['listing_decision'] == 'include'}
    evidence = defaultdict(list)
    photos = defaultdict(set)
    for pid, product in products.items():
        for photo in product['photos']['listing']['images'] + product['photos']['in_situ']['images']:
            parts = photo.get('name', '').split('__')
            if len(parts) > 1 and '-and-' in parts[1]:
                photos[photo['id']].add(pid)
    groups = [(ids, {'source': 'selected_group_photo', 'image_id': aid}) for aid, ids in photos.items() if len(ids) > 1]
    anchors = defaultdict(lambda: defaultdict(set))
    for pid, product in products.items():
        anchors[product['family']][strip_role(normal(folder_name(product.get('folder_url'))))].add(pid)
    for family, folders in snapshot.get('family_inventory', {}).get('family_folders', {}).items():
        for folder in folders:
            ids = match_group(folder['name'], anchors[family])
            if ids:
                groups.append((set(ids), {'source': 'explicit_component_folder', 'folder_id': folder['id'], 'path': folder['path']}))
    for ids, source in groups:
        for pid in ids:
            for other in ids:
                if (pid != other and products[pid]['family'] == products[other]['family']
                        and design_key(products[pid]) != design_key(products[other])):
                    evidence[(design_key(products[pid]), design_key(products[other]))].append(source)
    result = {}
    for pid, product in products.items():
        design = design_key(product)
        others = sorted({b[1] for a, b in evidence if a == design})
        if not others:
            continue
        names = others[0] if len(others) == 1 else ', '.join(others[:-1]) + ' and ' + others[-1]
        label = 'pair' if len(others) == 1 else 'group'
        line = (f'This is one piece of a coordinating {label} with {names}. '
                'Companion sculptures are sold separately; this listing is for one sculpture only.')
        result[pid] = {'design': design[1], 'companions': others, 'text': line,
                       'evidence': [source for (a, _), sources in evidence.items() if a == design for source in sources]}
    return result


def apply_companion_note(text, note):
    text = re.sub(r'(?m)^Companion pieces:[^\n]*\n?', '', text).strip()
    if not note:
        return text
    point = 'Companion pieces: ' + note['text']
    if re.search(r'(?m)^Quantity supplied:[^\n]*', text):
        return re.sub(r'(?m)^Quantity supplied:[^\n]*',
                      lambda match: match.group(0) + '\n' + point, text, count=1)
    return text + '\n' + point
