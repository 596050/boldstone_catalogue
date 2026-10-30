"""Prepare a private navigation draft; never publish or mutate Dropbox/app state."""
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from html import escape
from pathlib import Path, PurePosixPath
from urllib.parse import quote
import hashlib
import json
import sqlite3

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[2]
NATIVE = Path('/Users/tprice/BoldstoneMigration/path-renaming-20261026')
INPUTS = HERE / 'inputs'
INPUTS.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
read = lambda path: json.loads(Path(path).read_text())


def capture(path, name):
    data = Path(path).read_bytes()
    target = INPUTS / name
    if target.exists():
        assert target.read_bytes() == data, 'Snapshot drift: ' + name
    else:
        with target.open('xb') as stream:
            stream.write(data)
    return target


def url(path, folder=False):
    return 'https://www.dropbox.com/' + ('home' if folder else 'preview') + quote(path, safe='/')


pointer_path = BASE / 'current-master.json'
pointer_sha = sha(pointer_path)
pointer = read(capture(pointer_path, 'current-master.json'))
register_path = BASE / pointer['register']
assert sha(register_path) == pointer['register_sha256']
original = read(capture(register_path, 'register.json'))
verification = read(capture(NATIVE / 'verification.json', 'filename-verification.json'))
assert verification['status'] in ['FAIL', 'PASS']
assert all(row['check'] == 'original_shared_link_retained' for row in verification['errors'])
native_path = Path(verification['native_final'])
assert native_path.is_relative_to(NATIVE)
assert sha(native_path) == verification['native_final_sha256']
native = read(capture(native_path, 'native-final.json'))
records = {row['id']: row for scope in ['wall', 'workshop'] for row in native[scope]['entries']}
files = {fid: row for fid, row in records.items() if row['kind'] == 'file'}
assert len(files) == verification['current_files'] == 5994
assert all(native[scope]['pagination_exhausted'] for scope in ['wall', 'workshop'])
assert len({row['path'].casefold() for row in files.values()}) == len(files)
for row in files.values():
    assert row['parent_id'] in records
    assert records[row['parent_id']]['path'] == str(PurePosixPath(row['path']).parent)

old_review = BASE / 'components/reconciliation/background-organisation-app-reference-2026-10-26/anchor-review'
primary_packet = read(capture(old_review / 'primary-reference-refresh.json', 'recorded-primary-choices.json'))
cup_packet = read(capture(old_review / 'folder-anchor-review.json', 'recorded-cup-match.json'))['queued_primary_reference_update']
primary_changes = {row['product_id']: row for row in primary_packet['queued_updates']}
primary_changes[cup_packet['product_id']] = cup_packet
context_changes = {'BSI-A76B86DA7928': 'id:cnqzTNngPVsAAAAAAAyjSQ'}
database = Path.home() / 'Library/Application Support/BoldstoneReview/reviews.sqlite3'
connection = sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)
connection.row_factory = sqlite3.Row
try:
    connection.execute('BEGIN')
    cutoff = connection.execute('SELECT MAX(id) FROM events').fetchone()[0]
    reviews = [dict(row) for row in connection.execute("SELECT * FROM reviews WHERE kind IN ('image','assignment','deletion')")]
finally:
    connection.close()
for row in reviews:
    row['data'] = json.loads(row['data'])
lookup = {(row['kind'], row['product_id'], row['item_id']): row for row in reviews}
approval_rows = []
for pid, proposal in primary_changes.items():
    fid = proposal['proposed_current_file_id']
    assert fid in files and files[fid]['parent_id'] == proposal['proposed_current_folder_id']
    assert files[fid]['path'].startswith('/BOLDSTONE MASTER/Products/01 Wall Sculptures/')
    deletion = lookup.get(('deletion', '', fid), {}).get('data', {})
    assert deletion.get('state') not in ['prepared', 'queued', 'running', 'executing', 'uncertain', 'deleted']
    image = lookup.get(('image', pid, fid))
    assert not image or image['data'].get('decision') != 'exclude'
    if pid != cup_packet['product_id']:
        assert image and image['source_hash'] == pointer['register_sha256']
        assert image['data'].get('primary') is True and image['data'].get('decision') == 'reviewed'
        assert 'listing' in image['data'].get('uses', [])
        approval_rows.append(image)
    else:
        assert files[fid]['content_hash'] == cup_packet['cached_original_dropbox_content_hash']
