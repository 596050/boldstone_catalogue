"""Audit the saved Gold finish, parent identity, and unchanged review scopes."""
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BATCH = int(sys.argv[1]) if len(sys.argv) > 1 else 38
CID, VID, NAME, FID, FOLDER_ID, LINES = {
    38: ('BC-BR-1', 'BR-1-GOLD-LEAF', 'Brancusi 1 — Gold Leaf', 'id:cnqzTNngPVsAAAAAAAyjwQ', 'id:cnqzTNngPVsAAAAAAAyjbA', [26266, 26306]),
    40: ('BC-BR-2', 'BR-2-GOLD-LEAF', 'Brancusi 2 — Gold Leaf', 'id:cnqzTNngPVsAAAAAAAyjvw', 'id:cnqzTNngPVsAAAAAAAyjbw', [26367, 26391]),
}[BATCH]
HERE = ROOT / f'components/reviews/parallel-import-2026-10-19-batch{BATCH}'
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
paths = {'user': ROOT / 'components/reviews/user_classifications.json', 'progress': ROOT / 'components/reviews/specification_review_progress.json',
         'walkthrough': ROOT / 'components/reviews/walkthrough_checkpoint.json', 'component': ROOT / 'components/checkpoint.json', 'root': ROOT / 'checkpoint.json'}
