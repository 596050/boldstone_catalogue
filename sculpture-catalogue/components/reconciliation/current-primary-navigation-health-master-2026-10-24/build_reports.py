"""Publish scoped navigation health alongside unchanged source-photo coverage."""
import csv,hashlib,html,json,re,shutil
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import unquote,urlsplit
H=Path(__file__).resolve().parent; B=H.parents[2];OUT=B/'outputs'/H.name
read=lambda p:json.loads(Path(p).read_text()); sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();esc=lambda x:html.escape(str(x),quote=True)
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
m=read(H/'input-manifest.json');src=read(m['source_report_verification']['snapshot']);OLD=Path(src['output_directory']);g=read(H/'canonical-master-register.json');a=read(H/'image-coverage-current.json');nav=read(H/'current-primary-navigation-health.json');proj=read(H/'projection-index.json');norm=proj['case_only_replacements'];rows={r['product_id']:r for r in nav['rows']};held={o['product_id']:o for o in g['options']if o.get('current_primary_navigation')};pages={};csvs=[];images=[];changes=[]
notice='<section><strong>Current position:</strong> 188 active options and112 working component identities. Source-photo coverage is retained. A scoped metadata check verified46 selected files and all48 containing folders;2 Wall Circle primary references remain unresolved. <a href="current-primary-navigation-health.html">Image and folder links for all48 checked options</a>.22 missing context cases,1 Series case and the legacy Frozen Fish identity remain held or deferred.</section>'
for x in src['thumbnail_files']:
 p=Path(x['path']);assert sha(p)==x['sha256'];d=OUT/p.relative_to(OLD);d.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,d);images.append({**x,'path':str(d)})
for x in src['pages']:
 p=Path(x['path']);assert sha(p)==x['sha256'];text=p.read_text().replace(str(OLD),str(OUT));text=re.sub(r'<section><strong>Current (?:position|catalogue):</strong>.*?</section>','',text,flags=re.S)
 def anchor(z):
  u=html.unescape(z.group(2));return z.group(1)+esc(norm.get(u,u))+z.group(3)
 text=re.sub(r'(<a\b[^>]*?\bhref=")([^"]*)("[^>]*>)',anchor,text)
 for o in held.values():
  note='<p class="native-reference-warning"><strong>Current primary reference unresolved:</strong> the saved image below is a historical source reference. Its containing folder was verified; no replacement was selected. Identity review remains on hold. <a href="current-primary-navigation-health.html#'+esc(o['product_id'])+'">Readback evidence and links</a>.</p>'
  def annotate(z):
   card=z.group(0)
   if esc(o['image_url'])in card or o['image_url']in card:return card.replace('</article>',note+'</article>')
   return card
  text=re.sub(r'<article\b.*?</article>',annotate,text,flags=re.S)
 text=text.replace('</h1>','</h1>'+notice,1);d=OUT/p.name;d.write_text(text);pages[d.name]={'path':str(d),'sha256':sha(d),'cards':text.count('<article')}
css=re.search(r'<style>(.*?)</style>',(OUT/'index.html').read_text(),re.S).group(1)
cards=[]
for r in nav['rows']:
 unresolved=r['product_id']in held; label='Saved image reference (unresolved)'if unresolved else'Image (metadata verified)'
 status='Selected primary unresolved; containing folder verified'if unresolved else('Selected image and parent verified; capitalization normalized'if r['product_id']=='BSI-70C7029C1DB1'else'Selected image and actual parent verified')
 qualification='<p>ID and exact-path lookups failed; the saved ID/path was absent from the complete checked containing-folder listing. This does not establish deletion, absence elsewhere or web-URL failure. Source-photo coverage and owner holds are retained; no alternate image selected.</p>'if unresolved else'<p>Metadata readback only; no new image-content, physical sculpture or exact platform-configuration verification.</p>'
 cards.append('<article id="'+esc(r['product_id'])+'"><h2>'+esc(r['name'])+'</h2><p>'+esc(status)+'</p><p><a href="'+esc(r['current_image_url'])+'">'+label+'</a> · <a href="'+esc(r['current_folder_url'])+'">Verified containing folder</a></p>'+qualification+'<small>'+esc(r['product_id'])+' · '+esc(r['file_id'])+' · '+esc(r['folder_id'])+'</small></article>')
