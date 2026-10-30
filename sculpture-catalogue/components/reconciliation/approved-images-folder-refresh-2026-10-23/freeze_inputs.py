import json,hashlib,shutil
from pathlib import Path
from datetime import datetime,timezone
H=Path(__file__).resolve().parent;B=H.parents[2];R=B.parent
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
p=read(B/'current-master.json');prior=(B/p['register']).parent
sources={'master_pointer':B/'current-master.json','master_workbook':B/p['workbook'],'master_register':B/p['register'],'audit':Path(p['latest_image_coverage_audit']['path']),'report_assets':prior/'current-assets.json','report_reviews':prior/'photo-review-queue.json','guided_state':prior/'guided-owner-review-state.json','review_progress':B/'components/reviews/specification_review_progress.json','component_checkpoint':B/'components/checkpoint.json','root_checkpoint':B/'checkpoint.json','squarespace_hold':B/'components/parallel-reviews/listing-execution-2026-10-21/SQUARESPACE_WRITE_HOLD.json'}
packets={};overlays={};pr=B/'components/parallel-reviews';br=pr/'guided-photography-review-2026-10-23'
for label in ['gleneagles-1','gleneagles-2','gleneagles-3','gleneagles-4','lava-moon-1','lava-moon-2','lava-moon-3']:
 f=br/(label+'-owner-image-acceptance.json');s=br/(label+'-owner-image-acceptance-seal.json');seal=read(s);assert sha(f)==seal['sha256'];packets[label]=f;sources['seal_'+label]=s
for label,folder,name in [('ffs1-spec','frozen-fish-one-white-specification-confirmation-2026-10-23','owner-confirmation.json'),('frozen-fish-references','frozen-fish-owner-image-review-2026-10-23','owner-decision.json'),('raked1-spec','raked-spiral-one-beige-specification-confirmation-2026-10-23','owner-confirmation.json'),('raked1-references','raked-spiral-one-beige-image-role-approval-2026-10-23','owner-image-approval.json'),('raked2-references','raked-spiral-two-beige-image-role-approval-2026-10-23','owner-image-approval.json'),('moon-shellwave1-reference','moon-and-shellwave-one-water-feature-image-approval-2026-10-23','owner-image-approval.json')]:packets[label]=pr/folder/name
for label,folder in [('moonshell-lava','dropbox-moonshell-lava-pair-rename-2026-10-22'),('deco-dune-ripple','dropbox-deco-dune-ripple-numbered-renames-2026-10-23'),('ammonite','dropbox-ammonite-full-name-renames-2026-10-23'),('moon-fishwave','dropbox-moon-fishwave-full-name-renames-2026-10-23'),('fold-unfold','dropbox-fold-unfold-group-changes-2026-10-23'),('spiralmoon','dropbox-spiralmoon-pair-rename-2026-10-23')]:
 f=R/'reports'/folder/'current-reference-overlay.json';o=read(f);assert o['status']=='COMPLETE_VERIFIED';overlays[label]=f
 for i,r in enumerate(o.get('receipts',[])):
  dest=Path(r['path']);assert sha(dest)==r['sha256'];sources['receipt_'+label+'_'+str(i)]=dest
sources.update({'approval_'+k:v for k,v in packets.items()});sources.update({'overlay_'+k:v for k,v in overlays.items()})
sources.update({'native_'+f.stem:f for f in H.glob('*.json')if f.name not in ['input-manifest.json','scope.json','WORK_STATE.json']})
for i in [1,3]:sources['archived_acanthus_'+str(i)]=prior/'archived-originals'/f'acanthus__acanthus-one-leaf-assorted-colours__{i:03}.jpg'
(H/'inputs').mkdir(exist_ok=True)
if not(H/'input-manifest.json').exists():
 m={}
 for k,f in sources.items():
  dest=H/'inputs'/(k+'.before');shutil.copy2(f,dest);m[k]={'path':str(f),'snapshot':str(dest),'sha256':sha(f)}
 write(H/'input-manifest.json',m)
 write(H/'scope.json',{'recorded_utc':datetime.now(timezone.utc).isoformat(),'approvals':{k:str(v)for k,v in packets.items()},'overlays':{k:str(v)for k,v in overlays.items()},'native_writes':'Two targeted Acanthus file revision restores only; same original file IDs, recreated containing folder has new ID','native_parent_rename_performed':False,'new_options':0,'new_components':0,'platform_writes':0,'cutoff':'Lava Moon 3 White and Moon and Shellwave 1 upper accepted; subsequent review decisions and Seaweed Ripple rename remain queued'})
m=read(H/'input-manifest.json')
for k,x in m.items():assert sha(x['path'])==sha(x['snapshot'])==x['sha256'],k
assert sha(B/p['workbook'])==p['workbook_sha256']and sha(B/p['register'])==p['register_sha256']
print(json.dumps({'status':'FROZEN','inputs':len(m),'approvals':len(packets),'overlays':len(overlays),'pointer':sha(B/'current-master.json')}))
