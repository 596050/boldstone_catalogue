"""Import one sealed navigation change and four exact owner photo policies."""
import copy, hashlib, json, shutil
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import quote

H=Path(__file__).resolve().parent; B=H.parents[2]; OUT=B/'outputs'/H.name
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
now=lambda:datetime.now(timezone.utc).isoformat()
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def display(p):return '/'+p.split('//',1)[1].lstrip('/') if p.startswith('ns:') else p
def namespaced(p):return 'ns:202238505/'+display(p)
assert not (H/'import-summary.json').exists(), 'Prepared input is immutable'
(H/'inputs').mkdir(exist_ok=True); OUT.mkdir(parents=True,exist_ok=True)
p=read(B/'current-master.json'); OLD=(B/p['register']).parent
assert p['register_sha256']=='5016039da1ca1d5c5a3b7d2ede3128e68ba2bf3fcab4d33e985dc8b0abcd7cdc'
oldout=Path(read(OLD/'report-verification.json')['output_directory'])
D=B.parent/'reports/dropbox-riyadh-workshop-context-filing-20261023T233429Z'
batch_paths=[B/'components/parallel-reviews'/x for x in [
 'frozen-fish-series-owner-review-20261023T233556Z/sealed-frozen-fish-series-policy-batch-02.json',
 'moon-shellwave2-black-white-series-policy-20261023T234009Z/sealed-b-series-policy-batch02.json']]
assert [sha(x)for x in batch_paths]==['37d8da43e01c4addbe4f2e5c565f8028f8ab9c672ca7c9ab2413cb99c8f3c8ce','b654935579aec822bbaf5d7c5bab7b30416d1ad537f281129e1ec33b05ffa8d7']
assert sha(D/'execution-seal.json')=='825bf786e2ef02103a614939183820b00b5d185ddd0a147d90e8fca2d0eb1f5e'
assert sha(D/'current-reference-overlay.json')=='b0ca77780bac545e1c48e22008bb5702345a95974cb8c06f62dbd03d610b06b6'
policies=[e for path in batch_paths for e in read(path)['decisions']]
assert len({e['option_id']for e in policies})==len(policies)==4
files={'pointer':B/'current-master.json','master_workbook':B/p['workbook'],'master_register':B/p['register'],
 'audit':OLD/'image-coverage-current.json','native_map':OLD/'current-native-reference-map.json',
 'report_assets':OLD/'current-assets.json','report_reviews':OLD/'photo-review-queue.json',
 'review_state':OLD/'guided-owner-review-state.json','pending':OLD/'pending-followups.json',
 'review_progress':B/'components/reviews/specification_review_progress.json',
 'component_checkpoint':B/'components/checkpoint.json','root_checkpoint':B/'checkpoint.json',
 'source_report_verification':OLD/'report-verification.json','source_count_summary':oldout/'current-count-summary.json',
 'source_photo_requests':oldout/'remaining-photograph-requests.json',
 'riyadh_overlay':D/'current-reference-overlay.json','riyadh_seal':D/'execution-seal.json'}
for i,path in enumerate(batch_paths):files['owner_batch_'+str(i)]=path
for i,e in enumerate(policies):
 assert sha(e['path'])==e['sha256']; files['policy_'+str(i)]=Path(e['path'])
seal=read(D/'execution-seal.json'); overlay=read(D/'current-reference-overlay.json')
assert seal['status']==overlay['status']=='COMPLETE_VERIFIED' and len(seal['receipts'])==20
assert not overlay['deleted_files'] and not overlay['deleted_folders']
for i,r in enumerate(seal['receipts']):
 assert sha(r['path'])==r['sha256'] and Path(r['path']).stat().st_size==r['size']
 files['native_receipt_'+str(i)]=Path(r['path'])
m={}
for key,path in files.items():
 snap=H/'inputs'/(key+'.before'); shutil.copy2(path,snap)
 m[key]={'path':str(path),'snapshot':str(snap),'sha256':sha(path)}
