"""Read saved finish records independently and verify unchanged owner scopes."""
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
batch = int(sys.argv[1]); assert batch in [31, 34, 36]
here = ROOT / f'components/reviews/parallel-import-2026-10-19-batch{batch}'
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
paths = {'user': ROOT / 'components/reviews/user_classifications.json', 'progress': ROOT / 'components/reviews/specification_review_progress.json',
         'walkthrough': ROOT / 'components/reviews/walkthrough_checkpoint.json', 'component': ROOT / 'components/checkpoint.json', 'root': ROOT / 'checkpoint.json'}
before, receipt, manifest = (read(here / name) for name in ['before-import.json', 'import-receipt.json', 'source-manifest.json'])
current = {k: read(p) for k, p in paths.items()}
cid, vid = receipt['summary']['component_id'], receipt['summary']['size_finish_variant_id']
parent, old_parent = current['progress']['reviews'][cid], before['progress']['reviews'][cid]
node = parent['size_finish_variants'][vid]
source = read(ROOT / node['source_review_snapshot'])
decision = current['user']['size_finish_variant_decisions'][-1]
checks = {f'previous_user_{k}_preserved': current['user'][k] == value for k, value in before['user'].items()
          if k not in ['updated_utc', 'size_finish_variant_decisions', 'identity_confirmation_counts']}
checks.update({
    'one_exact_finish_name_decision': current['user']['size_finish_variant_decisions'][:-1] == before['user']['size_finish_variant_decisions'] and len(current['user']['size_finish_variant_decisions']) == len(before['user']['size_finish_variant_decisions']) + 1,
    'exact_name_and_selected_source': node['canonical_name'] == decision['canonical_name'] and node['primary_image_id'] == decision['primary_file_id'] and node['primary_folder_id'] == decision['folder_id'],
    'identity_only_not_specs': node['identity_confirmed'] and not node['specifications_approved'] and not node['proposals_approved'] and not node['owner_estimates_accepted'] and not node['physical_specs_verified'],
    'six_source_groups_equal': len(node['specification_proposals']) == 6 and node['specification_proposals'] == source['specifications'] and node['specification_proposals'] == decision['source_specifications_retained'],
    'all_six_owner_approval_flags_false': all(v['owner_approved'] is False for v in node['specification_proposals'].values()),
    'prior_white_parent_fields_unchanged': {k: v for k, v in parent.items() if k != 'size_finish_variants'} == {k: v for k, v in old_parent.items() if k != 'size_finish_variants'},
    'prior_finish_nodes_unchanged': all(parent['size_finish_variants'][k] == v for k, v in old_parent.get('size_finish_variants', {}).items()),
    'all_other_component_reviews_unchanged': all(current['progress']['reviews'][k] == v for k, v in before['progress']['reviews'].items() if k != cid),
    'legacy_name_count_plus_one': current['user']['identity_confirmation_counts']['explicit_size_finish_variant_names'] == before['user']['identity_confirmation_counts']['explicit_size_finish_variant_names'] + 1,
    'same_component_scope_count': current['user']['identity_confirmation_counts']['components_with_any_identity_scope'] == before['user']['identity_confirmation_counts']['components_with_any_identity_scope'],
    'main_current_question_unchanged': all(current['walkthrough'][k] == v for k, v in before['walkthrough'].items() if k.startswith('current_')),
    'main_active_comparison_stays_pending': current['walkthrough']['current_question_id'] == before['walkthrough']['current_question_id'] and not current['walkthrough']['current_answer_recorded'],
    'canonical_consolidation_stays_answered': current['walkthrough']['current_identity_relationship_answer_recorded'] is True,
    'canonical_consolidation_unchanged': current['progress']['canonical_component_consolidations'] == before['progress']['canonical_component_consolidations'],
    'group_policy_and_G050_unchanged': current['walkthrough']['deferred_reviews'] == before['walkthrough']['deferred_reviews'] and current['progress']['group_photo_review_policy'] == before['progress']['group_photo_review_policy'],
    'source_design_reviews_unchanged': current['progress']['source_design_reviews'] == before['progress']['source_design_reviews'],
    'source_files_verified': all(sha(ROOT / x['snapshot']) == x['sha256'] and (ROOT / x['snapshot']).stat().st_size == x['bytes'] for x in manifest['files']),
    'protected_files_unchanged': all(sha(Path(path)) == digest for path, digest in receipt['protected_sha256'].items()),
    'saved_shared_hashes_match': all(sha(paths[k]) == digest for k, digest in receipt['shared_after_sha256'].items()),
    'root_component_mirror': current['root']['current_component_review'] == current['component'],
    'no_component_or_stock_count_change': current['component']['counts'] == before['component']['counts'] and receipt['summary']['new_registered_BC_component_ids'] == [],
    'no_manufacture_or_platform_upgrade': not node['owner_manufacture_confirmed'] and not node['existing_platform_match_confirmed'],
    'no_new_original_or_remote_write': receipt['summary']['root_new_private_original_downloads'] == receipt['summary']['remote_mutations'] == 0,
    'correct_owner_card_sequence': [x['line'] for x in manifest['verified_messages']] == ({31: [25905, 25938], 34: [26008, 26015], 36: [26100, 26129]}[batch]),
    'owner_literal_exact': manifest['verified_messages'][-1]['text'] == 'Keep “' + node['canonical_name'] + '”',
})
assert all(checks.values()), [k for k, v in checks.items() if not v]
out = {'status': 'PASS', 'checked_utc': datetime.now(timezone.utc).isoformat(), 'check_count': len(checks),
       'checks': {k: 'PASS' for k in checks}, 'idempotency_status': 'PASS_NO_WRITE', 'shared_after_sha256': receipt['shared_after_sha256']}
(here / 'independent-shared-readback.json').write_text(json.dumps(out, indent=2) + '\n')
event = {'event': 'verified_finish_name_followup', 'batch': batch, 'component_id': cid, 'size_finish_variant_id': vid,
         'new_name_approvals': 1, 'new_specification_approvals': 0, 'new_BC_ids': [], 'remote_mutations': 0}
for path in [ROOT / 'components/reviews/identity_review_journal.jsonl', ROOT / 'review_journal.jsonl']:
    with path.open('a') as stream: stream.write(json.dumps(event) + '\n')
print(json.dumps({'batch': batch, 'status': 'PASS', 'checks': len(checks), 'receipt_sha256': sha(here / 'import-receipt.json'), 'readback_sha256': sha(here / 'independent-shared-readback.json')}))