p=OUT/'current-primary-navigation-health.html';p.write_text('<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Current primary image navigation</title><style>'+css+'</style></head><body><main><h1>Current primary image navigation</h1>'+notice+'<p>'+esc(nav['scope'])+'</p><p>Checked '+esc(nav['recorded_utc'])+'. Source-photo status “Available” records previously reviewed image content; it does not assert a currently verified Dropbox file.</p><nav><a href="Current_Primary_Navigation_48.csv">Download48 checked references</a> · <a href="../../components/parallel-reviews/unpaired43-native-navigation-20261024T023834Z/review.html">Sealed read-only observation</a> · <a href="index.html">Current catalogue</a></nav>'+''.join(cards)+'</main></body></html>');pages[p.name]={'path':str(p),'sha256':sha(p),'cards':48}
for x in src['csv_files']:
 p=Path(x['path']);assert sha(p)==x['sha256'];d=OUT/p.name
 with p.open(encoding='utf-8-sig',newline='')as f:reader=csv.DictReader(f);headers=reader.fieldnames;data=list(reader)
 edited=False
 # Raw source capture files and retired/history exports remain byte-identical.
 protect=any(t in p.name for t in ['Captured_','Historical_','Retired_','Unresolved_Historical_'])
 if not protect:
  for rn,row in enumerate(data,2):
   for k,v in list(row.items()):
    if v in norm and k in ['image_url','folder_url','individual_image','containing_folder','context_image','context_folder','series_image','series_folder']:
     row[k]=norm[v];changes.append({'file':p.name,'row':rn,'column':k,'before':v,'current':row[k]});edited=True
 if p.name=='Current_Individual_Options_188.csv':
  extra=['current_primary_native_status','current_primary_file_verified','current_primary_folder_verified','current_primary_readback_scope'];headers=headers+extra
  for row in data:
   r=rows.get(row['option_id']);row.update({k:''for k in extra})
   if r:row.update(current_primary_native_status=r['navigation_status'],current_primary_file_verified=str(r['file_verified_by_id']),current_primary_folder_verified=str(r['folder_verified_by_id']),current_primary_readback_scope='Scoped metadata readback24 Oct2026; source-photo coverage retained')
  edited=True
 if edited:
  with d.open('w',encoding='utf-8-sig',newline='')as f:wr=csv.DictWriter(f,fieldnames=headers);wr.writeheader();wr.writerows(data)
 else:shutil.copy2(p,d)
 csvs.append({**x,'path':str(d),'sha256':sha(d)})
columns=['option_id','name','source_offer_refs','file_id','folder_id','image_url','folder_url','navigation_status','file_verified','folder_verified','readback_utc','scope']
p=OUT/'Current_Primary_Navigation_48.csv'
with p.open('w',encoding='utf-8-sig',newline='')as f:
 w=csv.DictWriter(f,fieldnames=columns);w.writeheader()
 for r in nav['rows']:w.writerow(dict(zip(columns,[r['product_id'],r['name'],'; '.join(r['source_offer_refs']),r['file_id'],r['folder_id'],r['current_image_url'],r['current_folder_url'],r['navigation_status'],r['file_verified_by_id'],r['folder_verified_by_id'],nav['recorded_utc'],nav['scope']])))
csvs.append({'path':str(p),'sha256':sha(p),'rows':48})
write(H/'current-csv-navigation-changes.json',changes)
shutil.copy2(m['source_photo_requests']['snapshot'],OUT/'remaining-photograph-requests.json')
count=read(m['source_count_summary']['snapshot']);count['current_option_list']={'path':str(OUT/'Current_Individual_Options_188.csv'),'sha256':sha(OUT/'Current_Individual_Options_188.csv'),'rows':188};count['current_primary_navigation_health']=g['current_primary_navigation_health'];write(OUT/'current-count-summary.json',count)
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
for p,q in parsed.items():
 for u in q.links+q.images:
  assert 'BOLDSTONE_BACKUP'not in u.upper()
  if u.startswith(('https:','data:')):continue
  name,_,anchor=u.partition('#');target=(p.parent/unquote(name)).resolve()if name else p
  assert target.is_file(),(p.name,u)
  if anchor and target in parsed:assert anchor in parsed[target].ids,(p.name,u)
result={**src,'status':'PASS','output_directory':str(OUT),'register_sha256':sha(H/'canonical-master-register.json'),'audit_sha256':sha(H/'image-coverage-current.json'),'pages':list(pages.values()),'csv_files':csvs,'thumbnail_files':images,'current_primary_navigation_health':g['current_primary_navigation_health']}
write(H/'report-verification.json',result);print(json.dumps({'status':'PASS','pages':len(pages),'csvs':len(csvs),'thumbnails':len(images),'checked_references':48,'unresolved_primaries':2}))
