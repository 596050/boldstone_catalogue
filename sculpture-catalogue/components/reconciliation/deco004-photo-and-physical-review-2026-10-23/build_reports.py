"""Retain current review views and add bounded photo/physical evidence walkthroughs."""
import copy,csv,hashlib,html,json,re,shutil
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import quote,unquote,urlsplit,parse_qs
from datetime import datetime,timezone
H=Path(__file__).resolve().parent;B=H.parents[2];OUT=B/'outputs'/H.name;OUT.mkdir(exist_ok=True);read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();esc=lambda x:html.escape(str(x),quote=True)
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
m=read(H/'input-manifest.json');source=read(m['source_report_verification']['snapshot']);OLD=Path(source['output_directory']);hist=read(H/'path-change-history.json');r=hist['reference'];fid=r['file_id'];old=hist['before'];oldfolder='https://www.dropbox.com/home'+quote(old['display_path'].rsplit('/',1)[0],safe='/');pages=[];csvs=[];images=[];native=read(H/'current-native-reference-map.json');assets=read(H/'current-assets.json');defers=read(H/'owner-context-deferral-imports.json');deferids={d['option_id']for d in defers};defernote='Owner held this context request: "ignore it for the time being". Gap remains open until the owner resumes.'
for x in source['pages']+source['csv_files']+source['thumbnail_files']:assert sha(x['path'])==x['sha256'],x['path']
def refresh_url(u):
 if not u.startswith('https://www.dropbox.com/'):return u.replace(str(OLD),str(OUT))
 z=urlsplit(u);p=unquote(z.path)
 for route in ['/home','/preview']:
  if p.startswith(route+'/'):p=p[len(route):];break
 name=parse_qs(z.query).get('preview',[''])[0]
 if name:p+='/'+name
 if p.casefold()==old['display_path'].casefold():return r['image_url']
 ident=native['old_path_to_id'].get(p.casefold())
 if ident in {'id:cnqzTNngPVsAAAAAAAyh5w','id:cnqzTNngPVsAAAAAAAyh6w','id:cnqzTNngPVsAAAAAAAyh6g'}:
  obj=native['current_objects'][ident]
  return 'https://www.dropbox.com/'+('home'if obj['object_type']=='folder'else'preview')+quote(obj['display_path'],safe='/')
 return u
def update_article(match):
 text=match.group(0)
 if fid not in text:return text
 text=text.replace(oldfolder,r['folder_url']).replace(old['parent_id'],r['folder_id'])
 return text
for x in source['thumbnail_files']:
 src=Path(x['path']);dest=OUT/src.relative_to(OLD);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dest);assert sha(dest)==x['sha256'];images.append({**x,'path':str(dest)})
