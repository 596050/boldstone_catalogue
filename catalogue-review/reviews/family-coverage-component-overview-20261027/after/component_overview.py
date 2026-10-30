"""A read-only component contact sheet with the current listing specifications."""
from component_links import shown
from specifications import specification_overview


def component_overview(view, pid):
    if pid not in view.cat.products:
        raise KeyError('Unknown sculpture')
    product = next(p for p in specification_overview(view.cat, view.reviews)['products'] if p['id'] == pid)
    images, related = [], []
    for image in view.images(pid):
        aid = image['id']
        choice = view.decision('image', pid, aid)
        tags = view.decision('asset', '', aid)
        uses = choice.get('uses', []) if choice.get('decision') == 'reviewed' else []
        withheld = []
        if image.get('duplicate_conflicts'):
            withheld.append('Conflicting duplicate reviews')
        if tags.get('rights') == 'restricted':
            withheld.append('Restricted rights')
        if choice.get('edit_notes', '').strip():
            withheld.append('Image edit requested')
        image = {**image, 'effective_types': tags.get('types', image.get('types', [])),
                 'selected_uses': uses, 'excluded': choice.get('decision') == 'exclude',
                 'withheld_reasons': withheld, 'primary_selected': bool(choice.get('primary')),
                 'primary_eligible': bool(choice.get('primary')) and 'listing' in uses and not withheld}
        (images if shown(view, pid, aid) else related).append(image)
    primary = [a['id'] for a in images if a['primary_eligible']]
    situ = [a['id'] for a in images if 'in_situ' in a['effective_types'] and not a['excluded']]
    reference = view.cid(view.cat.products[pid].get('primary_id'))
    return {'product': product, 'images': images, 'related_images': related,
            'primary_id': primary[0] if len(primary) == 1 else None,
            'primary_conflict': len(primary) > 1,
            'source_reference_id': reference if any(a['id'] == reference for a in images) else None,
            'in_situ_ids': situ, 'source_hash': view.cat.source['register_sha256']}
