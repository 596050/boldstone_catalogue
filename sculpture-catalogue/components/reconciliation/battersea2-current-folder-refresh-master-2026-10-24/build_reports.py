"""Refresh current navigation without changing any photograph requirement."""
import csv,hashlib,html,json,re,shutil
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlsplit,unquote,parse_qs,quote
from datetime import datetime,timezone
H=Path(__file__).resolve().parent;B=H.parents[2];OUT=B/'outputs'/H.name
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();esc=lambda x:html.escape(str(x),quote=True)
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
m=read(H/'input-manifest.json');src=read(m['source_report_verification']['snapshot']);OLD=Path(src['output_directory']);g=read(H/'canonical-master-register.json');a=read(H/'image-coverage-current.json');proj=read(H/'projection-index.json');objects=proj['changed_native_objects'];files={i:o for i,o in objects.items()if o['object_type']=='file'};paths={p.casefold():i for i,o in files.items()for p in [o['old_path'],o['current_path']]};pages={};csvs=[];images=[]
def identify(u):
 if not u.startswith('https://www.dropbox.com/'):return None
 z=urlsplit(u);p=unquote(z.path)
 for route in ['/home','/preview']:
  if p.startswith(route+'/'):p=p[len(route):];break
 name=parse_qs(z.query).get('preview',[''])[0]
 if name:p+='/'+name
 return paths.get(p.casefold())
def imageurl(o):return 'https://www.dropbox.com/preview'+quote(o['current_path'],safe='/')
def folderurl(o):return 'https://www.dropbox.com/home'+quote(o['current_path'].rsplit('/',1)[0],safe='/')
notice='<section><strong>Current position:</strong>188 active options,189 retained records and112 working component identities. Battersea Shellmoon2 has seven same-ID photographs in its new In Situ folder. Existing photo selections and specifications retained.25 diagnostic requirements remain:22 held context,one held Series, one active individual water-build photograph and one deferred Frozen Fish identity.70 Series photographs are optional. <a href="battersea-folder-changes.html">Current Battersea2 image and folder links</a>.</section>'
for x in src['thumbnail_files']:
 p=Path(x['path']);assert sha(p)==x['sha256'];d=OUT/p.relative_to(OLD);d.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,d);images.append({**x,'path':str(d)})
for x in src['pages']:
 p=Path(x['path']);assert sha(p)==x['sha256'];text=p.read_text().replace(str(OLD),str(OUT));text=re.sub(r'<section><strong>Current (?:position|catalogue):</strong>.*?</section>','',text,flags=re.S)
 last=[None]
 def anchor(z):
  u=html.unescape(z.group(2));ident=identify(u);target=u
  if ident:last[0]=ident;target=imageurl(files[ident])
  elif last[0]:
   o=files[last[0]];oldfolder='https://www.dropbox.com/home'+quote(o['old_path'].rsplit('/',1)[0],safe='/')
   if u==oldfolder:target=folderurl(o)
   last[0]=None
  return z.group(1)+esc(target)+z.group(3)
 text=re.sub(r'(<a\b[^>]*?\bhref=")([^"]*)("[^>]*>.*?</a>)',anchor,text,flags=re.S)
 text=text.replace('</h1>','</h1>'+notice,1);d=OUT/p.name;d.write_text(text);pages[p.name]={'path':str(d),'sha256':sha(d),'cards':text.count('<article')}
