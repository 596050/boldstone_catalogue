"""Non-destructive, deduplicated view of source associations and review overlays."""
from collections import defaultdict
from copy import deepcopy


class Projection:
    def __init__(self, cat, reviews):
        self.cat = cat
        self.raw = reviews
        self.lookup = {(r['kind'], r['product_id'], r['item_id']): r for r in reviews}
        self.canonical = getattr(cat, 'canonical_assets', {})
        self.members = getattr(cat, 'duplicate_members', {})
        # A native deletion suppresses its retained display group, never deleting
        # another original or falling back to a historical platform copy.
        self.deleted = {self.cid(r['item_id']): r for r in reviews
                        if r['kind'] == 'deletion' and r['data'].get('state') in ('executing', 'uncertain', 'deleted')}
        self.deleted.update({self.cid(aid): {'data': {'state': 'outside_current_inventory'}}
                             for aid,a in cat.assets.items() if a.get('source_unavailable')})
        self.edges = defaultdict(dict)
        self.removed = defaultdict(dict)
        self.reviews = [r for r in reviews if r['kind'] not in ('image', 'asset', 'assignment')]
        self.effective = {(r['kind'], r['product_id'], r['item_id']): r for r in self.reviews}
        grouped = defaultdict(list)
        for r in reviews:
            if r['kind'] in ('image', 'asset', 'assignment'):
                grouped[(r['kind'], r['product_id'], self.cid(r['item_id']))].append(r)
        for (kind, pid, aid), rows in grouped.items():
            canonical = self.lookup.get((kind, pid, aid), {'version': 0})
            values = [r['data'] for r in rows]
            conflicts = []
            value = deepcopy(rows[-1]['data'])
            if kind == 'asset':
                for key in ('tags', 'types'):
                    if any(key in d for d in values):
                        value[key] = list(dict.fromkeys(x for d in values for x in d.get(key, [])))
                rights = {d.get('rights', 'unknown') for d in values}
                value['rights'] = 'restricted' if 'restricted' in rights else 'unknown' if 'unknown' in rights else sorted(rights)[0]
                for key in ('rights', 'collection', 'notes'):
                    if len({d.get(key, '') for d in values}) > 1:
                        conflicts.append('Different ' + key + ' on identical copies')
            elif kind == 'image' and any(v != values[0] for v in values[1:]):
                conflicts.append('Identical copies have different image choices for this sculpture')
                # Exclusions are never silently converted into listing approval.
                value = {**value, 'decision': 'pending', 'uses': [], 'primary': False}
            if kind == 'image' and value.get('decision') != 'exclude':
                asset=cat.assets.get(aid,{})
                current=asset.get('original',{}).get('dropbox_content_hash')
                changed=asset.get('live_synced') and current and any(
                    (r['data'].get('reviewed_content_hash') or r.get('original',{}).get('asset',{}).get('original',{}).get('dropbox_content_hash')) not in (None,current)
                    for r in rows)
                if changed:
                    conflicts.append('Dropbox image bytes changed; review the updated image before using it.')
                    value={**value,'decision':'pending','uses':[],'primary':False}
            versions = {x: self.lookup.get((kind, pid, x), {}).get('version', 0) for x in self.member_ids(aid)}
            record = {**rows[-1], 'item_id': aid, 'version': canonical['version'], 'data': value,
                      'member_versions': versions, 'duplicate_conflicts': conflicts,
                      'retained_review_ids': [r['item_id'] for r in rows]}
            self.reviews.append(record)
            self.effective[(kind, pid, aid)] = record
        for pid, edges in cat.edges.items():
            for aid, edge in edges.items():
                canonical = self.cid(aid)
                merged = self.edges[pid].setdefault(canonical, {'asset_id': canonical, 'uses': [], 'qualifications': [], 'association_ids': [], 'source_asset_ids': [], 'tier': 'related'})
                for k in ('uses', 'qualifications', 'association_ids'):
                    merged[k] = list(dict.fromkeys(merged[k] + edge.get(k, [])))
                merged['source_asset_ids'].append(aid)
                tier = edge.get('tier', 'folder')
                if {'accepted': 0, 'folder': 1, 'related': 2}[tier] < {'accepted': 0, 'folder': 1, 'related': 2}[merged['tier']]:
                    merged['tier'] = tier
        for r in self.reviews:
            if r['kind'] != 'assignment':
                continue
            pid, aid, d = r['product_id'], r['item_id'], r['data']
            if pid not in cat.products or aid not in cat.assets:
                continue
            if d.get('state') == 'attached':
                edge = self.edges[pid].setdefault(aid, {'asset_id': aid, 'uses': [], 'qualifications': [], 'association_ids': [], 'source_asset_ids': []})
                edge.update(tier='manual', assignment=d)
            elif d.get('state') == 'removed':
                edge = self.edges[pid].pop(aid, {'asset_id': aid, 'uses': [], 'qualifications': [], 'association_ids': [], 'source_asset_ids': []})
                self.removed[pid][aid] = {**edge, 'tier': 'removed', 'assignment': d}
        self.product_ids = defaultdict(list)
        self.deleted_associations = defaultdict(dict)
        for pid in list(self.edges):
            for aid in list(self.edges[pid]):
                if aid in self.deleted:
                    self.deleted_associations[pid][aid] = self.edges[pid].pop(aid)
        for pid, edges in self.edges.items():
            for aid in edges:
                self.product_ids[aid].append(pid)

    def cid(self, aid):
        return self.canonical.get(aid, aid)

    def member_ids(self, aid):
        return self.members.get(aid, [aid])

    def decision(self, kind, pid='', aid=''):
        return self.record(kind, pid, aid).get('data', {})

    def record(self, kind, pid='', aid=''):
        return self.effective.get((kind, pid, aid), {'version': 0, 'data': {}})

    def asset(self, aid):
        a = {**self.cat.assets[aid], 'product_ids': self.product_ids[aid]}
        a['duplicates'] = [{k: self.cat.assets[x].get(k) for k in ('id', 'name', 'source', 'url', 'folder_url', 'role', 'folder_label')}
                           for x in self.member_ids(aid)] if len(self.member_ids(aid)) > 1 else []
        a['duplicate_count'] = len(self.member_ids(aid)) - 1
        a['duplicate_conflicts'] = self.record('asset', '', aid).get('duplicate_conflicts', [])
        a['duplicate_review_details'] = [{k: r[k] for k in ('kind', 'product_id', 'item_id', 'data')}
                                         for r in self.raw if r['kind'] == 'asset' and r['item_id'] in self.member_ids(aid)] if a['duplicates'] else []
        return a

    def images(self, pid, include_removed=False):
        edges = {**self.edges[pid], **(self.removed[pid] if include_removed else {})}
        primary = self.cid(self.cat.products[pid].get('primary_id', ''))
        images = []
        for aid, edge in edges.items():
            if aid in self.deleted:
                continue
            a = self.asset(aid)
            r = self.record('image', pid, aid)
            a.update(association=edge, duplicate_conflicts=a['duplicate_conflicts'] + r.get('duplicate_conflicts', []))
            if a['duplicates']:
                a['duplicate_review_details'].extend({k: row[k] for k in ('kind', 'product_id', 'item_id', 'data')}
                                                     for row in self.raw if row['kind'] == 'image' and row['product_id'] == pid and row['item_id'] in self.member_ids(aid))
            images.append(a)
        return sorted(images, key=lambda a: (a['id'] != primary,
                      {'manual': 0, 'accepted': 1, 'folder': 2, 'related': 3, 'removed': 4}[a['association']['tier']],
                      a['source'] != 'Dropbox', a['name']))

    def library(self):
        return [self.asset(aid) for aid in self.cat.assets if self.cid(aid) == aid and aid not in self.deleted]
