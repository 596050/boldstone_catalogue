"""Seed a complete, explicitly unfinished image register from current evidence.

This never publishes canonical files or treats folder membership as identity proof.
Visual roles and candidate associations require subsequent evidence integration.
"""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import html
import json
from pathlib import Path
import sqlite3

H = Path(__file__).resolve().parent
B = H.parents[2]
ROOT = B.parent
WALL = '/BOLDSTONE MASTER/Products/01 Wall Sculptures/'
IMAGE_SUFFIXES = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.tif', '.tiff', '.bmp', '.heic', '.psd'}

def read(path):
    return json.loads(Path(path).read_text())

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def write(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()[:24]

pointer_path = B / 'current-master.json'
pointer_hash = sha(pointer_path)
p = read(pointer_path)
regpath = B / p['register']
assetpath = B / p['current_asset_reference_map']['path']
nativepath = B / p['current_native_reference_map']['path']
source_index_path = B / p['current_source_photo_review_index']['path']
assert sha(regpath) == p['register_sha256']
assert sha(assetpath) == p['current_asset_reference_map']['sha256']
assert sha(nativepath) == p['current_native_reference_map']['sha256']
assert sha(source_index_path) == p['current_source_photo_review_index']['sha256']
g, asset_map = read(regpath), read(assetpath)
active = set(g['active_option_ids'])
products = {x['product_id']: x for x in g['options'] if x['product_id'] in active}
assert len(products) == p['current_option_count'] == 188

stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
run = H / 'runs' / stamp
run.mkdir(parents=True, exist_ok=False)
inputs = {str(path): sha(path) for path in [pointer_path, regpath, assetpath, nativepath, source_index_path, H / 'requirements.json']}
objective = Path(read(H / 'requirements.json')['objective_file'])
inputs[str(objective)] = sha(objective)
fresh_path = ROOT / 'reports/dropbox-wall-complete-role-review-20261024T214349Z/all-current-6360-image-folder-links.json'
fresh_native_path = fresh_path.with_name('complete-current-native-object-map.json')
readback_path = H / 'selected-reference-readbacks.json'
for path in [fresh_path, fresh_native_path, readback_path]:
    inputs[str(path)] = sha(path)
fresh = {x['file_id']: x for x in read(fresh_path)}
fresh_native = read(fresh_native_path)
direct = {x['requested_id']: x for x in read(readback_path)}
assert len(fresh) == 6360

# All saved assets remain visible in the inventory. Only current Wall Sculptures
# paths enter the principal review population; other evidence stays separate.
images = {}
for file_id, asset in asset_map.items():
    path = asset.get('path') or asset.get('display_path') or asset.get('path_display') or ''
    suffix = Path(asset.get('name', '')).suffix.lower()
    in_wall = WALL in path
    images[file_id] = {
        'file_id': file_id, 'name': asset.get('name'), 'family': asset.get('family'),
        'folder_id': asset.get('folder_id'), 'path': path,
        'image_url': asset.get('image_url'), 'folder_url': asset.get('folder_url'),
        'is_image': suffix in IMAGE_SUFFIXES, 'in_wall_sculpture_tree': in_wall,
        'inventory_status': 'SAVED_CURRENT_ASSET_MAP_AWAITING_FULL_FRESH_INVENTORY' if path else 'HISTORICAL_REFERENCE_WITHOUT_CURRENT_PATH',
        'visual_role': None, 'visual_review_status': 'AWAITING_EVIDENCE_INTEGRATION',
        'metadata': asset,
    }

# Current native IDs and actual parent paths take precedence for navigation.
# Absence from a scoped inventory is never silently interpreted as deletion.
for file_id, row in images.items():
    if file_id in fresh:
        continue
    receipt = direct.get(file_id, {})
    metadata = receipt.get('metadata') or {}
    if receipt.get('metadata_type') == 'file':
        parent = direct.get(row['folder_id'], {}).get('metadata') or {}
        assert str(Path(metadata['path_display']).parent) == parent['path_display']
        row['inventory_status'] = 'CURRENT_NATIVE_FILE_AND_ACTUAL_PARENT_VERIFIED_OUTSIDE_WALL_SCOPE'
        row['current_native_evidence'] = {'path': str(readback_path), 'sha256': inputs[str(readback_path)], 'file_id': file_id}
        row['path'] = metadata['path_display']
        row['current_native_metadata'] = metadata
    elif row['in_wall_sculpture_tree']:
        row['inventory_status'] = 'HISTORICAL_REFERENCE_ABSENT_FROM_CURRENT_WALL_INVENTORY'
    else:
        row['inventory_status'] = 'SAVED_REFERENCE_OUTSIDE_CURRENT_WALL_INVENTORY_SCOPE'

navigation_changes = []
for file_id, now in fresh.items():
    previous = images.get(file_id, {})
    parent = fresh_native[now['folder_id']]
    assert parent['object_type'] == 'folder'
    assert str(Path(now['display_path']).parent) == parent['display_path']
    if previous and (previous['folder_id'] != now['folder_id'] or previous['path'].split('//')[-1].lstrip('/') != now['display_path'].lstrip('/')):
        navigation_changes.append({'file_id': file_id, 'before': {k: previous.get(k) for k in ['path', 'folder_id', 'image_url', 'folder_url']}, 'now': now})
    images[file_id] = {
        **previous, 'file_id': file_id, 'name': now['name'], 'family': now['family'],
        'folder_id': now['folder_id'], 'path': now['path'], 'image_url': now['image_url'],
        'folder_url': now['folder_url'], 'is_image': True, 'in_wall_sculpture_tree': True,
        'inventory_status': 'CURRENT_NATIVE_FILE_AND_ACTUAL_PARENT_VERIFIED',
        'visual_role': None, 'visual_review_status': 'AWAITING_EVIDENCE_INTEGRATION',
        'saved_asset_metadata': previous.get('metadata'), 'metadata': now,
        'current_native_evidence': {'path': str(fresh_path), 'sha256': inputs[str(fresh_path)], 'file_id': file_id},
    }

associations = {}
def add(option_id, file_id, use, status, source, pointer, details):
    if option_id not in products or not file_id:
        return
    key = digest([option_id, file_id, use, status])
    evidence = {'path': str(source), 'sha256': inputs[str(source)], 'json_pointer': pointer, 'details': details}
    row = associations.setdefault(key, {
        'association_id': key, 'product_id': option_id, 'file_id': file_id,
        'intended_use': use, 'association_status': status, 'visual_role': None,
        'visual_role_status': 'NOT_YET_CLASSIFIED', 'evidence': [],
        'image_url': images.get(file_id, {}).get('image_url'),
        'folder_url': images.get(file_id, {}).get('folder_url'),
        'folder_id': images.get(file_id, {}).get('folder_id'),
        'current_image_in_map': file_id in images,
        'current_native_status': images.get(file_id, {}).get('inventory_status', 'REFERENCE_NOT_IN_ASSET_MAP'),
    })
    if evidence not in row['evidence']:
        row['evidence'].append(evidence)

folder_candidates = defaultdict(list)
for i, option in enumerate(g['options']):
    oid = option['product_id']
    if oid not in products:
        continue
    add(oid, option.get('file_id'), 'selected_primary_reference', 'CURRENT_ACCEPTED_REFERENCE', regpath,
        f'/options/{i}', {'photo_coverage': option.get('photo_coverage'), 'identity_basis': option.get('identity_basis'), 'source_scope_notes': option.get('source_scope_notes')})
    add(oid, option.get('context_file_id'), 'selected_context_reference', 'CURRENT_QUALIFIED_CONTEXT_REFERENCE', regpath,
        f'/options/{i}', {'context_status': option.get('context_status'), 'context_description': option.get('context_description')})
    for field, use in [('folder_id', 'primary_folder'), ('context_folder_id', 'context_folder')]:
        if option.get(field):
            folder_candidates[option[field]].append((oid, use, f'/options/{i}'))

for i, cfg in enumerate(g['source_media_configuration_coverage']):
    for oid in cfg.get('exact_supported_target_ids', []):
        for fid in cfg.get('example_file_ids', []):
            add(oid, fid, 'source_configuration_example', 'RETAINED_SOURCE_SCOPE_SUPPORT', regpath,
                f'/source_media_configuration_coverage/{i}', {'configuration_id': cfg['configuration_id'], 'qualification': cfg.get('exact_supported_target_basis'), 'flags': cfg.get('flags', [])})
        for key, use in [('baseline_solo_folder_ids', 'configuration_solo_folder'), ('baseline_context_folder_ids', 'configuration_context_folder'), ('baseline_series_folder_ids', 'configuration_series_folder')]:
            for folder_id in cfg.get(key, []):
                folder_candidates[folder_id].append((oid, use, f'/source_media_configuration_coverage/{i}'))

for file_id, image in images.items():
    if file_id not in fresh:
        continue
    for oid, use, pointer in folder_candidates.get(image['folder_id'], []):
        add(oid, file_id, use, 'FOLDER_CANDIDATE_REQUIRES_VISUAL_REVIEW', regpath, pointer,
            {'basis': 'Exact recorded folder ID only; not proof of depicted component, finish, role or approval.'})

# Source gallery membership comes from retained full collection arrays. Keep
# source-index samples separate where a full native gallery is unavailable.
offer_path = B / 'components/evidence/offer_review_index.json'
inputs[str(offer_path)] = sha(offer_path)
offers = read(offer_path)
rawdir = B / 'components/parallel-reviews/listing-resolution-2026-10-21/worker-01/raw-public'
native_products = {}
for filename in ['collection-initial.body', 'collection-page-01.body']:
    path = rawdir / filename
    inputs[str(path)] = sha(path)
    for i, native in enumerate(read(path).get('items', [])):
        native_products[native['id']] = (native, path, i)
gallery = []
gallery_scope = []
for offer in offers:
    ref, pid = offer['ref'], offer['pid']
    if pid in native_products:
        native, source, position = native_products[pid]
        media = native.get('items', [])
        scope = 'COMPLETE_RETAINED_PUBLIC_GALLERY_NOT_CURRENT_ADMIN_VERIFICATION'
        members = [(i + 1, image.get('id'), image['assetUrl'], f'/items/{position}/items/{i}') for i, image in enumerate(media)]
    else:
        source = offer_path
        scope = 'SAMPLE_ONLY_FULL_GALLERY_REQUIRES_CURRENT_NATIVE_EVIDENCE'
        members = [(image['order'], None, image['url'], None) for image in offer['images']]
    gallery_scope.append({'offer_ref': ref, 'native_product_id': pid, 'membership_status': scope, 'known_media_count': len(members)})
    for order, media_id, url, pointer in members:
        gallery.append({'gallery_entry_id': digest([ref, media_id, order, url]), 'offer_ref': ref,
            'native_product_id': pid, 'native_media_id': media_id, 'gallery_order': order, 'source_url': url,
            'source_document': str(source), 'source_document_sha256': inputs[str(source)], 'json_pointer': pointer,
            'membership_status': scope, 'download_status': 'NOT_YET_INTEGRATED',
            'visual_review_status': 'NOT_YET_INTEGRATED', 'file_correspondences': []})

# The authenticated local 24 October export contains full product galleries.
# Its URL arrays supersede earlier sampled membership. Historical media IDs
# remain dated 21 October observations, not new variant-image assignments.
historical_gallery = gallery
local_gallery_path = ROOT / 'reports/local-platform-crosswalk-20261024-root/local-squarespace-80-full-galleries.json'
inputs[str(local_gallery_path)] = sha(local_gallery_path)
assert inputs[str(local_gallery_path)] == '3e81f28ed39eb562ab1b891169c7a72df6a988f366f364fbeaf8474383725383'
local_gallery = read(local_gallery_path)
raw_export = local_gallery['source']['raw_export']
assert sha(raw_export['path']) == raw_export['sha256']
inputs[raw_export['path']] = raw_export['sha256']
old_by_url = {(x['offer_ref'], x['source_url']): x for x in historical_gallery}
gallery, gallery_scope = [], []
for i, product in enumerate(local_gallery['records']):
    scope = 'COMPLETE_AUTHENTICATED_LOCAL_EXPORT_PRODUCT_GALLERY'
    gallery_scope.append({'offer_ref': product['offer_ref'], 'native_product_id': product['native_product_id'],
        'membership_status': scope, 'known_media_count': len(product['ordered_gallery']),
        'captured_utc': product['captured_utc'], 'csv_row': product['csv_record_including_header_1based']})
    for j, item in enumerate(product['ordered_gallery']):
        old = old_by_url.get((product['offer_ref'], item['url']), {})
        gallery.append({'gallery_entry_id': digest([product['offer_ref'], item['url'], j + 1]),
            'offer_ref': product['offer_ref'], 'native_product_id': product['native_product_id'],
            'native_media_id': old.get('native_media_id'),
            'native_media_id_scope': 'Historical retained collection observation only' if old.get('native_media_id') else 'Not exported',
            'gallery_order': j + 1, 'source_url': item['url'],
            'source_document': str(local_gallery_path), 'source_document_sha256': inputs[str(local_gallery_path)],
            'json_pointer': f'/records/{i}/ordered_gallery/{j}', 'raw_export': raw_export,
            'csv_record_including_header_1based': item['csv_record_including_header_1based'],
            'captured_utc': product['captured_utc'], 'membership_status': scope,
            'variant_specific_assignment_certified': False,
            'download_status': 'NOT_YET_INTEGRATED', 'visual_review_status': 'NOT_YET_INTEGRATED', 'file_correspondences': []})
assert len(gallery) == 445 and len(gallery_scope) == 80

db = sqlite3.connect(run / 'image-register.sqlite')
db.executescript('''
CREATE TABLE metadata (key TEXT PRIMARY KEY, value_json TEXT NOT NULL);
CREATE TABLE products (product_id TEXT PRIMARY KEY, name TEXT NOT NULL, family TEXT, record_json TEXT NOT NULL);
CREATE TABLE images (file_id TEXT PRIMARY KEY, folder_id TEXT, path TEXT, is_image INTEGER, in_wall_tree INTEGER, record_json TEXT NOT NULL);
CREATE TABLE associations (association_id TEXT PRIMARY KEY, product_id TEXT NOT NULL, file_id TEXT NOT NULL, intended_use TEXT, status TEXT, record_json TEXT NOT NULL);
CREATE INDEX associations_product ON associations(product_id);
CREATE INDEX associations_image ON associations(file_id);
CREATE TABLE source_gallery (gallery_entry_id TEXT PRIMARY KEY, offer_ref TEXT NOT NULL, native_product_id TEXT, native_media_id TEXT, source_url TEXT, record_json TEXT NOT NULL);
''')
dump = lambda obj: json.dumps(obj, ensure_ascii=False)
db.executemany('INSERT INTO products VALUES(?,?,?,?)', [(oid, o['name'], o.get('family'), dump(o)) for oid, o in products.items()])
db.executemany('INSERT INTO images VALUES(?,?,?,?,?,?)', [(fid, row['folder_id'], row['path'], row['is_image'], row['in_wall_sculpture_tree'], dump(row)) for fid, row in images.items()])
db.executemany('INSERT INTO associations VALUES(?,?,?,?,?,?)', [(row['association_id'], row['product_id'], row['file_id'], row['intended_use'], row['association_status'], dump(row)) for row in associations.values()])
db.executemany('INSERT INTO source_gallery VALUES(?,?,?,?,?,?)', [(row['gallery_entry_id'], row['offer_ref'], row['native_product_id'], row['native_media_id'], row['source_url'], dump(row)) for row in gallery])
summary = {
    'status': 'PREPARATION_COMPLETE_REVIEW_AND_MATCHING_IN_PROGRESS', 'recorded_utc': datetime.now(timezone.utc).isoformat(),
    'baseline_pointer_sha256': pointer_hash, 'active_products': len(products), 'saved_asset_map_records': len(asset_map), 'retained_and_current_asset_records': len(images),
    'wall_image_assets': len(fresh),
    'current_inventory_status_counts': dict(Counter(x['inventory_status'] for x in images.values())),
    'navigation_changes_since_saved_map': len(navigation_changes),
    'newly_inventoried_file_ids': len(set(fresh) - set(asset_map)),
    'association_rows': len(associations), 'association_status_counts': dict(Counter(x['association_status'] for x in associations.values())),
    'scoped_source_offers': len(offers), 'known_gallery_entries': len(gallery), 'unique_source_urls': len({x['source_url'] for x in gallery}),
    'gallery_membership_status_counts': dict(Counter(x['membership_status'] for x in gallery_scope)),
    'full_gallery_unestablished_refs': [x['offer_ref'] for x in gallery_scope if x['membership_status'].startswith('SAMPLE_ONLY')],
    'finished_requirements': [], 'canonical_writes': 0,
    'limits': ['Candidate folder associations are not confirmed image identities.', 'Fresh current native inventory is integrated; all prior visual reviews and per-image roles are not yet integrated.', 'All five objective requirements remain active.']
}
db.execute('INSERT INTO metadata VALUES(?,?)', ('summary', dump(summary)))
db.execute('INSERT INTO metadata VALUES(?,?)', ('input_manifest', dump(inputs)))
db.commit()
assert db.execute('SELECT COUNT(*) FROM products').fetchone()[0] == 188
assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
db.close()
write(run / 'summary.json', summary)
write(run / 'input-manifest.json', inputs)
write(run / 'gallery-membership.json', gallery_scope)
write(run / 'source-gallery.json', gallery)
write(run / 'historical-source-gallery.json', historical_gallery)
write(run / 'images.json', list(images.values()))
write(run / 'associations.json', list(associations.values()))
write(run / 'navigation-changes.json', navigation_changes)
counts = Counter(x['product_id'] for x in associations.values() if x['association_status'] != 'FOLDER_CANDIDATE_REQUIRES_VISUAL_REVIEW')
candidate_counts = Counter(x['product_id'] for x in associations.values() if x['association_status'] == 'FOLDER_CANDIDATE_REQUIRES_VISUAL_REVIEW')
e = lambda value: html.escape(str(value), quote=True)
rows = ''.join('<tr><td>' + e(o['name']) + '</td><td>' + str(counts[oid]) + '</td><td>' + str(candidate_counts[oid]) + '</td><td>' + ('<a href="' + e(o['image_url']) + '">Selected image</a> · ' if o.get('image_url') else '') + ('<a href="' + e(o['folder_url']) + '">Folder</a>' if o.get('folder_url') else 'No selected folder') + '</td></tr>' for oid, o in sorted(products.items(), key=lambda item: item[1]['name']))
page = '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Complete image matching in progress</title><style>body{font:16px system-ui;max-width:1150px;margin:32px auto;padding:0 20px;line-height:1.5}td,th{padding:10px;border-bottom:1px solid #ddd;text-align:left}table{border-collapse:collapse;width:100%}</style></head><body><h1>All-product image matching: in progress</h1><p>All 188 active catalogue options are represented. Recorded references and source examples are distinct from folder candidates. Candidate counts are association rows, not verified photographs. Full visual roles, current links, held identities and current platform matches are still being completed.</p><table><tr><th>Product / finish</th><th>Recorded reference / source rows</th><th>Folder candidate rows</th><th>Existing links</th></tr>' + rows + '</table></body></html>'
(run / 'index.html').write_text(page)
assert sha(pointer_path) == pointer_hash
write(H / 'current-work.json', {'status': summary['status'], 'run': str(run), 'summary': str(run / 'summary.json'), 'database': str(run / 'image-register.sqlite'), 'reader': str(run / 'index.html')})
print(json.dumps({'run': str(run), 'summary': summary}, indent=2))
