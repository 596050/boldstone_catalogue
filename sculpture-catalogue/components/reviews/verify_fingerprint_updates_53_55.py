"""Independent saved-readback for the exact Fingerprint decisions."""
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from import_fingerprint_updates_53_55 import CONFIG

ROOT = Path(__file__).resolve().parents[2]
read = lambda path: json.loads(Path(path).read_text())
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
batch = int(sys.argv[1]); cfg = CONFIG[batch]; here = ROOT / f'components/reviews/parallel-import-2026-10-19-batch{batch}'
paths = {'user': ROOT / 'components/reviews/user_classifications.json', 'progress': ROOT / 'components/reviews/specification_review_progress.json', 'walkthrough': ROOT / 'components/reviews/walkthrough_checkpoint.json', 'component': ROOT / 'components/checkpoint.json', 'root': ROOT / 'checkpoint.json'}
old = read(here / 'before-import.json'); cur = {key: read(path) for key, path in paths.items()}; receipt = read(here / 'import-receipt.json'); key = cfg['key']; ledger = receipt['ledger']
u, p, cp = (cur[name] for name in ['user', 'progress', 'walkthrough']); node = p['source_design_reviews'][key]
decision = read(ROOT / u[ledger][-1]['approval_record'])
checks = {f'prior_user_{name}_unchanged': u[name] == value for name, value in old['user'].items() if name not in ['updated_utc', ledger]}
checks.update({
    'one_exact_ledger_append': u[ledger] == old['user'][ledger] + [decision] and decision['decision_id'] == receipt['decision_id'],
    'canonical_owner_answer': decision['authoritative_user_evidence']['line'] == cfg['line'] and decision['authoritative_user_evidence']['role'] == 'user',
    'exact_cached_review_and_current_metadata_ID_revision': node['source_asset_id'] == read(here / 'current-reference-check.json')['metadata'][0]['file']['id'] and node['source_file_revision'] == read(here / 'current-reference-check.json')['metadata'][0]['file']['rev'],
    'all_existing_component_reviews_and_aliases_unchanged': all(p[name] == old['progress'][name] for name in ['reviews', 'catalogue_alias_reviews', 'catalogue_design_aliases']),
    'other_source_design_reviews_unchanged': all(p['source_design_reviews'][name] == value for name, value in old['progress']['source_design_reviews'].items() if name != key),
    'universal_policy_not_replayed_or_changed': p['physical_manufacture_review_policy'] == old['progress']['physical_manufacture_review_policy'] and u['manufacture_policy_decisions'] == old['user']['manufacture_policy_decisions'] and receipt['summary']['new_owner_policy_events'] == 0,
    'six_specification_estimates_pending': len(node['specifications']) == 6 and node['all_six_complete_specification_groups_pending'] and node['owner_estimates_accepted'] is False and node['physical_specs_verified'] is False,
    'no_member_or_stock_count_created': node['component_ids'] == [] and node['component_member_identification_required_for_current_review'] is False and cur['component']['counts'] == old['component']['counts'],
    'owner_stated_manufacture_not_photo_authentication': node['owner_stated_design_physically_made'] is True and node['physical_production_independently_verified'] is False and node['source_image_authenticated_as_original_photo'] is False,
    'root_active_question_preserved': cp['current_question_id'] == old['walkthrough']['current_question_id'] and not cp['current_answer_recorded'] and all(cp[name] == value for name, value in old['walkthrough'].items() if name.startswith('current_')),
    'root_component_mirror_exact': cur['root']['current_component_review'] == cur['component'],
    'protected_sources_and_published_workbook_unchanged': all(sha(path) == value for path, value in receipt['protected_sha256'].items()),
    'frozen_source_hashes_match': all(sha(ROOT / item['snapshot']) == item['sha256'] for item in read(here / 'source-manifest.json')['files']),
    'saved_shared_hashes_match': all(sha(paths[name]) == value for name, value in receipt['shared_after_sha256'].items()),
    'no_downloads_or_remote_writes': receipt['summary']['root_new_private_original_downloads'] == receipt['summary']['remote_mutations'] == 0,
})
if batch == 53:
    checks['manufacture_only_name_pending'] = not node['identity_confirmed'] and receipt['summary']['new_source_production_confirmations'] == 1 and receipt['summary']['new_source_name_approvals'] == 0
    checks['case_level_AI_not_exact_file_AI'] = node['case_level_partial_AI_resolution_preserved'] and not node['exact_file_AI_declaration_established'] and node['root_original_verification']['embedded_AI_creation_declaration_present'] is None
elif batch == 54:
    checks['name_only_specs_and_production_unchanged'] = node['identity_confirmed'] and node['canonical_source_name'] == 'Fingerprint — Fine Ridge Panels (Verdigris)' and node['specifications'] == old['progress']['source_design_reviews'][key]['specifications'] and u['design_production_confirmation_decisions'] == old['user']['design_production_confirmation_decisions']
elif batch == 55:
    checks['name_only_no_fake_source_manufacture_receipt'] = node['identity_confirmed'] and node['canonical_source_name'] == 'Fingerprint — Diagonal Spiral Panels (Verdigris)' and node['no_source_specific_manufacture_decision_created'] and u['design_production_confirmation_decisions'] == old['user']['design_production_confirmation_decisions']
    checks['exact_AI_declaration_signature_unverified'] = node['source_AI_creation_declaration_preserved'] and node['exact_file_AI_declaration_established'] and node['embedded_signature_verified'] is False
