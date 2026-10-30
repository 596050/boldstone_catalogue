import datetime, hashlib, json, sys
from pathlib import Path

J = Path(__file__).parent
B = J.parents[2]
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
staged = '--stage' in sys.argv
pointer = read(B / 'current-master.json')
before_path = B / 'components/reconciliation/qualified-display-and-series-review-2026-10-23/canonical-master-register.json'
target = 'components/reconciliation/bordered-moonphase-master-refresh-2026-10-23/canonical-master-register.json'
assert staged or pointer['register'] == target, 'Combined Moonphase/context publication has not finished'
after_path = B / target
assert sha(before_path) == '0cee8d9f6c1406d00227aad1a8196bedfff34dbe93a1f82887e53fd7903ffddc'
after_sha = sha(after_path)
old_reg, new_reg = read(before_path), read(after_path)
old = {x['product_id']: x for x in old_reg['options']}
new = {x['product_id']: x for x in new_reg['options']}
assert old.keys() == new.keys() and len(old) == 188
A = J.parent / 'remaining-photo-sources-and-bordered-import-20261023T200049Z'
apath = A / 'bordered-display-reference-decisions.json'
bpath = J / 'qualified-workshop-garden-decisions.json'
assert sha(apath) == '898986b245cdae06d2645007a58905a886f711eb6643e58249dc057ea89164ed'
assert sha(bpath) == '02e248dfef6996d58e7986884fdafc5beb297cc099950ad5fc0653d9600e4673'
decisions = read(apath)['decisions'] + read(bpath)['decisions']
selected = {x['product_id'] for x in decisions}
bordered = {'BSI-65A93033A200', 'BSI-4515726BBC18'}
assert len(selected) == 4 and {oid for oid in old if old[oid] != new[oid]} == selected
protected = ['file_id', 'folder_id', 'image_url', 'folder_url', 'name', 'canonical_key', 'canonical_design_id', 'sale_unit', 'specifications', 'master_fields', 'offered_fixing_choices', 'selling_details', 'current_commercial_policy', 'physical_specifications_verified']
old_cov = {x['option_id']: x for x in read(before_path.with_name('image-coverage-current.json'))['coverage']}
audit = read(after_path.with_name('image-coverage-current.json'))
new_cov = {x['option_id']: x for x in audit['coverage']}
state = read(after_path.with_name('guided-owner-review-state.json'))
for oid in old:
    for key in protected:
        assert (key in old[oid]) == (key in new[oid]) and old[oid].get(key) == new[oid].get(key), (oid, key)
    assert old_cov[oid]['individual'] == new_cov[oid]['individual'], (oid, 'individual')
    if oid in bordered:
        for key in ['file_id', 'folder_id', 'name']:
            assert old_cov[oid]['series']['reference'][key] == new_cov[oid]['series']['reference'][key], (oid, 'series', key)
        assert old_cov[oid]['series']['status'] == new_cov[oid]['series']['status']
        assert '/Moonphase 1 and Moonphase 2 With Borders White/' in new_cov[oid]['series']['reference']['path']
    else:
        assert old_cov[oid]['series'] == new_cov[oid]['series'], (oid, 'series')
    if oid not in selected:
        assert old_cov[oid] == new_cov[oid], (oid, 'unselected coverage')
checks = []
for d in decisions:
    oid = d['product_id']; role = new_cov[oid]['in_situ']; ref = role['reference']
    assert role['status'] == 'Available'
    for key in ['file_id', 'folder_id', 'name', 'path', 'image_url', 'folder_url']:
        assert ref[key] == d['reference'][key], (oid, key)
    assert role['display_qualification'] == d['display_qualification']
    for key in ['explicit_owner_image_role_approval', 'scene_authenticity_verified', 'physical_cast_or_size_certified', 'creation_origin_verified']:
        assert role[key] is False, (oid, key)
    assert role['qualified_display_only'] is True
    assert new[oid]['context_file_id'] == ref['file_id'] and new[oid]['context_folder_id'] == ref['folder_id']
    assert new[oid]['current_photo_task_review']['recorded_utc'].startswith('2026-10-23T')
    checks.append({'option_id': oid, 'file_id': ref['file_id'], 'parent_id': ref['folder_id'], 'qualification': role['display_qualification']})
held = set(state['held_in_situ_ids'])
assert len(held) == 8 and not held & selected
assert all(old[x] == new[x] and old_cov[x] == new_cov[x] for x in held)
assert new_reg['current_removed_empty_folder_history'] == old_reg['current_removed_empty_folder_history']
mp1 = 'BSI-65A93033A200'
old_extra = old[mp1].get('additional_individual_references', [])
extra = new[mp1]['additional_individual_references']
assert extra[:len(old_extra)] == old_extra and len(extra) == len(old_extra) + 1
item = extra[-1]
assert item['file_id'] == 'id:cnqzTNngPVsAAAAAAAt4DQ' and item['folder_id'] == 'id:cnqzTNngPVsAAAAAAAylYQ'
assert '/Moonphase 1 With Borders White/' in item['path'] and item['primary_replacement'] is False and item['physical_specification_evidence'] is False
counts = audit['counts']
assert counts['individual_options'] == 187 and counts['in_situ_statuses']['No verified image'] == 22 and counts['series_statuses']['No verified image'] == 17 and counts['required_picture_actions'] == 40
assert len(state['queues']['in_situ']) == 14 and len(state['queues']['series']) == 17
assert sha(after_path) == after_sha, 'Register changed during checks'
result = {'recorded_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'status': 'PASS_STAGED_FOUR_QUALIFIED_ROLES_AND_MOONPHASE_FOLDER_REFRESH' if staged else 'PASS_PUBLISHED_FOUR_QUALIFIED_ROLES_AND_MOONPHASE_FOLDER_REFRESH', 'staged_not_published': staged, 'register': str(after_path), 'register_sha256': after_sha, 'binding_checks': checks, 'protected_field_checks': 188 * len(protected), 'individual_image_roles_unchanged': 188, 'series_identity_bindings_preserved': 188, 'unselected_option_and_coverage_records_unchanged': 184, 'held_cases_unchanged': 8, 'nine_removed_empty_folder_history_preserved': True, 'image_008_additional_only_at_correct_parent': True, 'active_options': 187, 'active_context_gaps': 14, 'total_context_gaps_including_holds': 22, 'series_gaps': 17, 'required_actions_including_deferred_identity': 40, 'B_native_or_platform_writes': 0}
if not staged:
    assert pointer['register_sha256'] == after_sha
    assert sha(B / pointer['workbook']) == pointer['workbook_sha256']
    receipt = read(B / pointer['publication_receipt'])
    assert receipt['status'] == 'PASS_PUBLISHED_AND_READ_BACK'
    assert receipt['register_sha256'] == after_sha and receipt['workbook_sha256'] == pointer['workbook_sha256']
    result.update(workbook=str(B / pointer['workbook']), workbook_sha256=pointer['workbook_sha256'], pointer_sha256=sha(B / 'current-master.json'), publication_receipt=str(B / pointer['publication_receipt']))
filename = 'staged-moonphase-and-context-readback.json' if staged else 'published-moonphase-and-context-readback.json'
(J / filename).write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({k: v for k, v in result.items() if k != 'binding_checks'}))
