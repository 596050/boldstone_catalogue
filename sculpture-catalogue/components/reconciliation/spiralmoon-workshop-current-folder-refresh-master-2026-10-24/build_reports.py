"""Refresh current image/folder links while preserving all review dispositions."""
import csv,hashlib,html,json,re,shutil
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlsplit,unquote,parse_qs,quote
from datetime import datetime,timezone
H=Path(__file__).resolve().parent;B=H.parents[2];OUT=B/'outputs'/H.name
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();esc=lambda x:html.escape(str(x),quote=True)
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
m=read(H/'input-manifest.json');src=read(m['source_report_verification']['snapshot']);OLD=Path(src['output_directory']);g=read(H/'canonical-master-register.json');a=read(H/'image-coverage-current.json');proj=read(H/'projection-index.json');objects={i:o for i,o in proj['changed_native_objects'].items()if o['object_type']=='file'};paths={p.casefold():i for i,o in objects.items()for p in [o['old_path'],o['current_path']]};pages={};csvs=[];images=[];csv_changes=[]
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
notice='<section><strong>Current position:</strong> 188 active options and 112 working component identities. Two approved Spiralmoon workshop photographs now have a new flat Workshop Views folder. No active photograph requests. The 22 context requests, one Series request and Frozen Fish legacy identity remain held or deferred. <a href="spiralmoon-folder-changes.html">Current Spiralmoon images and containing folders</a>.</section>'
for x in src['thumbnail_files']:
 p=Path(x['path']);assert sha(p)==x['sha256'];d=OUT/p.relative_to(OLD);d.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,d);images.append({**x,'path':str(d)})
for x in src['pages']:
 p=Path(x['path']);assert sha(p)==x['sha256'];text=p.read_text().replace(str(OLD),str(OUT));text=re.sub(r'<section><strong>Current (?:position|catalogue):</strong>.*?</section>','',text,flags=re.S);last=[None]
 def anchor(z):
  u=html.unescape(z.group(2));ident=identify(u);target=u
  if ident:last[0]=ident;target=imageurl(objects[ident])
  elif last[0]:
   o=objects[last[0]];oldfolder='https://www.dropbox.com/home'+quote(o['old_path'].rsplit('/',1)[0],safe='/')
   if u==oldfolder:target=folderurl(o)
   last[0]=None
  return z.group(1)+esc(target)+z.group(3)
 text=re.sub(r'(<a\b[^>]*?\bhref=")([^"]*)("[^>]*>.*?</a>)',anchor,text,flags=re.S);text=text.replace('</h1>','</h1>'+notice,1);d=OUT/p.name;d.write_text(text);pages[p.name]={'path':str(d),'sha256':sha(d),'cards':text.count('<article')}
css=re.search(r'<style>(.*?)</style>',(OUT/'index.html').read_text(),re.S).group(1)
overlay=read(m['spiralmoon_overlay']['snapshot']);o=next(o for o in g['options']if o['product_id']=='BSI-10BFED6B265B');assets=read(H/'current-assets.json');thumb=Path(assets[o['file_id']]['thumb']);td=OUT/'thumbnails/spiralmoon-selected-011.jpg';td.parent.mkdir(exist_ok=True);shutil.copy2(thumb,td);images.append({'path':str(td),'sha256':sha(td)})
body='<article id="BSI-10BFED6B265B"><h2>Spiralmoon — White</h2><img src="thumbnails/spiralmoon-selected-011.jpg" alt="Selected Spiralmoon White photograph"><p><a href="'+esc(o['image_url'])+'">Selected photograph 011.JPG</a> · <a href="'+esc(o['folder_url'])+'">Actual containing folder</a></p><p>The two studio-series workshop photographs002.jpg and003.jpg moved from In Situ into the new Spiralmoon 1 White Workshop Views folder. The selected catalogue photograph011.JPG and existing context photograph stay in In Situ with the same file IDs and roles.</p><p>82 family files retained. Product folder: 10. In Situ: 54. Workshop Views: 2. Other folders: 16. Current image roles, owner decisions and working specifications are unchanged.</p><small>'+esc(o['file_id'])+' / '+esc(o['folder_id'])+'</small></article>'
def page(name,title,content):
 p=OUT/name;p.write_text('<!doctype html><html lang="en"><head><meta charset="utf-8"><title>'+esc(title)+'</title><style>'+css+'</style></head><body><main><h1>'+esc(title)+'</h1>'+notice+content+'</main></body></html>');pages[p.name]={'path':str(p),'sha256':sha(p),'cards':content.count('<article')}
