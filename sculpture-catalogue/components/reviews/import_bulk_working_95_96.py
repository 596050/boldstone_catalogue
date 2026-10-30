"""Import typed existing scopes with exact proposal IDs and immutable source snapshots."""
import copy,json,sys
from pathlib import Path
from datetime import datetime,timezone
from import_moonphase_silver_working_specs_62 import ROOT,PATHS,read,sha,rel,write,specification_counts
from import_leaf_policy_working_82_83 import FIELDS
CONFIG={95:dict(stem='all-remaining-a-standing-working-specs-2026-10-20',sha='4b31266f25d05838ca39342e480e95d2f23568cc25bd9c5e455e1dbfd65a6ea1',scopes=56,delta=327),96:dict(stem='remaining-lane-b-working-specs-2026-10-20',sha='e19deb03632ceba6585434b6b07d0828f690b184215d4d7232fa8d71a216d830',scopes=40,delta=240)}
def at(p,locator):
 for key in locator:p=p[key]
 return p
def locate(batch,d):
 if batch==95:
  loc=d['model_locator'];scope=d['scope_key']
 else:
  scope=d['scope_key'].split('|',1)[1];kind=d['variant_kind']
  # The first White finish is stored directly on three legacy parent nodes.
  # Its typed review remains a finish review; do not duplicate the source node.
  parent_finish=(d['component_id'],scope) in [('BC-CORAL','CORAL-WHITE'),('BC-DR-WAVE1','DR1-WHITE'),('BC-DR-SPIRAL','DR2-WHITE')]
  loc=['source_design_reviews',scope] if kind=='whole_source_review' else ['reviews',d['component_id']]+([] if d.get('base_scope')=='BASE' or parent_finish else [kind,scope])
 kind='CATALOGUE_ALIAS' if loc[0]=='catalogue_alias_reviews' else 'WHOLE_SOURCE' if loc[0]=='source_design_reviews' else ('BASE' if scope=='BASE' else 'VARIANT') if len(loc)==2 else {'size_finish_variants':'VARIANT','build_variants':'BUILD','component_layouts':'COMPONENT_LAYOUT'}[loc[2]]
 return loc,scope,kind
