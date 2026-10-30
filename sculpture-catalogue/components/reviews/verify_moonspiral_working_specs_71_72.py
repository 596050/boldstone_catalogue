"""Independently verify each working approval and bounded contextual-image import."""
import copy
import json
import subprocess
import sys
from datetime import datetime,timezone
from import_moonspiral_working_specs_71_72 import CONFIG,ROOT,PATHS,read,sha,write

batch=int(sys.argv[1]);cfg=CONFIG[batch];number=cfg['number'];cid,vid=f'BC-MS-{number}',f'MS{number}-WHITE';here=ROOT/f'components/reviews/parallel-import-2026-10-19-batch{batch}';old=read(here/'before-import.json');cur={key:read(path) for key,path in PATHS.items()};receipt=read(here/'import-receipt.json');decision=read(here/'working-specification-approval.json');u,p,cp=(cur[key] for key in ['user','progress','walkthrough']);node=p['reviews'][cid]['size_finish_variants'][vid];prior=old['progress']['reviews'][cid]['size_finish_variants'][vid];reviews=copy.deepcopy(p['reviews']);reviews[cid]['size_finish_variants'][vid]=prior;gaps=copy.deepcopy(p['current_component_photograph_gaps']);gap=gaps.pop(vid)
checks={f'prior_user_{key}_unchanged':u[key]==value for key,value in old['user'].items() if key not in ['updated_utc','size_finish_variant_specification_decisions','specification_approval_counts']}
checks.update({
 'one_exact_working_ledger_append':u['size_finish_variant_specification_decisions']==old['user']['size_finish_variant_specification_decisions']+[decision],
 'canonical_named_owner_and_full_card':decision['authoritative_user_evidence']['line']==cfg['owner'] and decision['verified_review_card_evidence']['line']==cfg['card'] and decision['authoritative_user_evidence']['text']==cfg['literal'],
 'canonical_raw_digest_convention_explicit':all(item['source_raw_line_digest_includes_line_ending'] for item in read(here/'source-manifest.json')['verified_messages']),
 'six_original_catalogue_proposals_unchanged':node['specification_proposals']==prior['specification_proposals']==decision['source_specification_proposals_retained'],
 'six_prepared_source_values_retained':decision['source_specifications_retained']==read(decision['source_review_before_answer']['path'])['specifications'],
 'six_working_overlay_fields_accepted':len(node['accepted_working_specifications'])==6 and node['proposals_approved'] and node['all_six_working_specification_fields_accepted'] and all(item['owner_approved'] and not item['physical_value_verified'] for item in node['accepted_working_specifications'].values()),
 'five_other_source_displays_retained':all(node['accepted_working_specifications'][field]['display']==value['display'] for field,value in decision['source_specifications_retained'].items() if field!='individual_price'),
 'historical_source_values_flags_immutable':all(node['accepted_working_specifications'][field].get('source_values')==value.get('source_values') for field,value in decision['source_specifications_retained'].items()),
 'weight_conflict_retained_no_actual_mass_selected':not node['physical_weight_conflict_resolved'] and all(text in node['accepted_working_specifications']['weight']['display'] for text in ['12–15 kg','20 kg']),
 'accepted_working_price_and_archived_conflicts_labelled':all(text in node['accepted_working_specifications']['individual_price']['display'] for text in ['£800' if number==2 else '£875','owner-accepted working proposal','646.71']) and not node['current_public_selling_price_verified'],
 'six_unique_scoped_IDs_and_one_working_count_increment':len(set(decision['approved_proposal_ids']))==6 and all(item.startswith(vid+':') for item in decision['approved_proposal_ids']) and u['specification_approval_counts']['proposal_groups']==cfg['count'] and u['specification_approval_counts']['size_finish_variant_approvals']==(7 if number==2 else 8),
 'physical_specs_stock_and_exact_platform_not_confirmed':not node['physical_specs_verified'] and not node['actual_stock_verified'] and node['fully_confirmed_specification_groups']==[] and node.get('existing_platform_match_confirmed') is not True,
 'prior_name_stable_IDs_platform_mapping_unchanged':all(node[key]==prior[key] for key in ['canonical_name','identity_confirmed','identity_approval','primary_image_id','primary_folder_id','current_dropbox_reference','platform_mapping']),
 'all_other_components_unchanged':reviews==old['progress']['reviews'],
 'all_aliases_source_groups_and_policies_unchanged':all(p[key]==old['progress'][key] for key in ['catalogue_alias_reviews','catalogue_design_aliases','source_design_reviews','asset_assignment_overrides','catalogue_group_overrides','group_photo_review_policy','physical_manufacture_review_policy','duplicate_source_image_reviews']),
 'exactly_one_new_scoped_photo_gap':gaps==old['progress']['current_component_photograph_gaps'] and gap['component_id']==cid and 'dedicated individual' in gap['missing'],
 'shared_context_not_individual_room_or_stock':node['photo_coverage']['contextual_file_ids'][0]==('id:cnqzTNngPVsAAAAAAAuc3w' if number==2 else 'id:cnqzTNngPVsAAAAAAA52SA') and not node['photo_coverage']['individual_wider_room_established'] and not node['photo_coverage']['exact_physical_cast_identity_verified'] and node['photo_coverage']['installation_provenance']=='UNCONFIRMED',
 'root_current_question_preserved':cp['current_question_id']=='MCP4-VERDIGRIS-RUST-FIXING-COUNT-01' and not cp['current_answer_recorded'] and all(cp[key]==value for key,value in old['walkthrough'].items() if key.startswith('current_')),
 'previous_owner_allocations_and_pending_alias_question_preserved':all(cp[key]==old['walkthrough'][key] for key in ['parallel_working_specification_reviews','parallel_source_reconciliation_reviews','pending_source_name_consolidations']),
 'physical_counts_unchanged':cur['component']['counts']==old['component']['counts'] and cur['component']['interactive_review_state']['approved_proposal_groups']==cfg['count'],
 'root_component_mirror_exact':cur['root']['current_component_review']==cur['component'],
 'frozen_source_hashes_match':all(sha(ROOT/item['snapshot'])==item['sha256'] for item in read(here/'source-manifest.json')['files']),
 'saved_shared_hashes_match':all(sha(PATHS[key])==value for key,value in receipt['shared_after_sha256'].items()),
 'protected_sources_and_workbook_unchanged':all(sha(path)==value for path,value in receipt['protected_sha256'].items()),
 'zero_downloads_or_remote_writes':receipt['summary']['root_new_private_original_downloads']==receipt['summary']['remote_mutations']==0,
})
if number==2:
 checks['short_Keep_is_one_corrob_event_not_second_approval']=len(decision['verified_corroborating_owner_evidence'])==1 and decision['verified_corroborating_owner_evidence'][0]['line']==28456 and len(u['size_finish_variant_specification_decisions'])==len(old['user']['size_finish_variant_specification_decisions'])+1
 checks['MS2_all_sources_thumbnail_only']=node['root_image_evidence_kind']=='THUMBNAILS_ONLY' and node['photo_coverage']['on_wall'] and node['photo_coverage']['family_wider_room_context']
 checks['MS2_SKU_conflict_not_resolved_by_working_acceptance']='MS-1-70.50' in json.dumps(decision['platform_mapping']) and 'O040' in node['scope']
