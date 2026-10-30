import datetime
import hashlib
import json
import sys
from pathlib import Path

J = Path(__file__).parent
B = J.parents[2]
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
pointer_path = B / 'current-master.json'
p = read(pointer_path)
packet = read(J / 'reviewer-reference-decisions.json')
before_path = B / 'components/reconciliation/nine-empty-folder-master-refresh-2026-10-23/canonical-master-register.json'
staged = '--stage' in sys.argv
after_path = B / ('components/reconciliation/qualified-display-and-series-review-2026-10-23/canonical-master-register.json' if staged else p['register'])
assert after_path != before_path, 'The eighteen-display publication has not completed yet'
assert sha(before_path) == '2d720e26cf547bd95426123ef8f179e68556665747880b1099e45a8c82be6d9f'
after_sha = sha(after_path)
if not staged:
    assert after_sha == p['register_sha256']
    assert sha(B / p['workbook']) == p['workbook_sha256']
before = read(before_path)
after = read(after_path)
old = {x['product_id']: x for x in before['options']}
new = {x['product_id']: x for x in after['options']}
assert old.keys() == new.keys() and len(old) == 188
ids = {x['product_id'] for x in packet['decisions']}
changed = {oid for oid in old if old[oid] != new[oid]}
plan = read(J / 'active-insitu-review-plan.json')
series_findings_path = B / 'components/parallel-reviews/series-gap-review-20261023T190939Z/review-findings.json'
assert sha(series_findings_path) == '85e126cb81f8dab0ec62ac509f6c65c2de59ada9c487744d05216666cd89a200'
assert sha(J / 'reviewer-reference-decisions.json') == '1ce85376cdace64ccf3649f24840b3c0b8975b3335962cbad086c3497f04b015'
insitu_ids = {x['option_id'] for x in plan['active_options']}
series_ids = {x['option_id'] for x in read(series_findings_path)['residual_tasks']}
reviewed_ids = insitu_ids | series_ids
held_ids = set(plan['held_option_ids'])
assert len(insitu_ids) == 36 and len(series_ids) == 17 and len(reviewed_ids) == 44
assert len(ids) == 18 and ids <= insitu_ids and changed == reviewed_ids
assert len(held_ids) == 8 and not (changed & held_ids)
display_fields = {'context_description', 'context_file_id', 'context_folder_id', 'context_folder_url', 'context_image_url', 'context_status', 'current_photo_task_review', 'current_reviewed_display_reference', 'historical_owner_superseded_contexts', 'photo_coverage'}
note_checks = []
for oid in changed:
    fields = {k for k in old[oid].keys() | new[oid].keys() if (k in old[oid]) != (k in new[oid]) or old[oid].get(k) != new[oid].get(k)}
    assert fields <= (display_fields if oid in ids else {'current_photo_task_review'}), (oid, fields)
    note = new[oid]['current_photo_task_review']
    expected_roles = ({'in_situ'} if oid in insitu_ids else set()) | ({'series'} if oid in series_ids else set())
    assert set(note['roles']) == expected_roles, (oid, 'stale or out-of-scope current role')
    assert note['historical_previous_review'] == old[oid].get('current_photo_task_review'), (oid, 'historical review changed')
    assert note['recorded_utc'].startswith('2026-10-23T'), (oid, 'review date')
    for role, detail in note['roles'].items():
        assert detail['recorded_utc'].startswith('2026-10-23T'), (oid, role, 'role review date')
    note_checks.append({'option_id': oid, 'changed_fields': sorted(fields), 'current_review_roles': sorted(expected_roles), 'recorded_utc': note['recorded_utc'], 'prior_review_preserved_verbatim_as_historical': True})
old_cov = {x['option_id']: x for x in read(before_path.with_name('image-coverage-current.json'))['coverage']}
new_audit = read(after_path.with_name('image-coverage-current.json'))
new_cov = {x['option_id']: x for x in new_audit['coverage']}
checks = []
protected = ['file_id', 'folder_id', 'image_url', 'folder_url', 'name', 'canonical_key', 'canonical_design_id', 'sale_unit', 'specifications', 'master_fields', 'offered_fixing_choices', 'selling_details', 'current_commercial_policy', 'physical_specifications_verified']
assert old_cov.keys() == new_cov.keys() and len(old_cov) == 188
for oid in old:
    for field in protected:
        assert (field in old[oid]) == (field in new[oid]) and old[oid].get(field) == new[oid].get(field), (oid, field)
    assert old_cov[oid]['individual'] == new_cov[oid]['individual'], (oid, 'individual role changed')
    assert old_cov[oid]['series'] == new_cov[oid]['series'], (oid, 'series role changed')
    if oid not in ids:
        assert old_cov[oid]['in_situ']['status'] == new_cov[oid]['in_situ']['status'], (oid, 'unselected in-situ status changed')
        assert old_cov[oid]['in_situ'].get('reference') == new_cov[oid]['in_situ'].get('reference'), (oid, 'unselected in-situ reference changed')
for oid in held_ids:
    assert old[oid] == new[oid] and old_cov[oid] == new_cov[oid], (oid, 'held case changed')
