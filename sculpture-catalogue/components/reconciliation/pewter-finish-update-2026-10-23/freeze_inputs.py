import json,hashlib,shutil
from pathlib import Path
H=Path(__file__).resolve().parent; B=H.parents[2]
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=read(B/'current-master.json'); prior=B/Path(p['register']).parent
sources={'master_pointer':B/'current-master.json','master_workbook':B/p['workbook'],'master_register':B/p['register'],'audit':Path(p['latest_image_coverage_audit']['path']),'report_assets':prior/'current-assets.json','report_reviews':prior/'photo-review-queue.json','guided_state':prior/'guided-owner-review-state.json','review_progress':B/'components/reviews/specification_review_progress.json','component_checkpoint':B/'components/checkpoint.json','root_checkpoint':B/'checkpoint.json','squarespace_hold':B/'components/parallel-reviews/listing-execution-2026-10-21/SQUARESPACE_WRITE_HOLD.json'}
sources.update({x.stem:H/x.name for x in H.glob('*.json') if x.name not in ['input-manifest.json','WORK_STATE.json']})
(H/'inputs').mkdir(exist_ok=True)
cache=Path('/Users/tprice/Library/Application Support/BoldstoneLocal/cache/acanthus-pewter-inspection-yhycup18')
(H/'archived-originals').mkdir(exist_ok=True)
for n in [1,3]:
 s=cache/f'acanthus__acanthus-one-leaf-assorted-colours__{n:03}.jpg';t=H/'archived-originals'/s.name
 if not t.exists():shutil.copy2(s,t)
 sources['archived_acanthus_'+str(n)]=t
if not(H/'input-manifest.json').exists():
 m={}
 for k,s in sources.items():
  t=H/'inputs'/(k+'.before');shutil.copy2(s,t);m[k]={'path':str(s),'snapshot':str(t),'sha256':sha(s)}
 (H/'input-manifest.json').write_text(json.dumps(m,indent=2)+'\n')
m=read(H/'input-manifest.json')
for k,x in m.items():assert sha(x['path'])==sha(x['snapshot'])==x['sha256'],k
assert sha(B/p['workbook'])==p['workbook_sha256'] and sha(B/p['register'])==p['register_sha256']
print(json.dumps({'status':'FROZEN','inputs':len(m),'workbook':p['workbook_sha256'],'register':p['register_sha256']}))
