import csv,hashlib,html,json,re,shutil
from pathlib import Path
from html.parser import HTMLParser
from datetime import datetime,timezone
from navigation import refresh
from urllib.parse import urlsplit,unquote,parse_qs
H=Path(__file__).resolve().parent;B=H.parents[2];OUT=B/'outputs'/H.name
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();esc=lambda x:html.escape(str(x),quote=True)
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
m=read(H/'input-manifest.json');src=read(m['source_report_verification']['snapshot']);OLD=Path(src['output_directory']);g=read(H/'canonical-master-register.json');a=read(H/'image-coverage-current.json');cases=read(H/'verified-six-cases.json')['rows'];pages={};images=[];csvs=[];csvchanges=[]
notice='<section><strong>Current position:</strong> 188 active options;112 retained component IDs;110 working design groups. Six current image and folder URL corrections and ten separately approved Moonwave photo moves are imported. Moonwave has84 White and15 In Situ files; all99 originals remain. The prior nine-photo plan remains withdrawn history. Selected images, roles, qualified specifications and owner holds are retained. <a href="six-current-link-corrections.html">Six corrected links</a> · <a href="moonwave-approved-folder-changes.html">Approved Moonwave filing</a>.</section>'
for x in src['thumbnail_files']:
 p=Path(x['path']);assert sha(p)==x['sha256'];d=OUT/p.relative_to(OLD);d.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,d);images.append({**x,'path':str(d)})
for x in src['pages']:
 p=Path(x['path']);assert sha(p)==x['sha256'];t=p.read_text().replace(str(OLD),str(OUT));t=re.sub(r'<section><strong>Current (?:position|catalogue):</strong>.*?</section>','',t,flags=re.S)
 def anchor(z):return z.group(1)+esc(refresh(html.unescape(z.group(2))))+z.group(3)
 t=re.sub(r'(<a\b[^>]*?\bhref=")([^"]*)(")',anchor,t)
 # A containing-folder link follows its own image, rather than a global family-folder substitution.
 ov=read(H/'moonwave-native-overlay.json');last=[None]
 def own_anchor(z):
  u=html.unescape(z.group(2));uri=urlsplit(u);fp=unquote(uri.path);fp=fp[len('/home'):]if fp.startswith('/home/')else fp[len('/preview'):]if fp.startswith('/preview/')else fp;preview=parse_qs(uri.query).get('preview',[''])[0];fp=fp+'/'+preview if preview else fp;found=next((o for o in ov['objects']if o['object_type']=='file'and o['old_path']!=o['current_path']and fp==o['current_path']),None)
  if found:last[0]=found
  elif last[0]:
   from urllib.parse import quote
   old='https://www.dropbox.com/home'+quote(last[0]['old_path'].rsplit('/',1)[0],safe='/')
   if u==old:u='https://www.dropbox.com/home'+quote(last[0]['current_path'].rsplit('/',1)[0],safe='/')
   last[0]=None
  return z.group(1)+esc(u)+z.group(3)
 t=re.sub(r'(<a\b[^>]*?\bhref=")([^"]*)("[^>]*>.*?</a>)',own_anchor,t,flags=re.S);t=t.replace('</h1>','</h1>'+notice,1);d=OUT/p.name;d.write_text(t);pages[d.name]={'path':str(d),'sha256':sha(d),'cards':t.count('<article')}
css=re.search(r'<style>(.*?)</style>',(OUT/'index.html').read_text(),re.S).group(1);opts={o['product_id']:o for o in g['options']};cards=[]
for i,r in enumerate(cases,1):
 o=opts[r['option_id']];specs=''.join('<tr><th>'+esc(k)+'</th><td>'+esc(v['display'])+'<br><small>'+esc(v.get('state',''))+'</small></td></tr>'for k,v in o['master_fields'].items());cards.append('<article id="'+esc(o['product_id'])+'"><h2>'+str(i)+'. '+esc(o['name'])+'</h2><p><a href="'+esc(o['image_url'])+'">Image</a> · <a href="'+esc(o['folder_url'])+'">Containing folder</a></p><p>Only current URL capitalization is corrected. Existing evidence, estimates, selected file and immediate parent IDs remain. Metadata observations keep their original clocks; no new live or binary read and no physical verification.</p><table>'+specs+'</table><small>'+esc(o['file_id'])+' / '+esc(o['folder_id'])+'</small></article>')
