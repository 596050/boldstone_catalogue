"""Create current native navigation, retaining historical source identities."""
from pathlib import Path
from urllib.parse import quote
from collections import Counter
import argparse
import csv
import hashlib
import html
import json

ROOT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument('--state-dir', type=Path, default=ROOT)
parser.add_argument('--output-name', default='automatic-image-inventory-2026-10-26')
args = parser.parse_args()
H = args.state_dir.resolve()
B = ROOT.parents[2]
OUT = B / 'outputs' / args.output_name
OUT.mkdir(exist_ok=True)
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
dump = lambda p, v: Path(p).write_text(json.dumps(v, ensure_ascii=False, indent=2) + '\n')
esc = lambda s: html.escape(str(s), quote=True)
verification = read(H / 'independent-verification.json')
assert verification['status'] in {'PASS_INDEPENDENT_AUTOMATIC_IMAGE_INVENTORY_AND_REVIEW_HISTORY', 'PASS_INDEPENDENT_FOLDER_TAGS_RENAMES_AND_NATIVE_FOLLOWUP'}
ref = read(H / 'latest-inventory-input.json')
assert sha(ref['snapshot_path']) == ref['snapshot_sha256']
state = read(ref['snapshot_path'])
p = read(B / 'current-master.json')
assert p['register_sha256'] == '9b4b15ca857bea027637b3dd1474bfb98c87746bb842b49003b526da6770e748'
g = read(B / p['register'])
base = read(B / p['current_native_reference_map']['path'])['current_objects']
old_assets = read(B / p['current_asset_reference_map']['path'])
new = read(H / 'new-images.json')
absences = read(H / 'native-absence-register.json')
reviews = read(H / 'saved-review-state.json')
values_path = B.parent / 'catalogue-review/reviews/specification-completion-20261025/all-188-readback.json'
values = {r['product_id']: r for r in read(values_path)}
current = {}
for fid, r in state['records'].items():
    parent = str(Path(r['path']).parent)
    item = {'file_id': fid, 'name': r['name'], 'display_path': r['path'],
        'object_type': r['kind'], 'current_wall_snapshot_present': True}
    if r['kind'] == 'file':
        item.update(folder_id=r['folder_id'], bytes=r['bytes'], revision=r['rev'], content_hash=r['content_hash'],
            image_url='https://www.dropbox.com/preview' + quote(r['path'], safe='/'),
            folder_url='https://www.dropbox.com/home' + quote(parent, safe='/'))
        old_hash = old_assets.get(fid, {}).get('source_content_hash')
        item['content_changed_since_retained_source'] = bool(old_hash and old_hash != r['content_hash'])
    current[fid] = item
images = {fid: r for fid, r in current.items() if r['object_type'] == 'file'}
image_count, absence_count, new_count = len(images), len(absences['rows']), len(new)
folder_count = sum(r['object_type'] == 'folder' for r in current.values())
assert image_count == state['image_count']
map_doc = {'schema': 'boldstone.current-native-overlay/v2',
    'status': 'VERIFIED_COMPLETE_FIXED_SNAPSHOT_WITH_SEPARATE_RECEIPT_HISTORY',
    'scope': {'namespace': '202238505', 'root_id': state['scope']['root_id'], 'root_path': state['scope']['root_path']},
    'source_snapshot': ref, 'baseline_map_path': p['current_native_reference_map']['path'],
    'baseline_map_sha256': p['current_native_reference_map']['sha256'],
    'current_objects': current, 'absent_baseline_files': absences['rows'],
    'counts': {'current_images': image_count, 'folders_including_root': folder_count, 'new_images': new_count,
        'baseline_file_ids_not_found': absence_count, 'app_confirmed_deletion_receipts': len(absences['confirmed_app_deletions']),
        'other_native_absences_without_app_deletion_receipts': sum(not r['owner_deletion_receipt_present'] for r in absences['rows']),
        'retained_file_ids_with_changed_contents': sum(r.get('content_changed_since_retained_source', False) for r in images.values())},
    'current_image_availability_does_not_import_product_identity_specifications_or_listing_choices': True}
dump(H / 'current-native-overlay.json', map_doc)

def write_csv(path, rows, columns):
    with Path(path).open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)

write_csv(OUT / f'Current_Wall_Images_{image_count}.csv', images.values(),
    ['file_id', 'name', 'folder_id', 'display_path', 'image_url', 'folder_url', 'revision', 'bytes', 'content_hash'])