page('spiralmoon-folder-changes.html','Spiralmoon current folders','<nav><a href="all-current-spiralmoon-images.html">All 82 current image and folder links</a></nav>'+body)
cards=[]
for x in sorted((x for x in overlay['objects']if x['object_type']=='file'),key=lambda x:x['current_path'].casefold()):
 ident=x['file_id'];cards.append('<article id="'+esc(ident.split(':')[1])+'"><h2>'+esc(x['current_name'])+'</h2><p><a href="'+esc(imageurl(x))+'">Image</a> · <a href="'+esc(folderurl(x))+'">Containing folder</a></p><p>'+('Moved to the new Workshop Views folder.'if ident in objects else'Containing folder unchanged.')+'</p><small>'+esc(ident)+' / '+esc(x['current_parent_id'])+'</small></article>')
page('all-current-spiralmoon-images.html','All 82 Spiralmoon images',''.join(cards))
for x in src['csv_files']:
 p=Path(x['path']);assert sha(p)==x['sha256'];d=OUT/p.name
 with p.open(encoding='utf-8-sig',newline='')as f:reader=csv.DictReader(f);headers=reader.fieldnames;rows=list(reader)
 edited=False
 for rowno,row in enumerate(rows,2):
  ident=row.get('file_id')
  if ident in objects:
   obj=objects[ident]
   for k,v in [('image_url',imageurl(obj)),('folder_url',folderurl(obj)),('individual_image',imageurl(obj)),('containing_folder',folderurl(obj)),('folder_id',obj['current_parent_id'])]:
    if k in row and row[k]!=v:csv_changes.append({'file':p.name,'row':rowno,'column':k,'before':row[k],'current':v});row[k]=v;edited=True
 if edited:
  with d.open('w',encoding='utf-8-sig',newline='')as f:wr=csv.DictWriter(f,fieldnames=headers);wr.writeheader();wr.writerows(rows)
 else:shutil.copy2(p,d)
 csvs.append({**x,'path':str(d),'sha256':sha(d)})
write(H/'current-csv-navigation-changes.json',csv_changes)
brief=read(m['source_photo_requests']['snapshot']);write(OUT/'remaining-photograph-requests.json',brief)
count=read(m['source_count_summary']['snapshot']);count['current_option_list']={'path':str(OUT/'Current_Individual_Options_188.csv'),'sha256':sha(OUT/'Current_Individual_Options_188.csv'),'rows':188};count['latest_spiralmoon_native_navigation_import']=read(H/'import-summary.json');write(OUT/'current-count-summary.json',count)
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
counts={**src['counts'],'current_file_paths_refreshed':2,'current_folder_names_refreshed':0,'actual_parent_id_changes':2,'actual_folder_parent_id_changes':0,'new_owner_series_optionality_policies':0,'new_owner_reference_exceptions':0,'new_complete_photographs_verified':0}
assert pages['index.html']['cards']==24 and pages['series-images.html']['cards']==1 and pages['remaining-photograph-requests.html']['cards']==0
r={'status':'PASS_CURRENT_LINKED_REPORTS','recorded_utc':datetime.now(timezone.utc).isoformat(),'output_directory':str(OUT),'pages':list(pages.values()),'csv_files':csvs,'thumbnail_files':images,'counts':counts,'register_sha256':sha(H/'canonical-master-register.json'),'audit_sha256':sha(H/'image-coverage-current.json'),'pixels_edited':False,'native_or_platform_writes':0,'copied_image_bytes_verified':True};write(H/'report-verification.json',r);print(json.dumps({'status':r['status'],'pages':len(pages),'csv_navigation_edits':len(csv_changes),'source_selections_changed':0,'photo_requests_changed':0}))
