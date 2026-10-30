"""Publish reviewable local draft projections and correctly scoped photo lists."""
import copy,csv,hashlib,html,json,re,shutil
from pathlib import Path
from html.parser import HTMLParser
from datetime import datetime,timezone
H=Path(__file__).resolve().parent;B=H.parents[2];OUT=B/'outputs'/H.name
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();esc=lambda x:html.escape(str(x),quote=True)
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
m=read(H/'input-manifest.json');src=read(m['source_report_verification']['snapshot']);OLD=Path(src['output_directory']);g=read(H/'canonical-master-register.json');a=read(H/'image-coverage-current.json');oid='BSI-C3AA3700F7DA';o=next(o for o in g['options']if o['product_id']==oid);event=read(H/'imported-owner-image-acceptance.json');pages={};csvs={};images=[]
notice='<section><strong>Current position:</strong>188 active options,189 retained records and112 working component identities. No active photograph requests. The MSW2 White Water Feature whole-group image is owner-accepted as a qualified one-panel listing reference for now; technical coverage stays Group only.24 diagnostic requirements remain:22 held context,one held Series and one deferred Frozen Fish identity.10 group/combined-reference exceptions remain qualified; no new complete photograph or physical verification. <a href="water-group-listing-reference.html">Exact image approval</a> · <a href="current-draft-projections.html">Current local draft values</a>.</section>'
for x in src['thumbnail_files']:
 p=Path(x['path']);assert sha(p)==x['sha256'];d=OUT/p.relative_to(OLD);d.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,d);images.append({**x,'path':str(d)})
for x in src['pages']:
 p=Path(x['path']);assert sha(p)==x['sha256'];text=p.read_text().replace(str(OLD),str(OUT));text=re.sub(r'<section><strong>Current (?:position|catalogue):</strong>.*?</section>','',text,flags=re.S)
 if p.name in ['index.html','individual-images.html','remaining-photograph-requests.html','photograph-review-walkthrough.html']:
  text=re.sub(r'<article\b[^>]*>.*?</article>',lambda z:''if oid in z.group(0)else z.group(0),text,flags=re.S)
 for before,after in [('25 diagnostic actions','24 diagnostic actions'),('1 active source request','No active source requests'),('One new individual water-build photograph requirement. No active Series-photo requests remain.','No active individual or Series photograph requests remain.'),('1 individual image','1 deferred identity'),('Separate_Individual_Photographs_Required_1.csv','Separate_Individual_Photographs_Required_0.csv')]:text=text.replace(before,after)
 text=text.replace('</h1>','</h1>'+notice,1);d=OUT/p.name;d.write_text(text);pages[p.name]={'path':str(d),'sha256':sha(d),'cards':text.count('<article')}
css=re.search(r'<style>(.*?)</style>',(OUT/'index.html').read_text(),re.S).group(1)
def page(name,title,body):
 p=OUT/name;p.write_text('<!doctype html><html lang="en"><head><meta charset="utf-8"><title>'+title+'</title><style>'+css+'</style></head><body><main><h1>'+title+'</h1>'+notice+body+'</main></body></html>');pages[name]={'path':str(p),'sha256':sha(p),'cards':body.count('<article')}
def links(o):return '<p><a href="'+esc(o['image_url'])+'">Whole identification/source photograph</a> · <a href="'+esc(o['folder_url'])+'">Actual containing folder</a></p>'
water='<article id="'+oid+'"><h2>'+esc(o['name'])+'</h2>'+links(o)+'<p>'+esc(event['approved_caption'])+'</p><p>Owner response: '+esc(event['owner_text'])+'. Whole group accepted for now. Technical source remains Group only; no separate complete image, exact member pixel position, manufacturing evidence or physical installation is newly verified.</p><p>Existing six working fields, single-panel sale record, context/series bindings and image/folder IDs retained. No crop or image alteration.</p><small>'+esc(o['file_id']+' / '+o['folder_id'])+'</small></article>'
page('water-group-listing-reference.html','Moon and Shellwave2 qualified group listing reference',water)
ap=OUT/'accepted-listing-references.html';text=ap.read_text();text=text.replace('</main>',water+'</main>');ap.write_text(text);pages[ap.name]={'path':str(ap),'sha256':sha(ap),'cards':text.count('<article')}
cards=[];opts={o['product_id']:o for o in g['options']}
for x in read(H/'fingerprint-field-projections.json'):
 o1=opts[x['option_id']];rows=''.join('<tr><th>'+esc(k)+'</th><td>'+esc(v['display'])+'</td></tr>'for k,v in x['full_working_fields'].items());cards.append('<article id="'+o1['product_id']+'"><h2>'+esc(o1['name'])+'</h2>'+links(o1)+'<p>Six existing qualified working fields projected into the current local draft. Existing SKU/group/variant identifiers and activation/media conditions retained. No native listing created.</p><table>'+rows+'</table></article>')
