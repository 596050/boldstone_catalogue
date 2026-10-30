"""Import exact named working-field approvals with separately bounded photo context."""
import copy
import hashlib
import json
import sys
from datetime import datetime,timezone
from pathlib import Path
from import_source_followups_24_25 import canonical_messages
from import_moonphase_silver_working_specs_62 import ROOT,PATHS,read,sha,rel,write,specification_counts

CONFIG={
 71:{'number':2,'package':'6867ae9d6abd6bcf7d8ad6fa0fe98fe3d008ae5c2449955bf31d4cb9cb8dbb89','decision':'242845aa106a84c79d385998ab82e000ce346ead0c293127100bf42ccbc9a2fa','owner':28448,'card':28441,'prior':70,'count':106,'literal':'Keep these six working specifications for Moonspiral Two — White (MS2), with the source conflicts, proposals and unknowns still labelled?','context':'637dfbca76cc05d95c6d01494cd17167a35f54d35b6fe6e8cebcae9e29ec7bc2'},
 72:{'number':3,'package':'83919073ed90df0f4f886de51e125a23ae334af0e3bbb1f0bd1996300d8b619e','decision':'1cd11433a88dfc93f6143727704128876fc136b626b554656ecded6ebd3f7c04','owner':18401,'card':18381,'prior':71,'count':112,'literal':'Approve these six working details for “Moonspiral Three — White (MS3)”,','context':'f8c08e12db3d2ef017933793bf92d8c43574107cf1933b35c64cdd2e6728bacb','seal':'845b41f3b4a5c1c4f9e8fa8b0431c52aeeaeb7061eb3c4e65d89de9892c1f233'},
}

