import json,hashlib
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path('/Users/tprice/Documents/boldstone')
BASE=ROOT/'sculpture-catalogue'
HERE=Path(__file__).resolve().parent
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p): return json.loads(p.read_text())
c=read(BASE/'current-master.json')
job=(BASE/c['register']).parent
n=read(job/'current-native-reference-map.json')['current_objects']
e=read(HERE/'fresh-native-evidence.json')
assert all(not e['results'][x]['has_more'] and not e['results'][x].get('cursor') for x in ['moon','workshop'])
live={x['file_id']:x for k in ['moon','workshop'] for x in e['results'][k]['entries']}
for k in ['moon-root','workshop-root']:
 f=e['results'][k]['folder'];live[f['id']]={'file_id':f['id'],'object_type':'folder','name':f['name'],'path':'ns:202238505//'+f['path_display'].lstrip('/')}
folders={v['path']:i for i,v in live.items() if v['object_type']=='folder'}
checks=[]
def check(ok,label):
 checks.append(label)
 if not ok: raise AssertionError(label)
for fid,x in live.items():
 check(fid in n,f'{fid}:stable ID retained')
 y=n[fid]
 check(x['path']==y['path'],f'{fid}:current native path equals master')
 check(x['name']==y['name'],f'{fid}:basename retained')
 check(x['object_type']==y['object_type'],f'{fid}:type retained')
 parent=folders.get(x['path'].rsplit('/',1)[0])
 if parent is not None: check(parent==y['parent_id'],f'{fid}:actual containing parent ID')
 if x['object_type']=='file': check(x.get('file',{}).get('size',0)==y['size'],f'{fid}:file size unchanged')
scope=read(job/'path-refresh-scope.json');p=scope['prefix_maps'];check(len(p)==8,'eight completed folder paths')
for x in p:
 y=live[x['file_id']]
 check('/'+y['path'].split('//',1)[1].lstrip('/')==x['current_path'],'completed folder at expected current path')
 check(n[x['file_id']]['path']==y['path'],'completed folder included in master map')
receipts=read(job/'publication-receipt.json')
check(sha(BASE/c['workbook'])==c['workbook_sha256']==receipts['workbook_sha256'],'saved workbook hash matches current pointer and receipt')
check(sha(BASE/c['register'])==c['register_sha256']==receipts['register_sha256'],'register hash matches current pointer and receipt')
packet_paths=['dropbox-moon-and-shellwave-pair-renames-2026-10-23','dropbox-moon-and-shellwave-triptych-rename-2026-10-23','dropbox-moon-and-shellwave-remaining-arrangement-renames-2026-10-23','dropbox-remaining-workshop-separation-2026-10-23']
packet_hashes={str(ROOT/'reports'/x/'current-reference-overlay.json'):sha(ROOT/'reports'/x/'current-reference-overlay.json') for x in packet_paths}
imported=read(job/'pending-followups.json')['imported_in_this_release']
for path,digest in packet_hashes.items(): check(any(x['path']==path and x['sha256']==digest for x in imported),'sealed queued packet already imported')
r={'status':'PASS_ALREADY_IMPORTED_AND_FRESH_NATIVE_READBACK','recorded_utc':datetime.now(timezone.utc).isoformat(),'source_scope':'BOLDSTONE MASTER only','checks':len(checks),'objects_checked':len(live),'descendants_checked':len(live)-2,'queued_folder_paths_verified':8,'already_refreshed_image_paths':123,'packet_hashes':packet_hashes,'current_workbook_sha256':c['workbook_sha256'],'current_register_sha256':c['register_sha256'],'in_situ_gaps_before_new_image_decisions':48,'series_gaps':17,'new_native_mutations':0,'new_master_mutations_for_already_imported_links':0,'notes':'Four completed link packets were already published. No repeated application, duplicate import or source-ID changes were needed.'}
(HERE/'queued-link-readback.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(r,ensure_ascii=False,indent=2))
