"""Read bounded native Dropbox headers from archival originals, without full downloads."""
from pathlib import Path
from datetime import datetime,timezone
from concurrent.futures import ThreadPoolExecutor,as_completed
import sys,json
from PIL import ImageFile
ROOT=Path('/Users/tprice/Documents/boldstone');OUT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'catalogue-review'))
from delete_dropbox import connection

targets=json.loads((OUT/'dropbox-overlooked-header-targets.json').read_text())
results=[]
with connection(ROOT) as (db,_):
    def check(p):
        row={**p,'checked_utc':datetime.now(timezone.utc).isoformat()}
        if p['bytes']>=50_000_000:return {**row,'status':'OVER_NATIVE_SIZE_LIMIT'}
        response=None
        try:
            m,response=db.files_download('rev:'+p['revision'])
            assert m.id==p['id'] and m.content_hash==p['content_hash'] and m.size==p['bytes']
            parser=ImageFile.Parser();count=0
            for chunk in response.iter_content(chunk_size=16384):
                if not chunk:continue
                count+=len(chunk);parser.feed(chunk)
                if parser.image or count>=1048576:break
            if not parser.image:raise ValueError('Header not determined within 1 MiB')
            w,h=parser.image.size
            row.update(status='NATIVE_REVISION_HEADER_VERIFIED',width=w,height=h,format=parser.image.format,mode=parser.image.mode,bytes_read=count,pixel_candidate=(w>=1500 and h>=1200) or (w>=1200 and h>=1500))
        except Exception as e:row.update(status='READ_UNVERIFIED',error_type=type(e).__name__,error=str(e))
        finally:
            if response is not None:response.close()
        return row
    with ThreadPoolExecutor(max_workers=2) as pool:
        tasks=[pool.submit(check,p) for p in targets]
        for f in as_completed(tasks):
            results.append(f.result());(OUT/'archival-original-headers.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
            if len(results)%10==0 or len(results)==len(targets):print(json.dumps(dict(checked=len(results),of=len(targets),pixel_candidates=sum(r.get('pixel_candidate',False) for r in results))),flush=True)
print('Bounded archival read complete; no complete originals retained by this check',flush=True)