def apply(batch):
 cfg=CONFIG[batch];number=cfg['number'];cid,vid=f'BC-MS-{number}',f'MS{number}-WHITE';here=ROOT/f'components/reviews/parallel-import-2026-10-19-batch{batch}';source=ROOT/f'components/parallel-reviews/moonspiral-{("two" if number==2 else "three")}-white-working-specs-2026-10-20/owner-working-specs-keep'
 docs={key:read(path) for key,path in PATHS.items()}
 if (here/'import-receipt.json').exists():
  assert docs['progress']['reviews'][cid]['size_finish_variants'][vid]['all_six_working_specification_fields_accepted']
  print(json.dumps({'batch':batch,'status':'ALREADY_IMPORTED_IDEMPOTENT_NO_WRITE'}));return
 before,guards=copy.deepcopy(docs),{key:sha(path) for key,path in PATHS.items()};files=[]
 def freeze(path,digest):
  path=Path(path);assert sha(path)==digest,str(path);dest=here/'sources'/(digest+path.suffix);dest.parent.mkdir(parents=True,exist_ok=True)
  if dest.exists():assert sha(dest)==digest
  else:dest.write_bytes(path.read_bytes())
  files.append({'source':str(path),'snapshot':rel(dest),'sha256':digest});return rel(dest)
 package_path=source/'IMPORT_PACKAGE.json';freeze(package_path,cfg['package']);package=read(package_path);freeze(package['manifest']['path'],package['manifest']['sha256'])
 for item in read(package['manifest']['path'])['files']:freeze(item['path'],item['sha256'])
 if cfg.get('seal'):
  seal=source/'SEALED_PACKAGE_MANIFEST.json';freeze(seal,cfg['seal'])
  for item in read(seal)['files']:freeze(item['path'],item['sha256'])
 assert sha(package['decision']['path'])==cfg['decision'];decision=read(package['decision']['path'])
 evidence=[decision['preceding_review_card_evidence'],decision['authoritative_user_evidence'],*decision.get('corroborating_owner_evidence',[])];messages=canonical_messages([item|{'transcript':item['transcript_path']} for item in evidence],package['source_owner_session'])
 assert messages[0]['line']==cfg['card'] and messages[1]['line']==cfg['owner'] and messages[1]['text']==cfg['literal']
 assert ('Moonspiral Two' if number==2 else 'Moonspiral Three') in messages[0]['text']
 if number==2:assert len(messages)==3 and messages[2]['line']==28456 and messages[2]['text']=='Keep'
 u,p,cp,c=(docs[key] for key in ['user','progress','walkthrough','component']);node=p['reviews'][cid]['size_finish_variants'][vid]
 assert docs['root']['current_component_review']==c and cp['last_parallel_import']['batch']==cfg['prior'] and node['identity_confirmed'] and not node['proposals_approved']
 assert node['specification_proposals']==decision['source_specification_proposals_retained'] and len(node['specification_proposals'])==6
 assert decision['source_specifications_retained']==read(decision['source_review_before_answer']['path'])['specifications']
 heads={item[item['metadata_type']]['id']:item[item['metadata_type']] for item in read(here/'current-reference-check.json')['metadata']};ref=node['current_dropbox_reference'];head,folder=heads[ref['file_id']],heads[ref['folder_id']]
 assert head['rev']==ref['rev'] and head['size']==ref['bytes'] and head['path_display']==ref['file_path'] and folder['path_display']==ref['folder_path']
 context_ref=package['context_output_update'];assert context_ref['sha256']==cfg['context'];freeze(context_ref['path'],cfg['context']);context=read(context_ref['path']);ctx=context['context_images'];binding_ref=ctx['source_binding'];freeze(binding_ref['path'],binding_ref['sha256']);binding=read(binding_ref['path']);evidence_kind='THUMBNAILS_ONLY'
 if number==2:
  freeze(binding['current_metadata']['path'],binding['current_metadata']['sha256'])
  for item in binding['sources']:
   freeze(item['cached_preview']['path'],item['cached_preview']['sha256']);h,parent=heads[item['file_id']],heads[item['folder_id']]
   assert h['rev']==item['rev'] and h['size']==item['remote_original_bytes'] and h['path_display'].rsplit('/',1)[0]==parent['path_display'] and not item['original_bytes_rehashed_this_turn']
  assert len(binding['sources'])==3 and not binding['original_bytes_verified_this_turn']
 else:
  primary=binding['primary'];original=Path(primary['cached_original']['path']);freeze(original,primary['cached_original']['sha256']);content=original.read_bytes()
  assert len(content)==head['size']==primary['bytes'];blocks=b''.join(hashlib.sha256(content[i:i+4194304]).digest() for i in range(0,len(content),4194304));assert hashlib.sha256(blocks).hexdigest()==primary['Dropbox_content_hash']
  shared=binding['shared_context'];freeze(shared['cached_thumbnail']['path'],shared['cached_thumbnail']['sha256']);shared_head=heads[shared['file_id']];assert shared_head['rev']==shared['native_metadata']['rev'] and shared_head['size']==shared['native_metadata']['size'] and shared_head['path_display'].rsplit('/',1)[0]==heads[shared['folder_id']]['path_display']
  for item in [binding['individual_contact_sheet'],binding['shared_context_contact_sheet']]:freeze(item['path'],item['sha256'])
  evidence_kind='PRIMARY_CACHED_ORIGINAL_REHASHED;SHARED_CONTEXT_THUMBNAIL_ONLY'
 freeze(here/'current-reference-check.json',sha(here/'current-reference-check.json'))
 protected={str(path):sha(path) for path in [ROOT/cp['register_workbook'],ROOT/cp['current_review_record'],ROOT/'components/evidence/component_register.json',ROOT.parent/'Boldstone_Wall_Sculptures_Matched_All_Fields_2026-10-15.xlsx']};now=datetime.now(timezone.utc).isoformat();approval=rel(here/'working-specification-approval.json');fields=decision['approved_field_groups'];assert len(fields)==6 and set(fields)==set(decision['specifications'])
 scoped_ids=[vid+':'+field.upper() for field in fields];decision.update({'source_approved_proposal_ids':copy.deepcopy(decision['approved_proposal_ids']),'approved_proposal_ids':scoped_ids,'approval_record':approval,'imported_utc':now,'authoritative_user_evidence':messages[1],'verified_review_card_evidence':messages[0],'verified_corroborating_owner_evidence':messages[2:],'shared_master_import_performed':True,'root_image_evidence_kind':evidence_kind,'context_evidence_imported_once':True})
 assert not any(item.get('decision_id')==decision['decision_id'] for item in u['size_finish_variant_specification_decisions']);u['size_finish_variant_specification_decisions'].append(decision);u['specification_approval_counts']=specification_counts(u);assert u['specification_approval_counts']['proposal_groups']==before['user']['specification_approval_counts']['proposal_groups']+6==cfg['count']
 accepted=copy.deepcopy(decision['specifications'])
 for field,item in accepted.items():item['proposal_id']=vid+':'+field.upper()
 node.update({'specifications_approved':True,'proposals_approved':True,'owner_estimates_accepted':True,'source_claims_accepted_as_working':True,'all_six_working_specification_fields_accepted':True,'approved_proposal_ids':scoped_ids,'specification_approval':approval,'working_specifications_approval_scope':'EXACT_FINISH_ALL_SIX_WORKING_VALUES','accepted_working_specifications':accepted,'source_specification_proposals_retained_unchanged':True,'physical_specs_verified':False,'actual_stock_verified':False,'fully_confirmed_specification_groups':[],'physical_weight_conflict_resolved':False,'current_public_selling_price_verified':False,'specification_status_display':'Six working specifications accepted; source conflicts, proposals and unknowns retained','scope':decision['scope']+' Prior name, stable image/folder IDs and sibling distinctions retained. Source_values flags remain immutable historical snapshots; working acceptance is a separate overlay.','root_image_evidence_kind':evidence_kind})
 context_record=rel(here/'context-evidence.json');photo=copy.deepcopy(node.get('photo_coverage',{}));status='Available: on-wall/outdoor and shared family room context' if number==2 else 'Available: shared outdoor display context';description=ctx['type']+'. '+ctx['limitations']+' Root evidence: '+('three cached thumbnails; no original-byte verification.' if number==2 else 'primary cached file bytes rehashed; shared display reviewed as a cached thumbnail. Exact camera-original and scene provenance remain unverified.')
 photo.update({'contextual_images_available':True,'contextual_source_status':status,'contextual_source_description':description,'contextual_file_ids':[ctx['representative_file_id']]+([ctx['individual_context_file_id']] if number==2 else []),'series_arrangement':True,'outdoor_display_available':True,'individual_wider_room_established':False,'installation_provenance':'UNCONFIRMED','exact_physical_cast_identity_verified':False,'root_evidence_kind':evidence_kind,'evidence_record':context_record})
 if number==2:photo.update({'on_wall':True,'family_wider_room_context':True,'individual_context_file_id':ctx['individual_context_file_id'],'individual_context_folder_id':ctx['individual_context_folder_id']})
 node.update({'photo_coverage':photo,'context_output_review':context_record});assert vid not in p['current_component_photograph_gaps']
 gap={'component_id':cid,'size_finish_variant_id':vid,'canonical_name':node['canonical_name'],'finish':'White','front':'Complete individual front source linked; '+('thumbnail evidence only.' if number==2 else 'cached file bytes rehashed; camera-original status unverified.'),'room':('Individual on-wall/outdoor sources available; wider-room pair scene is shared family context. Dedicated individual wider-room image unestablished.' if number==2 else 'Shared outdoor leaning/display image available; dedicated individual wider-room or installed-room image unestablished.'),'series':ctx['type']+'; no new physical count or group decomposition.','evidence':description+' Not a whole-library absence claim.','missing':'Rear/fixing, calibrated side/profile and dedicated individual wider-room image not established in the reviewed packet.','review_record':context_record,'source_package_sha256':cfg['context']};p['current_component_photograph_gaps'][vid]=gap
 context.update({'root_imported_utc':now,'root_current_reference_check':rel(here/'current-reference-check.json'),'root_image_evidence_kind':evidence_kind,'root_new_private_original_downloads':0,'new_owner_or_specification_approval_from_context':False,'shared_master_import_performed':True})
 p.setdefault('pending_specification_checks',{})[vid+'-WORKING-SPECS-01']={'owner_answer_recorded':True,'approval_record':approval,'working_values_accepted':True,'actual_specification_fields_pending':fields,'physical_specs_verified':False,'weight_conflict_resolved':False};c['interactive_review_state']['approved_proposal_groups']=cfg['count']
 summary={'batch':batch,'recorded_utc':now,'receipt':rel(here/'import-receipt.json'),'scope_kind':f'EXACT_MS{number}_WHITE_SIX_WORKING_FIELDS_AND_CONTEXT','component_id':cid,'size_finish_variant_id':vid,'new_working_specification_approvals':1,'new_accepted_working_proposal_groups':6,'new_physically_verified_specification_groups':0,'new_name_approvals':0,'new_owner_policy_events':0,'new_registered_BC_component_ids':[],'new_photo_gap_rows':1,'root_new_private_original_downloads':0,'remote_mutations':0,'workbook_export_pending':True}
 cp['parallel_import_queue'].append({'scope_kind':summary['scope_kind'],'receipt':rel(package_path),'receipt_sha256':cfg['package'],'approval_imported':True,'evidence_imported':True,'import_receipt':summary['receipt'],'status':'SIX_WORKING_FIELDS_ACCEPTED;SOURCE_CONFLICTS_RETAINED;SCOPED_CONTEXT_RECORDED;ACTUAL_DETAILS_UNVERIFIED'});c['parallel_import_queue']=copy.deepcopy(cp['parallel_import_queue'])
 for target,key in [(p,'latest_parallel_import'),(cp,'last_parallel_import'),(c,'last_parallel_import')]:target[key]=copy.deepcopy(summary)
 for doc in docs.values():doc['updated_utc']=now
 docs['root']['current_component_review']=copy.deepcopy(c)
 assert node['specification_proposals']==before['progress']['reviews'][cid]['size_finish_variants'][vid]['specification_proposals'] and all(cp[key]==value for key,value in before['walkthrough'].items() if key.startswith('current_')) and all(sha(PATHS[key])==value for key,value in guards.items()) and all(sha(path)==value for path,value in protected.items())
 write(here/'before-import.json',before);write(here/'working-specification-approval.json',decision);write(here/'accepted-working-review.json',node);write(here/'context-evidence.json',context);write(here/'photo-gap.json',gap);write(here/'source-manifest.json',{'files':files,'verified_messages':messages})
 for key,path in PATHS.items():write(path,docs[key])
 write(here/'import-receipt.json',{'status':'APPLIED;INDEPENDENT_READBACK_REQUIRED','summary':summary,'decision_id':decision['decision_id'],'protected_sha256':protected,'shared_after_sha256':{key:sha(path) for key,path in PATHS.items()}});print(json.dumps({'batch':batch,'status':'APPLIED','accepted_working_groups':cfg['count'],'one_owner_approval_event':True,'source_conflicts_retained':True,'context_recorded_once':True,'actual_specs_verified':False}))

if __name__=='__main__':apply(int(sys.argv[1]))
