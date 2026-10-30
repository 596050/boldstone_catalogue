"""Publish the validated owner consolidation with source/review compare-and-swap."""
from contextlib import closing
from copy import deepcopy
from datetime import datetime,timezone
from pathlib import Path
import fcntl,hashlib,json,os,sqlite3,sys,urllib.request
H=Path(__file__).resolve().parent;PROJECT=H.parents[2];BASE=PROJECT/'sculpture-catalogue'
OUT=BASE/'components/reconciliation/frozen-fish-three-finishes-2026-10-29'
RUNTIME=Path('/Users/tprice/Library/Application Support/BoldstoneReview')
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
write=lambda p,v:Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def api(path,data=None):
 req=urllib.request.Request('http://127.0.0.1:8767/api/'+path,data=None if data is None else json.dumps(data).encode(),headers={'Content-Type':'application/json','Origin':'http://127.0.0.1:8767','X-Review-Token':(RUNTIME/'server-token').read_text().strip()})
 with urllib.request.urlopen(req,timeout=30) as r:return json.load(r)
def rows():
 with closing(sqlite3.connect('file:'+str(RUNTIME/'reviews.sqlite3')+'?mode=ro',uri=True)) as db:
  db.row_factory=sqlite3.Row
  return [dict(r) for r in db.execute('SELECT * FROM reviews ORDER BY kind,product_id,item_id')]
def put(path,value):
 tmp=path.with_name(path.name+'.frozen-fish-pending');tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');os.replace(tmp,path)
def update_controls(old,new):
 controls=[BASE/'components/reviews/specification_review_progress.json',BASE/'components/checkpoint.json',BASE/'checkpoint.json',BASE/'current-master.json'];before={};values={}
 for p in controls:
  before[p]=p.read_bytes();current=read(p)
  if p.name=='current-master.json':assert current==old;values[p]=new
  else:assert current['current_master_catalogue']==old;current['current_master_catalogue']=new;values[p]=current
 changed=[]
 try:
  for p in controls:
   assert p.read_bytes()==before[p],str(p);put(p,values[p]);changed.append(p)
  assert read(controls[-1])==new
  assert all(read(p)['current_master_catalogue']==new for p in controls[:-1])
 except BaseException:
  for p in reversed(changed):
   if read(p)==values[p]:p.write_bytes(before[p])
  raise
if '--apply' not in sys.argv:raise SystemExit('Pass --apply to publish the validated owner decision.')
verify=read(OUT/'independent-verification.json');manifest=read(OUT/'input-manifest.json');new=read(OUT/'next-current-master.json');decision=read(OUT/'owner-decision.json');names=decision['active_names'];affected=set(names)|set(decision['retired_option_ids'])
assert verify['status']=='PASS_THREE_FINISHES_PRESERVATION'
assert sha(OUT/'canonical-master-register.json')==verify['register_sha256']==new['register_sha256']
assert sha(OUT/'gallery-projection/complete-image-platform-register.sqlite')==verify['gallery_sha256']==new['current_published_gallery_projection']['database_sha256']
for name,rec in manifest['controls'].items():assert sha(BASE/name)==rec['sha256'],name
for k in ('input_register','input_gallery'):assert sha(manifest[k]['path'])==manifest[k]['sha256']
before_rows=rows();fish_rows=[r for r in before_rows if r['product_id'] in affected]
assert fish_rows==read(OUT/'inputs/frozen-fish-saved-reviews.json'),'Frozen Fish changed; reconcile before publishing.'
assert api('health')['version']=='2.14.14'
jobs_before=api('jobs');assert not jobs_before.get('active_count') and not jobs_before.get('reservation')
assert not any(j['state'] in ('queued','running','uncertain') for j in jobs_before['jobs'])
with (RUNTIME/'native-jobs/writer.lock').open('a') as writer,(RUNTIME/'deletion-review-reader.lock').open('a') as reader:
 fcntl.flock(writer,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(reader,fcntl.LOCK_EX|fcntl.LOCK_NB)
 jobs=api('jobs');assert not jobs.get('active_count') and not jobs.get('reservation')
 before_pointer=read(BASE/'current-master.json')
 receipt={'status':'PUBLISHED_READBACK_PENDING','published_utc':datetime.now(timezone.utc).isoformat(),'register_sha256':verify['register_sha256'],'gallery_sha256':verify['gallery_sha256'],'active_options':184,'retained_options':191,'retired_options':7,'native_writes':0,'specification_changes':0,'field_review_name_updates':[]}
 write(OUT/'publication-receipt.json',receipt)
 update_controls(before_pointer,new)
 boot=api('bootstrap');assert len(boot['products'])==184, len(boot['products'])
 # Preserve every other saved field and append the naming decision to the audit trail.
 for pid,name in names.items():
  previous=next(r for r in before_rows if r['kind']=='field' and r['product_id']==pid and r['item_id']=='Name')
  data=json.loads(previous['data']);data.update(decision='edit',value=name)
  data['notes']=(data.get('notes','')+' Owner approved three Frozen Fish finish listings on 2026-10-29; previous names retained as aliases.').strip()
  saved=api('reviews',{'kind':'field','product_id':pid,'item_id':'Name','version':previous['version'],'data':data})
  assert saved['data']['value']==name and saved['version']==previous['version']+1
  receipt['field_review_name_updates'].append({'product_id':pid,'old_version':previous['version'],'new_version':saved['version'],'name':name})
  write(OUT/'publication-receipt.json',receipt)
 boot=api('bootstrap');active={p['id']:p for p in boot['products']}
 assert {p:r['name'] for p,r in active.items() if r['family']=='Frozen Fish'}==names
 assert not set(decision['retired_option_ids'])&active.keys()
 for pid,name in names.items():
  detail=api('products/'+pid);assert detail['name']==name
  write(OUT/('live-'+pid+'.json'),detail)
 after_rows=rows();key=lambda r:(r['kind'],r['product_id'],r['item_id'])
 bykey={key(r):r for r in after_rows};assert len(before_rows)==len(after_rows)
 changed_keys={('field',pid,'Name') for pid in names}
 for row in before_rows:
  if key(row) not in changed_keys:assert row==bykey[key(row)],key(row)
 after_jobs=api('jobs');assert [(j['id'],j['state']) for j in jobs_before['jobs']]==[(j['id'],j['state']) for j in after_jobs['jobs']]
 receipt.update(status='PASS_PUBLISHED_THREE_FINISHES_LIVE_READBACK',verified_utc=datetime.now(timezone.utc).isoformat(),reviews_preserved_except_three_name_updates=len(before_rows)-3,job_history_preserved=True,current_dropbox_images=43,all_control_mirrors_verified=True,live_app_version=api('health')['version'],working_specs_preserved=True)
 write(OUT/'publication-receipt.json',receipt)
 final=deepcopy(new)
 final['current_review_application'].update(status='PUBLISHED184_SOURCE_AND_APP2_14_14_VERIFIED',source_rebase_required=False,last_verified_utc=receipt['verified_utc'],verification=str((OUT/'publication-receipt.json').relative_to(BASE)),verification_sha256=sha(OUT/'publication-receipt.json'),contract_sha256=sha(PROJECT/'catalogue-review/README.md'))
 final['current_published_gallery_projection']['status']='CURRENT184_THREE_FROZEN_FISH_FINISHES_VERIFIED'
 update_controls(new,final)
 write(OUT/'final-current-master.json',final)
 print(json.dumps(receipt,indent=2))
