"""Atomic, explicit component visibility and per-product image-use decisions."""
from component_links import payload, shown
from store import Conflict, validate


def save_components(app, body):
    view = app.projection()
    aid = body.get('asset_id')
    current = payload(view, aid)
    if body.get('content_hash') != current['content_hash']:
        raise Conflict('This image changed since you opened its components. Reopen it before saving.')
    rows = body.get('rows')
    if not isinstance(rows, list) or not 1 <= len(rows) <= len(view.cat.products):
        raise ValueError('Choose at least one component change.')
    if any(not isinstance(r, dict) for r in rows):
        raise ValueError('Invalid component choices.')
    pids = [row.get('product_id') for row in rows]
    if any(not isinstance(pid, str) or pid not in view.cat.products for pid in pids) or len(set(pids)) != len(pids):
        raise ValueError('Choose unique, active sculptures.')
    changes = []
    for row in rows:
        pid = row['product_id']
        if any(type(row.get(k)) is not bool for k in ('shown', 'listing', 'advertising')):
            raise ValueError('Component choices must be checked or unchecked.')
        if not row['shown'] and (row['listing'] or row['advertising']):
            raise ValueError('Show the image under a component before choosing listing or advertising use.')
        for kind, field in [('image', 'image'), ('assignment', 'assignment')]:
            version = row.get(field + '_version')
            members = row.get(field + '_member_versions')
            if (type(version) is not int or version < 0 or not isinstance(members, dict)
                    or set(members) != set(view.member_ids(aid))
                    or any(type(v) is not int or v < 0 for v in members.values())
                    or members.get(aid) != version):
                raise ValueError('The component review versions are invalid. Reopen the chooser.')
            record = view.record(kind, pid, aid)
            actual = record.get('member_versions', {x: 0 for x in view.member_ids(aid)})
            if record['version'] != version or actual != members:
                raise Conflict('A component choice changed in another tab. Reopen the chooser before saving.')
        edge = view.edges.get(pid, {}).get(aid)
        if row['shown'] != shown(view, pid, aid) or (row['shown'] and edge and edge.get('tier') == 'related'):
            assignment = {'state': 'attached' if row['shown'] else 'removed', 'mode': 'components',
                          'from_product_id': '__library__', 'to_product_id': pid,
                          'asset_ids': view.member_ids(aid), 'basis': 'User selected the components visible in this image'}
            changes.append({'kind': 'assignment', 'product_id': pid, 'item_id': aid,
                            'data': assignment, 'version': row['assignment_version'],
                            'member_versions': row['assignment_member_versions'],
                            'original': {'source_association': edge, 'asset_id': aid}})
        old = view.decision('image', pid, aid)
        uses = list(old.get('uses', []))
        for use in ('listing', 'advertising'):
            if row[use] and use not in uses:
                uses.append(use)
            elif not row[use]:
                uses = [u for u in uses if u != use]
        if uses != old.get('uses', []) or (row['shown'] and any(row[u] for u in ('listing', 'advertising')) and old.get('decision') != 'reviewed'):
            data = {k: v for k, v in old.items() if k != 'reviewed_content_hash'}
            data.update(uses=uses, primary=bool(old.get('primary') and row['shown'] and row['listing']))
            if uses:
                data['decision'] = 'reviewed'
            elif old.get('decision') != 'exclude':
                data['decision'] = 'reviewed'
            data = validate('image', data)
            if view.cat.assets[aid].get('live_synced'):
                data['reviewed_content_hash'] = view.cat.assets[aid].get('original', {}).get('dropbox_content_hash')
            changes.append({'kind': 'image', 'product_id': pid, 'item_id': aid, 'data': data,
                            'version': row['image_version'], 'member_versions': row['image_member_versions'],
                            'original': {'asset': view.cat.assets[aid], 'association': edge}})
    app.store.save_component_reviews(changes, view.cat.source['register_sha256'])
    return {'changed_records': len(changes), **payload(app.projection(), aid)}
