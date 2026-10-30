"""Independently verify finish-scoped working acceptance and bounded source gaps."""
import copy
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from import_acanthus_bronze_and_source_gap_74 import ROOT, HERE, PATHS, CID, VID, read, sha, write

old = read(HERE / 'before-import.json'); cur = {k: read(v) for k, v in PATHS.items()}; receipt = read(HERE / 'import-receipt.json')
u, p, cp, c = (cur[k] for k in ['user', 'progress', 'walkthrough', 'component']); node = p['reviews'][CID]['size_finish_variants'][VID]
decision = read(HERE / 'working-specification-approval.json'); accepted = node['accepted_working_specifications']; source = old['progress']['reviews'][CID]['size_finish_variants'][VID]
reviews = copy.deepcopy(p['reviews']); reviews[CID]['size_finish_variants'][VID] = source
checks = {f'prior_user_{key}_preserved': u[key] == value for key, value in old['user'].items() if key not in ['updated_utc', 'size_finish_variant_specification_decisions', 'specification_approval_counts']}
checks.update({
 'all_prior_spec_approvals_preserved_plus_exactly_one': u['size_finish_variant_specification_decisions'][:-1] == old['user']['size_finish_variant_specification_decisions'] and u['size_finish_variant_specification_decisions'][-1]['decision_id'] == decision['decision_id'],
 'six_new_working_fields_only': u['specification_approval_counts']['proposal_groups'] == 118 and c['interactive_review_state']['approved_proposal_groups'] == 118 and len(node['approved_proposal_ids']) == len(set(node['approved_proposal_ids'])) == len(accepted) == 6,
 'six_exact_fields_owner_accepted_not_physically_measured': all(x['owner_approved'] and x['owner_accepted'] and not x['physical_value_verified'] for x in accepted.values()) and not node['physical_specs_verified'] and not node['actual_stock_verified'] and node['fully_confirmed_specification_groups'] == [],
 'original_six_dictionaries_preserved': node['specification_proposals'] == source['specification_proposals'] == decision['source_specification_proposals_retained'],
 'prepared_source_snapshot_retained': node['source_specifications_retained'] == decision['source_specifications_retained'] and all(not x['owner_approved'] for x in node['source_specifications_retained'].values()),
 'working_price_current_acceptance_resolved_source_wording_retained': accepted['individual_price']['value_gbp'] == 77.79 and 'owner-accepted working proposal' in accepted['individual_price']['display'] and 'owner selling price unconfirmed' not in accepted['individual_price']['display'] and 'owner selling price unconfirmed' in node['source_specifications_retained']['individual_price']['display'],
 'dimensions_listing_claim_unmeasured': accepted['dimensions']['value_cm'] == [30, 30, 6] and 'unmeasured' in accepted['dimensions']['display'],
 'weight_guess_and_unknown_export_unit_retained': accepted['weight']['approximate_kg'] == 5 and accepted['weight']['range_kg'] == [4, 6] and 'no encoded unit' in accepted['weight']['basis'] and 'If pounds' in accepted['weight']['basis'],
 'finish_composition_hardware_cast_stock_and_lead_unknowns_retained': 'exact substrate unverified' in accepted['material_finish']['display'] and 'same cast as001 and load rating unconfirmed' in accepted['fixing']['display'] and 'stock and lead time unknown' in accepted['availability']['display'],
 'existing_bronze_platform_mapping_not_promoted': not node['existing_platform_match_confirmed'] and node['platform_mapping'] == source['platform_mapping'],
 'all_other_component_finish_scopes_unchanged': reviews == old['progress']['reviews'],
 'canonical_alias73_and_other_catalogue_scopes_preserved': all(p[k] == old['progress'][k] for k in ['source_design_reviews', 'duplicate_source_image_reviews', 'catalogue_alias_reviews', 'asset_assignment_overrides', 'catalogue_group_overrides', 'group_photo_review_policy', 'physical_manufacture_review_policy']),
 'one_owner_event_binds_last_nonblank_card': decision['authoritative_user_evidence']['line'] == 28701 and decision['verified_review_card_evidence']['line'] == 28639 and decision['authoritative_user_evidence']['immediately_preceding_assistant']['line'] == 28639,
 'bronze_context_six_view_scope_correct': node['photo_coverage']['on_wall'] and not node['photo_coverage']['individual_wider_room_established'] and not node['photo_coverage']['series_imagery_established'] and node['photo_coverage']['rear_reference_file_id'] == 'id:cnqzTNngPVsAAAAAAAygEw' and 'All6 direct-child' in node['photo_coverage']['contextual_source_description'],
 'rear_reference_not_promoted_to_cast_or_load_verification': not node['photo_coverage']['exact_physical_cast_identity_verified'] and 'rear006' in p['current_component_photograph_gaps'][VID]['missing'],
 'all_previous_photo_gaps_preserved_one_new_bronze': {k: v for k, v in p['current_component_photograph_gaps'].items() if k != VID} == old['progress']['current_component_photograph_gaps'],
 'FFL_source_size_documented_but_exact_mapping_unknown': p['source_only_gap_reviews']['BC-FFL-1']['historical_size_cm'] == [100, 22] and p['source_only_gap_reviews']['BC-FFL-1']['historical_depth_cm'] == [5, 7] and p['source_only_gap_reviews']['BC-FFL-1']['groups_checked'] == 7 and p['source_only_gap_reviews']['BC-FFL-1']['asset_metadata_checked'] == 96 and not p['source_only_gap_reviews']['BC-FFL-1']['mapping_confirmed'],
 'FFL_no_invented_IDs_or_absence_claim': p['source_only_gap_reviews']['BC-FFL-1']['stable_dropbox_file_id'] is None and p['source_only_gap_reviews']['BC-FFL-1']['stable_dropbox_folder_id'] is None and not p['source_only_gap_reviews']['BC-FFL-1']['absence_claimed'] and p['source_only_gap_reviews']['BC-FFL-1']['new_owner_decisions'] == 0,
 'root_current_question_and_unanswered_count_preserved': all(cp[k] == v for k, v in old['walkthrough'].items() if k.startswith('current_')) and cp['current_question_id'] == 'MCP4-VERDIGRIS-RUST-FIXING-COUNT-01' and not cp['current_answer_recorded'],
 'physical_counts_and_other_review_allocations_preserved': c['counts'] == old['component']['counts'] and cp['parallel_working_specification_reviews'] == old['walkthrough']['parallel_working_specification_reviews'],
 'root_component_mirror_exact': cur['root']['current_component_review'] == c,
 'shared_hashes_match': all(sha(PATHS[k]) == v for k, v in receipt['shared_after_sha256'].items()),
 'source_snapshots_and_current_metadata_hashes_match': all(sha(ROOT / x['snapshot']) == x['sha256'] for x in read(HERE / 'source-manifest.json')['files']),
 'protected_workbook_and_source_hashes_unchanged': all(sha(path) == v for path, v in receipt['protected_sha256'].items()),
 'no_private_downloads_or_remote_writes': receipt['summary']['root_new_private_original_downloads'] == receipt['summary']['remote_mutations'] == 0,
})
binding = read(ROOT / 'components/parallel-reviews/acanthus-two-leaves-bronze-working-specs-2026-10-20/CACHED_IMAGE_BINDING.json')
originals = []
for item in binding['sources']:
    if item['cache_kind'] != 'original': continue
    raw = __import__('pathlib').Path(item['cached_image']['path']).read_bytes()
    blocks = b''.join(hashlib.sha256(raw[i:i+4194304]).digest() for i in range(0, len(raw), 4194304))
    originals.append(hashlib.sha256(blocks).hexdigest() == item['baseline_original_dropbox_hash'] and hashlib.sha256(raw).hexdigest() == item['cached_image']['sha256'])
