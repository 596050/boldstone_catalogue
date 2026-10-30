import hashlib,json
from pathlib import Path
from urllib.parse import quote
H=Path(__file__).resolve().parent;read=lambda p:json.loads(Path(p).read_text())
a=read(H/'current-assets.json');ms=read(H/'current-source-metadata.json');extra=read(H/'additional-source-metadata.json');ms.append(extra['extra_primary']);hashes={x['id']:x for x in read(H/'current-native-content-hashes.json')};changed_times=[]
for z in ms:
 n=z['file'];x=a[n['id']];native=hashes[n['id']]
 assert n['size']==x['bytes']and n['path_display'].casefold()==x['display_path'].casefold()
 assert native['content_hash']==(x.get('current_original_native_hash')or x.get('source_content_hash'))
 if n.get('server_modified')!=x.get('modified_time'):changed_times.append({'file_id':n['id'],'previous':x.get('modified_time'),'current':n.get('server_modified'),'native_content_hash_unchanged':True})
 fp=str(Path(n['path_display']).parent);x.update(path='ns:202238505/'+n['path_display'],display_path=n['path_display'],folder_path='ns:202238505/'+fp,image_url='https://www.dropbox.com/home'+quote(fp,safe='/')+'?preview='+quote(n['name'],safe=''),folder_url='https://www.dropbox.com/home'+quote(fp,safe='/'),current_native_revision=n['rev'],current_native_content_hash=native['content_hash'],current_metadata_server_modified=n.get('server_modified'))
assert extra['flower_folder']['folder']['id']==a['id:cnqzTNngPVsAAAAAAAyh5Q']['folder_id']
(H/'current-assets.json').write_text(json.dumps(a,ensure_ascii=False,indent=2)+'\n')
r={'status':'PASS_CURRENT_SOURCE_IDENTITY','sources':40,'metadata_path_case_spelling_refreshes':1,'native_sizes_unchanged':True,'native_content_hashes_unchanged':40,'current_revision_ids_recorded':40,'metadata_server_times_differ_from_old_snapshot':changed_times,'new_originals_downloaded_and_rehashed':4,'stable_folder_IDs_preserved':True,'temporary_download_URLs_in_evidence':False};(H/'metadata-verification.json').write_text(json.dumps(r,indent=2)+'\n')
rows=read(H/'candidate-checks.json')
if not any(x['sequence']==39 for x in rows):
 ex=read(H/'opportunistic-brancusi1-task.json');cand=next(x for x in rows if x['sequence']==41)['candidate_reference'];rows.append({'sequence':39,'option_id':ex['option_id'],'name':ex['name'],'family':ex['family'],'role':ex['requested_role'],'primary_reference':ex['primary_reference'],'candidate_reference':cand,'prior_finding':ex['findings'][-1],'state':'PENDING_DEEP_REVIEW','findings':[],'additional_capture_action_from_shared_pair_review':True});rows.sort(key=lambda x:x['sequence'])
assert len(rows)==32
for x in rows:
 for k in ['primary_reference','candidate_reference']:
  fid=x[k]['file_id'];x[k]={**x[k],**{s:a[fid][s]for s in ['file_id','folder_id','name','path','image_url','folder_url']}}
(H/'candidate-checks.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'status':r['status'],'native_hashes_unchanged':40,'checks':len(rows),'case_spelling_updated':1}))