elif batch == 58:
    checks['Multiple_Spiral_name_only_no_fake_source_manufacture'] = node['identity_confirmed'] and node['canonical_source_name'] == 'Fingerprint — Multiple Spiral Panels (Verdigris)' and node['no_source_specific_manufacture_decision_created'] and u['design_production_confirmation_decisions'] == old['user']['design_production_confirmation_decisions']
    checks['Multiple_Spiral_case_level_AI_not_exact_file_AI'] = node['case_level_partial_AI_resolution_preserved'] and not node['exact_file_AI_declaration_established'] and node['root_original_verification']['embedded_AI_creation_declaration_present'] is None
elif batch == 60:
    checks['Oval_Rings_name_only_no_fake_source_manufacture'] = node['identity_confirmed'] and node['canonical_source_name'] == 'Fingerprint — Oval Rings (Verdigris)' and node['no_source_specific_manufacture_decision_created'] and u['design_production_confirmation_decisions'] == old['user']['design_production_confirmation_decisions']
    checks['Oval_Rings_case_level_AI_not_exact_file_AI'] = node['case_level_partial_AI_resolution_preserved'] and not node['exact_file_AI_declaration_established'] and node['root_original_verification']['embedded_AI_creation_declaration_present'] is None
elif batch == 63:
    checks['Twin_Spirals_name_only_no_fake_source_manufacture'] = node['identity_confirmed'] and node['canonical_source_name'] == 'Fingerprint — Twin Spirals (Verdigris)' and node['no_source_specific_manufacture_decision_created'] and u['design_production_confirmation_decisions'] == old['user']['design_production_confirmation_decisions']
    checks['Twin_Spirals_case_level_AI_not_exact_file_AI'] = node['case_level_partial_AI_resolution_preserved'] and not node['exact_file_AI_declaration_established'] and node['root_original_verification']['embedded_AI_creation_declaration_present'] is None
elif batch == 65:
    checks['Oval_Rings_Curls_name_only_no_fake_source_manufacture'] = node['identity_confirmed'] and node['canonical_source_name'] == 'Fingerprint — Oval Rings and Curls (Verdigris)' and node['no_source_specific_manufacture_decision_created'] and u['design_production_confirmation_decisions'] == old['user']['design_production_confirmation_decisions']
    checks['Oval_Rings_Curls_case_level_AI_not_exact_file_AI'] = node['case_level_partial_AI_resolution_preserved'] and not node['exact_file_AI_declaration_established'] and node['root_original_verification']['embedded_AI_creation_declaration_present'] is None
elif batch == 66:
    checks['Offset_Spiral_name_only_no_fake_source_manufacture'] = node['identity_confirmed'] and node['canonical_source_name'] == 'Fingerprint — Offset Spiral Panels (Verdigris)' and node['no_source_specific_manufacture_decision_created'] and u['design_production_confirmation_decisions'] == old['user']['design_production_confirmation_decisions']
    checks['Offset_Spiral_case_level_AI_not_exact_file_AI'] = node['case_level_partial_AI_resolution_preserved'] and not node['exact_file_AI_declaration_established'] and node['root_original_verification']['embedded_AI_creation_declaration_present'] is None
else:
    checks['Rough_Concentric_name_only_no_fake_source_manufacture'] = node['identity_confirmed'] and node['canonical_source_name'] == 'Fingerprint — Rough Concentric Panels (Verdigris)' and node['no_source_specific_manufacture_decision_created'] and u['design_production_confirmation_decisions'] == old['user']['design_production_confirmation_decisions']
    checks['Rough_Concentric_case_level_AI_not_exact_file_AI'] = node['case_level_partial_AI_resolution_preserved'] and not node['exact_file_AI_declaration_established'] and node['root_original_verification']['embedded_AI_creation_declaration_present'] is None
    checks['Rough_Concentric_original_model_relationship_unconfirmed'] = node['original_Fingerprint_model_relationship'] == 'UNCONFIRMED; descriptive source-group naming only' and node['original_40cm_dimensions_inherited'] is False
guards = {name: sha(path) for name, path in paths.items()}
repeat = subprocess.run(['python3', str(ROOT / 'components/reviews/import_fingerprint_updates_53_55.py'), str(batch)], capture_output=True, text=True, check=True)
checks['idempotent_repeat_NO_WRITE'] = 'ALREADY_IMPORTED_IDEMPOTENT_NO_WRITE' in repeat.stdout and all(sha(paths[name]) == value for name, value in guards.items())
assert all(checks.values()), [name for name, value in checks.items() if not value]
out = {'status': 'PASS', 'checked_utc': datetime.now(timezone.utc).isoformat(), 'check_count': len(checks), 'checks': {name: 'PASS' for name in checks}, 'import_receipt_sha256': sha(here / 'import-receipt.json')}
(here / 'independent-readback.json').write_text(json.dumps(out, indent=2) + '\n')
event = {'event_id': decision['decision_id'], 'event': 'OWNER_EXACT_GROUP_MANUFACTURE' if batch == 53 else 'OWNER_KEPT_GROUP_SOURCE_NAME', 'batch': batch, 'specifications_approved': False, 'approval': decision['approval_record'], 'readback_sha256': sha(here / 'independent-readback.json')}
for path in [ROOT / 'components/reviews/identity_review_journal.jsonl', ROOT / 'review_journal.jsonl']:
    if not any(json.loads(line).get('event_id') == event['event_id'] for line in path.read_text().splitlines() if line.strip()):
        with path.open('a') as stream: stream.write(json.dumps(event) + '\n')
print(json.dumps({'batch': batch, 'status': 'PASS', 'checks': len(checks), 'readback_sha256': sha(here / 'independent-readback.json')}))
