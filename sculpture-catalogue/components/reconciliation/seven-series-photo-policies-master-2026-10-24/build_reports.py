"""Refresh current review pages and exported checklists from the frozen data."""
import copy,csv,hashlib,html,json,re,shutil
from pathlib import Path
from datetime import datetime,timezone
from html.parser import HTMLParser
from urllib.parse import urlsplit,unquote,parse_qs,quote
H=Path(__file__).resolve().parent;B=H.parents[2];OUT=B/'outputs'/H.name
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();esc=lambda x:html.escape(str(x),quote=True)
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
m=read(H/'input-manifest.json');src=read(m['source_report_verification']['snapshot']);OLD=Path(src['output_directory']);g=read(H/'canonical-master-register.json');a=read(H/'image-coverage-current.json');proj=read(H/'projection-index.json');ids=set(proj['option_ids']);events=read(H/'imported-owner-series-policies.json');objects=proj['changed_native_objects'];pages={};csvs={};images=[]
paths={o['old_path'].casefold():o for o in objects.values()if o['old_path']}
def refresh(v):
 if not isinstance(v,str):return v
 if v.startswith('https://www.dropbox.com/'):
  u=urlsplit(v);p=unquote(u.path)
  for route in ['/home','/preview']:
   if p.startswith(route+'/'):p=p[len(route):];break
  name=parse_qs(u.query).get('preview',[''])[0]
  if name:p+='/'+name
  o=paths.get(p.casefold())
  if o:return 'https://www.dropbox.com/'+('home'if o['object_type']=='folder'else'preview')+quote(o['current_path'],safe='/')
 elif v.startswith(('ns:202238505//BOLDSTONE','/BOLDSTONE')):
  p='/'+v.split('//',1)[1].lstrip('/')if v.startswith('ns:')else v;o=paths.get(p.casefold())
  if o:return ('ns:202238505/'if v.startswith('ns:')else'')+o['current_path']
 return v.replace(str(OLD),str(OUT))
notice='<section><strong>Current position:</strong>188 active options,189 retained records and112 working component identities. Seven further group/series photograph requirements made optional under exact owner decisions.26 diagnostic requirements remain:22 held context,2 Series (one active and one held), one individual water-build photograph and one deferred Frozen Fish identity.69 Series photographs are optional. <a href="navigation-and-owner-decisions.html">Exact scoped photograph decisions</a>.</section>'
for x in src['thumbnail_files']:
 p=Path(x['path']);assert sha(p)==x['sha256'];d=OUT/p.relative_to(OLD);d.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,d);images.append({**x,'path':str(d)})
for x in src['pages']:
 p=Path(x['path']);assert sha(p)==x['sha256'];text=p.read_text().replace(str(OLD),str(OUT))
 text=re.sub(r'<section><strong>Current (?:position|catalogue):</strong>.*?</section>','',text,flags=re.S)
 text=re.sub(r'<section><strong>Current (?:review|owner instruction):</strong>.*?</section>','',text,flags=re.S)
 text=re.sub(r'<p>Current image evidence uses BOLDSTONE MASTER only\..*?</p>','',text,flags=re.S)
 text=re.sub(r'href="([^"]+)"',lambda z:'href="'+esc(refresh(html.unescape(z.group(1))))+'"',text)
 if p.name in ['index.html','series-images.html','remaining-photograph-requests.html','photograph-review-walkthrough.html']:
  text=re.sub(r'<article\b[^>]*>.*?</article>',lambda z:''if any(oid in z.group(0)for oid in ids)else z.group(0),text,flags=re.S)
 for before,after in [('33 diagnostic actions','26 diagnostic actions'),('9 active source requests','2 active source requests'),('8 existing Series requests','one existing Series request'),('8 active Series requests','one active Series request'),('9 required Series gaps','2 required Series gaps'),('9 Series gaps','2 Series gaps'),('62 Series are optional','69 Series are optional'),('Active_Series_Photographs_Required_8.csv','Active_Series_Photographs_Required_1.csv')]:text=text.replace(before,after)
 text=text.replace('>1 deferred individual/identity entry<','>Individual image and identity entries<')
 text=text.replace('</h1>','</h1>'+notice,1);d=OUT/p.name;d.write_text(text);pages[p.name]={'path':str(d),'sha256':sha(d),'cards':text.count('<article')}
css=re.search(r'<style>(.*?)</style>',(OUT/'index.html').read_text(),re.S).group(1);opts={o['product_id']:o for o in g['options']};cards=[]
for event in events:
 o=opts[event['option_id']];c=next(c for c in a['coverage']if c['option_id']==event['option_id'])
 cards.append('<article id="'+o['product_id']+'"><h2>'+esc(o['name'])+'</h2><p><a href="'+esc(o['image_url'])+'">Identification photograph</a> · <a href="'+esc(o['folder_url'])+'">Containing folder</a></p><p>Group/series photograph optional. Owner response: '+esc(event['owner_text'])+'.</p><p>'+esc(c['series']['basis'])+'</p><p>Existing individual sale, photograph bindings and working specifications retained.</p><small>'+esc(o['file_id']+' / '+o['folder_id'])+'</small></article>')
def page(name,title,body):
 p=OUT/name;p.write_text('<!doctype html><html lang="en"><head><meta charset="utf-8"><title>'+title+'</title><style>'+css+'</style></head><body><main><h1>'+title+'</h1>'+notice+'<nav><a href="remaining-photograph-requests.html">2 active photograph requests</a> · <a href="specifications-to-verify.html">Physical specifications to verify</a></nav>'+body+'</main></body></html>');pages[name]={'path':str(p),'sha256':sha(p),'cards':body.count('<article')}