write(H/'input-manifest.json',m)
write(H/'WORK_STATE.json',{'status':'FROZEN_FOUR_POLICIES_AND_RIYADH','plan':['Verify sealed sources and stable identities','Project current navigation and exact photo requirements','Author and verify workbook','Refresh reports and publish with input checks'],'later_receipts':'Queue separately; do not enlarge this freeze'})
g=read(m['master_register']['snapshot']); a=read(m['audit']['snapshot'])
native=read(m['native_map']['snapshot']); assets=read(m['report_assets']['snapshot'])
reviews=read(m['report_reviews']['snapshot']); state=read(m['review_state']['snapshot'])
pending=read(m['pending']['snapshot']); photo=read(OLD/'photo-source-review.json')
objects={o['file_id']:o for o in overlay['objects']}
changed={i:o for i,o in objects.items() if o.get('old_path')!=o['current_path']}
assert len(objects)==52 and len(changed)==26
assert sum(o['object_type']=='file'for o in changed.values())==24
assert sum(o['object_type']=='file'and o['old_parent_id']!=o['current_parent_id']for o in changed.values())==21
assert len(overlay['created_folders'])==1 and overlay['prefix_maps'][0]['file_id']=='id:cnqzTNngPVsAAAAAAAylig'
root=overlay['source_scope']; assert root.startswith('/BOLDSTONE MASTER/Products/01 Wall Sculptures/')
originals=read(OLD/'original-verification.json'); original_ids={x['file_id']for x in originals['files']}
for item in seal['verified_post_move_originals']:
 data=Path(item['path']).read_bytes()
 content=hashlib.sha256(b''.join(hashlib.sha256(data[i:i+4194304]).digest() for i in range(0,len(data),4194304))).hexdigest()
 assert hashlib.sha256(data).hexdigest()==item['sha256'] and len(data)==item['size'] and content==item['dropbox_content_hash']
 if item['file_id'] not in original_ids:
  originals['files'].append({'file_id':item['file_id'],'local_original':item['path'],'sha256':item['sha256'],'bytes':len(data),'dropbox_content_hash':content}); original_ids.add(item['file_id'])
assert len(seal['verified_post_move_originals'])==47 and sum(x['size']for x in seal['verified_post_move_originals'])==56646044
path_history=[]; previously_unrepresented=[]
for ident,obj in objects.items():
 assert obj['current_path'].startswith(root+'/')
 assert obj['old_path'] is None or obj['old_client_modified']==obj['current_client_modified']
 before=copy.deepcopy(native['current_objects'].get(ident))
 if before:assert display(before['path'])==display(obj['old_path'])
 else:previously_unrepresented.append(ident)
 cur={**(before or {}),'file_id':ident,'object_type':obj['object_type'],'name':obj['current_name'],
  'path':namespaced(obj['current_path']),'display_path':obj['current_path'],'parent_id':obj['current_parent_id'],
  'size':obj['size'],'current_navigation_source':str(D/'current-reference-overlay.json')}
 native['current_objects'][ident]=cur
 for path in [obj.get('old_path'),obj['current_path']]:
  if path:native['old_path_to_id'][display(path).casefold()]=ident
 if ident in changed:path_history.append({'file_id':ident,'before':before or {'path':obj['old_path'],'parent_id':obj['old_parent_id']},'current':cur})
 if obj['object_type']=='file':
  asset=assets[ident]
  assert display(asset['path'])==obj['old_path'] and asset['folder_id']==obj['old_parent_id'] and asset['bytes']==obj['size'] and asset['name']==obj['current_name']
  if ident in changed:
   asset.setdefault('historical_same_id_navigation',[]).append({k:asset[k]for k in ['path','folder_id','image_url','folder_url']})
   asset.update(path=namespaced(obj['current_path']),display_path=obj['current_path'],folder_id=obj['current_parent_id'],
    folder_path=namespaced(obj['current_path'].rsplit('/',1)[0]),image_url='https://www.dropbox.com/preview'+quote(obj['current_path'],safe='/'),
    folder_url='https://www.dropbox.com/home'+quote(obj['current_path'].rsplit('/',1)[0],safe='/'),modified_time=obj['current_server_modified'])
