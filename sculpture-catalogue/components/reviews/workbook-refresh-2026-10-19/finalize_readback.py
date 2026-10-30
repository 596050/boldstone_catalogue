"""Update current evidence pointers after a saved-and-visually-verified publication."""
import copy
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime,timezone
from pathlib import Path

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def write(path,value):
 temp=path.with_name(path.name+'.tmp');temp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');temp.replace(path)

batch=int(sys.argv[1]);p=read(ROOT/'components/reviews/specification_review_progress.json');cp=read(ROOT/'components/reviews/walkthrough_checkpoint.json');c=read(ROOT/'components/checkpoint.json');root=read(ROOT/'checkpoint.json');s=p['latest_workbook_export'];qa=read(HERE/'independent-file-verification.json');visual=read(HERE/'visual-qa.json');now=datetime.now(timezone.utc).isoformat()
assert s['included_owner_review_imports_through_batch']==batch and s['workbook_sha256']==sha(ROOT/s['workbook'])==qa['output_sha256']
assert qa['status']=='PASS' and qa['visual_verification']=='PASS' and visual['actual_model_inspection_complete']
assert s['validation_sha256']==sha(HERE/'independent-file-verification.json') and s['export_receipt_sha256']==sha(HERE/'export-receipt.json')
assert root['current_component_review']==c
assert all(p['reviews'][f'BC-MS-{i}']['size_finish_variants'][f'MS{i}-WHITE']['all_six_working_specification_fields_accepted'] for i in [1,2,3])
for path in [ROOT/'components/reviews/concave-to-mcp4-consolidation-2026-10-19/final-completion-readback.json',ROOT/'components/reviews/context-output-requirement-2026-10-19/current-workbook-readback.json']:
 value=read(path)
 if 'canonical_component_id' in value:value.update({'latest_workbook_after_subsequent_owner_imports':s,'latest_checked_utc':now,'current_main_question':cp['current_question_id']})
 else:value.update({'checked_utc':now,'workbook_sha256':s['workbook_sha256'],'included_import_batch':batch,'current_question':cp['current_question_id'],'answer_recorded':cp['current_answer_recorded'],'MS1_working_approval_batch':68,'MS2_working_approval_and_context_batch':71,'MS3_working_approval_and_context_batch':72,'Offset_Rough_duplicate_picture_evidence_batch':70})
 write(path,value)
path=ROOT/'components/reviews/pending-sealed-owner-imports-2026-10-19.json';queue=read(path)
for item in queue['imports']:
 if isinstance(item.get('import_batch'),int) and item['import_batch']<=batch:item.update({'status':'IMPORTED_AND_INCLUDED_IN_WORKBOOK','workbook_export_through_batch':batch,'workbook_sha256':s['workbook_sha256']})
queue['updated_utc']=now;write(path,queue)
for item in cp['parallel_working_specification_reviews']:
 parent=p['reviews'].get(item.get('component_id'),{})
 node={}
 if item.get('model_locator'):
  node=p
  for part in item['model_locator']:node=node[part]
 if not node:node=parent.get('size_finish_variants',{}).get(item.get('size_finish_variant_id'),{})
 if not node:node=parent.get('component_layouts',{}).get(item.get('size_finish_variant_id'),{})
 if not node and parent.get('size_finish_variant_id')==item.get('size_finish_variant_id'):node=parent
 if not node.get('all_six_working_specification_fields_accepted'):continue
 match=re.search(r'parallel-import-[^/]*-batch(\d+)/',node['specification_approval']);assert match
 approval_batch=int(match.group(1));assert approval_batch<=batch
 policy_derived=node.get('working_acceptance_basis')=='DERIVED_FROM_STANDING_OWNER_POLICY'
 item.update({'status':('STANDING_POLICY_SIX_WORKING_FIELDS_IMPORTED;NO_INDIVIDUAL_REPLY;ACTUAL_VALUES_PENDING' if policy_derived else 'OWNER_SIX_WORKING_FIELDS_IMPORTED;ACTUAL_VALUES_AND_SOURCE_CONFLICTS_PENDING'),'owner_answer_recorded':not policy_derived,'working_approval_import_batch':approval_batch,'import_receipt':f'components/reviews/parallel-import-2026-10-19-batch{approval_batch}/import-receipt.json','included_in_workbook_through_batch':batch})
 item['workbook_export_pending']=False
