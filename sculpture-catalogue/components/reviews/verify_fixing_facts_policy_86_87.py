"""Independent readback: two fixing facts versus one global offered-choice policy."""
import copy,json,subprocess,sys
from datetime import datetime,timezone
from import_fixing_facts_policy_86_87 import ROOT,PATHS,target,read,sha,write
batch=int(sys.argv[1]);here=ROOT/f'components/reviews/parallel-import-2026-10-19-batch{batch}';old=read(here/'before-import.json');cur={k:read(v) for k,v in PATHS.items()};receipt=read(here/'import-receipt.json');u,p,cp,c=(cur[k] for k in ['user','progress','walkthrough','component']);checks={};restored=copy.deepcopy(p['reviews'])
checks.update({
 'working240_counts_no_new_six_field_acceptances':u['specification_approval_counts']==old['user']['specification_approval_counts'] and u['specification_approval_counts']['proposal_groups']==240 and u['size_finish_variant_specification_decisions']==old['user']['size_finish_variant_specification_decisions'] and receipt['summary']['new_accepted_working_proposal_groups']==0,
 'no_new_names_dimensions_weights_materials_or_stock_records':all(u[k]==v for k,v in old['user'].items() if k not in ['updated_utc','fixing_detail_decisions','global_fixing_choice_policy_decisions']),
 'all_current_root_answers_including_unanswered_count_preserved':all(cp[k]==v for k,v in old['walkthrough'].items() if k.startswith('current_')) and cp['current_answer_recorded'] and not cp['current_fixing_count_answer_recorded'],
 'all_photo_gaps_and_unresolved_sources_preserved':all(p[k]==old['progress'][k] for k in ['current_component_photograph_gaps','source_design_reviews','source_only_gap_reviews','duplicate_source_image_reviews']),
 'working_manufacture_and_group_policies_unchanged':all(p[k]==old['progress'][k] for k in ['working_specification_acceptance_policy','physical_manufacture_review_policy','group_photo_review_policy']),
 'physical_counts_unchanged':c['counts']==old['component']['counts'],
 'MCP4_175_unlimited_one_week_not_changed':p['reviews']['BC-MCP-4']==old['progress']['reviews']['BC-MCP-4'],
 'root_component_mirror_exact':cur['root']['current_component_review']==c,
 'exact_canonical_owner_messages_checked':[x['line'] for x in read(here/'source-manifest.json')['verified_messages']]==[29616,29734,29758,29769],
 'saved_shared_hashes_match':all(sha(PATHS[k])==v for k,v in receipt['shared_after_sha256'].items()),
 'all_frozen_sources_match':all(sha(ROOT/x['snapshot'])==x['sha256'] for x in read(here/'source-manifest.json')['files']),
 'protected_workbook_and_original_sources_unchanged':all(sha(path)==v for path,v in receipt['protected_sha256'].items()),
 'no_private_downloads_remote_writes_or_physical_counts':all(receipt['summary'][k]==0 for k in ['root_new_private_original_downloads','remote_mutations','new_physical_stock_or_mould_counts']),
})
if batch==86:
 checks['two_fixing_type_records_only']=len(u['fixing_detail_decisions'])==len(old['user']['fixing_detail_decisions'])+2 and u['fixing_detail_decisions'][:-2]==old['user']['fixing_detail_decisions'] and u.get('global_fixing_choice_policy_decisions')==old['user'].get('global_fixing_choice_policy_decisions')
 for cid,vid in [('BC-EMBED-SHELLS','EMBED-SHELLS-WHITE'),('BC-FACET-MOUND','FACET-MOUND-GOLD-LEAF')]:
  node,_=target(p,cid,vid);prior,_=target(old['progress'],cid,vid);r=restored[cid]['size_finish_variants'].get(vid) if vid in restored[cid].get('size_finish_variants',{}) else restored[cid];r.clear();r.update(copy.deepcopy(prior));a=node['accepted_working_specifications']['fixing'];d=read(ROOT/node['owner_fixing_type_decision'])
  checks[vid+'_owner_keyhole_type_count_and_load_unknown']=node['owner_confirmed_fixing_type']=='Keyhole fixing' and node['owner_fixing_point_count'] is None and a['number_of_fixing_points'] is None and a['hardware_material_positions_attachment_and_load_capacity'] is None and not a['physical_value_verified'] and not d['complete_fixing_group_approved']
  checks[vid+'_original_six_and_other_five_working_fields_preserved']=node['specification_proposals']==prior['specification_proposals'] and {k:v for k,v in node['accepted_working_specifications'].items() if k!='fixing'}=={k:v for k,v in prior['accepted_working_specifications'].items() if k!='fixing'} and a['source_accepted_working_fixing_before_owner_type']==prior['accepted_working_specifications']['fixing']
  checks[vid+'_same_actual_two_owner_inputs_not_fabricated_replies']=d['authoritative_user_evidence']['line']==29734 and d['scope_clarification_evidence']['line']==29758 and d['scope_clarification_evidence']['text']=='- Both sculptures' and d['verified_preceding_card']['line']==29616
 checks['all_other_sculpture_scopes_unchanged']=restored==old['progress']['reviews']
 checks['no_global_policy_event_imported86']=receipt['summary']['new_global_owner_policy_events']==0
