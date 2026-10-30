"""Apply existing owner policy to seven Moon Crater and two single-panel scopes."""
import copy,hashlib,json,sys
from datetime import datetime,timezone
from pathlib import Path
from import_moonphase_silver_working_specs_62 import ROOT,PATHS,read,sha,rel,write,specification_counts
from import_leaf_policy_working_82_83 import target,FIELDS
CONFIG={84:{'stem':'moon-crater-phases-1-3-standing-working-specs-2026-10-20','sha':'6ead5ddfe743451db5eca3de5fe077291a16e6112d9e064d7f6613cb44b12ca4','scopes':7,'originals':11,'count':228},85:{'stem':'embedded-shells-faceted-mound-working-specs-2026-10-20','sha':'098872e9bf0be016dfd4237e1aefca09de22a3e23ca82fc5c0b9eb2203af3f41','scopes':2,'originals':6,'count':240}}

def main(batch):
 cfg=CONFIG[batch];here=ROOT/f'components/reviews/parallel-import-2026-10-19-batch{batch}';source=ROOT/'components/parallel-reviews'/cfg['stem'];docs={k:read(v) for k,v in PATHS.items()}
 if (here/'import-receipt.json').exists():
  for item in read(here/'import-receipt.json')['scopes']:assert target(docs['progress'],item['component_id'],item['size_finish_variant_id'])[0]['all_six_working_specification_fields_accepted']
  print(json.dumps({'batch':batch,'status':'ALREADY_IMPORTED_IDEMPOTENT_NO_WRITE'}));return
 before=copy.deepcopy(docs);guards={k:sha(v) for k,v in PATHS.items()};frozen=[];visited=set();historical=[]
 def freeze(path,digest,recurse=True):
  path=Path(path)
  if str(path).startswith(('ns:','id:','https:','/BOLDSTONE MASTER/')):return
  if path in PATHS.values():historical.append({'path':str(path),'historical_sha256':digest,'scope':'Historical mutable reference retained in frozen allocation snapshot; current master guarded separately.'});return
  assert sha(path)==digest,str(path)
  if (str(path),digest) in visited:return
  visited.add((str(path),digest));dest=here/'sources'/(digest+path.suffix);dest.parent.mkdir(parents=True,exist_ok=True)
  if dest.exists():assert sha(dest)==digest
  else:dest.write_bytes(path.read_bytes())
  frozen.append({'source':str(path),'snapshot':rel(dest),'sha256':digest})
  if recurse and path.suffix=='.json':refs(read(path))
 def refs(value):
  if isinstance(value,dict):
   if isinstance(value.get('path'),str) and isinstance(value.get('sha256'),str):freeze(value['path'],value['sha256'])
   for v in value.values():refs(v)
  elif isinstance(value,list):
   for v in value:refs(v)
 package=source/'IMPORT_PACKAGE.json';freeze(package,cfg['sha']);pkg=read(package)
 for name in ['FILE_MANIFEST.json','SEALED_PACKAGE_MANIFEST.json','HISTORICAL_SOURCE_MANIFEST.json','SEALED_MANIFEST.json','BATCH_VERIFICATION.json','INDEPENDENT_PACKAGE_READBACK.json','PUBLIC_SOURCE_REFRESH.json','PREPARATION_SOURCE_LIMIT_CLARIFICATION.json']:
  path=source/name
  if path.exists():
   freeze(path,sha(path));items=read(path).get('files',{})
   if isinstance(items,dict):
    for name,digest in items.items():freeze(source/name,digest)
 decisions=[read(x['path']) for x in pkg['decisions']] if batch==84 else [read(read(x['package']['path'])['decision']['path']) for x in pkg['existing_variants']]
 assert len(decisions)==cfg['scopes']
 binding_path=source/('CACHED_IMAGE_BINDINGS.json' if batch==84 else 'CACHED_IMAGE_BINDING.json');freeze(binding_path,sha(binding_path));binding=read(binding_path)
 originals=binding['selected_originals'] if batch==84 else [{'file_id':x['file_id'],'local_path':x['path'],'sha256':x['sha256'],'size':x['bytes'],'current_rev':x['current_rev'],'content_hash':x['dropbox_content_hash']} for d in binding['designs'] for x in d['cached_originals']]
 assert len(originals)==cfg['originals'];freeze(here/'current-reference-check.json',sha(here/'current-reference-check.json'));metadata=read(here/'current-reference-check.json');heads={x[x['metadata_type']]['id']:x[x['metadata_type']] for x in metadata['metadata']}
 for item in originals:
  path=item.get('local_path') or item['original']['path'];digest=item.get('sha256') or item['original']['sha256'];freeze(path,digest,False);raw=Path(path).read_bytes();h=heads[item['file_id']];assert len(raw)==item['size']==h['size'] and h['rev']==(item.get('current_rev') or item['current_metadata_binding']['rev']);blocks=b''.join(hashlib.sha256(raw[i:i+4194304]).digest() for i in range(0,len(raw),4194304));assert hashlib.sha256(blocks).hexdigest()==(item.get('content_hash') or item['dropbox_content_hash']);assert any(h['path_display'].rsplit('/',1)[0]==f['path_display'] and 'rev' not in f for f in heads.values())
 previews=[]
 if batch==84:refs(binding['comparisons'])
 else:
  for design in binding['designs']:
   previews+=design['preview_bindings'];freeze(design['contact_sheet']['path'],design['contact_sheet']['sha256'],False)
  assert len(previews)==20
  for item in previews:freeze(item['preview_path'],item['sha256'],False)
 u,p,cp,c=(docs[k] for k in ['user','progress','walkthrough','component']);assert cp['last_parallel_import']['batch']==batch-1 and docs['root']['current_component_review']==c;policy=p['working_specification_acceptance_policy'];assert len(u['working_specification_acceptance_policy_decisions'])==1 and policy['policy_id'].endswith('LINE18928')
 protected={str(path):sha(path) for path in [ROOT/cp['register_workbook'],ROOT/cp['current_review_record'],ROOT/'components/evidence/component_register.json',ROOT.parent/'Boldstone_Wall_Sculptures_Matched_All_Fields_2026-10-15.xlsx']};now=datetime.now(timezone.utc).isoformat();scopes=[]
 for original in decisions:
  d=copy.deepcopy(original);cid,vid=d['component_id'],d['size_finish_variant_id'];node,kind=target(p,cid,vid);current_source=d.get('revised_source_specification_proposals_retained') or d['source_specification_proposals_retained'];assert node['identity_confirmed'] and not node.get('proposals_approved') and node['specification_proposals']==current_source and len(node['specification_proposals'])==6 and set(d['specifications'])==set(FIELDS);assert not any(x.get('decision_id')==d['decision_id'] for x in u['size_finish_variant_specification_decisions']);d['source_current_specification_proposals_retained']=copy.deepcopy(current_source)
  active=copy.deepcopy(d['specifications']);ids=[vid+':'+field.upper() for field in FIELDS]
  for field,item in active.items():
   assert item['owner_approved'] and not item['physical_value_verified'];item['proposal_id']=vid+':'+field.upper();item['source_status_before_root_overlay']=item.get('status');item['status']='WORKING_ACCEPTED_UNDER_OWNER_STANDING_POLICY; '+item.get('status','').replace('UNAPPROVED','HISTORICAL PROPOSAL')
  if batch==84:
   price=active['individual_price'];price['source_display_before_root_overlay']=price['display']
   if vid.endswith('-WHITE'):price['display']='£150 per White panel — working proposal accepted under standing policy, rounded from dated £156.25 retail reference; exact White offer unconfirmed'
   elif vid=='MCP1-VERDIGRIS-RUST':price['display']='£150 per panel — working proposal accepted under standing policy using a related coloured-series reference; exact offer unconfirmed'
   elif vid=='MCP2-BLUE-SPLASHES':price['display']='£350 per panel — working proposal accepted under standing policy using a related coloured-MCP2 reference; exact Blue offer unconfirmed'
   else:
    amount=350 if vid.startswith('MCP2') else 395;price['display']=f'£{amount} per panel — working price accepted from the 20 October listing reference; current exact-image correspondence unverified'
    price['basis']=price.get('basis','')+' Public-source refresh20October retained a price reference but changed CDN URLs;19October exact-photo mapping remains historical, not reverified by this price acceptance.'
  approval=rel(here/(vid+'-working-specification-approval.json'));context_record=rel(here/(vid+'-context-evidence.json'))
  if batch==85:
   d['source_authoritative_user_evidence_is_global_policy_only']=d.pop('authoritative_user_evidence');d['source_user_statement_is_global_policy_only']=d.pop('user_statement');assert not d['per_card_owner_reply_received'] and not d['synthetic_owner_reply_created']
  else:assert d['owner_answer_for_this_finish'] is None and d['new_explicit_owner_answer_events']==0
  d.update({'source_approved_proposal_ids':copy.deepcopy(d['approved_proposal_ids']),'approved_proposal_ids':ids,'approval_record':approval,'working_acceptance_basis':'DERIVED_FROM_STANDING_OWNER_POLICY','canonical_shared_policy_id':policy['policy_id'],'canonical_policy_record':policy['approval_record'],'owner_answer_for_this_scope':None,'new_individual_owner_reply_events':0,'root_imported_utc':now,'shared_master_import_performed':True,'active_working_specifications':active});u['size_finish_variant_specification_decisions'].append(d)
  node.update({'proposals_approved':True,'specifications_approved':True,'owner_estimates_accepted':True,'all_six_working_specification_fields_accepted':True,'approved_proposal_ids':ids,'specification_approval':approval,'working_specifications_approval_scope':'EXACT_FINISH_ALL_SIX_WORKING_VALUES','accepted_working_specifications':active,'source_specifications_retained':d['source_specifications_retained'],'source_specification_proposals_retained_unchanged':True,'physical_specs_verified':False,'actual_stock_verified':False,'fully_confirmed_specification_groups':[],'working_acceptance_basis':'DERIVED_FROM_STANDING_OWNER_POLICY','standing_working_approval_policy_id':policy['policy_id'],'owner_answer_for_this_scope':None,'specification_status_display':'Six working specifications accepted under standing instruction; estimates, conflicts and unknowns retained'})
  if d.get('revised_source_specification_proposals_retained'):node['revised_source_specification_proposals_retained']=d['revised_source_specification_proposals_retained']
  node['scope']=node.get('scope','')+' Working values accepted under standing owner policy, without an individual reply. Original source dictionaries remain unchanged; measurements, stock, scene provenance, fixing counts and load remain unverified. MCP4 price, owner4kg weight, unlimited stock and one-week lead time are not transferred.'
  h,f=heads[node['primary_image_id']],heads[node['primary_folder_id']];assert h['id']==d['primary_file_id'] and f['id']==d['folder_id'] and h['path_display'].rsplit('/',1)[0]==f['path_display'];node['current_dropbox_reference']={'file_id':h['id'],'folder_id':f['id'],'file_path':h['path_display'],'folder_path':f['path_display'],'file_revision':h['rev'],'file_bytes':h['size'],'image_url':d['image_link'],'folder_url':d['folder_link'],'checked_utc':metadata['checked_utc']}
  source_context=None;rear_candidate=False;ctxid=h['id'];series='Matching-finish series unestablished in selected references; elsewhere unknown.'
  if batch==84:
   desc='Parent inspected seven front references, three candidate rears and one shared White-series image in two comparison plates; all11 cached originals rehashed against fresh native revisions/sizes. Historical broader preview reviews were not repeated.'
   if vid.endswith('-WHITE'):
    status='Available: shared White series; prior exhibition context retained';ctxid='id:cnqzTNngPVsAAAAAAAugDQ';front='Complete clean front linked; native individual originals in the dated review are close-ups. Clean-image edit lineage unverified.';room='Shared series and previously recorded exhibition context available; individual home/client room unestablished in selected packet, elsewhere unknown.';series='Exact White027 family photograph retained as series context; no new component decomposition or physical count.';missing='Authenticated complete native individual front, finished White rear/fixing, calibrated profile and individual wider-room image unestablished in selected packet; elsewhere unknown.'
   else:
    front='Complete native individual front linked; camera-original/scene provenance unverified.';rear_candidate='VERDIGRIS-RUST' in vid
    if vid=='MCP1-VERDIGRIS-RUST':status='Available: on-wall; five prior room references retained';room='Five room references are recorded in the dated source review; outdoor on-wall primary rechecked. Installation provenance and exact cast remain unverified.';missing='Candidate rear011 exists but exact front/back pairing and load unknown; calibrated profile and authenticated wider-room/series coverage unestablished in selected packet, elsewhere unknown.'
    elif vid=='MCP2-BLUE-SPLASHES':status='Available: outdoor on-wall product view';room='Outdoor on-wall product view available; wider-room view unestablished in the historical six-file finish review and current selected primary, elsewhere unknown.';missing='Finished Blue rear/fixing, calibrated profile, wider-room and matching-finish series images unestablished in bounded evidence; elsewhere unknown.'
    else:status='Available: outdoor on-wall and candidate rear reference';room='Outdoor on-wall product view available; wider-room and matching-finish series unestablished in the dated finish review, elsewhere unknown.';missing='Candidate rear exists but exact front/back pairing and load unknown; calibrated profile, wider-room and matching-finish series unestablished in bounded evidence, elsewhere unknown.'
    if vid in ['MCP2-VERDIGRIS-RUST','MCP3-VERDIGRIS-RUST']:node['current_public_image_association_verified']=False;desc+=' Exact public photograph match is dated19October.20October CDN URL changes were not checked for byte-level correspondence; platform-pair status unchanged.'
   desc+=' Existing broader room/exhibition/source observations retained as dated evidence. No physical cast, stock or installed-hardware identity certified.'
  else:
   source_context=read(d['context_output_update']['path']);ctx=source_context['context_images'];ctxid=ctx['representative_file_id'];status='Available: room and historical outdoor-wall presentations' if vid=='EMBED-SHELLS-WHITE' else 'Available: seven indoor room presentations';desc=ctx['type']+'. '+ctx['limitations']+' Parent viewed both complete20-preview contact sheets and all six representative cached originals, then rehashed their bytes against current metadata.';front='Complete individual front linked; camera-original/edit lineage unverified.';room=ctx['type']+' available; installation and exact physical cast unverified.';missing='Finished rear/fixing photograph, calibrated profile and separate series arrangement unestablished among the reviewed12files, elsewhere unknown.' if vid=='EMBED-SHELLS-WHITE' else 'Finished rear/fixing photograph, calibrated profile and separate series arrangement unestablished among the reviewed8files, elsewhere unknown.'
  photo=copy.deepcopy(node.get('photo_coverage',{}));photo.update({'contextual_images_available':True,'contextual_source_status':status,'contextual_source_description':desc,'contextual_file_ids':[ctxid],'candidate_rear_reference_retained':rear_candidate,'rear_paired_to_selected_front':False,'individual_wider_room_established':batch==85,'rear_reference_established':False,'installation_provenance':'UNCONFIRMED','exact_physical_cast_identity_verified':False,'evidence_record':context_record});node.update({'photo_coverage':photo,'context_output_review':context_record});assert vid not in p['current_component_photograph_gaps'];finish='White' if vid.endswith('-WHITE') else ('Blue Splashes' if 'BLUE' in vid else ('Gold Leaf' if 'GOLD' in vid else 'Verdigris and Rust'))
  gap={'component_id':cid,'size_finish_variant_id':vid,'review_scope':kind,'canonical_name':node['canonical_name'],'finish':finish,'front':front,'room':room,'series':series,'evidence':desc,'missing':missing,'review_record':context_record};p['current_component_photograph_gaps'][vid]=gap;p.setdefault('pending_specification_checks',{})[vid+'-WORKING-SPECS-01']={'owner_answer_recorded':False,'standing_policy_acceptance_recorded':True,'individual_owner_reply_required':False,'approval_record':approval,'working_values_accepted':True,'actual_specification_fields_pending':FIELDS,'physical_specs_verified':False}
  write(ROOT/approval,d);write(ROOT/context_record,{'root_imported_utc':now,'description':desc,'source_context':source_context,'no_new_component_or_stock_count':True,'no_private_original_downloads':True});write(here/(vid+'-photo-gap.json'),gap);scopes.append({'component_id':cid,'size_finish_variant_id':vid,'review_scope':kind,'decision_id':d['decision_id'],'approval_record':approval})
 added=cfg['scopes']*6;u['specification_approval_counts']=specification_counts(u);assert u['specification_approval_counts']['proposal_groups']==before['user']['specification_approval_counts']['proposal_groups']+added==cfg['count'];c['interactive_review_state']['approved_proposal_groups']=cfg['count'];summary={'batch':batch,'recorded_utc':now,'receipt':rel(here/'import-receipt.json'),'scope_kind':'EXISTING_SCOPES_SIX_WORKING_FIELDS_UNDER_CANONICAL_POLICY_AND_BOUNDED_CONTEXT','scopes':scopes,'new_working_specification_approvals':cfg['scopes'],'new_accepted_working_proposal_groups':added,'new_owner_policy_events':0,'new_individual_owner_reply_events':0,'new_physically_verified_specification_groups':0,'new_name_approvals':0,'new_registered_BC_component_ids':[],'new_photo_gap_rows':cfg['scopes'],'root_new_private_original_downloads':0,'remote_mutations':0,'workbook_export_pending':True}
 cp['parallel_import_queue'].append({'scope_kind':summary['scope_kind'],'receipt':rel(package),'receipt_sha256':sha(package),'approval_imported':True,'evidence_imported':True,'import_receipt':summary['receipt'],'status':'SCOPED_WORKING_ACCEPTANCES_UNDER_EXISTING_POLICY;UNKNOWN_VALUES_RETAINED'});c['parallel_import_queue']=copy.deepcopy(cp['parallel_import_queue'])
 for doc,key in [(p,'latest_parallel_import'),(cp,'last_parallel_import'),(c,'last_parallel_import')]:doc[key]=copy.deepcopy(summary)
 for doc in docs.values():doc['updated_utc']=now
 docs['root']['current_component_review']=copy.deepcopy(c);assert all(cp[k]==v for k,v in before['walkthrough'].items() if k.startswith('current_')) and all(sha(PATHS[k])==v for k,v in guards.items()) and all(sha(path)==v for path,v in protected.items());write(here/'before-import.json',before);write(here/'source-manifest.json',{'files':frozen,'historical_mutable_references':historical,'parent_selected_originals_visually_inspected':len(originals),'cached_preview_hashes_checked':len(previews)})
 for k,path in PATHS.items():write(path,docs[k])
 write(here/'import-receipt.json',{'status':'APPLIED;INDEPENDENT_READBACK_REQUIRED','summary':summary,'scopes':scopes,'protected_sha256':protected,'shared_after_sha256':{k:sha(v) for k,v in PATHS.items()}});print(json.dumps({'batch':batch,'status':'APPLIED','working_groups':cfg['count'],'scopes':len(scopes),'new_owner_replies':0,'new_policy_events':0}))

if __name__=='__main__':main(int(sys.argv[1]))
