import json,hashlib,copy,collections,posixpath
from pathlib import Path
from urllib.parse import quote,unquote,urlsplit,parse_qs
from datetime import datetime,timezone
H=Path(__file__).resolve().parent;B=H.parents[2];read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();now=lambda:datetime.now(timezone.utc).isoformat()
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
m=read(H/'input-manifest.json');scope=read(H/'scope.json');cross=read(H/'native-current-crosswalk.json');objects=cross['current_objects'];oldpaths=cross['old_path_to_id'];old=read(H/'inputs/master_register.before');g=copy.deepcopy(old);a=read(H/'inputs/audit.before');assets=read(H/'inputs/report_assets.before');reviews=read(H/'inputs/report_reviews.before');oldparent=cross['historical_Acanthus_parent_id'];newparent=cross['recreated_Acanthus_parent_id'];restored={x['file_id']for x in cross['restored_sources']}
for k,x in m.items():assert sha(x['path'])==sha(x['snapshot'])==x['sha256'],k
def ref(fid):
 x=objects[fid];assert x['object_type']=='file';p=x['display_path'];return{'file_id':fid,'folder_id':x['parent_id'],'name':x['name'],'path':x['path'],'image_url':'https://www.dropbox.com/preview'+quote(p,safe='/'),'folder_url':'https://www.dropbox.com/home'+quote(posixpath.dirname(p),safe='/'),'native_reference_status':'VERIFIED_CURRENT_ID_AND_ACTUAL_PARENT','physical_cast_or_size_certified':False}
def urlid(s):
 if not isinstance(s,str)or not s.startswith('https://www.dropbox.com/'):return None
 u=urlsplit(s);p=unquote(u.path)
 for r in ['/home','/preview']:
  if p.startswith(r+'/'):
   p=p[len(r):];name=parse_qs(u.query).get('preview',[''])[0];return oldpaths.get((p+('/'+name if name else '')).casefold())
 return None
def currenturl(s):
 fid=urlid(s)
 if fid==oldparent:fid=newparent
 if fid not in objects:return s
 x=objects[fid];return'https://www.dropbox.com/'+('preview'if x['object_type']=='file'else'home')+quote(x['display_path'],safe='/')
def project(z):
 if isinstance(z,list):return[project(x)for x in z]
 if not isinstance(z,dict):return currenturl(z)
 out={k:copy.deepcopy(v)if k.startswith(('historical_','prior_','original_','before_'))or k in ['specifications','master_fields','accepted_working_fields','six_working_fields','evidence_ref','master_ref','source_ref']else project(v)for k,v in z.items()}
 for fk,pk,ik,uk in [('file_id','folder_id','image_url','folder_url'),('context_file_id','context_folder_id','context_image_url','context_folder_url')]:
  fid=out.get(fk)
  if fid in objects and objects[fid]['object_type']=='file':
   r=ref(fid)
   for key,value in [(pk,r['folder_id']),(ik,r['image_url']),(uk,r['folder_url'])]:
    if key in out:out[key]=value
   if 'path'in out:out['path']=r['path']
   if fid in restored:
    archive={k:out[k]for k in ['native_reference_status','archived_original','archived_original_sha256','current_family_navigation_url','folder_id']if k in out}
    out.setdefault('historical_native_unavailability',[]).append(archive);out['native_reference_status']='RESTORED_ORIGINAL_FILE_ID_VERIFIED_NEW_PARENT_ID'
    for k in ['archived_original','archived_original_sha256','current_family_navigation_url','historical_file_and_parent_IDs_retained']:out.pop(k,None)
    out['historical_parent_id']=oldparent
 return out
layers=['options','components','aliases','source_review_reconciliation','original_specification_current_references','exceptions','arrangement_context_references','current_listing_resolution_details','current_listing_source_links','current_listing_match_evidence','current_listing_issues']
for layer in layers:
 if layer in g:g[layer]=project(g[layer])
for layer in ['source_sets','source_offer_edges']:
 for x in g[layer]:
  if 'current_primary_reference'in x:x['current_primary_reference']=project(x['current_primary_reference'])
