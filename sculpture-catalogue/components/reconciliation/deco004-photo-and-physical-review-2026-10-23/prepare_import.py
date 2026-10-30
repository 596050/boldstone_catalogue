"""Refresh one completed native file move, preserving identities and historical sources."""
import copy,hashlib,json,shutil
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import quote
H=Path(__file__).resolve().parent;B=H.parents[2]
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();now=lambda:datetime.now(timezone.utc).isoformat()
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
m=read(H/'input-manifest.json')
for k,x in m.items():assert sha(x['path'])==sha(x['snapshot'])==x['sha256'],k
overlay=read(m['deco_overlay']['snapshot']);seal=read(m['deco_seal']['snapshot']);assert overlay['status']==seal['status']=='COMPLETE_VERIFIED'
for x in seal['native_receipts']+seal['review_receipts']:assert sha(x['path'])==x['sha256'],x['path']
assert len(overlay['specific_file_maps'])==len(overlay['created_folders'])==1 and not overlay['deleted_files']and not overlay['deleted_folders']
x=overlay['specific_file_maps'][0];fid=x['file_id'];pid=x['current_parent_id'];assert fid=='id:cnqzTNngPVsAAAAAAAyluQ'and pid=='id:cnqzTNngPVsAAAAAAA6VrQ'
fresh={}
for z in read(H/'fresh-native-evidence.json')['records']:
 r=z['result'];assert not r.get('isError');s=r['structuredContent'];f=s[s['metadata_type']];assert f['id']==z['id']and f['path_display'].startswith('/BOLDSTONE MASTER/');fresh[f['id']]=f
f=fresh[fid];parent=fresh[pid];assert f['path_display'].rsplit('/',1)[0]==parent['path_display'];assert f['name']==x['current_name']and f['size']==x['size']and f['client_modified']==x['current_client_modified']and f['server_modified']==x['current_server_modified']
lists={}
for z in read(H/'fresh-parent-lists.json')['records']:
 r=z['result'];assert not r.get('isError')and not r['structuredContent']['has_more'];lists[z['path']]=r['structuredContent']['entries']
assert {z['file_id']for z in lists['ns:202238505/'+parent['path_display']]}=={fid}
oldpid=x['old_parent_id'];held={'id:cnqzTNngPVsAAAAAAAyh6w','id:cnqzTNngPVsAAAAAAAyh6g'};assert {z['file_id']for z in lists['ns:202238505/'+fresh[oldpid]['path_display']]}==held
old=read(m['master_register']['snapshot']);g=copy.deepcopy(old);a=read(m['audit']['snapshot']);native=read(m['native_map']['snapshot']);assets=read(m['report_assets']['snapshot']);reviews=read(m['report_reviews']['snapshot']);state=read(m['review_state']['snapshot']);pending=read(m['pending']['snapshot'])
asset=assets[fid];prior=copy.deepcopy(native['current_objects'].get(fid))or{'file_id':fid,'object_type':'file','name':asset['name'],'path':asset['path'],'display_path':asset['display_path'],'parent_id':asset['folder_id'],'size':asset['bytes']};assert prior['parent_id']==oldpid and prior['path']==x['old_path']and pid not in native['current_objects']
root=read(H/'fresh-wall-sculpture-root.json')['result']['structuredContent']['folder'];familyid=overlay['family']['file_id'];family=fresh[familyid];assert family['path_display'].rsplit('/',1)[0]==root['path_display']
for ident,parentid in [(familyid,root['id']),(oldpid,familyid)]:
 obj=fresh[ident];native['current_objects'].setdefault(ident,{'file_id':ident,'object_type':'folder','name':obj['name'],'path':'ns:202238505/'+obj['path_display'],'display_path':obj['path_display'],'parent_id':parentid,'size':0})
