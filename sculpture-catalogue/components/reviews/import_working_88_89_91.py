"""Import sealed, existing finish reviews without creating new owner replies."""
import copy, hashlib, json, sys
from pathlib import Path
from datetime import datetime, timezone
from import_moonphase_silver_working_specs_62 import ROOT, PATHS, read, sha, rel, write, specification_counts
from import_leaf_policy_working_82_83 import target, FIELDS

CONFIG = {
 88: dict(stem='acanthus-one-left-sandstone-pewter-working-specs-2026-10-20', sha='cf3621a767b8e96f2443a62da15776543a0198344cf51268ad9c486d7dfa76d3', scopes=2, originals=4, count=252, previous=87),
 89: dict(stem='panel-plant-raked-standing-working-specs-2026-10-20', sha='5c7276e951c8c187872e7a7fc6f2030dfcdfc7ca7903432990ed6597297db1eb', scopes=9, originals=13, count=306, previous=88),
 91: dict(stem='crater-fishwave-ring-standing-working-specs-2026-10-20', sha='d13dcd66551f61f3f7449b7996e59f66cb85c4b5b6beafe69803026378525f17', scopes=4, originals=6, count=330, previous=90),
}

def photograph_review(batch, d, node):
 vid=d['size_finish_variant_id']; ctx=None
 if batch==88:
  ctx=read(d['context_output_update']['path']); x=d['context_images']; ids=[x['representative_file_id']]
  status='Available: grouped workshop context; primary is a cropped detail'
  desc=x['type']+'. '+x['limitations']+' Root inspected all four rehashed cached originals; fresh native metadata agrees.'
  front='Cropped detail primary; complete target visible within grouped workshop003. Isolated complete neutral-light front unestablished in the complete three-file Assorted Colours census; elsewhere unknown.'
  room='Individual room installation unestablished in the three-file census; elsewhere unknown.'
  series='Mixed workshop group003 retained with existing target position; no new component, mould or stock count.'
  missing='Isolated complete neutral-light target, finished rear/fixings, calibrated profile and individual room installation unestablished in this three-file census; elsewhere unknown.'
 else:
  refs=d['links']['context_and_series']; ids=[x['file_id'] for x in refs]
  desc='Root inspected and rehashed the selected cached originals against fresh native revisions and sizes. Historical broader observations remain dated evidence. '
  front=d['primary_reference_scope']+'. Camera-original or edit lineage unverified.'
  if vid in ['RAKED-SPIRAL1-BEIGE','RAKED-SPIRAL2-BEIGE']:
   front='Complete target visible as '+d['primary_target_position'].lower()+' in shared beige pair001; isolated individual photograph unestablished in this bounded review, elsewhere unknown.'
   desc+='Pair001 links the already-kept left/right design positions; it is not an isolated single-component photograph. '
  if refs:
   status='Available: paired room and outdoor-wall presentations' if vid.startswith('MFW-') else 'Available: existing wall or series display references'
   room='Paired indoor display available; individual home/client room unestablished in selected evidence, elsewhere unknown.' if vid.startswith('MFW-') else 'Wall/display context available; authenticated individual home/client room unestablished in selected evidence, elsewhere unknown.'
   series='Existing paired or series context retained with target positions; no new component, mould or stock count.'
   desc+='Existing context and target positions: '+'; '.join((x.get('reference_scope') or x.get('role') or 'context')+((': '+x['target_position']) if x.get('target_position') else '') for x in refs)+'.'
  else:
   status='Unestablished: wider-room or series; individual product view available'
   room='Wider-room installation unestablished in the selected primary and dated review, elsewhere unknown.'
   series='Matching-finish series unestablished in this bounded review, elsewhere unknown.'
   desc+='Complete individual product view retained; a product background does not establish wider-room or series coverage.'
  missing='Finished rear/fixing, calibrated profile and authenticated individual home/client room unestablished in this bounded evidence; elsewhere unknown.'
  if not refs:missing='Finished rear/fixing, calibrated profile, wider-room and matching-finish series unestablished in this bounded evidence; elsewhere unknown.'
  if vid in ['RAKED-SPIRAL1-BEIGE','RAKED-SPIRAL2-BEIGE']:missing='Isolated complete individual front, finished rear/fixing, calibrated profile and authenticated individual home/client room unestablished in selected references; elsewhere unknown.'
 desc+=' No exact physical cast, installed hardware, stock or scene provenance certified.'
 return dict(status=status,description=desc,ids=ids,front=front,room=room,series=series,missing=missing,source_context=ctx)

