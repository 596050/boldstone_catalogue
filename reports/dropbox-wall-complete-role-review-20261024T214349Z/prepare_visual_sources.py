import hashlib,json,pathlib
from collections import Counter
from PIL import Image
P=pathlib.Path(__file__).resolve().parent
def read(p):return json.loads(pathlib.Path(p).read_text())
def hashes(path):
 sha=hashlib.sha256();blocks=[]
 with pathlib.Path(path).open('rb') as f:
  while data:=f.read(4194304):sha.update(data);blocks.append(hashlib.sha256(data).digest())
 return sha.hexdigest(),hashlib.sha256(b''.join(blocks)).hexdigest()
def run():
 rows=read(P/'all-current-6360-image-folder-links.json');native={r['id']:r for r in read(P/'fresh-all-6360-native-hash-metadata.json')['entries']};cache=read(P/'candidate-current-image-cache-paths.json')['candidates'];fresh={r['id']:r for r in read(P/'verified-new-current-originals.json')};out=[];counts=Counter()
 for r in rows:
  fid=r['file_id'];n=native[fid];assert n['name']==r['name'] and n['size']==r['size'];c=cache[fid];asset=c['asset_record'] or {};item={'file_id':fid,'family':r['family'],'native_content_hash':n['content_hash'],'source_image_path':None,'visual_source_kind':None,'original_bytes_rehashed_current':False}
  if asset.get('source_content_hash')==n['content_hash'] and c['thumbnails']:
   item.update(source_image_path=c['thumbnails'][0],visual_source_kind='CACHED_DERIVATIVE_WITH_CURRENT_NATIVE_SOURCE_HASH_BINDING')
  elif fid in fresh:
   x=fresh[fid];assert x['dropbox_content_hash']==n['content_hash'];item.update(source_image_path=x['local_path'],visual_source_kind='FRESH_CURRENT_ORIGINAL_HASH_VERIFIED',original_bytes_rehashed_current=True,original_sha256=x['sha256'])
  else:
   for candidate in c['originals']:
    path=pathlib.Path(candidate)
    if not path.is_file() or path.stat().st_size!=r['size']:continue
    sh,dh=hashes(path)
    if dh==n['content_hash']:
     item.update(source_image_path=str(path),visual_source_kind='EXISTING_ORIGINAL_REHASHED_AGAINST_CURRENT_NATIVE_HASH',original_bytes_rehashed_current=True,original_sha256=sh);break
  if not item['source_image_path']:
   item['visual_source_kind']='UNAVAILABLE_CURRENT_VISUAL_SOURCE';counts[item['visual_source_kind']]+=1;out.append(item);continue
  path=pathlib.Path(item['source_image_path']);item['actual_visual_source_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
  try:
   with Image.open(path) as im:item['source_dimensions']=list(im.size);item['source_format']=im.format
  except Exception as e:item.update(visual_source_kind='UNREADABLE_CURRENT_VISUAL_SOURCE',source_error=type(e).__name__)
  counts[item['visual_source_kind']]+=1;out.append(item)
 (P/'current-6360-visual-source-evidence.json').write_text(json.dumps(out,indent=2)+'\n');(P/'visual-source-coverage.json').write_text(json.dumps({'images':len(out),'counts':counts,'provenance_basis':'Cached derivatives used only when recorded source content hash equals the fresh native source hash. Such derivatives are not labelled original-byte rehashes. Original fallback and newly fetched images have actual bytes rehashed.','native_writes':0},indent=2)+'\n');print(json.dumps(counts),flush=True)
if __name__=='__main__':run()
