"""Independent saved readback for Silver working acceptance and Acanthus context."""
import copy
import json
import subprocess
from datetime import datetime, timezone
from import_moonphase_silver_working_specs_62 import ROOT, HERE, PATHS, DESIGN, VARIANT, read, sha, write

old = read(HERE / 'before-import.json'); cur = {key: read(path) for key, path in PATHS.items()}; receipt = read(HERE / 'import-receipt.json'); decision = read(HERE / 'working-specification-approval.json')
u, p, cp = (cur[key] for key in ['user', 'progress', 'walkthrough']); node = p['catalogue_alias_reviews'][VARIANT]; prior = old['progress']['catalogue_alias_reviews'][VARIANT]
ac = p['reviews']['BC-AC-FULL']['size_finish_variants']['AC-FULL-GOLD-LEAF']; ac_prior = old['progress']['reviews']['BC-AC-FULL']['size_finish_variants']['AC-FULL-GOLD-LEAF']
reviews = copy.deepcopy(p['reviews']); reviews['BC-AC-FULL']['size_finish_variants']['AC-FULL-GOLD-LEAF'] = copy.deepcopy(ac_prior)
overrides = copy.deepcopy(p['asset_assignment_overrides']); overrides[node['primary_image_id']] = old['progress']['asset_assignment_overrides'][node['primary_image_id']]
groups = copy.deepcopy(p['catalogue_group_overrides']); groups['G243'] = old['progress']['catalogue_group_overrides']['G243']
checks = {f'prior_user_{key}_unchanged': u[key] == value for key, value in old['user'].items() if key not in ['updated_utc', 'size_finish_variant_specification_decisions', 'specification_approval_counts']}
checks.update({
    'one_exact_six_working_field_ledger_append': u['size_finish_variant_specification_decisions'] == old['user']['size_finish_variant_specification_decisions'] + [decision],
    'canonical_owner_and_card': decision['authoritative_user_evidence']['line'] == 27839 and decision['verified_review_card_evidence']['line'] == 27819 and decision['authoritative_user_evidence']['text'] == 'Keep these six working specifications for Moonphase Four — Silver (MP4)',
    'canonical_raw_digest_convention_explicit': all(item['source_raw_line_digest_includes_line_ending'] for item in read(HERE / 'source-manifest.json')['verified_messages']),
    'original_six_proposal_dicts_unchanged': node['specification_proposals'] == prior['specification_proposals'],
    'six_accepted_working_overlay_fields': len(node['accepted_working_specifications']) == 6 and all(item['owner_approved'] and not item['physical_value_verified'] for item in node['accepted_working_specifications'].values()) and node['proposals_approved'] and node['specifications_approved'],
    'working_price_owner_acceptance_current_display': node['accepted_working_specifications']['individual_price']['display'] == '£87.79 per panel — owner-accepted working price, sourced from listing.' and 'awaiting' not in node['accepted_working_specifications']['individual_price']['display'],
    'five_other_displays_retained': all(node['accepted_working_specifications'][field]['display'] == value['display'] for field, value in decision['source_specifications_retained'].items() if field != 'individual_price'),
    'six_unique_scoped_IDs': len(set(decision['approved_proposal_ids'])) == 6 and all(item.startswith(VARIANT + ':') for item in decision['approved_proposal_ids']),
    'accepted_working_counts_only': u['specification_approval_counts']['proposal_groups'] == 88 and u['specification_approval_counts']['size_finish_variant_proposal_groups'] == 33 and u['specification_approval_counts']['size_finish_variant_approvals'] == 4,
    'physical_details_and_stock_unverified': not node['physical_specs_verified'] and not node['actual_stock_verified'] and node['fully_confirmed_specification_groups'] == [] and not node['existing_platform_match_confirmed'],
    'Silver_name_lineage_reference_and_context_unchanged': all(node[key] == prior[key] for key in ['canonical_name', 'identity_confirmed', 'identity_approval', 'primary_image_id', 'primary_folder_id', 'historical_component_ids', 'historical_physical_maker_code_unresolved', 'current_dropbox_reference', 'photo_coverage', 'root_verified_cached_original', 'platform_mapping']),
    'all_other_aliases_unchanged': all(p['catalogue_alias_reviews'][key] == value for key, value in old['progress']['catalogue_alias_reviews'].items() if key != VARIANT),
    'Acanthus_only_two_context_fields_changed': all(ac[key] == value for key, value in ac_prior.items() if key not in ['photo_coverage', 'context_output_review']) and set(ac) - set(ac_prior) <= {'photo_coverage', 'context_output_review'},
    'Acanthus_specifications_unapproved_unchanged': ac['specification_proposals'] == ac_prior['specification_proposals'] and not ac['proposals_approved'],
    'Acanthus_room_context_link_bound': ac['photo_coverage']['wider_room'] and ac['photo_coverage']['on_wall'] and ac['photo_coverage']['contextual_file_ids'][0] == 'id:cnqzTNngPVsAAAAAAAyh2A' and ac['photo_coverage']['installation_provenance'] == 'UNCONFIRMED',
    'all_other_component_scopes_unchanged': reviews == old['progress']['reviews'],
    'only_Silver_asset_assignment_note_changed': overrides == old['progress']['asset_assignment_overrides'],
    'only_Silver_group_assignment_note_changed': groups == old['progress']['catalogue_group_overrides'],
    'source_groups_design_aliases_and_manufacture_unchanged': all(p[key] == old['progress'][key] for key in ['source_design_reviews', 'catalogue_design_aliases', 'physical_manufacture_review_policy', 'group_photo_review_policy']),
    'root_question_and_all_current_state_preserved': not cp['current_answer_recorded'] and cp['current_question_id'] == 'MCP4-VERDIGRIS-RUST-FIXING-COUNT-01' and all(cp[key] == value for key, value in old['walkthrough'].items() if key.startswith('current_')),
    'MCP4_Rust_all_values_unchanged': p['reviews']['BC-MCP-4'] == old['progress']['reviews']['BC-MCP-4'],
    'physical_counts_unchanged': cur['component']['counts'] == old['component']['counts'] and cur['component']['interactive_review_state']['approved_proposal_groups'] == 88,
    'root_component_mirror_exact': cur['root']['current_component_review'] == cur['component'],
    'saved_shared_hashes_match': all(sha(PATHS[key]) == value for key, value in receipt['shared_after_sha256'].items()),
    'protected_sources_and_workbook_unchanged': all(sha(path) == value for path, value in receipt['protected_sha256'].items()),
    'frozen_source_hashes_match': all(sha(ROOT / item['snapshot']) == item['sha256'] for item in read(HERE / 'source-manifest.json')['files']),
    'zero_downloads_and_remote_mutations': receipt['summary']['root_new_private_original_downloads'] == receipt['summary']['remote_mutations'] == 0,
})
guards = {key: sha(path) for key, path in PATHS.items()}
repeat = subprocess.run(['python3', str(ROOT / 'components/reviews/import_moonphase_silver_working_specs_62.py')], capture_output=True, text=True, check=True)
checks['idempotent_repeat_NO_WRITE'] = 'ALREADY_IMPORTED_IDEMPOTENT_NO_WRITE' in repeat.stdout and all(sha(PATHS[key]) == value for key, value in guards.items())
assert all(checks.values()), [key for key, value in checks.items() if not value]
write(HERE / 'independent-readback.json', {'status': 'PASS', 'checked_utc': datetime.now(timezone.utc).isoformat(), 'check_count': len(checks), 'checks': {key: 'PASS' for key in checks}, 'import_receipt_sha256': sha(HERE / 'import-receipt.json')})
event = {'event_id': decision['decision_id'], 'event': 'OWNER_KEPT_SIX_MOONPHASE_FOUR_SILVER_WORKING_SPECIFICATIONS', 'batch': 62, 'actual_specs_verified': False, 'approval': decision['approval_record'], 'separate_Acanthus_context_evidence_no_approval': True, 'readback_sha256': sha(HERE / 'independent-readback.json')}
for path in [ROOT / 'components/reviews/identity_review_journal.jsonl', ROOT / 'review_journal.jsonl']:
    if not any(json.loads(line).get('event_id') == event['event_id'] for line in path.read_text().splitlines() if line.strip()):
        with path.open('a') as stream: stream.write(json.dumps(event) + '\n')
print(json.dumps({'batch': 62, 'status': 'PASS', 'checks': len(checks), 'readback_sha256': sha(HERE / 'independent-readback.json')}))
