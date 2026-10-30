"""Refresh current same-ID links, retain gaps, and show the scoped Series decision."""
import copy,csv,hashlib,html,json,re,shutil
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlsplit,unquote,parse_qs,quote
from datetime import datetime,timezone
H=Path(__file__).resolve().parent;B=H.parents[2];OUT=B/'outputs'/H.name
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();esc=lambda x:html.escape(str(x),quote=True)
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
m=read(H/'input-manifest.json');source=read(m['source_report_verification']['snapshot']);OLD=Path(source['output_directory']);projection=read(H/'projection-index.json');objects=projection['changed_native_objects'];g=read(H/'canonical-master-register.json');a=read(H/'image-coverage-current.json');assets=read(H/'current-assets.json');opts={x['product_id']:x for x in g['options']};defer=read(H/'series-owner-deferral-import.json');oid=defer['current_item']['option_id'];pewter='BSI-3635E3DC3434';pages=[];csvs=[];images=[]
def display(p):return '/'+p.split('//',1)[1].lstrip('/')if p.startswith('ns:')else p
paths={display(x['old_path']).casefold():i for i,x in objects.items()if x['old_path']}
def refresh(u):
 if not u.startswith('https://www.dropbox.com/'):return u.replace(str(OLD),str(OUT))
 z=urlsplit(u);p=unquote(z.path)
 for route in ['/home','/preview']:
  if p.startswith(route+'/'):p=p[len(route):];break
 name=parse_qs(z.query).get('preview',[''])[0]
 if name:p+='/'+name
 ident=paths.get(p.casefold())
 if not ident:return u
 x=objects[ident];return 'https://www.dropbox.com/'+('home'if x['object_type']=='folder'else'preview')+quote(display(x['current_path']),safe='/')
notice='<section><strong>Current review:</strong> all22 missing context/display requests remain held.17 Series gaps remain:16 active and Dune Ripple2 Copper held. The right-hand curved panel in the reviewed courtyard photo is owner-identified as Bronze finish, so it is excluded as the exact Pewter Series reference. Native navigation updates preserve all identities, image-role bindings and physical specifications.</section>'
for item in source['thumbnail_files']:
 src=Path(item['path']);assert sha(src)==item['sha256'];dest=OUT/src.relative_to(OLD);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dest);images.append({**item,'path':str(dest)})
def article_update(match,name):
 t=match.group(0)
 if oid in t and name in ['remaining-photograph-requests.html','photograph-review-walkthrough.html']:return ''
 if oid in t and '<p>Series · Open</p>'in t:t=t.replace('<p>Series · Open</p>','<p><strong>Series · Owner held — gap retained</strong></p>')
 if pewter in t and name in ['remaining-photograph-requests.html','photograph-review-walkthrough.html']:t=t.replace('</h2>','</h2><p><strong>The reviewed courtyard photo right-hand panel is Bronze finish, per owner. It does not close this exact Pewter Series gap.</strong></p>',1)
 # File moves have precedence over containing-folder prefixes. No existing
 # workbook binding uses these eight images; this guards any review-only card.
 for x in objects.values():
  if x['object_type']=='file'and x['old_parent_id']!=x['current_parent_id']:
   oldimage='https://www.dropbox.com/preview'+quote(display(x['old_path']),safe='/')
   if x['file_id']in t or oldimage in t:
    oldfolder='https://www.dropbox.com/home'+quote(display(x['old_path'].rsplit('/',1)[0]),safe='/');newfolder='https://www.dropbox.com/home'+quote(display(x['current_path'].rsplit('/',1)[0]),safe='/');t=t.replace(oldfolder,newfolder).replace(x['old_parent_id'],x['current_parent_id'])
 return t
for item in source['pages']:
 src=Path(item['path']);assert sha(src)==item['sha256'];t=src.read_text().replace(str(OLD),str(OUT));t=re.sub(r'<article\b[^>]*>.*?</article>',lambda z:article_update(z,src.name),t,flags=re.S);t=re.sub(r'href="([^"]+)"',lambda z:'href="'+esc(refresh(html.unescape(z.group(1))))+'"',t)
 t=t.replace('17 active series photograph requests','16 active series photograph requests').replace('17 active series requests','16 active series requests').replace('17 separate series requests remain active','16 separate series requests remain active; Dune Ripple2 Copper Series is held').replace('These17 series roles remain active','These16 series roles remain active; one Series request is held')
 t=t.replace('</h1>','</h1>'+notice,1);dest=OUT/src.name;dest.write_text(t);count=item['cards']-1 if src.name in ['remaining-photograph-requests.html','photograph-review-walkthrough.html']else item['cards'];pages.append({**item,'path':str(dest),'sha256':sha(dest),'cards':count})