css=re.search(r'<style>(.*?)</style>',(OUT/'index.html').read_text(),re.S).group(1)
o=next(o for o in g['options']if o['product_id']=='BSI-1B70A9FB1B26')
body='<article id="BSI-1B70A9FB1B26"><h2>Battersea Shellmoon 2 — White Water Feature</h2><p><a href="'+esc(o['context_image_url'])+'">Existing selected context004 photograph</a> · <a href="'+esc(o['context_folder_url'])+'">Actual context containing folder</a></p><p><a href="'+esc(o['image_url'])+'">Individual product photograph, unchanged</a> · <a href="'+esc(o['folder_url'])+'">Product containing folder, unchanged</a></p><p>Seven existing photographs moved to the new Battersea Shellmoon 2 Water Feature White In Situ folder. Product001,003,010 and011 remain in the product folder. All77 family originals, file names, IDs, sizes and client times are preserved.</p><p>The selected context image remains the same file and keeps its existing qualified role. Navigation does not verify plumbing, waterproofing, installed hardware, scene origin or physical specifications.</p><small>Context '+esc(o['context_file_id'])+' / '+esc(o['context_folder_id'])+'</small></article>'
p=OUT/'battersea-folder-changes.html';p.write_text('<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Battersea2 current folders</title><style>'+css+'</style></head><body><main><h1>Battersea2 current folders</h1>'+notice+'<nav><a href="all-current-battersea-images.html">All77 current image and folder links</a> · <a href="remaining-photograph-requests.html">Remaining active photograph request</a></nav>'+body+'</main></body></html>');pages[p.name]={'path':str(p),'sha256':sha(p),'cards':1}
D=Path(m['battersea_overlay']['path']).parent;shutil.copy2(D/'all-current-battersea-image-folder-links.html',OUT/'all-current-battersea-images.html');p=OUT/'all-current-battersea-images.html';pages[p.name]={'path':str(p),'sha256':sha(p),'cards':p.read_text().count('<article')}
for x in src['csv_files']:
 p=Path(x['path']);assert sha(p)==x['sha256'];d=OUT/p.name;shutil.copy2(p,d);csvs.append({**x,'path':str(d)})
brief=read(m['source_photo_requests']['snapshot']);write(OUT/'remaining-photograph-requests.json',brief)
count=read(m['source_count_summary']['snapshot']);count['current_option_list']={'path':str(OUT/'Current_Individual_Options_188.csv'),'sha256':sha(OUT/'Current_Individual_Options_188.csv'),'rows':188};count['latest_battersea2_native_navigation_import']=read(H/'import-summary.json');write(OUT/'current-count-summary.json',count)
class Parser(HTMLParser):
 def __init__(self):super().__init__();self.ids=set();self.links=[];self.images=[];self.cards=0
 def handle_starttag(self,t,attrs):
  d=dict(attrs)
  if t=='article':self.cards+=1
  if d.get('id'):self.ids.add(d['id'])
  if t=='a':self.links.append(d.get('href',''))
  if t=='img':self.images.append(d.get('src',''))
parsed={}
for x in pages.values():
 p=Path(x['path']).resolve();q=Parser();q.feed(p.read_text());assert q.cards==x['cards'];parsed[p]=q
for p,q in list(parsed.items()):
 for u in q.links:
  assert 'BOLDSTONE_BACKUP'not in u.upper()
  if u.startswith('https://'):continue
  d,_,anchor=u.partition('#');dest=(p.parent/d).resolve()if d and not Path(d).is_absolute()else(Path(d).resolve()if d else p);assert dest.is_file(),(p,u)
  if anchor and dest.suffix=='.html':
   if dest not in parsed:z=Parser();z.feed(dest.read_text());parsed[dest]=z
   assert anchor in parsed[dest].ids,(p,u)
 for u in q.images:assert(p.parent/u).is_file(),(p,u)
counts={**src['counts'],'current_file_paths_refreshed':7,'current_folder_names_refreshed':0,'actual_parent_id_changes':7,'actual_folder_parent_id_changes':0,'new_owner_series_optionality_policies':0}
assert pages['index.html']['cards']==25 and pages['series-images.html']['cards']==1 and pages['remaining-photograph-requests.html']['cards']==1
r={'status':'PASS_CURRENT_LINKED_REPORTS','recorded_utc':datetime.now(timezone.utc).isoformat(),'output_directory':str(OUT),'pages':list(pages.values()),'csv_files':csvs,'thumbnail_files':images,'counts':counts,'register_sha256':sha(H/'canonical-master-register.json'),'audit_sha256':sha(H/'image-coverage-current.json'),'pixels_edited':False,'native_or_platform_writes':0,'copied_image_bytes_verified':True};write(H/'report-verification.json',r);print(json.dumps({'status':r['status'],'pages':len(pages),'source_selections_changed':0,'photo_requests_changed':0}))
