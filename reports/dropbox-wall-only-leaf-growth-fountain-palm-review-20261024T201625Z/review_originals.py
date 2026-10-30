import concurrent.futures, datetime, hashlib, io, json, pathlib, sys, urllib.request
from PIL import Image, ImageOps

ROOT = pathlib.Path(__file__).parent
Image.MAX_IMAGE_PIXELS = 250_000_000

def hashes(data):
    blocks = b''.join(hashlib.sha256(data[i:i+4*1024*1024]).digest() for i in range(0,len(data),4*1024*1024))
    return hashlib.sha256(data).hexdigest(), hashlib.sha256(blocks).hexdigest()

def run(payload):
    candidates = json.loads((ROOT/'candidate-local-original-paths.json').read_text())
    listing = json.loads((ROOT/'fresh-complete-native-listings.json').read_text())
    family_by_id = {e['file_id']:r['name'] for r in listing['listings'] for e in r['result']['entries'] if e['object_type']=='file'}
    def one(r):
        clean={k:v for k,v in r.items() if k!='download_url'}
        clean['family']=family_by_id[r['id']]
        reused=False
        data=None
        for name in candidates.get(r['id'],[]):
            q=pathlib.Path(name)
            if q.is_file() and q.stat().st_size==r['size']:
                trial=q.read_bytes(); sh,dh=hashes(trial)
                if dh==r['content_hash']:
                    data=trial; target=q; reused=True; break
        if data is None:
            target=ROOT/'originals'/clean['family']/(r['id'].replace('id:','')+'__'+r['name'])
            target.parent.mkdir(parents=True,exist_ok=True)
            if target.exists():
                trial=target.read_bytes(); sh,dh=hashes(trial)
                if len(trial)==r['size'] and dh==r['content_hash']:data=trial;reused=True
            if data is None:
                with urllib.request.urlopen(r['download_url'],timeout=120) as resp:
                    assert resp.status==200
                    data=resp.read()
                assert len(data)==r['size']
                sh,dh=hashes(data)
                assert dh==r['content_hash']
                target.write_bytes(data)
        sh,dh=hashes(data)
        assert len(data)==r['size'] and dh==r['content_hash']
        with Image.open(io.BytesIO(data)) as im:
            clean.update(dimensions=list(im.size),image_format=im.format,display_dimensions=list(ImageOps.exif_transpose(im).size))
        clean.update(local_path=str(target),sha256=sh,dropbox_content_hash=dh,reused_native_identical_local_bytes=reused,verified_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
        return clean
    out=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        fs={ex.submit(one,r):r['id'] for r in payload['entries']}
        for future in concurrent.futures.as_completed(fs):
            try:out.append(future.result())
            except Exception as e:out.append({'id':fs[future],'error_type':type(e).__name__})
    path=ROOT/('original-batch-'+str(payload['batch'])+'.json')
    path.write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps({'batch':payload['batch'],'verified':sum('sha256' in r for r in out),'errors':[r for r in out if 'error_type' in r],'reused':sum(r.get('reused_native_identical_local_bytes',False) for r in out)}),flush=True)

if __name__=='__main__':run(json.load(sys.stdin))
