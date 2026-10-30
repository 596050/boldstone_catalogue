"""Project only the completed, owner-approved Spiralmoon navigation change."""
import copy,hashlib,json,shutil
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import quote
H=Path(__file__).resolve().parent;B=H.parents[2];OUT=B/'outputs'/H.name
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();now=lambda:datetime.now(timezone.utc).isoformat()
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def display(p):return '/'+p.split('//',1)[1].lstrip('/') if p.startswith('ns:') else p
def namespace(p):return 'ns:202238505/'+display(p)
assert not(H/'import-summary.json').exists()
p=read(B/'current-master.json');OLD=(B/p['register']).parent;oldout=Path(read(OLD/'report-verification.json')['output_directory'])
assert p['register_sha256']=='2205546ab8502b4723d1eb9597c6da4104f8df18e7addcfd1ad9d9a4df328c16'
D=B.parent/'reports/dropbox-wave-moonshadow-mixed-scene-moves-20261024T014335Z'
expected=read(H/'approved-native-packet.json')
for n,digest in expected.items():assert sha(D/n)==digest,n
overlay=read(D/'current-reference-overlay.json');seal=read(D/'execution-seal.json')
assert overlay['status']==seal['status']=='COMPLETE_VERIFIED'
assert not overlay['deleted_files'] and not overlay['deleted_folders']
(H/'inputs').mkdir(exist_ok=True);OUT.mkdir(parents=True,exist_ok=True)
files={'pointer':B/'current-master.json','master_workbook':B/p['workbook'],'master_register':B/p['register'],'audit':OLD/'image-coverage-current.json','native_map':OLD/'current-native-reference-map.json','report_assets':OLD/'current-assets.json','report_reviews':OLD/'photo-review-queue.json','review_state':OLD/'guided-owner-review-state.json','pending':OLD/'pending-followups.json','review_progress':B/'components/reviews/specification_review_progress.json','component_checkpoint':B/'components/checkpoint.json','root_checkpoint':B/'checkpoint.json','source_report_verification':OLD/'report-verification.json','source_count_summary':oldout/'current-count-summary.json','source_photo_requests':oldout/'remaining-photograph-requests.json','wave_overlay':D/'current-reference-overlay.json','wave_seal':D/'execution-seal.json'}
for i,r in enumerate(seal['receipts']):
 assert sha(r['path'])==r['sha256'] and Path(r['path']).stat().st_size==r['size'];files['native_receipt_'+str(i)]=Path(r['path'])
m={}
for k,path in files.items():
 snap=H/'inputs'/(k+'.before');shutil.copy2(path,snap);m[k]={'path':str(path),'snapshot':str(snap),'sha256':sha(path)}
write(H/'input-manifest.json',m)
g=read(m['master_register']['snapshot']);a=read(m['audit']['snapshot']);native=read(m['native_map']['snapshot']);assets=read(m['report_assets']['snapshot']);reviews=read(m['report_reviews']['snapshot']);state=read(m['review_state']['snapshot']);pending=read(m['pending']['snapshot']);photo=read(OLD/'photo-source-review.json')
objects={o['file_id']:o for o in overlay['objects']};changed={i:o for i,o in objects.items()if o.get('old_path')!=o['current_path']}
filechanges={i:o for i,o in changed.items()if o['object_type']=='file'}
assert len(changed)==3 and len(filechanges)==2 and len(overlay['created_folders'])==1
assert all(o['old_parent_id']=='id:cnqzTNngPVsAAAAAAAyjHQ' and o['current_parent_id']=='id:cnqzTNngPVsAAAAAAA6Vsg' for o in filechanges.values())
assert set(filechanges)=={'id:cnqzTNngPVsAAAAAAArqLg','id:cnqzTNngPVsAAAAAAAuXZA'}
root=overlay['source_scope'];assert root=='/BOLDSTONE MASTER/Products/01 Wall Sculptures/Wave and Moonshadow'
originals=read(OLD/'original-verification.json');original_ids={x['file_id']for x in originals['files']};total_bytes=0
for item in seal['verified_post_move_originals']:
 data=Path(item['path']).read_bytes();content=hashlib.sha256(b''.join(hashlib.sha256(data[i:i+4194304]).digest()for i in range(0,len(data),4194304))).hexdigest()
 assert hashlib.sha256(data).hexdigest()==item['sha256'] and len(data)==item['size'] and content==item['dropbox_content_hash']
 total_bytes+=len(data)
 if item['file_id']not in original_ids:
  originals['files'].append({'file_id':item['file_id'],'local_original':item['path'],'sha256':item['sha256'],'bytes':len(data),'dropbox_content_hash':content});original_ids.add(item['file_id'])