if batch>=97:
 for item in cp.get('next_reserved_policy_batches',[]):
  if item['batch']<=batch:item.update(status='IMPORTED_VERIFIED_AND_INCLUDED_IN_WORKBOOK97',workbook_export_through_batch=batch,workbook_sha256=s['workbook_sha256'])
 cp['all_remaining_working_review_state'].update(status='ALL_ALLOCATED_WORKING_REVIEWS_IMPORTED_VERIFIED_AND_INCLUDED_IN_WORKBOOK97',included_import_batch=batch,workbook=s['workbook'],workbook_sha256=s['workbook_sha256'])
 cp['pending_owner_weight_instruction_status']='POLICY90_AND_SUBSEQUENT_WORKING_VIEWS_INCLUDED_IN_WORKBOOK97'
 path=ROOT/cp['pending_owner_weight_instruction'];weight=read(path);weight.update(status='POLICY90_AND_SUBSEQUENT_WORKING_VIEWS_INCLUDED_IN_WORKBOOK97',workbook_export_through_batch=batch,workbook_sha256=s['workbook_sha256']);write(path,weight)
 c['next_reserved_policy_batches']=copy.deepcopy(cp['next_reserved_policy_batches']);c['all_remaining_working_review_state']=copy.deepcopy(cp['all_remaining_working_review_state']);c['pending_owner_weight_instruction_status']=cp['pending_owner_weight_instruction_status']
c['parallel_working_specification_reviews']=copy.deepcopy(cp['parallel_working_specification_reviews']);cp['updated_utc']=c['updated_utc']=root['updated_utc']=now;root['current_component_review']=copy.deepcopy(c)
for path,doc in [(ROOT/'components/reviews/walkthrough_checkpoint.json',cp),(ROOT/'components/checkpoint.json',c),(ROOT/'checkpoint.json',root)]:write(path,doc)
duplicate=p['duplicate_source_image_reviews']['PIXEL-IDENTICAL-G158022-G160001']
final={'status':'PASS_FINAL_SAVED_AND_VISUAL_READBACK','checked_utc':now,'included_import_batch':batch,'workbook_sha256':s['workbook_sha256'],'independent_checks':qa['check_count'],'affected_previews_inspected':len(visual['affected_previews']),'native_hyperlinks':s['native_hyperlinks'],'review_scope_rows':s['review_scope_rows'],'specification_entries':s['reviewed_specification_entries'],'accepted_working_field_groups':p['reviews'] and read(ROOT/'components/reviews/user_classifications.json')['specification_approval_counts']['proposal_groups'],'group_reference_records':s['group_reference_records'],'photo_gap_records':s['photograph_gap_records'],'three_Moonspiral_working_approvals_included':True,'weight_conflicts_retained':True,'exact_duplicate_picture_evidence_included':True,'duplicate_canonical_name_decision_pending':duplicate['canonical_name_decision_pending'],'root_current_question':cp['current_question_id'],'root_answer_recorded':cp['current_answer_recorded'],'final_individual_listing_count':None,'all_actual_specifications_complete':False,'pending_evidence_not_imported':[x['package'] for x in queue['imports'] if not x.get('import_batch')],'remote_mutations':0}
final['FountainWhite_current_owner_stated_weight_kg']=p['reviews'].get('BC-FOUNTAIN-EG',{}).get('owner_stated_weight_kg')
final['FountainWhite_outstanding_catalogue_weight_conflict']=p['reviews'].get('BC-FOUNTAIN-EG',{}).get('outstanding_catalogue_weight_conflict')
final['canonical_standing_working_policy_count']=len(read(ROOT/'components/reviews/user_classifications.json').get('working_specification_acceptance_policy_decisions',[]))
final['root_MCP4_price_and_availability_answer_recorded']=cp.get('current_price_answer_recorded') and cp.get('current_availability_answer_recorded')
final['root_MCP4_keyhole_count_still_unknown']=not cp.get('current_fixing_count_answer_recorded')
if batch>=87:
 final['global_fixing_choice_policy_events']=len(read(ROOT/'components/reviews/user_classifications.json').get('global_fixing_choice_policy_decisions',[]))
 final['offered_fixing_choices']=[x['label'] for x in p['global_fixing_choice_policy']['offered_fixing_options']]
 final['owner_keyhole_type_recorded_for_Embedded_and_Faceted']=all(p['reviews'][cid]['owner_confirmed_fixing_type']=='Keyhole fixing' for cid in ['BC-EMBED-SHELLS','BC-FACET-MOUND'])
