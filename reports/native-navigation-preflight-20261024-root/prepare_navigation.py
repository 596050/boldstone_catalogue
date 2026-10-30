"""Compare the complete current Wall census to retained navigation, read-only."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

H = Path(__file__).resolve().parent
ROOT = H.parents[1]
B = ROOT / 'sculpture-catalogue'
N = ROOT / 'reports/dropbox-wall-complete-role-review-20261024T214349Z'
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
digest = lambda v: hashlib.sha256(json.dumps(v, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
write = lambda p, v: Path(p).write_text(json.dumps(v, ensure_ascii=False, indent=2) + '\n')

def navurl(url):
    u = urlparse(url or '')
    p = unquote(u.path)
    for prefix in ['/home', '/preview']:
        if p.startswith(prefix+'/'):
            p = p[len(prefix):]
            break
    query = parse_qs(u.query)
    return p.rstrip('/') + ('/'+query['preview'][0] if query.get('preview') else '')

def saved_path(row):
    # Earlier overlays sometimes updated path but retained historical display_path.
    # Neither a stale display_path nor the family label establishes current scope.
    return (row.get('path') or row.get('display_path') or '').replace('ns:202238505/', '', 1)

checks = []
def check(name, value):
    checks.append({'check': name, 'pass': bool(value)})
    assert value, name

pointer = read(B / 'current-master.json')
check('Exact64e canonical baseline', sha(B / 'current-master.json') == '64e22f7c3aaca874817b11b497294c4b40b17564b717ce7c05e41ffbc44f22b7')
check('Exact native link/hash seal', sha(N / 'native-link-and-cache-binding-seal.json') == '382191be65eb632ae3d6ca1f357bf541cc9e59f9d25724a3c7bf84916e37dddf')
native_seal = read(N / 'native-link-and-cache-binding-seal.json')
for member in native_seal['files']:
    check('Native sealed member ' + member['path'], sha(N / member['path']) == member['sha256'])
assets_path = B / pointer['current_asset_reference_map']['path']
native_path = B / pointer['current_native_reference_map']['path']
check('Authoritative saved asset map exact', sha(assets_path) == pointer['current_asset_reference_map']['sha256'])
check('Authoritative saved native map exact', sha(native_path) == pointer['current_native_reference_map']['sha256'])
assets = read(assets_path)
old_native = read(native_path)
native = read(N / 'complete-current-native-object-map.json')
files = {k: v for k, v in native.items() if v.get('object_type') == 'file'}
source = {v['file_id']: v for v in read(N / 'current-6360-visual-source-evidence.json')}
check('Complete fresh Wall-only source coverage', len(files) == len(source) == 6360 and set(files) == set(source))
prefix = '/BOLDSTONE MASTER/Products/01 Wall Sculptures/'
for fid, current in files.items():
    check('Current file parent and path ' + fid, current['display_path'].startswith(prefix) and current['parent_id'] == current['folder_id'] and native[current['folder_id']]['display_path'] == current['folder_path'])

patches, style_only, unknown_parent, parent_changed, unknown_hash, hash_changed = [], [], [], [], [], []
for fid in sorted(files.keys() & assets.keys()):
    old = assets[fid]
    current = files[fid]
    changed = []
    for field in ['name', 'folder_id']:
        if old.get(field) != current.get(field):
            changed.append(field)
    for field in ['image_url', 'folder_url']:
        if navurl(old.get(field)) != navurl(current.get(field)):
            changed.append(field)
    if not old.get('folder_id'):
        parent_state = 'UNKNOWN_SAVED_PARENT_NOT_ENCODED'
        unknown_parent.append(fid)
    elif old['folder_id'] != current['folder_id']:
        parent_state = 'ACTUAL_PARENT_DIFFERS_FROM_SAVED_REFERENCE'
        parent_changed.append(fid)
    else:
        parent_state = 'SAME_SAVED_AND_CURRENT_PARENT'
    if not old.get('source_content_hash'):
        unknown_hash.append(fid)
    elif old['source_content_hash'] != source[fid]['native_content_hash']:
        hash_changed.append(fid)
    if changed:
        fields = ['file_id', 'name', 'path', 'display_path', 'folder_id', 'folder_path', 'image_url', 'folder_url']
        patches.append({'file_id': fid, 'changed_navigation_fields': changed,
            'before': {k: old.get(k) for k in fields}, 'current': {k: current.get(k) for k in fields},
            'saved_parent_comparison_state': parent_state,
            'actual_parent_matches_saved_parent': (None if parent_state.startswith('UNKNOWN') else parent_state.startswith('SAME')),
            'native_source_content_hash': source[fid]['native_content_hash'],
            'new_native_change_performed_by_preflight': False})
    elif any(old.get(field) != current.get(field) for field in ['image_url', 'folder_url']):
        style_only.append(fid)
check('No source hash drift among previously encoded current files', not hash_changed)
new_files = [files[fid] for fid in sorted(files.keys()-assets.keys())]
absent = []
for fid in sorted(assets.keys()-files.keys()):
    old = assets[fid]
    path = saved_path(old)
    scope = 'RETAINED_WALL_PATH_NOT_IN_CURRENT_WALL_CENSUS' if path.startswith(prefix) else 'OUTSIDE_CURRENT_WALL_CENSUS_SCOPE_OR_SAVED_PATH_NOT_ENCODED'
    absent.append({'file_id': fid, 'name': old.get('name'), 'saved_path': path,
                  'image_url': old.get('image_url'), 'folder_url': old.get('folder_url'),
                  'disposition': scope, 'deletion_inferred': False, 'retained_history_should_be_preserved': True})
register = read(B / pointer['register'])
selected_patches, selected_absent = [], []
occurrences_present = 0
for option in register['options']:
    if not option['counted_as_individual_option']:
        continue
    for role, prefix_field in [('primary', ''), ('context', 'context_')]:
        fid = option.get(prefix_field+'file_id')
        if not fid:
            continue
        if fid not in files:
            selected_absent.append({'option_id': option['product_id'], 'name': option['name'], 'role': role,
                'file_id': fid, 'outside_wall_scope_is_not_missing': not navurl(option.get(prefix_field+'image_url')).startswith(prefix)})
            continue
        occurrences_present += 1
        n = files[fid]
        delta = [k for k in ['folder_id', 'image_url', 'folder_url'] if
            (option.get(prefix_field+k) != n[k] if k == 'folder_id' else navurl(option.get(prefix_field+k)) != navurl(n[k]))]
        if delta:
            keys = ['file_id', 'folder_id', 'image_url', 'folder_url']
            selected_patches.append({'option_id': option['product_id'], 'name': option['name'], 'role': role,
                'expected_whole_option_sha256': digest(option), 'expected_working_fields_sha256': digest(option['master_fields']),
                'changed_fields': [prefix_field+k for k in delta],
                'before': {prefix_field+k: option.get(prefix_field+k) for k in keys},
                'proposed': {prefix_field+k: n[k] for k in keys},
                'photo_role_identity_and_all_working_fields_unchanged': True})
check('Exactly two same-ID selected context URL refreshes', len(selected_patches) == 2 and all(r['role'] == 'context' and set(r['changed_fields']) == {'context_image_url', 'context_folder_url'} for r in selected_patches))
protected = {}
for relative in ['current-master.json', pointer['register'], pointer['workbook'],
                 pointer['current_asset_reference_map']['path'], pointer['current_native_reference_map']['path'],
                 'components/reviews/specification_review_progress.json', 'components/checkpoint.json', 'checkpoint.json']:
    protected[str(B / relative)] = sha(B / relative)
counts = {'saved_asset_records': len(assets), 'fresh_wall_files': len(files), 'fresh_native_objects_including_root': len(native),
    'fresh_file_ids_already_in_saved_assets': len(files.keys() & assets.keys()),
    'fresh_file_ids_newly_represented_in_asset_map': len(new_files),
    'normalized_navigation_or_minimal_record_enrichment_rows': len(patches),
    'url_style_only_differences_no_path_change': len(style_only),
    'actual_parent_changes_with_known_saved_parent': len(parent_changed),
    'unknown_saved_parent_metadata_rows': len(unknown_parent),
    'common_files_without_previously_encoded_source_hash': len(unknown_hash), 'source_hash_drift_where_old_hash_encoded': len(hash_changed),
    'saved_asset_ids_not_in_wall_census': len(absent),
    'retained_wall_paths_absent_from_wall_census': sum(r['disposition'].startswith('RETAINED_WALL') for r in absent),
    'out_of_scope_or_path_unencoded_saved_ids': sum(not r['disposition'].startswith('RETAINED_WALL') for r in absent),
    'selected_primary_or_context_occurrences_present_in_current_wall_census': occurrences_present,
    'same_id_selected_context_url_refreshes_prepared': len(selected_patches),
    'native_or_platform_writes': 0, 'canonical_writes': 0}
packet = {'status': 'READ_ONLY_NAVIGATION_IMPORT_PREFLIGHT_READY_NOT_PUBLISHED',
    'recorded_utc': datetime.now(timezone.utc).isoformat(), 'baseline_pointer_sha256': sha(B / 'current-master.json'),
    'counts': counts, 'navigation_patches': patches, 'newly_represented_existing_native_files': new_files,
    'absent_saved_references_retained_with_scope': absent, 'selected_context_refreshes': selected_patches,
    'selected_references_outside_current_wall_census': selected_absent,
    'parent_changes': parent_changed, 'unknown_saved_parents': unknown_parent,
    'scope': 'Current Wall census only. No deletion inference from absence, no override of historical source/field references, no new photo-role or component assignment. Cup Ring Master Documents reference remains outside this census and has separate direct readback. Two deleted Wall Circle primaries have their separate guarded replacement proposal. MCP1 historical context remains unavailable with existing deferral retained.',
    'source_native_snapshot_seal': {'path': str(N / 'native-link-and-cache-binding-seal.json'), 'sha256': sha(N / 'native-link-and-cache-binding-seal.json')},
    'saved_asset_map': {'path': str(assets_path), 'sha256': sha(assets_path)},
    'saved_native_map': {'path': str(native_path), 'sha256': sha(native_path)}, 'protected_current_files': protected}
write(H / 'navigation-import-preflight.json', packet)
for path, value in protected.items():
    check('Protected source unchanged ' + path, sha(path) == value)
write(H / 'verification.json', {'status': 'PASS', 'checks_passed': len(checks), 'checks_total': len(checks),
    'checks': checks, 'packet_sha256': sha(H / 'navigation-import-preflight.json'), 'counts': counts})
write(H / 'sealed-handoff.json', {'status': 'SEALED_READ_ONLY_NAVIGATION_IMPORT_PREFLIGHT',
    'files': {str(p): sha(p) for p in [H / 'prepare_navigation.py', H / 'navigation-import-preflight.json', H / 'verification.json']}})
print(json.dumps({'status': 'PASS', 'checks': len(checks), 'counts': counts, 'seal_sha256': sha(H / 'sealed-handoff.json')}, indent=2))
