"""Current review coverage, without creating products or inferring new identities."""
from collections import defaultdict
from urllib.parse import unquote, urlparse
import re
from component_photos import component_photos, photo_preview


def display_name(view, product):
    edit = view.decision('field', product['id'], 'Name')
    return edit.get('value', '') if edit.get('decision') == 'edit' else product['name']


def plain_white_evidence(product, name):
    # Mixed finishes must not satisfy a plain White component requirement.
    suffix = re.split(r'\s+[-—–]\s+', name)[-1].strip().casefold()
    if suffix == 'white':
        return 'named_white'
    if re.search(r'\s+[-—–]\s+', name):
        return None
    mixed = r'\b(blue|black|green|brown|pink|gold|silver)\s+(and|with)\s+white$'
    if name.casefold().endswith(' white') and not re.search(mixed, name, re.I) and not re.search(r'\b(marbled|wash)\b', name, re.I):
        return 'named_white'
    folder = unquote(urlparse(product.get('folder_url', '')).path).rstrip('/').split('/')[-1]
    if (folder.casefold().endswith(' white')
        and not re.search(r'\b(marbled|wash|in situ|together)\b', folder, re.I)
        and not re.search(mixed, folder, re.I)):
        return 'white_folder_title_missing'
    return None


def product_coverage(view, product, include_photos=False):
    pid = product['id']
    images = view.images(pid, include_removed=True)
    photos = component_photos(view, pid, images)
    counts = {'total': sum(image['association']['tier'] != 'removed' for image in images), 'sculpture': 0, 'related': 0, 'removed': 0}
    situ, individual, listing_situ, family_images = [], [], [], set()
    for image in images:
        aid = image['id']
        choice = view.decision('image', pid, aid)
        tags = view.decision('asset', '', aid)
        types = tags.get('types', image.get('types', []))
        tier = image['association']['tier']
        listing = choice.get('decision') == 'reviewed' and 'listing' in choice.get('uses', [])
        scope = 'removed' if tier == 'removed' else 'sculpture' if tier != 'related' or listing else 'related'
        counts[scope] += 1
        if scope != 'removed':
            family_images.add(aid)
        available = (scope == 'sculpture' and image['source'] == 'Dropbox'
                     and image.get('original', {}).get('dropbox_content_hash')
                     and image.get('original', {}).get('bytes')
                     and choice.get('decision') != 'exclude' and not image.get('duplicate_conflicts'))
        if not available:
            continue
        if 'in_situ' in types:
            situ.append(aid)
            if listing:
                listing_situ.append(aid)
        if 'product' in types:
            individual.append(aid)
    excluded = view.decision('product', pid).get('decision') == 'exclude'
    name = display_name(view, product)
    group = getattr(view.cat, 'working_design_groups', {}).get(pid, {})
    selected_ids = set(photos['listing_ids']) | set(situ)
    result = {'id': pid, 'name': name, 'family': product['family'], 'component_id': product.get('component_id'),
            'design_group_id': group.get('working_design_group_id', product.get('component_id')),
            'grouping_basis': group.get('grouping_basis', 'Existing component ID; no new design identity inferred'),
            'folder_url': product.get('folder_url', ''), 'excluded': excluded, 'counts': counts,
            'in_situ': {'count': len(situ), 'target': 2, 'missing': max(0, 2-len(situ)),
                        'image_ids': situ, 'listing_count': len(listing_situ)},
            'individual': {'count': len(individual), 'image_ids': individual},
            'listing': {'count': len(photos['listing_ids']), 'image_ids': photos['listing_ids']},
            'content_hashes': {a['id']: (a.get('original', {}).get('dropbox_content_hash')
                                       or a.get('original', {}).get('sha256'))
                               for a in photos['images']
                               if a['id'] in selected_ids},
            'white_evidence': plain_white_evidence(product, name), 'image_ids': sorted(family_images),
            'primary_listing': photos['primary_listing'],
            'primary_content_hash': next((a.get('original', {}).get('dropbox_content_hash')
                                         or a.get('original', {}).get('sha256')
                                         for a in photos['images'] if a['id'] == photos['primary_id']), None)}
    if include_photos:
        result['photos'] = photo_preview(photos, situ)
    return result


def coverage(view, include_photos=False):
    products = {pid: product_coverage(view, p, include_photos) for pid, p in view.cat.products.items()}
    families = {}
    for name in sorted({p['family'] for p in products.values()}):
        members = [p for p in products.values() if p['family'] == name]
        grouped = defaultdict(list)
        for p in members:
            if p['design_group_id']:
                grouped[p['design_group_id']].append(p)
        components = []
        for cid, variants in sorted(grouped.items()):
            whites = [p for p in variants if p['white_evidence']]
            active = [p for p in whites if not p['excluded']]
            if not whites:
                status = 'white_entry_not_found'
            elif not active:
                status = 'white_entry_excluded'
            elif any(p['white_evidence'] == 'named_white' for p in active):
                status = 'white_entry_present'
            else:
                status = 'white_title_missing'
            component_name = getattr(view.cat, 'component_names', {}).get(cid, variants[0]['name'])
            # A renamed single listing should have one current display name
            # throughout the app. A finish-specific edit must not rename a
            # design shared by several listings; retain that group's identity.
            if len(variants) == 1 and view.decision('field', variants[0]['id'], 'Name').get('decision') == 'edit':
                component_name = variants[0]['name']
            components.append({'id': cid, 'name': component_name.replace('—', '-'),
                               'retained_component_ids': sorted({p['component_id'] for p in variants if p['component_id']}),
                               'grouping_basis': variants[0]['grouping_basis'],
                               'product_ids': [p['id'] for p in variants], 'white_product_ids': [p['id'] for p in whites],
                               'status': status, 'individual_image_count': len(set(aid for p in active for aid in p['individual']['image_ids']))})
        active = [p for p in members if not p['excluded']]
        families[name] = {'name': name, 'product_ids': [p['id'] for p in members], 'components': components,
                          'option_count': len(members), 'component_count': len({p['component_id'] for p in members if p['component_id']}),
                          'design_group_count': len(components),
                          'unresolved_component_ids': [p['id'] for p in members if not p['design_group_id']],
                          'unique_image_count': len(set(aid for p in members for aid in p['image_ids'])),
                          'in_situ_ready': sum(p['in_situ']['missing'] == 0 for p in active),
                          'in_situ_gaps': sum(p['in_situ']['missing'] > 0 for p in active),
                          'in_situ_images_missing': sum(p['in_situ']['missing'] for p in active),
                          'white_entries_missing': sum(c['status'] in ('white_entry_not_found', 'white_entry_excluded') for c in components),
                          'white_titles_missing': sum(c['status'] == 'white_title_missing' for c in components),
                          'white_individual_gaps': sum(bool(c['white_product_ids']) and c['individual_image_count'] == 0 for c in components)}
    return {'products': products, 'families': families, 'in_situ_target': 2,
            'basis': 'Current saved Dropbox inventory, native deletion receipts and your review choices. Related candidates, excluded images and platform-only copies do not meet coverage targets. In-situ tags can include group scenes and mock-ups; they do not certify a photographed installation.'}
