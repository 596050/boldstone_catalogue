from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
import json, sys, time

PROJECT = Path('/Users/tprice/Documents/boldstone')
OUT = Path(__file__).resolve().parent
sys.path.insert(0,str(PROJECT/'catalogue-review'))
from delete_dropbox import connection
from dropbox.common import PathRoot
from dropbox.exceptions import RateLimitError
from dropbox.files import FileMetadata

inventory = json.loads((OUT/'native-inventory.json').read_text())
rows = [r for r in inventory['entries'] if r['object_type']=='file']
output = OUT/'verified-metadata.json'
results = json.loads(output.read_text()) if output.exists() else []
done = {x['id'] for x in results if x.get('success')}
rows = [x for x in rows if x['id'] not in done]
results = [x for x in results if x.get('success')]

with connection(PROJECT) as (client, verified_catalogue_root):
    scoped = client.with_path_root(PathRoot.namespace_id('10782830832'))
    def verify(row):
        result = {'id':row['id'],'expected_rev':row['rev']}
        try:
            for attempt in range(3):
                try:
                    m = scoped.files_get_metadata(row['id'])
                    break
                except RateLimitError as exc:
                    if attempt==2: raise
                    time.sleep(min(max(exc.backoff or 1,1),55))
            assert isinstance(m,FileMetadata)
            assert m.id==row['id'] and m.rev==row['rev'] and m.size==row['size'] and m.content_hash==row['content_hash'] and m.path_lower==row['path_lower'], 'File changed since inventory'
            result.update(success=True,rev=m.rev,path_display=m.path_display,size=m.size,content_hash=m.content_hash,checked_utc=datetime.now(timezone.utc).isoformat())
            s=getattr(m,'sharing_info',None)
            if s:
                result['sharing_info']={k:getattr(s,k) for k in ('parent_shared_folder_id','read_only') if getattr(s,k,None) is not None}
        except Exception as exc:
            result.update(success=False,error_type=type(exc).__name__,error=str(exc))
        return result
    with ThreadPoolExecutor(max_workers=10) as pool:
        for future in as_completed([pool.submit(verify,r) for r in rows]):
            results.append(future.result())
            if len(results)%100==0:
                output.write_text(json.dumps(results,indent=2))
                print(json.dumps({'verified':len(results),'failures':sum(not x.get('success') for x in results)}),flush=True)
    output.write_text(json.dumps(results,indent=2))
    print(json.dumps({'verified':len(results),'failures':sum(not x.get('success') for x in results),'complete':True}),flush=True)
