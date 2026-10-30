"""Refresh current linked reports from frozen local evidence, with no image edits."""
import copy,csv,hashlib,html,json,re,shutil
from pathlib import Path
from datetime import datetime,timezone
from html.parser import HTMLParser
H=Path(__file__).resolve().parent;B=H.parents[2];OUT=B/'outputs'/H.name
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();esc=lambda x:html.escape(str(x),quote=True)
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
m=read(H/'input-manifest.json');src=read(m['source_report_verification']['snapshot']);OLD=Path(src['output_directory']);g=read(H/'canonical-master-register.json');a=read(H/'image-coverage-current.json');proj=read(H/'projection-index.json');oid=proj['optional_option_id'];opts={x['product_id']:x for x in g['options']};cov={x['option_id']:x for x in a['coverage']};summary=read(H/'import-summary.json');pages={};csvs={};images=[]
notice='<section><strong>Current position:</strong>187 active sale options,112 working component identities.22 missing context requests remain owner-held.16 required Series gaps remain:15 active and one owner-held. Copper and Partial Verdigris Series is optional by owner policy; no new photograph or physical measurement is verified. <a href="current-note-corrections.html">Latest reference corrections</a>.</section>'
for x in src['thumbnail_files']:
 p=Path(x['path']);assert sha(p)==x['sha256'];d=OUT/p.relative_to(OLD);d.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,d);images.append({**x,'path':str(d)})
