import copy,hashlib,json,shutil
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import quote
from navigation import refresh,namespace,display
H=Path(__file__).resolve().parent;B=H.parents[2];D=B.parent/'reports/dropbox-moonwave-ten-approved-moves-20261024T182423Z';read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();now=lambda:datetime.now(timezone.utc).isoformat()
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
assert not(H/'moonwave-native-import.json').exists();assert sha(D/'execution-seal.json')=='4b4e9f78572efcabec11681cabc3c6a8abaf2fb6fa954203c36d19448b5afdc0';assert sha(D/'current-reference-overlay.json')=='d61786201d4cd745c55019a4dfd218e4e8018a5a5b7de8abb793203366715110'
seal=read(D/'execution-seal.json');ov=read(D/'current-reference-overlay.json');authority=read(D/'owner-approval-source-evidence.json');assert seal['status']==ov['status']=='COMPLETE_VERIFIED'and seal['native_moves']==10
assert not ov['created_folders']and not ov['deleted_files']and not ov['deleted_folders']and not ov['prefix_maps']
m=read(H/'input-manifest.json')
for i,x in enumerate(seal['receipts']):
 assert sha(x['path'])==x['sha256']and Path(x['path']).stat().st_size==x['size'];key='moonwave_receipt_'+str(i);snap=H/'inputs'/(key+'.before');shutil.copy2(x['path'],snap);m[key]={'path':x['path'],'snapshot':str(snap),'sha256':x['sha256']}
for key,name in [('moonwave_seal','execution-seal.json'),('moonwave_overlay','current-reference-overlay.json')]:
 snap=H/'inputs'/(key+'.before');shutil.copy2(D/name,snap);m[key]={'path':str(D/name),'snapshot':str(snap),'sha256':sha(D/name)}
record=authority['recorded_source']
with Path(record['session_file']).open('rb')as f:f.seek(record['byte_offset']);line=f.readline()
assert hashlib.sha256(line).hexdigest()==record['complete_line_sha256'];event=json.loads(line);assert event['payload']['role']=='user'and event['timestamp']==record['record_timestamp'];assert '\n'.join(x.get('text','')for x in event['payload']['content'])==record['owner_text_verbatim'];assert record['owner_text_verbatim'].startswith('Make these changes:')
objects={o['file_id']:o for o in ov['objects']};moves={i:o for i,o in objects.items()if o['old_path']!=o['current_path']};assert len(moves)==10 and len(objects)==101
write(H/'moonwave-native-overlay.json',ov);refresh.__globals__['path_map'].cache_clear()
fresh=[]
for x in seal['verified_current_originals']:
 if x['id']not in moves:continue
 data=Path(x['local_path']).read_bytes();block=hashlib.sha256(b''.join(hashlib.sha256(data[i:i+4194304]).digest()for i in range(0,len(data),4194304))).hexdigest();assert len(data)==x['size']and hashlib.sha256(data).hexdigest()==x['sha256']and block==x['dropbox_content_hash'];fresh.append(x)
assert len(fresh)==10;assert ov['summary']['files']==99 and ov['summary']['bytes']==784220860
g=read(H/'canonical-master-register.json');a=read(H/'image-coverage-current.json');assets=read(H/'current-assets.json');native=read(H/'current-native-reference-map.json');history=read(H/'path-change-history.json');journal=read(H/'current-reference-change-journal.json')
newly_represented=[]
for ident,o in moves.items():
 before=copy.deepcopy(native['current_objects'].get(ident))
 if before is None:
  newly_represented.append(ident);before={'file_id':ident,'object_type':'file','name':o['old_name'],'path':namespace(o['old_path']),'display_path':o['old_path'],'parent_id':o['old_parent_id'],'size':o['size'],'before_evidence':'Sealed native pre-move observation; this ID was not previously represented in the scoped canonical map'}
 assert display(before['path'])==o['old_path']and before['parent_id']==o['old_parent_id'];cur={**before,'path':namespace(o['current_path']),'display_path':o['current_path'],'parent_id':o['current_parent_id']};native['current_objects'][ident]=cur;history.append({'file_id':ident,'before':before,'current':copy.deepcopy(cur),'previously_in_scoped_map':ident not in newly_represented})
 for p in [o['old_path'],o['current_path']]:native['old_path_to_id'][p.casefold()]=ident
 asset=assets[ident];assert asset['folder_id']==o['old_parent_id']and display(asset['path'])==o['old_path'];asset.update(path=namespace(o['current_path']),display_path=o['current_path'],folder_path=namespace(o['current_path'].rsplit('/',1)[0]),folder_id=o['current_parent_id'],image_url=o['current_native_url'],folder_url='https://www.dropbox.com/home'+quote(o['current_path'].rsplit('/',1)[0],safe='/'),modified_time=o['current_server_modified'])
