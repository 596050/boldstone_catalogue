"""Import two owner fixing-type facts and one distinct catalogue-choice policy."""
import copy,json,sys
from datetime import datetime,timezone
from pathlib import Path
from import_moonphase_silver_working_specs_62 import ROOT,PATHS,read,sha,rel,write,specification_counts
from import_leaf_policy_working_82_83 import target
from import_source_followups_24_25 import canonical_messages
SOURCE=ROOT/'components/parallel-reviews/embedded-shells-faceted-mound-working-specs-2026-10-20/owner-fixing-correction-and-options-2026-10-20'
PACKAGE_SHA='bcbe8bc226f5624ff210204b3b65b2d9d4d883b4554c1193e74285a1451e9298'

def main(batch):
 assert batch in [86,87];here=ROOT/f'components/reviews/parallel-import-2026-10-19-batch{batch}';docs={k:read(v) for k,v in PATHS.items()}
 if (here/'import-receipt.json').exists():
  if batch==86:assert all(target(docs['progress'],x['component_id'],x['variant'])[0]['owner_confirmed_fixing_type']=='Keyhole fixing' for x in read(SOURCE/'IMPORT_PACKAGE.json')['two_owner_fixing_type_corrections'])
  else:assert len(docs['user']['global_fixing_choice_policy_decisions'])==1
  print(json.dumps({'batch':batch,'status':'ALREADY_IMPORTED_IDEMPOTENT_NO_WRITE'}));return
 before=copy.deepcopy(docs);guards={k:sha(v) for k,v in PATHS.items()};files=[];seen=set()
 def freeze(path,digest):
  path=Path(path);assert sha(path)==digest,str(path)
  if str(path) in seen:return
  seen.add(str(path));dest=here/'sources'/(digest+path.suffix);dest.parent.mkdir(parents=True,exist_ok=True)
  if dest.exists():assert sha(dest)==digest
  else:dest.write_bytes(path.read_bytes())
  files.append({'source':str(path),'snapshot':rel(dest),'sha256':digest})
  if path.is_relative_to(SOURCE) and path.suffix=='.json':refs(read(path))
 def refs(x):
  if isinstance(x,dict):
   if 'path' in x and 'sha256' in x:freeze(x['path'],x['sha256'])
   for v in x.values():refs(v)
  elif isinstance(x,list):
   for v in x:refs(v)
 package=SOURCE/'IMPORT_PACKAGE.json';freeze(package,PACKAGE_SHA);pkg=read(package);e=read(pkg['owner_evidence']['path']);messages=canonical_messages([e[k]|{'transcript':e[k]['transcript_path']} for k in ['preceding_nonblank_review_card','fixing_statement','both_sculptures_clarification','global_fixing_choice_instruction']],pkg['source_owner_session']);assert [x['line'] for x in messages]==[29616,29734,29758,29769] and all(x['immediately_preceding_assistant']['line']==29616 for x in messages[1:]);assert messages[1]['text']=='It has:\nkey hole fixing' and messages[2]['text']=='- Both sculptures' and messages[3]['text']=='All sculptures should have a choice of keyhole fixing/french cleat'
 u,p,cp,c=(docs[k] for k in ['user','progress','walkthrough','component']);assert docs['root']['current_component_review']==c and cp['last_parallel_import']['batch']==batch-1 and u['specification_approval_counts']['proposal_groups']==240
 protected={str(path):sha(path) for path in [ROOT/cp['register_workbook'],ROOT/cp['current_review_record'],ROOT/'components/evidence/component_register.json',ROOT.parent/'Boldstone_Wall_Sculptures_Matched_All_Fields_2026-10-15.xlsx']};now=datetime.now(timezone.utc).isoformat();events=[]
 if batch==86:
  for item in pkg['two_owner_fixing_type_corrections']:
   d=read(item['decision']['path']);cid,vid=d['component_id'],d['size_finish_variant_id'];node,_=target(p,cid,vid);assert node['all_six_working_specification_fields_accepted'] and node['identity_confirmed'] and node['primary_image_id']==d['primary_file_id'] and node['primary_folder_id']==d['primary_folder_id'];assert d['number_of_fixing_points'] is None and d['confirmed_fixing_type']=='Keyhole fixing' and not d['complete_fixing_group_approved'] and not d['physical_specs_verified'];assert not any(x.get('decision_id')==d['decision_id'] for x in u.get('fixing_detail_decisions',[]))
   approval=rel(here/(vid+'-owner-fixing-type.json'));d.update({'approval_record':approval,'root_imported_utc':now,'authoritative_user_evidence':messages[1],'scope_clarification_evidence':messages[2],'verified_preceding_card':messages[0],'new_six_field_acceptance_events':0});u.setdefault('fixing_detail_decisions',[]).append(d)
   old=copy.deepcopy(node['accepted_working_specifications']['fixing']);active=copy.deepcopy(old);active.update({'display':'Keyhole fixing — owner-stated type; number, hardware, attachment and load capacity unconfirmed','status':'OWNER_STATED_KEYHOLE_TYPE;COUNT_HARDWARE_ATTACHMENT_AND_LOAD_UNCONFIRMED','basis':'Owner wrote key hole fixing and then explicitly applied it to both reviewed sculptures. This confirms type only; counts, hardware composition, position, attachment and load rating remain unknown. Offered keyhole/French-cleat choices are a separate global catalogue instruction.','owner_approved':True,'owner_accepted':True,'physical_value_verified':False,'owner_stated_type':'Keyhole fixing','number_of_fixing_points':None,'hardware_material_positions_attachment_and_load_capacity':None,'source_accepted_working_fixing_before_owner_type':old,'owner_type_record':approval});node['accepted_working_specifications']['fixing']=active;node.update({'owner_confirmed_fixing_type':'Keyhole fixing','owner_fixing_point_count':None,'owner_fixing_type_decision':approval,'physical_specs_verified':False,'actual_stock_verified':False,'specification_status_display':'Six working specifications accepted; keyhole type owner-stated; counts, attachment and load unknown'})
   node['scope']+=' Owner subsequently confirmed keyhole fixing for this sculpture; actual counts, hardware and load rating remain unknown.';p['pending_specification_checks'][vid+'-WORKING-SPECS-01'].update({'owner_fixing_type_answer_recorded':True,'owner_fixing_type_record':approval,'actual_fixing_count_and_load_unknown':True});write(ROOT/approval,d);events.append({'event_id':d['decision_id'],'component_id':cid,'size_finish_variant_id':vid,'approval_record':approval})
  scope_kind='TWO_OWNER_KEYHOLE_FIXING_TYPE_FACTS_ONLY';newfacts=2;newpolicy=0
 else:
  policy=read(pkg['global_policy']['path']);assert sha(pkg['global_policy']['path'])=='3a5d5f8c2e86417a5d1aea0b6d055564b34e7c43b5f7860a5a9c2cd62057fc76';assert not u.get('global_fixing_choice_policy_decisions') and policy['offered_fixing_options']==[{'code':'KEYHOLE','label':'Keyhole fixing'},{'code':'FRENCH_CLEAT','label':'French cleat'}] and not policy['actual_installed_options_on_every_existing_cast_confirmed'] and not policy['physical_specifications_independently_verified']
  policy.update({'approval_record':rel(here/'global-fixing-choice-policy.json'),'authoritative_user_evidence':messages[3],'verified_context_card':messages[0],'root_imported_utc':now,'canonical_policy_event':True,'shared_master_import_performed':True});u['global_fixing_choice_policy_decisions']=[policy]
  for doc in [p,cp,c]:doc['global_fixing_choice_policy']=copy.deepcopy(policy)
  cp['repeat_fixing_options_question_required']=False;c['repeat_fixing_options_question_required']=False;write(here/'global-fixing-choice-policy.json',policy);events=[{'event_id':policy['policy_id'],'approval_record':policy['approval_record']}];scope_kind='SINGLE_GLOBAL_OFFERED_FIXING_CHOICE_POLICY;INSTALLED_HARDWARE_HISTORY_UNCHANGED';newfacts=0;newpolicy=1
 assert specification_counts(u)==before['user']['specification_approval_counts'];summary={'batch':batch,'recorded_utc':now,'receipt':rel(here/'import-receipt.json'),'scope_kind':scope_kind,'new_owner_fixing_type_facts':newfacts,'new_global_owner_policy_events':newpolicy,'new_working_specification_approvals':0,'new_accepted_working_proposal_groups':0,'new_name_approvals':0,'new_registered_BC_component_ids':[],'new_physical_stock_or_mould_counts':0,'root_new_private_original_downloads':0,'remote_mutations':0,'workbook_export_pending':True}
 cp['parallel_import_queue'].append({'scope_kind':scope_kind,'receipt':rel(package),'receipt_sha256':sha(package),'approval_imported':True,'evidence_imported':True,'import_receipt':summary['receipt'],'status':'OWNER_FIXING_FACTS_IMPORTED' if batch==86 else 'GLOBAL_OFFERED_FIXING_CHOICE_IMPORTED_ONCE'});c['parallel_import_queue']=copy.deepcopy(cp['parallel_import_queue'])
 for doc,key in [(p,'latest_parallel_import'),(cp,'last_parallel_import'),(c,'last_parallel_import')]:doc[key]=copy.deepcopy(summary)
 for doc in docs.values():doc['updated_utc']=now
 docs['root']['current_component_review']=copy.deepcopy(c);assert all(cp[k]==v for k,v in before['walkthrough'].items() if k.startswith('current_')) and all(sha(PATHS[k])==v for k,v in guards.items()) and all(sha(path)==v for path,v in protected.items());write(here/'before-import.json',before);write(here/'source-manifest.json',{'files':files,'verified_messages':messages})
 for k,path in PATHS.items():write(path,docs[k])
 write(here/'import-receipt.json',{'status':'APPLIED;INDEPENDENT_READBACK_REQUIRED','summary':summary,'events':events,'protected_sha256':protected,'shared_after_sha256':{k:sha(v) for k,v in PATHS.items()}});print(json.dumps({'batch':batch,'status':'APPLIED','owner_type_facts':newfacts,'global_policy_events':newpolicy,'working_groups_still':240}))

if __name__=='__main__':main(int(sys.argv[1]))