css=re.search(r'<style>(.*?)</style>',(OLD/'index.html').read_text(),re.S).group(1)
nav='<nav><a href="index.html">All required gaps</a> · <a href="remaining-photograph-requests.html">15 active Series requests</a> · <a href="held-in-situ-cases.html">22 held context cases</a> · <a href="held-series-cases.html">One held Series case</a> · <a href="specifications-to-verify.html">Physical specification checklist</a> · <a href="current-note-corrections.html">Current source notes</a></nav>'
def page(name,title,body):
 p=OUT/name;p.write_text('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+esc(title)+'</title><style>'+css+'</style></head><body><main><h1>'+esc(title)+'</h1>'+notice+nav+body+'</main></body></html>');pages[name]={'path':str(p),'sha256':sha(p),'cards':body.count('<article')}
for x in src['pages']:
 p=Path(x['path']);assert sha(p)==x['sha256'];text=p.read_text().replace(str(OLD),str(OUT))
 if p.name in ['index.html','series-images.html','remaining-photograph-requests.html','photograph-review-walkthrough.html']:
  text=re.sub(r'<article\b[^>]*>.*?</article>',lambda z:''if oid in z.group(0)else z.group(0),text,flags=re.S)
 replacements={'16 active series photograph requests':'15 active series photograph requests','16 active Series requests':'15 active Series requests','16 Series requests remain active':'15 Series requests remain active','16 active series requests':'15 active series requests','17 Series gaps remain:16 active':'16 Series gaps remain:15 active','40 diagnostic gaps':'39 diagnostic gaps','40 required':'39 required','17 series requests remain active':'15 Series requests remain active','17 series requests remain after two owner deferrals':'15 active Series requests remain; one Series request is held','17 series.':'16 required Series.','17 series gaps':'16 required Series gaps'}
 for before,after in replacements.items():text=text.replace(before,after)
 text=text.replace('</h1>','</h1>'+notice,1);d=OUT/p.name;d.write_text(text);pages[p.name]={'path':str(d),'sha256':sha(d),'cards':text.count('<article')}
def link(url,label):return '<a href="'+esc(url)+'" target="_blank" rel="noopener">'+esc(label)+'</a>'
# Rebuild this current presentation so stale descriptions are not the main caption.
cards=[]
for o in g['options']:
 c=cov[o['product_id']]
 if c['in_situ']['status']!='Available':continue
 r=c['in_situ']['reference'];note=o.get('current_reference_note');description=o.get('context_description','');body='<p>'+link(r['image_url'],'Selected context image')+' · '+link(r['folder_url'],'Actual containing folder')+'</p>'
 if note:
  body+='<p><strong>Dated current clarification:</strong> '+esc(note['text'])+'</p>'
  if note['role']=='Individual':body+='<p>'+link(o['image_url'],'Individual image010 discussed in this note')+' · '+link(o['folder_url'],'Individual containing folder')+'. The context image above is a separate retained selection.</p>'
  body+='<details><summary>Earlier source wording retained as history</summary><p>'+esc(description)+'</p></details>'
 else:body+='<p>'+esc(description)+'</p>'
 body+='<small>'+esc(r['file_id']+' / '+r['folder_id'])+'</small>'
 cards.append('<article id="'+esc(o['product_id'])+'"><h2>'+esc(o['name'])+'</h2>'+body+'</article>')
assert len(cards)==165;page('current-context-references.html','Recorded context photographs and their current qualifications',''.join(cards))
cards=[]
for ident in proj['b_option_ids']+proj['a_option_ids']:
 o=opts[ident];note=o.get('current_reference_note');text=note['text']if note else o['context_description'];role=note['role']if note else'In situ';url=o['image_url']if role=='Individual'else o['context_image_url'];folder=o['folder_url']if role=='Individual'else o['context_folder_url'];fid=o['file_id']if role=='Individual'else o['context_file_id'];pid=o['folder_id']if role=='Individual'else o['context_folder_id']
 cards.append('<article id="'+ident+'"><h2>'+esc(o['name'])+'</h2><p>'+esc(role)+' reference: '+link(url,'Whole selected image')+' · '+link(folder,'Actual containing folder')+'</p><p>'+esc(text)+'</p><p>Existing photo roles and physical/commercial fields are preserved. Earlier wording is retained in dated source history.</p><small>'+esc(fid+' / '+pid)+'</small></article>')
o=opts[oid];cards.append('<article id="'+oid+'"><h2>'+esc(o['name'])+' — Series optional</h2><p>'+link(o['image_url'],'Individual identification image')+' · '+link(o['folder_url'],'Actual containing folder')+'</p><p>Owner approved this one Series photograph as optional because the panel is sold individually with no fixed matched set. The exact-finish group image remains unverified. This changes the requirement only.</p><small>'+esc(o['file_id']+' / '+o['folder_id'])+'</small></article>')
page('current-note-corrections.html','Current reference corrections and one scoped Series policy',''.join(cards))
def csvfile(name,rows,fields):
 p=OUT/name
 with p.open('w',encoding='utf-8-sig',newline='')as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
 csvs[name]={'path':str(p),'sha256':sha(p),'rows':len(rows)}
oldcsv={}
for x in src['csv_files']:
 p=Path(x['path']);assert sha(p)==x['sha256']
 with p.open(encoding='utf-8-sig',newline='')as f:r=csv.DictReader(f);fields=r.fieldnames;rows=list(r)
 oldcsv[p.name]=(fields,rows)
 d=OUT/p.name;shutil.copy2(p,d);csvs[p.name]={**x,'path':str(d)}
fields=oldcsv['All_Current_Picture_Actions.csv'][0]
def taskrow(t,i):
 r=t.get('reference')or{};row={'sequence':i,'option_id':t['option_id'],'name':t['name'],'role':t['role'],'action_type':t['action_type'],'status':t['status'],'action':t['action'],'qualification':t.get('qualification',''),'owner_response':t.get('owner_response',''),'native_source_status':r.get('native_reference_status',r.get('native_source_status',''))}
 for k in ['image_url','folder_url','file_id','folder_id']:row[k]=r.get(k,'')
 return {k:row.get(k,'')for k in fields}
rows=copy.deepcopy(oldcsv['All_Current_Picture_Actions.csv'][1]);assert len(rows)==len(a['missing_pictures'])
for row,t in zip(rows,a['missing_pictures']):
 assert row['option_id']==t['option_id']and row['role']==t['role']
 if t['option_id']==oid and t['role']=='Series':
  for key in ['action_type','status','action','qualification','owner_response']:row[key]=t[key]
required=[r for r in rows if r['status']not in ['Resolved','Optional','Retired / not applicable']];series=[r for r in required if r['role']=='Series'];optional=[r for r in rows if r['status']=='Optional'];held=read(H/'guided-owner-review-state.json')['held_series_ids'];active=[r for r in series if r['option_id']not in held]
assert(len(rows),len(required),len(series),len(optional),len(active))==(209,39,16,55,15)
csvfile('All_Current_Picture_Actions.csv',rows,fields);csvfile('Missing_Pictures_Required.csv',required,fields);csvfile('Missing_Series_Images.csv',series,fields);csvfile('Optional_Series_Images.csv',optional,fields);csvfile('Active_Series_Photographs_Required_15.csv',active,fields)
# A superseded count-named CSV is retained as a dated snapshot, with no current links.
csvs.pop('Active_Series_Photographs_Required_16.csv');(OUT/'Active_Series_Photographs_Required_16.csv').unlink()
for name in ['Current_Individual_Options_187.csv','Combined_Shoot_and_Measure_Checklist.csv']:
 fields,data=oldcsv[name];data=copy.deepcopy(data)
 for row in data:
  if row['option_id']==oid:row['required_picture_roles']=''
 if name.startswith('Combined_'):data=[r for r in data if r['required_picture_roles']]
 csvfile(name,data,fields)
for path in OUT.glob('*.html'):
 text=path.read_text().replace('Active_Series_Photographs_Required_16.csv','Active_Series_Photographs_Required_15.csv');path.write_text(text);pages[path.name]['sha256']=sha(path)
brief=read(m['source_photo_requests']['snapshot']);match=[r for r in brief['requests']if r['option_id']==oid];assert len(match)==1;brief['requests']=[r for r in brief['requests']if r['option_id']!=oid];brief.setdefault('owner_optional_series_requests',[]).append({'previous_request':match[0],'policy':read(H/'owner-series-optionality-import.json')});brief.update(recorded_utc=datetime.now(timezone.utc).isoformat(),status='CURRENT_15_SERIES_ACTIVE_ONE_SERIES_HELD_ALL22_CONTEXT_HELD');brief['counts'].update(option_records=15,missing_roles=15,series=15,owner_optional_series_policies=1);write(OUT/'remaining-photograph-requests.json',brief)
count=read(m['source_count_summary']['snapshot'])
def reroute(x):
 if isinstance(x,str):return x.replace(str(OLD),str(OUT))
 if isinstance(x,list):return[reroute(v)for v in x]
 if isinstance(x,dict):return{k:reroute(v)for k,v in x.items()}
 return x
count=reroute(count);count.update(active_context_requests=0,held_context_cases=22,series_gaps=16,active_series_requests=15,held_series_cases=1,optional_series_requirements=55,required_picture_actions=39,latest_current_note_finalization=summary);write(OUT/'current-count-summary.json',count)
counts={**src['counts'],'required_actions':39,'find_capture':38,'series_gaps':16,'optional':55,'combined_required_option_rows':36,'active_photograph_roles':15,'active_series_requests':15,'new_owner_series_deferrals':0,'current_file_paths_refreshed':0,'current_folder_names_refreshed':0,'actual_parent_id_changes':0,'actual_folder_parent_id_changes':0,'new_owner_series_optionality_policies':1,'current_descriptions_updated':5,'current_statuses_aligned_to_existing_available_role':4,'dated_current_reference_notes_appended':2}
class Parser(HTMLParser):
 def __init__(self):super().__init__();self.ids=set();self.links=[];self.images=[];self.cards=0
 def handle_starttag(self,t,attrs):
  d=dict(attrs)
  if t=='article':self.cards+=1
  if d.get('id'):self.ids.add(d['id'])
  if t=='a':self.links.append(d.get('href',''))
  if t=='img':self.images.append(d.get('src',''))
parsed={}
for item in pages.values():
 p=Path(item['path']).resolve();z=Parser();z.feed(p.read_text());assert z.cards==item['cards'];parsed[p]=z
for p,z in list(parsed.items()):
 for u in z.links:
  assert 'BOLDSTONE_BACKUP'not in u.upper()
  if u.startswith('https://'):continue
  d,_,anchor=u.partition('#');dest=(p.parent/d).resolve()if d and not Path(d).is_absolute()else(Path(d).resolve()if d else p);assert dest.is_file(),(p,u)
  if anchor and dest.suffix=='.html':
   if dest not in parsed:q=Parser();q.feed(dest.read_text());parsed[dest]=q
   assert anchor in parsed[dest].ids,(p,u)
 for u in z.images:assert(p.parent/u).is_file(),(p,u)
assert sha(OUT/'Physical_Verification_Input_187_Options.csv')==sha(OLD/'Physical_Verification_Input_187_Options.csv')
result={'status':'PASS_CURRENT_LINKED_REPORTS','recorded_utc':datetime.now(timezone.utc).isoformat(),'output_directory':str(OUT),'pages':list(pages.values()),'csv_files':list(csvs.values()),'thumbnail_files':images,'counts':counts,'register_sha256':sha(H/'canonical-master-register.json'),'audit_sha256':sha(H/'image-coverage-current.json'),'pixels_edited':False,'native_or_platform_writes':0,'copied_image_bytes_verified':True,'source_report_sha256':m['source_report_verification']['sha256']};write(H/'report-verification.json',result);print(json.dumps({'status':result['status'],'pages':len(pages),'active_series':15,'held_series':1,'context_holds':22,'required_picture_actions':39}))