def main(batch):
 cfg=CONFIG[batch]; here=ROOT/f'components/reviews/parallel-import-2026-10-19-batch{batch}'; source=ROOT/'components/parallel-reviews'/cfg['stem']; docs={k:read(v) for k,v in PATHS.items()}
 if (here/'import-receipt.json').exists():
  assert all(target(docs['progress'],x['component_id'],x['size_finish_variant_id'])[0]['all_six_working_specification_fields_accepted'] for x in read(here/'import-receipt.json')['scopes'])
  print(json.dumps(dict(batch=batch,status='ALREADY_IMPORTED_IDEMPOTENT_NO_WRITE')));return
 before=copy.deepcopy(docs); guards={k:sha(v) for k,v in PATHS.items()}; frozen=[]; visited=set(); historical=[]
 def freeze(path,digest,recurse=True):
  path=Path(path)
  if str(path).startswith(('ns:','id:','https:','/BOLDSTONE MASTER/')):return
  if path in PATHS.values():historical.append(dict(path=str(path),historical_sha256=digest,scope='Historical mutable reference; current master guarded separately.'));return
  assert sha(path)==digest,str(path)
  if (str(path),digest) in visited:return
  visited.add((str(path),digest)); dest=here/'sources'/(digest+path.suffix);dest.parent.mkdir(parents=True,exist_ok=True)
  if dest.exists():assert sha(dest)==digest
  else:dest.write_bytes(path.read_bytes())
  frozen.append(dict(source=str(path),snapshot=rel(dest),sha256=digest))
  if recurse and path.suffix=='.json':refs(read(path))
 def refs(v):
  if isinstance(v,dict):
   if isinstance(v.get('path'),str) and isinstance(v.get('sha256'),str):freeze(v['path'],v['sha256'])
   for x in v.values():refs(x)
  elif isinstance(v,list):
   for x in v:refs(x)
 package=source/'IMPORT_PACKAGE.json';freeze(package,cfg['sha']);pkg=read(package)
 for name in ['FILE_MANIFEST.json','SEALED_PACKAGE_MANIFEST.json','HISTORICAL_SOURCE_MANIFEST.json','SEALED_MANIFEST.json','BATCH_VERIFICATION.json','INDEPENDENT_PACKAGE_READBACK.json']:
  path=source/name
  if path.exists():
   freeze(path,sha(path)); files=read(path).get('files',{})
   if isinstance(files,dict):
    for name,digest in files.items():freeze(source/name,digest)
 decisions=[read(x['path']) for x in pkg['decisions']] if batch!=88 else [read(read(x['package']['path'])['decision']['path']) for x in pkg['existing_variants']]
 assert len(decisions)==cfg['scopes']; binding=read(source/('CACHED_IMAGE_BINDING.json' if batch==88 else 'CACHED_IMAGE_BINDINGS.json'))
 originals=binding['bindings'] if batch==88 else binding['selected_originals'] if batch==89 else binding['images'];assert len(originals)==cfg['originals']
 freeze(here/'current-reference-check.json',sha(here/'current-reference-check.json'));metadata=read(here/'current-reference-check.json');heads={x[x['metadata_type']]['id']:x[x['metadata_type']] for x in metadata['metadata']}
 for item in originals:
  path=item.get('local_path') or (item['original']['path'] if 'original' in item else item['path']);digest=item.get('sha256') or item['original']['sha256'];freeze(path,digest,False);raw=Path(path).read_bytes();h=heads[item['file_id']];size=item.get('size',item.get('bytes'));rev=item.get('rev',item.get('current_rev',item.get('current_metadata_binding',{}).get('rev')));dh=item.get('dropbox_content_hash',item.get('content_hash'))
  assert len(raw)==size==h['size'] and h['rev']==rev
  assert hashlib.sha256(b''.join(hashlib.sha256(raw[i:i+4194304]).digest() for i in range(0,len(raw),4194304))).hexdigest()==dh
  assert any(h['path_display'].rsplit('/',1)[0]==f['path_display'] and 'rev' not in f for f in heads.values())
 u,p,cp,c=(docs[k] for k in ['user','progress','walkthrough','component']);policy=p['working_specification_acceptance_policy'];assert cp['last_parallel_import']['batch']==cfg['previous'] and docs['root']['current_component_review']==c
 assert len(u['working_specification_acceptance_policy_decisions'])==1 and policy['policy_id'].endswith('LINE18928')
 protected={str(path):sha(path) for path in [ROOT/cp['register_workbook'],ROOT/cp['current_review_record'],ROOT/'components/evidence/component_register.json',ROOT.parent/'Boldstone_Wall_Sculptures_Matched_All_Fields_2026-10-15.xlsx']};now=datetime.now(timezone.utc).isoformat();scopes=[]
 for original in decisions:
  d=copy.deepcopy(original);cid,vid=d['component_id'],d['size_finish_variant_id'];node,kind=target(p,cid,vid);raw=d.get('revised_source_specification_proposals_retained') or d['source_specification_proposals_retained']
  if batch==88:
   fieldmap={'dimensions_and_depth':'dimensions','weight':'weight','material':'material_finish','fixing':'fixings','individual_price':'individual_price','availability':'availability'}
   assert {fieldmap[x['group']]:dict(display=x['display'],status=x['source_evidence_state']) for x in node['specification_proposals']}==raw
   raw=copy.deepcopy(node['specification_proposals'])
  assert node['identity_confirmed'] and not node.get('proposals_approved') and node['specification_proposals']==raw and len(raw)==6 and set(d['specifications'])==set(FIELDS),vid
  assert not any(x.get('decision_id')==d['decision_id'] for x in u['size_finish_variant_specification_decisions']);d['source_current_specification_proposals_retained']=copy.deepcopy(raw);active=copy.deepcopy(d['specifications']);ids=[vid+':'+field.upper() for field in FIELDS]
  for field,item in active.items():
   assert item['owner_approved'] and not item['physical_value_verified'];item['proposal_id']=vid+':'+field.upper();item['source_status_before_root_overlay']=item.get('status');item['status']='WORKING_ACCEPTED_UNDER_OWNER_STANDING_POLICY; '+item.get('status','').replace('UNAPPROVED','HISTORICAL PROPOSAL')
  if 'authoritative_user_evidence' in d:d['source_authoritative_user_evidence_is_global_policy_only']=d.pop('authoritative_user_evidence')
  if 'user_statement' in d:d['source_user_statement_is_global_policy_only']=d.pop('user_statement')
  approval=rel(here/(vid+'-working-specification-approval.json'));context=rel(here/(vid+'-context-evidence.json'))
  d.update(dict(source_approved_proposal_ids=copy.deepcopy(d['approved_proposal_ids']),approved_proposal_ids=ids,approval_record=approval,working_acceptance_basis='DERIVED_FROM_STANDING_OWNER_POLICY',canonical_shared_policy_id=policy['policy_id'],canonical_policy_record=policy['approval_record'],owner_answer_for_this_scope=None,new_individual_owner_reply_events=0,root_imported_utc=now,shared_master_import_performed=True,active_working_specifications=active));u['size_finish_variant_specification_decisions'].append(d)
  node.update(dict(proposals_approved=True,specifications_approved=True,owner_estimates_accepted=True,all_six_working_specification_fields_accepted=True,approved_proposal_ids=ids,specification_approval=approval,working_specifications_approval_scope='EXACT_FINISH_ALL_SIX_WORKING_VALUES',accepted_working_specifications=active,source_specifications_retained=d['source_specifications_retained'],source_specification_proposals_retained_unchanged=True,physical_specs_verified=False,actual_stock_verified=False,fully_confirmed_specification_groups=[],working_acceptance_basis='DERIVED_FROM_STANDING_OWNER_POLICY',standing_working_approval_policy_id=policy['policy_id'],owner_answer_for_this_scope=None,specification_status_display='Six working specifications accepted under standing instruction; estimates, conflicts and unknowns retained'))
  node['scope']=node.get('scope','')+' Working values accepted under standing owner policy without an individual reply. Source dictionaries, owner-confirmed subfields, unknowns and conflicts remain; no new measurements, stock or hardware certification.'
  h,f=heads[node.get('primary_image_id') or node['reference_image_id']],heads[node['primary_folder_id']];assert h['id']==d['primary_file_id'] and f['id']==d['folder_id'] and h['path_display'].rsplit('/',1)[0]==f['path_display'];node['current_dropbox_reference']=dict(file_id=h['id'],folder_id=f['id'],file_path=h['path_display'],folder_path=f['path_display'],file_revision=h['rev'],file_bytes=h['size'],image_url=d['image_link'],folder_url=d['folder_link'],checked_utc=metadata['checked_utc'])
  ph=photograph_review(batch,d,node);photo=copy.deepcopy(node.get('photo_coverage',{}));photo.update(dict(contextual_images_available=bool(ph['ids']),contextual_source_status=ph['status'],contextual_source_description=ph['description'],contextual_file_ids=ph['ids'],individual_wider_room_established=False,rear_reference_established=False,installation_provenance='UNCONFIRMED',exact_physical_cast_identity_verified=False,evidence_record=context));node.update(photo_coverage=photo,context_output_review=context)
  assert vid not in p['current_component_photograph_gaps'];finish=node['canonical_name'].split('—')[-1].strip() if '—' in node['canonical_name'] else node['canonical_name']
  gap=dict(component_id=cid,size_finish_variant_id=vid,review_scope=kind,canonical_name=node['canonical_name'],finish=finish,front=ph['front'],room=ph['room'],series=ph['series'],evidence=ph['description'],missing=ph['missing'],review_record=context);p['current_component_photograph_gaps'][vid]=gap
  p.setdefault('pending_specification_checks',{})[vid+'-WORKING-SPECS-01']=dict(owner_answer_recorded=False,standing_policy_acceptance_recorded=True,individual_owner_reply_required=False,approval_record=approval,working_values_accepted=True,actual_specification_fields_pending=FIELDS,physical_specs_verified=False)
  write(ROOT/approval,d);write(ROOT/context,dict(root_imported_utc=now,description=ph['description'],source_context=ph['source_context'],no_new_component_or_stock_count=True,no_private_original_downloads=True));write(here/(vid+'-photo-gap.json'),gap);scopes.append(dict(component_id=cid,size_finish_variant_id=vid,review_scope=kind,decision_id=d['decision_id'],approval_record=approval))
 u['specification_approval_counts']=specification_counts(u);assert u['specification_approval_counts']['proposal_groups']==before['user']['specification_approval_counts']['proposal_groups']+cfg['scopes']*6==cfg['count'];c['interactive_review_state']['approved_proposal_groups']=cfg['count']
 summary=dict(batch=batch,recorded_utc=now,receipt=rel(here/'import-receipt.json'),scope_kind='EXISTING_SCOPES_SIX_WORKING_FIELDS_UNDER_CANONICAL_POLICY_AND_BOUNDED_CONTEXT',scopes=scopes,new_working_specification_approvals=cfg['scopes'],new_accepted_working_proposal_groups=cfg['scopes']*6,new_owner_policy_events=0,new_individual_owner_reply_events=0,new_physically_verified_specification_groups=0,new_name_approvals=0,new_registered_BC_component_ids=[],new_photo_gap_rows=0 if batch==88 else cfg['scopes'],updated_existing_supplemental_photo_gap_rows=2 if batch==88 else 0,root_new_private_original_downloads=0,remote_mutations=0,workbook_export_pending=True)
 cp['parallel_import_queue'].append(dict(scope_kind=summary['scope_kind'],receipt=rel(package),receipt_sha256=sha(package),approval_imported=True,evidence_imported=True,import_receipt=summary['receipt'],status='SCOPED_WORKING_ACCEPTANCES_UNDER_EXISTING_POLICY;UNKNOWN_VALUES_RETAINED'));c['parallel_import_queue']=copy.deepcopy(cp['parallel_import_queue'])
 for doc,key in [(p,'latest_parallel_import'),(cp,'last_parallel_import'),(c,'last_parallel_import')]:doc[key]=copy.deepcopy(summary)
 for doc in docs.values():doc['updated_utc']=now
 docs['root']['current_component_review']=copy.deepcopy(c);assert all(cp[k]==v for k,v in before['walkthrough'].items() if k.startswith('current_')) and all(sha(PATHS[k])==v for k,v in guards.items()) and all(sha(path)==v for path,v in protected.items())
 write(here/'before-import.json',before);write(here/'source-manifest.json',dict(files=frozen,historical_mutable_references=historical,parent_selected_originals_visually_inspected=len(originals)))
 for k,path in PATHS.items():write(path,docs[k])
 write(here/'import-receipt.json',dict(status='APPLIED;INDEPENDENT_READBACK_REQUIRED',summary=summary,scopes=scopes,protected_sha256=protected,shared_after_sha256={k:sha(v) for k,v in PATHS.items()}));print(json.dumps(dict(batch=batch,status='APPLIED',working_groups=cfg['count'],scopes=len(scopes),new_owner_replies=0,new_policy_events=0)))

if __name__=='__main__':main(int(sys.argv[1]))
