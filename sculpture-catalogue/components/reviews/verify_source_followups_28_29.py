"""Independent saved-state audit for manufacture and name-only group follow-ups."""
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
batch = int(sys.argv[1]); assert batch in [28, 29, 32, 33, 37, 39, 42, 44, 46, 47]
manufacture = batch in [28, 32, 37, 42, 46]
looped = batch in [46, 47]
asymmetric = batch in [42, 44]
three_panel = batch in [32, 33]
four_panel_row = batch in [37, 39]
expected_file = 'id:cnqzTNngPVsAAAAAAAyhVQ' if looped else 'id:cnqzTNngPVsAAAAAAAyhQQ' if asymmetric else 'id:cnqzTNngPVsAAAAAAAyhPg' if four_panel_row else 'id:cnqzTNngPVsAAAAAAAyhPA' if three_panel else 'id:cnqzTNngPVsAAAAAAAyhTA'
expected_folder = 'id:cnqzTNngPVsAAAAAAAyhOw' if three_panel or four_panel_row or asymmetric else 'id:cnqzTNngPVsAAAAAAAyhHw'
here = ROOT / f'components/reviews/parallel-import-2026-10-19-batch{batch}'
paths = {'user': ROOT / 'components/reviews/user_classifications.json', 'progress': ROOT / 'components/reviews/specification_review_progress.json',
         'walkthrough': ROOT / 'components/reviews/walkthrough_checkpoint.json', 'component': ROOT / 'components/checkpoint.json', 'root': ROOT / 'checkpoint.json'}
old, receipt, manifest = (read(here / name) for name in ['before-import.json', 'import-receipt.json', 'source-manifest.json'])
cur = {k: read(p) for k, p in paths.items()}; key = receipt['source_design_key']; node = cur['progress']['source_design_reviews'][key]
ledger = 'design_production_confirmation_decisions' if manufacture else 'source_design_name_decisions'
checks = {f'previous_user_{k}_unchanged': cur['user'][k] == value for k, value in old['user'].items() if k not in ['updated_utc', ledger]}
checks.update({'one_exact_new_scoped_decision': cur['user'][ledger][:-1] == old['user'][ledger] and len(cur['user'][ledger]) == len(old['user'][ledger]) + 1,
    'source_file_and_folder_exact': node['source_asset_id'] == expected_file and node['source_folder_id'] == expected_folder,
    'manufacture_owner_statement_not_independently_verified': node['owner_stated_design_physically_made'] and not node['physical_production_independently_verified'],
    'all_six_estimates_unaccepted': len(node['specifications']) == 6 and not node['owner_estimates_accepted'] and node['specification_fields_fully_approved'] == [],
    'group_dimensions_remain_proposal': node['specifications']['dimensions']['proposal_overall_HWD_cm'] == ([50, 105, 4] if looped else [50, 90, 4] if asymmetric else [50, 180, 4] if four_panel_row else [50, 130, 4] if three_panel else [80, 80, 4]) and not node['specifications']['dimensions']['owner_confirmed'],
    'group_weight_and_scoped_range_unaccepted': node['specifications']['weight']['proposal_dry_group_kg'] == (19 if looped else 16 if asymmetric else 32 if four_panel_row else 22) and node['specifications']['weight']['conditional_range_kg'] == ([14, 24] if looped else [12, 20] if asymmetric else [24, 40] if four_panel_row else [17, 28] if three_panel else [16, 27]) and not node['specifications']['weight']['owner_estimate_accepted'],
    'no_component_member_or_stock_count': node['component_ids'] == node['new_registered_BC_component_ids'] == [] and not node['component_member_identification_required_for_current_review'],
    'source_origin_preserved_without_photo_authentication': not node['source_image_authenticated_as_original_photo'] and node['exact_file_AI_declaration_established'] is (three_panel or four_panel_row or asymmetric or looped) and not node['embedded_signature_verified'],
    'all_other_source_reviews_unchanged': all(cur['progress']['source_design_reviews'][k] == v for k, v in old['progress']['source_design_reviews'].items() if k != key),
    'all_component_reviews_unchanged': cur['progress']['reviews'] == old['progress']['reviews'],
    'all_frozen_reference_hashes_and_sizes': all(sha(ROOT / x['snapshot']) == x['sha256'] and (ROOT / x['snapshot']).stat().st_size == x['bytes'] for x in manifest['files']),
    'main_MCP4_answer_and_review_scope_preserved': all(cur['walkthrough'][k] == v for k, v in old['walkthrough'].items() if k.startswith('current_')),
    'MCP4_canonical_consolidation_preserved': cur['progress']['canonical_component_consolidations'] == old['progress']['canonical_component_consolidations'],
    'G050_and_group_policy_preserved': cur['walkthrough']['deferred_reviews'] == old['walkthrough']['deferred_reviews'] and cur['progress']['group_photo_review_policy'] == old['progress']['group_photo_review_policy'],
    'legacy_counts_unchanged': cur['component']['counts'] == old['component']['counts'],
    'root_component_mirror': cur['root']['current_component_review'] == cur['component'],
    'protected_files_unchanged': all(sha(Path(p)) == digest for p, digest in receipt['protected_sha256'].items()),
    'shared_hashes_and_repeat_import_no_write': all(sha(paths[k]) == digest for k, digest in receipt['shared_after_sha256'].items()),
    'no_remote_mutation_or_new_original': receipt['summary']['root_new_private_original_downloads'] == 0 and receipt['summary']['remote_mutations'] == 0})
