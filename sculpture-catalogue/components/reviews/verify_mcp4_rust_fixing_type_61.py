"""Independently check a keyhole type statement while its number remains open."""
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / 'components/reviews/parallel-import-2026-10-19-batch61'
read = lambda path: json.loads(Path(path).read_text())
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
paths = {'user': ROOT / 'components/reviews/user_classifications.json', 'progress': ROOT / 'components/reviews/specification_review_progress.json', 'walkthrough': ROOT / 'components/reviews/walkthrough_checkpoint.json', 'component': ROOT / 'components/checkpoint.json', 'root': ROOT / 'checkpoint.json'}
old = read(HERE / 'before-import.json'); cur = {key: read(path) for key, path in paths.items()}; receipt = read(HERE / 'import-receipt.json'); decision = read(HERE / 'owner-fixing-type.json')
u, p, cp = (cur[key] for key in ['user', 'progress', 'walkthrough']); cid, vid = 'BC-MCP-4', 'MCP4-VERDIGRIS-RUST'; node = p['reviews'][cid]['size_finish_variants'][vid]; prior = old['progress']['reviews'][cid]['size_finish_variants'][vid]
checks = {f'prior_user_{key}_unchanged': u[key] == value for key, value in old['user'].items() if key not in ['updated_utc', 'fixing_detail_decisions']}
checks.update({
    'one_exact_fixing_ledger_append': u['fixing_detail_decisions'] == old['user']['fixing_detail_decisions'] + [decision],
    'canonical_owner_text_and_card_preserved': decision['authoritative_user_evidence']['line'] == 20173 and decision['user_statement'] == 'keyhold fixing' and decision['preceding_assistant_card_evidence']['line'] == 20138,
    'normalized_keyhole_type_only': decision['confirmed_fixing_type'] == 'Keyhole' and node['owner_stated_fixing_type'] == 'Keyhole fixing',
    'count_and_hardware_not_inferred': decision['number_of_fixing_points'] is None and node['owner_stated_fixing_point_count'] is None and node['specification_proposals'][3]['value']['fixing_point_count'] is None and not decision['complete_fixing_group_approved'] and not node['fixing_hardware_or_load_rating_verified'],
    'five_other_proposals_byte_identical': all(node['specification_proposals'][index] == prior['specification_proposals'][index] for index in [0, 1, 2, 4, 5]),
    'owner_dimensions_weight_and_material_preserved': node['owner_confirmed_dimensions_cm'] == {'height': 25, 'width': 25, 'depth': 6} and node['owner_confirmed_depth_qualifier'] == 'approximately' and node['owner_stated_weight_kg'] == 4 and node['owner_stated_base_material'] == 'Plaster composite',
    'price_and_availability_remain_unapproved': all(not item['owner_approved'] for item in node['specification_proposals'][4:]) and not node['proposals_approved'] and not node['physical_specs_verified'],
    'all_other_component_reviews_unchanged': all(p['reviews'][key] == value for key, value in old['progress']['reviews'].items() if key != cid),
    'all_other_MCP4_finishes_unchanged': all(p['reviews'][cid]['size_finish_variants'][key] == value for key, value in old['progress']['reviews'][cid]['size_finish_variants'].items() if key != vid),
    'source_alias_asset_and_global_policy_unchanged': all(p[key] == old['progress'][key] for key in ['source_design_reviews', 'catalogue_alias_reviews', 'asset_assignment_overrides', 'physical_manufacture_review_policy']),
    'same_component_IDs_and_counts': set(p['reviews']) == set(old['progress']['reviews']) and cur['component']['counts'] == old['component']['counts'],
    'exact_source_file_folder_and_revision_preserved': node['current_dropbox_reference'] == prior['current_dropbox_reference'] and decision['primary_file_id'] == 'id:cnqzTNngPVsAAAAAAAylRA' and decision['primary_folder_id'] == 'id:cnqzTNngPVsAAAAAAAyipA',
    'count_question_unanswered_type_answer_saved': cp['current_question_id'] == 'MCP4-VERDIGRIS-RUST-FIXING-COUNT-01' and not cp['current_answer_recorded'] and cp['current_fixing_type_answer_recorded'] and not cp['current_fixing_count_answer_recorded'],
    'count_one_is_only_an_unapproved_proposal': read(ROOT / cp['current_review_record'])['proposed_fixing_point_count'] == 1 and read(ROOT / cp['current_review_record'])['proposal_owner_approved'] is False,
    'root_component_mirror_exact': cur['root']['current_component_review'] == cur['component'],
    'protected_sources_card_and_workbook_unchanged': all(sha(path) == value for path, value in receipt['protected_sha256'].items()),
    'frozen_evidence_hashes_match': all(sha(ROOT / item['snapshot']) == item['sha256'] for item in read(HERE / 'source-manifest.json')['files']),
    'shared_saved_hashes_match': all(sha(paths[key]) == value for key, value in receipt['shared_after_sha256'].items()),
    'no_downloads_or_remote_mutations': receipt['summary']['root_new_private_original_downloads'] == receipt['summary']['remote_mutations'] == 0,
})
guards = {key: sha(path) for key, path in paths.items()}
repeat = subprocess.run(['python3', str(ROOT / 'components/reviews/apply_mcp4_rust_fixing_type_61.py')], capture_output=True, text=True, check=True)
checks['idempotent_repeat_NO_WRITE'] = 'ALREADY_IMPORTED_IDEMPOTENT_NO_WRITE' in repeat.stdout and all(sha(paths[key]) == value for key, value in guards.items())
assert all(checks.values()), [key for key, value in checks.items() if not value]
out = {'status': 'PASS', 'checked_utc': datetime.now(timezone.utc).isoformat(), 'check_count': len(checks), 'checks': {key: 'PASS' for key in checks}, 'import_receipt_sha256': sha(HERE / 'import-receipt.json')}
(HERE / 'independent-readback.json').write_text(json.dumps(out, indent=2) + '\n')
event = {'event_id': decision['decision_id'], 'event': 'OWNER_STATED_MCP4_RUST_KEYHOLE_FIXING_TYPE', 'batch': 61, 'count_or_complete_fixing_approved': False, 'approval': decision['approval_record'], 'readback_sha256': sha(HERE / 'independent-readback.json')}
for path in [ROOT / 'components/reviews/identity_review_journal.jsonl', ROOT / 'review_journal.jsonl']:
    if not any(json.loads(line).get('event_id') == event['event_id'] for line in path.read_text().splitlines() if line.strip()):
        with path.open('a') as stream: stream.write(json.dumps(event) + '\n')
print(json.dumps({'batch': 61, 'status': 'PASS', 'checks': len(checks), 'readback_sha256': sha(HERE / 'independent-readback.json')}))
