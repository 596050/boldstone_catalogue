"""Verify a scoped working-spec acceptance without changing source proposal dictionaries."""
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BATCH = int(sys.argv[1]) if len(sys.argv) > 1 else 56
assert BATCH in [56, 59]
HERE = ROOT / f'components/reviews/parallel-import-2026-10-19-batch{BATCH}'
read = lambda path: json.loads(Path(path).read_text())
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
paths = {'user': ROOT / 'components/reviews/user_classifications.json', 'progress': ROOT / 'components/reviews/specification_review_progress.json', 'walkthrough': ROOT / 'components/reviews/walkthrough_checkpoint.json', 'component': ROOT / 'components/checkpoint.json', 'root': ROOT / 'checkpoint.json'}
old = read(HERE / 'before-import.json'); cur = {key: read(path) for key, path in paths.items()}; receipt = read(HERE / 'import-receipt.json'); decision = read(HERE / 'working-specification-approval.json')
u, p, cp = (cur[key] for key in ['user', 'progress', 'walkthrough']); number = 1 if BATCH == 56 else 2; cid, vid = f'BC-BR-{number}', f'BR-{number}-GOLD-LEAF'; other_cid = 'BC-BR-2' if number == 1 else 'BC-BR-1'
node = p['reviews'][cid]['size_finish_variants'][vid]; prior = old['progress']['reviews'][cid]['size_finish_variants'][vid]
checks = {f'prior_user_{key}_unchanged': u[key] == value for key, value in old['user'].items() if key not in ['updated_utc', 'size_finish_variant_specification_decisions', 'specification_approval_counts']}
checks.update({
    'one_exact_working_spec_ledger_append': u['size_finish_variant_specification_decisions'] == old['user']['size_finish_variant_specification_decisions'] + [decision],
    'canonical_owner_and_card_verified': decision['authoritative_user_evidence']['line'] == (27308 if BATCH == 56 else 27672) and decision['verified_review_card_evidence']['line'] == (27301 if BATCH == 56 else 27665) and 'with the estimates still labelled' in decision['verified_review_card_evidence']['text'] and (BATCH == 56 or decision['user_statement'] == 'yes'),
    'six_source_dictionaries_byte_identical': node['specification_proposals'] == prior['specification_proposals'] == decision['source_specifications_retained'],
    'six_accepted_working_overlay_fields': node['proposals_approved'] and node['owner_estimates_accepted'] and node['all_six_working_specification_fields_accepted'] and len(node['accepted_working_specifications']) == 6 and all(item['owner_approved'] for item in node['accepted_working_specifications'].values()),
    'estimates_and_unknowns_preserved': all(node['accepted_working_specifications'][key]['display'] == value['display'] and node['accepted_working_specifications'][key]['basis'] == value['basis'] and node['accepted_working_specifications'][key]['physical_value_verified'] is False for key, value in prior['specification_proposals'].items()),
    'six_globally_unique_scoped_proposal_IDs': len(set(decision['approved_proposal_ids'])) == 6 and all(item.startswith(vid + ':') for item in decision['approved_proposal_ids']),
    'accepted_working_count_and_finish_count': u['specification_approval_counts']['proposal_groups'] == (76 if BATCH == 56 else 82) and u['specification_approval_counts']['size_finish_variant_proposal_groups'] == (21 if BATCH == 56 else 27) and u['specification_approval_counts']['size_finish_variant_approvals'] == (2 if BATCH == 56 else 3),
    'actual_physical_specs_and_stock_not_verified': node['physical_specs_verified'] is False and node['fully_confirmed_specification_groups'] == [] and decision['independently_measured_or_certified'] is False,
    'prior_name_IDs_reference_and_context_unchanged': all(node[key] == prior[key] for key in ['canonical_name', 'identity_confirmed', 'identity_approval', 'primary_image_id', 'primary_folder_id', 'current_dropbox_reference', 'photo_coverage', 'photo_coverage_summary', 'photo_coverage_review']),
    'all_other_component_reviews_unchanged': all(p['reviews'][key] == value for key, value in old['progress']['reviews'].items() if key != cid),
    'other_Brancusi_component_and_other_finish_scopes_unchanged': p['reviews'][other_cid] == old['progress']['reviews'][other_cid] and all(p['reviews'][cid]['size_finish_variants'][key] == value for key, value in old['progress']['reviews'][cid]['size_finish_variants'].items() if key != vid),
    'source_reviews_and_manufacture_policy_unchanged': all(p[key] == old['progress'][key] for key in ['source_design_reviews', 'catalogue_alias_reviews', 'physical_manufacture_review_policy', 'asset_assignment_overrides']),
    'root_active_question_and_all_current_state_unchanged': cp['current_question_id'] == old['walkthrough']['current_question_id'] and not cp['current_answer_recorded'] and all(cp[key] == value for key, value in old['walkthrough'].items() if key.startswith('current_')),
    'same_component_stock_counts': cur['component']['counts'] == old['component']['counts'] and cur['component']['interactive_review_state']['approved_proposal_groups'] == (76 if BATCH == 56 else 82),
    'root_component_mirror_exact': cur['root']['current_component_review'] == cur['component'],
    'protected_sources_and_workbook_unchanged': all(sha(path) == value for path, value in receipt['protected_sha256'].items()),
    'frozen_source_hashes_match': all(sha(ROOT / item['snapshot']) == item['sha256'] for item in read(HERE / 'source-manifest.json')['files']),
    'shared_saved_hashes_match': all(sha(paths[key]) == value for key, value in receipt['shared_after_sha256'].items()),
    'zero_downloads_and_remote_writes': receipt['summary']['root_new_private_original_downloads'] == receipt['summary']['remote_mutations'] == 0,
})
guards = {key: sha(path) for key, path in paths.items()}
repeat = subprocess.run(['python3', str(ROOT / 'components/reviews/import_brancusi_gold_working_specs_56.py'), str(BATCH)], capture_output=True, text=True, check=True)
checks['idempotent_repeat_NO_WRITE'] = 'ALREADY_IMPORTED_IDEMPOTENT_NO_WRITE' in repeat.stdout and all(sha(paths[key]) == value for key, value in guards.items())
assert all(checks.values()), [key for key, value in checks.items() if not value]
out = {'status': 'PASS', 'checked_utc': datetime.now(timezone.utc).isoformat(), 'check_count': len(checks), 'checks': {key: 'PASS' for key in checks}, 'import_receipt_sha256': sha(HERE / 'import-receipt.json')}
(HERE / 'independent-readback.json').write_text(json.dumps(out, indent=2) + '\n')
event = {'event_id': decision['decision_id'], 'event': f'OWNER_KEPT_SIX_BRANCUSI{number}_GOLD_WORKING_SPECIFICATIONS', 'batch': BATCH, 'actual_specs_verified': False, 'approval': decision['approval_record'], 'readback_sha256': sha(HERE / 'independent-readback.json')}
for path in [ROOT / 'components/reviews/identity_review_journal.jsonl', ROOT / 'review_journal.jsonl']:
    if not any(json.loads(line).get('event_id') == event['event_id'] for line in path.read_text().splitlines() if line.strip()):
        with path.open('a') as stream: stream.write(json.dumps(event) + '\n')
print(json.dumps({'batch': BATCH, 'status': 'PASS', 'checks': len(checks), 'readback_sha256': sha(HERE / 'independent-readback.json')}))
