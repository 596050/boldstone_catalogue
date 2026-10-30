import concurrent.futures as cf,hashlib,json,urllib.request
from pathlib import Path
from PIL import Image
project=Path(__file__).resolve().parents[1];ev=project/'evidence';private=ev/'additional_sources.private.json';private.chmod(0o600)
links=json.loads(private.read_text());cache=json.loads((ev/'image_review_cache_index.json').read_text());media=Path('/Users/tprice/Library/Application Support/BoldstoneCatalogue/media')
def contenthash(b):return hashlib.sha256(b''.join(hashlib.sha256(b[x:x+4194304]).digest() for x in range(0,len(b),4194304))).hexdigest()
def run(r):
    out={k:v for k,v in r.items() if k!='download_url'}
    try:
        old=cache.get(r['id'],{}).get('local_path');p=Path(old) if old and Path(old).is_file() and contenthash(Path(old).read_bytes())==r['content_hash'] else media/(r['id'][3:]+'.image')
        if not p.exists() or contenthash(p.read_bytes())!=r['content_hash']:
            with urllib.request.urlopen(r['download_url'],timeout=60) as response:p.write_bytes(response.read())
        b=p.read_bytes();assert contenthash(b)==r['content_hash'],'Content hash mismatch'
        with Image.open(p) as im:out['image_size']=list(im.size)
        out.update(local_path=str(p),sha256=hashlib.sha256(b).hexdigest(),hash_verified=True)
    except Exception as exc:out['error']=str(exc)
    return out
with cf.ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(run,links))
for r in results:
    if r.get('hash_verified'):cache[r['id']]=r
receipt_file=ev/'additional_source_receipts.json'
previous=json.loads(receipt_file.read_text()) if receipt_file.exists() else []
receipts={r['id']:r for r in previous}
receipts.update({r['id']:r for r in results})
receipt_file.write_text(json.dumps(list(receipts.values()),ensure_ascii=False));(ev/'image_review_cache_index.json').write_text(json.dumps(cache,ensure_ascii=False));private.unlink()
# Invalidate only the candidate-feature cache because new images were added.
feature=ev/'current_cache_image_features.pickle'
if feature.exists():feature.unlink()
print(json.dumps(dict(attempted=len(results),verified=sum(r.get('hash_verified',False) for r in results),errors=[r for r in results if r.get('error')])))
