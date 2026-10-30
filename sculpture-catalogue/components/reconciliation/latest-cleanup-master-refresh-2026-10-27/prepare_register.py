"""Prepare the current register from immutable native and owner-review inputs."""
from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from urllib.parse import quote
import hashlib
import importlib.util
import json
import re
import sqlite3

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[2]
read = lambda path: json.loads(Path(path).read_text())
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
manifest = read(HERE / 'input-manifest.json')
CUT = Path(manifest['input_directory'])
original = read(manifest['sources']['register']['snapshot'])
draft = deepcopy(original)
files = read(CUT / 'current-audited-files.json')
wall = read(manifest['sources']['current_wall_census']['snapshot'])
completed = read(manifest['sources']['completed_native_census']['snapshot'])
folders = {r['id']: r for scope in ['wall', 'workshop'] for r in completed[scope]['entries'] if r['kind'] == 'folder'}
folders.update({fid: row for fid, row in wall['records'].items() if row['kind'] == 'folder'})
deleted = read(CUT / 'verified-deletion-tombstones.json')
connection = sqlite3.connect(Path(manifest['sources']['app_review_cut']['snapshot']).as_uri() + '?mode=ro', uri=True)
connection.row_factory = sqlite3.Row
try:
    reviews = [dict(row) for row in connection.execute('SELECT * FROM reviews')]
finally:
    connection.close()
for row in reviews:
    row['data'] = json.loads(row['data'])
lookup = {(r['kind'], r['product_id'], r['item_id']): r for r in reviews}
assets = {r['item_id']: r['data'] for r in reviews if r['kind'] == 'asset'}
active = set(original['active_option_ids'])


def nav(fid):
    row = files[fid]
    parent_id = row.get('folder_id') or row['parent_id']
    parent = folders[parent_id]
    # Dropbox paths are case insensitive. The current parent record is the
    # authority for display casing; keep both stable IDs unchanged.
    assert parent['path'].casefold() == str(PurePosixPath(row['path']).parent).casefold()
    canonical_path = str(PurePosixPath(parent['path']) / PurePosixPath(row['path']).name)
    return {'file_id': fid, 'folder_id': parent_id,
            'image_url': 'https://www.dropbox.com/preview' + quote(canonical_path, safe='/'),
            'folder_url': 'https://www.dropbox.com/home' + quote(parent['path'], safe='/')}


def allowed_review(pid, fid):
    row = lookup.get(('image', pid, fid))
    assignment = lookup.get(('assignment', pid, fid), {}).get('data', {})
    return bool(row and fid in files and row['data'].get('decision') == 'reviewed'
                and 'listing' in row['data'].get('uses', []) and assignment.get('state') != 'removed')


primary = {}
for row in read(CUT / 'recorded-primary-choices.json'):
    pid, fid = row['product_id'], row['item_id']
    if not allowed_review(pid, fid):
        continue
    assert any(x['product_id']==pid and x['source_hash']==row['source_hash'] for x in manifest.get('validated_older_primary_review_scopes',[])) or row['source_hash'] in {manifest['sources']['register']['sha256'],manifest['review_ancestor_sha256']} or next(o for o in original['options'] if o['product_id']==pid).get('file_id')==fid, 'An older review can only reconfirm its already-published exact Primary'
    if pid in active: primary[pid] = row

