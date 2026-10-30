"""Read-only photo selections shared by component cards, coverage and contact sheets."""
from component_links import shown


def component_photos(view, pid, images=None):
    associated, related = [], []
    for image in view.images(pid) if images is None else images:
        if image.get('association', {}).get('tier') == 'removed':
            continue
        aid = image['id']
        choice = view.decision('image', pid, aid)
        tags = view.decision('asset', '', aid)
        uses = choice.get('uses', []) if choice.get('decision') == 'reviewed' else []
        withheld = []
        primary_selected = bool(choice.get('primary'))
        if image.get('duplicate_conflicts'):
            withheld.append('Image or duplicate review needs resolving')
            # Projection deliberately clears unsafe choices. Retain a warning
            # for a formerly selected primary, without restoring its approval.
            primary_selected = primary_selected or any(
                r['kind'] == 'image' and r['product_id'] == pid
                and view.cid(r['item_id']) == aid and r['data'].get('primary') for r in view.raw)
        if tags.get('rights') == 'restricted':
            withheld.append('Restricted rights')
        if choice.get('edit_notes', '').strip():
            withheld.append('Image edit requested')
        image = {**image, 'effective_types': tags.get('types', image.get('types', [])),
                 'selected_uses': uses, 'excluded': choice.get('decision') == 'exclude',
                 'withheld_reasons': withheld, 'primary_selected': bool(primary_selected),
                 'primary_eligible': bool(choice.get('primary')) and 'listing' in uses and not withheld}
        (associated if shown(view, pid, aid) else related).append(image)
    selected = [a for a in associated if a['primary_selected'] and not a['excluded']]
    primary_id = selected[0]['id'] if len(selected) == 1 and selected[0]['primary_eligible'] else None
    # A selected primary can become a related candidate when changed bytes or
    # duplicate conflicts invalidate its saved listing use. It needs review.
    stale = [a for a in related if a['primary_selected'] and a['withheld_reasons'] and not a['excluded']]
    if stale:
        primary_id = None
    primary = {'status': 'set' if primary_id else 'needs_review' if selected or stale else 'missing',
               'image_id': primary_id, 'selected_ids': [a['id'] for a in selected + stale]}
    for image in associated + related:
        image['primary_eligible'] = image['id'] == primary_id
    listing = [a for a in associated if 'listing' in a['selected_uses'] and not a['excluded']]
    listing.sort(key=lambda a: (a['id'] != primary_id, view.decision('image', pid, a['id']).get('order', 0),
                                a['name'].casefold(), a['id']))
    return {'images': associated, 'related_images': related, 'primary_listing': primary,
            'primary_id': primary_id, 'primary_conflict': len(selected + stale) > 1,
            'listing_ids': [a['id'] for a in listing],
            'in_situ_ids': [a['id'] for a in associated if 'in_situ' in a['effective_types'] and not a['excluded']]}


def photo_preview(photos, situ_ids, limit=6):
    """Small card payload; totals are complete, previews are bounded per section."""
    lookup = {a['id']: a for a in photos['images']}

    def section(ids):
        previews = []
        for aid in ids[:limit]:
            image = lookup[aid]
            preview = {k: image.get(k) for k in ('id', 'name', 'local_preview', 'remote_preview',
                                                 'primary_eligible', 'withheld_reasons')}
            preview['original'] = {k: v for k, v in image.get('original', {}).items()
                                   if k in ('dropbox_content_hash', 'sha256')}
            previews.append(preview)
        return {'count': len(ids), 'images': previews}

    return {'primary_listing': photos['primary_listing'], 'listing': section(photos['listing_ids']),
            'in_situ': {**section(situ_ids), 'target': 2, 'missing': max(0, 2 - len(situ_ids))}}