current={**prior,'name':f['name'],'path':'ns:202238505/'+f['path_display'],'display_path':f['path_display'],'parent_id':pid};native['current_objects'][fid]=current;native['current_objects'][pid]={'file_id':pid,'object_type':'folder','name':parent['name'],'path':'ns:202238505/'+parent['path_display'],'display_path':parent['path_display'],'parent_id':overlay['family']['file_id'],'size':0}
for item in [prior,current,native['current_objects'][pid]]:
 for key in ['path','display_path']:
  p=item[key];p='/'+p.split('//',1)[1].lstrip('/')if p.startswith('ns:')else p;native['old_path_to_id'][p.casefold()]=item['file_id']
r={'file_id':fid,'folder_id':pid,'name':f['name'],'path':current['path'],'image_url':'https://www.dropbox.com/preview'+quote(f['path_display'],safe='/'),'folder_url':'https://www.dropbox.com/home'+quote(parent['path_display'],safe='/')}
def refresh_refs(z):
 if isinstance(z,dict):
  if z.get('file_id')==fid:
   z.update({k:v for k,v in r.items()if k in z or k in ['folder_id','path','image_url','folder_url']});return
  for v in z.values():refresh_refs(v)
 elif isinstance(z,list):
  for v in z:refresh_refs(v)
targets=[]
for o in g['options']:
 if o.get('context_file_id')!=fid:continue
 oid=o['product_id'];targets.append(oid);history={'context_folder_id':o['context_folder_id'],'context_image_url':o['context_image_url'],'context_folder_url':o['context_folder_url'],'current_photo_task_review':copy.deepcopy(o.get('current_photo_task_review')),'current_candidate_binding_review':copy.deepcopy(o.get('current_candidate_binding_review'))};o.setdefault('historical_deco004_path_references',[]).append(history);o.update(context_folder_id=pid,context_image_url=r['image_url'],context_folder_url=r['folder_url'])
 for key in ['current_photo_task_review','current_candidate_binding_review']:
  if key in o:refresh_refs(o[key])
assert len(targets)==3
for c in a['coverage']:
 if c['option_id']not in targets:continue
 c.setdefault('historical_deco004_path_references',[]).append({'in_situ':copy.deepcopy(c['in_situ']),'terminal_task_review':copy.deepcopy(c.get('terminal_task_review')),'candidate_binding_review':copy.deepcopy(c.get('candidate_binding_review'))})
 c['in_situ']['reference'].update(r)
 for key in ['terminal_task_review','candidate_binding_review']:
  if key in c:refresh_refs(c[key])
for task in a['missing_pictures']:
 if task['reference'].get('file_id')==fid:task.setdefault('historical_reference_paths',[]).append(copy.deepcopy(task['reference']));task['reference'].update(r)
for task in reviews:
 if task.get('source_reference',{}).get('file_id')==fid:task.setdefault('historical_reference_paths',[]).append(copy.deepcopy(task['source_reference']));task['source_reference'].update(r)
