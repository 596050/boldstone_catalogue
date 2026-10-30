"""Independent saved-state check of the owner's exact4kg answer."""
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / 'components/reviews/parallel-import-2026-10-19-batch52'
read = lambda path: json.loads(Path(path).read_text())
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
paths = {'user': ROOT / 'components/reviews/user_classifications.json', 'progress': ROOT / 'components/reviews/specification_review_progress.json', 'walkthrough': ROOT / 'components/reviews/walkthrough_checkpoint.json', 'component': ROOT / 'components/checkpoint.json', 'root': ROOT / 'checkpoint.json'}
old = read(HERE / 'before-import.json'); receipt = read(HERE / 'import-receipt.json'); cur = {key: read(path) for key, path in paths.items()}
u, p, cp = (cur[key] for key in ['user', 'progress', 'walkthrough']); cid, vid = 'BC-MCP-4', 'MCP4-VERDIGRIS-RUST'
node = p['reviews'][cid]['size_finish_variants'][vid]; prior = old['progress']['reviews'][cid]['size_finish_variants'][vid]; decision = read(HERE / 'owner-weight.json')
checks = {f'prior_user_{key}_unchanged': u[key] == value for key, value in old['user'].items() if key != 'updated_utc'}
checks.update({
    'one_exact_new_weight_decision': u['weight_decisions'] == old['user'].get('weight_decisions', []) + [decision],
    'authoritative_exact4kg_answer_and_preceding_card': decision['authoritative_user_evidence']['line'] == 19523 and decision['authoritative_user_evidence']['text'] == '4 kg' and decision['preceding_assistant_card_evidence']['line'] == 19516,
    'four_kg_numeric_value_and_dry_context_saved': node['owner_stated_weight_kg'] == 4 and node['specification_proposals'][1]['value'] == {'weight_kg': 4, 'basis': 'dry'},
    'measurement_not_invented': node['actual_measured_weight_kg'] is None and node['weight_measurement_method'] == 'UNCONFIRMED' and decision['independently_weighed'] is False,
    'prior_estimated_range_not_approved': decision['prior_estimated_range_approved'] is False and '3–5' not in node['specification_proposals'][1]['display'] and '3–5' in decision['prior_weight_proposal']['display'],
    'owner_statement_not_full_specification_approval': node['specification_proposals'][1]['owner_confirmed'] is True and node['specification_proposals'][1]['owner_approved'] is False and node['proposals_approved'] is False and node['physical_specs_verified'] is False,
    'dimensions_and_other_four_proposals_byte_identical': all(node['specification_proposals'][index] == prior['specification_proposals'][index] for index in [0, 2, 3, 4, 5]),
    'four_pending_fields_and_display': node['specification_status_display'] == 'Dimensions and weight owner-stated; four specification groups pending' and all(not item['owner_approved'] for item in node['specification_proposals'][2:]),
    'owner_dimensions25_and_approx6_preserved': node['owner_confirmed_dimensions_cm'] == {'height': 25, 'width': 25, 'depth': 6} and node['owner_confirmed_depth_qualifier'] == 'approximately',
    'all_other_component_reviews_unchanged': all(p['reviews'][key] == value for key, value in old['progress']['reviews'].items() if key != cid),
    'all_other_MCP4_finishes_unchanged': all(p['reviews'][cid]['size_finish_variants'][key] == value for key, value in old['progress']['reviews'][cid]['size_finish_variants'].items() if key != vid),
    'source_alias_asset_and_manufacture_policy_unchanged': all(p[key] == old['progress'][key] for key in ['source_design_reviews', 'catalogue_alias_reviews', 'asset_assignment_overrides', 'physical_manufacture_review_policy']),
    'same_component_IDs_and_counts': set(p['reviews']) == set(old['progress']['reviews']) and cur['component']['counts'] == old['component']['counts'],
    'exact_same_source_file_folder_and_revision': node['current_dropbox_reference'] == prior['current_dropbox_reference'] and node['primary_image_id'] == 'id:cnqzTNngPVsAAAAAAAylRA' and node['primary_folder_id'] == 'id:cnqzTNngPVsAAAAAAAyipA',
    'new_material_question_unanswered_weight_answer_saved': cp['current_question_id'] == 'MCP4-VERDIGRIS-RUST-MATERIAL-01' and not cp['current_answer_recorded'] and cp['current_weight_answer_recorded'] is True and cp['current_owner_dry_weight_kg'] == 4,
    'material_card_does_not_approve_material': read(ROOT / cp['current_review_record'])['owner_answer_recorded'] is False and read(ROOT / cp['current_review_record'])['actual_material_verified'] is False,
    'root_component_mirror_exact': cur['root']['current_component_review'] == cur['component'],
    'protected_inputs_and_original_weight_card_unchanged': all(sha(path) == value for path, value in receipt['protected_sha256'].items()),
    'frozen_evidence_hashes_match': all(sha(ROOT / item['snapshot']) == item['sha256'] for item in read(HERE / 'source-manifest.json')['files']),
    'saved_shared_hashes_match': all(sha(paths[key]) == value for key, value in receipt['shared_after_sha256'].items()),
    'no_downloads_or_remote_mutations': receipt['summary']['root_new_private_original_downloads'] == receipt['summary']['remote_mutations'] == 0,
})
guards = {key: sha(path) for key, path in paths.items()}
repeat = subprocess.run(['python3', str(ROOT / 'components/reviews/apply_mcp4_rust_weight_52.py')], capture_output=True, text=True, check=True)
checks['idempotent_repeat_NO_WRITE'] = 'ALREADY_IMPORTED_IDEMPOTENT_NO_WRITE' in repeat.stdout and all(sha(paths[key]) == value for key, value in guards.items())
assert all(checks.values()), [key for key, value in checks.items() if not value]
out = {'status': 'PASS', 'checked_utc': datetime.now(timezone.utc).isoformat(), 'check_count': len(checks), 'checks': {key: 'PASS' for key in checks}, 'import_receipt_sha256': sha(HERE / 'import-receipt.json')}
(HERE / 'independent-readback.json').write_text(json.dumps(out, indent=2) + '\n')
event = {'event_id': decision['decision_id'], 'event': 'OWNER_STATED_MCP4_RUST_DRY_WEIGHT4KG', 'batch': 52, 'other_four_fields_approved': False, 'approval': decision['approval_record'], 'readback_sha256': sha(HERE / 'independent-readback.json')}
for path in [ROOT / 'components/reviews/identity_review_journal.jsonl', ROOT / 'review_journal.jsonl']:
    if not any(json.loads(line).get('event_id') == event['event_id'] for line in path.read_text().splitlines() if line.strip()):
        with path.open('a') as stream: stream.write(json.dumps(event) + '\n')
print(json.dumps({'batch': 52, 'status': 'PASS', 'checks': len(checks), 'readback_sha256': sha(HERE / 'independent-readback.json')}))