old, receipt, manifest = (read(HERE / name) for name in ['before-import.json', 'import-receipt.json', 'source-manifest.json'])
cur = {k: read(v) for k, v in paths.items()}
parent = cur['progress']['reviews'][CID]; node = parent['size_finish_variants'][VID]
source = read(ROOT / node['source_review_snapshot']); prior = next(x for x in old['user']['decisions'] if x.get('component_id') == CID)
model = read(ROOT / 'components/evidence/component_register.json'); heads = read(HERE / 'current-reference-check.json')['metadata']
asset = next(x for x in model['assets'] if x['id'] == prior['evidence_file_id'])
head = next(x['file'] for x in heads if x.get('file', {}).get('id') == prior['evidence_file_id'])
source_path = '/' + asset['path'].split('//', 1)[1].lstrip('/') if asset['path'].startswith('ns:') else asset['path']
checks = {f'previous_user_{k}_unchanged': cur['user'][k] == v for k, v in old['user'].items() if k not in ['updated_utc', 'identity_confirmation_counts', 'size_finish_variant_decisions']}
checks.update({
    'one_new_scoped_finish_decision': cur['user']['size_finish_variant_decisions'][:-1] == old['user']['size_finish_variant_decisions'] and len(cur['user']['size_finish_variant_decisions']) == len(old['user']['size_finish_variant_decisions']) + 1,
    'existing_parent_identity_reflects_legacy_keep': parent['identity_confirmed'] and parent['canonical_name'] == prior['proposed_name_at_review'] and parent['primary_image_id'] == prior['evidence_file_id'],
    'parent_keeps_no_specification_approval': not parent['proposals_approved'] and parent['specification_proposals'] == [],
    'legacy_White_metadata_source_path_current': source_path == head['path_display'] and parent['primary_folder_id'] == prior['containing_folder_id'],
    'Gold_name_exact': node['canonical_name'] == NAME and node['identity_confirmed'],
    'Gold_six_proposals_unchanged': len(node['specification_proposals']) == 6 and node['specification_proposals'] == source['specifications'],
    'Gold_all_proposals_unaccepted': not node['proposals_approved'] and not node['specifications_approved'] and not node['owner_estimates_accepted'] and all(x['owner_approved'] is False for x in node['specification_proposals'].values()),
    'Gold_price325_not_an_observed_offer': node['specification_proposals']['individual_price']['value_gbp'] == 325 and node['specification_proposals']['individual_price']['status'] == 'NEW_DISCUSSION_PROPOSAL_NOT_CURRENT_OFFER',
    'Gold_single_panel_dimensions_and_weight_only': node['specification_proposals']['dimensions']['face_cm'] == [50, 25] and node['specification_proposals']['weight']['range_kg'] == [6, 8],
    'Gold_cached_thumbnail_only_limit': not node['root_verified_cached_thumbnail']['is_original_byte_hash'] and not node['root_verified_cached_thumbnail']['original_bytes_verified'],
    'Gold_exact_selected_ID_and_parent': node['primary_image_id'] == FID and node['primary_folder_id'] == FOLDER_ID,
    'Gold_no_platform_or_manufacture_upgrade': not node['existing_platform_match_confirmed'] and not node['owner_manufacture_confirmed'] and node['source_offer_refs'] == [] and node['related_offer_refs'] == ['O029'],
    'all_other_component_reviews_unchanged': all(cur['progress']['reviews'][k] == v for k, v in old['progress']['reviews'].items()),
    'source_design_reviews_unchanged': cur['progress']['source_design_reviews'] == old['progress']['source_design_reviews'],
    'finish_scope_count_plus_one': cur['user']['identity_confirmation_counts']['explicit_size_finish_variant_names'] == old['user']['identity_confirmation_counts']['explicit_size_finish_variant_names'] + 1,
    'component_scope_count_unchanged': cur['user']['identity_confirmation_counts']['components_with_any_identity_scope'] == old['user']['identity_confirmation_counts']['components_with_any_identity_scope'],
    'main_current_review_fields_unchanged': all(cur['walkthrough'][k] == v for k, v in old['walkthrough'].items() if k.startswith('current_')),
    'main_Verdigris_question_pending': not cur['walkthrough']['current_answer_recorded'] and cur['walkthrough']['current_question_id'] == 'MCP4-NATIVE-VS-FORMER-CONCAVE-VERDIGRIS-FINISH-EQUIVALENCE-01',
    'MCP4_Silver_alias_preserved': cur['progress']['canonical_variant_aliases'] == old['progress']['canonical_variant_aliases'],
    'group_policy_G050_preserved': cur['walkthrough']['deferred_reviews'] == old['walkthrough']['deferred_reviews'] and cur['progress']['group_photo_review_policy'] == old['progress']['group_photo_review_policy'],
    'root_component_mirror': cur['root']['current_component_review'] == cur['component'],
    'legacy_counts_unchanged': cur['component']['counts'] == old['component']['counts'],
    'protected_files_unchanged': all(sha(Path(k)) == v for k, v in receipt['protected_sha256'].items()),
    'frozen_reference_hashes_and_sizes': all(sha(ROOT / x['snapshot']) == x['sha256'] and (ROOT / x['snapshot']).stat().st_size == x['bytes'] for x in manifest['files']),
    'shared_hashes_match_after_NO_WRITE': all(sha(paths[k]) == v for k, v in receipt['shared_after_sha256'].items()),
    'owner_and_card_lines_exact': [x['line'] for x in manifest['verified_messages']] == LINES,
    'no_new_original_or_remote_mutation': receipt['summary']['root_new_private_original_downloads'] == receipt['summary']['remote_mutations'] == 0,
})
assert all(checks.values()), [k for k, v in checks.items() if not v]
report = {'status': 'PASS', 'checked_utc': datetime.now(timezone.utc).isoformat(), 'check_count': len(checks), 'checks': {k: 'PASS' for k in checks}, 'idempotency_status': 'PASS_NO_WRITE', 'shared_after_sha256': receipt['shared_after_sha256']}
(HERE / 'independent-shared-readback.json').write_text(json.dumps(report, indent=2) + '\n')
event = {'event': 'verified_Brancusi_selected_finish_name', 'batch': BATCH, 'component_id': CID, 'size_finish_variant_id': VID, 'new_specification_approvals': 0, 'new_BC_ids': [], 'remote_mutations': 0}
for path in [ROOT / 'components/reviews/identity_review_journal.jsonl', ROOT / 'review_journal.jsonl']:
    with path.open('a') as stream: stream.write(json.dumps(event) + '\n')
print(json.dumps({'batch': BATCH, 'status': 'PASS', 'checks': len(checks), 'receipt_sha256': sha(HERE / 'import-receipt.json'), 'readback_sha256': sha(HERE / 'independent-shared-readback.json')}))
