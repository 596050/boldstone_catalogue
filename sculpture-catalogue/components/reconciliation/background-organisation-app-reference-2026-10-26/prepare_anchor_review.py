"""Prepare a read-only folder-anchor review; never writes shared catalogue state."""
from collections import Counter
from datetime import datetime, timezone
from html import escape
from pathlib import Path, PurePosixPath
from urllib.parse import quote
import hashlib
import json
import urllib.request

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[2]
OUT = HERE / 'anchor-review'
OUT.mkdir(exist_ok=True)


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def get(path):
    with urllib.request.urlopen('http://127.0.0.1:8767' + path, timeout=30) as response:
        return json.load(response)


def folder_url(path):
    return 'https://www.dropbox.com/home' + quote(path, safe='/')


def file_url(path):
    return 'https://www.dropbox.com/preview' + quote(path, safe='/')


pointer_path = BASE / 'current-master.json'
pointer_sha = sha(pointer_path)
pointer = read(pointer_path)
register_path = BASE / pointer['register']
assert sha(register_path) == pointer['register_sha256']
register = read(register_path)
verification = read(HERE / 'independent-verification.json')
held = {row['product_id']: row for row in verification['computed_plans']
        if row['status'] == 'needs_review'}
assert len(held) == 15
bootstrap = get('/api/bootstrap')
assert bootstrap['source']['register_sha256'] == pointer['register_sha256']
native_path = Path(bootstrap['source']['live_dropbox']['path'])
assert sha(native_path) == bootstrap['source']['live_dropbox']['sha256']
native = read(native_path)['records']
folders = {row['path']: row for row in native.values() if row['kind'] == 'folder'}
options = {row['product_id']: row for row in register['options']}
rows = []

for option in register['options']:
    pid = option['product_id']
    if pid not in held:
        continue
    source_id = option.get('file_id', '')
    source_folder_id = option.get('folder_id', '')
    image = native.get(source_id)
    folder = native.get(source_folder_id)
    parent = folders.get(str(PurePosixPath(image['path']).parent)) if image else None
    if image:
        assert image['kind'] == 'file' and parent and parent['id'] == source_folder_id
        kind = 'shared_folder'
        image_link = file_url(image['path'])
        folder_link = folder_url(parent['path'])
        navigation_basis = 'Exact file ID and actual containing-folder ID in the captured Wall inventory.'
    elif source_id:
        kind = 'accepted_reference_outside_wall_inventory'
        image_link = option['image_url']
        folder_link = option['folder_url']
        navigation_basis = 'Retained accepted reference outside the Wall inventory. Absence here is not a deletion finding.'
    else:
        kind = 'legacy_option_without_exact_file_anchor'
        image_link = folder_link = ''
        navigation_basis = 'No exact file/folder binding for this retained historical option.'
    family_root = '/BOLDSTONE MASTER/Products/01 Wall Sculptures/' + option['family']
    candidate_folders = [
        {'id': row['id'], 'path': row['path'], 'url': folder_url(row['path'])}
        for row in native.values()
        if row['kind'] == 'folder' and str(PurePosixPath(row['path']).parent) == family_root
    ]
    rows.append({
        'product_id': pid, 'name': option['name'], 'family': option['family'],
        'classification': kind, 'planner_reason': held[pid]['reason'],
        'retained_file_id': source_id, 'retained_folder_id': source_folder_id,
        'observed_file': image, 'observed_containing_folder': parent,
        'image_url': image_link, 'folder_url': folder_link,
        'navigation_basis': navigation_basis,
        'family_url': folder_url(family_root),
        'existing_family_folders_not_identity_matches': candidate_folders,
        'identity_basis_preserved': option.get('identity_basis', ''),
        'photograph_coverage_preserved': option.get('photo_coverage', {}),
        'no_specification_stock_price_or_variant_inference': True,
    })

# The accepted Cup Ring reference has closed rings. The current isolated PNG in
# folder 1 has the same complete relief geometry. Folder 2's sampled PNG is a
# spiral in another finish; the historical CRS2 code is not a folder number.
cup = options['BSI-ADD5F3BEFCF5']
candidate_id = 'id:cnqzTNngPVsAAAAAAA53Yw'
candidate = native[candidate_id]
candidate_parent = folders[str(PurePosixPath(candidate['path']).parent)]
cached = OUT / 'previews/cup-folder1.image'
digest = hashlib.sha256()
with cached.open('rb') as stream:
    while block := stream.read(4 * 1024 * 1024):
        digest.update(hashlib.sha256(block).digest())
assert digest.hexdigest() == candidate['content_hash']
assert cached.stat().st_size == candidate['bytes']
assert candidate_parent['id'] == 'id:cnqzTNngPVsAAAAAAAyiRQ'
assert not any(o['product_id'] != cup['product_id'] and
               o.get('folder_id') == candidate_parent['id']
               for o in register['options'] if o['product_id'] in register['active_option_ids'])
