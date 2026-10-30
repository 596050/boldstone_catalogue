"""Import six existing Leaf scopes under the single owner working-specification policy."""
import copy, hashlib, json, sys
from datetime import datetime, timezone
from pathlib import Path
from import_moonphase_silver_working_specs_62 import ROOT, PATHS, read, sha, rel, write, specification_counts

CONFIG = {
 82: {'stem':'leaf-curve-growth-standing-working-specs-2026-10-20','package_sha':'42754280399e8ac982e4e71b0a38a362d9530040b22b8544e8efebb986b7f7e0','binding':'CACHED_IMAGE_BINDINGS.json','count':168},
 83: {'stem':'leaf-form-working-specs-2026-10-20','package_sha':'2831caa47ef9e6ac19bf42df6e7ec703d92a597bb3745395d86859f250a75ea2','binding':'CACHED_IMAGE_BINDING.json','count':186},
}
FIELDS = ['dimensions','weight','material_finish','fixing','individual_price','availability']

def target(p,cid,vid):
 parent=p['reviews'][cid]
 if vid in parent.get('component_layouts',{}):return parent['component_layouts'][vid], 'COMPONENT_LAYOUT'
 if vid in parent.get('size_finish_variants',{}):return parent['size_finish_variants'][vid], 'VARIANT'
 assert parent['size_finish_variant_id']==vid
 return parent,'BASE'