def photo(batch,d):
 if batch==96:
  ctx=d['context_images'];refs=ctx['selected_context_images'];ids=[x['file_id'] for x in refs];desc=ctx['visual_observation']+' '+ctx['scope_limit'];detail=ctx['primary_is_cropped_detail'];group=False;missing_front=ctx['isolated_front_not_established'];scene=ctx['primary_is_context_scene'];historical=ctx['historical_photo_evidence_retained']
  if scene and not ids:ids=[d['primary_file_id']]
  status='Available: selected context presentation; provenance unverified' if ids else 'Historical context retained; selected primary is a cropped detail' if detail else 'Selected product reference; broader context remains source qualified'
  front='Selected primary is a cropped detail; historical complete-view evidence retained without a new whole-folder census.' if detail else 'Complete target represented within context; isolated product-only front unestablished in this pass.' if missing_front else 'Selected individual depiction retained; image/cast provenance unverified.'
  missing=' '.join(read(d['context_output_update']['path'])['current_unresolved_photo_requests'])+' Bounded selected evidence only; elsewhere unknown.'
 else:
  links=d['links'];rear_refs=[x for x in links['context_and_series'] if 'REAR' in str(x.get('role','')).upper()];selected=[x for x in links['context_and_series'] if x not in rear_refs];hist=links['additional_historical_contexts'];refs=selected+hist;ids=list(dict.fromkeys(x['file_id'] for x in refs if x.get('file_id')));detail=d['primary_reference_is_detail_only'];group=d['primary_is_group_reference'];missing_front=d['individual_photo_missing'];historical=hist
  status='Available: selected context/series; provenance unverified' if selected else 'Available: dated historical context/series, not newly rechecked' if hist else 'Selected product reference; wider-room/series unestablished in bounded review'
  front='Selected primary is a cropped/detail reference; complete isolated front unestablished in this bounded review, elsewhere unknown.' if detail else 'Complete target visible within the existing group reference; isolated individual front unestablished in this bounded review, elsewhere unknown.' if group or missing_front else 'Complete individual depiction linked; camera/scene and physical-cast provenance unverified.'
  desc='Exact kept source/reference roles retained. Selected cached first frames were inspected by root; complete native binary versus derivative-only limits remain explicit. Historical contexts outside this selected packet are retained as dated observations and were not freshly rechecked. No cast, stock, installation or source-version equivalence inferred.'
  missing=('Complete isolated individual front; ' if detail or group or missing_front else '')+'exact cast-linked rear/hardware, calibrated profile and authenticated installation unestablished in this bounded review; elsewhere unknown.'
  if len(links['all_selected_reference_file_ids'])>1:
   front='Multiple historically kept source views retained separately. Primary may be a group depiction; an additional complete individual view exists for the separate kept source. Same cast, mould and measured-version equivalence are unconfirmed.'
  if rear_refs:desc+=' Native rear reference IDs retained separately: '+', '.join(x['file_id'] for x in rear_refs)+'. Exact selected-front/back pairing remains unconfirmed.'
  if d.get('unresolved_alternative_images_retained'):desc+=' Unresolved alternative images remain in the source; no new design or measured-size equivalence assigned.'
 room='Context or arrangement reference available; wider-room coverage remains source qualified and actual installation/same-cast identity unverified.' if ids else 'Wider-room or in-situ coverage unestablished in the selected packet; dated historical observations retained, elsewhere unknown.'
 series='Existing series/group context retained without new components or set-price/weight division.' if group or any('series' in str(x.get('role','')).lower() for x in refs) else 'Matching series unestablished in this selected packet; any historical evidence retained, elsewhere unknown.'
 if batch==95:
  special={'DDR-SPIRAL-VERDIGRIS':'Indoor room presentation available; scene/installation and same-cast provenance unverified.','DECO-1-VERDIGRIS':'Paired outdoor-wall/garden presentation available; authenticated individual room unestablished in selected evidence, elsewhere unknown.','DECO-2-VERDIGRIS':'Indoor room presentation of a pair available; scene/installation and same-cast provenance unverified.'}
  room=special.get(d['scope_key'],room)
 desc+=' Root rehashed selected cached bytes and validated the sealed same-day native metadata locally; no duplicate API read or private-original download. Six working fields do not certify actual measurements, scene authenticity, fixing load or stock.'
 return dict(ids=ids,status=status,description=desc,front=front,room=room,series=series,missing=missing,historical=historical,rear_ids=[x['file_id'] for x in rear_refs] if batch==95 else [])