for layer in ['coverage','missing_pictures','identity_review']:a[layer]=project(a[layer])
reviews=project(reviews);assets=project(assets);opts={x['product_id']:x for x in g['options']};covs={x['option_id']:x for x in a['coverage']};packets={k:read(v)for k,v in scope['approvals'].items()};full=[];accepted=[];specids=[]
def packetref(k):return{'path':scope['approvals'][k],'sha256':sha(scope['approvals'][k]),'decision_id':packets[k]['decision_id']}
def resolve_action(oid,did,kind,basis,r,answer):
 for x in a['missing_pictures']:
  if x['option_id']==oid and x['role']=='Individual'and x['status']=='Open':
   x.setdefault('historical_actions',[]).append(copy.deepcopy(x));x.update(status='Resolved',action_type='Find / capture',action=kind,reference=copy.deepcopy(r),qualification=basis,owner_response=answer,owner_decision_id=did,resolution_kind='COMPLETE_INDIVIDUAL_IMAGE'if oid in full else'OWNER_ACCEPTED_QUALIFIED_REFERENCE',technical_separate_photo_available=oid in full)
 for x in reviews:
  if x.get('option_id',x.get('product_id'))==oid and x.get('role')=='Individual':x.update(review_state='OWNER_ACCEPTED_CURRENT_REFERENCE',finding=basis,next_action='Individual listing-reference review accepted. Keep remaining context and physical checks separate.',owner_decision_id=did,source_reference=copy.deepcopy(r))
for k,d in packets.items():
 if 'accepted_reference'not in d:continue
 oid=d['product_id'];o=opts[oid];c=covs[oid];r=ref(d['accepted_reference']['file_id']);assert r['folder_id']==d['accepted_reference']['folder_id'];full.append(oid);c.setdefault('historical_individual_references',[]).append(copy.deepcopy(c['individual']))
 basis=d['visual_basis']+' Owner explicitly accepts this complete individual listing image. Photographic/generated origin and exact physical cast remain unverified; no crop or image edit created.'
 c['individual']={'status':'Available','reference':r,'basis':basis,'exact_option':True,'physical_cast_or_size_certified':False,'owner_acceptance':packetref(k)};c['notes'].append(basis);c['owner_review']=d['decision_id'];c['scene_origin']+=' Individual listing image creation origin remains unconfirmed.'
 for key in ['file_id','folder_id','image_url','folder_url']:o[key]=r[key]
 o['native_reference_status']=r['native_reference_status'];o['current_full_individual_image']=copy.deepcopy(r);o['photo_coverage']['individual']='Available';o['current_photo_gap_review']={'status':'OWNER_ACCEPTED_COMPLETE_INDIVIDUAL_IMAGE','reference':r,'approval':packetref(k),'creation_origin_unverified':True}
 resolve_action(oid,d['decision_id'],'Owner-approved complete individual image now available.',basis,r,d['owner_instruction']['text'])
# Record scoped qualified working confirmations without changing their values or source assertions.
for k in ['ffs1-spec','raked1-spec']:
 d=packets[k]
 for target in d['options']:
  oid=target['product_id'];o=opts[oid];specids.append(oid)
  for f,display in target['current_displays_approved_as_working'].items():
   v=o['master_fields'][f];assert v['display']==display,(oid,f);before=copy.deepcopy(v);v.setdefault('historical_working_revisions',[]).append({'before':before,'decision_id':d['decision_id']});v['explicit_owner_confirmation']={'decision_id':d['decision_id'],'instruction':packetref(k),'scope':d['scope'],'qualified_working_value_accepted':True,'actual_physical_value_verified':False};v['state']+='\nExplicit owner confirmation23October2026 of this qualified working detail; estimates and unknowns retained.';v['basis']+='\nDirect scoped owner confirmation23October2026. The accepted wording retains its estimate, hypothesis, historical-source and offered-choice qualifications.';v.setdefault('source_references',[]).append({'owner_confirmation':packetref(k)});assert v['physical_verification']==before['physical_verification']
  g.setdefault('owner_working_specification_confirmations',[]).append({'decision_id':d['decision_id'],'option_id':oid,'fields':target['approved_working_field_groups'],'scope':d['scope'],'source':packetref(k),'physical_verification':False})
  for z in g['current_listing_resolution_details']['entries']:
   if z['product_id']==oid:
    z['accepted_working_fields']=copy.deepcopy(o['master_fields'])
    if z.get('draft_listing'):z['draft_listing']['six_working_fields']=copy.deepcopy(o['master_fields'])