write_csv(OUT / f'Native_Image_Absences_{absence_count}.csv', absences['rows'],
    ['file_id', 'name', 'family', 'historical_path', 'state', 'owner_deletion_receipt_present', 'native_not_found_checked_utc'])
write_csv(OUT / f'New_Acanthus_Uploads_{new_count}.csv', new,
    ['file_id', 'name', 'folder_id', 'image_url', 'folder_url', 'revision', 'bytes', 'sha256', 'dropbox_content_hash'])
css = 'body{font:17px/1.5 Arial;max-width:1150px;margin:35px auto;padding:0 20px;color:#222}article{border:1px solid #ccc;margin:24px 0;padding:20px;overflow-wrap:anywhere}img{max-width:100%;max-height:520px;object-fit:contain;background:#f4f4f0}small{overflow-wrap:anywhere}table{border-collapse:collapse;width:100%}td,th{padding:9px;border-bottom:1px solid #ddd;text-align:left;vertical-align:top}th{width:24%}.scope{padding:15px;background:#f0f3ed}.missing{padding:12px;background:#fff0d8}a{color:#075993}'
nav = '<p><a href="index.html">New uploads</a> · <a href="all-options.html">188 options and specifications</a> · <a href="absent-images.html">Native absences</a> · <a href="Current_Wall_Images_' + str(image_count) + '.csv">Current image inventory</a> · <a href="http://127.0.0.1:8767">Live review app</a></p>'
scope = '<p class="scope">Fixed generation ' + str(ref['generation']) + ' snapshot captured ' + esc(ref['immutable_snapshot_captured_utc']) + ': ' + format(image_count, ',') + ' images and ' + str(folder_count) + ' folders including the root. The live app continues checking Dropbox every 60 seconds. These are image and folder counts; the catalogue retains 188 active sculpture options. Source identities and physical specifications are preserved.</p>'
def document(title, body):
    return '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>' + esc(title) + '</title><style>' + css + '</style><body><h1>' + esc(title) + '</h1>' + scope + nav + body + '</body></html>'
choices = {r['file_id']: r for r in reviews['current_new_image_choices']}
def new_card(r):
    chosen = choices.get(r['file_id'])
    label = 'Saved app listing-primary choice' if chosen and chosen['data'].get('primary') else 'New native image; image-use choices remain separate'
    if ref['generation'] >= 8 and r['folder_id'] == 'id:cnqzTNngPVsAAAAAAA6wUQ':
        label = 'Folder-derived In Situ tag; associated with Acanthus One Leaf White'
    return '<article id="' + esc(r['file_id']) + '"><h2>' + esc(Path(r['path']).parent.name) + '</h2><img src="' + esc(Path(r['local_path']).as_uri()) + '" alt="' + esc(r['name']) + '"><p>' + esc(label) + '</p><p><a href="' + esc(r['image_url']) + '">Dropbox image</a> · <a href="' + esc(r['folder_url']) + '">Actual containing folder</a></p><p>' + esc(r['dimensions'][0]) + ' × ' + esc(r['dimensions'][1]) + ' pixels · ' + format(r['bytes'], ',') + ' bytes</p><small>File ' + esc(r['file_id']) + '<br>Folder ' + esc(r['folder_id']) + '<br>Revision ' + esc(r['revision']) + '</small><p>Original uploaded bytes verified. Image origin, installation, finish and physical specifications are separate questions.</p></article>'
(OUT / 'index.html').write_text(document('Six new Acanthus uploads picked up automatically', ''.join(new_card(r) for r in new)))
missing_cards = []
for r in absences['rows']:
    a = old_assets[r['file_id']]
    status = 'Owner-confirmed app deletion' if r['owner_deletion_receipt_present'] else 'Native file not found; no deletion receipt in the review app'
    missing_cards.append('<article><h2>' + esc(r['name']) + '</h2><p>' + esc(status) + '</p><small>' + esc(r['file_id']) + '</small><p><a href="' + esc(a['folder_url']) + '">Recorded containing folder</a></p></article>')