rootid=overlay['preserved_scope_roots'][0]['file_id']
native['current_objects'].setdefault(rootid,{'file_id':rootid,'object_type':'folder','name':root.rsplit('/',1)[1],'path':namespaced(root),'display_path':root,'size':0,'parent_id':None,'parent_id_status':'Not inferred from this scoped packet'})
native['status']='CURRENT_MAP_WITH_VERIFIED_RIYADH_NAVIGATION'
native.setdefault('verified_path_change_history',[]).append({'overlays':[{'path':str(D/'current-reference-overlay.json'),'sha256':sha(D/'current-reference-overlay.json')}],
 'objects':path_history,'new_native_folder_ids':['id:cnqzTNngPVsAAAAAAA6Vrw'],'existing_native_ids_newly_represented_in_scoped_map':[i for i in previously_unrepresented if i!='id:cnqzTNngPVsAAAAAAA6Vrw'],
 'source_originals_rehashed':47,'all_library_source_bytes_rehashed':False})
current_refs=[]
def project_current(x,path=''):
 """Refresh exact current reference fields. Immutable decisions/history stay dated."""
 if isinstance(x,list):
  for i,v in enumerate(x):project_current(v,path+'/'+str(i))
 elif isinstance(x,dict):
  for prefix in ['', 'context_', 'series_']:
   ident=x.get(prefix+'file_id')
   if ident in changed and changed[ident]['object_type']=='file':
    asset=assets[ident]
    for k in ['path','image_url','folder_url','folder_id']:
     key=prefix+k
     if key in x and x[key]!=asset[k]:x[key]=asset[k];current_refs.append(path+'/'+key)
  for k,v in list(x.items()):
   if any(s in k.lower()for s in ['historical','history','before','prior_','owner_policy','owner_photo_decision','source_receipt','imported_']):continue
   if k in ['specifications','master_fields','selling_details','current_commercial_policy']:continue
   project_current(v,path+'/'+k)
for collection in ['options','components']:
 project_current(g[collection],collection)
for collection in ['source_sets','source_offer_edges']:
 for i,row in enumerate(g[collection]):project_current(row.get('current_primary_reference',{}),collection+'/'+str(i)+'/current_primary_reference')
project_current(g['arrangement_context_references'],'arrangement_context_references')
for collection in ['coverage','missing_pictures','identity_review']:project_current(a[collection],'audit/'+collection)
project_current(reviews,'photo-review-queue'); project_current(photo['requests'],'photo-source-review/requests')
opts={o['product_id']:o for o in g['options']}; cov={c['option_id']:c for c in a['coverage']}; events=[]
scope_texts={
 'BSI-8DE87C63B013':'Owner approved the Series photograph as optional for this current individual offering without a fixed matched set. Exact group photograph remains unverified. Revisit if the offering changes.',
 'BSI-0D80125C0E35':'Owner confirmed individual sale and made a mandatory Series photograph unnecessary. Optional companion combinations remain possible. Exact group photograph remains unverified.',
 'BSI-096BA2E00517':'Owner made the group/series photograph optional. Existing individual sale and family/arrangement associations remain. This does not confirm that no companion set exists. Exact group photograph remains unverified.',
 'BSI-6E9202BEAD51':'Owner made the group/series photograph optional. Existing individual sale and family/arrangement associations remain. This does not confirm that no companion set exists. Exact group photograph remains unverified.'}
