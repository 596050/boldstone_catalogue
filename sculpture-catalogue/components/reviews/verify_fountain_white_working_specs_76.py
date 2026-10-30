"""Independent saved-state verification of one exact-finish working approval."""
import copy
import json
import subprocess
import sys
from datetime import datetime, timezone
from import_fountain_white_working_specs_76 import ROOT, HERE, PATHS, CID, VID, read, sha, write

old = read(HERE / 'before-import.json'); cur = {k: read(v) for k, v in PATHS.items()}; receipt = read(HERE / 'import-receipt.json'); decision = read(HERE / 'working-specification-approval.json')
u, p, cp, c = (cur[k] for k in ['user', 'progress', 'walkthrough', 'component']); node = p['reviews'][CID]; source = old['progress']['reviews'][CID]; accepted = node['accepted_working_specifications']; restored = copy.deepcopy(p['reviews']); restored[CID] = source
checks = {f'prior_user_{key}_preserved': u[key] == value for key, value in old['user'].items() if key not in ['updated_utc', 'size_finish_variant_specification_decisions', 'specification_approval_counts']}
checks.update({
 'one_new_exact_six_field_working_event': u['size_finish_variant_specification_decisions'][:-1] == old['user']['size_finish_variant_specification_decisions'] and u['size_finish_variant_specification_decisions'][-1]['decision_id'] == decision['decision_id'] and u['specification_approval_counts']['proposal_groups'] == c['interactive_review_state']['approved_proposal_groups'] == 130,
 'all_other_component_and_finish_scopes_preserved': restored == old['progress']['reviews'],
 'original_and_prepared_six_dicts_unchanged': node['specification_proposals'] == source['specification_proposals'] == decision['source_specification_proposals_retained'] and node['source_specifications_retained'] == decision['source_specifications_retained'],
 'six_fields_working_only': len(accepted) == 6 and all(x['owner_approved'] and x['owner_accepted'] and not x['physical_value_verified'] for x in accepted.values()) and not node['physical_specs_verified'] and not node['actual_stock_verified'] and node['fully_confirmed_specification_groups'] == [],
 'listing_dimensions_and_weight_source_conflict_retained': '100 × 50 × 6' in accepted['dimensions']['display'] and 'unmeasured' in accepted['dimensions']['display'] and '15 kg' in accepted['weight']['display'] and '16 kg' in accepted['weight']['display'] and not accepted['weight']['physical_weight_conflict_resolved'],
 'material_fixing_and_sale_policy_unknowns_retained': 'AC730 is a working hypothesis' in accepted['material_finish']['display'] and 'type,count,attachment and rated load unknown' in accepted['fixing']['display'] and 'stock,reproduction capacity and lead time unknown' in accepted['availability']['display'],
 '900_working_retail_distinct_from625_dated_trade': accepted['individual_price']['observed_public_retail_price_gbp'] == 900 and 'owner-accepted working retail price' in accepted['individual_price']['display'] and '625' in accepted['individual_price']['display'] and accepted['individual_price']['dated_trade_reference_is_not_current_retail'] and not accepted['individual_price']['current_live_Shopify_or_cast_offer_applicability_confirmed'],
 'active_working_statuses_no_stale_unapproved_labels': 'UNAPPROVED' not in accepted['fixing']['status'] and 'UNAPPROVED' not in accepted['availability']['status'] and 'UNAPPROVED' in source['specification_proposals'][3]['status'],
 'same_family_other_finish_scope_and_platform_mapping_unchanged': node['size_finish_variants'] == source['size_finish_variants'] and node['platform_mapping'] == source['platform_mapping'],
 'owner_binds_exact_last_nonblank_card': decision['authoritative_user_evidence']['line'] == 18706 and decision['verified_review_card_evidence']['line'] == 18688 and decision['authoritative_user_evidence']['immediately_preceding_assistant']['line'] == 18688,
 'outdoor_workshop_context_dated_coverage_not_authenticated_installation': node['photo_coverage']['contextual_source_status'] == 'Available: outdoor/workshop display; prior paired context retained' and not node['photo_coverage']['individual_wider_room_established'] and not node['photo_coverage']['rear_reference_established'] and 'dated18October' in node['photo_coverage']['contextual_source_description'] and 'propped on a bucket' in p['current_component_photograph_gaps'][VID]['room'] and p['current_component_photograph_gaps'][VID]['review_scope'] == 'BASE',
 'all_old_photo_gaps_preserved_one_new': {k:v for k,v in p['current_component_photograph_gaps'].items() if k != VID} == old['progress']['current_component_photograph_gaps'],
 'all_source_aliases_policies_and_pending_FFL_gap_preserved': all(p[k] == old['progress'][k] for k in ['duplicate_source_image_reviews','source_design_reviews','source_only_gap_reviews','catalogue_alias_reviews','group_photo_review_policy','physical_manufacture_review_policy']),
 'root_commercial_question_and_unknown_count_preserved': cp['current_question_id'] == 'MCP4-VERDIGRIS-RUST-PRICE-AVAILABILITY-01' and not cp['current_answer_recorded'] and not cp['current_fixing_count_answer_recorded'] and all(cp[k] == v for k,v in old['walkthrough'].items() if k.startswith('current_')),
 'physical_counts_and_allocations_preserved': c['counts'] == old['component']['counts'] and cp['parallel_working_specification_reviews'] == old['walkthrough']['parallel_working_specification_reviews'],
 'root_component_mirror_exact': cur['root']['current_component_review'] == c,
 'saved_shared_hashes_match': all(sha(PATHS[k]) == v for k,v in receipt['shared_after_sha256'].items()),
 'frozen_source_and_metadata_hashes_match': all(sha(ROOT/x['snapshot']) == x['sha256'] for x in read(HERE/'source-manifest.json')['files']),
 'workbook_and_immutable_sources_unchanged': all(sha(path) == v for path,v in receipt['protected_sha256'].items()),
 'no_private_downloads_or_remote_writes': receipt['summary']['root_new_private_original_downloads'] == receipt['summary']['remote_mutations'] == 0,
})
guards = {k:sha(v) for k,v in PATHS.items()}; repeat = subprocess.run([sys.executable,str(ROOT/'components/reviews/import_fountain_white_working_specs_76.py')],capture_output=True,text=True,check=True)
checks['idempotent_repeat_NO_WRITE'] = 'ALREADY_IMPORTED_IDEMPOTENT_NO_WRITE' in repeat.stdout and all(sha(PATHS[k]) == v for k,v in guards.items())
assert all(checks.values()),[k for k,v in checks.items() if not v]
write(HERE/'independent-readback.json',{'status':'PASS','checked_utc':datetime.now(timezone.utc).isoformat(),'check_count':len(checks),'checks':{k:'PASS' for k in checks},'import_receipt_sha256':sha(HERE/'import-receipt.json')})
event={'event_id':decision['decision_id'],'event':'EXACT_FOUNTAIN_EGYPTIAN_WHITE_SIX_WORKING_FIELDS_ACCEPTED_WITH_CONTEXT','batch':76,'new_accepted_field_groups':6,'new_physical_counts':0,'readback_sha256':sha(HERE/'independent-readback.json')}
for path in [ROOT/'components/reviews/identity_review_journal.jsonl',ROOT/'review_journal.jsonl']:
 if not any(json.loads(line).get('event_id')==event['event_id'] for line in path.read_text().splitlines() if line.strip()):
  with path.open('a') as stream:stream.write(json.dumps(event)+'\n')
print(json.dumps({'batch':76,'status':'PASS','checks':len(checks),'readback_sha256':sha(HERE/'independent-readback.json')}))