assert len(seal['verified_post_move_originals'])==59
path_history=[];new_map_ids=[];asset_repairs=[]
for ident,obj in objects.items():
 assert obj['current_path'].startswith(root+'/')
 assert obj['old_path']is None or obj['old_client_modified']==obj['current_client_modified']
 before=copy.deepcopy(native['current_objects'].get(ident))
 if before:assert display(before['path'])==display(obj['old_path'])
 else:new_map_ids.append(ident)
 cur={**(before or {}),'file_id':ident,'object_type':obj['object_type'],'name':obj['current_name'],'path':namespace(obj['current_path']),'display_path':obj['current_path'],'parent_id':obj['current_parent_id'],'size':obj['size'],'current_navigation_source':str(D/'current-reference-overlay.json')}
 native['current_objects'][ident]=cur
 for path in [obj.get('old_path'),obj['current_path']]:
  if path:native['old_path_to_id'][display(path).casefold()]=ident
 if ident in changed:path_history.append({'file_id':ident,'before':before or {'path':obj['old_path'],'parent_id':obj['old_parent_id']},'current':cur})
 if obj['object_type']=='file' and ident in assets:
  asset=assets[ident];assert display(asset['path'])==obj['old_path'] and asset['folder_id']==obj['old_parent_id'] and asset['bytes']==obj['size'] and asset['name']==obj['current_name']
  if ident in changed:
   asset.setdefault('historical_same_id_navigation',[]).append({k:asset[k]for k in ['path','folder_id','image_url','folder_url']})
   asset.update(path=namespace(obj['current_path']),display_path=obj['current_path'],folder_id=obj['current_parent_id'],folder_path=namespace(obj['current_path'].rsplit('/',1)[0]),image_url='https://www.dropbox.com/preview'+quote(obj['current_path'],safe='/'),folder_url='https://www.dropbox.com/home'+quote(obj['current_path'].rsplit('/',1)[0],safe='/'),modified_time=obj['current_server_modified'])
  for key,val in [('display_path',obj['current_path']),('folder_path',namespace(obj['current_path'].rsplit('/',1)[0]))]:
   if asset.get(key)!=val:asset_repairs.append({'file_id':ident,'field':key,'before':asset.get(key),'current':val});asset[key]=val
assert all(i in assets for i in filechanges)
assert all(x['file_id'] in objects and x['field'] in ['display_path','folder_path'] for x in asset_repairs)
rootid=overlay['preserved_scope_roots'][0]['file_id'];native['current_objects'].setdefault(rootid,{'file_id':rootid,'object_type':'folder','name':'Wave and Moonshadow','path':namespace(root),'display_path':root,'size':0,'parent_id':None,'parent_id_status':'Not inferred from this scoped packet'})
native['status']='CURRENT_MAP_WITH_VERIFIED_WAVE_MOONSHADOW_NAVIGATION'
native.setdefault('verified_path_change_history',[]).append({'overlays':[{'path':str(D/'current-reference-overlay.json'),'sha256':sha(D/'current-reference-overlay.json')}],'objects':path_history,'new_native_folder_ids':['id:cnqzTNngPVsAAAAAAA6Vsg'],'existing_native_ids_newly_represented_in_scoped_map':[i for i in new_map_ids if i!='id:cnqzTNngPVsAAAAAAA6Vsg'],'source_originals_rehashed':59,'all_library_source_bytes_rehashed':False})
current_refs=[]
def project(x,path=''):
 if isinstance(x,list):
  for i,v in enumerate(x):project(v,path+'/'+str(i))
 elif isinstance(x,dict):
  for prefix in ['', 'context_', 'series_']:
   ident=x.get(prefix+'file_id')
   if ident in changed:
    asset=assets[ident]
    for k in ['path','image_url','folder_url','folder_id']:
     key=prefix+k
     if key in x and x[key]!=asset[k]:x[key]=asset[k];current_refs.append(path+'/'+key)
  for k,v in list(x.items()):
   if any(s in k.lower()for s in ['historical','history','before','prior_','owner_policy','owner_photo_decision','source_receipt','imported_']):continue
   if k in ['specifications','master_fields','selling_details','current_commercial_policy','original_review_specification_assertions']:continue
   project(v,path+'/'+k)
