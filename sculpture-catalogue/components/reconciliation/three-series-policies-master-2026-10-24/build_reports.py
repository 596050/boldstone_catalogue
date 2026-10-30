"""Refresh current lists for three scoped policy changes; preserve all photographs."""
import copy,csv,hashlib,html,json,re,shutil
from pathlib import Path
from datetime import datetime,timezone
from html.parser import HTMLParser
H=Path(__file__).resolve().parent;B=H.parents[2];OUT=B/'outputs'/H.name;read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();esc=lambda x:html.escape(str(x),quote=True)
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
m=read(H/'input-manifest.json');src=read(m['source_report_verification']['snapshot']);OLD=Path(src['output_directory']);g=read(H/'canonical-master-register.json');a=read(H/'image-coverage-current.json');ids=set(read(H/'projection-index.json')['option_ids']);events=read(H/'imported-owner-series-policies.json');pages={};csvs={};images=[]
notice='<section><strong>Current position:</strong>188 active options,189 retained records and112 working component identities. Three current owner Series policies imported.37 diagnostic requirements remain:22 held context,13 Series (12 active and one held), one new water-build individual photograph and one deferred Frozen Fish identity.58 Series are optional. <a href="series-policy-decisions.html">Exact scoped decisions</a>.</section>'
for x in src['thumbnail_files']:
 p=Path(x['path']);assert sha(p)==x['sha256'];d=OUT/p.relative_to(OLD);d.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,d);images.append({**x,'path':str(d)})
for x in src['pages']:
 p=Path(x['path']);assert sha(p)==x['sha256'];text=p.read_text().replace(str(OLD),str(OUT));text=re.sub(r'<section><strong>Current catalogue:</strong>.*?</section>','',text,flags=re.S)
 if p.name in ['index.html','series-images.html','remaining-photograph-requests.html','photograph-review-walkthrough.html']:
  text=re.sub(r'<article\b[^>]*>.*?</article>',lambda z:''if any(oid in z.group(0)for oid in ids)else z.group(0),text,flags=re.S)
 for before,after in [('40 diagnostic actions','37 diagnostic actions'),('16 active source requests','13 active source requests'),('15 existing Series requests','12 existing Series requests'),('15 active Series requests','12 active Series requests'),('15 active series photograph requests','12 active series photograph requests'),('16 required Series gaps','13 required Series gaps'),('16 Series gaps','13 Series gaps')]:text=text.replace(before,after)
 text=text.replace('</h1>','</h1>'+notice,1);d=OUT/p.name;d.write_text(text);pages[p.name]={'path':str(d),'sha256':sha(d),'cards':text.count('<article')}
css=re.search(r'<style>(.*?)</style>',(OUT/'index.html').read_text(),re.S).group(1);opts={o['product_id']:o for o in g['options']};cards=[]
for event in events:
 o=opts[event['option_id']];body='<article id="'+o['product_id']+'"><h2>'+esc(o['name'])+'</h2><p><a href="'+esc(o['image_url'])+'">Individual identification image</a> · <a href="'+esc(o['folder_url'])+'">Actual containing folder</a></p><p>Series photograph: Optional / no fixed set. Owner response: '+esc(event['owner_text'])+'. '+esc(event.get('temporal_qualification',event.get('policy_review_condition','')))+'</p><p>Exact group photograph remains unverified. Existing primary/context sources, individual sale record, physical and commercial fields remain unchanged.</p><small>'+esc(o['file_id']+' / '+o['folder_id'])+'</small></article>';cards.append(body)
p=OUT/'series-policy-decisions.html';p.write_text('<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Three scoped Series policies</title><style>'+css+'</style></head><body><main><h1>Three scoped Series policies</h1>'+notice+'<nav><a href="remaining-photograph-requests.html">13 active source requests</a> · <a href="water-products-and-memberships.html">Water option and four Moonphase members</a></nav>'+''.join(cards)+'</main></body></html>');pages[p.name]={'path':str(p),'sha256':sha(p),'cards':3}
oldcsv={}
for x in src['csv_files']:
 p=Path(x['path']);assert sha(p)==x['sha256']
 with p.open(encoding='utf-8-sig',newline='')as f:r=csv.DictReader(f);fields=r.fieldnames;rows=list(r)
 oldcsv[p.name]=(fields,rows);d=OUT/p.name;shutil.copy2(p,d);csvs[p.name]={**x,'path':str(d)}
