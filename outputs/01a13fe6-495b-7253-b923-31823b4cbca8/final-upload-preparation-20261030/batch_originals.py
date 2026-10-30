"""Read originals concurrently, retaining exact-byte receipts. No Dropbox writes."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from contextlib import closing
import json, sys, os, uuid, time

PROJECT = Path('/Users/tprice/Documents/boldstone')
OUT = Path(__file__).resolve().parent
RUNTIME = Path('/Users/tprice/Library/Application Support/BoldstoneReview')
sys.path.insert(0, str(PROJECT/'catalogue-review'))
from delete_dropbox import connection
from fetch_original import check_metadata
from media import MediaCache, verified_original_metadata

def worker(items):
    receipts=[]
    with connection(PROJECT) as (client, root):
        for a in items:
            aid=a['id']; native=a['original']; h=native['dropbox_content_hash']
            target=RUNTIME/'originals'/(h+'.image'); rp=RUNTIME/'originals'/(h+'.json')
            tmp=target.with_name(h+'.'+uuid.uuid4().hex+'.tmp')
            receipt={'id':aid,'name':a['name'],'expected_hash':h}
            for attempt in range(3):
                try:
                    prior=verified_original_metadata(RUNTIME,h,native['bytes'])
                    if prior:
                        receipt.update(status='verified',original=prior,cached=True)
                    elif target.exists():
                        info=MediaCache(RUNTIME).inspect(target,hashes=True)
                        assert info['dropbox_content_hash']==h and info['bytes']==native['bytes']
                        receipt.update(status='verified',original=info,cached=True)
                    else:
                        meta,response=client.files_download(aid)
                        with closing(response):
                            check_metadata(meta,aid,h,native['bytes'],'/BOLDSTONE MASTER/Products/01 Wall Sculptures')
                            length=0
                            with tmp.open('xb') as f:
                                os.chmod(tmp,0o600)
                                for b in response.iter_content(chunk_size=1048576):
                                    length+=len(b)
                                    assert length<=native['bytes']
                                    f.write(b)
                        info=MediaCache(RUNTIME).inspect(tmp,hashes=True)
                        assert info['dropbox_content_hash']==h and info['bytes']==native['bytes']
                        assert info['dimensions'], 'Original dimensions unreadable'
                        info={k:info[k] for k in ('bytes','dimensions','sha256','dropbox_content_hash')}
                        info.update(file_id=aid,path=str(target),original_path=meta.path_display,checked_utc=datetime.now(timezone.utc).isoformat(),dropbox_mutations=0)
                        tmp.replace(target)
                        rtmp=rp.with_suffix('.'+uuid.uuid4().hex+'.tmp');rtmp.write_text(json.dumps(info,indent=2));rtmp.replace(rp)
                        receipt.update(status='verified',original=info)
                        # The receipt retains verified metadata; keep disk use bounded.
                        target.unlink()
                    break
                except Exception as e:
                    tmp.unlink(missing_ok=True)
                    receipt.update(status='failed',error_type=type(e).__name__)
                    delay=max(2*(attempt+1),getattr(e,'backoff',0) or 0)
                    time.sleep(min(delay,30))
            (OUT/'dimension-receipts'/ (aid.replace(':','_')+'.json')).write_text(json.dumps(receipt,indent=2))
            print(json.dumps({'id':aid,'status':receipt['status'],'name':a['name']}),flush=True)
            receipts.append(receipt)
    return receipts

if __name__=='__main__':
    items=json.loads((OUT/'selected-images.json').read_text());queue=[i['image'] for i in items if not i['image']['original'].get('dimensions')]
    (OUT/'dimension-receipts').mkdir(exist_ok=True)
    with ThreadPoolExecutor(max_workers=3) as pool:
        result=[x for f in as_completed([pool.submit(worker,queue[i::3]) for i in range(3)]) for x in f.result()]
    (OUT/'original-verification.json').write_text(json.dumps(result,indent=2))
    print(json.dumps({'checked':len(result),'verified':sum(r['status']=='verified' for r in result)}))
