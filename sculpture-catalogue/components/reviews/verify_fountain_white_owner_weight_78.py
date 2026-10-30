"""Independently verify one scoped owner weight update without replaying approvals."""
import copy
import json
import subprocess
import sys
from datetime import datetime,timezone
from import_fountain_white_owner_weight_78 import ROOT,HERE,PATHS,CID,VID,read,sha,write

old=read(HERE/'before-import.json');cur={k:read(v) for k,v in PATHS.items()};receipt=read(HERE/'import-receipt.json');decision=read(HERE/'owner-weight.json');u,p,cp,c=(cur[k] for k in ['user','progress','walkthrough','component']);node=p['reviews'][CID];prior=old['progress']['reviews'][CID];current=node['accepted_working_specifications']['weight'];reviews=copy.deepcopy(p['reviews']);reviews[CID]=prior
checks={f'prior_user_{k}_preserved':u[k]==v for k,v in old['user'].items() if k not in ['updated_utc','weight_decisions','weight_confirmation_counts']}
checks.update({
 'one_new_owner_weight_event_no_six_field_replay':u['weight_decisions'][:-1]==old['user']['weight_decisions'] and u['weight_decisions'][-1]['decision_id']==decision['decision_id'] and len(u['weight_decisions'])==2 and u['weight_confirmation_counts']['individual_weight_decisions']==2 and u['weight_confirmation_counts']['components']==2,
 'working_specification_counts_unchanged136':u['specification_approval_counts']==old['user']['specification_approval_counts'] and u['specification_approval_counts']['proposal_groups']==c['interactive_review_state']['approved_proposal_groups']==136,
 'owner15kg_catalogue_selection_resolved':node['owner_stated_weight_kg']==current['owner_confirmed_weight_kg']==15 and not node['outstanding_catalogue_weight_conflict'] and not current['outstanding_catalogue_weight_conflict'] and node['owner_catalogue_weight_selection_resolves_source_conflict'],
 '16kg_retained_historical_not_current_choice':'earlier16 kg draft estimate retained as historical' in current['display'] and current['source_values']['draft_estimated_kg']==16 and current['source_values']['shopify_export_kg']==15 and 'no longer a pending catalogue weight choice' in node['scope'],
 'independent_weighing_not_inferred':not node['physical_specs_verified'] and not node['actual_weighing_independently_verified'] and node['actual_measured_weight_kg'] is None and not current['physical_value_verified'] and not current['actual_weighing_independently_verified'] and node['weight_measurement_method']=='UNCONFIRMED',
 'other_five_active_fields_exactly_unchanged':{k:v for k,v in node['accepted_working_specifications'].items() if k!='weight'}=={k:v for k,v in prior['accepted_working_specifications'].items() if k!='weight'},
 'all_original_and_prepared_source_dicts_preserved':node['specification_proposals']==prior['specification_proposals'] and node['source_specifications_retained']==prior['source_specifications_retained'],
 'prior_six_working_approval_and_original_receipt_unchanged':node['specification_approval']==prior['specification_approval'] and node['all_six_working_specification_fields_accepted'] and u['size_finish_variant_specification_decisions']==old['user']['size_finish_variant_specification_decisions'],
 'same_family_bronze_and_every_other_sculpture_unchanged':node['size_finish_variants']==prior['size_finish_variants'] and reviews==old['progress']['reviews'],
 'same_primary_context_platform_and_photo_gaps_unchanged':all(node[k]==prior[k] for k in ['primary_image_id','primary_folder_id','current_dropbox_reference','platform_mapping','photo_coverage','context_output_review']) and p['current_component_photograph_gaps']==old['progress']['current_component_photograph_gaps'],
 'owner_exact15kg_and_White_context_verified':decision['authoritative_user_evidence']['text']=='15 kg' and decision['authoritative_user_evidence']['line']==18751 and decision['authoritative_user_evidence']['immediately_preceding_assistant']['line']==18744 and 'Fountain Palm Egyptian — White' in decision['verified_assistant_context_evidence']['text'],
 'root_price_availability_and_unknown_keyhole_count_unchanged':all(cp[k]==v for k,v in old['walkthrough'].items() if k.startswith('current_')) and cp['current_question_id']=='MCP4-VERDIGRIS-RUST-PRICE-AVAILABILITY-01' and not cp['current_fixing_count_answer_recorded'],
 'all_physical_counts_and_policy_scopes_unchanged':c['counts']==old['component']['counts'] and all(p[k]==old['progress'][k] for k in ['physical_manufacture_review_policy','group_photo_review_policy','source_design_reviews','duplicate_source_image_reviews','source_only_gap_reviews','catalogue_alias_reviews']),
 'root_component_mirror_exact':cur['root']['current_component_review']==c,
 'saved_shared_hashes_match':all(sha(PATHS[k])==v for k,v in receipt['shared_after_sha256'].items()),
 'frozen_sources_match':all(sha(ROOT/x['snapshot'])==x['sha256'] for x in read(HERE/'source-manifest.json')['files']),
 'published_workbook_and_other_protected_sources_unchanged':all(sha(path)==v for path,v in receipt['protected_sha256'].items()),
 'no_new_downloads_or_remote_writes':receipt['summary']['root_new_private_original_downloads']==receipt['summary']['remote_mutations']==0,
})
guards={k:sha(v) for k,v in PATHS.items()};repeat=subprocess.run([sys.executable,str(ROOT/'components/reviews/import_fountain_white_owner_weight_78.py')],capture_output=True,text=True,check=True)
checks['idempotent_repeat_NO_WRITE']='ALREADY_IMPORTED_IDEMPOTENT_NO_WRITE' in repeat.stdout and all(sha(PATHS[k])==v for k,v in guards.items())
assert all(checks.values()),[k for k,v in checks.items() if not v]
write(HERE/'independent-readback.json',{'status':'PASS','checked_utc':datetime.now(timezone.utc).isoformat(),'check_count':len(checks),'checks':{k:'PASS' for k in checks},'import_receipt_sha256':sha(HERE/'import-receipt.json')})
event={'event_id':decision['decision_id'],'event':'EXACT_FOUNTAIN_WHITE_OWNER15KG_WEIGHT;16KG_HISTORICAL','batch':78,'new_six_field_approvals':0,'new_physical_counts':0,'readback_sha256':sha(HERE/'independent-readback.json')}
for path in [ROOT/'components/reviews/identity_review_journal.jsonl',ROOT/'review_journal.jsonl']:
 if not any(json.loads(line).get('event_id')==event['event_id'] for line in path.read_text().splitlines() if line.strip()):
  with path.open('a') as stream:stream.write(json.dumps(event)+'\n')
print(json.dumps({'batch':78,'status':'PASS','checks':len(checks),'readback_sha256':sha(HERE/'independent-readback.json')}))