# Accept existing references as an explicit owner exception, retaining technical Group-only coverage.
for k in ['frozen-fish-references','raked1-references','raked2-references','moon-shellwave1-reference']:
 d=packets[k];targets=d.get('current_bound_options')or[{'product_id':d['product_id']}]
 for target in targets:
  oid=target['product_id'];o=opts[oid];c=covs[oid];r=c['individual']['reference'];extra=[]
  for role in d.get('approved_reference_roles',[]):
   src=role['source'];nr=ref(src['id']);extra.append({**copy.deepcopy(role),'reference':nr})
  basis=d.get('current_review_outcome',d.get('requested_register_change',''))
  approval={'approval':packetref(k),'technical_individual_status_retained':c['individual']['status'],'basis':basis,'references':extra or[{'role':'existing_current_family_reference','reference':copy.deepcopy(r)}],'separate_full_image_verified':False,'no_repeat_individual_capture_prompt':True,'physical_verification_added':False}
  o['owner_accepted_listing_references']=copy.deepcopy(approval);o['owner_image_review_disposition']='OWNER_ACCEPTED_EXISTING_QUALIFIED_REFERENCE';c['owner_accepted_listing_references']=copy.deepcopy(approval);c['individual']['owner_review_disposition']='ACCEPTED_FOR_LISTING_REFERENCE_WITH_TECHNICAL_SOURCE_ROLE_RETAINED';c['individual']['owner_acceptance']=packetref(k);c['notes'].append(basis);c['owner_review']=d['decision_id']
  if k=='frozen-fish-references':o['owner_source_process_qualification']={'statement':d['owner_source_process_statement'],'per_file_process_assignment':None,'qualification':d['classification_qualification']}
  if c['individual']['status']!='Available':
   accepted.append(oid);resolve_action(oid,d['decision_id'],'Owner accepts existing qualified listing reference; separate-photo request closed by scoped exception.',basis,r,d['exact_owner_message'])
for k in packets:g.setdefault('imported_owner_review_packets',[]).append({**packetref(k),'imported_utc':now(),'no_physical_or_platform_verification_added':True})
for x in read(H/'download-verification.json')['files']:assets[x['file_id']]={'thumb':x['local_original'],'original':x['local_original'],'sha256':x['sha256'],'file_id':x['file_id'],'pixels_edited':False,'native_reference_status':'VERIFIED_CURRENT_ID_AND_ACTUAL_PARENT'}
for oid in ['BSI-C41824131174','BSI-3635E3DC3434']:
 o=opts[oid];o.setdefault('source_location_repairs',[]).append({'restored_file_ids':sorted(restored),'current_parent_id':newparent,'historical_parent_id':oldparent,'original_bytes_unchanged':True,'owner_component_positions_unchanged':True});o['source_scope_notes']+=' Acanthus detail/workshop source links restored23October2026; same original file IDs, recreated containing folder ID recorded. Existing photo-role limitations remain.'
active=[x for x in a['missing_pictures']if x['status']!='Resolved'];opened=[x for x in a['missing_pictures']if x['status']=='Open'];ind=[x for x in opened if x['role']=='Individual'];cap=[x for x in ind if x['action_type']=='Find / capture'];counts=a['counts'];counts.update(individual_options=len(g['options']),individual_statuses=dict(collections.Counter(x['individual']['status']for x in a['coverage'])),in_situ_statuses=dict(collections.Counter(x['in_situ']['status']for x in a['coverage'])),series_statuses=dict(collections.Counter(x['series']['status']for x in a['coverage'])),actions_by_role=dict(collections.Counter(x['role']for x in active)),actions_by_type=dict(collections.Counter(x['action_type']for x in active)),action_rows=len(a['missing_pictures']),active_action_rows=len(active),resolved_action_rows=sum(x['status']=='Resolved'for x in a['missing_pictures']),required_picture_actions=len(opened),technical_individual_reference_gaps=sum(x['individual']['status']!='Available'for x in a['coverage']),outstanding_individual_image_or_identity_actions=len(ind),separate_individual_photographs_required=len(cap),owner_accepted_group_or_combined_reference_exceptions=len(accepted),archived_source_files_currently_not_found=0)
assert len(full)==7 and len(accepted)==5 and len(ind)==6 and len(cap)==5
assert counts['individual_statuses']=={'Available':177,'Detail only':1,'Unbound identity':1,'Group only':9}
assert len(opened)==87 and counts['in_situ_statuses']['No verified image']==63 and counts['series_statuses']['No verified image']==18
for x in g['options']:
 before=next(z for z in old['options']if z['product_id']==x['product_id']);assert x['canonical_key']==before['canonical_key']and x['canonical_component_id']==before['canonical_component_id'];assert x['specifications']==before['specifications'];assert x['selling_details']==before['selling_details']
 for f in x['master_fields']:assert x['master_fields'][f]['display']==before['master_fields'][f]['display']and x['master_fields'][f]['physical_verification']==before['master_fields'][f]['physical_verification']
