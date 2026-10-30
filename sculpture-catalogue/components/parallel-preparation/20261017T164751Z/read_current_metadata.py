from pathlib import Path
import sys,json,datetime,hashlib
sys.path.insert(0,'/Users/tprice/Library/Application Support/BoldstoneImageConsistency/identity-resolution-20261016T120156Z')
import classification_executor as e
R=Path(__file__).parent
assert json.loads((R/'Fake_Adapter_Gate.json').read_text())['passed']==74
P=Path(json.loads((R/'Live_Metadata_Location.json').read_text())['private_metadata_directory'])
api=e.f.n.AuditAPI();rows=[];pages=0
try:
 root=e.head(api.read('files_get_metadata','id:cnqzTNngPVsAAAAAAArpsA'))
 assert root['path']=='/BOLDSTONE MASTER/Products/01 Wall Sculptures',root['path']
 result=api.read('files_list_folder','id:cnqzTNngPVsAAAAAAArpsA',recursive=True,include_deleted=False,include_non_downloadable_files=True,limit=1000)
 while True:
  pages+=1;raw=e.f.n.sdk_json(result)
  e.f.durable(P/f'page-{pages:03d}.json',raw)
  rows.extend(e.head(x) for x in result.entries)
  print('Read metadata page',pages,'entries',len(rows),flush=True)
  if not result.has_more:break
  result=api.read('files_list_folder_continue',result.cursor)
 ids=[r['id'] for r in rows];assert len(ids)==len(set(ids))
 out={'recorded_utc':e.f.n.now(),'root':root,'namespace_id':'202238505','pages':pages,'pagination_exhausted':True,'entries':rows,'remote_mutations':0}
 e.f.durable(P/'Native_Census.json',out)
 b=(P/'Native_Census.json').read_bytes()
 e.f.durable(R/'Current_Metadata_Receipt.json',{'status':'PASS_COMPLETE_READ_ONLY_CENSUS','path':str(P/'Native_Census.json'),'sha256':hashlib.sha256(b).hexdigest(),'files':sum(x['kind']=='file' for x in rows),'folders':sum(x['kind']=='folder' for x in rows),'pages':pages,'recorded_utc':out['recorded_utc'],'remote_mutations':0})
 print('PASS complete native metadata census',len(rows),'records',flush=True)
finally:api.close()
