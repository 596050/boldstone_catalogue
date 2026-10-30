"""Project only current report references; retain historical decisions and sources."""
import copy,hashlib,json,shutil
from pathlib import Path
from urllib.parse import quote,unquote,urlsplit,urlunsplit
H=Path(__file__).resolve().parent;BASE=H.parents[2]
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
write=lambda p,d:Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
m=read(H/'input-manifest.json');old=BASE/'components/reconciliation/photo-gap-completion-2026-10-22'
for k,f in [('report_assets','current-assets.json'),('report_reviews','photo-review-queue.json')]:
 p=old/f;snap=H/'inputs'/(k+'.before')
 if k not in m:
  shutil.copy2(p,snap);m[k]={'path':str(p),'snapshot':str(snap),'sha256':sha(p)}
 assert sha(p)==sha(snap)==m[k]['sha256']
write(H/'input-manifest.json',m)
maps=read(H/'inputs/raked_overlay.before')['prefix_maps']+read(H/'inputs/glen_overlay.before')['prefix_maps']
maps.sort(key=lambda x:len(x['old_path']),reverse=True)
g=read(H/'canonical-master-register.json');before=read(H/'inputs/master_register.before')
names={x['name']:next(y['name']for y in g['options']if y['product_id']==x['product_id'])for x in before['options']}
def path(p):
 for x in maps:
  if p==x['old_path']or p.startswith(x['old_path']+'/'):return x['current_path']+p[len(x['old_path']):]
 return p
def value(s):
 if not isinstance(s,str):return s
 if s in names:return names[s]
 if s.startswith('ns:202238505//'):return 'ns:202238505/'+path('/'+s.split('//',1)[1])
 if s.startswith('/BOLDSTONE MASTER/'):return path(s)
 if not s.startswith('https://www.dropbox.com/'):return s
 p=urlsplit(s);dec=unquote(p.path)
 for route in ['/home','/preview']:
  if dec.startswith(route+'/'):
   new=path(dec[len(route):])
   if new!=dec[len(route):]:return urlunsplit((p.scheme,p.netloc,quote(route+new,safe='/'),p.query,p.fragment))
 return s
def project(x):
 if isinstance(x,list):return [project(y)for y in x]
 if isinstance(x,dict):return{k:copy.deepcopy(v)if k.startswith(('prior_','historical_'))or '_before_'in k else project(v)for k,v in x.items()}
 return value(x)
for f,k in [('current-assets.json','report_assets'),('photo-review-queue.json','report_reviews')]:write(H/f,project(read(m[k]['snapshot'])))
s=(old/'build_review_reports.py').read_text().replace("OUT=BASE/'outputs/photo-gap-completion-2026-10-22'","OUT=BASE/'outputs/raked-gleneagles-master-refresh-2026-10-22'")
s=s.replace('All 111 carried-forward actions reviewed; six further roles mapped.','Current links reflect the verified Raked Spiral folder names and Gleneagles numbering. Four new Gleneagles PNG candidates are linked in the workbook for creation-provenance review; their individual-photo gaps remain qualified. All 111 carried-forward actions reviewed; six further roles mapped.')
write(H/'report-preparation.json',{'status':'PASS','historical_source_reports_preserved':True,'coverage_upgrades':0,'source_files':{k:m[k]for k in ['report_assets','report_reviews']}})
(H/'build_review_reports.py').write_text(s)
print('REPORT_INPUTS_READY')
