"""Import the completed bordered Moonphase move and rename without changing roles."""
import copy,hashlib,json,shutil
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import quote,urlsplit,unquote,parse_qs
H=Path(__file__).resolve().parent;B=H.parents[2]
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();now=lambda:datetime.now(timezone.utc).isoformat()
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def display(p):return '/'+p.split('//',1)[1].lstrip('/') if p.startswith('ns:') else p
m=read(H/'input-manifest.json')
for k,x in m.items():assert sha(x['path'])==sha(x['snapshot'])==x['sha256'],k
overlay=read(m['border_overlay']['snapshot']);assert overlay['status']=='COMPLETE_VERIFIED'
assert not any(overlay[k] for k in ['created_folders','deleted_folders','deleted_files'])
for sealkey in ['execution_seal','review_seal']:
 seal=read(m[sealkey]['snapshot']);base=Path(m[sealkey]['path']).parent
 for x in seal['receipt_hashes']:assert sha(base/x['file'])==x['sha256'],x['file']
old=read(m['master_register']['snapshot']);g=copy.deepcopy(old);a=read(m['audit']['snapshot']);assets=read(m['report_assets']['snapshot']);native=read(m['native_map']['snapshot']);pending=read(m['pending']['snapshot'])
changed={x['file_id']:x for x in overlay['objects']if x['old_path']!=x['current_path']};assert len(changed)==9
fresh={}
for record in read(H/'fresh-native-evidence.json')['records']:
 r=record['result'];assert not r.get('isError');s=r['structuredContent'];x=s[s['metadata_type']];assert x['id']==record['id'] and x['path_display'].startswith('/BOLDSTONE MASTER/');fresh[x['id']]=x
assert set(changed)<=set(fresh)
for fid,x in changed.items():
 f=fresh[fid];assert f['name']==x['current_name']and f['path_display'].casefold()==display(x['current_path']).casefold()
 if x['object_type']=='file':assert f['size']==x['size']and f['client_modified']==x['current_client_modified']and f['server_modified']==x['current_server_modified']
parent_lists={}
for record in read(H/'fresh-parent-lists.json')['records']:
 r=record['result'];assert not r.get('isError');s=r['structuredContent'];assert not s['has_more'];parent_lists[display(record['path']).casefold()]=s['entries']
for parent_id,count in [('id:cnqzTNngPVsAAAAAAAydLQ',7),('id:cnqzTNngPVsAAAAAAAylYQ',2)]:
 entries=parent_lists[fresh[parent_id]['path_display'].casefold()];assert len(entries)==count
 expected={x['file_id']for x in overlay['objects']if x['object_type']=='file'and x['current_parent_id']==parent_id};assert {x['file_id']for x in entries}==expected
 for x in entries:assert display(x['path']).rsplit('/',1)[0].casefold()==fresh[parent_id]['path_display'].casefold()
originals=[];download=read(Path(overlay['review_receipts'])/'download-receipts.json');checks=read(Path(overlay['receipts'])/'content-hash-readback-validation.json');hashes={x['file_id']:x for x in checks['files']}
for x in download:
 p=Path(x['local_path']);data=p.read_bytes();h=hashlib.sha256(b''.join(hashlib.sha256(data[i:i+4194304]).digest()for i in range(0,len(data),4194304))).hexdigest()
 assert len(data)==x['size']and sha(p)==x['sha256']and h==x['verified_dropbox_content_hash']==hashes[x['id']]['current_dropbox_content_hash']
 originals.append({'file_id':x['id'],'local_original':str(p),'sha256':sha(p),'dropbox_content_hash':h,'bytes':len(data)})
assert len(originals)==10
history=[]
for fid,x in changed.items():
 before=copy.deepcopy(native['current_objects'][fid]);f=fresh[fid];path='ns:202238505/'+f['path_display'];current={**before,'name':f['name'],'path':path,'display_path':f['path_display'],'parent_id':x['current_parent_id']}
 native['current_objects'][fid]=current
 for p in [x['old_path'],before['path'],before['display_path'],f['path_display'],path]:native['old_path_to_id'][display(p).casefold()]=fid
 history.append({'file_id':fid,'before':before,'current':current,'old_parent_id':x['old_parent_id'],'current_parent_id':x['current_parent_id'],'native_metadata':f})
def ref(fid):
 x=native['current_objects'][fid];parent=native['current_objects'][x['parent_id']]
 return {'file_id':fid,'folder_id':x['parent_id'],'name':x['name'],'path':x['path'],'image_url':'https://www.dropbox.com/preview'+quote(x['display_path'],safe='/'),'folder_url':'https://www.dropbox.com/home'+quote(parent['display_path'],safe='/')}
for fid,x in changed.items():
 if fid in assets:
  oldasset=assets[fid];r=ref(fid);parent=native['current_objects'][r['folder_id']]
  oldasset.update(r,display_path=native['current_objects'][fid]['display_path'],folder_path=parent['path'])