series_rows=None;series_fields=None
for item in source['csv_files']:
 src=Path(item['path']);assert sha(src)==item['sha256'];dest=OUT/src.name
 with src.open(encoding='utf-8-sig',newline='')as f:r=csv.DictReader(f);fields=r.fieldnames;rows=list(r)
 changed=False
 for row in rows:
  ident=row.get('file_id')
  if ident in objects and objects[ident]['object_type']=='file':
   ref=assets[ident]
   for key in ['image_url','folder_url','folder_id']:
    if key in row and row[key]!=ref[key]:row[key]=ref[key];changed=True
  if row.get('option_id')==oid and row.get('role')=='Series':
   for key in ['owner_response','qualification']:
    if key in row:row[key]=(row[key]+'\nOwner held this Series request; retain source gap and current primary.').strip();changed=True
   if 'review_state'in row:row['review_state']='OWNER_HELD_SERIES_GAP_RETAINED';changed=True
  if row.get('option_id')==pewter and row.get('role')=='Series'and 'qualification'in row:row['qualification']+='\nOwner identified the reviewed courtyard right-hand curved panel as Bronze finish; exclude that member as an exact Pewter Series reference.';changed=True
 if changed:
  with dest.open('w',encoding='utf-8-sig',newline='')as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
 else:shutil.copy2(src,dest)
 csvs.append({**item,'path':str(dest),'sha256':sha(dest),'rows':len(rows)})
 if src.name=='Missing_Series_Images.csv':series_rows=rows;series_fields=fields
def csvfile(name,rows,fields):
 p=OUT/name
 with p.open('w',encoding='utf-8-sig',newline='')as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
 csvs.append({'path':str(p),'sha256':sha(p),'rows':len(rows)})