for pid, fid in context_changes.items():
    image = lookup[('image', pid, fid)]
    assert image['source_hash'] == pointer['register_sha256'] and image['data']['decision'] == 'reviewed'
    assert 'listing' in image['data'].get('uses', []) and fid in files
    approval_rows.append(image)
approval_snapshot = {'review_event_cutoff': cutoff, 'exact_product_image_rows': approval_rows}
approval_path = INPUTS / 'approval-readback.json'
if approval_path.exists():
    assert read(approval_path) == approval_snapshot
else:
    approval_path.write_text(json.dumps(approval_snapshot, indent=2) + '\n')

draft = deepcopy(original)
active = set(draft['active_option_ids'])
history, unresolved, edits = [], [], []
new_context_holds = []
primary_resolved = context_resolved = design_resolved = 0
for option in draft['options']:
    pid = option['product_id']
    if pid not in active:
        continue
    before = deepcopy(option)
    if pid in primary_changes:
        option['file_id'] = primary_changes[pid]['proposed_current_file_id']
    if pid in context_changes:
        option['context_file_id'] = context_changes[pid]
        option['context_status'] = 'Available: qualified room-display reference; actual installation unverified'
        option['photo_coverage']['in_situ'] = 'Available — qualified display reference'
        option['context_description'] = ('Owner-reviewed room-display image of the complete White Barbados Wave. '
            'Scene origin, displayed scale and actual installation remain unverified. No fitted hardware or outdoor durability is certified.')
    for role, file_key, folder_key, image_key, folder_url_key in [
        ('primary', 'file_id', 'folder_id', 'image_url', 'folder_url'),
        ('context', 'context_file_id', 'context_folder_id', 'context_image_url', 'context_folder_url')]:
        fid = option.get(file_key)
        if fid in files:
            row = files[fid]
            option.update({folder_key: row['parent_id'], image_key: url(row['path']),
                           folder_url_key: url(records[row['parent_id']]['path'], True)})
            if role == 'primary':
                primary_resolved += 1
            else:
                context_resolved += 1
        elif fid:
            unresolved.append({'product_id': pid, 'name': option['name'], 'role': role,
                               'file_id': fid, 'folder_id': option.get(folder_key),
                               'status': 'Not present in the audited Wall and retained Workshop folders; global deletion is not inferred.'})
            if role == 'context':
                option[image_key] = ''
                option['context_status'] = 'Historical display reference only; current Dropbox reference unavailable. Replacement remains on owner hold.'
                option['photo_coverage']['in_situ'] = 'Historical reference only — current Dropbox link unavailable; owner hold'
                new_context_holds.append(pid)
        folder = records.get(option.get(folder_key))
        if folder and folder['kind'] == 'folder':
            option[folder_url_key] = url(folder['path'], True)
    design = option.get('owner_confirmed_design_reference')
    if design and design.get('file_id') in files:
        row = files[design['file_id']]
        design.update(folder_id=row['parent_id'], image_url=url(row['path']),
                      folder_url=url(records[row['parent_id']]['path'], True))
        design_resolved += 1
    if any(before.get(key) != option.get(key) for key in ['file_id', 'folder_id', 'image_url', 'folder_url']):
        option['current_link_basis'] = ('Draft current navigation resolved through stable Dropbox file and actual parent-folder IDs '
            'in the captured native readback. Original shared-link verification and publication remain pending.')
    changed = {key: {'before': before.get(key), 'after': option.get(key)}
               for key in set(before) | set(option) if before.get(key) != option.get(key)}
    if changed:
        edits.append({'product_id': pid, 'name': option['name'], 'fields': changed})
        history.append({'product_id': pid, 'previous_navigation_and_photo_fields':
                        {key: before.get(key) for key in changed}})

