"""Merge owner-authorized estimates, three listing images and later folder paths."""
import collections,copy,hashlib,json,posixpath,re,shutil,struct
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import quote,unquote,urlsplit,urlunsplit
H=Path(__file__).resolve().parent;BASE=H.parents[2]
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();now=lambda:datetime.now(timezone.utc).isoformat();rel=lambda p:str(Path(p).relative_to(BASE))
canon=lambda z:hashlib.sha256(json.dumps(z,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def write(p,z):Path(p).write_text(json.dumps(z,ensure_ascii=False,indent=2)+'\n')
m=read(H/'input-manifest.json')
for key,filename in [('moonspirals_native','moonspirals-native-readback.json'),('echo_native','echo-sound-native-readback.json'),('decowaves_native','decowaves-native-readback.json'),('image_decision','owner-image-decision.json'),('original_image_verification','three-image-original-verification.json')]+[(f'image{i}_metadata',f'new-image-{i}-fresh-metadata.json')for i in range(1,4)]:
 p=H/filename;t=H/'inputs'/(key+'.before');shutil.copy2(p,t);m[key]={'path':str(p),'snapshot':str(t),'sha256':sha(p)}
write(H/'input-manifest.json',m)
for k,x in m.items():assert sha(x['path'])==sha(x['snapshot'])==x['sha256'],k
overlays=[read(H/'inputs'/f'{x}_overlay.before')for x in ['moonspirals','echo','decowaves']];native=[read(H/'inputs'/f'{x}_native.before')for x in ['moonspirals','echo','decowaves']];objects={};prefixes=[]
for o,live in zip(overlays,native):
 assert o['verification']['status']=='PASS'and not live['has_more']
 for x in o['receipts']:assert sha(x['path'])==x['sha256']
 byid={x['file_id']:x for x in live['entries']};assert set(byid)=={x['file_id']for x in o['objects']}
 parents={x['current_path'].casefold():x['file_id']for x in o['objects']if x['object_type']=='folder'};parents[o['family']['path'].casefold()]=o['family']['file_id']
 for x in o['objects']:
  y=byid[x['file_id']];assert y['path']=='ns:202238505/'+x['current_path']and y['name']==x['current_name']and y['object_type']==x['object_type']
  assert parents[posixpath.dirname(x['current_path']).casefold()]==x['current_parent_id']==x['old_parent_id']
  if x['object_type']=='file':assert y['file'].get('size',0)==x['size']and x['current_name']==x['old_name']
  objects[x['file_id']]=x
 prefixes+=o['prefix_maps']
prefixes.sort(key=lambda x:len(x['old_path']),reverse=True);assert len(objects)==515 and len(prefixes)==14
def path(s):
 for p in prefixes:
  if s==p['old_path']or s.startswith(p['old_path']+'/'):return p['current_path']+s[len(p['old_path']):]
 return s
def ref(s):
 if not isinstance(s,str):return s
 if s.startswith('ns:202238505//'):return'ns:202238505/'+path('/'+s.split('//',1)[1])
 if s.startswith('/BOLDSTONE MASTER/'):return path(s)
 if not s.startswith('https://www.dropbox.com/'):return s
 p=urlsplit(s);d=unquote(p.path)
 for route in ['/home','/preview']:
  if d.startswith(route+'/'):
   new=path(d[len(route):])
   if new!=d[len(route):]:return urlunsplit((p.scheme,p.netloc,quote(route+new,safe='/'),p.query,p.fragment))
 return s
def project(x):
 for k in ['image_url','folder_url','context_image_url','context_folder_url','path','ns_path','url']:
  if k in x:x[k]=ref(x[k])
 obj=objects.get(x.get('file_id'))
 if obj and 'name'in x and x['name']==obj['old_name']:x['name']=obj['current_name']
def rebase(z):
 if isinstance(z,list):return[rebase(v)for v in z]
 if isinstance(z,dict):
  out={k:copy.deepcopy(v)if k.startswith(('historical_','prior_'))or'_before_'in k or k in ['source_ref','evidence_ref','master_ref','frozen_master']else rebase(v)for k,v in z.items()};project(out);return out
 return ref(z)
g=read(H/'inputs/master_register.before');old=copy.deepcopy(g);a=read(H/'inputs/audit.before');olda=copy.deepcopy(a)
for layer in ['options','components','aliases','source_review_reconciliation','original_specification_current_references','exceptions']:
 for x in g[layer]:project(x)
for layer in ['source_sets','source_offer_edges']:
 for x in g[layer]:project(x.get('current_primary_reference',{}))
for x in g['arrangement_context_references']:
 project(x)
 for y in x.get('images',[]):project(y)
for x in g['options']:
 for k in ['current_candidate_binding_review','current_photo_task_review','current_photo_gap_review']:
  if k in x:x[k]=rebase(x[k])
for x in a['coverage']:
 for role in ['individual','in_situ','series']:
  if x[role].get('reference'):project(x[role]['reference'])
for layer in ['missing_pictures','identity_review']:
 for x in a[layer]:
  for key in ['reference','comparison']:
   if x.get(key):project(x[key])
assets=rebase(read(H/'inputs/report_assets.before'));reviews=rebase(read(H/'inputs/report_reviews.before'))

packet=read(H/'inputs/commercial_packet.before');seal=read(H/'inputs/commercial_seal.before')
assert seal['packet']['sha256']==m['commercial_packet']['sha256']and seal['owner_instruction']['sha256']==m['commercial_owner']['sha256']
assert packet['source_register']['sha256']==m['master_register']['sha256']and sha(H/'inputs/commercial_report.before')==seal['report']['sha256']
assert packet['merge_contract']['separately_authorized_parallel_image_overlay_allowed']
byid={x['product_id']:x for x in g['options']};assert len(packet['entries'])==186 and {x['product_id']for x in packet['entries']}==set(byid)
history=[];changedfields=0;policyref={'decision_id':packet['decision_id'],'packet':m['commercial_packet'],'owner_instruction':m['commercial_owner'],'exact_amounts_individually_owner_confirmed':False,'live_platform_or_physical_verification':False}
for p in packet['entries']:
 x=byid[p['product_id']];before={k:copy.deepcopy(x['master_fields'][k])for k in ['Individual price','Availability']}
 assert before==p['before_master_fields']and canon(before)==p['before_master_fields_sha256']and x['canonical_component_id']==p['canonical_component_id']
 d=p['selling_details'];amount=d['estimated_price'];high=d['estimated_price_upper'];assert d['currency']=='GBP'and amount>0 and(high is None or high>=amount)and d['physical_stock_quantity']is None and not d['customer_listing_readiness_changed']
 history.append({'product_id':x['product_id'],'prior_current_master_fields':before,'decision_id':packet['decision_id'],'source_register_sha256':m['master_register']['sha256']})
 if p.get('retain_current_commercial_fields_exactly'):
  assert x['product_id']=='BSI-46F6DB226213'and amount==175 and d['lead_time_min_weeks']==d['lead_time_max_weeks']==1
 else:
  for field in ['Individual price','Availability']:
   f=x['master_fields'][field];physical=f['physical_verification'];f.update(copy.deepcopy(p['after'][field]))
   # The earlier Fingerprint table approved a quote-only policy, not this new
   # estimated amount. Preserve that decision without labelling it current.
   if 'explicit_owner_confirmation'in f:f['historical_explicit_owner_confirmation']=f.pop('explicit_owner_confirmation')
   f['current_commercial_instruction']=copy.deepcopy(policyref);f['source_references'].append({'current_commercial_instruction':copy.deepcopy(policyref)})
   assert f['physical_verification']==physical;changedfields+=1
 x['selling_details']=copy.deepcopy(d);x['current_commercial_policy']=({'decision_id':packet['decision_id'],'specific_owner_confirmed_commercial_fields_retained_exactly':True,'generic_new_policy_applied':False}if p.get('retain_current_commercial_fields_exactly')else copy.deepcopy(policyref))
assert changedfields==370
g.setdefault('historical_commercial_field_revisions',[]).append({'recorded_utc':now(),'decision_id':packet['decision_id'],'options':history})
g['latest_commercial_completion']={'status':'OWNER_AUTHORIZED_WORKING_PRICE_ESTIMATES_AND_MADE_TO_ORDER_POLICY','recorded_utc':now(),'packet':m['commercial_packet'],'seal':m['commercial_seal'],'owner_instruction':m['commercial_owner'],'source_report_snapshot':m['commercial_report_snapshot'],'decision_id':packet['decision_id'],'summary':packet['summary'],'current_options':186,'current_field_groups_changed':370,'specific_owner_confirmed_exception':'BSI-46F6DB226213','physical_stock_or_verified_live_prices_added':0,'source_snapshot_image_counts_not_current_publication_counts':True,'platform_or_Dropbox_writes':0}

decision=read(H/'owner-image-decision.json');assert decision['exact_owner_response']=='- Use these as standalone listing images'
originals={x['file_id']:x for x in read(H/'three-image-original-verification.json')['files']};image_updates=[]
drop_hashes={'id:cnqzTNngPVsAAAAAAA6VkQ':'c7372d4cccbd19d94408d4a9ee2ec79ca6e91046e821371245019f74c39180ee','id:cnqzTNngPVsAAAAAAA6VjQ':'d6d4dbefd3e22c1b33b555737f9776fefec9d6df9f1b2f56092452ec2cfbf76a','id:cnqzTNngPVsAAAAAAA6Vjg':'7a6aa83138409ea88910797a8b4fddbff19098e9c64c1122513bd858301bf12b'}
for i,p in enumerate(decision['scope'],1):
 meta=read(H/f'new-image-{i}-fresh-metadata.json');f=meta['file']['file'];parent=meta['parent']['folder'];x=byid[p['option_id']];blob=originals[p['file_id']];assert f['id']==p['file_id']==blob['file_id']and f['rev']==blob['rev']and f['size']==Path(blob['local_path']).stat().st_size
 data=Path(blob['local_path']).read_bytes();assert hashlib.sha256(data).hexdigest()==blob['sha256']and data.startswith(b'\x89PNG\r\n\x1a\n')
 dh=hashlib.sha256(b''.join(hashlib.sha256(data[j:j+4194304]).digest()for j in range(0,len(data),4194304))).hexdigest();assert dh==drop_hashes[p['file_id']]
 assert posixpath.dirname(f['path_display'])==parent['path_display'];folder_url='https://www.dropbox.com/home'+quote(parent['path_display'],safe='/');url=folder_url+'?preview='+quote(f['name'],safe='')
 reference={'file_id':f['id'],'folder_id':parent['id'],'name':f['name'],'path':'ns:202238505/'+f['path_display'],'image_url':url,'folder_url':folder_url,'source_sha256':blob['sha256'],'dropbox_content_hash':dh,'image_role':'Owner-accepted complete individual listing image','creation_provenance':'Photographic or generated origin unverified; not asserted to be an unedited camera photograph.'}
 prior={k:copy.deepcopy(x.get(k))for k in ['image_url','folder_url','file_id','folder_id','photo_coverage']};x.setdefault('historical_primary_references',[]).append({'recorded_utc':now(),'before_owner_listing_image_acceptance':prior})
 x.update({k:reference[k]for k in ['image_url','folder_url','file_id','folder_id']});x['photo_coverage']['individual']='Available';x['current_owner_accepted_individual_listing_image']={'reference':copy.deepcopy(reference),'owner_decision':m['image_decision'],'physical_specification_or_identity_certified':False}
 c=next(z for z in a['coverage']if z['option_id']==x['product_id']);assert c['individual']['status']=='Detail only';c['individual']['historical_reference_before_owner_acceptance']=copy.deepcopy(c['individual'])
 c['individual'].update(status='Available',reference=copy.deepcopy(reference),exact_option=True,basis='Owner accepts this full-panel image for the existing individual design and finish. Photographic or generation provenance remains unverified; no measured size, material, cast or inventory proof.',owner_acceptance=copy.deepcopy(m['image_decision']))
 task=next(z for z in a['missing_pictures']if z['option_id']==x['product_id']and z['role']=='Individual');assert task['status']=='Open';task['historical_capture_request']=copy.deepcopy(task)
 task.update(status='Resolved',reference=copy.deepcopy(reference),action='Use the owner-accepted complete standalone image for this individual listing; retain original detail/group context.',scope='Individual listing-image coverage only; in-situ/series and physical specifications retain their own evidence state.',qualification=reference['creation_provenance'],owner_response=decision['exact_owner_response'])
 review=next(z for z in reviews if z['option_id']==x['product_id']and z['role']=='Individual');review['historical_capture_review']=copy.deepcopy(review);review.update(review_state='RESOLVED_OWNER_ACCEPTED_COMPLETE_INDIVIDUAL_LISTING_IMAGE',finding=task['qualification'],next_action=task['action'],source_reference=copy.deepcopy(reference),owner_decision=copy.deepcopy(m['image_decision']))
 assets[f['id']]={'file_id':f['id'],'folder_id':parent['id'],'name':f['name'],'path':reference['path'],'image_url':url,'folder_url':folder_url,'full':blob['local_path'],'thumb':blob['local_path'],'source_sha256':blob['sha256']}
 image_updates.append({'product_id':x['product_id'],'name':x['name'],'prior':prior,'reference':reference,'pixels_unchanged':True,'width_height':list(struct.unpack('>II',data[16:24]))})
assert len(image_updates)==3
for x in g['current_listing_resolution_details']['entries']:
 oid=x['product_id'];x['accepted_working_fields']=copy.deepcopy(byid[oid]['master_fields'])
 for draftkey in ['draft_listing','custom_unlisted_pattern_draft']:
  d=x.get(draftkey)
  if isinstance(d,dict)and'six_working_fields'in d:d['six_working_fields']=copy.deepcopy(byid[oid]['master_fields']);d['six_working_fields_sha256']=canon(d['six_working_fields'])
 if oid in {z['product_id']for z in image_updates}:
  x['current_individual_listing_image']=copy.deepcopy(byid[oid]['current_owner_accepted_individual_listing_image'])
  if x.get('draft_listing'):x['draft_listing']['media_condition']='Use the owner-accepted complete standalone listing image, retaining unverified photographic/generation provenance. In-situ and series requirements remain separate; no publication or platform match is asserted.'

counts=a['counts'];counts['individual_statuses']={'Available':167,'Detail only':2,'Group only':16,'Unbound identity':1};counts['actions_by_role']['Individual']=19;counts['actions_by_type']['Find / capture']=97;counts['resolved_action_rows']=54;counts['active_action_rows']=151;counts['required_picture_actions']=98
a['individual_capture_queue_counts']={'individual_gaps':19,'separate_photographs_required':18,'legacy_identity_deferred':1,'approved_crop_actions':0,'historical_crop_candidates_declined':13,'new_owner_accepted_individual_listing_images':3}
scope={'status':'CURRENT_MOONSPIRALS_ECHO_DECOWAVES_PATHS_AND_THREE_ACCEPTED_INDIVIDUAL_IMAGES','recorded_utc':now(),'path_overlays':[m['moonspirals_overlay'],m['echo_overlay'],m['decowaves_overlay']],'folder_renames':14,'stable_native_objects_verified':515,'stable_native_file_IDs_and_sizes':485,'native_parent_IDs_unchanged':True,'image_decision':m['image_decision'],'accepted_individual_images':image_updates,'individual_roles_closed':3,'in_situ_or_series_roles_closed':0,'new_components_or_options':0,'new_measured_physical_specifications':0,'root_Dropbox_or_platform_writes':0}
g['latest_catalogue_followup']=copy.deepcopy(scope);a['latest_catalogue_followup']=copy.deepcopy(scope);a['recorded_utc']=now();a['status']='CURRENT_OWNER_ACCEPTED_INDIVIDUAL_LISTING_IMAGES_AND_COMMERCIAL_COMPLETION'
g['current_individual_photo_capture_policy']['current_requirements']={'individual_gaps':19,'separate_individual_images_required':18,'deferred_identity':1,'owner_accepted_standalone_listing_images':3,'other_thirteen_crop_requests_remain_declined':True}
a['current_individual_photo_capture_policy']=copy.deepcopy(g['current_individual_photo_capture_policy']);a['primary_reference_changes']+=copy.deepcopy(image_updates)
write(H/'image-coverage-current.json',a);g['historical_image_coverage_audits'].append(copy.deepcopy(g['latest_image_coverage_audit']))
g['latest_image_coverage_audit'].update(recorded_utc=now(),path=str(H/'image-coverage-current.json'),audit=rel(H/'image-coverage-current.json'),audit_sha256=sha(H/'image-coverage-current.json'),counts=copy.deepcopy(counts),verification=rel(H/'saved-file-verification.json'),visual_verification=rel(H/'visual-verification.json'),scope='186 current options; three owner-accepted standalone listing images close individual-image roles, with photographic provenance unverified.19individual gaps (18separate images and1deferred identity),61in situ and18series gaps remain. No crops created.')
for k in ['verification_sha256','visual_verification_sha256']:g['latest_image_coverage_audit'].pop(k,None)
write(H/'canonical-master-register.json',g);write(H/'photo-review-queue.json',reviews);write(H/'current-assets.json',assets);write(H/'image-updates.json',image_updates);write(H/'native-and-originals-verification.json',{'status':'PASS','native_objects_verified':515,'file_IDs_sizes_and_parent_IDs_preserved':485,'folder_renames':14,'new_individual_images':3,'native_revisions_and_local_bytes_verified':True,'photographic_origin_certified':False,'root_native_writes':0})
assert g['summary']==old['summary']and len(g['options'])==186 and len(g['components'])==112 and g['original_review_specification_assertions']==old['original_review_specification_assertions']
for x,y in zip(g['options'],old['options']):
 assert all(x[k]==y[k]for k in ['product_id','canonical_component_id','name','family','specifications'])
 for field in ['Dimensions / depth','Weight','Material / finish','Fixing']:assert x['master_fields'][field]==y['master_fields'][field]
 for field in x['master_fields']:assert x['master_fields'][field]['physical_verification']==y['master_fields'][field]['physical_verification']
assert next(x for x in g['options']if x['product_id']=='BSI-46F6DB226213')['master_fields']==next(x for x in old['options']if x['product_id']=='BSI-46F6DB226213')['master_fields']
def diff(x,y,p=[]):
 if x==y:return[]
 if isinstance(x,dict)and isinstance(y,dict):
  out=[]
  for k in sorted(set(x)|set(y)):
   if k not in x:out.append({'path':p+[k],'kind':'added','after':y[k]})
   elif k not in y:out.append({'path':p+[k],'kind':'removed','before':x[k]})
   else:out+=diff(x[k],y[k],p+[k])
  return out
 if isinstance(x,list)and isinstance(y,list)and len(x)==len(y):return[z for i,(v,w)in enumerate(zip(x,y))for z in diff(v,w,p+[i])]
 return[{'path':p,'kind':'changed','before':x,'after':y}]
write(H/'register-change-log.json',diff(old,g));write(H/'audit-change-log.json',diff(olda,a))
write(H/'preparation-verification.json',{'status':'PASS','options':186,'components':112,'commercial_fields_changed':370,'specific_owner_exception_preserved_exactly':True,'other_four_working_fields_and_all_original_specifications_preserved':True,'folder_renames':14,'new_owner_accepted_listing_images':3,'individual_gaps':19,'separate_individual_images_required':18,'deferred_identity':1,'in_situ_gaps':61,'series_gaps':18,'required_picture_actions':98,'current_resolved_actions':54,'new_physical_specification_verifications':0})
print(json.dumps(read(H/'preparation-verification.json')))