for d in packet['decisions']:
    oid = d['product_id']
    for field in protected:
        assert old[oid].get(field) == new[oid].get(field), (oid, field)
    assert new_cov[oid]['individual'] == old_cov[oid]['individual']
    assert new_cov[oid]['series'] == old_cov[oid]['series']
    assert new_cov[oid]['in_situ']['status'] == 'Available'
    ref = new_cov[oid]['in_situ']['reference']
    for field in ['file_id', 'folder_id', 'image_url', 'folder_url']:
        assert ref[field] == d['reference'][field], (oid, field)
    assert new[oid]['context_file_id'] == d['reference']['file_id']
    assert new[oid]['context_folder_id'] == d['reference']['folder_id']
    current = new_cov[oid]['in_situ']
    for field in ['scene_authenticity_verified', 'physical_cast_or_size_certified', 'creation_origin_verified', 'explicit_owner_image_role_approval']:
        assert current[field] is False, (oid, field)
    assert current['qualified_display_only'] is True
    assert current['display_qualification'] == d['display_qualification']
    assert new[oid]['current_reviewed_display_reference']['reference'] == d['reference']
    checks.append({'option_id': oid, 'context_file_id': ref['file_id'], 'actual_parent_id': ref['folder_id'], 'protected_fields_and_other_image_roles_unchanged': True})
counts = new_audit['counts']
assert counts['in_situ_statuses']['No verified image'] == 26
assert counts['series_statuses']['No verified image'] == 17
assert counts['individual_options'] == 187 and counts['required_picture_actions'] == 44
assert new_cov['BSI-3635E3DC3434']['series']['status'] == 'No verified image'
assert after['current_removed_empty_folder_history'] == before['current_removed_empty_folder_history']
assert sha(after_path) == after_sha, 'Register changed during semantic readback; repeat against stable bytes'
semantic_result = {'status': 'PASS_SCOPED_DISPLAY_AND_REVIEW_METADATA_SEMANTICS', 'recorded_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'register': str(after_path), 'register_sha256': after_sha, 'staged_not_published': staged, 'display_role_changes': len(ids), 'review_metadata_only_options': len(changed - ids), 'retained_option_objects_semantically_unchanged': len(old) - len(changed), 'protected_field_checks_across_all_retained_options': len(old) * len(protected), 'individual_and_series_roles_preserved': len(old_cov), 'held_option_and_coverage_rows_unchanged': len(held_ids), 'historical_reviews_preserved': len(note_checks), 'current_reviews_contain_only_requested_roles': True, 'current_review_dates_verified': True, 'review_note_checks': note_checks}
if staged:
    (J / 'staged-semantic-readback.json').write_text(json.dumps(semantic_result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: v for k, v in semantic_result.items() if k != 'review_note_checks'}))
    sys.exit(0)
pub = read(B / p['publication_receipt'])
assert pub['status'] == 'PASS_PUBLISHED_AND_READ_BACK'
assert pub['workbook_sha256'] == p['workbook_sha256'] and pub['register_sha256'] == p['register_sha256']
assert pub.get('explicit_owner_image_role_approvals_added', 0) == 0
assert pub.get('new_physical_verifications', 0) == 0
result = {'status': 'PASS_PUBLISHED_EIGHTEEN_DISPLAY_ROLES_AND_PROTECTED_RECORDS', 'recorded_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'register': str(after_path), 'register_sha256': p['register_sha256'], 'workbook': str(B / p['workbook']), 'workbook_sha256': p['workbook_sha256'], 'pointer_sha256': sha(pointer_path), 'publication_receipt': str(B / p['publication_receipt']), 'packet_sha256': sha(J / 'reviewer-reference-decisions.json'), 'binding_checks': checks, 'semantic_readback': semantic_result, 'nonselected_options_preserved_except_scoped_review_metadata': len(old) - len(ids), 'nine_folder_history_preserved': True, 'published_counts': {'active_options': 187, 'in_situ_gaps': 26, 'series_gaps': 17, 'required_actions': 44}, 'personal_Use_image_claims_added': 0, 'native_or_platform_writes_by_this_lane': 0}
(J / 'published-readback.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
prepared = (J / 'review-results.html').read_text()
published = prepared.replace('18 qualified display references prepared for import', '18 qualified display references saved to the catalogue').replace('Publication status must be read from the current master.', 'Publication and all eighteen source bindings have been independently read back; no product specification or individual primary changed.')
(J / 'published-review-results.html').write_text(published)
completion = {'status': 'COMPLETE_FOLDER_REFRESH_AND_BOUNDED_IMAGE_REVIEWS', 'recorded_utc': result['recorded_utc'], 'published_readback': str(J / 'published-readback.json'), 'published_readback_sha256': sha(J / 'published-readback.json'), 'nine_folder_readback': str(J / 'nine-folder-published-readback.json'), 'series_review': str(B / 'components/parallel-reviews/series-gap-review-20261023T190939Z/review-findings.json'), 'in_situ_cases_reviewed': 44, 'active_in_situ_cases': 36, 'held_or_deferred_cases_preserved': 8, 'qualified_display_roles_added': 18, 'series_cases_reviewed': 17, 'new_series_matches': 0, 'remaining_in_situ_gaps': 26, 'remaining_series_gaps': 17}
(J / 'completion.json').write_text(json.dumps(completion, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({k: v for k, v in result.items() if k not in ['binding_checks', 'semantic_readback']}, ensure_ascii=False))
