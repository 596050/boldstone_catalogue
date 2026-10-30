"""Save the prepared app field overlay with backups and per-item version guards."""
from pathlib import Path
from datetime import datetime, timezone
from contextlib import closing
import argparse
import hashlib
import json
import os
import sqlite3
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent
BASE = 'http://127.0.0.1:8767'
parser = argparse.ArgumentParser()
parser.add_argument('--apply', action='store_true')
args = parser.parse_args()
plan_bytes = (ROOT/'prepared-values.json').read_bytes()
plan = json.loads(plan_bytes)

def read(path):
    with urllib.request.urlopen(BASE+path,timeout=60) as response:
        return json.load(response)

boot = read('/api/bootstrap')
for key in ('register_sha256','gallery_sha256'):
    assert boot['source'][key] == plan['source'][key], ('Live source changed',key)
for path_key,hash_key in [('register','register_sha256'),('gallery_database','gallery_sha256')]:
    assert hashlib.sha256(Path(plan['source'][path_key]).read_bytes()).hexdigest() == plan['source'][hash_key]
data_root = Path(boot['data_directory'])
db_path = data_root/'reviews.sqlite3'
assert db_path == Path.home()/'Library/Application Support/BoldstoneReview/reviews.sqlite3'
stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
backup = data_root/'backups'/('before-specification-cleanup-'+stamp+'.sqlite3')
backup.parent.mkdir(exist_ok=True)
with closing(sqlite3.connect('file:'+str(db_path)+'?mode=ro',uri=True)) as db:
    db.row_factory = sqlite3.Row
    baseline = {table:[dict(row) for row in db.execute('SELECT * FROM '+table+' ORDER BY rowid')]
                for table in ('reviews','events','operations','deletion_jobs','deletion_batches')}
    existing = {(r['kind'],r['product_id'],r['item_id']):r for r in baseline['reviews']}
    for change in plan['changes']:
        old = existing.get(('field',change['product_id'],change['item_id']))
        assert (old['version'] if old else 0) == change['version'], ('Concurrent edit',change['product_id'],change['item_id'])
        if old:
            assert json.loads(old['data']) == change['before']['data']
    assert not [r for r in baseline['deletion_jobs'] if r['state'] in ('executing','deleting')], 'Native deletion in progress'
    if args.apply:
        assert not backup.exists()
        with closing(sqlite3.connect(backup)) as destination:
            db.backup(destination)
        backup.chmod(0o600)

if not args.apply:
    print(json.dumps({'ready':True,'changes':len(plan['changes']),'live_reviews':len(existing)}))
    raise SystemExit

assert not (ROOT/'apply-receipt.json').exists(), 'This batch has already been applied; read its receipt instead.'
(ROOT/'before-live-state.json').write_text(json.dumps(baseline,ensure_ascii=False,indent=2)+'\n')
receipts = []
with (ROOT/'save-results.jsonl').open('x') as log:
    for count,change in enumerate(plan['changes'],1):
        body = {'kind':'field','product_id':change['product_id'],'item_id':change['item_id'],
                'version':change['version'],'data':change['data']}
        request = urllib.request.Request(BASE+'/api/reviews',data=json.dumps(body).encode(),method='POST',headers={
            'Content-Type':'application/json','Origin':BASE,'X-Review-Token':boot['csrf_token']})
        try:
            with urllib.request.urlopen(request,timeout=90) as response:
                result = json.load(response)
        except Exception:
            # A lost response is not permission to retry a write. Read back once.
            product = read('/api/products/'+change['product_id'])
            result = next((r for r in product['reviews'] if r['kind']=='field' and r['item_id']==change['item_id']),{})
            if result.get('version') != change['version']+1 or result.get('data') != change['data']:
                raise
        assert result['version'] == change['version']+1
        assert result['data'] == change['data'], (change['product_id'],change['item_id'], 'Validation changed proposal')
        receipts.append(result)
        log.write(json.dumps(result,ensure_ascii=False)+'\n')
        log.flush()
        if count%100==0:
            print(json.dumps({'saved':count,'total':len(plan['changes'])}),flush=True)

receipt = {'finished_utc':datetime.now(timezone.utc).isoformat(),'source':plan['source'],
           'plan_sha256':hashlib.sha256(plan_bytes).hexdigest(),'backup':str(backup),
           'backup_sha256':hashlib.sha256(backup.read_bytes()).hexdigest(),
           'baseline_reviews':len(baseline['reviews']), 'baseline_event_cutoff':max(r['id'] for r in baseline['events']),
           'saved_fields':len(receipts),'specification_fields':1316,'title_punctuation_edits':167,
           'source_or_image_changes':False}
(ROOT/'apply-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt),flush=True)