else:
 checks['MS3_primary_bytes_verified_context_thumbnail_only']=node['root_image_evidence_kind']=='PRIMARY_CACHED_ORIGINAL_REHASHED;SHARED_CONTEXT_THUMBNAIL_ONLY' and node['photo_coverage']['contextual_source_status']=='Available: shared outdoor display context'
guards={key:sha(path) for key,path in PATHS.items()};repeat=subprocess.run(['python3',str(ROOT/'components/reviews/import_moonspiral_working_specs_71_72.py'),str(batch)],capture_output=True,text=True,check=True);checks['idempotent_repeat_NO_WRITE']='ALREADY_IMPORTED_IDEMPOTENT_NO_WRITE' in repeat.stdout and all(sha(PATHS[key])==value for key,value in guards.items())
assert all(checks.values()),[key for key,value in checks.items() if not value]
write(here/'independent-readback.json',{'status':'PASS','checked_utc':datetime.now(timezone.utc).isoformat(),'check_count':len(checks),'checks':{key:'PASS' for key in checks},'import_receipt_sha256':sha(here/'import-receipt.json')})
event={'event_id':decision['decision_id'],'event':f'OWNER_KEPT_SIX_MS{number}_WORKING_SPECIFICATIONS_WITH_CONFLICTS','batch':batch,'actual_specs_verified':False,'approval':decision['approval_record'],'readback_sha256':sha(here/'independent-readback.json')}
for path in [ROOT/'components/reviews/identity_review_journal.jsonl',ROOT/'review_journal.jsonl']:
 if not any(json.loads(line).get('event_id')==event['event_id'] for line in path.read_text().splitlines() if line.strip()):
  with path.open('a') as stream:stream.write(json.dumps(event)+'\n')
print(json.dumps({'batch':batch,'status':'PASS','checks':len(checks),'readback_sha256':sha(here/'independent-readback.json')}))