def main(batch):
 cfg=CONFIG[batch];here=ROOT/f'components/reviews/parallel-import-2026-10-19-batch{batch}';source=ROOT/'components/parallel-reviews'/cfg['stem'];docs={k:read(v) for k,v in PATHS.items()}
 if (here/'import-receipt.json').exists():
  for item in read(here/'import-receipt.json')['scopes']:
   assert target(docs['progress'],item['component_id'],item['size_finish_variant_id'])[0]['all_six_working_specification_fields_accepted']
  print(json.dumps({'batch':batch,'status':'ALREADY_IMPORTED_IDEMPOTENT_NO_WRITE'}));return
 before=copy.deepcopy(docs);guards={k:sha(v) for k,v in PATHS.items()};frozen=[];visited=set();historical_mutable_references=[]
 control_changes={}
 if batch==83:
  addendum=source/'CONTROL_MANIFEST_ADDENDUM.json';assert sha(addendum)=='8a91333a45fe81f14b516f674b65393aa56129261beff36a781a7c9a5fb3b2ab';a=read(addendum);assert a['status']=='PASS' and a['changed_control_file_count']==6 and a['unchanged_manifest_entry_count']==31 and a['total_original_manifest_entries']==37;control_changes={x['path']:x for x in a['control_file_changes']}
 def freeze(path,digest,recurse=True):
  path=Path(path)
  if str(path).startswith(('ns:','id:','https:','/BOLDSTONE MASTER/')):return
  if path in PATHS.values():
   historical_mutable_references.append({'path':str(path),'historical_sha256':digest,'verification_scope':'Historical reference retained inside frozen allocation snapshot; current mutable master is separately guarded.'});return
  if str(path) in control_changes and digest==control_changes[str(path)]['original_manifest_sha256']:
   item=control_changes[str(path)];assert sha(path)==item['current_sha256'];original=read(path)
   for key,value in item['added_fields'].items():assert original.pop(key)==value
   raw=(json.dumps(original,ensure_ascii=False,indent=2)+'\n').encode();assert hashlib.sha256(raw).hexdigest()==digest;dest=here/'sources'/(digest+path.suffix);dest.parent.mkdir(parents=True,exist_ok=True)
   if dest.exists():assert sha(dest)==digest
   else:dest.write_bytes(raw)
   if not any(x['snapshot']==rel(dest) for x in frozen):frozen.append({'source':str(path),'snapshot':rel(dest),'sha256':digest,'reconstructed_original_control_bytes':True,'current_sha256':item['current_sha256'],'only_two_canonical_binding_fields_added':True})
   freeze(path,item['current_sha256']);return
  assert sha(path)==digest,str(path)
  if (str(path),digest) in visited:return
  visited.add((str(path),digest));dest=here/'sources'/(digest+path.suffix);dest.parent.mkdir(parents=True,exist_ok=True)
  if dest.exists():assert sha(dest)==digest
  else:dest.write_bytes(path.read_bytes())
  frozen.append({'source':str(path),'snapshot':rel(dest),'sha256':digest})
  if recurse and path.suffix=='.json':references(read(path))
 def references(value):
  if isinstance(value,dict):
   if isinstance(value.get('path'),str) and isinstance(value.get('sha256'),str):freeze(value['path'],value['sha256'])
   for v in value.values():references(v)
  elif isinstance(value,list):
   for v in value:references(v)
 package=source/'IMPORT_PACKAGE.json';freeze(package,cfg['package_sha']);pkg=read(package)
 if batch==83:freeze(addendum,sha(addendum))
 for manifest in ['FILE_MANIFEST.json','SEALED_PACKAGE_MANIFEST.json','HISTORICAL_SOURCE_MANIFEST.json','COORDINATOR_IMPORT_PACKAGE.json','CANONICAL_POLICY_BINDING.json','BATCH_VERIFICATION.json']:
  path=source/manifest
  if path.exists():freeze(path,sha(path))
 if batch==82:decisions=[read(x['path']) for x in pkg['decisions']]
 else:decisions=[read(read(x['package']['path'])['decision']['path']) for x in pkg['packages']]
 assert len(decisions)==3
 u,p,cp,c=(docs[k] for k in ['user','progress','walkthrough','component']);policy=p['working_specification_acceptance_policy'];policy_id=policy['policy_id']
 assert len(u['working_specification_acceptance_policy_decisions'])==1 and policy_id.endswith('LINE18928') and cp['last_parallel_import']['batch']==batch-1 and docs['root']['current_component_review']==c
 freeze(here/'current-reference-check.json',sha(here/'current-reference-check.json'));metadata=read(here/'current-reference-check.json');heads={x[x['metadata_type']]['id']:x[x['metadata_type']] for x in metadata['metadata']}
 binding_path=source/cfg['binding'];freeze(binding_path,sha(binding_path));binding=read(binding_path)
 assert len(binding['selected_originals'])==(5 if batch==82 else 6)
 for item in binding['selected_originals']:
  path=item.get('local_path') or item['original']['path'];digest=item.get('sha256') or item['original']['sha256'];freeze(path,digest,False);raw=Path(path).read_bytes();head=heads[item['file_id']]
  assert len(raw)==item['size']==head['size'] and head['rev']==(item.get('current_rev') or item['current_metadata_binding']['rev'])
  blocks=b''.join(hashlib.sha256(raw[i:i+4194304]).digest() for i in range(0,len(raw),4194304));assert hashlib.sha256(blocks).hexdigest()==(item.get('content_hash') or item['dropbox_content_hash'])
  assert any(head['path_display'].rsplit('/',1)[0]==h['path_display'] and 'rev' not in h for h in heads.values())
 if batch==83:
  assert len(binding['preview_hashes'])==135
  for item in binding['preview_hashes']:freeze(item['preview_path'],item['sha256'],False)
  references(binding['contact_sheets'])
 else:freeze(binding['derived_comparison']['path'],binding['derived_comparison']['sha256'],False)
 now=datetime.now(timezone.utc).isoformat();scopes=[];protected={str(path):sha(path) for path in [ROOT/cp['register_workbook'],ROOT/cp['current_review_record'],ROOT/'components/evidence/component_register.json',ROOT.parent/'Boldstone_Wall_Sculptures_Matched_All_Fields_2026-10-15.xlsx']}
 for original in decisions:
  decision=copy.deepcopy(original);cid,vid=decision['component_id'],decision['size_finish_variant_id'];node,kind=target(p,cid,vid);assert node['identity_confirmed'] and not node.get('proposals_approved')
  assert node['specification_proposals']==decision['source_specification_proposals_retained'] and len(node['specification_proposals'])==6 and set(decision['specifications'])==set(FIELDS)
  assert not any(x.get('decision_id')==decision['decision_id'] for x in u['size_finish_variant_specification_decisions'])
  accepted=copy.deepcopy(decision['specifications']);ids=[vid+':'+f.upper() for f in FIELDS]
  for field,item in accepted.items():
   assert item['owner_approved'] and not item['physical_value_verified'];item['proposal_id']=vid+':'+field.upper();item['source_status_before_root_policy_overlay']=item.get('status');item['status']='WORKING_ACCEPTED_UNDER_OWNER_STANDING_POLICY; '+item.get('status','').replace('UNAPPROVED','HISTORICAL PROPOSAL').replace('OWNER ADOPTION PENDING','SOURCE ADOPTION NOW WORKING ACCEPTED').replace('NOT OWNER APPROVED','SOURCE PRICE STILL UNVERIFIED')
  if batch==82:
   price=accepted['individual_price'];price['source_display_before_root_policy_overlay']=price['display']
   if vid=='LEAF-CURVE-WHITE-GOLD':price['display']='£250–£350 per panel — working range accepted under standing instruction; exact source-priced offer unconfirmed'
   elif vid=='LEAF-GROWTH-WHITE':price['display']='£800 per White panel — working price accepted under standing instruction; dated £750 retail / £375 trade retained separately'
   else:price['display']='£900 per panel — uncosted working proposal accepted under standing instruction; exact Gold offer or quote unconfirmed'
  approval=rel(here/(vid+'-working-specification-approval.json'));context_record=rel(here/(vid+'-context-evidence.json'))
  if batch==83:
   decision['source_authoritative_user_evidence_is_global_policy_only']=decision.pop('authoritative_user_evidence');decision['source_user_statement_is_global_policy_only']=decision.pop('user_statement');assert not decision['per_card_owner_reply_received'] and not decision['synthetic_owner_reply_created']
  else:assert decision['owner_answer_for_this_finish'] is None and decision['new_explicit_owner_answer_events']==0
  decision.update({'source_approved_proposal_ids':copy.deepcopy(decision['approved_proposal_ids']),'approved_proposal_ids':ids,'approval_record':approval,'working_acceptance_basis':'DERIVED_FROM_STANDING_OWNER_POLICY','canonical_shared_policy_id':policy_id,'canonical_policy_record':policy['approval_record'],'owner_answer_for_this_scope':None,'new_individual_owner_reply_events':0,'root_imported_utc':now,'shared_master_import_performed':True,'active_working_specifications':accepted})
  u['size_finish_variant_specification_decisions'].append(decision)
  node.update({'proposals_approved':True,'specifications_approved':True,'owner_estimates_accepted':True,'all_six_working_specification_fields_accepted':True,'approved_proposal_ids':ids,'specification_approval':approval,'working_specifications_approval_scope':'EXACT_FINISH_ALL_SIX_WORKING_VALUES','accepted_working_specifications':accepted,'source_specifications_retained':decision['source_specifications_retained'],'source_specification_proposals_retained_unchanged':True,'physical_specs_verified':False,'actual_stock_verified':False,'fully_confirmed_specification_groups':[],'working_acceptance_basis':'DERIVED_FROM_STANDING_OWNER_POLICY','standing_working_approval_policy_id':policy_id,'owner_answer_for_this_scope':None,'specification_status_display':'Six working specifications accepted under standing instruction; estimates, conflicts and unknowns retained'})
  node['scope']=node.get('scope','')+' Working values accepted under the existing standing owner policy; no individual reply is invented. Estimates, source conflicts, unknown measurements and scene provenance remain labelled. MCP4 stock policy and one-week lead time are not transferred.'
  head,folder=heads[node['primary_image_id']],heads[node['primary_folder_id']];assert head['id']==decision['primary_file_id'] and folder['id']==decision['folder_id'] and head['path_display'].rsplit('/',1)[0]==folder['path_display']
  node['current_dropbox_reference']={'file_id':head['id'],'folder_id':folder['id'],'file_path':head['path_display'],'folder_path':folder['path_display'],'file_revision':head['rev'],'file_bytes':head['size'],'image_url':decision['image_link'],'folder_url':decision['folder_link'],'checked_utc':metadata['checked_utc']}
  context=None;ctxid=None;available=True;front='Complete individual primary linked; cached original rehashed. Actual camera-original provenance unverified.'
  if batch==82:
   if vid=='LEAF-CURVE-WHITE-GOLD':
    ctxid='id:cnqzTNngPVsAAAAAAAuY0w';status='Available: individual front and outdoor brick-wall display';desc='Root viewed five selected cached references together and rehashed five originals across these three Leaf scopes. This finish has a complete front and brick-wall display. Prior88-file census dated18October was not repeated.';room='Outdoor brick-wall display available; indoor wider-room view unestablished in selected references, elsewhere unknown.';series='Individual panel shown; series context unestablished in this bounded selection, elsewhere unknown.'
   elif vid=='LEAF-GROWTH-WHITE':
    ctxid='id:cnqzTNngPVsAAAAAAAsS4w';status='Available: brick-wall and indoor red-board display';desc='Complete tall panel in brick-wall and indoor red-board displays. Root viewed selected cached references and rehashed originals; prior116-file family census dated18October was not repeated. Display is not an authenticated client installation.';room='Indoor red-board display available; authenticated home/client room unestablished, elsewhere unknown.';series='Single continuous Leaf Growth panel; no integral leaves split into sale components.'
   else:
    available=False;status='Unestablished: cropped Gold details only';desc='Eight cropped/detail-only Gold images in the dated source review; selected detail original rehashed and inspected. Complete Gold front, wider room and series depiction unestablished in this bounded evidence; elsewhere unknown.';front='Cropped Gold details only; complete individual front unestablished among eight reviewed source images, elsewhere unknown.';room='Wider-room context unestablished among eight cropped Gold details, elsewhere unknown.';series='Gold series context unestablished among eight cropped details, elsewhere unknown.'
   missing='Finished rear/fixing and calibrated profile unestablished in selected references; elsewhere unknown.'
   if not available:missing='Complete Gold front, in-situ/room, series, finished rear/fixing and calibrated profile unestablished among eight cropped source images; elsewhere unknown.'
  else:
   context=read(decision['context_output_update']['path']);ctx=context['context_images'];ctxid=ctx['representative_file_id'];desc=ctx['type']+'. '+ctx['limitations']+' Parent independently viewed the six selected cached originals in two comparison plates and rehashed them; 135 cached preview hashes verified without repeating the lane visual census.'
   if vid=='LEAF-FORM-GOLD':status='Available: Gold room presentations; scene provenance unverified';room='Seven Gold room presentations available; real installation and same-cast identity unverified.';series='Gold series context unestablished among seven room presentations, elsewhere unknown.';front='Gold artwork visible in room presentations; authenticated product-only full-front photograph unestablished among seven references, elsewhere unknown.';missing='Authenticated product-only Gold front, Gold series, finished rear/fixing and calibrated profile unestablished among seven references; elsewhere unknown.'
   else:status='Available: individual outdoor, paired garden and indoor exhibition';room='Individual outdoor, paired garden and indoor exhibition available; authenticated home/client room unestablished, elsewhere unknown.';series='Paired White family/garden and exhibition context available; no new component, mould or stock count inferred.';missing='Finished rear/fixing, calibrated profile and authenticated home/client room unestablished in reviewed source census; elsewhere unknown.'
  photo=copy.deepcopy(node.get('photo_coverage',{}));photo.update({'contextual_images_available':available,'contextual_source_status':status,'contextual_source_description':desc,'contextual_file_ids':[ctxid] if ctxid else [],'individual_wider_room_established':vid=='LEAF-FORM-GOLD','rear_reference_established':False,'installation_provenance':'UNCONFIRMED','exact_physical_cast_identity_verified':False,'evidence_record':context_record});node.update({'photo_coverage':photo,'context_output_review':context_record});assert vid not in p['current_component_photograph_gaps']
  gap={'component_id':cid,'size_finish_variant_id':vid,'review_scope':kind,'canonical_name':node['canonical_name'],'finish':node.get('finish',vid),'front':front,'room':room,'series':series,'evidence':desc,'missing':missing,'review_record':context_record};p['current_component_photograph_gaps'][vid]=gap
  p.setdefault('pending_specification_checks',{})[vid+'-WORKING-SPECS-01']={'owner_answer_recorded':False,'standing_policy_acceptance_recorded':True,'individual_owner_reply_required':False,'approval_record':approval,'working_values_accepted':True,'actual_specification_fields_pending':FIELDS,'physical_specs_verified':False}
  write(ROOT/approval,decision);write(ROOT/context_record,{'root_imported_utc':now,'description':desc,'source_context':context,'no_new_component_or_stock_count':True,'no_private_original_downloads':True});write(here/(vid+'-photo-gap.json'),gap);scopes.append({'component_id':cid,'size_finish_variant_id':vid,'review_scope':kind,'decision_id':decision['decision_id'],'approval_record':approval})
 u['specification_approval_counts']=specification_counts(u);assert u['specification_approval_counts']['proposal_groups']==before['user']['specification_approval_counts']['proposal_groups']+18==cfg['count'];c['interactive_review_state']['approved_proposal_groups']=cfg['count']
 summary={'batch':batch,'recorded_utc':now,'receipt':rel(here/'import-receipt.json'),'scope_kind':'THREE_EXISTING_LEAF_SCOPES_SIX_WORKING_FIELDS_UNDER_CANONICAL_POLICY_AND_BOUNDED_CONTEXT','scopes':scopes,'new_working_specification_approvals':3,'new_accepted_working_proposal_groups':18,'new_owner_policy_events':0,'new_individual_owner_reply_events':0,'new_physically_verified_specification_groups':0,'new_name_approvals':0,'new_registered_BC_component_ids':[],'new_photo_gap_rows':3,'root_new_private_original_downloads':0,'remote_mutations':0,'workbook_export_pending':True}
 cp['parallel_import_queue'].append({'scope_kind':summary['scope_kind'],'receipt':rel(package),'receipt_sha256':sha(package),'approval_imported':True,'evidence_imported':True,'import_receipt':summary['receipt'],'status':'THREE_SIX_FIELD_WORKING_ACCEPTANCES_UNDER_EXISTING_POLICY;UNKNOWN_VALUES_RETAINED'});c['parallel_import_queue']=copy.deepcopy(cp['parallel_import_queue'])
 for doc,key in [(p,'latest_parallel_import'),(cp,'last_parallel_import'),(c,'last_parallel_import')]:doc[key]=copy.deepcopy(summary)
 for doc in docs.values():doc['updated_utc']=now
 docs['root']['current_component_review']=copy.deepcopy(c);assert all(cp[k]==v for k,v in before['walkthrough'].items() if k.startswith('current_')) and all(sha(PATHS[k])==v for k,v in guards.items()) and all(sha(path)==v for path,v in protected.items())
 write(here/'before-import.json',before);write(here/'source-manifest.json',{'files':frozen,'historical_mutable_references':historical_mutable_references,'parent_selected_originals_visually_inspected':len(binding['selected_originals']),'cached_preview_hashes_checked':135 if batch==83 else 0})
 for k,path in PATHS.items():write(path,docs[k])
 write(here/'import-receipt.json',{'status':'APPLIED;INDEPENDENT_READBACK_REQUIRED','summary':summary,'scopes':scopes,'protected_sha256':protected,'shared_after_sha256':{k:sha(v) for k,v in PATHS.items()}});print(json.dumps({'batch':batch,'status':'APPLIED','working_groups':cfg['count'],'scopes':len(scopes),'new_individual_owner_replies':0,'new_policy_events':0}))

if __name__=='__main__':main(int(sys.argv[1]))
