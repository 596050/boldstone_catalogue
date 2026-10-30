"""Publish series-only active requests while retaining all context gaps as held."""
import copy,csv,hashlib,html,json,re,shutil
from pathlib import Path
from html.parser import HTMLParser
from datetime import datetime,timezone
H=Path(__file__).resolve().parent;B=H.parents[2];OUT=B/'outputs'/H.name
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();esc=lambda x:html.escape(str(x),quote=True)
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
m=read(H/'input-manifest.json');source=read(m['source_report_verification']['snapshot']);OLD=Path(source['output_directory']);g=read(H/'canonical-master-register.json');a=read(H/'image-coverage-current.json');event=read(H/'global-owner-context-hold.json');held=set(event['all_held_option_ids']);opts={x['product_id']:x for x in g['options']};pages=[];csvs=[];images=[]
notice='<section><strong>Current owner instruction:</strong> all22 missing in situ/display photograph requests are on hold until the owner resumes. Their gaps remain recorded.17 separate series requests remain active. Individual references and all physical specifications retain their existing qualifications.</section>'
def current_text(t):
 t=t.replace(str(OLD),str(OUT)).replace('Active_In_Situ_Photographs_Required_12.csv','Active_In_Situ_Photographs_Required_0.csv').replace('Held_In_Situ_Cases_10.csv','Held_In_Situ_Cases_22.csv')
 for old,new in [('12 active in situ photograph requests','0 active in situ photograph requests'),('12 active context','0 active context'),('10 held context','22 held context'),('Ten held context cases — gaps retained','All22 missing context cases — owner held'),('29 remain active after two scoped deferrals','17 series requests remain active after the global context hold'),('12 active context and17 series requests remain after two owner deferrals;10 held context cases retain open gaps.','0 context prompts remain active;17 separate series requests remain active and22 context gaps are held.')]:t=t.replace(old,new)
 return t
def cards(t):return re.findall(r'<article\b[^>]*>.*?</article>',t,re.S)
active_source=current_text((OLD/'active-in-situ-photo-requests.html').read_text());held_source=current_text((OLD/'held-in-situ-cases.html').read_text());held_cards=cards(held_source)+cards(active_source);assert len(held_cards)==22
def mark_context(t):return t.replace('<p>In situ · Open</p>','<p><strong>In situ · Owner held — gap retained</strong></p>')
for item in source['thumbnail_files']:
 src=Path(item['path']);assert sha(src)==item['sha256'];dest=OUT/src.relative_to(OLD);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dest);images.append({**item,'path':str(dest)})
regenerate={'remaining-photograph-requests.html','photograph-review-walkthrough.html'}
for item in source['pages']:
 src=Path(item['path']);assert sha(src)==item['sha256'];name=src.name
 if name in regenerate:continue
 t=current_text(src.read_text());count=item['cards']
 if name=='active-in-situ-photo-requests.html':t=re.sub(r'<article\b[^>]*>.*?</article>','',t,flags=re.S);count=0
 if name=='held-in-situ-cases.html':
  t=re.sub(r'<article\b[^>]*>.*?</article>','',t,flags=re.S);t=t.replace('</main>',''.join(mark_context(z).replace('</h2>','</h2><p><strong>OWNER HOLD — do not request this missing context photograph until the owner resumes.</strong></p>',1)for z in held_cards)+'</main>');count=22
 if name in ['index.html','in-situ-images.html']:t=mark_context(t)
 t=t.replace('</h1>','</h1>'+notice,1);dest=OUT/name;dest.write_text(t);pages.append({**item,'path':str(dest),'sha256':sha(dest),'cards':count})
active_rows=[]
for item in source['csv_files']:
 src=Path(item['path']);assert sha(src)==item['sha256'];dest=OUT/src.name
 with src.open(encoding='utf-8-sig',newline='')as f:r=csv.DictReader(f);fields=r.fieldnames;rows=list(r)
 changed=False
 if src.name=='Active_In_Situ_Photographs_Required_12.csv':active_rows=copy.deepcopy(rows);assert len(rows)==12;rows=[];dest=OUT/'Active_In_Situ_Photographs_Required_0.csv';changed=True
 if src.name=='Held_In_Situ_Cases_10.csv':assert len(active_rows)==12;rows.extend([{k:z.get(k,'')for k in fields}for z in active_rows]);dest=OUT/'Held_In_Situ_Cases_22.csv';changed=True
 for row in rows:
  if row.get('option_id')in held and (row.get('role')in ['In situ','Display/context']or src.name=='Held_In_Situ_Cases_10.csv'):
   for key in ['owner_response','qualification']:
    if key in row:row[key]=(row[key]+'\nOwner global hold: defer missing context photography until owner resumes; gap retained.').strip();changed=True
   if 'review_state'in row:row['review_state']='OWNER_GLOBAL_CONTEXT_HOLD_GAP_RETAINED';changed=True
 if changed:
  with dest.open('w',encoding='utf-8-sig',newline='')as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
 else:shutil.copy2(src,dest)
 csvs.append({**item,'path':str(dest),'sha256':sha(dest),'rows':len(rows)})