def csvfile(name,data,fields,prior=None):
 if prior and prior!=name:csvs.pop(prior);(OUT/prior).unlink()
 p=OUT/name
 with p.open('w',encoding='utf-8-sig',newline='')as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(data)
 csvs[name]={'path':str(p),'sha256':sha(p),'rows':len(data)}
fields,rows=copy.deepcopy(oldcsv['All_Current_Picture_Actions.csv']);taskmap={(t['option_id'],t['role']):t for t in a['missing_pictures']}
for r in rows:
 if r['option_id']in ids and r['role']=='Series':
  t=taskmap[(r['option_id'],r['role'])]
  for key in ['action_type','status','action','qualification','owner_response']:r[key]=t[key]
required=[r for r in rows if r['status']=='Open'];series=[r for r in required if r['role']=='Series'];optional=[r for r in rows if r['status']=='Optional'];held=read(H/'guided-owner-review-state.json')['held_series_ids'];active=[r for r in series if r['option_id']not in held]
assert(len(rows),len(required),len(series),len(optional),len(active))==(210,37,13,58,12)
for name,data in [('All_Current_Picture_Actions.csv',rows),('Missing_Pictures_Required.csv',required),('Missing_Series_Images.csv',series),('Optional_Series_Images.csv',optional)]:csvfile(name,data,fields)
csvfile('Active_Series_Photographs_Required_12.csv',active,fields,'Active_Series_Photographs_Required_15.csv')
for name in ['Current_Individual_Options_188.csv','Current_Selling_Details_188.csv','Combined_Shoot_and_Measure_Checklist.csv']:
 fields,data=copy.deepcopy(oldcsv[name])
 for r in data:
  if r['option_id']in ids:r['required_picture_roles']='; '.join(x.strip()for x in r['required_picture_roles'].split(';')if x.strip()!='Series')
 if name.startswith('Combined_'):data=[r for r in data if r['required_picture_roles']]
 csvfile(name,data,fields)
for p in OUT.glob('*.html'):
 text=p.read_text().replace('Active_Series_Photographs_Required_15.csv','Active_Series_Photographs_Required_12.csv');p.write_text(text);pages[p.name]['sha256']=sha(p)
brief=read(m['source_photo_requests']['snapshot']);brief['requests']=[r for r in brief['requests']if r['option_id']not in ids];brief.setdefault('owner_optional_series_requests',[]).extend([{'owner_policy':e}for e in events]);brief.update(recorded_utc=datetime.now(timezone.utc).isoformat(),status='CURRENT12_SERIES_AND_ONE_INDIVIDUAL_ACTIVE');brief['counts'].update(option_records=13,missing_roles=13,series=12,individual=1);write(OUT/'remaining-photograph-requests.json',brief)
count=read(m['source_count_summary']['snapshot']);count.update(series_gaps=13,active_series_requests=12,optional_series_requirements=58,required_picture_actions=37,latest_three_series_optionality_import=read(H/'import-summary.json'));write(OUT/'current-count-summary.json',count)
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
counts={**src['counts'],'required_actions':37,'find_capture':36,'series_gaps':13,'optional':58,'combined_required_option_rows':34,'active_photograph_roles':13,'active_series_requests':12,'new_water_build_options':0,'new_option_qualified_group_context_roles':0,'confirmed_existing_arrangement_members_added':0,'physical_options_source_audited_this_refresh':0,'physical_field_groups_source_audited_this_refresh':0,'new_owner_series_optionality_policies':3}
r={'status':'PASS_CURRENT_LINKED_REPORTS','recorded_utc':datetime.now(timezone.utc).isoformat(),'output_directory':str(OUT),'pages':list(pages.values()),'csv_files':list(csvs.values()),'thumbnail_files':images,'counts':counts,'register_sha256':sha(H/'canonical-master-register.json'),'audit_sha256':sha(H/'image-coverage-current.json'),'pixels_edited':False,'native_or_platform_writes':0,'copied_image_bytes_verified':True};write(H/'report-verification.json',r);print(json.dumps({'status':r['status'],'pages':len(pages),'required':37,'active_series':12,'optional':58}))
