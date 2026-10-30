"""Check the saved Silver name-only decision independently of its importer."""
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / 'components/reviews/parallel-import-2026-10-19-batch50'
read = lambda path: json.loads(Path(path).read_text())
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
paths = {'user': ROOT / 'components/reviews/user_classifications.json', 'progress': ROOT / 'components/reviews/specification_review_progress.json', 'walkthrough': ROOT / 'components/reviews/walkthrough_checkpoint.json', 'component': ROOT / 'components/checkpoint.json', 'root': ROOT / 'checkpoint.json'}
before = read(HERE / 'before-import.json')
cur = {key: read(path) for key, path in paths.items()}
receipt = read(HERE / 'import-receipt.json')
decision = read(HERE / 'identity-approval.json')
u, p, cp = (cur[key] for key in ['user', 'progress', 'walkthrough'])
variant = 'MOONPHASE-CURRENT-4:SILVER'
node = p['catalogue_alias_reviews'][variant]
ref = node['current_dropbox_reference']
checks = {
    'one_exact_new_name_decision': u['catalogue_finish_alias_decisions'][:-1] == before['user']['catalogue_finish_alias_decisions'] and u['catalogue_finish_alias_decisions'][-1] == decision,
    'canonical_owner_keep_line27046': decision['verified_authoritative_user']['line'] == 27046 and decision['verified_authoritative_user']['text'] == 'Keep “Moonphase Four — Silver (MP4)”',
    'canonical_card_line27039': decision['verified_authoritative_user']['immediately_preceding_assistant']['line'] == 27039,
    'current_four_design_retained': node['catalogue_design_key'] == 'MOONPHASE-CURRENT-4' and p['catalogue_design_aliases'] == before['progress']['catalogue_design_aliases'],
    'exact_finish_name_kept': node['canonical_name'] == 'Moonphase Four — Silver (MP4)' and node['identity_confirmed'] and node['identity_decision_display'] == 'Owner kept this Silver finish name',
    'nine_current_finish_aliases': len(p['catalogue_alias_reviews']) == 9 and u['catalogue_alias_confirmation_counts']['Moonphases']['catalogue_finish_construction_aliases'] == 9,
    'eight_existing_finish_aliases_unchanged': all(p['catalogue_alias_reviews'][key] == value for key, value in before['progress']['catalogue_alias_reviews'].items()),
    'all_existing_component_reviews_unchanged': p['reviews'] == before['progress']['reviews'],
    'legacy_identity_counts_unchanged': u['identity_confirmation_counts'] == before['user']['identity_confirmation_counts'],
    'accepted_specification_counts_unchanged': u['specification_approval_counts'] == before['user']['specification_approval_counts'],
    'dimension_decisions_unchanged': u['dimension_decisions'] == before['user']['dimension_decisions'] and u['dimension_confirmation_counts'] == before['user']['dimension_confirmation_counts'],
    'component_counts_unchanged': cur['component']['counts'] == before['component']['counts'],
    'six_listing_claims_unapproved': len(node['specification_proposals']) == 6 and all(item['owner_approved'] is False and item['status'] == 'PUBLIC_LISTING_CLAIM;OWNER_UNAPPROVED;ACTUAL_SPECIMEN_APPLICABILITY_TO_CHECK' for item in node['specification_proposals']),
    'no_blanket_or_physical_spec_approval': not node['proposals_approved'] and not node['physical_specs_verified'],
    'listing30_size_and8kg_not_white_approval': '30' in node['specification_proposals'][0]['display'] and '7' in node['specification_proposals'][0]['display'] and '8 kg' in node['specification_proposals'][1]['display'],
    'exact_source001_file_and_folder_IDs': ref['file_id'] == 'id:cnqzTNngPVsAAAAAAAyfKA' and ref['folder_id'] == 'id:cnqzTNngPVsAAAAAAAyfJQ' and ref['file_path'].endswith('__001.jpg'),
    'historical_BC_MP1_MP5_retained': node['historical_component_ids'] == ['BC-MP-1', 'BC-MP-5'] and node['historical_physical_maker_code_unresolved'],
    'G243_current_four_and_historical_IDs': p['catalogue_group_overrides']['G243']['component_ids'] == ['BC-MP-1', 'BC-MP-5'] and 'MOONPHASE-CURRENT-4' in p['catalogue_group_overrides']['G243']['assignment_status'],
    'on_wall_context_only_scoped': node['photo_coverage']['on_wall'] and not node['photo_coverage']['wider_room'] and not node['photo_coverage']['rear'] and node['photo_coverage']['installation_provenance'] == 'UNCONFIRMED',
    'no_platform_upgrade': not node['existing_platform_match_confirmed'],
    'root_weight_question_unchanged': all(cp[key] == value for key, value in before['walkthrough'].items() if key.startswith('current_')) and cp['current_question_id'] == 'MCP4-VERDIGRIS-RUST-WEIGHT-01' and not cp['current_answer_recorded'],
    'owner_dimensions49_preserved': p['reviews']['BC-MCP-4']['size_finish_variants']['MCP4-VERDIGRIS-RUST']['owner_confirmed_dimensions_cm'] == {'height': 25, 'width': 25, 'depth': 6},
    'root_component_mirror_exact': cur['root']['current_component_review'] == cur['component'],
    'frozen_source_hashes_match': all(sha(ROOT / item['snapshot']) == item['sha256'] for item in read(HERE / 'source-manifest.json')['files']),
    'shared_saved_hashes_match': all(sha(paths[key]) == value for key, value in receipt['shared_after_sha256'].items()),
    'zero_private_original_downloads_and_remote_writes': receipt['summary']['root_new_private_original_downloads'] == receipt['summary']['remote_mutations'] == 0,
}
guards = {key: sha(path) for key, path in paths.items()}
repeat = subprocess.run(['python3', str(ROOT / 'components/reviews/import_moonphase_four_silver_50.py')], capture_output=True, text=True, check=True)
checks['idempotent_repeat_NO_WRITE'] = 'ALREADY_IMPORTED_IDEMPOTENT_NO_WRITE' in repeat.stdout and all(sha(paths[key]) == value for key, value in guards.items())
assert all(checks.values()), [key for key, value in checks.items() if not value]
out = {'status': 'PASS', 'checked_utc': datetime.now(timezone.utc).isoformat(), 'check_count': len(checks), 'checks': {key: 'PASS' for key in checks}, 'import_receipt_sha256': sha(HERE / 'import-receipt.json')}
(HERE / 'independent-readback.json').write_text(json.dumps(out, indent=2) + '\n')
event = {'event_id': decision['decision_id'], 'event': 'OWNER_KEPT_CURRENT_MOONPHASE_FOUR_SILVER_FINISH_NAME', 'batch': 50, 'specifications_approved': False, 'approval': decision['approval_record'], 'readback_sha256': sha(HERE / 'independent-readback.json')}
for path in [ROOT / 'components/reviews/identity_review_journal.jsonl', ROOT / 'review_journal.jsonl']:
    if not any(json.loads(line).get('event_id') == event['event_id'] for line in path.read_text().splitlines() if line.strip()):
        with path.open('a') as stream: stream.write(json.dumps(event) + '\n')
print(json.dumps({'batch': 50, 'status': 'PASS', 'checks': len(checks), 'readback_sha256': sha(HERE / 'independent-readback.json')}))