for item in policies:
 e=read(item['path']); oid=e['option_id']; o=opts[oid]; c=cov[oid]
 assert not o.get('current_series_optionality_policy') and c['series']['status']=='No verified image' and c['series']['reference'] is None and c['series_required'] is True
 assert o['file_id']==e['primary_reference']['file_id'] and o['folder_id']==e['primary_reference']['folder_id']
 if 'context_reference' in e:assert all(o[k]==v for k,v in e['context_reference'].items()if k in ['context_file_id','context_folder_id'])
 event={**e,'source_receipt':item['path'],'source_sha256':item['sha256'],'canonical_applied':True,'applied_utc':now()}; events.append(event)
 text=scope_texts[oid]
 o['current_series_optionality_policy']=event; o['photo_coverage']['series']='Optional / no fixed set'
 review=o['current_photo_task_review']['roles']['series']
 o['current_photo_task_review'].setdefault('historical_policy_superseded_roles',[]).append({'recorded_utc':now(),'role':'series','before':copy.deepcopy(review),'owner_policy':event})
 review.update(state='OWNER_APPROVED_SERIES_PHOTOGRAPH_OPTIONAL',finding=text,next_action='No mandatory Series photograph under this exact owner policy. Retain existing family and arrangement associations.',owner_policy=event)
 c.setdefault('historical_series_requirement_revisions',[]).append({'recorded_utc':now(),'prior_series':copy.deepcopy(c['series']),'prior_series_required':True,'prior_owner_review':c['owner_review']})
 c['series'].update(status='Optional / no fixed set',basis=text,terminal_review_state='OWNER_APPROVED_SERIES_PHOTOGRAPH_OPTIONAL',owner_policy=event)
 c['series_required']=False; c['owner_review']=(c['owner_review']+'\n'+text).strip()
 task=next(t for t in a['missing_pictures']if t['option_id']==oid and t['role']=='Series')
 prior_task=copy.deepcopy(task)
 task.setdefault('historical_owner_policy_actions',[]).append({'recorded_utc':now(),'before':prior_task,'owner_policy':event})
 task.update(action_type='Optional image',status='Optional',action='Group/series photograph optional under the owner decision for this exact option.',owner_response=text,terminal_review_state='OWNER_APPROVED_SERIES_PHOTOGRAPH_OPTIONAL',owner_series_policy=event)
 task['qualification']+='\n'+text
 for rv in reviews:
  if rv['option_id']==oid and rv['role']=='Series':rv['historical_owner_policy_review']=copy.deepcopy(rv);rv.update(review_state='OWNER_APPROVED_SERIES_PHOTOGRAPH_OPTIONAL',next_action=review['next_action'],finding=text,owner_series_policy=event)
 assert oid in state['queues']['series'];state['queues']['series'].remove(oid)
 matched=[r for r in photo['requests']if r['option_id']==oid and r['role']=='Series'];assert len(matched)==1
 photo['requests']=[r for r in photo['requests']if r not in matched];photo.setdefault('owner_optional_series_requests',[]).append({'previous_request':matched[0],'owner_policy':event})
c=a['counts'];c['series_statuses']['No verified image']-=4;c['series_statuses']['Optional / no fixed set']+=4;c['series_required_options']-=4
c['actions_by_type']['Find / capture']-=4;c['actions_by_type']['Optional image']+=4;c['required_picture_actions']-=4
state.setdefault('owner_approved_optional_series_reviews',[]).extend(events)
state.update(updated_utc=now(),missing_source_task='8 active Series and one individual water-build source requirement;22 context and one separate Series request held. Frozen Fish legacy identity deferred.')
photo.update(status='8_SERIES_AND_ONE_INDIVIDUAL_ACTIVE_CONTEXT_HELD',role_counts={'Individual':1,'Display/context':0,'Series':8})
summary={'status':'RIYADH_NAVIGATION_AND_FOUR_OWNER_PHOTO_POLICIES_IMPORTED','recorded_utc':now(),
 'option_ids':[e['option_id']for e in events],'new_series_requirements_made_optional':4,'current_options':188,'retained_options':189,'component_identities':112,
 'required_picture_actions':33,'active_series':8,'held_series':1,'active_individual_source_cases':1,'held_context':22,'optional_series':62,
 'changed_file_paths':24,'actual_file_parent_changes':21,'existing_folder_renames':1,'created_native_folders':1,
 'new_native_folder_id':'id:cnqzTNngPVsAAAAAAA6Vrw','source_originals_rehashed':47,'source_original_bytes':56646044,
 'new_photo_bindings':0,'new_verified_group_photos':0,'new_physical_verifications':0,'new_native_calls':0,'native_or_platform_writes':0,
 'individual_primary_bindings_changed':0,'current_reference_fields_refreshed':len(current_refs),'series_photo_optional_does_not_remove_companion_associations':True}
