"""Read-only independent verification of the exact authorized stable IDs."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from collections import Counter
import json
import sqlite3
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from delete_dropbox import connection, verify_absent, stamp

output=Path(__file__).resolve().parent
database=Path.home()/'Library/Application Support/BoldstoneReview/reviews.sqlite3'
with sqlite3.connect('file:'+str(database)+'?mode=ro',uri=True) as db:
    db.row_factory=sqlite3.Row
    batches=[dict(db.execute('SELECT * FROM deletion_batches WHERE id=?',(bid,)).fetchone()) for bid in
             ['E46Z3JaFmHE7NrFxHW0Azx4he6y8IrYU','bwChstl6PcVufCmJX2DNO8KMtQ22vSxR']]
    operations=[]
    for batch in batches:
        for oid in json.loads(batch['payload'])['operation_ids']:
            row=dict(db.execute('SELECT * FROM deletion_jobs WHERE id=?',(oid,)).fetchone())
            payload=json.loads(row['payload']);result=json.loads(row['result'])
            assert row['state']=='deleted' and result['verified_absent']
            operations.append({'id':row['file_id'],'operation_id':oid,'batch_id':batch['id'],
                               'reviewed_name':payload['binding']['name'],'verified_name':payload['file']['name'],
                               'bytes':payload['file']['bytes'],'deletion_receipt':result})
    for row in json.loads((output/'prior-four-removals.json').read_text()):
        operations.append({'id':row['file_id'],'operation_id':row['operation_id'],'previously_absent':True,
                           'reviewed_name':row['payload']['binding']['name'],'deletion_receipt':row['result']})
assert len(operations)==192 and len({r['id'] for r in operations})==192
def check_chunk(rows):
    with connection(Path(__file__).resolve().parents[3]) as (client,root):
        return [{**row,'independent_readback':verify_absent(client,row['id'])} for row in rows]
with ThreadPoolExecutor(max_workers=4) as pool:
    results=[row for chunk in pool.map(check_chunk,[operations[i::4] for i in range(4)]) for row in chunk]
result={'checked_at':stamp(),'requested_deletions':188,'previously_absent':4,
        'states':dict(Counter(r['independent_readback']['state'] for r in results)),
        'all_verified_absent':all(r['independent_readback']['verified_absent'] for r in results),
        'no_mutations_in_this_check':True,'files':results}
(output/'independent-absence-readback.json').write_text(json.dumps(result,indent=2))
print(json.dumps({k:v for k,v in result.items() if k!='files'}))