assert g['original_review_specification_assertions']==old['original_review_specification_assertions']
result={'status':'APPROVED_IMAGES_AND_CURRENT_FOLDER_REFERENCES_IMPORTED','recorded_utc':now(),'scope':scope,'complete_individual_images_added':full,'owner_accepted_qualified_reference_exceptions':accepted,'working_spec_confirmation_options':specids,'working_fields_explicitly_confirmed':12,'current_options':188,'working_component_identities':112,'working_field_groups':1128,'current_counts':copy.deepcopy(counts),'new_physical_verifications':0,'new_platform_writes':0,'same_file_id_restores':cross['restored_sources']}
g['latest_approved_images_folder_refresh']=copy.deepcopy(result);a['latest_approved_images_folder_refresh']=copy.deepcopy(result);a['recorded_utc']=now();a['status']='CURRENT_APPROVED_IMAGES_FOLDER_REFRESH_2026_10_23';g['historical_image_coverage_audits'].append(copy.deepcopy(g['latest_image_coverage_audit']))
write(H/'image-coverage-current.json',a);g['latest_image_coverage_audit'].update(recorded_utc=now(),path=str(H/'image-coverage-current.json'),audit=str((H/'image-coverage-current.json').relative_to(B)),audit_sha256=sha(H/'image-coverage-current.json'),counts=copy.deepcopy(counts),scope='188 current options; seven complete images and five scoped accepted-reference exceptions; current folder IDs and restored Acanthus originals verified.',status=a['status'])
for k in ['verification_sha256','visual_verification_sha256','independent_verification','independent_verification_sha256','native_binding_verification_sha256']:g['latest_image_coverage_audit'].pop(k,None)
g['latest_image_coverage_audit'].update(verification=str((H/'saved-file-verification.json').relative_to(B)),visual_verification=str((H/'visual-verification.json').relative_to(B)))
write(H/'canonical-master-register.json',g);write(H/'current-assets.json',assets);write(H/'photo-review-queue.json',reviews);write(H/'preparation-verification.json',result)
state=read(H/'inputs/guided_state.before');state.setdefault('historical_states',[]).append(copy.deepcopy({k:v for k,v in state.items()if k!='historical_states'}));state.update(status='CURRENT_IMPORT_COMPLETE_ACANTHUS_PHYSICAL_REVIEW_PENDING',current_phase='individual',current_position=0,current_option_id='BSI-C41824131174',queues={'individual':[x['option_id']for x in ind if x['action_type']=='Find / capture'],'in_situ':[x['option_id']for x in opened if x['role']=='In situ'],'series':[x['option_id']for x in opened if x['role']=='Series']},deferred_identity_option_ids=['BSI-04D6E8690F30'],no_repeat_individual_prompt_option_ids=accepted,working_specification_question='Actual Acanthus Sandstone dimensions/depth, weighed mass, recipe and fitted hardware requested; no answer inferred.')
write(H/'guided-owner-review-state.json',state)
print(json.dumps({'status':result['status'],'complete_images':7,'accepted_reference_exceptions':5,'working_confirmations':12,'outstanding_individual_entries':6,'individual_capture':5,'in_situ':63,'series':18,'required_actions':87,'physical_upgrades':0}))