assert len(series_rows)==17;csvfile('Active_Series_Photographs_Required_16.csv',[r for r in series_rows if r['option_id']!=oid],series_fields);csvfile('Held_Series_Cases_1.csv',[r for r in series_rows if r['option_id']==oid],series_fields)
css=re.search(r'<style>(.*?)</style>',(OUT/'index.html').read_text(),re.S).group(1);nav='<nav><a href="remaining-photograph-requests.html">16 active Series requests</a> · <a href="held-in-situ-cases.html">22 held context cases</a> · <a href="held-series-cases.html">Held Series case</a> · <a href="navigation-and-owner-decisions.html">Completed navigation and owner decisions</a></nav>'
def link(u,label):return '<a href="'+esc(u)+'">'+esc(label)+'</a>'
def page(name,title,body,n):
 p=OUT/name;p.write_text('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+esc(title)+'</title><style>'+css+'</style></head><body><main><h1>'+esc(title)+'</h1>'+notice+nav+body+'</main></body></html>');pages.append({'path':str(p),'sha256':sha(p),'cards':n})
originals={x['file_id']:x for x in read(H/'original-verification.json')['files']};folder_samples=[('id:cnqzTNngPVsAAAAAAAyjBQ','id:cnqzTNngPVsAAAAAAArp5A'),('id:cnqzTNngPVsAAAAAAAyi6g','id:cnqzTNngPVsAAAAAAAt_xQ'),('id:cnqzTNngPVsAAAAAAA6Vrg','id:cnqzTNngPVsAAAAAAArp4Q'),('id:cnqzTNngPVsAAAAAAAyidA','id:cnqzTNngPVsAAAAAAAuedw')];folder_cards=[]
for pid,fid in folder_samples:
 folder=objects[pid];asset=assets[fid];original=originals[fid];src=Path(original['local_original']);dest=OUT/'images'/('native-navigation-'+fid.split(':',1)[1]+src.suffix);shutil.copy2(src,dest);assert sha(dest)==original['sha256'];images.append({'path':str(dest),'sha256':sha(dest),'file_id':fid})
 picture=''if pid=='id:cnqzTNngPVsAAAAAAAyidA'else'<img src="images/'+esc(dest.name)+'" alt="Whole unmodified navigation example" loading="lazy">'
 folder_cards.append('<article id="'+esc(pid)+'"><h2>'+esc(folder['current_name'])+'</h2><p>'+link(asset['image_url'],'Whole example image')+' · '+link(asset['folder_url'],'Actual containing folder')+'</p>'+picture+'<p>Same native image and folder identities. Arrangement and workshop references remain context; no new component or finish match is inferred.</p><small>'+esc(fid+' / '+pid)+'</small></article>')
policy=read(H/'owner-water-fountain-inclusion-policy.json');bronze=read(H/'pewter-bronze-candidate-exclusion.json');candidate=assets[bronze['candidate_file_id']];pwo=opts[pewter]
owner_cards='<article id="dune-copper-series-hold"><h2>Dune Ripple2 — Copper: Series owner hold</h2><p>'+link(opts[oid]['image_url'],'Current individual image')+' · '+link(opts[oid]['folder_url'],'Containing folder')+'</p><p>Hold this missing Series prompt until the owner resumes. No wider Series hold, new image match or changed specification is inferred.</p></article>'
owner_cards+='<article id="pewter-courtyard-finish"><h2>Courtyard right-hand panel: Bronze finish</h2><p>'+link(candidate['image_url'],'Whole courtyard photograph')+' · '+link(candidate['folder_url'],'Courtyard containing folder')+'</p><p>Owner identified only the right-hand curved panel as Bronze finish. It is excluded as an exact Pewter Series reference. Other members, files, existing associations and underlying material remain separately qualified.</p><p>'+link(pwo['image_url'],'Accepted Pewter individual image')+' · '+link(pwo['folder_url'],'Pewter containing folder')+'</p></article>'
page('navigation-and-owner-decisions.html','Completed native navigation and scoped owner decisions','<section><strong>Current structure-discovery scope:</strong> Wall Sculptures descendants only. No new outside-root search, listing or download is permitted. Earlier completed navigation history remains recorded.</section><p>66 same-ID file paths refreshed. Eight Raked originals now have their verified new containing-folder ID; the three Workshop Views images retain their folder ID after its move. Raked008/009 stay in their existing folder. No new catalogue options or physical verifications are added.</p><section><strong>Owner category policy:</strong> '+esc(policy['policy'])+' The Knightsbridge outbound proposal is cancelled. Remaining water-fountain component coverage still requires reconciliation; the187 current options are not a certified whole-library count.</section>'+''.join(folder_cards)+owner_cards,6)
page('held-series-cases.html','One owner-held Series request','<article id="'+oid+'"><h2>'+esc(opts[oid]['name'])+'</h2><p>'+link(opts[oid]['image_url'],'Current individual image')+' · '+link(opts[oid]['folder_url'],'Actual containing folder')+'</p><p>Owner deferred this Series photograph request. The source gap remains open;16 other Series requests remain active.</p></article>',1)
brief=read(m['source_photo_requests']['snapshot']);removed=[x for x in brief['requests']if x['option_id']==oid];assert len(removed)==1;brief['requests']=[x for x in brief['requests']if x['option_id']!=oid];brief.update(recorded_utc=datetime.now(timezone.utc).isoformat(),status='CURRENT_16_SERIES_ACTIVE_ONE_SERIES_HELD_ALL22_CONTEXT_HELD',held_series_requests=removed,series_owner_deferral=defer);brief['counts'].update(option_records=16,missing_roles=16,series=16,held_series_cases_excluded=1);write(OUT/'remaining-photograph-requests.json',brief)
count=read(m['source_count_summary']['snapshot'])
def reroute(v):
 if isinstance(v,str):return v.replace(str(OLD),str(OUT))
 if isinstance(v,list):return[reroute(x)for x in v]
 if isinstance(v,dict):return{k:reroute(x)for k,x in v.items()}
 return v
count=reroute(count);count.update(active_context_requests=0,held_context_cases=22,active_series_requests=16,held_series_cases=1,latest_arrangement_workshop_navigation=read(H/'import-summary.json'));write(OUT/'current-count-summary.json',count)
class Parser(HTMLParser):
 def __init__(self):super().__init__();self.ids=set();self.links=[];self.images=[];self.cards=0
 def handle_starttag(self,t,attrs):
  d=dict(attrs)
  if t=='article':self.cards+=1
  if d.get('id'):self.ids.add(d['id'])
  if t=='a':self.links.append(d.get('href',''))
  if t=='img':self.images.append(d.get('src',''))
parsed={}
for item in pages:
 p=Path(item['path']).resolve();z=Parser();z.feed(p.read_text());assert z.cards==item['cards'],(p,z.cards,item['cards']);parsed[p]=z
for p,z in list(parsed.items()):
 for u in z.links:
  assert 'BOLDSTONE_BACKUP'not in u.upper()
  if u.startswith('https://'):continue
  dest,_,anchor=u.partition('#');dest=(p.parent/dest).resolve()if dest and not Path(dest).is_absolute()else(Path(dest).resolve()if dest else p);assert dest.is_file(),(p,u)
  if anchor and dest.suffix=='.html':
   if dest not in parsed:q=Parser();q.feed(dest.read_text());parsed[dest]=q
   assert anchor in parsed[dest].ids,(p,u)
 for u in z.images:assert(p.parent/u).is_file(),(p,u)
counts={**source['counts'],'active_photograph_roles':16,'active_series_requests':16,'held_series_cases':1,'current_file_paths_refreshed':66,'current_folder_names_refreshed':3,'actual_parent_id_changes':8,'actual_folder_parent_id_changes':1,'new_owner_series_deferrals':1,'new_photo_roles_closed':0,'new_physical_verifications':0}
result={'status':'PASS_CURRENT_LINKED_REPORTS','recorded_utc':datetime.now(timezone.utc).isoformat(),'output_directory':str(OUT),'pages':pages,'csv_files':csvs,'thumbnail_files':images,'counts':counts,'register_sha256':sha(H/'canonical-master-register.json'),'audit_sha256':sha(H/'image-coverage-current.json'),'pixels_edited':False,'native_or_platform_writes':0,'copied_image_bytes_verified':True,'source_report_sha256':m['source_report_verification']['sha256']};write(H/'report-verification.json',result);print(json.dumps({'status':result['status'],'pages':len(pages),'active_series':16,'held_series':1,'context_holds':22,'same_ID_file_paths_refreshed':66,'image_roles_closed':0}))