else:
 policy=p['global_fixing_choice_policy'];checks['one_global_choice_policy_exactly_once']=len(u['global_fixing_choice_policy_decisions'])==1 and not old['user'].get('global_fixing_choice_policy_decisions') and policy['policy_id'].endswith('LINE29769') and policy['authoritative_user_evidence']['text']=='All sculptures should have a choice of keyhole fixing/french cleat'
 checks['two_offered_options_not_both_installed']=policy['choice_mode']=='CHOOSE_ONE_FOR_THE_SCULPTURE' and [x['label'] for x in policy['offered_fixing_options']]==['Keyhole fixing','French cleat'] and not policy['actual_installed_options_on_every_existing_cast_confirmed'] and not policy['both_types_simultaneously_fitted_to_every_sculpture_claimed']
 checks['no_counts_load_stock_or_measurements_certified']=not policy['fixing_count_hardware_material_position_attachment_and_load_rating_confirmed'] and not policy['physical_specifications_independently_verified'] and not policy['physical_manufacture_stock_and_lead_time_changed']
 checks['all_individual_installed_fixing_histories_unchanged']=p['reviews']==old['progress']['reviews'] and u['fixing_detail_decisions']==old['user']['fixing_detail_decisions']
 checks['all_policy_mirrors_equal']=policy==cp['global_fixing_choice_policy']==c['global_fixing_choice_policy']==u['global_fixing_choice_policy_decisions'][0]
 checks['no_repeat_options_question_and_unknown_count_still_unknown']=not cp['repeat_fixing_options_question_required'] and not c['repeat_fixing_options_question_required'] and not cp['current_fixing_count_answer_recorded']
guards={k:sha(v) for k,v in PATHS.items()};repeat=subprocess.run([sys.executable,str(ROOT/'components/reviews/import_fixing_facts_policy_86_87.py'),str(batch)],capture_output=True,text=True,check=True);checks['idempotent_repeat_NO_WRITE']='ALREADY_IMPORTED_IDEMPOTENT_NO_WRITE' in repeat.stdout and all(sha(PATHS[k])==v for k,v in guards.items());assert all(checks.values()),[k for k,v in checks.items() if not v]
write(here/'independent-readback.json',{'status':'PASS','checked_utc':datetime.now(timezone.utc).isoformat(),'check_count':len(checks),'checks':{k:'PASS' for k in checks},'import_receipt_sha256':sha(here/'import-receipt.json')})
for item in receipt['events']:
 event={'event_id':item['event_id'],'event':receipt['summary']['scope_kind'],'batch':batch,'new_six_field_acceptance_events':0,'new_physical_counts':0,'readback_sha256':sha(here/'independent-readback.json')}
 for path in [ROOT/'components/reviews/identity_review_journal.jsonl',ROOT/'review_journal.jsonl']:
  if not any(json.loads(line).get('event_id')==event['event_id'] for line in path.read_text().splitlines() if line.strip()):
   with path.open('a') as stream:stream.write(json.dumps(event)+'\n')
print(json.dumps({'batch':batch,'status':'PASS','checks':len(checks),'readback_sha256':sha(here/'independent-readback.json')}))
