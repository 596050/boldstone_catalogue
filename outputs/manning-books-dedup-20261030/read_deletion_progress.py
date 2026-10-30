from datetime import datetime,timezone
from pathlib import Path
import json,sys
PROJECT=Path('/Users/tprice/Documents/boldstone');OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(PROJECT/'catalogue-review'))
from delete_dropbox import connection
from dropbox.common import PathRoot
from dropbox.files import FileMetadata
plan=json.loads((OUT/'deletion-review.json').read_text())
with connection(PROJECT) as (c,root):
    c=c.with_path_root(PathRoot.namespace_id('10782830832'))
    pg=c.files_list_folder('',recursive=True,limit=2000,include_deleted=False);rows=list(pg.entries)
    while pg.has_more:pg=c.files_list_folder_continue(pg.cursor);rows.extend(pg.entries)
    current={r.id:r for r in rows if isinstance(r,FileMetadata)}
    unchanged=0;errors=[]
    for r in plan['keepers']:
        m=current.get(r['id'])
        if m and all(getattr(m,k)==r[k] for k in ('rev','size','content_hash','path_lower')):unchanged+=1
        else:errors.append(r['id'])
    result={'checked_utc':datetime.now(timezone.utc).isoformat(),'current_files':len(current),'approved_files_absent':sum(r['id'] not in current for r in plan['removals']),'approved_files_total':4403,'keepers_verified_unchanged':unchanged,'keeper_errors':errors,'completed_batch_receipts':len(list(OUT.glob('deletion-batch-*-completion.json')))}
    (OUT/'deletion-progress.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))
