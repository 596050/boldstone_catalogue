import concurrent.futures,hashlib,json,pathlib,sys,urllib.request
P=pathlib.Path(__file__).resolve().parent
def hashes(data):
 blocks=b''.join(hashlib.sha256(data[i:i+4194304]).digest() for i in range(0,len(data),4194304))
 return hashlib.sha256(data).hexdigest(),hashlib.sha256(blocks).hexdigest()
def run(records,output_name='verified-new-current-originals.json'):
 native={r['id']:r for r in json.loads((P/'fresh-all-6360-native-hash-metadata.json').read_text())['entries']}
 current={r['file_id']:r for r in json.loads((P/'all-current-6360-image-folder-links.json').read_text())}
 folder=P/'new-current-originals';folder.mkdir(exist_ok=True)
 def one(r):
  assert r['content_hash']==native[r['id']]['content_hash'] and r['size']==current[r['id']]['size']
  target=folder/(r['id'].replace('id:','')+'__'+r['name'])
  if target.exists():data=target.read_bytes()
  else:
   with urllib.request.urlopen(r['download_url'],timeout=90) as response:
    assert response.status==200;data=response.read()
  sh,dh=hashes(data);assert len(data)==r['size'] and dh==r['content_hash'];target.write_bytes(data)
  return {**{k:v for k,v in r.items() if k!='download_url'},'local_path':str(target),'sha256':sh,'dropbox_content_hash':dh,'family':current[r['id']]['family']}
 out=[]
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
  for result in ex.map(one,records):out.append(result)
 target_receipt=P/output_name
 assert not target_receipt.exists(),'Do not overwrite a completed original receipt'
 target_receipt.write_text(json.dumps(out,indent=2)+'\n');print('VERIFIED_CURRENT_ORIGINALS',len(out),flush=True)
