"""Bounded v2 review against the independently sealed, preserved v1 candidate."""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import json
from inspect_candidate import LANE, ROOT, CANDIDATE as C, load, sha, diffs


def save(name, value):
    with (LANE / name).open('x') as f:
        json.dump(value, f, ensure_ascii=False, indent=2); f.write('\n')


checks = []
def check(name, passed, detail=None):
    checks.append({'name': name, 'passed': bool(passed), 'details': detail})


v1 = load(LANE / 'candidate-readback.json')
seal1 = load(LANE / 'sealed-handoff.json')
freeze = load(C / 'candidate-freeze.json')
assert freeze['candidate_register_sha256'] != v1['candidate_register_sha256'], 'Wait for v2 freeze'
frozen = dict(freeze['frozen_artifacts'])
frozen[str(C / 'candidate-freeze.json')] = sha(C / 'candidate-freeze.json')
assert all(sha(p) == h for p, h in frozen.items()), 'Frozen files are not stable'
old_folder = C / 'superseded-candidate-v1-counter-scope'
check('prior_36_check_PASS_and_full_B_seal_remain_valid',
      v1['status'] == seal1['status'] == 'PASS' and v1['checks_passed'] == v1['checks_total'] == 36 and
      all(sha(x['path']) == x['sha256'] for x in seal1['files']))
changed_names = {'canonical-master-register.json', 'import-summary.json', 'source-evidence-verification.json',
                 'report-verification.json', 'saved-file-verification.json', 'native-binding-verification.json',
                 'visual-verification.json'}
old_hashes = v1['frozen_artifacts']
check('all_seven_superseded_v1_files_and_freeze_match_independent_QA_hashes',
      all(sha(old_folder / n) == old_hashes[str(C / n)] for n in changed_names | {'candidate-freeze.json'}))
actual_changed = {Path(p).name for p, h in old_hashes.items() if sha(p) != h}
check('only_seven_metadata_files_counter_emitting_importer_and_freeze_changed',
      actual_changed == changed_names | {'candidate-freeze.json', 'import_moonwave.py'}, sorted(actual_changed))
added_frozen = set(frozen) - set(old_hashes)
removed_frozen = set(old_hashes) - set(frozen)
check('new_freeze_keeps_every_prior_artifact_and_only_adds_counter_receipt',
      not removed_frozen and added_frozen <= {str(C / 'counter-scope-correction.json')},
      {'added': sorted(added_frozen), 'removed': sorted(removed_frozen)})
changes = {n: list(diffs(load(old_folder / n), load(C / n))) for n in sorted(changed_names)}


def counter_corrected(before, obsolete):
    after = deepcopy(before)
    assert after.pop(obsolete) == 0
    after['new_original_binary_downloads_by_importer'] = 0
    after['local_originals_rehashed_by_importer'] = 10
    return after


old_summary = load(old_folder / 'import-summary.json')
summary = load(C / 'import-summary.json')
check('summary_only_replaces_ambiguous_zero_reads_with_zero_downloads_and_ten_local_rehashes',
      counter_corrected(old_summary, 'new_original_binary_reads') == summary)
old_register = load(old_folder / 'canonical-master-register.json')
register = load(C / 'canonical-master-register.json')
expected_register = deepcopy(old_register)
expected_register['latest_current_url_case_normalization'] = summary
check('full_register_only_changes_same_three_counter_fields', expected_register == register)
old_evidence = load(old_folder / 'source-evidence-verification.json')
evidence = load(C / 'source-evidence-verification.json')
check('source_verification_only_replaces_same_ambiguous_counter',
      counter_corrected(old_evidence, 'binary_reads') == evidence)
new_reg_hash = sha(C / 'canonical-master-register.json')
receipt_checks = []
for name in ['report-verification.json', 'saved-file-verification.json', 'native-binding-verification.json']:
    before = load(old_folder / name); after = load(C / name)
    expected_receipt = deepcopy(before)
    expected_receipt['register_sha256'] = new_reg_hash
    expected_receipt['recorded_utc'] = after['recorded_utc']
    receipt_checks.append(expected_receipt == after and
                          datetime.fromisoformat(after['recorded_utc']) >= datetime.fromisoformat(before['recorded_utc']))
check('three_validation_receipts_only_rebind_register_hash_and_update_timestamp', all(receipt_checks))
old_visual = load(old_folder / 'visual-verification.json')
visual = load(C / 'visual-verification.json')
expected_visual = deepcopy(old_visual); expected_visual['register_sha256'] = new_reg_hash
visual_body = deepcopy(visual); rebind = visual_body.pop('metadata_rebind')
check('visual_receipt_only_rebinds_register_with_explicit_same_workbook_previews_note',
      visual_body == expected_visual and rebind == {
          'recorded_utc': rebind['recorded_utc'],
          'reason': 'Counter-scope clarification only: zero new importer network downloads and ten local original rehashes. Workbook and all inspected previews are byte-identical to visually inspected v1.',
          'superseded_receipt': str(old_folder / 'visual-verification.json'),
          'superseded_receipt_sha256': sha(old_folder / 'visual-verification.json')} and
      datetime.fromisoformat(rebind['recorded_utc']) >= datetime.fromisoformat(old_visual['recorded_utc']) and
      all(sha(x['path']) == x['sha256'] for x in visual['previews']))
code_reconstruction = load(LANE / 'v1-snapshots/import-code-reconstruction.json')
old_code_path = LANE / 'v1-snapshots/import_moonwave.py'
expected_code = old_code_path.read_text()
for new_text, old_text in code_reconstruction['changes_reversed']:
    assert expected_code.count(old_text) == 1, 'Counter replacement is not unique'
    expected_code = expected_code.replace(old_text, new_text)
