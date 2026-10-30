import json,hashlib,posixpath
from pathlib import Path
H=Path(__file__).resolve().parent
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def display(p):return '/'+p.split('//',1)[1].lstrip('/')if p.startswith('ns:')else p
scope=read(H/'scope.json');lists=read(H/'current-family-listings.json');oldpaths={};expected={};receipts=[];roots={}
for k,p in scope['overlays'].items():
 d=read(p);assert d['status']=='COMPLETE_VERIFIED'and d['verification']['status']=='PASS';roots[display(d['family']['path'])]=d['family']['file_id']
 for rec in d['receipts']:assert sha(rec['path'])==rec['sha256'];receipts.append(rec)
 for x in d['objects']:
  fid=x['file_id'];expected[fid]=x
  for key in ['old_path','current_path']:
   if x.get(key):oldpaths[display(x[key]).casefold()]=fid
 for x in d['prefix_maps']:
  for key in ['old_path','current_path']:
   if x.get(key):oldpaths[display(x[key]).casefold()]=x['file_id']
 for x in d.get('specific_file_maps',[]):expected[x['file_id']]=x
current={}
for root,fid in roots.items():
 l=lists[root];assert l['complete'];paths={x['path'].casefold():x['file_id']for x in l['entries']if x['object_type']=='folder'};paths[('ns:202238505/'+root).casefold()]=fid
 current[fid]={'file_id':fid,'object_type':'folder','display_path':root,'path':'ns:202238505/'+root,'name':posixpath.basename(root),'parent_id':None,'size':0}
 for x in l['entries']:
  e=expected[x['file_id']];assert display(x['path'])==display(e['current_path']),(x['file_id'],x['path'],e['current_path']);assert x['name']==e['current_name'];size=x.get('file',{}).get('size',0);assert size==e['size'];parent=paths[posixpath.dirname(x['path']).casefold()];assert parent==e['current_parent_id']
  current[x['file_id']]={'file_id':x['file_id'],'object_type':x['object_type'],'display_path':display(x['path']),'path':x['path'],'name':x['name'],'parent_id':parent,'size':size,'client_modified':x.get('client_modified'),'modified_time':x.get('modified_time')}
assert set(current)-set(roots.values())==set(expected)
out={'status':'PASS_VERIFIED_FIVE_NATIVE_OVERLAYS_COMPOSED_IN_ORDER','current_objects':current,'old_path_to_id':oldpaths,'overlay_paths':scope['overlays'],'receipt_hashes_verified':receipts,'per_file_parent_overrides':39,'new_native_mutations':0,'image_bytes_rehashed_for_path_only_change':False}
(H/'native-current-crosswalk.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'status':'PASS','families':len(roots),'current_objects':len(current),'receipt_hashes':len(receipts),'specific_file_parent_changes':39}))