allowed = {'file_id', 'folder_id', 'image_url', 'folder_url', 'context_file_id', 'context_folder_id',
           'context_image_url', 'context_folder_url', 'owner_confirmed_design_reference',
           'context_description', 'context_status', 'photo_coverage', 'current_link_basis'}
for before, after in zip(original['options'], draft['options']):
    changed = {key for key in set(before) | set(after) if before.get(key) != after.get(key)}
    assert changed <= allowed
    assert before['specifications'] == after['specifications']
    if before['product_id'] not in active:
        assert before == after
    if before.get('owner_confirmed_design_reference'):
        assert before['owner_confirmed_design_reference']['reference_scope'] == after['owner_confirmed_design_reference']['reference_scope']
assert primary_resolved == 186 and context_resolved == 163 and len(unresolved) == 2
assert set(new_context_holds) == {'BSI-EBD43DF0704F', 'BSI-3C849B547D50'}
assert draft['original_review_specification_assertions'] == original['original_review_specification_assertions']
assert len(draft['active_option_ids']) == 187 and len(draft['options']) == 189
draft['proposed_native_filename_reconciliation'] = {
    'status': 'DRAFT_NOT_PUBLISHED_SHARING_VERIFICATION_AND_APP_HANDOFF_REQUIRED',
    'captured_native_filename_verification_status': verification['status'],
    'current_native_snapshot': str(INPUTS / 'native-final.json'),
    'current_native_snapshot_sha256': sha(INPUTS / 'native-final.json'),
    'previous_navigation_preserved': history,
    'new_unavailable_context_references_on_existing_owner_hold': new_context_holds,
    'no_new_identity_physical_specification_stock_price_or_platform_match_claim': True,
}
(HERE / 'draft-master-register.json').write_text(json.dumps(draft, ensure_ascii=False, indent=2) + '\n')

gallery = (BASE / pointer['current_published_gallery_projection']['path']).parent / 'complete-image-platform-register.sqlite'
connection = sqlite3.connect(gallery.resolve().as_uri() + '?mode=ro', uri=True)
try:
    existing_ids = {row[0] for row in connection.execute('SELECT file_id FROM images')}
finally:
    connection.close()
overlay = [{'file_id': fid, 'folder_id': row['parent_id'], 'name': row['name'], 'path': row['path'],
            'image_url': url(row['path']), 'folder_url': url(records[row['parent_id']]['path'], True),
            'native_content_hash': row['content_hash'], 'native_bytes': row['size'],
            'already_in_retained_source_gallery': fid in existing_ids}
           for fid, row in sorted(files.items(), key=lambda pair: pair[1]['path'].casefold())]
(HERE / 'draft-current-image-overlay.json').write_text(json.dumps(overlay, indent=2) + '\n')
shared_cases = []
for error in verification['errors']:
    row = files[error['id']]
    references = [o for o in draft['options'] if o['product_id'] in active and o.get('file_id') == row['id']]
    shared_cases.append({'file_id': row['id'], 'folder_id': row['parent_id'],
                         'option_names': [o['name'] for o in references],
                         'image_url': url(row['path']), 'folder_url': url(records[row['parent_id']]['path'], True),
                         'outstanding_check': error['check']})