d=OUT/'six-current-link-corrections.html';d.write_text('<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Six current image and folder links</title><style>'+css+'</style></head><body><main><h1>Six current image and folder links</h1>'+notice+''.join(cards)+'</main></body></html>');pages[d.name]={'path':str(d),'sha256':sha(d),'cards':6}
from urllib.parse import quote
def mooncard(o):return '<article id="'+esc(o['file_id'].split(':')[1])+'"><h2>'+esc(o['current_name'])+'</h2><p><a href="'+esc(o['current_native_url'])+'">Image</a> · <a href="https://www.dropbox.com/home'+esc(quote(o['current_path'].rsplit('/',1)[0],safe='/'))+'">Actual containing folder</a></p><small>'+esc(o['file_id'])+' / '+esc(o['current_parent_id'])+'</small></article>'
ov=read(H/'moonwave-native-overlay.json')
for name,title,selected in [('moonwave-approved-folder-changes.html','Ten approved Moonwave photo moves',[o for o in ov['objects']if o['old_path']!=o['current_path']]),('all-current-moonwave-images.html','All99 current Moonwave image and folder links',[o for o in ov['objects']if o['object_type']=='file'])]:
 d=OUT/name;cards=''.join(mooncard(o)for o in sorted(selected,key=lambda o:o['current_path']));d.write_text('<!doctype html><html lang="en"><head><meta charset="utf-8"><title>'+title+'</title><style>'+css+'</style></head><body><main><h1>'+title+'</h1>'+notice+'<p>The approved plan moved six full brick-wall views to In Situ and four close views to White. Three borderline and four room images stayed in their folders. Source offer O016 (array index15) and coverage163 retain their own file IDs and source snapshots, with current containing-folder navigation.</p>'+cards+'</main></body></html>');pages[d.name]={'path':str(d),'sha256':sha(d),'cards':len(selected)}
for x in src['csv_files']:
 p=Path(x['path']);assert sha(p)==x['sha256'];d=OUT/p.name
 with p.open(encoding='utf-8-sig',newline='')as f:reader=csv.DictReader(f);headers=reader.fieldnames;rows=list(reader)
 edits=[]
 for no,row in enumerate(rows,2):
  for key,v in row.items():
   new=refresh(v)if key in ['image_url','folder_url','individual_image','containing_folder']else v
   if new!=v:edits.append({'file':p.name,'row':no,'column':key,'before':v,'value':new});row[key]=new
 if edits:
  with d.open('w',encoding='utf-8-sig',newline='')as f:wr=csv.DictWriter(f,fieldnames=headers);wr.writeheader();wr.writerows(rows)
 else:shutil.copy2(p,d)
 csvchanges.extend(edits);csvs.append({**x,'path':str(d),'sha256':sha(d)})
write(H/'current-csv-navigation-changes.json',csvchanges);write(OUT/'remaining-photograph-requests.json',read(m['source_photo_requests']['snapshot']))
count=read(m['source_count_summary']['snapshot']);count['current_option_list']={'path':str(OUT/'Current_Individual_Options_188.csv'),'sha256':sha(OUT/'Current_Individual_Options_188.csv'),'rows':188};count['latest_current_url_case_normalization']=read(H/'import-summary.json');write(OUT/'current-count-summary.json',count)
class Parser(HTMLParser):
 def __init__(self):super().__init__();self.ids=set();self.links=[];self.images=[];self.cards=0
 def handle_starttag(self,t,a):
  d=dict(a)
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
  if u.startswith(('https://','http://')):continue
  d,_,anchor=u.partition('#');dest=(p.parent/d).resolve()if d and not Path(d).is_absolute()else(Path(d).resolve()if d else p);assert dest.is_file(),(p,u)
  if anchor and dest.suffix=='.html':
   if dest not in parsed:z=Parser();z.feed(dest.read_text());parsed[dest]=z
   assert anchor in parsed[dest].ids,(p,u)
 for u in q.images:assert(p.parent/u).is_file()
counts={**src['counts'],'current_file_paths_refreshed':10,'actual_parent_id_changes':10,'case_only_primary_options_normalized':6,'case_only_primary_URL_fields_normalized':12}
result={'status':'PASS_CURRENT_LINKED_REPORTS','recorded_utc':datetime.now(timezone.utc).isoformat(),'output_directory':str(OUT),'pages':list(pages.values()),'csv_files':csvs,'thumbnail_files':images,'counts':counts,'register_sha256':sha(H/'canonical-master-register.json'),'audit_sha256':sha(H/'image-coverage-current.json'),'pixels_edited':False,'native_or_platform_writes':0,'copied_image_bytes_verified':True};write(H/'report-verification.json',result);print(json.dumps({'status':result['status'],'pages':len(pages),'case_only_current_CSV_fields':len(csvchanges)}))
