"""Independently read back the exact Acanthus working approval and preserved context."""
import copy
import json
import subprocess
from datetime import datetime, timezone
from import_acanthus_gold_working_specs_64 import ROOT, HERE, PATHS, CID, VID, read, sha, write

old = read(HERE / 'before-import.json'); cur = {key: read(path) for key, path in PATHS.items()}; receipt = read(HERE / 'import-receipt.json'); decision = read(HERE / 'working-specification-approval.json')
u, p, cp = (cur[key] for key in ['user', 'progress', 'walkthrough']); node = p['reviews'][CID]['size_finish_variants'][VID]; prior = old['progress']['reviews'][CID]['size_finish_variants'][VID]
reviews = copy.deepcopy(p['reviews']); reviews[CID]['size_finish_variants'][VID] = copy.deepcopy(prior)
checks = {f'prior_user_{key}_unchanged': u[key] == value for key, value in old['user'].items() if key not in ['updated_utc', 'size_finish_variant_specification_decisions', 'specification_approval_counts']}
checks.update({
    'one_exact_working_specification_ledger_append': u['size_finish_variant_specification_decisions'] == old['user']['size_finish_variant_specification_decisions'] + [decision],
    'canonical_owner_and_latest_full_card': decision['authoritative_user_evidence']['line'] == 28058 and decision['verified_review_card_evidence']['line'] == 28051 and decision['user_statement'] == decision['authoritative_user_evidence']['text'] and decision['user_statement'].startswith('Keep these six working specifications for Acanthus and Moon — Gold Leaf'),
    'literal_question_mark_retained': decision['user_statement'].endswith('?'),
    'canonical_raw_digest_convention_explicit': all(item['source_raw_line_digest_includes_line_ending'] for item in read(HERE / 'source-manifest.json')['verified_messages']),
    'original_catalogue_six_dicts_unchanged': node['specification_proposals'] == prior['specification_proposals'] == decision['prior_catalogue_specifications_retained'],
    'presented_six_source_dicts_retained': decision['source_specifications_retained'] == read(decision['source_review_before_answer']['path'])['specifications'],
    'six_working_overlay_fields_accepted': len(node['accepted_working_specifications']) == 6 and all(item['owner_approved'] and not item['physical_value_verified'] for item in node['accepted_working_specifications'].values()) and node['proposals_approved'] and node['specifications_approved'],
    'five_source_displays_and_bases_retained': all(node['accepted_working_specifications'][field]['display'] == value['display'] and node['accepted_working_specifications'][field]['basis'] == value['basis'] for field, value in decision['source_specifications_retained'].items() if field != 'individual_price'),
    'accepted_working_price_display_resolved': node['accepted_working_specifications']['individual_price']['display'] == '£250 per panel — owner-accepted working price, sourced from listing.' and node['accepted_working_specifications']['individual_price']['status'] == 'PUBLIC_LISTING_PRICE_OWNER_ACCEPTED_AS_WORKING',
    'source_labels_unknowns_and_MTO_proposal_retained': all(text in node['accepted_working_specifications'][field]['display'] for field, text in [('dimensions', '50 × 30 × 6'), ('weight', 'Approximately 8 kg'), ('material_finish', 'exact leaf composition unconfirmed'), ('fixing', 'hardware and load rating unknown'), ('availability', 'Made to order — proposal; listing says in stock, actual stock and lead time unconfirmed')]),
    'six_unique_scoped_IDs': len(set(decision['approved_proposal_ids'])) == 6 and all(item.startswith(VID + ':') for item in decision['approved_proposal_ids']),
    'working_counts_only': u['specification_approval_counts']['proposal_groups'] == 94 and u['specification_approval_counts']['size_finish_variant_proposal_groups'] == 39 and u['specification_approval_counts']['size_finish_variant_approvals'] == 5,
    'physical_details_and_stock_not_verified': not node['physical_specs_verified'] and not node['actual_stock_verified'] and node['fully_confirmed_specification_groups'] == [] and not node['existing_platform_match_confirmed'],
    'prior_name_IDs_and_context_unchanged': all(node[key] == prior[key] for key in ['canonical_name', 'identity_confirmed', 'identity_approval', 'primary_image_id', 'primary_folder_id', 'current_dropbox_reference', 'root_verified_cached_original', 'photo_coverage', 'context_output_review', 'missing_photographs', 'platform_mapping']),
    'all_other_component_scopes_unchanged': reviews == old['progress']['reviews'],
    'all_aliases_source_groups_and_policies_unchanged': all(p[key] == old['progress'][key] for key in ['catalogue_alias_reviews', 'catalogue_design_aliases', 'source_design_reviews', 'asset_assignment_overrides', 'catalogue_group_overrides', 'group_photo_review_policy', 'physical_manufacture_review_policy']),
    'root_question_and_all_current_state_preserved': not cp['current_answer_recorded'] and cp['current_question_id'] == 'MCP4-VERDIGRIS-RUST-FIXING-COUNT-01' and all(cp[key] == value for key, value in old['walkthrough'].items() if key.startswith('current_')),
    'new_Moonspiral_allocation_preserved': cp['parallel_working_specification_reviews'] == old['walkthrough']['parallel_working_specification_reviews'],
    'physical_counts_unchanged': cur['component']['counts'] == old['component']['counts'] and cur['component']['interactive_review_state']['approved_proposal_groups'] == 94,
    'root_component_mirror_exact': cur['root']['current_component_review'] == cur['component'],
    'protected_sources_and_workbook_unchanged': all(sha(path) == value for path, value in receipt['protected_sha256'].items()),
    'frozen_sources_match': all(sha(ROOT / item['snapshot']) == item['sha256'] for item in read(HERE / 'source-manifest.json')['files']),
    'saved_shared_hashes_match': all(sha(PATHS[key]) == value for key, value in receipt['shared_after_sha256'].items()),
    'zero_downloads_or_remote_mutations': receipt['summary']['root_new_private_original_downloads'] == receipt['summary']['remote_mutations'] == 0,
})
guards = {key: sha(path) for key, path in PATHS.items()}
repeat = subprocess.run(['python3', str(ROOT / 'components/reviews/import_acanthus_gold_working_specs_64.py')], capture_output=True, text=True, check=True)
checks['idempotent_repeat_NO_WRITE'] = 'ALREADY_IMPORTED_IDEMPOTENT_NO_WRITE' in repeat.stdout and all(sha(PATHS[key]) == value for key, value in guards.items())
assert all(checks.values()), [key for key, value in checks.items() if not value]
write(HERE / 'independent-readback.json', {'status': 'PASS', 'checked_utc': datetime.now(timezone.utc).isoformat(), 'check_count': len(checks), 'checks': {key: 'PASS' for key in checks}, 'import_receipt_sha256': sha(HERE / 'import-receipt.json')})
event = {'event_id': decision['decision_id'], 'event': 'OWNER_KEPT_SIX_ACANTHUS_GOLD_WORKING_SPECIFICATIONS', 'batch': 64, 'actual_specs_verified': False, 'approval': decision['approval_record'], 'readback_sha256': sha(HERE / 'independent-readback.json')}
for path in [ROOT / 'components/reviews/identity_review_journal.jsonl', ROOT / 'review_journal.jsonl']:
    if not any(json.loads(line).get('event_id') == event['event_id'] for line in path.read_text().splitlines() if line.strip()):
        with path.open('a') as stream: stream.write(json.dumps(event) + '\n')
print(json.dumps({'batch': 64, 'status': 'PASS', 'checks': len(checks), 'readback_sha256': sha(HERE / 'independent-readback.json')}))