report = {
    'status': 'DRAFT_PREPARED_NOT_PUBLISHED', 'recorded_utc': datetime.now(timezone.utc).isoformat(),
    'baseline_pointer_sha256': pointer_sha, 'baseline_register_sha256': pointer['register_sha256'],
    'draft_register_sha256': sha(HERE / 'draft-master-register.json'),
    'source_gallery_sha256': sha(gallery), 'native_files': len(files),
    'wall_files': sum('/Products/01 Wall Sculptures/' in row['path'] for row in files.values()),
    'retained_workshop_files': sum('/Products/Workshop and Moulding/' in row['path'] for row in files.values()),
    'new_native_ids_missing_from_saved_source_gallery': sorted(set(files) - existing_ids),
    'active_options': 187, 'retained_options': 189, 'retired_options_unchanged': 2,
    'current_primary_references_resolved': primary_resolved,
    'current_context_references_resolved': context_resolved,
    'shared_design_references_resolved_without_creating_a_primary': design_resolved,
    'recorded_primary_choices_prepared': 3, 'visual_cup_ring_match_prepared': 1,
    'recorded_barbados_display_replacement_prepared': 1,
    'unavailable_context_references_on_existing_hold': unresolved,
    'shared_link_checks_pending': shared_cases, 'option_edits': edits,
    'original_source_assertions_preserved': len(draft['original_review_specification_assertions']),
    'all_specification_price_stock_identity_and_platform_fields_preserved': True,
    'original_owner_photo_hold_and_history_preserved': True,
    'workbook_authoring_or_shared_publication_started': False,
    'root_app_or_native_writes': 0,
}
assert sha(pointer_path) == pointer_sha
(HERE / 'draft-review.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
def anchor(address, label):
    return '<a href="' + escape(address, quote=True) + '">' + escape(label) + '</a>'
cards = []
for row in shared_cases:
    cards.append('<article><h2>' + escape(' / '.join(row['option_names'])) + '</h2><p>' + anchor(row['image_url'], 'Current image') + ' · ' + anchor(row['folder_url'], 'Containing folder') + '</p><p>The current file and folder IDs are present. The original shared-link preservation check is still outstanding.</p><small>File ID: ' + escape(row['file_id']) + '<br>Folder ID: ' + escape(row['folder_id']) + '</small></article>')
for pid, is_context in ([(pid, False) for pid in primary_changes] + [(pid, True) for pid in context_changes]):
    o = next(o for o in draft['options'] if o['product_id'] == pid)
    image_key, folder_key = ('context_image_url', 'context_folder_url') if is_context else ('image_url', 'folder_url')
    cards.append('<article><h2>' + escape(o['name']) + (' — display reference' if is_context else '') + '</h2><p>' + anchor(o[image_key], 'Prepared image reference') + ' · ' + anchor(o[folder_key], 'Containing folder') + '</p><p>Prepared for the master; no publication has occurred.</p></article>')
html = '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Master navigation draft</title><style>body{max-width:980px;margin:36px auto;padding:0 22px;font:17px/1.5 system-ui;color:#202725}article{border-top:1px solid #ced6d1;padding:18px 0}h1{font-size:30px}h2{font-size:22px}a{color:#14583f}small{overflow-wrap:anywhere}</style><body><h1>Master navigation draft — not published</h1><p>5,994 current image paths captured: 5,798 Wall Sculptures and 196 retained Workshop images. The draft resolves 186 primary references across 187 active options; the historical Frozen Fish option keeps its qualified shared-design reference.</p><p>Three saved Primary choices, one Cup Ring match and one approved Barbados display reference are prepared. Physical specifications, source history and identity qualifications are preserved.</p><p>Two historical display references (MCP1 Verdigris and Rust and Azure) are not present in the audited folders. Their replacements remain on the existing photography hold. Six original shared-link checks still require the owning session readback.</p>' + ''.join(cards) + '</body></html>'
(HERE / 'index.html').write_text(html)
(HERE / 'CURRENT_STATUS.json').write_text(json.dumps({
    'status': report['status'], 'draft_review': str(HERE / 'draft-review.json'),
    'draft_register_sha256': report['draft_register_sha256'], 'baseline_pointer_sha256': pointer_sha,
    'shared_link_checks_pending': len(shared_cases), 'unavailable_context_references_on_hold': len(unresolved),
    'workbooks_or_shared_controls_not_modified': True,
}, indent=2) + '\n')
print(json.dumps({key: report[key] for key in ['status', 'native_files', 'active_options',
    'current_primary_references_resolved', 'current_context_references_resolved',
    'recorded_primary_choices_prepared', 'visual_cup_ring_match_prepared',
    'recorded_barbados_display_replacement_prepared', 'original_source_assertions_preserved']}, indent=2))
