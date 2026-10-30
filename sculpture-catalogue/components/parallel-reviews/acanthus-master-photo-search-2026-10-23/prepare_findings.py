import datetime
import hashlib
import html
import json
import shutil
from pathlib import Path
from urllib.parse import quote

HERE = Path(__file__).resolve().parent
CAT = HERE.parents[2]
now = datetime.datetime.now(datetime.timezone.utc).isoformat()
def load(p): return json.loads(p.read_text())
def save(name, value):
    (HERE / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
def browse(path, kind='preview'):
    return 'https://www.dropbox.com/' + kind + quote(path, safe='/')

family = load(HERE / 'family-listings.json')
pages = family['pages']
assert len(pages) == 16
assert all(not x['listing'].get('has_more') for x in pages)
files = [e for p in pages for e in p['listing']['entries'] if e['object_type'] == 'file']
assert len(files) == 79
assert not any('sandstone' in p['folder']['name'].lower() for p in pages)
current = load(CAT / 'current-master.json')
register = load(CAT / current['register'])
source = load(HERE / 'context-original-verification.json')
sources = {r['id']: r for r in source}
scene = sources['id:cnqzTNngPVsAAAAAAAuf1w']
primary = sources['id:cnqzTNngPVsAAAAAAAygFw']
scene_copy = HERE / 'originals' / 'cnqzTNngPVsAAAAAAAuf1w.jpg'
if not scene_copy.exists(): shutil.copyfile(scene['local_path'], scene_copy)
assert hashlib.sha256(scene_copy.read_bytes()).hexdigest() == scene['sha256']
scene['local_review_copy'] = str(scene_copy)
folder = '/BOLDSTONE MASTER/Products/01 Wall Sculptures/Acanthus/Acanthus and Moon and Others Together'
bronze_folder = '/BOLDSTONE MASTER/Products/01 Wall Sculptures/Acanthus/Acanthus Two Leaves Bronze'
question = 'Use this courtyard image as the installation reference for Acanthus Two Leaves — Bronze, shown as the right-hand square panel?'
review = {
    'schema': 1, 'recorded_utc': now, 'owner_thread': '01a13fe6-495b-7253-b923-31823b4cbca8',
    'status': 'PREPARED_AWAITING_OWNER_REVIEW', 'product_id': 'BSI-A9FE7D79863A',
    'name': 'Acanthus Two Leaves — Bronze', 'role': 'In situ',
    'question': question, 'suggested_replies': ['Use image', 'Different sculpture or finish', 'Next'],
    'candidate': {
        'file_id': scene['id'], 'folder_id': 'id:cnqzTNngPVsAAAAAAAyhzw',
        'path': scene['path'], 'display_path': scene['path_display'],
        'image_url': browse(scene['path_display']), 'folder_url': browse(folder, 'home'),
        'sha256': scene['sha256'], 'content_hash': scene['content_hash'],
        'local_path': str(scene_copy), 'target_position': 'Right-hand square panel',
    },
    'comparison_primary': {
        'file_id': primary['id'], 'folder_id': 'id:cnqzTNngPVsAAAAAAAygEg',
        'image_url': browse(primary['path_display']), 'folder_url': browse(bronze_folder, 'home'),
        'sha256': primary['sha256'], 'local_path': primary['local_path'],
    },
    'visual_assessment': 'The right-hand square courtyard panel has two sweeping concentric crescent bands and a brown/bronze appearance consistent with the current Bronze Two Leaves primary. Proposed design-and-finish context association; exact physical cast, size, finish formulation and image provenance are not established.',
    'other_components_in_scene': 'Context only; no additional products or component identifications proposed.',
    'existing_position_records': ['REF-BC-PORTMAN-1', 'REF-BC-PORTMAN-2'],
    'existing_position_records_unchanged': True,
    'owner_approved': False, 'canonical_import_performed': False, 'dropbox_writes': False,
}
save('installation-review.json', review)
findings = {
    'schema': 1, 'recorded_utc': now, 'status': 'BOUNDED_MASTER_SEARCH_COMPLETE_GAPS_REMAIN',
    'source_scope': '/BOLDSTONE MASTER',
    'scope_limit': 'Complete current direct-child inventory of Acanthus and its16 child folders, plus returned Master-wide filename search candidates. This is not an exhaustive visual review of every photograph elsewhere in Master.',
    'family_folders': 16, 'family_files': 79, 'all_family_listing_pages_complete': True,
    'search_queries': ['acanthus', 'sandstone', 'one leaf'],
    'additional_native_document_images_inspected': 4,
    'document_findings': [
        {'file_id': 'id:cnqzTNngPVsAAAAAAAyXOA', 'name': 'acanthus 1.JPG', 'finding': 'White full multi-leaf landscape relief on a board; not Sandstone/Pewter One Leaf or a series photograph.'},
        {'file_id': 'id:cnqzTNngPVsAAAAAAAyciw', 'name': 'acanthus 3.JPG', 'finding': 'White individual curved relief against plywood; no Sandstone/Pewter finish or wider installation setting.'},
        {'file_id': 'id:cnqzTNngPVsAAAAAAAyXHw', 'name': 'acanthus 21.JPG', 'finding': 'Tighter image of White landscape relief; not requested individual/series coverage.'},
        {'file_id': 'id:cnqzTNngPVsAAAAAAAyW2Q', 'name': 'acanthus 211.JPG', 'finding': 'Cooler/desaturated version of the same White landscape composition; not evidence of Pewter manufacture.'},
    ],
    'current_family_candidates_inspected': [
        {'file_id': 'id:cnqzTNngPVsAAAAAAA6Vkw', 'finding': 'Isolated White One Leaf panel on plain wall; no wider installation or series context.'},
        {'file_id': 'id:cnqzTNngPVsAAAAAAA6VlA', 'finding': 'Isolated White One Leaf panel on plain wall; no wider installation or series context.'},
        {'file_id': 'id:cnqzTNngPVsAAAAAAA6VmA', 'finding': 'Current complete Pewter One Leaf reference retained; no wider installation or series context.'},
        {'file_id': 'id:cnqzTNngPVsAAAAAAAuh_Q', 'finding': 'Courtyard scene, source documented as Bronze effect; no verified Sandstone/Pewter One Leaf association.'},
        {'file_id': 'id:cnqzTNngPVsAAAAAAAuf1w', 'finding': 'Closer courtyard scene with two panels; candidate right panel matches Two Leaves, not One Leaf. Prepared separate Bronze installation review.'},
        {'file_id': 'id:cnqzTNngPVsAAAAAAAygFw', 'finding': 'Bronze Two Leaves individual primary inspected for courtyard comparison.'},
    ],
    'unresolved': [
        {'product_id': 'BSI-C41824131174', 'name': 'Acanthus One Leaf Left — Sandstone', 'role': 'Individual', 'action': 'Locate or capture complete individual Sandstone photograph in BOLDSTONE MASTER. No verified replacement found in this pass.'},
        {'product_id': 'BSI-C41824131174', 'name': 'Acanthus One Leaf Left — Sandstone', 'role': 'Series', 'action': 'Locate or capture a series photograph clearly including this Sandstone option in BOLDSTONE MASTER.'},
        {'product_id': 'BSI-3635E3DC3434', 'name': 'Acanthus One Leaf Left — Pewter', 'role': 'Series', 'action': 'Locate or capture a series photograph clearly including this Pewter option in BOLDSTONE MASTER.'},
    ],
    'existing_gaps_preserved': True, 'new_photo_bindings': 0, 'new_product_ids': 0,
    'backup_images_used_as_current_evidence': False, 'cropped_or_generated_images_created': False,
    'canonical_writes': False, 'dropbox_writes': False,
    'review_packet': str(HERE / 'installation-review.json'),
    'evidence_files': ['family-listings.json', 'search-acanthus.json', 'search-sandstone.json', 'search-one_leaf.json', 'document-source-metadata.json', 'document-original-verification.json', 'context-original-verification.json'],
}
save('findings.json', findings)
e = html.escape
page = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Acanthus Two Leaves — Bronze | Installation review</title><style>body{font:18px/1.5 system-ui,sans-serif;background:#f5f3ee;color:#23241e;margin:0;padding:2rem;max-width:1300px;margin:auto}h1{font-size:2rem}a{color:#255b58}main{display:grid;grid-template-columns:1fr 1fr;gap:2rem}figure{margin:0;background:white;padding:1rem}img{width:100%;height:650px;object-fit:contain}figcaption{margin-top:.7rem}.question{font-weight:650;font-size:1.2rem;background:#e4ebe2;padding:1rem}small{color:#565c54}@media(max-width:750px){main{grid-template-columns:1fr}img{height:auto}body{padding:1rem}}</style>'''
page += '<h1>Next: Acanthus Two Leaves — Bronze</h1><p>Compare the right-hand square panel in the courtyard with the individual sculpture below.</p><main>'
for title, path, link, folder_link in [
    ('Courtyard image — proposed installation reference', 'originals/cnqzTNngPVsAAAAAAAuf1w.jpg', review['candidate']['image_url'], review['candidate']['folder_url']),
    ('Current individual Bronze reference', 'originals/cnqzTNngPVsAAAAAAAygFw.jpg', review['comparison_primary']['image_url'], review['comparison_primary']['folder_url']),
]:
    page += f'<figure><img src="{e(path)}" alt="{e(title)}"><figcaption>{e(title)}<br><a href="{e(link)}">Dropbox image</a> · <a href="{e(folder_link)}">Containing folder</a></figcaption></figure>'
page += '</main><p class="question">' + e(question) + '</p><p>Reply: <strong>Use image</strong>, <strong>Different sculpture or finish</strong>, or <strong>Next</strong>.</p><small>The other panel remains context. This review does not establish measured size, stock or installation provenance.</small></html>'
(HERE / 'installation-review.html').write_text(page)
print(json.dumps({'status': findings['status'], 'open_photo_requirements': 3, 'review': str(HERE / 'installation-review.html')}))