affected=[]
for row in a['coverage']:
 for role in ['individual','in_situ','series']:
  r=row[role].get('reference')
  if r and r.get('file_id')in changed:
   assert role=='series'and row['option_id']in ['BSI-65A93033A200','BSI-4515726BBC18'];r.update(ref(r['file_id']));affected.append(row['option_id'])
assert len(affected)==2
o=next(x for x in g['options']if x['product_id']=='BSI-65A93033A200');additional={**ref('id:cnqzTNngPVsAAAAAAAt4DQ'),'role':'ADDITIONAL_EXISTING_SINGLE_COMPONENT_REFERENCE','primary_replacement':False,'physical_specification_evidence':False,'basis':'Reviewed original008 depicts the existing bordered Moonphase1 design. It is an additional reference, with the selected001 primary preserved.'}
assert not o.get('additional_individual_references');o['additional_individual_references']=[additional]
summary={'status':'BORDERED_MOONPHASE_CORRECTIONS_IMPORTED','recorded_utc':now(),'source_overlay':m['border_overlay']['path'],'source_overlay_sha256':m['border_overlay']['sha256'],'changed_stable_ids':sorted(changed),'existing_file_paths_refreshed':8,'existing_folder_names_refreshed':1,'actual_file_parent_id_changes':1,'fresh_metadata_objects':11,'fresh_complete_parent_lists':2,'additional_individual_reference':additional,'primary_images_replaced':0,'coverage_roles_closed':0,'new_option_or_component_records':0,'new_physical_verifications':0,'native_or_platform_writes':0,'current_counts':copy.deepcopy(a['counts'])}
g['latest_bordered_moonphase_reference_import']=copy.deepcopy(summary);g['current_bordered_moonphase_references']={'option_ids':affected,'series_references':[{ 'option_id':x['option_id'],'reference':copy.deepcopy(x['series']['reference'])}for x in a['coverage']if x['option_id']in affected],'additional_individual_reference':additional,'no_primary_replacement':True}
g['latest_image_coverage_audit'].update(path=str(H/'image-coverage-current.json'),audit=str((H/'image-coverage-current.json').relative_to(B)),recorded_utc=now(),status='COVERAGE_ROLES_UNCHANGED_CURRENT_BORDERED_MOONPHASE_PATHS_REFRESHED')
for key,name in [('verification','saved-file-verification.json'),('native_binding_verification','native-binding-verification.json'),('visual_verification','visual-verification.json')]:g['latest_image_coverage_audit'][key]=str((H/name).relative_to(B));g['latest_image_coverage_audit'].pop(key+'_sha256',None)
g['latest_image_coverage_audit'].pop('audit_sha256',None)
ready=[x for x in pending['entries']if x.get('path')==m['border_overlay']['path']];assert len(ready)==1 and ready[0]['sha256']==m['border_overlay']['sha256']
pending['entries']=[x for x in pending['entries']if x not in ready];assert len(pending['entries'])==1 and pending['entries'][0]['status']=='PARTIAL_OWNER_HOLD'
pending.setdefault('imported_packet_history',[]).append({**ready[0],'applied_to_current_frozen_release':True,'imported_utc':now(),'local_import_summary':str(H/'import-summary.json')});pending.update(recorded_utc=now(),status='ONLY_OWNER_HELD_NATIVE_PACKET_REMAINS')
native['status']='CURRENT_MAP_WITH_BORDERED_MOONPHASE_SAME_ID_CORRECTIONS';native.setdefault('verified_path_change_history',[]).append({'overlay':m['border_overlay']['path'],'sha256':m['border_overlay']['sha256'],'objects':history})
for name,key in [('photo-review-queue.json','report_reviews'),('guided-owner-review-state.json','review_state')]:shutil.copy2(m[key]['snapshot'],H/name)
for name,data in [('canonical-master-register.json',g),('image-coverage-current.json',a),('current-assets.json',assets),('current-native-reference-map.json',native),('pending-followups.json',pending),('import-summary.json',summary),('path-change-history.json',{'changes':history,'additional_individual_reference':additional}),('original-verification.json',{'files':originals}),('source-evidence-verification.json',{'status':'PASS','native_receipt_hashes_verified':14,'review_receipt_hashes_verified':6,'cached_original_hashes_verified':10,'fresh_metadata_objects':11,'complete_parent_lists':2,'specific_008_parent_override_verified':True,'source_scope':'BOLDSTONE MASTER only','new_native_or_platform_writes':0})]:write(H/name,data)
write(H/'evidence-manifest.json',{str(H/name):{'sha256':sha(H/name)}for name in ['fresh-native-evidence.json','fresh-parent-lists.json','original-verification.json','source-evidence-verification.json']})
print(json.dumps({'status':summary['status'],'file_paths_refreshed':8,'series_reference_paths_refreshed':len(affected),'primary_images_replaced':0,'photo_gaps_closed':0}))