deferred_articles=[]
for x in source['pages']:
 src=Path(x['path']);dest=OUT/src.name;t=src.read_text().replace(str(OLD),str(OUT));t=re.sub(r'<article\b[^>]*>.*?</article>',update_article,t,flags=re.S)
 t=re.sub(r'href="([^"]+)"',lambda z:'href="'+esc(refresh_url(html.unescape(z.group(1))))+'"',t)
 t=t.replace('36 active in-situ cases and17 series cases were reviewed;8 held cases remain unchanged.','12 active context and17 series requests remain after two owner deferrals;10 held context cases retain open gaps.').replace('Active_In_Situ_Photographs_Required_14.csv','Active_In_Situ_Photographs_Required_12.csv').replace('Held_In_Situ_Cases_8.csv','Held_In_Situ_Cases_10.csv')
 if src.name=='active-in-situ-photo-requests.html':
  chunks=re.findall(r'<article\b[^>]*>.*?</article>',t,re.S);found=[z for z in chunks if any(oid in z for oid in deferids)];assert len(found)==2
  for article in found:
   deferred_articles.append(article.replace('</h2>','</h2><p><strong>'+esc(defernote)+'</strong></p>',1));t=t.replace(article,'')
  t=t.replace('14 active in situ photograph requests','12 active in situ photograph requests');cards=12
 elif src.name=='remaining-photograph-requests.html':
  chunks=re.findall(r'<article\b[^>]*>.*?</article>',t,re.S);found=[z for z in chunks if any('id="'+oid+'"'in z for oid in deferids)];assert len(found)==2
  for article in found:t=t.replace(article,'')
  t=t.replace('14 display/context roles and 17 series roles across 29 sculpture options','12 display/context roles and 17 series roles across 27 sculpture options').replace('Eight held context cases','Ten held context cases');cards=27
 elif src.name=='held-in-situ-cases.html':
  assert len(deferred_articles)==2;t=t.replace('</main>',''.join(deferred_articles)+'</main>').replace('Eight held in situ cases — unchanged','Ten held context cases — gaps retained');cards=10
 else:
  cards=x['cards']
  if src.name in ['index.html','in-situ-images.html']:
   def markheld(z):
    text=z.group(0)
    return text.replace('</h2>','</h2><p><strong>'+esc(defernote)+'</strong></p>',1)if any(oid in text for oid in deferids) else text
   t=re.sub(r'<article\b[^>]*>.*?</article>',markheld,t,flags=re.S)
 if src.name=='index.html':t=t.replace('</h1>','</h1><section>Deco004 now links to its actual In Situ containing folder.002/003 identity holds are retained while their folder navigation is current. All31 original photograph roles were reviewed;29 remain active after two scoped deferrals. The187-option physical audit retains estimates and identifies the object evidence still needed.</section>',1)
 dest.write_text(t);pages.append({**x,'path':str(dest),'sha256':sha(dest),'cards':cards})
deferred_csv_rows=[]
for x in source['csv_files']:
 src=Path(x['path']);dest=OUT/src.name
 with src.open(encoding='utf-8-sig',newline='')as f:reader=csv.DictReader(f);fields=reader.fieldnames;rows=list(reader)
 changed=False
 if src.name=='Active_In_Situ_Photographs_Required_14.csv':
  match=[z for z in rows if z.get('option_id')in deferids];assert len(match)==2;deferred_csv_rows=match;rows=[z for z in rows if z not in match];dest=OUT/'Active_In_Situ_Photographs_Required_12.csv';changed=True
 if src.name=='Held_In_Situ_Cases_8.csv':
  assert len(deferred_csv_rows)==2;rows.extend([{k:z.get(k,'')for k in fields}for z in deferred_csv_rows]);dest=OUT/'Held_In_Situ_Cases_10.csv';changed=True
 for row in rows:
  ident=row.get('file_id')
  if ident in {fid,'id:cnqzTNngPVsAAAAAAAyh6w','id:cnqzTNngPVsAAAAAAAyh6g'}:
   ref=r if ident==fid else assets[ident]
   for k,v in [('image_url',ref['image_url']),('folder_url',ref['folder_url']),('folder_id',ref['folder_id'])]:
    if k in row and row[k]!=v:row[k]=v;changed=True
  if row.get('option_id')in deferids and row.get('role','In situ')in ['In situ','Display/context']:
   for k in ['owner_response','qualification']:
    if k in row:row[k]=(row[k]+'\n'+defernote).strip();changed=True
 if changed:
  with dest.open('w',encoding='utf-8-sig',newline='')as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
 else:shutil.copy2(src,dest)
 csvs.append({**x,'path':str(dest),'sha256':sha(dest),'rows':len(rows)})