if manufacture:
    checks['name_not_approved_by_manufacture'] = not node['identity_confirmed'] and not node['catalogue_name_explicitly_approved']
    checks['exact_actual_owner_and_question'] = [x['line'] for x in manifest['verified_messages']] == ([17144, 17151] if looped else [16967, 16974] if asymmetric else [16796, 16814] if four_panel_row else [16700, 16707] if three_panel else [16537, 16560])
else:
    checks['name_kept_exact'] = node['identity_confirmed'] and node['canonical_name'] == ('Fingerprint — Looped Ridge Panels (Verdigris)' if looped else 'Fingerprint — Asymmetric Spiral Panels (Verdigris)' if asymmetric else 'Fingerprint — Four Panel Row (Verdigris)' if four_panel_row else 'Fingerprint — Three Panel Arrangement (Verdigris)' if three_panel else 'Fingerprint — Four Panel Arrangement (Verdigris)') and node['active_owner_question'] is None
    checks['no_manufacture_replay'] = cur['user']['design_production_confirmation_decisions'] == old['user']['design_production_confirmation_decisions'] and sum(x.get('source_design_key') == key for x in cur['user']['design_production_confirmation_decisions']) == 1
    checks['all_specifications_byte_equal_before_name'] = node['specifications'] == old['progress']['source_design_reviews'][key]['specifications']
    checks['exact_actual_owner_and_question'] = [x['line'] for x in manifest['verified_messages']] == ([17204, 17211] if looped else [17003, 17010] if asymmetric else [16843, 16883] if four_panel_row else [16732, 16750] if three_panel else [16587, 16605])
assert all(checks.values()), [k for k, v in checks.items() if not v]
out = {'status': 'PASS', 'checked_utc': datetime.now(timezone.utc).isoformat(), 'check_count': len(checks), 'checks': {k: 'PASS' for k in checks}, 'idempotency_status': 'PASS_NO_WRITE', 'shared_after_sha256': receipt['shared_after_sha256']}
(here / 'independent-shared-readback.json').write_text(json.dumps(out, indent=2) + '\n')
event = {'event': 'verified_group_source_followup', 'batch': batch, 'source_design_key': key, 'scope': ledger, 'new_specification_approvals': 0, 'new_BC_ids': [], 'remote_mutations': 0}
for path in [ROOT / 'components/reviews/identity_review_journal.jsonl', ROOT / 'review_journal.jsonl']:
    with path.open('a') as stream: stream.write(json.dumps(event) + '\n')
print(json.dumps({'batch': batch, 'status': 'PASS', 'checks': len(checks), 'receipt_sha256': sha(here / 'import-receipt.json'), 'readback_sha256': sha(here / 'independent-shared-readback.json')}))
