"""Read-only catalogue projection. Review choices live in a separate database."""
from collections import defaultdict
from contextlib import closing
from pathlib import Path
import hashlib
import json
import sqlite3
from urllib.parse import urlparse
from media import enrich, is_preview


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def short_id(value):
    return hashlib.sha256(value.encode()).hexdigest()[:24]


class Catalogue:
    def __init__(self, project, cache_root=None):
        self.project = Path(project).resolve()
        base = self.project / 'sculpture-catalogue'
        pointer = json.loads((base / 'current-master.json').read_text())
        register_path = base / pointer['register']
        register = json.loads(register_path.read_text())
        if digest(register_path) != pointer['register_sha256']:
            raise ValueError('The catalogue register does not match its published checksum.')
        gallery = (base / pointer['current_published_gallery_projection']['path']).parent
        database = gallery / 'complete-image-platform-register.sqlite'
        self.source = {'register': str(register_path), 'register_sha256': pointer['register_sha256'],
                       'gallery_database': str(database), 'gallery_sha256': digest(database),
                       'scope': 'Saved catalogue and local image inventory; no live platform changes.'}
        self.products = {}
        self.assets = {}
        self.edges = defaultdict(dict)
        self.paths = {}
        self.preview_paths = {}
        self.families = set()
        self.component_names = {c['component_id']: c['name'] for c in register.get('components', [])}
        self.working_design_groups = {pid: group for group in register.get('current_working_design_group_projection', {}).get('groups', [])
                                      for pid in group.get('active_option_ids', [])}
        active = set(register['active_option_ids'])
        self.retired_product_ids = set(register.get('retired_option_ids', []))
        with closing(sqlite3.connect('file:' + str(database) + '?mode=ro', uri=True)) as db:
            for pid, name, family, raw in db.execute('SELECT * FROM products'):
                if pid not in active:
                    continue
                p = json.loads(raw)
                fields = []
                for key, v in p.get('master_fields', p['specifications']).items():
                    if key in ('Individual price', 'Availability'):
                        continue
                    fields.append({'key': key, 'label': key, 'value': v.get('display', ''),
                                   'basis': v.get('basis', ''), 'qualification': v.get('state', ''),
                                   'section': 'Specifications'})
                selling = p.get('selling_details', {})
                low, high = selling.get('estimated_price'), selling.get('estimated_price_upper')
                price = ('£' + format(low, ',g') + ('–£' + format(high, ',g') if high else '')
                         + ' — ' + selling.get('price_status', 'working value')) if low is not None else 'Quote required'
                fields.extend([
                    {'key': 'Price', 'label': 'Individual price', 'value': price, 'basis': selling.get('sale_unit', ''), 'qualification': 'Working price; estimate status retained.', 'section': 'Selling details'},
                    {'key': 'Availability', 'label': 'Availability', 'value': selling.get('availability', 'Unknown').replace('_', ' '), 'basis': 'Current owner working policy', 'qualification': 'No physical stock quantity inferred.', 'section': 'Selling details'},
                    {'key': 'Lead time', 'label': 'Lead time', 'value': f"{selling.get('lead_time_min_weeks', '?')}–{selling.get('lead_time_max_weeks', '?')} weeks", 'basis': selling.get('lead_time_basis', ''), 'qualification': 'Working lead time; delivery and start event not specified.', 'section': 'Selling details'},
                    {'key': 'Name', 'label': 'Product name', 'value': name, 'basis': 'Catalogue name', 'qualification': '', 'section': 'Listing copy'},
                    {'key': 'Family', 'label': 'Family / collection', 'value': family, 'basis': 'Existing family association', 'qualification': 'Editing display text does not merge identities.', 'section': 'Listing copy'},
                    {'key': 'Description', 'label': 'Listing description', 'value': '', 'basis': 'Write your customer-facing description here.', 'qualification': '', 'section': 'Listing copy'},
                    {'key': 'Sale unit', 'label': 'Sale unit', 'value': p.get('sale_unit', ''), 'basis': 'Individual option scope', 'qualification': '', 'section': 'Listing copy'},
                ])
                self.products[pid] = {'id': pid, 'name': name, 'family': family, 'fields': fields,
                                     'folder_url': p.get('folder_url', ''), 'image_url': p.get('image_url', ''),
                                     'primary_id': p.get('file_id'), 'component_id': p.get('canonical_component_id'),
                                     'source_notes': p.get('source_scope_notes', ''), 'photo_coverage': p.get('photo_coverage', {}),
                                     'sale_unit': p.get('sale_unit', '')}
                self.families.add(family)
            for fid, folder, path, is_image, in_wall, raw in db.execute('SELECT * FROM images'):
                if not is_image:
                    continue
                im = json.loads(raw)
                saved = im.get('saved_asset_metadata') or {}
                evidence = (im.get('visual_role_evidence') or {}).get('evidence') or {}
                candidates = [(saved.get('full'), 'cached source'), (saved.get('thumb'), 'cached preview'),
                              (evidence.get('source_image_path'), 'cached preview')]
                self._asset(fid, im.get('name', fid), 'Dropbox', im.get('family', ''),
                            im.get('image_url', ''), im.get('folder_url', ''), folder,
                            im.get('visual_role', 'uncertain'), im.get('inventory_status', ''), candidates,
                            {'native_file_id': fid, 'native_folder_id': folder, 'path': path,
                             'source_content_hash': saved.get('source_content_hash'),
                             'current_original_rehashed': saved.get('current_original_content_rehashed', False)})
                metadata = im.get('metadata') or {}
                native_hash = (saved.get('current_native_content_hash') or evidence.get('source_native_content_hash')
                               or metadata.get('current_native_content_hash') or metadata.get('source_content_hash')
                               or saved.get('content_hash') or saved.get('source_content_hash'))
                self.assets[fid]['original'] = {
                    'bytes': metadata.get('size') or saved.get('source_bytes') or saved.get('size') or saved.get('bytes'),
                    'dropbox_content_hash': native_hash,
                    'size_basis': 'Retained Dropbox file metadata',
                    'recorded_dimensions': saved.get('dimensions'), 'dimensions_hash': saved.get('content_hash')}
                self.assets[fid]['secondary_roles'] = (im.get('visual_role_evidence') or {}).get('secondary_roles', [])
                self.assets[fid]['folder_label'] = (im.get('visual_role_evidence') or {}).get('native_finish_folder_label') or Path(path).parent.name
            for aid, pid, fid, use, status, raw in db.execute('SELECT * FROM associations'):
                if pid not in self.products:
                    continue
                if fid not in self.assets:
                    missing = json.loads(raw)
                    self._asset(fid, 'Unavailable historical reference · ' + fid, 'Dropbox', '',
                                missing.get('image_url') or '', missing.get('folder_url') or '', missing.get('folder_id') or '',
                                missing.get('visual_role') or 'uncertain', 'Historical reference unavailable in current image map', [],
                                {'native_file_id': fid, 'historical_association_only': True, 'current_image_record_present': False})
                edge = self.edges[pid].setdefault(fid, {'asset_id': fid, 'uses': [], 'qualifications': [], 'association_ids': []})
                for key, value in [('uses', use), ('qualifications', status), ('association_ids', aid)]:
                    if value and value not in edge[key]:
                        edge[key].append(value)
            by_offer = defaultdict(set)
            for offer, pid in db.execute('SELECT offer_ref,product_id FROM source_product_links'):
                if pid in self.products:
                    by_offer[offer].add(pid)
            for raw, in db.execute('SELECT record_json FROM source_gallery'):
                im = json.loads(raw)
                aid = 'sq:' + im['gallery_entry_id']
                candidates = [(x.get('path'), x.get('representation', 'cached source')) for x in im.get('cached_renditions', [])]
                self._asset(aid, f"Squarespace · {im['offer_ref']} · image {im.get('gallery_order', '?')}", 'Squarespace', '',
                            im.get('source_url', ''), '', '', im.get('visual_role', 'uncertain'), 'Historical platform gallery', candidates,
                            {'gallery_entry_id': im['gallery_entry_id'], 'native_product_id': im.get('native_product_id'),
                             'variant_specific_assignment_certified': False, 'corresponding_dropbox_ids': im.get('supported_photo_file_ids', [])})
                for pid in by_offer[im['offer_ref']]:
                    self.edges[pid][aid] = {'asset_id': aid, 'uses': ['Related Squarespace gallery'],
                                            'qualifications': ['Product-gallery membership; exact variant assignment unconfirmed'], 'association_ids': []}
            handles = defaultdict(set)
            for raw, in db.execute('SELECT record_json FROM local_source_offers'):
                offer = json.loads(raw)
                sh = offer.get('shopify_local_product') or {}
                handle = sh.get('handle') or (sh.get('product') or {}).get('handle')
                if handle:
                    handles[handle].update(by_offer[offer['offer_ref']])
            cached_shopify = {}
            for raw, in db.execute('SELECT record_json FROM local_shopify_gallery_reviews'):
                im = json.loads(raw)
                url = (im.get('exported_gallery_row') or {}).get('image_src')
                cached_shopify[url] = im
                for offer in im.get('matched_squarespace_offer_refs', []):
                    handles[im['handle']].update(by_offer[offer])
            seen = set()
            for handle, ordinal, raw in db.execute('SELECT * FROM local_shopify_media'):
                if handle not in handles:
                    continue
                im = json.loads(raw)
                for url in [im.get('image_src'), im.get('variant_image_raw')]:
                    if not url or (handle, url) in seen:
                        continue
                    seen.add((handle, url))
                    review = cached_shopify.get(url, {})
                    cached = review.get('source_download') or {}
                    aid = 'sh:' + short_id(handle + ':' + url)
                    self._asset(aid, f"Shopify · {handle} · image {im.get('image_position_raw') or ordinal}", 'Shopify', '', url, '', '',
                                review.get('source_visual_role', 'uncertain'), 'Historical platform gallery',
                                [(cached.get('path'), 'cached source')], {'handle': handle, 'source_row': im.get('source_row'),
                                'variant_specific_assignment_certified': False})
                    for pid in handles[handle]:
                        self.edges[pid][aid] = {'asset_id': aid, 'uses': ['Related Shopify gallery'],
                                                'qualifications': ['Product-gallery membership; exact variant assignment unconfirmed'], 'association_ids': []}
        if set(self.products) != active:
            raise ValueError('Published gallery is missing active product options.')
        self.asset_products = defaultdict(list)
        for pid, edges in self.edges.items():
            for aid in edges:
                self.asset_products[aid].append(pid)
        for aid, a in self.assets.items():
            a['product_ids'] = self.asset_products[aid]
        # Only selected reference folders supply the initial sculpture view.
        # Broad cross-finish/family and platform relationships remain review candidates.
        for pid, edges in self.edges.items():
            folders = {self.assets[aid]['folder_id'] for aid, edge in edges.items()
                       if any(x.startswith('selected_') for x in edge['uses']) and self.assets[aid]['folder_id']}
            for aid, edge in edges.items():
                selected = any(x.startswith('selected_') for x in edge['uses'])
                edge['tier'] = 'accepted' if selected else 'folder' if self.assets[aid]['source'] == 'Dropbox' and self.assets[aid]['folder_id'] in folders else 'related'
        cache_root = Path(cache_root or Path.home() / 'Library/Application Support/BoldstoneReview')
        for aid, asset in self.assets.items():
            h = asset.get('original', {}).get('dropbox_content_hash')
            if h and asset['source'] == 'Dropbox':
                local = cache_root / 'originals' / (h + '.image')
                if local.is_file():
                    self.paths[aid] = (local, 'verified Dropbox original')
                    asset.update(local_preview=True, representation='verified Dropbox original')
        enrich(self, cache_root)
        self.source['product_count'] = len(self.products)
        self.source['asset_count'] = len(self.assets)
        self.source['local_preview_count'] = len(self.paths)
        self.source['association_count'] = sum(len(v) for v in self.edges.values())

    def _asset(self, aid, name, source, family, url, folder_url, folder_id, role, status, candidates, provenance):
        name, family, url = name or aid, family or '', url or ''
        folder_url, folder_id = folder_url or '', folder_id or ''
        role, status = role or 'uncertain', status or 'Availability unconfirmed'
        selected = None
        for path, representation in sorted(candidates, key=lambda pair: is_preview(pair[1])):
            if not path:
                continue
            p = Path(path).resolve()
            allowed = (p.is_relative_to(self.project) or p.is_relative_to(Path.home() / 'Library/Application Support'))
            if allowed and p.is_file() and p.stat().st_size < 150_000_000:
                selected = (p, representation)
                self.paths[aid] = selected
                break
        for path, representation in candidates:
            if path and ('preview' in representation.lower() or 'thumbnail' in representation.lower()):
                p = Path(path).resolve()
                if (p.is_relative_to(self.project) or p.is_relative_to(Path.home() / 'Library/Application Support')) and p.is_file():
                    self.preview_paths[aid] = p
                    break
        external = urlparse(url).hostname or ''
        remote = url if external in ('images.squarespace-cdn.com', 'cdn.shopify.com') else ''
        self.assets[aid] = {'id': aid, 'name': name, 'source': source, 'family': family, 'url': url,
                            'folder_url': folder_url, 'folder_id': folder_id, 'role': role, 'inventory_status': status,
                            'local_preview': bool(selected), 'remote_preview': remote,
                            'representation': selected[1] if selected else 'External source' if remote else 'Preview unavailable',
                            'provenance': provenance}

    def fields(self, pid):
        return {x['key']: x for x in self.products[pid]['fields']}

    def ordered_images(self, pid):
        primary = self.products[pid]['primary_id']
        def key(pair):
            aid, edge = pair
            selected = any('selected' in x for x in edge['uses'])
            return (aid != primary, not selected, self.assets[aid]['source'] != 'Dropbox', self.assets[aid]['name'])
        return [dict(self.assets[aid], association=edge) for aid, edge in sorted(self.edges[pid].items(), key=key)]
