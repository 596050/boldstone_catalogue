"""Normalise legacy component working views without rewriting source evidence."""
import copy,json
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import quote
from import_bulk_working_95_96 import ROOT,PATHS,read,write,sha,at,FIELDS,specification_counts

SOURCE=ROOT/'components/reviews/root-remaining-normalization-2026-10-20'
HERE=ROOT/'components/reviews/parallel-import-2026-10-19-batch97'
rel=lambda p:str(Path(p).relative_to(ROOT))

def main():
 docs={k:read(v) for k,v in PATHS.items()};u,p,cp,c=(docs[k] for k in ['user','progress','walkthrough','component'])
 if (HERE/'import-receipt.json').exists():
  assert all(at(p,x['model_locator'])['all_six_working_specification_fields_accepted'] for x in read(HERE/'import-receipt.json')['scopes'])
  print(json.dumps(dict(batch=97,status='ALREADY_IMPORTED_IDEMPOTENT_NO_WRITE')));return
 before=copy.deepcopy(docs);guards={k:sha(v) for k,v in PATHS.items()};assert cp['last_parallel_import']['batch']==96 and docs['root']['current_component_review']==c
 prepared=read(SOURCE/'ROOT97_PREPARED.json');assert len(prepared['cards'])==12
 critique=read(ROOT/'components/parallel-reviews/root97-independent-audit-by-a-2026-10-20/PREIMPORT_CRITIQUE.json')
 assert critique['status']=='PASS' and critique['check_count']==41 and sha(SOURCE/'ROOT97_PREPARED.json')==critique['live_prepared_sha256_at_capture']==sha(critique['prepared_snapshot']['path'])
 # The independent critique is retained with the exact reviewed preparation.
 frozen=[]
 def freeze(path):
  path=Path(path);digest=sha(path);dest=HERE/'sources'/(digest+path.suffix);dest.parent.mkdir(parents=True,exist_ok=True)
  if dest.exists():assert sha(dest)==digest
  else:dest.write_bytes(path.read_bytes())
  frozen.append(dict(source=str(path),snapshot=rel(dest),sha256=digest))
 for path in SOURCE.iterdir():
  if path.is_file():freeze(path)
 freeze(ROOT/'components/parallel-reviews/root97-independent-audit-by-a-2026-10-20/PREIMPORT_CRITIQUE.json')
 freeze(critique['prepared_snapshot']['path'])
 media=read(SOURCE/'CACHED_IMAGE_CHECK.json')['selected']+read(SOURCE/'CONTEXT_IMAGE_CHECK.json')['selected']
 for x in media:assert sha(x['cached_path'])==x['sha256'];freeze(x['cached_path'])
 plates=sorted(SOURCE.glob('ROOT_*_COMPARISON_*.jpg'));assert len(plates)==8
 write(HERE/'parent-visual-inspection.json',dict(status='PASS',all_eight_comparison_plates_actually_inspected=True,inspection='Root visually inspected these five primary and three context plates earlier in this continuous task, before this import.',plates=[dict(path=rel(x),sha256=sha(x)) for x in plates],limits='Selected cached first-frame native or derivative depictions only; no scene authentication, whole-library census, physical measurement or complete multi-frame certification.'))
 heads={}
 for name in ['CURRENT_METADATA.json','CONTEXT_CURRENT_METADATA.json']:
  for x in read(SOURCE/name)['metadata']:heads[x[x['metadata_type']]['id']]=x[x['metadata_type']]
 contexts=read(SOURCE/'CONTEXT_IMAGE_CHECK.json')['selected'];policy=p['working_specification_acceptance_policy'];now=datetime.now(timezone.utc).isoformat();scopes=[]
 protected={str(path):sha(path) for path in [ROOT/cp['register_workbook'],ROOT/'components/evidence/component_register.json',ROOT.parent/'Boldstone_Wall_Sculptures_Matched_All_Fields_2026-10-15.xlsx']}
 def reference(node,x):
  h,f=heads[x['file_id']],heads[x['folder_id']];assert h['path_display'].rsplit('/',1)[0]==f['path_display']
  image='https://www.dropbox.com/home'+quote(f['path_display'],safe='/')+'?preview='+quote(h['name'])
  node['current_dropbox_reference']=dict(file_id=h['id'],folder_id=f['id'],file_path=h['path_display'],folder_path=f['path_display'],file_revision=h['rev'],file_bytes=h['size'],image_url=image,folder_url='https://www.dropbox.com/home'+quote(f['path_display'],safe='/'),checked_utc=read(SOURCE/'CURRENT_METADATA.json')['checked_utc'])
 def photo(cid,scope,node,name,x):
  key=cid+'|'+scope;selected=[z for z in contexts if key in z['scopes']];old=copy.deepcopy(node.get('photo_coverage',{}));old=old if isinstance(old,dict) else dict(historical_photo_coverage=old)
  ids=[z['file_id'] for z in selected];old.update(contextual_images_available=bool(ids),contextual_file_ids=ids,contextual_source_status='Available: selected room/arrangement presentation; provenance unverified' if ids else 'Selected product depiction; wider-room/series unestablished in bounded review',contextual_source_description='; '.join(z['role'] for z in selected)+'. Selected cached references inspected with current native file/folder metadata. Derivative limits retained; no installed-scene or same-cast authentication. Earlier photo evidence retained.',installation_provenance='UNCONFIRMED',exact_physical_cast_identity_verified=False,rear_paired_to_selected_front=False);node['photo_coverage']=old
  front='Complete individual front depiction linked; physical-cast and camera/edit provenance unverified.'
  if cid.startswith('AM-'):front+=' Existing split component image retained; edit lineage unverified.'
  if cid=='BC-BR-2':front+=' Selected cached derivative only; native-original binary not verified.'
  room='Selected room presentation available; solo component in-situ view unestablished in bounded review, elsewhere unknown.' if cid.startswith('AM-') else 'Selected room/context available; installation and exact-cast provenance unverified.' if any('room' in z['role'].lower() for z in selected) else 'Wider-room/in-situ view unestablished in bounded review; historical evidence retained, elsewhere unknown.'
  series='Existing pair/series presentation retained; no new component count or set-value division.' if any(('pair' in z['role'].lower() or 'diptych' in z['role'].lower() or 'series' in z['role'].lower()) for z in selected) else 'Matching series view unestablished in bounded review, elsewhere unknown.'
  gapkey=key if scope=='BASE' else scope
  p['current_component_photograph_gaps'][gapkey]=dict(component_id=cid,size_finish_variant_id=scope,photo_gap_id=gapkey,review_scope='BASE' if scope=='BASE' else 'VARIANT',model_locator=['reviews',cid]+([] if scope=='BASE' else ['size_finish_variants',scope]),canonical_name=name,finish='Exact kept component/finish',front=front,room=room,series=series,evidence='Selected primary and available room/pair references retained with stable Dropbox IDs. Native originals versus derivative-only evidence remains explicit. No photo absence inferred outside this bounded packet.',missing='Authenticated installation, exact front/back pairing and calibrated side/profile unestablished for the selected cast in bounded review; elsewhere unknown.',review_record=rel(SOURCE/'CURRENT_REFERENCE_BINDING.json'))
 for d in prepared['cards']:
  cid,scope=d['component_id'],d['scope'];loc=['reviews',cid]+([] if scope=='BASE' else ['size_finish_variants',scope]);node=at(p,loc);assert node==d['source_node_snapshot'],(cid,scope)
  assert set(d['specifications'])==set(FIELDS) and len(set(d['approved_proposal_ids']))==6
  approval=rel(HERE/(cid+'--'+scope+'-working-approval.json'));decision=copy.deepcopy(d);decision.pop('source_node_snapshot');decision.update(approval_record=approval,proposals_approved=True,working_acceptance_basis='DERIVED_FROM_STANDING_OWNER_POLICY',canonical_shared_policy_id=policy['policy_id'],root_imported_utc=now,model_locator=loc,physical_specs_verified=False,actual_stock_verified=False)
  if scope!='BASE':decision['size_finish_variant_id']=scope
  ledger='specification_decisions' if scope=='BASE' else 'size_finish_variant_specification_decisions';assert not any(x.get('decision_id')==d['decision_id'] for x in u.get(ledger,[]));u.setdefault(ledger,[]).append(decision)
  active=copy.deepcopy(d['specifications'])
  for x in active.values():x['status']='WORKING_ACCEPTED_UNDER_STANDING_POLICY; '+x.get('status','SOURCE_QUALIFIED');assert x['owner_approved'] and not x['physical_value_verified']
  node.update(proposals_approved=True,specifications_approved=True,owner_estimates_accepted=True,all_six_working_specification_fields_accepted=True,approved_proposal_ids=copy.deepcopy(d['approved_proposal_ids']),specification_approval=approval,accepted_working_specifications=active,working_specifications_approval_scope='EXACT_FINISH_ALL_SIX_WORKING_VALUES',source_specification_proposals_retained_unchanged=True,physical_specs_verified=False,actual_stock_verified=False,working_acceptance_basis='DERIVED_FROM_STANDING_OWNER_POLICY',standing_working_approval_policy_id=policy['policy_id'],owner_answer_for_this_scope=None,specification_status_display='Six working fields recorded under standing instruction; source conflicts and unknown actual values retained',historical_scope_before_working_acceptance=copy.deepcopy(node.get('scope')),scope='Working values accepted for this existing scope; no new individual owner reply. '+d['scope_note']+' Actual measurements, hardware/load, current offers/stock and scene provenance remain source qualified or unverified.')
  reference(node,d['current_reference']);photo(cid,scope,node,d['canonical_name'],d['current_reference']);write(ROOT/approval,decision)
  p['pending_specification_checks'][cid+'|'+scope+'-WORKING-SPECS-01']=dict(owner_answer_recorded=False,standing_policy_acceptance_recorded=True,individual_owner_reply_required=False,working_values_accepted=True,actual_specification_fields_pending=FIELDS,physical_specs_verified=False,approval_record=approval)
  scopes.append(dict(component_id=cid,size_finish_variant_id=scope,review_scope='BASE' if scope=='BASE' else 'VARIANT',model_locator=loc,ledger=ledger,decision_id=d['decision_id'],approval_record=approval,photo_gap_id=cid+'|'+scope if scope=='BASE' else scope))
 bar=prepared['existing_Barbados_display_recovery'];node=p['reviews'][bar['component_id']];assert node==bar['source_node_snapshot']
 # This is an output projection of the existing six owner-kept groups, not a
 # new decision or a rewrite of their original structured source dictionaries.
 node.update(accepted_working_specifications=copy.deepcopy(bar['specifications']),working_specifications_approval_scope='EXACT_FINISH_ALL_SIX_WORKING_VALUES',all_six_working_specification_fields_accepted=True,specification_status_display='Six previously accepted working groups displayed; physical values and stock unverified')
 x=next(x for x in read(SOURCE/'CACHED_IMAGE_CHECK.json')['selected'] if x['scope']=='BC-BAR-WAVE|BASE');reference(node,x);photo('BC-BAR-WAVE','BASE',node,node.get('canonical_name','Barbados Wave'),x)
 p['working_review_reference_dispositions']=copy.deepcopy(prepared['reference_dispositions'])
 port=p['reviews']['BC-PORTMAN-1'];x=next(x for x in read(SOURCE/'CACHED_IMAGE_CHECK.json')['selected'] if x['scope']=='BC-PORTMAN-1|BASE');reference(port,x)
 u['specification_approval_counts']=specification_counts(u);delta=u['specification_approval_counts']['proposal_groups']-before['user']['specification_approval_counts']['proposal_groups'];assert delta==70,(delta,u['specification_approval_counts']);c['interactive_review_state']['approved_proposal_groups']=u['specification_approval_counts']['proposal_groups']
 summary=dict(batch=97,recorded_utc=now,receipt=rel(HERE/'import-receipt.json'),scope_kind='LEGACY_COMPONENT_WORKING_VIEW_NORMALIZATION_AND_REFERENCE_DISPOSITIONS',scopes=scopes,new_working_specification_approvals=12,resulting_working_fields=72,new_accepted_working_proposal_groups=70,prior_commercial_groups_retained_without_recounting=2,existing_six_field_display_recovery=['BC-BAR-WAVE|BASE'],reference_dispositions=copy.deepcopy(prepared['reference_dispositions']),new_owner_policy_events=0,new_individual_owner_reply_events=0,new_name_approvals=0,new_physically_verified_specification_groups=0,new_registered_BC_component_ids=[],root_new_private_original_downloads=0,remote_mutations=0,workbook_export_pending=True)
 cp['parallel_import_queue'].append(dict(scope_kind=summary['scope_kind'],receipt=rel(SOURCE/'ROOT97_PREPARED.json'),receipt_sha256=sha(SOURCE/'ROOT97_PREPARED.json'),approval_imported=True,evidence_imported=True,import_receipt=summary['receipt'],workbook_export_pending=True,status='TWELVE_EXISTING_SCOPES_WORKING;ONE_PRIOR_DISPLAY_RECOVERY;TWO_REFERENCES'))
 c['parallel_import_queue']=copy.deepcopy(cp['parallel_import_queue'])
 for doc,key in [(p,'latest_parallel_import'),(cp,'last_parallel_import'),(c,'last_parallel_import')]:doc[key]=copy.deepcopy(summary)
 for doc in docs.values():doc['updated_utc']=now
 docs['root']['current_component_review']=copy.deepcopy(c)
 assert all(cp[k]==v for k,v in before['walkthrough'].items() if k.startswith('current_')) and all(sha(PATHS[k])==v for k,v in guards.items()) and all(sha(path)==v for path,v in protected.items())
 write(HERE/'before-import.json',before);write(HERE/'source-manifest.json',dict(files=frozen))
 for key,path in PATHS.items():write(path,docs[key])
 write(HERE/'import-receipt.json',dict(status='APPLIED;INDEPENDENT_READBACK_REQUIRED',summary=summary,scopes=scopes,protected_sha256=protected,shared_after_sha256={k:sha(v) for k,v in PATHS.items()}))
 print(json.dumps(dict(batch=97,status='APPLIED',scopes=12,new_groups=70,total_groups=u['specification_approval_counts']['proposal_groups'])))
if __name__=='__main__':main()
