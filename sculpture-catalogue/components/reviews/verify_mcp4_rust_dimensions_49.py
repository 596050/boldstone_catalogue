"""Independent saved-record check of dimensions-only approval and next unanswered question."""
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / 'components/reviews/parallel-import-2026-10-19-batch49'
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
paths = {'user': ROOT / 'components/reviews/user_classifications.json', 'progress': ROOT / 'components/reviews/specification_review_progress.json', 'walkthrough': ROOT / 'components/reviews/walkthrough_checkpoint.json', 'component': ROOT / 'components/checkpoint.json', 'root': ROOT / 'checkpoint.json'}
old, receipt = read(HERE / 'before-import.json'), read(HERE / 'import-receipt.json'); cur = {k: read(v) for k, v in paths.items()}
u, p, cp = (cur[k] for k in ['user', 'progress', 'walkthrough']); cid, vid = 'BC-MCP-4', 'MCP4-VERDIGRIS-RUST'
node = p['reviews'][cid]['size_finish_variants'][vid]; prior = old['progress']['reviews'][cid]['size_finish_variants'][vid]; decision = read(HERE / 'owner-dimensions.json')
checks = {f'prior_user_{k}_unchanged': u[k] == v for k, v in old['user'].items() if k not in ['updated_utc', 'dimension_decisions', 'dimension_confirmation_counts']}
checks.update({'one_exact_new_dimension_decision': u['dimension_decisions'][:-1] == old['user']['dimension_decisions'] and u['dimension_decisions'][-1] == decision,
    'exact_authoritative_owner_and_dimension_card': decision['authoritative_user_evidence']['line'] == 19184 and decision['preceding_assistant_card_evidence']['line'] == 19166,
    'face25_and_depth6_preserve_approximation': decision['confirmed_dimensions_cm'] == {'height': 25, 'width': 25, 'depth': 6} and decision['depth_qualifier'] == 'approximately' and decision['depth_is_exact'] is False,
    'owner_statement_not_independent_measurement': decision['independently_measured'] is False and node['physical_specs_verified'] is False,
    'only_dimension_proposal_changed_other5_byte_identical': node['specification_proposals'][1:] == prior['specification_proposals'][1:] and all(x['owner_approved'] is False for x in node['specification_proposals'][1:]),
    'dimension_owner_confirmation_saved': node['specification_proposals'][0]['owner_confirmed'] is True and node['specification_proposals'][0]['owner_approved'] is False and 'approximately 6 cm' in node['specification_proposals'][0]['display'],
    'no_blanket_spec_approval': node['proposals_approved'] is False and u['specification_approval_counts'] == old['user']['specification_approval_counts'],
    'dimension_instruction_count21_complete2_face19': u['dimension_confirmation_counts']['individual_dimension_decisions'] == 21 and u['dimension_confirmation_counts']['complete_dimension_instruction_decisions'] == 2 and u['dimension_confirmation_counts']['face_size_decisions'] == 19,
    'same_existing_design_IDs_and_legacy_counts': set(p['reviews']) == set(old['progress']['reviews']) and cur['component']['counts'] == old['component']['counts'],
    'all_other_component_reviews_unchanged': all(p['reviews'][k] == v for k, v in old['progress']['reviews'].items() if k != cid),
    'all_other_MCP4_finishes_unchanged': all(p['reviews'][cid]['size_finish_variants'][k] == v for k, v in old['progress']['reviews'][cid]['size_finish_variants'].items() if k != vid),
    'source_reviews_aliases_and_asset_assignments_unchanged': all(p[k] == old['progress'][k] for k in ['source_design_reviews', 'catalogue_alias_reviews', 'asset_assignment_overrides']),
    'new_weight_question_unanswered': cp['current_question_id'] == 'MCP4-VERDIGRIS-RUST-WEIGHT-01' and not cp['current_answer_recorded'] and cp['current_dimension_answer_recorded'] is True,
    'weight_card_is_unweighed_estimate_only': read(ROOT / cp['current_review_record'])['actual_measured_weight_kg'] is None and not read(ROOT / cp['current_review_record'])['owner_answer_recorded'],
    'same_primary_file_and_folder_IDs': node['primary_image_id'] == 'id:cnqzTNngPVsAAAAAAAylRA' and node['primary_folder_id'] == 'id:cnqzTNngPVsAAAAAAAyipA',
    'root_component_mirror_exact': cur['root']['current_component_review'] == cur['component'],
    'immutable_inputs_and_dimension_card_unchanged': all(sha(path) == value for path, value in receipt['protected_sha256'].items()),
    'frozen_evidence_hashes_match': all(sha(ROOT / x['snapshot']) == x['sha256'] for x in read(HERE / 'source-manifest.json')['files']),
    'shared_saved_hashes_match': all(sha(paths[k]) == value for k, value in receipt['shared_after_sha256'].items()),
    'zero_downloads_or_remote_writes': receipt['summary']['root_new_private_original_downloads'] == receipt['summary']['remote_mutations'] == 0})
guards = {k: sha(v) for k, v in paths.items()}
repeat = subprocess.run(['python3', str(ROOT / 'components/reviews/apply_mcp4_rust_dimensions_49.py')], capture_output=True, text=True, check=True)
checks['idempotent_repeat_NO_WRITE'] = 'ALREADY_IMPORTED_IDEMPOTENT_NO_WRITE' in repeat.stdout and all(sha(paths[k]) == value for k, value in guards.items())
assert all(checks.values()), [k for k, v in checks.items() if not v]
out = {'status': 'PASS', 'checked_utc': datetime.now(timezone.utc).isoformat(), 'check_count': len(checks), 'checks': {k: 'PASS' for k in checks}, 'import_receipt_sha256': sha(HERE / 'import-receipt.json')}
(HERE / 'independent-readback.json').write_text(json.dumps(out, indent=2) + '\n')
event = {'event_id': decision['decision_id'], 'event': 'OWNER_CONFIRMED_MCP4_RUST_FACE_AND_APPROX_DEPTH', 'batch': 49, 'other_five_fields_approved': False, 'approval': decision['approval_record'], 'readback_sha256': sha(HERE / 'independent-readback.json')}
for path in [ROOT / 'components/reviews/identity_review_journal.jsonl', ROOT / 'review_journal.jsonl']:
    if not any(json.loads(line).get('event_id') == event['event_id'] for line in path.read_text().splitlines() if line.strip()):
        with path.open('a') as stream: stream.write(json.dumps(event) + '\n')
print(json.dumps({'batch': 49, 'status': 'PASS', 'checks': len(checks), 'readback_sha256': sha(HERE / 'independent-readback.json')}))
