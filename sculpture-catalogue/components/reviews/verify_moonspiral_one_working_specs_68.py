"""Independent saved readback of MS1 working acceptance and retained conflicts."""
import copy
import json
import subprocess
from datetime import datetime,timezone
from import_moonspiral_one_working_specs_68 import ROOT,HERE,PATHS,CID,VID,read,sha,write

old=read(HERE/'before-import.json');cur={key:read(path) for key,path in PATHS.items()};receipt=read(HERE/'import-receipt.json');decision=read(HERE/'working-specification-approval.json');u,p,cp=(cur[key] for key in ['user','progress','walkthrough']);node=p['reviews'][CID]['size_finish_variants'][VID];prior=old['progress']['reviews'][CID]['size_finish_variants'][VID]
reviews=copy.deepcopy(p['reviews']);reviews[CID]['size_finish_variants'][VID]=prior
checks={f'prior_user_{key}_unchanged':u[key]==value for key,value in old['user'].items() if key not in ['updated_utc','size_finish_variant_specification_decisions','specification_approval_counts']}
checks.update({
 'one_exact_working_ledger_append':u['size_finish_variant_specification_decisions']==old['user']['size_finish_variant_specification_decisions']+[decision],
 'canonical_owner_and_full_card':decision['authoritative_user_evidence']['line']==28329 and decision['verified_review_card_evidence']['line']==28295 and decision['authoritative_user_evidence']['text'].startswith('Keep these six working specifications for Moonspiral One — White (MS1)'),
 'canonical_raw_digest_convention_explicit':all(item['source_raw_line_digest_includes_line_ending'] for item in read(HERE/'source-manifest.json')['verified_messages']),
 'six_original_catalogue_proposals_unchanged':node['specification_proposals']==prior['specification_proposals']==decision['source_specification_proposals_retained'],
 'six_prepared_source_values_retained':decision['source_specifications_retained']==read(decision['source_review_before_answer']['path'])['specifications'],
 'six_working_overlay_fields_accepted':len(node['accepted_working_specifications'])==6 and node['proposals_approved'] and node['all_six_working_specification_fields_accepted'] and all(item['owner_approved'] and not item['physical_value_verified'] for item in node['accepted_working_specifications'].values()),
 'five_other_source_displays_unchanged':all(node['accepted_working_specifications'][field]['display']==value['display'] for field,value in decision['source_specifications_retained'].items() if field!='individual_price'),
 'all_historical_source_values_flags_unchanged':all(node['accepted_working_specifications'][field]['source_values']==value['source_values'] for field,value in decision['source_specifications_retained'].items()),
 'unresolved_weight_conflict_not_collapsed':not node['physical_weight_conflict_resolved'] and '12–15 kg' in node['accepted_working_specifications']['weight']['display'] and '20 kg' in node['accepted_working_specifications']['weight']['display'],
 '875_accepted_working_proposal_not_current_offer':all(text in node['accepted_working_specifications']['individual_price']['display'] for text in ['£875','owner-accepted working proposal','£646.71','Current selling offer unverified']) and not node['current_public_selling_price_verified'],
 'six_unique_scoped_IDs_and_working_count':len(set(decision['approved_proposal_ids']))==6 and all(item.startswith(VID+':') for item in decision['approved_proposal_ids']) and u['specification_approval_counts']['proposal_groups']==100 and u['specification_approval_counts']['size_finish_variant_proposal_groups']==45 and u['specification_approval_counts']['size_finish_variant_approvals']==6,
 'actual_specs_stock_and_material_unverified':not node['physical_specs_verified'] and not node['actual_stock_verified'] and node['fully_confirmed_specification_groups']==[] and node.get('existing_platform_match_confirmed') is not True and node['platform_mapping']['MS1_exact_current_offer_match']=='Unconfirmed',
 'prior_name_stable_IDs_and_thumbnail_context_unchanged':all(node[key]==prior[key] for key in ['canonical_name','identity_confirmed','identity_approval','primary_image_id','primary_folder_id','current_dropbox_reference','photo_coverage','context_output_review','missing_photographs','platform_mapping']),
 'all_other_components_and_scopes_unchanged':reviews==old['progress']['reviews'],
 'all_aliases_source_groups_policies_and_gaps_unchanged':all(p[key]==old['progress'][key] for key in ['catalogue_alias_reviews','catalogue_design_aliases','source_design_reviews','asset_assignment_overrides','catalogue_group_overrides','group_photo_review_policy','physical_manufacture_review_policy','current_component_photograph_gaps']),
 'no_context_or_manufacture_replay':receipt['summary']['context_evidence_reimported'] is False and u['manufacture_policy_decisions']==old['user']['manufacture_policy_decisions'],
 'root_current_question_preserved':cp['current_question_id']=='MCP4-VERDIGRIS-RUST-FIXING-COUNT-01' and not cp['current_answer_recorded'] and all(cp[key]==value for key,value in old['walkthrough'].items() if key.startswith('current_')),
 'existing_allocations_unchanged':all(cp[key]==old['walkthrough'][key] for key in ['parallel_working_specification_reviews','parallel_source_reconciliation_reviews']),
 'physical_counts_unchanged':cur['component']['counts']==old['component']['counts'] and cur['component']['interactive_review_state']['approved_proposal_groups']==100,
 'root_component_mirror_exact':cur['root']['current_component_review']==cur['component'],
 'frozen_source_hashes_match':all(sha(ROOT/item['snapshot'])==item['sha256'] for item in read(HERE/'source-manifest.json')['files']),
 'saved_shared_hashes_match':all(sha(PATHS[key])==value for key,value in receipt['shared_after_sha256'].items()),
 'protected_sources_and_workbook_unchanged':all(sha(path)==value for path,value in receipt['protected_sha256'].items()),
 'no_downloads_or_remote_mutations':receipt['summary']['root_new_private_original_downloads']==receipt['summary']['remote_mutations']==0,
})
guards={key:sha(path) for key,path in PATHS.items()};repeat=subprocess.run(['python3',str(ROOT/'components/reviews/import_moonspiral_one_working_specs_68.py')],capture_output=True,text=True,check=True);checks['idempotent_repeat_NO_WRITE']='ALREADY_IMPORTED_IDEMPOTENT_NO_WRITE' in repeat.stdout and all(sha(PATHS[key])==value for key,value in guards.items())
assert all(checks.values()),[key for key,value in checks.items() if not value]
write(HERE/'independent-readback.json',{'status':'PASS','checked_utc':datetime.now(timezone.utc).isoformat(),'check_count':len(checks),'checks':{key:'PASS' for key in checks},'import_receipt_sha256':sha(HERE/'import-receipt.json')})
event={'event_id':decision['decision_id'],'event':'OWNER_KEPT_SIX_MS1_WORKING_SPECIFICATIONS_WITH_CONFLICTS','batch':68,'actual_specs_verified':False,'approval':decision['approval_record'],'readback_sha256':sha(HERE/'independent-readback.json')}
for path in [ROOT/'components/reviews/identity_review_journal.jsonl',ROOT/'review_journal.jsonl']:
 if not any(json.loads(line).get('event_id')==event['event_id'] for line in path.read_text().splitlines() if line.strip()):
  with path.open('a') as stream:stream.write(json.dumps(event)+'\n')
print(json.dumps({'batch':68,'status':'PASS','checks':len(checks),'readback_sha256':sha(HERE/'independent-readback.json')}))
