import concurrent.futures
import hashlib
import io
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from PIL import Image, ImageOps

P=Path(__file__).resolve().parent
Image.MAX_IMAGE_PIXELS=250_000_000
def hashes(data):return hashlib.sha256(data).hexdigest(),hashlib.sha256(b''.join(hashlib.sha256(data[i:i+4194304]).digest() for i in range(0,len(data),4194304))).hexdigest()
def run(payload):
    expected={r['file_id']:r for r in json.loads((P/'all-180-original-prewrite-hashes.json').read_text())}
    target=P/'verified-postmove-originals';target.mkdir(exist_ok=True)
    def one(record):
        out={k:v for k,v in record.items() if k!='download_url'}
        with urllib.request.urlopen(record['download_url'],timeout=120) as response:
            assert response.status==200
            data=response.read()
        sh,dh=hashes(data);pre=expected[record['id']]
        assert len(data)==pre['size']==record['size']
        assert sh==pre['sha256'] and dh==pre['dropbox_content_hash']==record['content_hash']
        path=target/(record['id'].replace('id:','')+'__'+record['name']);path.write_bytes(data)
        with Image.open(io.BytesIO(data)) as im:
            out.update(dimensions=list(im.size),display_dimensions=list(ImageOps.exif_transpose(im).size),image_format=im.format)
        out.update(local_path=str(path),sha256=sh,dropbox_content_hash=dh,fresh_http_download=True,verified_utc=datetime.now(timezone.utc).isoformat())
        return out
    result=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        futures={pool.submit(one,r):r['id'] for r in payload['entries']}
        for future in concurrent.futures.as_completed(futures):
            try:result.append(future.result())
            except Exception as error:result.append({'id':futures[future],'error_type':type(error).__name__})
    (P/'twenty-three-fresh-postmove-originals.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'fresh_downloads_verified':sum('sha256' in r for r in result),'failures':[r for r in result if 'error_type' in r]}),flush=True)

if __name__=='__main__':run(json.load(sys.stdin))
