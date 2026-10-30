"""A read-only component contact sheet with the current listing specifications."""
from component_photos import component_photos
from specifications import specification_overview
from component_links import component_row


def component_overview(view, pid):
    if pid not in view.cat.products:
        raise KeyError('Unknown sculpture')
    product = next(p for p in specification_overview(view.cat, view.reviews)['products'] if p['id'] == pid)
    photos = component_photos(view, pid, include_removed=True)
    for image in photos['images'] + photos['related_images']:
        aid = image['id']
        image['component_choice'] = component_row(view, pid, aid, image)
        image['asset_review'] = view.record('asset', '', aid)
        image['content_hash'] = (image.get('original', {}).get('dropbox_content_hash')
                                 or image.get('original', {}).get('sha256'))
    reference = view.cid(view.cat.products[pid].get('primary_id'))
    return {'product': product, **photos,
            'source_reference_id': reference if any(a['id'] == reference for a in photos['images']) else None,
            'source_hash': view.cat.source['register_sha256']}