page('series-policy-decisions.html','Seven scoped photograph policies',''.join(cards))
page('navigation-and-owner-decisions.html','Seven scoped photograph decisions','<p><a href="riyadh-all-images.html">Current Riyadh photographs and folders</a></p>'+''.join(cards))
oldcsv={}
for x in src['csv_files']:
 p=Path(x['path']);assert sha(p)==x['sha256']
 with p.open(encoding='utf-8-sig',newline='')as f:r=csv.DictReader(f);fields=r.fieldnames;rows=list(r)
 oldcsv[p.name]=(fields,rows)
def csvfile(name,data,fields):
 p=OUT/name
 with p.open('w',encoding='utf-8-sig',newline='')as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(data)
 csvs[name]={'path':str(p),'sha256':sha(p),'rows':len(data)}
for name,(fields,rows)in oldcsv.items():
 data=[{k:refresh(v)for k,v in r.items()}for r in rows]
 if name in ['Current_Individual_Options_188.csv','Current_Selling_Details_188.csv','Combined_Shoot_and_Measure_Checklist.csv']:
  for r in data:
   if r['option_id']in ids:r['required_picture_roles']='; '.join(x.strip()for x in r['required_picture_roles'].split(';')if x.strip()!='Series')
  if name.startswith('Combined_'):data=[r for r in data if r['required_picture_roles']]
 if name!='Active_Series_Photographs_Required_8.csv':csvfile(name,data,fields)
fields,rows=copy.deepcopy(oldcsv['All_Current_Picture_Actions.csv']);taskmap={(t['option_id'],t['role']):t for t in a['missing_pictures']}
for r in rows:
 for k in r:r[k]=refresh(r[k])
 if r['option_id']in ids and r['role']=='Series':
  t=taskmap[(r['option_id'],r['role'])]
  for key in ['action_type','status','action','qualification','owner_response']:r[key]=t[key]
required=[r for r in rows if r['status']=='Open'];series=[r for r in required if r['role']=='Series'];optional=[r for r in rows if r['status']=='Optional'];held=read(H/'guided-owner-review-state.json')['held_series_ids'];active=[r for r in series if r['option_id']not in held]
assert(len(rows),len(required),len(series),len(optional),len(active))==(210,26,2,69,1)
for name,data in [('All_Current_Picture_Actions.csv',rows),('Missing_Pictures_Required.csv',required),('Missing_Series_Images.csv',series),('Optional_Series_Images.csv',optional),('Active_Series_Photographs_Required_1.csv',active)]:csvfile(name,data,fields)
brief=read(m['source_photo_requests']['snapshot']);brief['requests']=[r for r in brief['requests']if r['option_id']not in ids]
brief.setdefault('owner_optional_series_requests',[]).extend([{'owner_policy':e}for e in events]);brief.update(recorded_utc=datetime.now(timezone.utc).isoformat(),status='CURRENT_ONE_SERIES_AND_ONE_INDIVIDUAL_ACTIVE');brief['counts'].update(option_records=2,missing_roles=2,series=1,individual=1,owner_optional_series_policies=len(brief['owner_optional_series_requests']));write(OUT/'remaining-photograph-requests.json',brief)
count=read(m['source_count_summary']['snapshot']);count.update(series_gaps=2,active_series_requests=1,optional_series_requirements=69,required_picture_actions=26,latest_seven_series_photo_policy_import=read(H/'import-summary.json'))
count['current_option_list']={'path':str(OUT/'Current_Individual_Options_188.csv'),'sha256':sha(OUT/'Current_Individual_Options_188.csv'),'rows':188};write(OUT/'current-count-summary.json',count)
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
assert sha(OUT/'Physical_Verification_Input_188_Options.csv')==sha(OLD/'Physical_Verification_Input_188_Options.csv')
counts={**src['counts'],'required_actions':26,'find_capture':25,'series_gaps':2,'optional':69,'combined_required_option_rows':csvs['Combined_Shoot_and_Measure_Checklist.csv']['rows'],'active_photograph_roles':2,'active_series_requests':1,
 'new_water_build_options':0,'new_option_qualified_group_context_roles':0,'confirmed_existing_arrangement_members_added':0,'physical_options_source_audited_this_refresh':0,'physical_field_groups_source_audited_this_refresh':0,'new_owner_series_optionality_policies':7,
 'current_file_paths_refreshed':0,'current_folder_names_refreshed':0,'actual_parent_id_changes':0,'actual_folder_parent_id_changes':0,'new_physical_verifications':0}
r={'status':'PASS_CURRENT_LINKED_REPORTS','recorded_utc':datetime.now(timezone.utc).isoformat(),'output_directory':str(OUT),'pages':list(pages.values()),'csv_files':list(csvs.values()),'thumbnail_files':images,'counts':counts,'register_sha256':sha(H/'canonical-master-register.json'),'audit_sha256':sha(H/'image-coverage-current.json'),'pixels_edited':False,'native_or_platform_writes':0,'copied_image_bytes_verified':True}
write(H/'report-verification.json',r);print(json.dumps({'status':r['status'],'pages':len(pages),'required':26,'active_series':1,'optional':69,'combined_options':counts['combined_required_option_rows']}))