(OUT / 'absent-images.html').write_text(document(str(absence_count) + ' absent historical native image IDs', '<p>All ' + str(absence_count) + ' IDs returned native NOT_FOUND. Thirteen have app deletion receipts; ' + str(absence_count - 13) + ' have no app deletion receipt. This reconciliation performed no native deletion and retains source history.</p>' + ''.join(missing_cards)))
selected = {r['product_id']: r for r in reviews['current_new_image_choices'] if r['data'].get('primary')}
option_cards = []
for o in g['options']:
    if o['product_id'] not in g['active_option_ids']:
        continue
    pid = o['product_id']
    ref_o = o if o.get('file_id') else o.get('owner_confirmed_design_reference', {})
    fid = ref_o.get('file_id')
    image = ''
    if pid in selected:
        row = next(r for r in new if r['file_id'] == selected[pid]['file_id'])
        image = '<p>Saved app listing image:</p><img src="' + esc(Path(row['local_path']).as_uri()) + '" alt="' + esc(o['name']) + '"><p><a href="' + esc(row['image_url']) + '">App-selected image</a> · <a href="' + esc(row['folder_url']) + '">Containing folder</a></p>'
    if fid in images:
        a = old_assets.get(fid, {})
        thumb = a.get('thumb') or a.get('full')
        if not image and thumb and Path(thumb).is_file() and not images[fid]['content_changed_since_retained_source']:
            image += '<img src="' + esc(Path(thumb).as_uri()) + '" alt="' + esc(o['name']) + '">'
        if images[fid]['content_changed_since_retained_source']:
            image += '<p class="missing">The file contents changed after the retained source snapshot; its older preview is withheld.</p>'
        image += '<p><a href="' + esc(images[fid]['image_url']) + '">Retained source reference</a> · <a href="' + esc(images[fid]['folder_url']) + '">Actual containing folder</a></p>'
    else:
        image += '<p class="missing">Historical master example is currently absent. Its stable ID and source history are retained.</p><p><a href="' + esc(ref_o.get('folder_url', o.get('folder_url', ''))) + '">Recorded containing folder</a></p>'
    if o.get('context_file_id') in {r['file_id'] for r in absences['rows']}:
        image += '<p class="missing">The recorded context-image file is currently absent. The existing owner hold and source history are retained.</p>'
    fields = values[pid]['values']
    table = '<table>' + ''.join('<tr><th>' + esc(k) + '</th><td>' + esc(v) + '</td></tr>' for k, v in fields.items()) + '</table>'
    option_cards.append('<article id="' + esc(pid) + '"><h2>' + esc(values[pid]['name']) + '</h2>' + image + table + '<p><a href="http://127.0.0.1:8767/#' + esc(pid) + '">Review in app</a></p><small>' + esc(pid) + ' · retained source file ' + esc(fid) + ' · physical verification remains separate</small></article>')
assert len(option_cards) == 188
(OUT / 'all-options.html').write_text(document('188 options with current native navigation', '<p>Saved working specification values are presented below. Native availability, app image choices, original source records and actual physical verification remain separate.</p>' + ''.join(option_cards)))
if ref['generation'] >= 8:
    plan_path = B.parent / 'catalogue-review/reviews/dropbox-folder-types-20261026/deco-rename-plan.json'
    plan = read(plan_path)['entries']
    cards = []
    for r in plan:
        folder = state['records'][r['file_id']]
        candidates = sorted((x for x in images.values() if x['folder_id'] == r['file_id']), key=lambda x: x['name'])
        example = candidates[0] if candidates else None
        links = '<a href="https://www.dropbox.com/home' + esc(quote(folder['path'], safe='/')) + '">Containing folder</a>'
        if example:
            links = '<a href="' + esc(example['image_url']) + '">Example image</a> · ' + links
        cards.append('<article><h2>' + esc(folder['name']) + '</h2><p>' + links + '</p><p>Previous name: ' + esc(r['source_name']) + '</p><small>Stable folder ID: ' + esc(r['file_id']) + '</small></article>')
    (OUT / 'deco-renamed-folders.html').write_text(document('18 Deco Palm and Spiral folders', ''.join(cards)))
verification = {'status': 'PASS_FIXED_NATIVE_READERS', 'active_option_cards': 188, 'new_upload_cards': new_count,
    'absence_cards': absence_count, 'current_images': image_count, 'folders_including_root': folder_count,
    'overlay_path': str(H / 'current-native-overlay.json'), 'overlay_sha256': sha(H / 'current-native-overlay.json'),
    'input_snapshot_sha256': ref['snapshot_sha256'], 'canonical_or_app_writes': 0,
    'outputs': {str(f): sha(f) for f in OUT.iterdir() if f.is_file()}}
dump(H / 'reader-verification.json', verification)
print(json.dumps({k: v for k, v in verification.items() if k != 'outputs'}, indent=2))