css=re.search(r'<style>(.*?)</style>',(OUT/'index.html').read_text(),re.S).group(1)
nav='<nav><a href="index.html">All diagnostic gaps</a> · <a href="remaining-photograph-requests.html">17 active series requests</a> · <a href="held-in-situ-cases.html">22 held context cases</a> · <a href="physical-evidence-review.html">Physical specification evidence</a></nav>'
def link(u,label):return '<a href="'+esc(u)+'">'+esc(label)+'</a>'
def ref(o):return link(o['image_url'],'Current individual image')+' · '+link(o['folder_url'],'Actual containing folder')
def page(name,title,body,n):
 p=OUT/name;p.write_text('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+esc(title)+'</title><style>'+css+'</style></head><body><main><h1>'+esc(title)+'</h1>'+notice+nav+body+'</main></body></html>');pages.append({'path':str(p),'sha256':sha(p),'cards':n})
photo=read(H/'photo-source-review.json');assert len(photo['requests'])==17 and all(x['role']=='Series'for x in photo['requests']);brief=read(m['source_photo_requests']['snapshot']);prior={x['option_id']:x for x in brief['requests']};series_cards=[];walk=[];requests=[]
for x in photo['requests']:
 o=opts[x['option_id']];action='Show '+o['name']+' as a complete, identifiable member of a group or series. Identify its position and exact finish. A plain group arrangement is sufficient; a wider in situ setting is not required.'
 qualification=x['qualification'];finding=x.get('retained_series_review_finding')
 if finding:qualification+=' '+str(finding)
 body='<h2>'+esc(o['name'])+' — Series</h2><p>'+ref(o)+'</p><p>'+esc(action)+'</p><p>'+esc(qualification)+'</p><small>'+esc(o['product_id']+' / '+o['file_id']+' / '+o['folder_id'])+'</small>'
 series_cards.append('<article id="'+esc(o['product_id'])+'">'+body+'</article>');walk.append('<article id="'+esc(o['product_id']+'-series')+'">'+body+'</article>')
 z=copy.deepcopy(prior[o['product_id']]);z['retained_previous_role_request']={'missing_roles':z['missing_roles'],'requested_photograph':z.get('requested_photograph')};z.update(missing_roles=['Series'],roles_count=1,requested_photograph=[action],existing_individual_reference={k:o[k]for k in ['image_url','folder_url','file_id','folder_id']});requests.append(z)
page('remaining-photograph-requests.html','17 active series photograph requests','<p>Context photography is held under the latest owner instruction. Start with Acanthus One Leaf Left — Pewter for a series-only group identification; its individual image is already accepted. Existing images and finishes must be identifiable before any new role is accepted.</p>'+''.join(series_cards),17)
anchors=''.join('<section id="'+esc(oid+'-context')+'">Context request owner-held; image gap retained.</section>'for oid in sorted(held))
page('photograph-review-walkthrough.html','Series-only photograph review','<p>The earlier31-role source audit is retained. The global owner hold suppresses all missing context prompts. These17 series roles remain active; no new photograph role or physical verification is claimed.</p>'+''.join(walk)+anchors,17)
brief.update(recorded_utc=datetime.now(timezone.utc).isoformat(),status='CURRENT_17_SERIES_REQUESTS_ALL_MISSING_CONTEXT_OWNER_HELD',requests=requests,global_context_owner_hold=event);brief['counts'].update(option_records=17,missing_roles=17,display_context=0,series=17,held_context_cases_excluded=22);write(OUT/'remaining-photograph-requests.json',brief)
count=read(m['source_count_summary']['snapshot']);count['active_context_requests']=0;count['held_context_cases']=22;count['latest_global_context_hold']={'owner_policy_sha256':m['owner_policy']['sha256'],'active_context':0,'held_context':22,'series_active':17,'gaps_closed':0};write(OUT/'current-count-summary.json',count)
class Parser(HTMLParser):
 def __init__(self):super().__init__();self.ids=set();self.links=[];self.images=[];self.cards=0
 def handle_starttag(self,tag,attrs):
  d=dict(attrs)
  if tag=='article':self.cards+=1
  if d.get('id'):self.ids.add(d['id'])
  if tag=='a':self.links.append(d.get('href',''))
  if tag=='img':self.images.append(d.get('src',''))
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
counts={**source['counts'],'active_in_situ_cases_reviewed':0,'source_required_in_situ_cases':0,'held_in_situ_cases':22,'new_owner_context_deferrals':12,'new_individual_roles_closed':0,'new_series_roles_closed':0,'in_situ_roles_closed':0,'current_file_paths_refreshed':0,'current_folder_names_refreshed':0,'actual_parent_id_changes':0,'physical_options_source_audited_this_refresh':0,'new_physical_verifications':0,'active_photograph_roles':17}
result={'status':'PASS_CURRENT_LINKED_REPORTS','recorded_utc':datetime.now(timezone.utc).isoformat(),'output_directory':str(OUT),'pages':pages,'csv_files':csvs,'thumbnail_files':images,'counts':counts,'register_sha256':sha(H/'canonical-master-register.json'),'audit_sha256':sha(H/'image-coverage-current.json'),'pixels_edited':False,'native_or_platform_writes':0,'copied_image_bytes_verified':True,'source_report_sha256':m['source_report_verification']['sha256']};write(H/'report-verification.json',result);print(json.dumps({'status':result['status'],'pages':len(pages),'active_series_requests':17,'active_context':0,'held_context':22,'photo_gaps_closed':0}))
