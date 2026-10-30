"""Publish the verified owner decision with source CAS and idle native leases."""
from contextlib import closing
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import fcntl, hashlib, json, os, sqlite3, sys, urllib.request
H=Path(__file__).resolve().parent; PROJECT=H.parents[2]; BASE=PROJECT/'sculpture-catalogue'
OUT=BASE/'components/reconciliation/lava-moon-three-white-products-2026-10-29'
RUNTIME=Path('/Users/tprice/Library/Application Support/BoldstoneReview')
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
write=lambda p,v:Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def api(path):
    with urllib.request.urlopen('http://127.0.0.1:8767/api/'+path,timeout=60) as r:return json.load(r)
def rows():
    with closing(sqlite3.connect('file:'+str(RUNTIME/'reviews.sqlite3')+'?mode=ro',uri=True)) as db:
        db.row_factory=sqlite3.Row
        return [dict(r) for r in db.execute('SELECT * FROM reviews ORDER BY kind,product_id,item_id')]
def put(path,value):
    tmp=path.with_name(path.name+'.lava-moon-pending')
    tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');os.replace(tmp,path)
def update_controls(old,new):
    controls=[BASE/'components/reviews/specification_review_progress.json',BASE/'components/checkpoint.json',BASE/'checkpoint.json',BASE/'current-master.json']
    before={};values={};changed=[]
    for p in controls:
        before[p]=p.read_bytes();current=read(p)
        if p.name=='current-master.json':assert current==old;values[p]=new
        else:assert current['current_master_catalogue']==old;current['current_master_catalogue']=new;values[p]=current
    try:
        for p in controls:
            assert p.read_bytes()==before[p],str(p);put(p,values[p]);changed.append(p)
        assert all(read(p)==values[p] for p in controls)
    except BaseException:
        for p in reversed(changed):
            if read(p)==values[p]:p.write_bytes(before[p])
        raise
def idle():
    j=api('jobs')
    assert not j.get('active_count') and not j.get('reservation')
    assert not any(x['state'] in ('queued','running','uncertain') for x in j['jobs'])
    return j
if '--apply' not in sys.argv:raise SystemExit('Pass --apply to publish the verified owner decision.')
v=read(OUT/'independent-verification.json');m=read(OUT/'input-manifest.json');new=read(OUT/'next-current-master.json');d=read(OUT/'owner-decision.json')
assert v['status']=='PASS_THREE_WHITE_PRODUCTS_PRESERVATION'
assert sha(OUT/'canonical-master-register.json')==v['register_sha256']==new['register_sha256']
assert sha(OUT/'gallery-projection/complete-image-platform-register.sqlite')==v['gallery_sha256']
for name,rec in m['controls'].items():assert sha(BASE/name)==rec['sha256'],name
for k in ('input_register','input_gallery'):assert sha(m[k]['path'])==m[k]['sha256']
before=rows();affected=set(d['active_option_ids'])|set(d['retired_option_ids'])
assert [r for r in before if r['product_id'] in affected]==[r for r in read(OUT/'inputs/saved-reviews.json') if r['product_id'] in affected], 'Lava Moon choices changed; revalidate before publication.'
assert api('health')['version']=='2.14.15'
jobs_before=idle()
with (RUNTIME/'native-jobs/writer.lock').open('a') as writer,(RUNTIME/'deletion-review-reader.lock').open('a') as reader:
    fcntl.flock(writer,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(reader,fcntl.LOCK_EX|fcntl.LOCK_NB)
    idle()
    for name,rec in m['controls'].items():assert sha(BASE/name)==rec['sha256'],name
    previous=read(BASE/'current-master.json')
    receipt={'status':'PUBLISHED_READBACK_PENDING','published_utc':datetime.now(timezone.utc).isoformat(),
        'register_sha256':v['register_sha256'],'gallery_sha256':v['gallery_sha256'],
        'active_options':181,'retained_options':191,'retired_options':10,'native_writes':0,'specification_changes':0}
    write(OUT/'publication-receipt.json',receipt);update_controls(previous,new)
    boot=api('bootstrap');active={p['id']:p for p in boot['products']}
    assert len(active)==181 and {p for p,r in active.items() if r['family']=='Lava Moon'}==set(d['active_option_ids'])
    assert not set(d['retired_option_ids'])&active.keys()
    for pid in d['active_option_ids']:
        detail=api('products/'+pid)
        write(OUT/('live-'+pid+'.json'),detail)
        assert not any(a['id'] in v['context_only_images'] for a in detail['images'])
    after=rows();bykey={(r['kind'],r['product_id'],r['item_id']):r for r in after}
    assert len(before)==len(after) and all(r==bykey[(r['kind'],r['product_id'],r['item_id'])] for r in before)
    after_jobs=api('jobs')
    assert [(j['id'],j['state']) for j in jobs_before['jobs']]==[(j['id'],j['state']) for j in after_jobs['jobs']]
    receipt.update(status='PASS_PUBLISHED_THREE_WHITE_PRODUCTS_LIVE_READBACK',verified_utc=datetime.now(timezone.utc).isoformat(),
        all_saved_reviews_preserved=len(before), job_history_preserved=True,
        context_only_images=v['context_only_images'],all_control_mirrors_verified=True,live_app_version='2.14.15')
    write(OUT/'publication-receipt.json',receipt)
    final=deepcopy(new)
    final['current_review_application'].update(status='PUBLISHED181_SOURCE_AND_APP2_14_15_VERIFIED',source_rebase_required=False,
        last_verified_utc=receipt['verified_utc'],verification=str((OUT/'publication-receipt.json').relative_to(BASE)),
        verification_sha256=sha(OUT/'publication-receipt.json'),contract_sha256=sha(PROJECT/'catalogue-review/README.md'))
    final['current_published_gallery_projection']['status']='CURRENT181_LAVA_MOON_THREE_WHITE_PRODUCTS_VERIFIED'
    update_controls(new,final);write(OUT/'final-current-master.json',final)
    print(json.dumps(receipt,indent=2))
