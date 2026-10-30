import json,hashlib,urllib.request,concurrent.futures,collections,posixpath
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import quote
H=Path(__file__).resolve().parent;read=lambda p:json.loads(Path(p).read_text());sha=lambda b:hashlib.sha256(b).hexdigest();write=lambda p,x:Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
(H/'originals').mkdir(exist_ok=True);req={x['file_id']:x for x in read(H/'source-requests.json')};md=read(H/'source-metadata-current.json');parents={v['folder']['path_display'].casefold():v['folder']['id']for v in md.values()if v['metadata_type']=='folder'}
def dbhash(b):return sha(b''.join(hashlib.sha256(b[i:i+4194304]).digest()for i in range(0,len(b),4194304)))
def get(x):
 fid=x['id'];expected=req[fid];meta=md[fid]['file'];dest=H/'originals'/(fid.split(':')[1]+'-'+x['name'])
 if not dest.exists():
  with urllib.request.urlopen(x['download_url'],timeout=90)as f:b=f.read()
  dest.write_bytes(b)
 else:b=dest.read_bytes()
 assert len(b)==x['size']==expected['size']==meta['size'];assert dbhash(b)==x['content_hash'];assert meta['id']==fid and meta['name']==expected['name'];assert not expected['rev']or meta['rev']==expected['rev']
 if expected['sha256']:assert sha(b)==expected['sha256']
 if expected['content_hash']:assert dbhash(b)==expected['content_hash']
 parent=parents[posixpath.dirname(meta['path_display']).casefold()]
 return{'file_id':fid,'folder_id':parent,'name':meta['name'],'path_display':meta['path_display'],'size':len(b),'sha256':sha(b),'content_hash':dbhash(b),'rev':meta['rev'],'local_original':str(dest),'image_url':'https://www.dropbox.com/preview'+quote(meta['path_display'],safe='/'),'folder_url':'https://www.dropbox.com/home'+quote(posixpath.dirname(meta['path_display']),safe='/'),'pixels_edited':False}
links=read(H/'download-links.private.json');files=list(concurrent.futures.ThreadPoolExecutor(max_workers=4).map(get,links['entries']));write(H/'original-verification.json',{'status':'PASS','files':files,'new_images_created':0,'pixels_edited':False});(H/'download-links.private.json').unlink()
scope=read(H/'scope.json');events=collections.defaultdict(dict);packets={k:read(p)for k,p in scope['approvals'].items()}
for oid,d in packets.items():
 e=d.get('source_owner_event',d.get('owner_instruction'));path=e.get('transcript_path',e.get('path'));digest=e.get('event_sha256',e.get('raw_sha256'));events[path].setdefault(digest,{'event':e,'option_ids':[]})['option_ids'].append(oid)
verified=[]
for path,expected in events.items():
 found={}
 with Path(path).open('rb')as f:
  for lineno,line in enumerate(f,1):
   for digest in [sha(line),sha(line.rstrip(b'\r\n'))]:
    if digest not in expected:continue
    e=expected[digest]['event'];z=json.loads(line);payload=z['payload']
    if z['type']=='event_msg':assert payload['type']=='user_message';text=payload['message']
    else:assert z['type']=='response_item'and payload['role']=='user';text=''.join(c.get('text','')for c in payload['content'])
    assert text==e['text']and z['timestamp']==e['timestamp'];found[digest]={'event_sha256':digest,'line':lineno,'timestamp':z['timestamp'],'option_ids':expected[digest]['option_ids'],'actual_owner_text_verified':True}
 assert set(found)==set(expected),(path,list(set(expected)-set(found)));verified.extend(found.values())
byid={x['file_id']:x for x in files};refs={fid:{**{k:v for k,v in x.items()if k not in ['local_original','sha256','content_hash','size','pixels_edited']},'path':'ns:202238505/'+x['path_display'],'native_reference_status':'VERIFIED_CURRENT_FILE_ID_REVISION_AND_ACTUAL_PARENT','physical_cast_or_size_certified':False}for fid,x in byid.items()}
for oid,d in packets.items():
 for r in d['approved_reference_roles']:
  src=r['source'];fid=src.get('id',src.get('file_id'));expectedparent=r.get('folder_id',src.get('folder_id'))
  if expectedparent:assert refs[fid]['folder_id']==expectedparent,(oid,fid)
write(H/'current-source-references.json',refs);write(H/'source-evidence-verification.json',{'status':'PASS','recorded_utc':datetime.now(timezone.utc).isoformat(),'owner_events':verified,'seven_packet_targets_verified':sorted(packets),'source_originals':files,'source_pixels_edited':False,'Dropbox_mutations':0,'platform_writes':0});write(H/'evidence-manifest.json',{str(H/n):{'sha256':sha((H/n).read_bytes())}for n in ['source-metadata-current.json','current-source-references.json','source-evidence-verification.json','original-verification.json']});print(json.dumps({'status':'PASS','packets':len(packets),'unique_owner_events':len(verified),'source_originals':len(files),'bytes':sum(x['size']for x in files)}))