g['latest_riyadh_navigation_and_series_policy_import']=summary
g.setdefault('imported_series_owner_review_packets',[]).extend({'path':str(path),'sha256':sha(path),'optional_series_policies':[e for e in events if any(e['option_id']==r['option_id']for r in read(path)['decisions'])],'new_verified_photos':0}for path in batch_paths)
pending.setdefault('imported_packet_history',[]).append({'path':str(D/'current-reference-overlay.json'),'sha256':sha(D/'current-reference-overlay.json'),'navigation_only':True,'applied_to_current_frozen_release':True})
pending['entries']=[x for x in pending['entries']if x.get('path')!=str(D/'current-reference-overlay.json')]
g['latest_active_photo_source_review'].update(path=str(H/'photo-source-review.json'),active_roles=9,active_series_roles=8,series_requests=8,active_individual_roles=1)
write(H/'photo-source-review.json',photo);g['latest_active_photo_source_review']['sha256']=sha(H/'photo-source-review.json')
g['latest_image_coverage_audit'].update(path=str(H/'image-coverage-current.json'),audit=str((H/'image-coverage-current.json').relative_to(B)),counts=copy.deepcopy(c),recorded_utc=now(),status='RIYADH_NAVIGATION_AND_FOUR_SERIES_PHOTO_REQUIREMENTS_OPTIONAL')
for key,file in [('verification','saved-file-verification.json'),('native_binding_verification','native-binding-verification.json'),('visual_verification','visual-verification.json')]:g['latest_image_coverage_audit'][key]=str((H/file).relative_to(B));g['latest_image_coverage_audit'].pop(key+'_sha256',None)
g['latest_image_coverage_audit'].pop('audit_sha256',None)
for file,value in [('canonical-master-register.json',g),('image-coverage-current.json',a),('photo-review-queue.json',reviews),('guided-owner-review-state.json',state),('import-summary.json',summary),('imported-owner-series-policies.json',events),('current-native-reference-map.json',native),('current-assets.json',assets),('pending-followups.json',pending),('path-change-history.json',path_history),('current-reference-fields-refreshed.json',current_refs),('original-verification.json',originals)]:write(H/file,value)
for file in ['physical-source-audit.json','guided_review.py','verify_workbook.py']:shutil.copy2(OLD/file,H/file)
shutil.copy2(B/p['latest_working_entry_owner_provenance']['path'],H/'working-entry-owner-provenance-sidecar.json')
write(H/'source-evidence-verification.json',{'status':'PASS','exact_owner_policy_receipts':4,'sealed_native_receipts':20,'source_originals_rehashed':47,'new_native_calls':0,'new_physical_verifications':0,'native_or_platform_writes':0})
write(H/'evidence-manifest.json',{str(files[k]):{'sha256':m[k]['sha256']}for k in m if k.startswith(('policy_','owner_batch_','riyadh_','native_receipt_'))})
write(H/'projection-index.json',{'old_output':str(oldout),'new_output':str(OUT),'option_ids':summary['option_ids'],'changed_native_objects':changed,'current_reference_fields':current_refs})
if not (H/'node_modules').exists():(H/'node_modules').symlink_to('/Users/tprice/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules',target_is_directory=True)
print(json.dumps(summary))
