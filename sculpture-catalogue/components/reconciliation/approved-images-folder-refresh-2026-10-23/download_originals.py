import json,hashlib,urllib.request,concurrent.futures
from pathlib import Path
H=Path(__file__).resolve().parent;read=lambda p:json.loads(Path(p).read_text());sha=lambda b:hashlib.sha256(b).hexdigest()
(H/'originals').mkdir(exist_ok=True)
def dbhash(b):return sha(b''.join(hashlib.sha256(b[i:i+4194304]).digest()for i in range(0,len(b),4194304)))
def get(x):
 fid=x.get('id',x.get('file_id')); dest=H/'originals'/(fid.split(':')[1]+'-'+x['name']);url=x['download_url']
 if not dest.exists():
  with urllib.request.urlopen(url,timeout=90)as r:b=r.read()
  dest.write_bytes(b)
 else:b=dest.read_bytes()
 assert len(b)==x['size'];assert dbhash(b)==x['content_hash'],fid
 return{'file_id':fid,'name':x['name'],'path_display':x.get('path_display'),'size':len(b),'sha256':sha(b),'content_hash':dbhash(b),'local_original':str(dest),'pixels_edited':False}
links=read(H/'download-links.private.json');out=list(concurrent.futures.ThreadPoolExecutor(max_workers=4).map(get,links['entries']))
s=read(H/'scope.json')
for k,p in s['approvals'].items():
 d=read(p)
 if 'accepted_reference'in d:
  ref=d['accepted_reference'];f=next(x for x in out if x['file_id']==ref['file_id']);assert f['sha256']==ref['source_sha256'];assert f['content_hash']==ref['content_hash']
 for z in d.get('approved_reference_roles',[]):
  src=z['source'];f=next(x for x in out if x['file_id']==src['id']);assert f['sha256']==src['sha256']
for number in [1,3]:
 p=Path(read(H/'input-manifest.json')['archived_acanthus_'+str(number)]['snapshot']);f=next(x for x in out if x['name'].endswith(f'__{number:03}.jpg'));assert p.read_bytes()==Path(f['local_original']).read_bytes()
(H/'download-verification.json').write_text(json.dumps({'status':'PASS','files':out,'verified_approved_and_archived_sources':True,'pixels_edited':False},indent=2)+'\n')
(H/'download-links.private.json').unlink()
print(json.dumps({'status':'PASS','files':len(out),'bytes':sum(x['size']for x in out),'restored_originals_byte_equal':2}))
