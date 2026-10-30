"""Read-only verification of the app owner's source-only rebase and live service."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,sqlite3,urllib.request,urllib.error

H=Path(__file__).resolve().parent;ROOT=H.parents[3]
A=ROOT/'catalogue-review/reviews/family-gallery-types-20261026'
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
reb=read(A/'retirement-rebase.json');g=read(H/'canonical-master-register.json');delta=read(H/'SOURCE_READY_FOR_APP_REBASE.json')
OID=delta['option_id'];checks=0
def check(value,message):
    global checks
    checks+=1
    assert value,message
def snapshot(path):
    con=sqlite3.connect(Path(path).as_uri()+'?mode=ro',uri=True);con.row_factory=sqlite3.Row
    try:
        con.execute('BEGIN')
        events=[dict(r) for r in con.execute('SELECT * FROM events ORDER BY id')]
        reviews=[dict(r) for r in con.execute('SELECT * FROM reviews ORDER BY kind,product_id,item_id')]
        operations=[dict(r) for r in con.execute('SELECT * FROM operations ORDER BY id')]
        tables=[r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        return {'events':events,'reviews':reviews,'operations':operations,'tables':tables}
    finally:con.close()
def unpack(row):
    if row is None:return None
    r=dict(row)
    if isinstance(r.get('data'),str):r['data']=json.loads(r['data'])
    if isinstance(r.get('original'),str):r['original']=json.loads(r['original'])
    return r
def key(r):return (r['kind'],r['product_id'],r['item_id'])
before_path=A/'before-retirement-rebase.sqlite3'
before=snapshot(before_path);live_path=Path(reb['data_directory'])/'reviews.sqlite3';live=snapshot(live_path)
check(reb['old_source_hash']==delta['old_register_sha256'],'Old source binding')
check(reb['new_source_hash']==delta['new_register_sha256']==sha(H/'canonical-master-register.json'),'Published source binding')
start,end=reb['event_cutoff_before'],reb['event_cutoff_after']
check(before['events'][-1]['id']==start,'Before backup exact event cutoff')
check([r for r in live['events'] if r['id']<=start]==before['events'],'All historical events byte values preserved')
events=[r for r in live['events'] if start<r['id']<=end]
check(len(events)==reb['reviews_to_rebind']==1839,'Exact source-binding event range')
original={key(r):unpack(r) for r in before['reviews']};at_cutoff=dict(original);rebound=[]
for event in events:
    old=unpack(json.loads(event['before_json']));new=unpack(json.loads(event['after_json']))
    k=key(new);check(k in at_cutoff and at_cutoff[k]==old,'Event before matches durable state')
    check(new['source_hash']==delta['new_register_sha256'] and old['source_hash']==delta['old_register_sha256'],'Exact old/new source hash')
    check(new['product_id'] in g['active_option_ids'] or new['product_id'] in ('','__library__'),'No retired review rebind')
    for field in ['kind','product_id','item_id','version','data','original']:check(old[field]==new[field],'Only binding/time changed: '+field)
    check(set(old)==set(new),'Review schema unchanged')
    at_cutoff[k]=new;rebound.append(k)
check(len(set(rebound))==len(rebound),'Each rebound review exactly once')
historic=[k for k,r in original.items() if r['product_id'] not in g['active_option_ids'] and r['product_id'] not in ('','__library__')]
check(len(historic)==reb['historical_rows_preserved']==18,'18 historical rows preserved')
check(all(at_cutoff[k]==original[k] for k in historic),'Retired review values/bindings/version untouched')
check(len(at_cutoff)==len(original)==1857,'No review row removed or created by rebase')
current={key(r):unpack(r) for r in live['reviews']}
for event in [r for r in live['events'] if r['id']>end]:at_cutoff[key(json.loads(event['after_json']))]=unpack(json.loads(event['after_json']))
check(at_cutoff==current,'Current durable rows follow preserved audit events')
check(set(before['tables'])<=set(live['tables']),'Historical DB tables preserved')
before_ops={r['id']:r for r in before['operations']};live_ops={r['id']:r for r in live['operations']}
check(all(live_ops.get(k)==v for k,v in before_ops.items()),'Existing transfer operations preserved')
def get(path):
    with urllib.request.urlopen('http://127.0.0.1:8767'+path,timeout=15) as r:return json.load(r)
health=get('/api/health');bootstrap=get('/api/bootstrap')
check(health['version']=='2.4.0' and health['products']==187,'Live v2.4.0 has187 options')
check({p['id'] for p in bootstrap['products']}==set(g['active_option_ids']),'Live exact active IDs')
check(OID not in {p['id'] for p in bootstrap['products']},'Retired option absent from live list')
check(bootstrap['source']['register_sha256']==delta['new_register_sha256'],'Live new register hash')
check(bootstrap['source']['gallery_sha256']==delta['unchanged_gallery_sha256'],'Live unchanged source gallery hash')
check(sha(bootstrap['source']['gallery_database'])==delta['unchanged_gallery_sha256'],'Saved gallery bytes unchanged')
try:get('/api/products/'+OID)
except urllib.error.HTTPError as e:check(e.code==404,'Retired API returns404')
else:raise AssertionError('Retired product API unexpectedly succeeds')
check(all(r['target'] not in read(bootstrap['source']['live_dropbox']['path'])['records'] for r in read(H/'native-readback.json')['rows']),'Live native snapshot excludes retired owned IDs')
report={'status':'PASS_INDEPENDENT_LIVE187_AND_SOURCE_REBASE','checked_utc':datetime.now(timezone.utc).isoformat(),
    'checks':checks,'live_app_version':health['version'],'live_active_options':187,'register_sha256':delta['new_register_sha256'],
    'gallery_sha256':delta['unchanged_gallery_sha256'],'before_backup':str(before_path),'before_backup_sha256':sha(before_path),
    'app_owner_rebase_receipt':str(A/'retirement-rebase.json'),'app_owner_rebase_receipt_sha256':sha(A/'retirement-rebase.json'),
    'event_cutoff_before':start,'event_cutoff_after_rebase':end,'event_cutoff_at_readback':live['events'][-1]['id'],
    'source_binding_only_events_verified':len(events),'review_rows_before':len(original),'review_rows_at_readback':len(current),
    'historical_review_rows_unchanged':len(historic),'all_preexisting_audit_events_preserved':True,
    'all_review_values_originals_versions_preserved_by_rebase':True,'retired_product_api_status':404,
    'live_native_snapshot':bootstrap['source']['live_dropbox'],'root_db_code_native_platform_mutations':0}
(H/'app-rebase-independent-verification.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
