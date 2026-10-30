"""A read-only component contact sheet with the current listing specifications."""
from component_photos import component_photos
from specifications import specification_overview


def component_overview(view, pid):
    if pid not in view.cat.products:
        raise KeyError('Unknown sculpture')
    product = next(p for p in specification_overview(view.cat, view.reviews)['products'] if p['id'] == pid)
    photos = component_photos(view, pid)
    reference = view.cid(view.cat.products[pid].get('primary_id'))
    return {'product': product, **photos,
            'source_reference_id': reference if any(a['id'] == reference for a in photos['images']) else None,
            'source_hash': view.cat.source['register_sha256']}