def main(batch):
 cfg=CONFIG[batch];source=ROOT/'components/parallel-reviews'/cfg['stem'];here=ROOT/f'components/reviews/parallel-import-2026-10-19-batch{batch}';docs={k:read(v) for k,v in PATHS.items()};u,p,cp,c=(docs[k] for k in ['user','progress','walkthrough','component'])
 if (here/'import-receipt.json').exists():
  assert all(at(p,x['model_locator'])['all_six_working_specification_fields_accepted'] for x in read(here/'import-receipt.json')['scopes']);print(json.dumps(dict(batch=batch,status='ALREADY_IMPORTED_IDEMPOTENT_NO_WRITE')));return
 before=copy.deepcopy(docs);guards={k:sha(v) for k,v in PATHS.items()};assert cp['last_parallel_import']['batch']==batch-1 and docs['root']['current_component_review']==c;frozen=[];seen=set();historical=[]
 def refs(v):
  if isinstance(v,dict):
   if isinstance(v.get('path'),str) and isinstance(v.get('sha256'),str):freeze(v['path'],v['sha256'])
   for x in v.values():refs(x)
  elif isinstance(v,list):
   for x in v:refs(x)
 def freeze(path,digest):
  path=Path(path)
  if str(path).startswith(('ns:','id:','https:','/BOLDSTONE MASTER/')):return
  if path in PATHS.values():historical.append(dict(path=str(path),historical_sha256=digest));return
  assert sha(path)==digest,str(path)
  if (str(path),digest) in seen:return
  seen.add((str(path),digest));dest=here/'sources'/(digest+path.suffix);dest.parent.mkdir(parents=True,exist_ok=True)
  if dest.exists():assert sha(dest)==digest
  else:dest.write_bytes(path.read_bytes())
  frozen.append(dict(source=str(path),snapshot=rel(dest),sha256=digest))
  # Discovery registers describe historical candidates, including superseded
  # mutable paths. Freeze the register itself; it is not a current-byte manifest
  # for every historical document it discovered. Cached media and sealed files
  # have their own explicit current-byte checks above.
  stop=path.name.startswith('snapshot-') or path.name in ['NODE_AT_ALLOCATION.json','SOURCE_REVIEW_AT_ALLOCATION.json','SOURCE_RECORDS_AT_ALLOCATION.json','ORIGINAL_REVIEW.json','DISCOVERED_EVIDENCE.json','VISUAL_INDEX.json'] or '/source-snapshots/' in str(path)
  if path.suffix=='.json' and not stop:refs(read(path))
 package=source/'IMPORT_PACKAGE.json';freeze(package,cfg['sha']);pkg=read(package)
 for name in ['SEALED_MANIFEST.json','SEALED_PACKAGE_MANIFEST.json','FILE_MANIFEST.json','HISTORICAL_SOURCE_MANIFEST.json','BATCH_VERIFICATION.json','INDEPENDENT_PACKAGE_READBACK.json']:
  path=source/name
  if path.exists():
   freeze(path,sha(path));files=read(path).get('files',{})
   if isinstance(files,dict):
    for name,digest in files.items():freeze(source/name,digest)
   else:refs(files)
 for name in ['current-reference-check.json','parent-media-hash-check.json']:freeze(here/name,sha(here/name))
 evidence=read(here/'parent-media-hash-check.json');assert evidence.get('root_all_plates_visually_inspected') is True
 metadata=read(here/'current-reference-check.json');heads={x[x['metadata_type']]['id']:x[x['metadata_type']] for x in metadata['metadata']};decisions=[read(x['path']) for x in pkg['decisions']];assert len(decisions)==cfg['scopes'];scopes=[];now=datetime.now(timezone.utc).isoformat();policy=p['working_specification_acceptance_policy'];protected={str(path):sha(path) for path in [ROOT/cp['register_workbook'],ROOT/'components/evidence/component_register.json',ROOT.parent/'Boldstone_Wall_Sculptures_Matched_All_Fields_2026-10-15.xlsx']}
 for original in decisions:
  d=copy.deepcopy(original);loc,scope,kind=locate(batch,d);node=at(p,loc);cid=d['component_id'];assert not node.get('all_six_working_specification_fields_accepted')
  if batch==96:assert node==read(d['source_snapshots']['node']['path'])
  elif kind=='CATALOGUE_ALIAS':assert node==read(d['source_review_at_allocation']['path']) and node['historical_name_keep_bindings']==d['historical_name_keep_bindings_retained']
  else:assert node.get('specification_proposals')==d['source_specification_proposals_retained']
  assert node.get('identity_confirmed') or node.get('source_depicted_identities_kept');assert set(d['specifications'])==set(FIELDS);ids=copy.deepcopy(d['approved_proposal_ids']);assert len(ids)==len(set(ids))==6;active=copy.deepcopy(d['specifications'])
  for field,x in active.items():
   assert x['owner_approved'] and not x['physical_value_verified'];x['source_status_before_root_overlay']=x.get('status');x['status']='WORKING_ACCEPTED_UNDER_OWNER_STANDING_POLICY; '+x.get('status','').replace('UNAPPROVED','HISTORICAL PROPOSAL')
  ledger='build_variant_decisions' if kind=='BUILD' else 'specification_decisions' if kind=='BASE' else 'size_finish_variant_specification_decisions';assert not any(x.get('decision_id')==d['decision_id'] for x in u.get(ledger,[]))
  if ledger=='size_finish_variant_specification_decisions':d['size_finish_variant_id']=scope
  if ledger=='build_variant_decisions':d['build_variant_id']=scope
  for key in ['authoritative_user_evidence','user_statement']:
   if key in d:d['source_'+key+'_is_global_policy_only']=d.pop(key)
  approval=rel(here/(cid+'--'+scope.replace(':','_')+'-working-approval.json'));context=rel(here/(cid+'--'+scope.replace(':','_')+'-context.json'));d.update(approval_record=approval,active_working_specifications=active,working_acceptance_basis='DERIVED_FROM_STANDING_OWNER_POLICY',canonical_shared_policy_id=policy['policy_id'],owner_answer_for_this_scope=None,new_individual_owner_reply_events=0,root_imported_utc=now,shared_master_import_performed=True);u.setdefault(ledger,[]).append(d)
  node.update(proposals_approved=True,specifications_approved=True,owner_estimates_accepted=True,all_six_working_specification_fields_accepted=True,approved_proposal_ids=ids,specification_approval=approval,working_specifications_approval_scope='EXACT_FINISH_ALL_SIX_WORKING_VALUES',accepted_working_specifications=active,source_specification_proposals_retained_unchanged=True,physical_specs_verified=False,actual_stock_verified=False,working_acceptance_basis='DERIVED_FROM_STANDING_OWNER_POLICY',standing_working_approval_policy_id=policy['policy_id'],owner_answer_for_this_scope=None,specification_status_display='Six working fields accepted under standing instruction; source versions, estimates and unknown actual values retained',historical_scope_before_working_acceptance=copy.deepcopy(node.get('scope')),scope='Working values accepted for this exact existing scope under standing owner instruction; no new individual reply. Physical measurements, exact material/cast applicability, installed hardware/load, current offers/stock and scene provenance remain source-qualified or unverified. Original dictionaries and prior owner subfields remain unchanged.')
  node.setdefault('source_specifications_retained',copy.deepcopy(d['source_specifications_retained']))
  fid=d.get('selected_reference_file_id') or d.get('reference_file_id') or d['primary_file_id'];h,f=heads[fid],heads[d['folder_id']];assert h['path_display'].rsplit('/',1)[0]==f['path_display'];node['current_dropbox_reference']=dict(file_id=fid,folder_id=f['id'],file_path=h['path_display'],folder_path=f['path_display'],file_revision=h['rev'],file_bytes=h['size'],image_url=d['image_link'],folder_url=d['folder_link'],checked_utc=metadata['checked_utc'])
  ph=photo(batch,d);coverage=copy.deepcopy(node.get('photo_coverage',{}));coverage=coverage if isinstance(coverage,dict) else dict(historical_photo_coverage=coverage);coverage.update(contextual_images_available=bool(ph['ids']),contextual_file_ids=ph['ids'],contextual_source_status=ph['status'],contextual_source_description=ph['description'],historical_photo_evidence_retained=ph['historical'],installation_provenance='UNCONFIRMED',exact_physical_cast_identity_verified=False,rear_reference_established=bool(ph['rear_ids'] or coverage.get('rear_reference_established') or coverage.get('rear')),rear_reference_file_ids=ph['rear_ids'],rear_paired_to_selected_front=False,evidence_record=context);node.update(photo_coverage=coverage,context_output_review=context)
  gapkey=cid+'|BASE' if scope=='BASE' else 'SOURCE-G310003' if kind=='WHOLE_SOURCE' else scope;assert gapkey not in p['current_component_photograph_gaps'];gap=dict(component_id=cid,size_finish_variant_id=scope,photo_gap_id=gapkey,review_scope=kind,model_locator=loc,canonical_name=d['canonical_name'],finish=d['canonical_name'].split('—')[-1].strip(),front=ph['front'],room=ph['room'],series=ph['series'],evidence=ph['description'],missing=ph['missing'],review_record=context);p['current_component_photograph_gaps'][gapkey]=gap
  p['pending_specification_checks'][cid+'|'+scope+'-WORKING-SPECS-01']=dict(owner_answer_recorded=False,standing_policy_acceptance_recorded=True,individual_owner_reply_required=False,working_values_accepted=True,actual_specification_fields_pending=FIELDS,physical_specs_verified=False,approval_record=approval)
  write(ROOT/approval,d);write(ROOT/context,dict(description=ph['description'],source_context=ph['historical'],new_physical_count=0,new_downloads=0));scopes.append(dict(component_id=cid,size_finish_variant_id=scope,review_scope=kind,model_locator=loc,ledger=ledger,decision_id=d['decision_id'],approval_record=approval,photo_gap_id=gapkey))
 u['specification_approval_counts']=specification_counts(u);delta=u['specification_approval_counts']['proposal_groups']-before['user']['specification_approval_counts']['proposal_groups'];assert delta==cfg['delta'],(batch,delta,cfg['delta']);c['interactive_review_state']['approved_proposal_groups']=u['specification_approval_counts']['proposal_groups'];summary=dict(batch=batch,recorded_utc=now,receipt=rel(here/'import-receipt.json'),scope_kind='TYPED_EXISTING_SCOPES_WITH_EXACT_SOURCE_IDS_AND_BOUNDED_PHOTO_EVIDENCE',scopes=scopes,new_working_specification_approvals=cfg['scopes'],resulting_working_fields=6*cfg['scopes'],new_accepted_working_proposal_groups=delta,new_owner_policy_events=0,new_individual_owner_reply_events=0,new_name_approvals=0,new_physically_verified_specification_groups=0,new_registered_BC_component_ids=[],root_new_private_original_downloads=0,remote_mutations=0,new_photo_gap_rows=cfg['scopes']-(1 if batch==96 else 0),workbook_export_pending=True)
 cp['parallel_import_queue'].append(dict(scope_kind=summary['scope_kind'],receipt=rel(package),receipt_sha256=cfg['sha'],approval_imported=True,evidence_imported=True,import_receipt=summary['receipt'],workbook_export_pending=True,status='EXISTING_SCOPES_SIX_WORKING_FIELDS;SOURCE_AND_ACTUAL_GAPS_RETAINED'));c['parallel_import_queue']=copy.deepcopy(cp['parallel_import_queue'])
 for doc,key in [(p,'latest_parallel_import'),(cp,'last_parallel_import'),(c,'last_parallel_import')]:doc[key]=copy.deepcopy(summary)
 for doc in docs.values():doc['updated_utc']=now
 docs['root']['current_component_review']=copy.deepcopy(c);assert all(cp[k]==v for k,v in before['walkthrough'].items() if k.startswith('current_')) and all(sha(PATHS[k])==v for k,v in guards.items()) and all(sha(path)==v for path,v in protected.items());write(here/'before-import.json',before);write(here/'source-manifest.json',dict(files=frozen,historical_mutable_references=historical))
 for key,path in PATHS.items():write(path,docs[key])
 write(here/'import-receipt.json',dict(status='APPLIED;INDEPENDENT_READBACK_REQUIRED',summary=summary,scopes=scopes,protected_sha256=protected,shared_after_sha256={k:sha(v) for k,v in PATHS.items()}));print(json.dumps(dict(batch=batch,status='APPLIED',scopes=len(scopes),new_working_groups=delta,total_working_groups=u['specification_approval_counts']['proposal_groups'])))
if __name__=='__main__':main(int(sys.argv[1]))