template=(OUT/'index.html').read_text();css=re.search(r'<style>(.*?)</style>',template,re.S).group(1)
nav='<nav><a href="index.html">Current picture requests</a> · <a href="deco004-changes.html">Deco004 folder refresh</a> · <a href="photograph-review-walkthrough.html">Current photograph reviews</a> · <a href="physical-evidence-review.html">Physical evidence for187 options</a></nav>'
def link(u,label):return '<a href="'+esc(u)+'">'+esc(label)+'</a>'if u else esc(label+' unbound')
def ref_links(z):return link(z.get('image_url',''),'Dropbox example image')+' · '+link(z.get('folder_url',''),'Containing folder')
def page(name,title,body,cards):
 p=OUT/name;p.write_text('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+esc(title)+'</title><style>'+css+'</style></head><body><main><h1>'+esc(title)+'</h1>'+nav+body+'</main></body></html>');pages.append({'path':str(p),'sha256':sha(p),'cards':cards})
def csvfile(name,rows):
 p=OUT/name
 with p.open('w',encoding='utf-8-sig',newline='')as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 csvs.append({'path':str(p),'sha256':sha(p),'rows':len(rows)})
original=read(H/'original-verification.json')['files'][0];src=Path(original['local_original']);dest=OUT/'images/deco004-whole-original.png';shutil.copy2(src,dest);assert sha(dest)==original['sha256'];images.append({'path':str(dest),'sha256':sha(dest),'file_id':fid,'relative_path':'images/deco004-whole-original.png'})
g=read(H/'canonical-master-register.json');a=read(H/'image-coverage-current.json');cm={x['option_id']:x for x in a['coverage']};opts={x['product_id']:x for x in g['options']};cards=[]
for oid in hist['affected_option_ids']:
 c=cm[oid];cards.append('<article id="'+esc(oid)+'"><h2>'+esc(opts[oid]['name'])+'</h2><p>'+ref_links(r)+'</p><p>'+esc(c['in_situ']['basis'])+'</p><small>'+esc(fid+' / '+r['folder_id'])+'</small></article>')
heldfolder=refresh_url('https://www.dropbox.com/home'+quote(old['display_path'].rsplit('/',1)[0],safe='/'))
page('deco004-changes.html','Deco004 actual folder and stable image mapping','<section><p><a href="'+esc(r['image_url'])+'"><img style="width:100%;height:auto;max-height:700px;object-fit:contain" src="images/deco004-whole-original.png" alt="Whole four-panel White garden scene"></a></p><p>'+ref_links(r)+'</p><p>Same original004, filename and image bytes. Its actual parent is the new In Situ folder. The three established context associations below are retained. No primary, canonical identity, image-role decision or physical specification is replaced.</p><p>002.png and003.jpeg remain on canonical identity hold in '+link(heldfolder,'their renamed scene-studies folder')+'. The completed same-ID scene-folder rename is imported for navigation only. The existing Timeless Spiral003 context association is retained with its current path and unchanged parent ID.004 remains in its separate In Situ folder. The general White arrangement remains unchanged.</p></section>'+''.join(cards),3)
photo=read(H/'photo-source-review.json');photo_cards=[]
for x in photo['requests']:
 z=x['existing_individual_reference'];action=x['required_photograph'];action=action if isinstance(action,str)else json.dumps(action,ensure_ascii=False);photo_cards.append('<article id="'+esc(x['option_id']+'-'+('context'if x['role']=='Display/context'else'series'))+'"><h2>'+esc(x['name'])+' — '+esc(x['role'])+'</h2><p>'+ref_links(z)+'</p><p><strong>Still required:</strong> '+esc(action)+'</p><p>'+esc(x['qualification'])+'</p><p>Current family membership checked: '+str(x['current_family_file_count'])+' files. The accepted individual source and its actual parent were found. Prior whole-original review is retained; no exact new source is inferred from unchanged metadata.</p><small>'+esc(x['option_id']+' / '+z['file_id']+' / '+z['folder_id'])+'</small></article>')
page('photograph-review-walkthrough.html','29 active photograph requests after two scoped owner deferrals','<p>All31 original roles were reviewed. After the Pale Blue and White Two Leaves and Pewter Two Leaves context deferrals,12 context and17 series roles remain active across27 options. Ten held context cases and the deferred Frozen Fish legacy identity are excluded. Only current BOLDSTONE MASTER evidence is used. Exact scene/finish qualifications remain in force.</p>'+''.join(photo_cards),29)
physical=read(H/'physical-source-audit.json');labels={'FITTED_FIXING_NOT_INSPECTED; OFFERED_CHOICES_OR_WORKING_ESTIMATE_RETAINED':'Fitted fixing not inspected; offered choices retained','OWNER_REPORTED_DETAIL; OBJECT_MEASUREMENT_OR_INSPECTION_NOT_DOCUMENTED':'Owner reported; object measurement or inspection not documented','OWNER_ACCEPTED_QUALIFIED_ESTIMATE; NOT_PHYSICALLY_VERIFIED':'Owner accepted estimate; physical check still needed','QUALIFIED_ESTIMATE_OR_COMPARATOR; NOT_PHYSICALLY_VERIFIED':'Estimate or comparator; physical check still needed','RECORDED_SOURCE_OR_WORKING_DETAIL; OBJECT_VERIFICATION_STILL_REQUIRED':'Recorded working/source detail; physical check still needed'};physical_cards=[];physical_rows=[]
for x in physical['options']:
 table=[]
 for row in x['physical_fields']:
  table.append('<tr><th>'+esc(row['field'])+'</th><td>'+esc(row['current_working_detail'])+'<p><strong>'+esc(labels[row['verification_outcome']])+'</strong></p><p>'+esc(row['requires_object_specific_evidence'])+'</p><details><summary>Retained source basis and assertions</summary><p>'+esc(row['recorded_basis'])+'</p><p>Recorded source assertions: '+str(row['source_assertions_count'])+'. No new physical measurement is supplied.</p></details></td></tr>');z=x['image_reference'];physical_rows.append({'option_id':x['option_id'],'component_id':row['component_id'],'name':x['name'],'field':row['field'],'working_detail':row['current_working_detail'],'verification_outcome':labels[row['verification_outcome']],'source_assertions':row['source_assertions_count'],'physical_evidence_needed':row['requires_object_specific_evidence'],'new_physical_verification':False,'image_url':z.get('image_url',''),'folder_url':z.get('folder_url',''),'file_id':z.get('file_id',''),'folder_id':z.get('folder_id','')})
 physical_cards.append('<article id="'+esc(x['option_id'])+'"><h2>'+esc(x['name'])+'</h2><p>'+ref_links(x['image_reference'])+'</p><table>'+''.join(table)+'</table><p>'+link('Physical_Verification_Input_187_Options.csv','Record actual measurements and maker/inspection evidence')+'</p><small>'+esc(x['option_id'])+'</small></article>')
page('physical-evidence-review.html','Physical specification evidence for187 active options','<p>All748 physical field groups were audited against their retained working details, source assertions and owner instructions. Five distinct recorded local source references match their saved digests. The187-row measurement input is empty. No option gains a new physical verification. Dimensions, weights, material hypotheses, offered fixing choices and source conflicts retain their existing qualifications.</p><p>Start with One Leaf Pewter. Provide actual width × height × maximum depth, bare-panel weight, maker material details and fitted fixing type/count with an object or batch reference and date. Accepted estimates remain in place until then.</p>'+''.join(physical_cards),187)
csvfile('Physical_Source_Audit_748_Field_Groups.csv',physical_rows)
csvfile('Photograph_Review_31_Roles.csv',[{'option_id':x['option_id'],'name':x['name'],'role':x['role'],'review_state':x['review_state'],'current_family_file_count':x['current_family_file_count'],'required_photograph':str(x['required_photograph']),'qualification':x['qualification'],'image_url':x['existing_individual_reference']['image_url'],'folder_url':x['existing_individual_reference']['folder_url'],'file_id':x['existing_individual_reference']['file_id'],'folder_id':x['existing_individual_reference']['folder_id']}for x in photo['requests']+photo['held_requests']])
for name in ['index.html','specifications-to-verify.html']:
 p=OUT/name;t=p.read_text().replace('</nav>',' · <a href="physical-evidence-review.html">Physical evidence audit</a> · <a href="photograph-review-walkthrough.html">Current photograph review</a> · <a href="deco004-changes.html">Deco004 folder</a></nav>',1);p.write_text(t)
 for x in pages:
  if x['path']==str(p):x['sha256']=sha(p)
count=read(m['source_count_summary']['snapshot'])
def reroute(t):
 if isinstance(t,str):return t.replace(str(OLD),str(OUT))
 if isinstance(t,list):return[reroute(x)for x in t]
 if isinstance(t,dict):return{k:reroute(x)for k,x in t.items()}
 return t
count=reroute(count);count['latest_deco004_folder_refresh']={'existing_file_paths_refreshed':1,'actual_parent_changes':1,'new_photo_roles':0};count['latest_scene_navigation_refresh']={'existing_file_paths_refreshed':2,'folder_names_refreshed':1,'new_photo_roles':0};count['active_context_requests']=12;count['held_context_cases']=10;count['latest_physical_source_audit']={'active_options':187,'physical_field_groups':748,'new_physical_verifications':0};write(OUT/'current-count-summary.json',count)
brief=read(m['source_photo_requests']['snapshot']);brief['requests']=[x for x in brief['requests']if x['option_id']not in deferids];brief.update(recorded_utc=datetime.now(timezone.utc).isoformat(),status='CURRENT_29_ACTIVE_PHOTOGRAPH_ROLES_AFTER_TWO_OWNER_DEFERRALS',expected_after_bordered_import=False);brief['counts'].update(option_records=27,missing_roles=29,display_context=12,held_context_cases_excluded=10);brief['owner_context_deferrals']=defers;write(OUT/'remaining-photograph-requests.json',brief)
class Parser(HTMLParser):
 def __init__(self):super().__init__();self.links=[];self.images=[];self.ids=set();self.cards=0
 def handle_starttag(self,t,attrs):
  d=dict(attrs)
  if t=='article':self.cards+=1
  if d.get('id'):self.ids.add(d['id'])
  if t=='a':self.links.append(d.get('href',''))
  if t=='img':self.images.append(d.get('src',''))
parsed={}
for x in pages:
 p=Path(x['path']).resolve();z=Parser();z.feed(p.read_text());assert z.cards==x['cards'],(p.name,z.cards,x['cards']);parsed[p]=z
for p,z in list(parsed.items()):
 for u in z.links:
  assert 'BOLDSTONE_BACKUP'not in u.upper()
  if u.startswith('https://www.dropbox.com/'):assert '/BOLDSTONE%20MASTER/'in u.upper()or'/BOLDSTONE MASTER/'in u.upper()
  if u.startswith('https://'):continue
  path,_,anchor=u.partition('#');dest=(p.parent/path).resolve()if path and not Path(path).is_absolute()else(Path(path).resolve()if path else p);assert dest.is_file(),(p,u)
  if anchor and dest.suffix=='.html':
   if dest not in parsed:q=Parser();q.feed(dest.read_text());parsed[dest]=q
   assert anchor in parsed[dest].ids,(p,u)
 for u in z.images:assert(p.parent/u).is_file(),(p,u)
counts={**source['counts'],'new_individual_roles_closed':0,'new_series_roles_closed':0,'in_situ_roles_closed':0,'reviewer_verified_display_bindings':0,'active_in_situ_cases_reviewed':14,'source_required_in_situ_cases':12,'held_in_situ_cases_unchanged':8,'new_owner_context_deferrals':2,'held_in_situ_cases':10,'series_cases_reviewed':17,'current_file_paths_refreshed':3,'current_folder_names_refreshed':1,'actual_parent_id_changes':1,'additional_individual_references':0,'physical_options_source_audited':187,'physical_field_groups_source_audited':748,'new_physical_verifications':0}
result={'status':'PASS_CURRENT_LINKED_REPORTS','recorded_utc':datetime.now(timezone.utc).isoformat(),'output_directory':str(OUT),'pages':pages,'csv_files':csvs,'thumbnail_files':images,'counts':counts,'register_sha256':sha(H/'canonical-master-register.json'),'audit_sha256':sha(H/'image-coverage-current.json'),'pixels_edited':False,'native_or_platform_writes':0,'copied_image_bytes_verified':True,'source_report_sha256':m['source_report_verification']['sha256']};write(H/'report-verification.json',result);print(json.dumps({'status':result['status'],'pages':len(pages),'photo_roles_reviewed':31,'physical_options_reviewed':187,'physical_groups':748,'photo_gaps_closed':0,'new_physical_verifications':0}))