checks['independent_two_cached_original_content_hashes_match'] = len(originals) == 2 and all(originals)
guards = {k: sha(v) for k, v in PATHS.items()}
repeat = subprocess.run([sys.executable, str(ROOT / 'components/reviews/import_acanthus_bronze_and_source_gap_74.py')], capture_output=True, text=True, check=True)
checks['idempotent_repeat_NO_WRITE'] = 'ALREADY_IMPORTED_IDEMPOTENT_NO_WRITE' in repeat.stdout and all(sha(PATHS[k]) == v for k, v in guards.items())
assert all(checks.values()), [k for k, v in checks.items() if not v]
write(HERE / 'independent-readback.json', {'status': 'PASS', 'checked_utc': datetime.now(timezone.utc).isoformat(), 'check_count': len(checks), 'checks': {k: 'PASS' for k in checks}, 'import_receipt_sha256': sha(HERE / 'import-receipt.json')})
event = {'event_id': decision['decision_id'], 'event': 'EXACT_BRONZE_SIX_WORKING_FIELDS_ACCEPTED_WITH_CONTEXT_AND_BOUNDED_FFL_GAP', 'batch': 74, 'new_accepted_field_groups': 6, 'new_physical_counts': 0, 'readback_sha256': sha(HERE / 'independent-readback.json')}
for path in [ROOT / 'components/reviews/identity_review_journal.jsonl', ROOT / 'review_journal.jsonl']:
    if not any(json.loads(line).get('event_id') == event['event_id'] for line in path.read_text().splitlines() if line.strip()):
        with path.open('a') as stream: stream.write(json.dumps(event) + '\n')
print(json.dumps({'batch': 74, 'status': 'PASS', 'checks': len(checks), 'readback_sha256': sha(HERE / 'independent-readback.json')}))