native['verified_path_change_history'].append({'status':'TEN_OWNER_APPROVED_MOONWAVE_FILE_MOVES_VERIFIED','overlay':str(D/'current-reference-overlay.json'),'sha256':sha(D/'current-reference-overlay.json'),'objects':history[-10:],'native_execution_owner':'Directory session','new_folders':0,'original_family_files':99})
native['status']='CURRENT_MAP_WITH_SIX_URL_CASE_CORRECTIONS_AND_TEN_APPROVED_MOONWAVE_MOVES'
def own(x,label):
 if isinstance(x,list):
  for i,v in enumerate(x):own(v,label+'/'+str(i))
 elif isinstance(x,dict):
  for prefix in ['', 'context_', 'series_']:
   ident=x.get(prefix+'file_id')
   if ident in moves:
    src=assets[ident]
    for k in ['path','image_url','folder_url','folder_id']:
     key=prefix+k
     if key in x and x[key]!=src[k]:journal.append({'path':label+'/'+key,'before':x[key],'value':src[k],'own_file_id':ident});x[key]=src[k]
  for k,v in list(x.items()):
   if any(t in k.lower()for t in ['history','historical','prior_','before','owner_','original_','source_offer','source_field','source_receipt','imported_']):continue
   if k in ['specifications','master_fields','selling_details','members']:continue
   own(v,label+'/'+k)
for key in ['components','source_review_reconciliation','original_specification_current_references','arrangement_context_references','current_listing_resolution_details','current_existing_listing_copy_projections']:
 if key in g:own(g[key],'register/'+key)
for key in ['source_sets','source_offer_edges']:
 for i,row in enumerate(g[key]):own(row.get('current_primary_reference',{}),'register/'+key+'/'+str(i)+'/current_primary_reference')
row=g['source_media_configuration_coverage'][163];assert 'id:cnqzTNngPVsAAAAAAArp2Q'in row['example_file_ids'];ident='id:cnqzTNngPVsAAAAAAArp2Q';row['current_example_reference_navigation']={ident:{k:assets[ident][k]for k in ['file_id','folder_id','path','image_url','folder_url']}};row['current_example_reference_navigation'][ident]['source_overlay_sha256']=sha(D/'current-reference-overlay.json')
assert g['source_offer_edges'][15]['offer_ref']=='O016'and g['source_offer_edges'][15]['current_primary_reference']['file_id']=='id:cnqzTNngPVsAAAAAAArp1g'and g['source_offer_edges'][15]['current_primary_reference']['folder_id']=='id:cnqzTNngPVsAAAAAAAyi-A'
for key in ['coverage','missing_pictures','identity_review']:own(a[key],'audit/'+key)
queue=read(H/'photo-review-queue.json');own(queue,'photo-review-queue');photo=read(H/'photo-source-review.json');own(photo.get('requests',[]),'photo-source-review/requests')
summary=read(H/'import-summary.json');summary.update(status='SIX_URL_CASE_CORRECTIONS_AND_TEN_APPROVED_MOONWAVE_MOVES_IMPORTED',approved_moonwave_file_paths_refreshed=10,approved_moonwave_actual_parent_changes=10,moonwave_White_files=84,moonwave_InSitu_files=15,moonwave_originals_preserved=99,moonwave_original_bytes_preserved=784220860,new_original_binary_downloads_by_importer=0,local_originals_rehashed_by_importer=10);summary.pop('new_original_binary_reads',None)
nav={'status':'TEN_EXACT_OWNER_APPROVED_MOONWAVE_MOVES_CURRENT','recorded_utc':now(),'overlay':str(D/'current-reference-overlay.json'),'overlay_sha256':sha(D/'current-reference-overlay.json'),'execution_seal':str(D/'execution-seal.json'),'execution_seal_sha256':sha(D/'execution-seal.json'),'approval_source':str(D/'owner-approval-source-evidence.json'),'approval_sha256':sha(D/'owner-approval-source-evidence.json'),'moved_file_ids':list(moves),'newly_represented_existing_file_IDs':newly_represented,'White_files':84,'InSitu_files':15,'originals':99,'original_bytes':784220860,'selected_primary_and_context_unchanged':True,'source_edge_index15_offer_ref':'O016','source_example_file_ids_retained':True,'old_nine_photo_proposal_remains_withdrawn':True}
g['latest_moonwave_approved_native_navigation']=nav;g['latest_current_url_case_normalization']=summary
for name,data in [('canonical-master-register.json',g),('image-coverage-current.json',a),('current-assets.json',assets),('current-native-reference-map.json',native),('path-change-history.json',history),('current-reference-change-journal.json',journal),('photo-review-queue.json',queue),('photo-source-review.json',photo),('import-summary.json',summary),('moonwave-native-import.json',nav),('input-manifest.json',m)]:write(H/name,data)
e=read(H/'source-evidence-verification.json');e.pop('binary_reads',None);e.update(new_original_binary_downloads_by_importer=0,local_originals_rehashed_by_importer=10,approved_Moonwave_sealed_receipts=len(seal['receipts']),Moonwave_family_originals_verified_by_native_lane=99,Moonwave_family_bytes=784220860,Moonwave_fresh_originals_rehashed_by_importer=10,unchanged89_original_rehashes_by_native_lane=True);write(H/'source-evidence-verification.json',e)
manifest=read(H/'evidence-manifest.json');manifest.update({x['path']:{'sha256':x['sha256']}for k,x in m.items()if k.startswith('moonwave_')});write(H/'evidence-manifest.json',manifest);print(json.dumps(nav))