# Retain the existing series choices when present. For four Brancusi rows whose
# old group references disappeared, use photographs reviewed for BOTH members.
spec = importlib.util.spec_from_file_location('native_book', BASE / 'components/reconciliation/acanthus-native-availability-2026-10-25/verify_workbook.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
book = module.Book(manifest['sources']['core_workbook']['snapshot'])
photo_cells, photo_links = book.sheet('Photo Coverage')
old_series = {}
for address, value in photo_cells.items():
    if re.fullmatch(r'A\d+', address) and value[1] in active:
        number = re.search(r'\d+', address).group()
        fid = photo_cells.get('Q' + number, ('', ''))[1]
        if isinstance(fid, str) and fid.startswith('id:'):
            old_series[value[1]] = fid
book.close()
series_replacements = {}
for members, fid in [(['BSI-923D5E50A898', 'BSI-F7ADC5AEE4E0'], 'id:cnqzTNngPVsAAAAAAAug6g'),
                      (['BSI-A1EB68571F0F', 'BSI-8968D21D702D'], 'id:cnqzTNngPVsAAAAAAAyjwg')]:
    assert all(allowed_review(pid, fid) for pid in members)
    assert '1 and' in str(PurePosixPath(files[fid]['path']).parent)
    for pid in members:
        if old_series.get(pid) not in files:
            series_replacements[pid] = fid

source_gallery = sqlite3.connect(Path(manifest['sources']['source_gallery']['snapshot']).as_uri() + '?mode=ro', uri=True)
source_gallery.row_factory = sqlite3.Row
gallery_rows = {r['file_id']: json.loads(r['record_json']) for r in source_gallery.execute('SELECT file_id,record_json FROM images')}
source_gallery.close()
role_history, primary_changes, context_changes, unavailable = [], [], [], []
series_changes = []
for option in draft['options']:
    pid = option['product_id']
    if pid not in active:
        continue
    before = deepcopy(option)
    if pid in primary:
        choice = primary[pid]
        option['file_id'] = choice['item_id']
        option['current_primary_selection'] = {
            'basis': 'Recorded product-specific Primary and Listing choice',
            'review_version': choice['version'], 'review_updated_at': choice['updated_at'],
            'decision_source_register_sha256': choice['source_hash'],
            'scope': 'Image selection only. Physical specifications, exact platform variants and stock retain their separate evidence.',
        }
        if before.get('file_id') != option['file_id']:
            primary_changes.append({'product_id': pid, 'name': option['name'], 'before_file_id': before.get('file_id'),
                                    **nav(option['file_id']), 'review_version': choice['version']})
    # Barbados's old selected context image was deleted. The two retained scenes
    # were explicitly reviewed for listing/advertising; keep their qualifications.
    if pid == 'BSI-A76B86DA7928' and option.get('context_file_id') not in files:
        fid = 'id:cnqzTNngPVsAAAAAAAyjSQ'
        assert allowed_review(pid, fid)
        option['context_file_id'] = fid
        option['context_status'] = 'Available: qualified room-display reference; actual installation unverified'
        option['context_description'] = 'Owner-reviewed room-display image of the complete White Barbados Wave. Scene origin, displayed scale and actual installation remain unverified.'
        option['photo_coverage']['in_situ'] = 'Available — qualified display reference'
        context_changes.append({'product_id': pid, 'name': option['name'], 'before_file_id': before.get('context_file_id'), **nav(fid)})
    for role, fid_key, folder_key, image_key, folder_url_key in [
        ('primary', 'file_id', 'folder_id', 'image_url', 'folder_url'),
        ('context', 'context_file_id', 'context_folder_id', 'context_image_url', 'context_folder_url')]:
        fid = option.get(fid_key)
        if fid in files:
            reference = nav(fid)
            option.update({folder_key: reference['folder_id'], image_key: reference['image_url'], folder_url_key: reference['folder_url']})
        elif fid:
            unavailable.append({'product_id': pid, 'name': option['name'], 'role': role, 'file_id': fid,
                                'verified_app_deletion': fid in deleted, 'folder_id': option.get(folder_key)})
            option[image_key] = ''
            if role == 'primary':
                assert fid in deleted, 'Unexplained primary absence requires separate investigation'
                option['historical_primary_reference'] = {
                    'file_id': fid, 'folder_id': option.get(folder_key),
                    'image_url_at_previous_publication': before.get(image_key),
                    'status': 'Owner-approved app deletion, verified absent; retained historical reference only',
                    'deletion_evidence': deleted[fid],
                }
                option[fid_key] = None
                option['photo_coverage']['individual'] = 'Current Primary unbound — previous reference deleted by owner; choose surviving full view or capture separately'
            if role == 'context' and before.get(image_key):
                option['context_status'] = 'Historical display reference only; current image unavailable. Replacement on owner hold.'
                option['context_description'] = 'Historical reference (current Dropbox image unavailable): ' + before.get('context_description', '')
                option['photo_coverage']['in_situ'] = 'Historical reference only — current image unavailable; owner hold'
        folder = folders.get(option.get(folder_key))
        if folder:
            option[folder_url_key] = 'https://www.dropbox.com/home' + quote(folder['path'], safe='/')
    design = option.get('owner_confirmed_design_reference')
    if design and design.get('file_id') in files:
        design.update(nav(design['file_id']))
    fid = series_replacements.get(pid, old_series.get(pid))
    if fid in files:
        previous_series=deepcopy(option.get('current_series_reference') or {})
        option['current_series_reference'] = {**previous_series, **nav(fid)}
        option['current_series_reference'].setdefault('scope','Qualified group reference; individual component specifications and sale units remain separate.')
        if pid in series_replacements:
            series_changes.append({'product_id': pid, 'name': option['name'], 'before_file_id': old_series.get(pid), **nav(fid)})
    elif fid and option.get('current_series_reference'):
        assert fid in deleted or fid in manifest.get('accepted_scoped_unavailable_ids',[]), 'New series disappearance requires exact absence evidence'
        option['historical_series_reference'] = {
            **deepcopy(option['current_series_reference']),
            'status': ('Owner-approved deletion, verified absent; retained history only' if fid in deleted else 'Native NOT_FOUND in complete scoped census; cause not inferred; retained history only'),
            'deletion_evidence': deleted.get(fid),
            'scoped_unavailable_evidence': None if fid in deleted else {'file_id':fid,'current_census':manifest['sources']['current_wall_census'],'owner_session_verification':'catalogue-review/reviews/acanthus-names-20261027/verification.json','qualification':manifest['scoped_unavailable_qualification']},
            'replacement_requirement': 'Family / series relevant; find a surviving qualified group view. No new identity or component membership inferred.'}
        option['current_series_reference'] = {}
        option['photo_coverage']['series'] = 'Historical reference only — current image unavailable; replacement required'
        unavailable.append({'product_id':pid,'name':option['name'],'role':'series','file_id':fid,'verified_app_deletion':fid in deleted,'folder_id':option['historical_series_reference']['folder_id']})
    if any(before.get(k) != option.get(k) for k in ['file_id', 'folder_id', 'image_url', 'folder_url']):
        option['current_link_basis'] = 'Current navigation resolved by stable Dropbox file and actual parent-folder IDs in the recorded native census and verified-deletion cut.'
    changed = {k: {'before': before.get(k), 'after': option.get(k)} for k in set(before) | set(option) if before.get(k) != option.get(k)}
    if changed:
        role_history.append({'product_id': pid, 'name': option['name'], 'fields': changed})

allowed = {'file_id','folder_id','image_url','folder_url','context_file_id','context_folder_id',
           'context_image_url','context_folder_url','context_status','context_description','photo_coverage',
           'owner_confirmed_design_reference','current_primary_selection','current_series_reference','current_link_basis','historical_primary_reference','historical_series_reference'}
for before, after in zip(original['options'], draft['options']):
    assert {k for k in set(before) | set(after) if before.get(k) != after.get(k)} <= allowed
    if before['product_id'] not in active:
        assert before == after
    assert before['specifications'] == after['specifications']
    if before.get('owner_confirmed_design_reference'):
        assert before['owner_confirmed_design_reference']['reference_scope'] == after['owner_confirmed_design_reference']['reference_scope']
for key in original:
    if key != 'options':
        assert original[key] == draft[key]
assert len(active) == 186 and len(draft['options']) == 189
assert all(o.get('file_id') in files for o in draft['options'] if o['product_id'] in active and o.get('file_id'))
assert draft['original_review_specification_assertions'] == original['original_review_specification_assertions']
effective_context_holds = sorted(o['product_id'] for o in draft['options'] if o['product_id'] in active
                                 and (not o.get('context_file_id') or o.get('context_file_id') not in files))
draft['summary']['individual_options_with_dropbox_reference'] = sum(o['product_id'] in active and o.get('file_id') in files for o in draft['options'])
draft['latest_verified_native_filename_import'] = {
    'refresh_scope': 'Post-consolidation export refresh with verified current navigation and saved Primary choices; owner duplicate retirement preserved; no physical/commercial changes',
    'previous_register_sha256': manifest['sources']['register']['sha256'],
    'status': 'VERIFIED_SOURCE_INPUTS_PREPARED_FOR_PUBLICATION',
    'recorded_utc': datetime.now(timezone.utc).isoformat(),
    'publication_cut_utc': manifest['recorded_utc'], 'wall_census': manifest['wall_census'],
    'completed_filename_verification': manifest['sources']['native_verification'],
    'completed_filename_paths': manifest['sources']['completed_filename_paths'],
    'subsequent_deletions_applied': manifest['subsequent_verified_deletions'],
    'current_scoped_files': len(files), 'current_native_navigation_history': role_history,
    'recorded_primary_choices_applied': len(primary_changes), 'qualified_context_replacements': context_changes,
    'qualified_series_replacements': series_changes, 'effective_context_owner_holds': effective_context_holds,
    'original_1668_assertions_and_all_physical_specifications_preserved': True,
    'native_platform_or_app_review_writes_by_publisher': 0,
}
(HERE / 'canonical-master-register.json').write_text(json.dumps(draft, ensure_ascii=False, indent=2) + '\n')
current_overlay = []
references = defaultdict(list)
for o in draft['options']:
    if o['product_id'] not in active:
        continue
    for role, fid in [('primary', o.get('file_id')), ('context', o.get('context_file_id')),
                      ('series', o.get('current_series_reference', {}).get('file_id')),
                      ('shared design', o.get('owner_confirmed_design_reference', {}).get('file_id'))]:
        if fid in files:
            references[fid].append({'product_id': o['product_id'], 'name': o['name'], 'role': role})
for fid, row in sorted(files.items(), key=lambda item: item[1]['path'].casefold()):
    reference = nav(fid)
    current_overlay.append({**row, **reference, 'selected_references': references[fid],
        'scope': 'Wall Sculptures' if '/Products/01 Wall Sculptures/' in row['path'] else 'Retained Workshop',
        'in_saved_source_gallery': fid in gallery_rows})
(HERE / 'current-image-overlay.json').write_text(json.dumps(current_overlay, ensure_ascii=False, indent=2) + '\n')
report = {'status': 'REGISTER_AND_CURRENT_IMAGE_OVERLAY_PREPARED',
    'register_sha256': sha(HERE / 'canonical-master-register.json'), 'active_options': 186,
    'retained_options': 189, 'current_scoped_files': len(files),
    'current_primary_references': sum(o['product_id'] in active and o.get('file_id') in files for o in draft['options']),
    'current_context_references': sum(o['product_id'] in active and o.get('context_file_id') in files for o in draft['options']),
    'current_series_references': sum(o['product_id'] in active and bool(o.get('current_series_reference')) for o in draft['options']),
    'new_context_losses': [o['product_id'] for o in draft['options'] if o['product_id'] in active and next(b for b in original['options'] if b['product_id']==o['product_id']).get('context_image_url') and not o.get('context_image_url')],
    'new_series_losses': [o['product_id'] for o in draft['options'] if o['product_id'] in active and o.get('historical_series_reference') and not next(b for b in original['options'] if b['product_id']==o['product_id']).get('historical_series_reference')],
    'explicit_current_primary_choices': len(primary),
    'primary_changes': primary_changes, 'context_changes': context_changes, 'series_changes': series_changes,
    'unavailable_selected_references': unavailable, 'effective_context_owner_holds': effective_context_holds,
    'new_native_images_to_append': sorted(set(files) - set(gallery_rows)),
    'source_assertions_preserved': len(draft['original_review_specification_assertions']),
    'all_physical_specification_identity_price_stock_and_platform_fields_unchanged': True,
    'native_app_or_shared_publication_writes': 0}
(HERE / 'register-preparation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({k: report[k] for k in ['status','active_options','retained_options','current_scoped_files',
    'current_primary_references','current_context_references','source_assertions_preserved']}, indent=2))
print('recorded_primary_changes', len(primary_changes), 'series_replacements', len(series_changes), 'context_holds', len(effective_context_holds))