queued = {
    'status': 'VISUAL_DESIGN_MATCH_QUEUED_FOR_FINAL_NATIVE_PATH_READBACK',
    'product_id': cup['product_id'], 'name_unchanged': cup['name'],
    'retained_accepted_reference_file_id': cup['file_id'],
    'proposed_current_file_id': candidate_id,
    'proposed_current_folder_id': candidate_parent['id'],
    'observed_image_url': file_url(candidate['path']),
    'observed_folder_url': folder_url(candidate_parent['path']),
    'cached_original_sha256': sha(cached),
    'cached_original_dropbox_content_hash': digest.hexdigest(),
    'cached_bytes_match_current_native_metadata': True,
    'visual_basis': 'Both references show the complete square white relief with closed concentric rings and no spiral centre.',
    'other_folder_sample_file_id': 'id:cnqzTNngPVsAAAAAAA53VQ',
    'other_folder_sample_observation': 'Spiral centre; sampled finish differs. Do not map CRS2 from the folder number.',
    'canonical_or_app_review_update_applied': False,
    'no_specifications_or_platform_offer_transferred': True,
}

report = {
    'status': 'READ_ONLY_15_FOLDER_ANCHOR_REVIEW_WITH_ONE_QUEUED_VISUAL_MATCH',
    'recorded_utc': datetime.now(timezone.utc).isoformat(),
    'canonical_pointer_sha256': pointer_sha,
    'register': str(register_path), 'register_sha256': sha(register_path),
    'active_options': len(register['active_option_ids']),
    'inventory': str(native_path), 'inventory_sha256': sha(native_path),
    'inventory_checked_utc': bootstrap['source']['live_dropbox']['checked_utc'],
    'snapshot_paths_can_change_during_filename_pass': True,
    'classifications': dict(Counter(row['classification'] for row in rows)),
    'folder_anchor_cases_are_not_a_sculpture_or_missing_photo_count': True,
    'owner_photograph_holds_preserved': True,
    'rows': rows, 'queued_primary_reference_update': queued,
    'shared_source_app_review_and_native_writes': 0,
}
assert sha(pointer_path) == pointer_sha
(OUT / 'folder-anchor-review.json').write_text(json.dumps(report, indent=2) + '\n')

def link(url, label):
    return '<a href="' + escape(url, quote=True) + '">' + escape(label) + '</a>' if url else 'No exact reference'


cards = []
for row in rows:
    details = '<p>' + link(row['image_url'], 'Example image') + ' · ' + link(row['folder_url'], 'Containing folder') + ' · ' + link(row['family_url'], 'Family folder') + '</p>'
    details += '<p>' + escape(row['navigation_basis']) + '</p>'
    details += '<p><small>File: ' + escape(row['retained_file_id'] or 'unbound') + '<br>Folder: ' + escape(row['retained_folder_id'] or 'unbound') + '</small></p>'
    details += '<p>' + escape(row['planner_reason']) + '</p>'
    if row['product_id'] == queued['product_id']:
        details += '<p><strong>Current Wall folder match queued:</strong> ' + link(queued['observed_image_url'], 'Isolated white closed-ring panel') + ' · ' + link(queued['observed_folder_url'], 'Actual containing folder') + '. Cached original bytes match the captured Dropbox metadata. Catalogue publication awaits final rename readback.</p>'
    cards.append('<article><h2>' + escape(row['name']) + '</h2><p><code>' + escape(row['product_id']) + '</code></p>' + details + '</article>')
html = '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Folder mapping review</title><style>body{max-width:980px;margin:36px auto;padding:0 22px;font:17px/1.5 system-ui;color:#202725}article{border-top:1px solid #ced6d1;padding:18px 0}h1{font-size:30px}h2{font-size:22px}a{color:#14583f}small,code{overflow-wrap:anywhere}</style><body><h1>Folder mapping review</h1><p>15 catalogue options currently lack a unique individual folder anchor for automatic image moves. This is a folder mapping list, not a sculpture count or a missing-photograph list.</p><p>One Cup Ring match is prepared. The master, app reviews and Dropbox remain unchanged. Existing photograph holds and specification qualifications remain in force.</p><p>Snapshot: ' + escape(report['inventory_checked_utc']) + '. Filenames may change while the rename pass finishes; stable IDs are retained below.</p>' + ''.join(cards) + '</body></html>'
(OUT / 'folder-anchor-review.html').write_text(html)
print(json.dumps({k: report[k] for k in ['status', 'active_options', 'classifications', 'shared_source_app_review_and_native_writes']}, indent=2))