check('importer_code_only_emits_the_two_reviewed_counter_corrections',
      sha(old_code_path) == old_hashes[str(C / 'import_moonwave.py')] == code_reconstruction['sha256'] and
      expected_code == (C / 'import_moonwave.py').read_text())
check('workbook_audit_and_every_other_frozen_payload_remain_byte_identical',
      all(sha(p) == h for p, h in old_hashes.items() if Path(p).name not in changed_names | {'candidate-freeze.json', 'import_moonwave.py'}) and
      sha(C / 'master-workbook.pending') == v1['candidate_workbook_sha256'] and
      sha(C / 'image-coverage-current.json') == v1['candidate_audit_sha256'])
check('all_HTML_and_CSV_outputs_remain_byte_identical_to_v1',
      all(sha(p) == h for p, h in v1['report_artifacts'].items()))
check('current_freeze_hash_bindings_match_v2_register_and_unchanged_book_audit',
      freeze['candidate_register_sha256'] == new_reg_hash and
      freeze['candidate_workbook_sha256'] == v1['candidate_workbook_sha256'] and
      freeze['candidate_audit_sha256'] == v1['candidate_audit_sha256'])
native = load(LANE / 'moonwave-native-readback.json')
check('ten_local_rehash_counter_matches_previously_sealed_native_evidence',
      native['status'] == 'PASS' and native['checks_passed'] == native['checks_total'] == 13 and
      evidence['Moonwave_fresh_originals_rehashed_by_importer'] == summary['local_originals_rehashed_by_importer'] == 10 and
      summary['new_original_binary_downloads_by_importer'] == evidence['new_original_binary_downloads_by_importer'] == 0)
prior_attestation = load(LANE / 'source-review-baseline-attestation.json')
check('B43_48_options_288_fields_source_observations_still_unchanged',
      prior_attestation['options_checked'] == 48 and prior_attestation['complete_working_fields_checked'] == 288 and
      register['options'] == old_register['options'] and
      register['current_authenticated_squarespace_inventory_observation'] == old_register['current_authenticated_squarespace_inventory_observation'])
counter_receipt = C / 'counter-scope-correction.json'
counter_hash = sha(counter_receipt)
check('correction_receipt_declares_no_book_option_source_navigation_role_changes',
      load(counter_receipt)['book_option_source_navigation_role_changes'] == 0 and
      Path(load(counter_receipt)['prior_candidate_preserved']) == old_folder)
check('frozen_v2_and_unchanged_published_baseline_stable_at_completion',
      all(sha(p) == h for p, h in frozen.items()) and
      sha(counter_receipt) == counter_hash and
      sha(ROOT / 'current-master.json') == load(LANE / 'expectations.json')['baseline_pointer_sha256'])
now = datetime.now(timezone.utc).isoformat()
result = {'schema': 'boldstone.independent.combined-navigation-v2-counter-addendum.v1',
          'status': 'PASS' if all(x['passed'] for x in checks) else 'FAIL', 'recorded_utc': now,
          'checks_passed': sum(x['passed'] for x in checks), 'checks_total': len(checks), 'checks': checks,
          'candidate_register_sha256': new_reg_hash,
          'candidate_workbook_sha256': v1['candidate_workbook_sha256'], 'candidate_audit_sha256': v1['candidate_audit_sha256'],
          'frozen_artifacts': frozen, 'report_artifacts': v1['report_artifacts'], 'metadata_differences': changes,
          'importer_counter_code_reconstruction': code_reconstruction,
          'prior_candidate_validation': {'path': str(LANE / 'candidate-readback.json'), 'sha256': sha(LANE / 'candidate-readback.json'),
                                         'checks_passed': 36, 'checks_total': 36, 'substantive_checks_retained_by_exact_v1_v2_comparison': True},
          'counter_receipt': {'path': str(counter_receipt), 'sha256': counter_hash},
          'scope': 'V2 distinguishes zero new downloads from ten local original rehashes. Only three counter-field changes in register/summary/evidence plus timestamp/hash rebindings; all workbook, navigation, source, identity, specifications, images and holds remain as independently checked in v1.',
          'shared_writes': 0, 'native_calls': 0}
save('candidate-v2-readback.json', result)
files = ['verify_metadata_addendum.py', 'candidate-v2-readback.json', 'candidate-readback.json', 'sealed-handoff.json',
         'v1-snapshots/import_moonwave.py', 'v1-snapshots/import-code-reconstruction.json']
if result['status'] == 'PASS':
    attestation = deepcopy(prior_attestation)
    attestation['recorded_utc'] = now; attestation['candidate_register_sha256'] = new_reg_hash
    attestation['prior_attestation'] = {'path': str(LANE / 'source-review-baseline-attestation.json'), 'sha256': sha(LANE / 'source-review-baseline-attestation.json')}
    save('source-review-baseline-v2-attestation.json', attestation)
    files.append('source-review-baseline-v2-attestation.json')
seal = {'status': result['status'], 'recorded_utc': now, 'candidate_register_sha256': new_reg_hash,
        'candidate_workbook_sha256': result['candidate_workbook_sha256'],
        'files': [{'path': str(LANE / n), 'sha256': sha(LANE / n)} for n in files],
        'prior_full_seal': {'path': str(LANE / 'sealed-handoff.json'), 'sha256': sha(LANE / 'sealed-handoff.json')},
        'shared_writes': 0, 'native_calls': 0}
save('sealed-v2-handoff.json', seal)
print(json.dumps({'status': result['status'], 'passed': result['checks_passed'], 'total': result['checks_total'],
                  'failed': [x for x in checks if not x['passed']], 'qa_sha256': sha(LANE / 'candidate-v2-readback.json'),
                  'seal_sha256': sha(LANE / 'sealed-v2-handoff.json')}, indent=2))
