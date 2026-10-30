"""Refresh the existing review lists to confirmed Lava names and current folders."""
import copy,hashlib,json,shutil
from pathlib import Path
from urllib.parse import quote,unquote,urlsplit,urlunsplit
H=Path(__file__).resolve().parent;BASE=H.parents[2]
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
write=lambda p,d:Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
m=read(H/'input-manifest.json');old=BASE/'components/reconciliation/raked-gleneagles-master-refresh-2026-10-22'
for k,f in [('report_assets','current-assets.json'),('report_reviews','photo-review-queue.json')]:
 p=old/f;s=H/'inputs'/(k+'.before')
 if k not in m:shutil.copy2(p,s);m[k]={'path':str(p),'snapshot':str(s),'sha256':sha(p)}
write(H/'input-manifest.json',m)
o=read(H/'inputs/owner_overlay.before');maps=o['prefix_maps'];move=o['file_moves'][0];g=read(H/'canonical-master-register.json');before=read(H/'inputs/master_register.before');names={x['name']:next(z['name']for z in g['options']if z['product_id']==x['product_id'])for x in before['options']};objects={x['file_id']:x for x in o['objects']}
def path(s):
 if s==move['old_path']:return move['current_path']
 for x in maps:
  if s==x['old_path']or s.startswith(x['old_path']+'/'):return x['current_path']+s[len(x['old_path']):]
 return s
def val(s):
 if not isinstance(s,str):return s
 if s in names:return names[s]
 if s.startswith('ns:202238505//'):return'ns:202238505/'+path('/'+s.split('//',1)[1])
 if s.startswith('/BOLDSTONE MASTER/'):return path(s)
 if not s.startswith('https://www.dropbox.com/'):return s
 p=urlsplit(s);dec=unquote(p.path)
 for route in ['/home','/preview']:
  if dec.startswith(route+'/'):
   tail=dec[len(route):]
   if tail==str(Path(move['old_path']).parent)and unquote(p.query).endswith('='+move['current_name']):tail=str(Path(move['current_path']).parent)
   new=path(tail)
   if new!=dec[len(route):]:return urlunsplit((p.scheme,p.netloc,quote(route+new,safe='/'),p.query,p.fragment))
 return s
def project(x):
 if isinstance(x,list):return[project(v)for v in x]
 if isinstance(x,dict):
  d={k:copy.deepcopy(v)if k.startswith(('prior_','historical_'))or'_before_'in k else project(v)for k,v in x.items()}
  if d.get('file_id')==move['file_id']:d.update(folder_id=move['current_parent_id'],folder_url=objects[move['current_parent_id']]['current_native_url'])
  return d
 return val(x)
for f,k in [('current-assets.json','report_assets'),('photo-review-queue.json','report_reviews')]:write(H/f,project(read(m[k]['snapshot'])))
src=(old/'build_review_reports.py').read_text().replace("outputs/raked-gleneagles-master-refresh-2026-10-22","outputs/lava-moon-numbering-2026-10-22")
src=src.replace('Current links reflect the verified Raked Spiral folder names and Gleneagles numbering.','Current links also reflect owner-confirmed Lava Moon1/2/3 numbering and current group folders. Three new Lava White PNGs are linked in the workbook as provenance-pending candidates. Six Lava individual-photo gaps remain qualified. Current links reflect the verified Raked Spiral folder names and Gleneagles numbering.')
(H/'build_review_reports.py').write_text(src)
print('LAVA_REPORT_INPUTS_READY')