for x in read(H/'current-copy-projections.json'):
 o1=opts[x['option_id']];rows=''.join('<tr><th>'+esc(k)+'</th><td>'+esc(v)+'</td></tr>'for k,v in x['copy_values'].items());cards.append('<article id="'+o1['product_id']+'"><h2>'+esc(o1['name'])+' — current copy draft</h2>'+links(o1)+'<p>Local copy projection from the current canonical working fields. Prices remain estimates and availability follows the recorded owner policy. Native tuple is dated source evidence; execution remains unapproved and unperformed. Original historical request and SKU unchanged.</p><table>'+rows+'</table></article>')
page('current-draft-projections.html','Six complete draft fieldsets and four current copy drafts','<p>All101 current individual draft records now embed six working field objects,606 total. These are local drafts; current authenticated platform matching and physical verification remain qualified.</p>'+''.join(cards))
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
 if name!='Separate_Individual_Photographs_Required_1.csv':csvfile(name,rows,fields)
fields,rows=copy.deepcopy(oldcsv['All_Current_Picture_Actions.csv']);task=next(t for t in a['missing_pictures']if t['option_id']==oid and t['role']=='Individual')
for r in rows:
 if r['option_id']==oid and r['role']=='Individual':
  for k in ['action','qualification','owner_response','status']:r[k]=task[k]
required=[r for r in rows if r['status']=='Open'];resolved=[r for r in rows if r['status']=='Resolved'];individual=[r for r in required if r['role']=='Individual']
assert(len(rows),len(required),len(resolved),len(individual))==(210,24,113,1)
for name,data in [('All_Current_Picture_Actions.csv',rows),('Missing_Pictures_Required.csv',required),('Missing_Individual_Images.csv',individual),('Resolved_Image_Associations.csv',resolved),('Separate_Individual_Photographs_Required_0.csv',[])]:csvfile(name,data,fields)
fields,data=copy.deepcopy(oldcsv['Owner_Accepted_Qualified_Listing_References.csv']);data.append({'option_id':oid,'name':o['name'],'technical_individual_status':'Group only','owner_accepted_listing_reference':'True','separate_photo_request':'Closed by scoped owner exception for now','reference_roles':json.dumps(o['owner_accepted_listing_references']['references'],ensure_ascii=False)});csvfile('Owner_Accepted_Qualified_Listing_References.csv',data,fields)
for name in ['Current_Individual_Options_188.csv','Current_Selling_Details_188.csv','Combined_Shoot_and_Measure_Checklist.csv']:
 fields,data=copy.deepcopy(oldcsv[name])
 for r in data:
  if r['option_id']==oid:r['required_picture_roles']='; '.join(x.strip()for x in r['required_picture_roles'].split(';')if x.strip()!='Individual')
 if name.startswith('Combined_'):data=[r for r in data if r['required_picture_roles']]
 csvfile(name,data,fields)
brief=read(m['source_photo_requests']['snapshot']);prior=copy.deepcopy(brief['requests']);assert len(prior)==1 and prior[0]['option_id']==oid;brief['requests']=[];brief.setdefault('owner_accepted_individual_listing_references',[]).append({'previous_request':prior[0],'owner_approval':event});brief.update(recorded_utc=datetime.now(timezone.utc).isoformat(),status='NO_ACTIVE_PHOTOGRAPH_REQUESTS_HOLDS_RETAINED');brief['counts'].update(option_records=0,missing_roles=0,individual=0);write(OUT/'remaining-photograph-requests.json',brief)
count=read(m['source_count_summary']['snapshot']);count.update(individual_gaps=1,separate_individual_photos_required=0,owner_accepted_reference_exceptions=10,required_picture_actions=24,active_individual_requests=0,latest_draft_projection_and_owner_reference_import=read(H/'import-summary.json'));count['current_option_list']={'path':str(OUT/'Current_Individual_Options_188.csv'),'sha256':sha(OUT/'Current_Individual_Options_188.csv'),'rows':188};write(OUT/'current-count-summary.json',count)
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
assert pages['index.html']['cards']==24 and pages['individual-images.html']['cards']==1 and pages['remaining-photograph-requests.html']['cards']==0 and pages['accepted-listing-references.html']['cards']==10
counts={**src['counts'],'required_actions':24,'find_capture':23,'individual_gaps':1,'owner_accepted_reference_exceptions':10,'separate_individual_photos_required':0,'resolved_actions':113,'combined_required_option_rows':csvs['Combined_Shoot_and_Measure_Checklist.csv']['rows'],'active_photograph_roles':0,'active_individual_source_requests':0,'current_file_paths_refreshed':0,'actual_parent_id_changes':0,'new_owner_reference_exceptions':1,'new_individual_roles_closed':0,'new_complete_photographs_verified':0}
r={'status':'PASS_CURRENT_LINKED_REPORTS','recorded_utc':datetime.now(timezone.utc).isoformat(),'output_directory':str(OUT),'pages':list(pages.values()),'csv_files':list(csvs.values()),'thumbnail_files':images,'counts':counts,'register_sha256':sha(H/'canonical-master-register.json'),'audit_sha256':sha(H/'image-coverage-current.json'),'pixels_edited':False,'native_or_platform_writes':0,'copied_image_bytes_verified':True};write(H/'report-verification.json',r);print(json.dumps({'status':r['status'],'pages':len(pages),'active_photo_requests':0,'qualified_group_exceptions':10,'copy_projections':4,'completed_fingerprint_drafts':6}))