if batch>=91:
 final['global_approximate_weight_policy_events']=len(read(ROOT/'components/reviews/user_classifications.json').get('global_approximate_weight_policy_decisions',[]))
 final['new_conditional_weight_estimates']=9
 final['recovered_existing_weight_displays']=7
 final['current_numeric_weight_bodies_retained']=214
 final['weight_reference_or_deferred_scope_dispositions']=48
 final['Chelsea_current_replacement_ID_resolved_by_prior_receipt_and_fresh_revision']=True
if batch>=97:
 final.update(remaining_working_review_scopes_completed=121,prior_six_field_display_recovery=1,allocated_remaining_scope_count=111,allocated_six_field_working_scopes=109,allocated_reference_dispositions=2,all_allocated_working_reviews_complete=True,additional_Azure_conditional_net_weight_estimates=1,Azure_shipping_weight_retained_separately=True,raw_source_proposals_and_historical_owner_statements_preserved=True)
write(HERE/f'final-readback-batch{batch}.json',final)
assert read(ROOT/'checkpoint.json')['current_component_review']==read(ROOT/'components/checkpoint.json')
digest=s['workbook_sha256'];history=HERE/'history'/digest;history.mkdir(exist_ok=True);snapshot=HERE/'published-snapshots'/(digest+'.xlsx.snapshot')
if snapshot.exists():assert sha(snapshot)==digest
else:shutil.copy2(ROOT/s['workbook'],snapshot)
for name in ['export-receipt.json','independent-file-verification.json','visual-qa.json','refresh-data.json','native-hyperlinks.json','checkpoint-publication-receipt.json',f'final-readback-batch{batch}.json',f'view-scope-readback-batch{batch}.json']:
 dest=history/name
 if dest.exists():assert dest.read_bytes()==(HERE/name).read_bytes()
 else:shutil.copy2(HERE/name,dest)
if batch==83:
 for name in ['model-preview-inspection-batch83.json','preview-inspection-pass1-batch83.json','pending-display-clarification-WhiteBlack-price-basis.json','Bronze-price-display-clarification.json']:
  shutil.copy2(HERE/name,history/name)
if batch==87:
 shutil.copy2(HERE/'model-preview-inspection-batch87.json',history/'model-preview-inspection-batch87.json')
if batch==91:
 for name in ['model-preview-inspection-batch91.json','preview-inspection-pass1-batch91.json','panel-front-display-clarification.json']:
  shutil.copy2(HERE/name,history/name)
if batch==97:
 for name in ['model-preview-inspection-batch97.json','preview-inspection-pass1-batch97.json','preview-plan-batch97.json']:
  shutil.copy2(HERE/name,history/name)
if not (history/'snapshot').exists():shutil.copytree(HERE/'snapshot',history/'snapshot')
print(json.dumps(final))
