import json,hashlib
from pathlib import Path
H=Path(__file__).resolve().parent;read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
s=read(H/'scope.json');out=[]
def collect(z,found):
 if isinstance(z,list):
  for v in z:collect(v,found)
 elif isinstance(z,dict):
  if z.get('file_id')and z.get('client_modified'):found[z['file_id']]=z
  for v in z.values():collect(v,found)
for name,p in s['overlays'].items():
 overlay=read(p);receipt=next(r for r in overlay['receipts']if Path(r['path']).name=='complete-post-readback.json');assert sha(receipt['path'])==receipt['sha256'];expected={};collect(read(receipt['path']),expected);live=read(H/'live'/f'{name}.json')['entries'];count=0
 for x in live:
  if x['object_type']=='file':
   assert x['file_id']in expected,(name,x['file_id']);e=expected[x['file_id']];assert x['client_modified']==e['client_modified'];assert x['name']==e['name'];assert x['file']['size']==e['file']['size'];count+=1
 out.append({'family':name,'original_file_client_timestamps_names_and_sizes_checked':count,'sealed_readback_sha256':receipt['sha256']})
(H/'client-timestamp-verification.json').write_text(json.dumps({'status':'PASS','families':out,'files_checked':sum(x['original_file_client_timestamps_names_and_sizes_checked']for x in out)},indent=2)+'\n');print(json.dumps({'status':'PASS','files_checked':sum(x['original_file_client_timestamps_names_and_sizes_checked']for x in out)}))