assets[fid].update(r,display_path=f['path_display'],folder_path=native['current_objects'][pid]['path'])
summary={'status':'DECO004_ACTUAL_PARENT_AND_LINKS_IMPORTED','recorded_utc':now(),'source_overlay':m['deco_overlay']['path'],'source_overlay_sha256':m['deco_overlay']['sha256'],'existing_file_id':fid,'old_parent_id':oldpid,'current_parent_id':pid,'created_native_folder_recorded':1,'current_file_path_changes':1,'actual_file_parent_id_changes':1,'existing_option_refs_refreshed':targets,'photograph_roles_closed':0,'current_photo_counts':copy.deepcopy(a['counts']),'individual_primaries_changed':0,'new_component_or_option_records':0,'owner_in_situ_filing_classification':'In Situ; scene origin and installation provenance remain unverified','held_scene_file_ids':sorted(held),'held_scene_identity_status':'ON_HOLD_PER_CURRENT_OWNER_INSTRUCTION','physical_specifications_changed':0,'native_or_platform_writes':0}
g['latest_deco004_path_refresh']=summary;g['latest_image_coverage_audit'].update(path=str(H/'image-coverage-current.json'),audit=str((H/'image-coverage-current.json').relative_to(B)),recorded_utc=now(),status='COVERAGE_UNCHANGED_DECO004_ACTUAL_PARENT_REFRESHED')
for key,name in [('verification','saved-file-verification.json'),('native_binding_verification','native-binding-verification.json'),('visual_verification','visual-verification.json')]:g['latest_image_coverage_audit'][key]=str((H/name).relative_to(B));g['latest_image_coverage_audit'].pop(key+'_sha256',None)
g['latest_image_coverage_audit'].pop('audit_sha256',None);native['status']='CURRENT_MAP_WITH_DECO004_SAME_ID_FILE_MOVE';native.setdefault('verified_path_change_history',[]).append({'overlay':m['deco_overlay']['path'],'sha256':m['deco_overlay']['sha256'],'objects':[{'file_id':fid,'before':prior,'current':current}],'new_current_folder':native['current_objects'][pid]})
ready=[z for z in pending['entries']if z.get('path')==m['deco_overlay']['path']];assert len(ready)==1;pending['entries']=[z for z in pending['entries']if z not in ready];pending.setdefault('imported_packet_history',[]).append({**ready[0],'applied_to_current_frozen_release':True,'imported_utc':now(),'local_import_summary':str(H/'import-summary.json')})
identity=B.parent/'reports/dropbox-deco-acanthus-flower-scene-review-2026-10-23/owner-identification-and-proposed-rename.json'
if identity.is_file():
 pending['entries'].append({'kind':'LATER_SCENE_IDENTIFICATION_AND_UNAPPLIED_RENAME_PROPOSAL','path':str(identity),'sha256':sha(identity),'status':'QUEUED_FOR_OWNER_SCOPE_RECONCILIATION','applied_to_current_frozen_release':False,'current_002_003_identity_hold_preserved':True,'native_rename_applied':False})
pending.update(recorded_utc=now(),status='DECO004_IMPORTED_OTHER_OWNER_HOLDS_AND_LATER_PROPOSALS_RETAINED')
downloads=read(Path(overlay['review_receipts'])/'download-receipts.json');original=next(z for z in downloads if z.get('id',z.get('file_id'))==fid);local=original.get('local_path',original.get('local_original_path'));assert local and sha(local)==overlay['summary']['moved_file_reviewed_original_sha256'];data=Path(local).read_bytes();content=hashlib.sha256(b''.join(hashlib.sha256(data[i:i+4194304]).digest()for i in range(0,len(data),4194304))).hexdigest();assert content==overlay['summary']['moved_file_content_hash']and len(data)==f['size'];assets[fid]['thumb']=local
for name,z in [('canonical-master-register.json',g),('image-coverage-current.json',a),('current-native-reference-map.json',native),('current-assets.json',assets),('photo-review-queue.json',reviews),('guided-owner-review-state.json',state),('pending-followups.json',pending),('import-summary.json',summary),('path-change-history.json',{'before':prior,'current':current,'current_parent':native['current_objects'][pid],'reference':r,'affected_option_ids':targets,'held_scene_file_ids':sorted(held)}),('original-verification.json',{'files':[{'file_id':fid,'local_original':local,'sha256':sha(local),'bytes':len(data),'dropbox_content_hash':content}]}),('source-evidence-verification.json',{'status':'PASS','sealed_native_receipts':len(seal['native_receipts']),'sealed_review_receipts':len(seal['review_receipts']),'fresh_metadata_objects':6,'complete_parent_lists':2,'whole_original_rehashed':1,'source_scope':'BOLDSTONE MASTER only','new_physical_verifications':0,'native_or_platform_writes':0})]:write(H/name,z)
write(H/'evidence-manifest.json',{str(H/name):{'sha256':sha(H/name)}for name in ['fresh-native-evidence.json','fresh-parent-lists.json','fresh-family-inventory.json','source-evidence-verification.json','original-verification.json']})
print(json.dumps({'status':summary['status'],'options_refreshed':targets,'current_parent':pid,'photo_gaps_closed':0,'physical_values_changed':0}))
