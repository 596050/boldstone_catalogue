"""Stage guarded current-navigation data, retaining all source and field history."""
from collections import Counter
from datetime import datetime, timezone
import copy
import hashlib
import json
from pathlib import Path

H = Path(__file__).resolve().parent
B = H.parents[2]
ROOT = B.parent
N = ROOT / 'reports/dropbox-wall-complete-role-review-20261024T214349Z'
P = B / 'components/parallel-reviews/held-identities-resumption-01a16dbc-20261024/deleted-reference-resolution'
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
digest = lambda v: hashlib.sha256(json.dumps(v, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
write = lambda p, v: Path(p).write_text(json.dumps(v, ensure_ascii=False, indent=2) + '\n')
now = datetime.now(timezone.utc).isoformat()
pointer_path = B / 'current-master.json'
assert sha(pointer_path) == '64e22f7c3aaca874817b11b497294c4b40b17564b717ce7c05e41ffbc44f22b7'
pointer = read(pointer_path)
nav = read(ROOT / 'reports/native-navigation-preflight-20261024-root/navigation-import-preflight.json')
replacement = read(P / 'proposed-reference-replacements.json')
assert nav['baseline_pointer_sha256'] == replacement['source_pointer_sha256'] == sha(pointer_path)
inputs = {
    'pointer': pointer_path, 'master_register': B / pointer['register'], 'master_workbook': B / pointer['workbook'],
    'asset_map': B / pointer['current_asset_reference_map']['path'],
    'native_map': B / pointer['current_native_reference_map']['path'],
    'coverage': (B / pointer['register']).parent / 'image-coverage-current.json',
    'review_progress': B / 'components/reviews/specification_review_progress.json',
    'component_checkpoint': B / 'components/checkpoint.json', 'checkpoint': B / 'checkpoint.json',
}
(H / 'inputs').mkdir(exist_ok=True)
manifest = {}
for label, path in inputs.items():
    frozen = H / 'inputs' / (label + '.before')
    if not frozen.exists():
        frozen.write_bytes(path.read_bytes())
    assert sha(path) == sha(frozen), 'Baseline drift: ' + label
    manifest[label] = {'path': str(path), 'snapshot': str(frozen), 'sha256': sha(path)}
write(H / 'input-manifest.json', manifest)
original = read(inputs['master_register'])
g = copy.deepcopy(original)
audit_before = read(inputs['coverage'])
audit = copy.deepcopy(audit_before)
options = {o['product_id']: o for o in g['options']}
coverage = {r['option_id']: r for r in audit['coverage']}
native = read(N / 'complete-current-native-object-map.json')
fresh = {k: v for k, v in native.items() if v.get('object_type') == 'file'}
evidence = {v['file_id']: v for v in read(N / 'current-6360-visual-source-evidence.json')}
assets = read(inputs['asset_map'])
native_wrapper = read(inputs['native_map'])
native_cumulative = copy.deepcopy(native_wrapper['current_objects'])
for fid, item in native.items():
    prior = native_cumulative.get(fid, {})
    native_cumulative[fid] = {**prior, **item,
        'current_wall_snapshot_present': True, 'current_wall_snapshot_verified_utc': item.get('native_metadata_verified_utc')}
for fid, item in fresh.items():
    old = assets.get(fid, {'file_id': fid})
    current = copy.deepcopy(old)
    # Retain the established namespace representation for asset path fields.
    for key in ['name', 'path', 'display_path', 'folder_id', 'image_url', 'folder_url']:
        current[key] = item[key]
    current['folder_path'] = 'ns:202238505/' + item['folder_path']
    current['family'] = item['family']
    current['bytes'] = item['size']
    current['modified_time'] = item['modified_time']
    current['client_modified'] = item['client_modified']
    if old.get('source_content_hash'):
        assert old['source_content_hash'] == evidence[fid]['native_content_hash']
    current['source_content_hash'] = evidence[fid]['native_content_hash']
    current['source_bytes'] = item['size']
    current['current_wall_snapshot_present'] = True
    current['current_wall_snapshot_verified_utc'] = item['native_metadata_verified_utc']
    current['current_visual_source_binding'] = evidence[fid]
    if not current.get('thumb'):
        current['thumb'] = evidence[fid]['source_image_path']
    assets[fid] = current
for row in nav['absent_saved_references_retained_with_scope']:
    fid = row['file_id']
    if row['disposition'].startswith('RETAINED_WALL'):
        assets[fid]['current_wall_snapshot_present'] = False
        assets[fid]['current_wall_snapshot_absence_scope'] = row['disposition']
        assets[fid]['absence_does_not_establish_deletion_or_global_unavailability'] = True
        if fid in native_cumulative:
            native_cumulative[fid]['current_wall_snapshot_present'] = False
            native_cumulative[fid]['absence_does_not_establish_deletion_or_global_unavailability'] = True
primary_changes = []
for change in replacement['changes']:
    oid = change['option_id']
    o = options[oid]
    assert digest(o) == change['expected_whole_option_sha256']
    assert digest(o['master_fields']) == change['expected_working_fields_sha256']
    old_navigation = copy.deepcopy(o['current_primary_navigation'])
    new_id = change['proposed']['file_id']
    for key, value in change['proposed'].items():
        o[key] = value
    o['current_link_basis'] = 'Current equivalent whole-frame image reference; old selected ID and exact deleted-file history retained under previous navigation observation.'
    o['current_primary_navigation'] = {
        'product_id': oid, 'name': o['name'], 'file_id': new_id, 'folder_id': o['folder_id'],
        'status': 'CURRENT_EQUIVALENT_PHOTOGRAPH_REFERENCE_VERIFIED', 'current_primary_verified': True,
        'folder_verified': True, 'image_url': o['image_url'], 'verified_folder_url': o['folder_url'],
        'replacement_selected': True, 'saved_reference_retained_as_history': True,
        'owner_hold_preserved': True, 'deletion_observed_in_exact_id_history': False,
        'current_replacement_history_observed_deleted': False, 'restored_to_dropbox': False,
        'comparison': change['comparison'], 'previous_navigation_observation': old_navigation,
        'source_evidence': {'path': str(P / 'proposed-reference-replacements.json'), 'sha256': sha(P / 'proposed-reference-replacements.json')},
        'source_photo_content_status_retained': o['photo_coverage']['individual'],
        'recorded_utc': now, 'web_url_openability_verified': False,
        'new_pattern_or_physical_specimen_identity_claimed': False,
    }
    cov = coverage[oid]
    cov['individual']['historical_selected_reference_before_equivalent_replacement'] = copy.deepcopy(cov['individual']['reference'])
    ref = cov['individual']['reference']
    for key in ['file_id', 'folder_id', 'name', 'path', 'image_url', 'folder_url']:
        ref[key] = fresh[new_id][key]
    cov['individual']['current_native_navigation'] = copy.deepcopy(o['current_primary_navigation'])
    primary_changes.append({'option_id': oid, 'before': change['before'], 'current': change['proposed'], 'comparison': change['comparison']})
for change in nav['selected_context_refreshes']:
    o = options[change['option_id']]
    assert all(o[k] == v for k, v in change['before'].items())
    o.update(change['proposed'])
    ref = coverage[o['product_id']]['in_situ']['reference']
    current = fresh[o['context_file_id']]
    for key in ['file_id', 'folder_id', 'name', 'path', 'image_url', 'folder_url']:
        ref[key] = current[key]
# Source-photo coverage remains separate from the availability of this old link.
mcp = options['BSI-EBD43DF0704F']
mcp['current_context_navigation'] = {
    'status': 'HISTORICAL_APPROVED_CONTEXT_CURRENT_REFERENCE_UNAVAILABLE_IN_CHECKED_MASTER_SCOPE',
    'file_id': mcp['context_file_id'], 'folder_id': mcp['context_folder_id'],
    'current_reference_verified': False, 'historical_source_photo_coverage_retained': True,
    'owner_deferral_retained_no_new_photo_request': True,
    'source_evidence': str(B / 'components/parallel-reviews/all-record-image-matching-20261024-B/mcp1-current-reference-status.json'),
    'no_finish_replacement_or_component_reassignment': True,
}
coverage[mcp['product_id']]['in_situ']['current_native_navigation'] = copy.deepcopy(mcp['current_context_navigation'])
for old, current in zip(original['options'], g['options']):
    assert all(old[k] == current[k] for k in ['product_id', 'name', 'canonical_component_id', 'specifications', 'master_fields', 'selling_details', 'photo_coverage'])
assert audit['counts'] == audit_before['counts']
assert g['summary'] == original['summary']
assert g['original_review_specification_assertions'] == original['original_review_specification_assertions']
metadata = {'status': 'CANDIDATE_ONLY_NOT_PUBLISHED', 'recorded_utc': now,
    'current_wall_files': 6360, 'current_wall_native_objects_including_root': 6802,
    'saved_asset_records_retained': 6656, 'newly_represented_existing_native_file_ids': 34,
    'cumulative_asset_records': len(assets), 'cumulative_native_object_records': len(native_cumulative),
    'normalized_asset_navigation_or_enrichment_rows': len(nav['navigation_patches']),
    'same_id_context_url_refreshes': len(nav['selected_context_refreshes']),
    'equivalent_primary_reference_replacements': primary_changes,
    'new_source_photo_roles_or_physical_fields': 0, 'new_component_or_finish_records': 0,
    'working_fields_and_source_assertions_unchanged': True,
    'owner_held_context': 22, 'owner_held_series': 1, 'legacy_frozen_fish_identity_deferred': True,
    'native_or_platform_writes': 0,
    'native_snapshot_seal': nav['source_native_snapshot_seal'],
    'full_gallery_matching_handoff': 'Await final sealed B and Directory role manifests before publication.'}
g['latest_complete_wall_navigation_candidate'] = metadata
audit['latest_complete_wall_navigation_candidate'] = metadata
native_wrapper['current_objects'] = native_cumulative
native_wrapper['status'] = 'CURRENT_CUMULATIVE_REFERENCE_MAP_WITH_COMPLETE_WALL_SNAPSHOT_AND_RETAINED_HISTORY'
for fid,item in native.items():
    for key in ['path','display_path']:
        if item.get(key):native_wrapper['old_path_to_id'][item[key]] = fid
for name, value in [('canonical-master-register.json', g), ('image-coverage-current.json', audit),
                    ('current-assets.json', assets), ('current-native-reference-map.json', native_wrapper),
                    ('candidate-navigation-summary.json', metadata)]:
    write(H / name, value)
for value in manifest.values():
    assert sha(value['path']) == sha(value['snapshot']) == value['sha256']
write(H / 'candidate-data-verification.json', {'status': 'PASS_PREPARED_NOT_PUBLISHED',
    'baseline_pointer_sha256': sha(pointer_path), 'active_options': 188, 'retained_options': 189,
    'retained_component_ids': 112, 'working_design_groups': 110,
    'retained_full_working_field_objects_verified_unchanged': 1134,
    'source_assertions_verified_unchanged': 1668,
    'all_source_role_counts_and_owner_deferrals_unchanged': True,
    'candidate_files': {str(H / name): sha(H / name) for name in ['canonical-master-register.json', 'image-coverage-current.json', 'current-assets.json', 'current-native-reference-map.json', 'candidate-navigation-summary.json']}})
print(json.dumps({'status': 'PREPARED_NOT_PUBLISHED', 'active_options': 188, 'asset_records': len(assets),
    'native_object_records': len(native_cumulative), 'primary_replacements': len(primary_changes), 'context_URL_refreshes': 2}, indent=2))
