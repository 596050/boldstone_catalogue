"""Verify saved global manufacture policy and unchanged review decisions."""
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / 'components/reviews/parallel-import-2026-10-19-batch51'
read = lambda path: json.loads(Path(path).read_text())
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
paths = {'user': ROOT / 'components/reviews/user_classifications.json', 'progress': ROOT / 'components/reviews/specification_review_progress.json', 'walkthrough': ROOT / 'components/reviews/walkthrough_checkpoint.json', 'component': ROOT / 'components/checkpoint.json', 'root': ROOT / 'checkpoint.json'}
old = read(HERE / 'before-import.json'); cur = {key: read(path) for key, path in paths.items()}; receipt = read(HERE / 'import-receipt.json')
policy = read(HERE / 'owner-policy.json'); p, cp = cur['progress'], cur['walkthrough']
checks = {
    'exact_owner_statement_verified': policy['verified_authoritative_user']['line'] == 17365 and policy['verified_authoritative_user']['text'] == 'consider all sculptures physically made',
    'one_global_policy_not_per_source_records': len(cur['user']['manufacture_policy_decisions']) == len(old['user'].get('manufacture_policy_decisions', [])) + 1 and cur['user']['manufacture_policy_decisions'][-1] == policy and receipt['summary']['new_per_source_confirmation_records'] == 0,
    'owner_stated_manufacture_all_scopes': p['physical_manufacture_review_policy'] == policy and policy['owner_confirms_all_sculpture_designs_physically_made'] and policy['evidence_level'] == 'OWNER_STATED_UNIVERSAL_MANUFACTURE',
    'repeat_manufacture_questions_disabled': all(cur[key]['physical_manufacture_review_policy']['repeat_per_source_manufacture_questions_required'] is False for key in ['progress', 'walkthrough', 'component']),
    'spec_stock_and_image_limits_retained': policy['specification_estimates_not_approved'] and policy['exact_dimensions_weight_material_coating_fixings_price_stock_and_leadtime_not_certified'] and policy['image_camera_original_or_client_installation_authenticity_not_certified'] and policy['no_inferred_model_mould_member_or_stock_counts'],
    'all_prior_component_and_source_reviews_unchanged': all(p[key] == old['progress'][key] for key in ['reviews', 'source_design_reviews', 'catalogue_alias_reviews', 'catalogue_design_aliases', 'asset_assignment_overrides']),
    'all_prior_owner_decisions_and_counts_unchanged': all(cur['user'][key] == value for key, value in old['user'].items() if key != 'updated_utc'),
    'same_component_counts': cur['component']['counts'] == old['component']['counts'],
    'root_weight_question_and_all_current_state_preserved': cp['current_question_id'] == 'MCP4-VERDIGRIS-RUST-WEIGHT-01' and not cp['current_answer_recorded'] and all(cp[key] == value for key, value in old['walkthrough'].items() if key.startswith('current_')),
    'root_component_mirror_exact': cur['root']['current_component_review'] == cur['component'],
    'frozen_source_hashes_match': all(sha(ROOT / item['snapshot']) == item['sha256'] for item in read(HERE / 'source-manifest.json')['files']),
    'saved_shared_hashes_match': all(sha(paths[key]) == value for key, value in receipt['shared_after_sha256'].items()),
    'no_downloads_or_remote_mutations': receipt['summary']['root_new_private_original_downloads'] == receipt['summary']['remote_mutations'] == 0,
}
guards = {key: sha(path) for key, path in paths.items()}
repeat = subprocess.run(['python3', str(ROOT / 'components/reviews/import_owner_manufacture_policy_51.py')], capture_output=True, text=True, check=True)
checks['idempotent_repeat_NO_WRITE'] = 'ALREADY_IMPORTED_IDEMPOTENT_NO_WRITE' in repeat.stdout and all(sha(paths[key]) == value for key, value in guards.items())
assert all(checks.values()), [key for key, value in checks.items() if not value]
out = {'status': 'PASS', 'checked_utc': datetime.now(timezone.utc).isoformat(), 'check_count': len(checks), 'checks': {key: 'PASS' for key in checks}, 'import_receipt_sha256': sha(HERE / 'import-receipt.json')}
(HERE / 'independent-readback.json').write_text(json.dumps(out, indent=2) + '\n')
event = {'event_id': policy['policy_id'], 'event': 'OWNER_STATES_ALL_CATALOGUE_SCULPTURES_PHYSICALLY_MADE', 'batch': 51, 'specifications_approved': False, 'approval': policy['approval_record'], 'readback_sha256': sha(HERE / 'independent-readback.json')}
for path in [ROOT / 'components/reviews/identity_review_journal.jsonl', ROOT / 'review_journal.jsonl']:
    if not any(json.loads(line).get('event_id') == event['event_id'] for line in path.read_text().splitlines() if line.strip()):
        with path.open('a') as stream: stream.write(json.dumps(event) + '\n')
print(json.dumps({'batch': 51, 'status': 'PASS', 'checks': len(checks), 'readback_sha256': sha(HERE / 'independent-readback.json')}))