for key in ['options','components','source_review_reconciliation','original_specification_current_references','arrangement_context_references','current_listing_resolution_details','current_existing_listing_copy_projections']:project(g[key],key)
for key in ['source_sets','source_offer_edges']:
 for i,row in enumerate(g[key]):project(row.get('current_primary_reference',{}),key+'/'+str(i)+'/current_primary_reference')
for key in ['coverage','missing_pictures','identity_review']:project(a[key],'audit/'+key)
project(reviews,'photo-review-queue');project(photo['requests'],'photo-source-review/requests')
assert g['summary']==read(m['master_register']['snapshot'])['summary'] and a['counts']==read(m['audit']['snapshot'])['counts']
summary={'status':'WAVE_MOONSHADOW_TWO_MIXED_SCENE_PATHS_AND_PARENTS_REFRESHED','recorded_utc':now(),'current_options':188,'retained_options':189,'component_identities':112,'changed_file_paths':2,'actual_file_parent_changes':2,'existing_folder_renames':0,'created_native_folders':1,'source_originals_rehashed':59,'source_original_bytes':total_bytes,'selected_primary_file_ids_changed':0,'selected_primary_parent_changes':0,'photograph_role_bindings_changed':0,'new_photo_bindings':0,'new_physical_verifications':0,'active_photo_requests':0,'held_series':1,'held_context':22,'required_picture_actions':24,'optional_series':70,'native_or_platform_writes':0,'current_reference_fields_refreshed':len(current_refs),'approved_mixed_scene_moves_applied':2}
summary['auxiliary_current_asset_path_fields_repaired']=len(asset_repairs)
write(H/'auxiliary-current-asset-navigation-repairs.json',asset_repairs)
g['latest_wave_moonshadow_native_navigation_import']=summary;g['latest_active_photo_source_review'].update(path=str(H/'photo-source-review.json'))
write(H/'photo-source-review.json',photo);g['latest_active_photo_source_review']['sha256']=sha(H/'photo-source-review.json')
g['latest_image_coverage_audit'].update(path=str(H/'image-coverage-current.json'),audit=str((H/'image-coverage-current.json').relative_to(B)),recorded_utc=now(),status='WAVE_MOONSHADOW_SAME_SOURCE_IDS_CURRENT_PARENT_REFRESH')
for k,f in [('verification','saved-file-verification.json'),('native_binding_verification','native-binding-verification.json'),('visual_verification','visual-verification.json')]:g['latest_image_coverage_audit'][k]=str((H/f).relative_to(B));g['latest_image_coverage_audit'].pop(k+'_sha256',None)
g['latest_image_coverage_audit'].pop('audit_sha256',None)
pending.setdefault('imported_packet_history',[]).append({'path':str(D/'current-reference-overlay.json'),'sha256':sha(D/'current-reference-overlay.json'),'navigation_only':True,'applied_to_current_frozen_release':True})
for f,v in [('canonical-master-register.json',g),('image-coverage-current.json',a),('current-native-reference-map.json',native),('current-assets.json',assets),('photo-review-queue.json',reviews),('guided-owner-review-state.json',state),('pending-followups.json',pending),('import-summary.json',summary),('path-change-history.json',path_history),('current-reference-fields-refreshed.json',current_refs),('original-verification.json',originals)]:write(H/f,v)
for f in ['physical-source-audit.json','guided_review.py','working-entry-owner-provenance-sidecar.json']:shutil.copy2(OLD/f,H/f)
write(H/'source-evidence-verification.json',{'status':'PASS','sealed_native_receipts':len(seal['receipts']),'source_originals_rehashed':59,'source_original_bytes':total_bytes,'new_native_calls':0,'native_or_platform_writes':0,'new_physical_verifications':0})
write(H/'evidence-manifest.json',{str(v):{'sha256':m[k]['sha256']}for k,v in files.items()if k.startswith(('spiralmoon_','native_receipt_'))})
write(H/'projection-index.json',{'old_output':str(oldout),'new_output':str(OUT),'option_ids':[],'changed_native_objects':changed,'current_reference_fields':current_refs})
write(H/'WORK_STATE.json',{'status':'FROZEN_NATIVE_NAVIGATION_ONLY','plan':['Read back two approved Wave and Moonshadow mixed-scene moves by stable ID','Preserve selected file, roles, working fields and all owner holds','Refresh current report/workbook links and actual parents','Verify and publish with frozen-source guards']})
if not(H/'node_modules').exists():(H/'node_modules').symlink_to('/Users/tprice/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules',target_is_directory=True)
print(json.dumps(summary))
