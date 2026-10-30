"""Publish current local review pages/CSVs, retaining earlier source evidence."""
import copy,csv,hashlib,html,json,re,shutil
from pathlib import Path
from datetime import datetime,timezone
from html.parser import HTMLParser
H=Path(__file__).resolve().parent;B=H.parents[2];OUT=B/'outputs'/H.name
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();esc=lambda x:html.escape(str(x),quote=True)
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
m=read(H/'input-manifest.json');src=read(m['source_report_verification']['snapshot']);OLD=Path(src['output_directory']);g=read(H/'canonical-master-register.json');a=read(H/'image-coverage-current.json');proj=read(H/'projection-index.json');o=g['options'][-1];oid=o['product_id'];ref=a['coverage'][-1]['individual']['reference'];summary=read(H/'import-summary.json');proposal=read(m['product_proposal']['snapshot']);members=read(m['member_decision']['snapshot']);pages={};csvs={};images=[]
for x in src['thumbnail_files']:
 p=Path(x['path']);assert sha(p)==x['sha256'];d=OUT/p.relative_to(OLD);d.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,d);images.append({**x,'path':str(d)})
original=proposal['reused_original'];dest=OUT/'images/new-msw2-water-whole-source.jpg';shutil.copy2(original['path'],dest);assert sha(dest)==original['sha256'];images.append({'path':str(dest),'sha256':sha(dest),'file_id':ref['file_id'],'whole_original':True})
css=re.search(r'<style>(.*?)</style>',(OLD/'index.html').read_text(),re.S).group(1)
notice='<section><strong>Current catalogue:</strong>188 active options,189 retained records and112 working component identities. One separate Moon and Shellwave2 White Water Feature option is added under its existing design. Four existing White Moonphase members are confirmed. All prior holds and estimates remain. <a href="water-products-and-memberships.html">New option and membership details</a>.</section>'
nav='<nav><a href="index.html">40 diagnostic actions</a> · <a href="remaining-photograph-requests.html">16 active source requests</a> · <a href="held-in-situ-cases.html">22 held context cases</a> · <a href="held-series-cases.html">One held Series case</a> · <a href="specifications-to-verify.html">188-option specifications</a></nav>'
for x in src['pages']:
 p=Path(x['path']);assert sha(p)==x['sha256'];text=p.read_text().replace(str(OLD),str(OUT));text=re.sub(r'<section><strong>Current position:</strong>.*?</section>','',text,flags=re.S);d=OUT/p.name;d.write_text(text);pages[p.name]={'path':str(d),'sha256':sha(d),'cards':text.count('<article')}
def page(name,title,body):
 p=OUT/name;p.write_text('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+esc(title)+'</title><style>'+css+'</style></head><body><main><h1>'+esc(title)+'</h1>'+notice+nav+body+'</main></body></html>');pages[name]={'path':str(p),'sha256':sha(p),'cards':body.count('<article')}
def link(url,label):return '<a href="'+esc(url)+'" target="_blank" rel="noopener">'+esc(label)+'</a>'
def article(title,body,ident=''):return '<article'+(' id="'+esc(ident)+'"'if ident else'')+'><h2>'+esc(title)+'</h2>'+body+'</article>'
def taskcard(t):
 r=t['reference'];return article(t['name'],'<p>'+esc(t['role']+' · '+t['status'])+'</p><p>'+link(r['image_url'],'Whole identification/source image')+' · '+link(r['folder_url'],'Actual containing folder')+'</p><p>'+esc(t['action'])+'</p><p>'+esc(t['qualification'])+'</p><small>'+esc(t['option_id']+' / '+r['file_id']+' / '+r['folder_id'])+'</small>',t['option_id']+'-'+t['role'].replace(' ',''))
required=[t for t in a['missing_pictures']if t['status']=='Open'];held=read(H/'guided-owner-review-state.json');active=[t for t in required if not(t['role']=='In situ'and t['option_id']in held['held_in_situ_ids'])and not(t['role']=='Series'and t['option_id']in held['held_series_ids'])and not(t['role']=='Individual'and t['option_id']in held['deferred_individual_ids'])]
assert len(required)==40 and len(active)==16
page('index.html','Current photograph and identity actions',''.join(taskcard(t)for t in required));page('individual-images.html','Two individual-image or identity cases','<p>Frozen Fish legacy identity stays deferred at70cm high×15cm wide. The new water-build option has a whole group reference but no approved isolated individual photograph.</p>'+''.join(taskcard(t)for t in required if t['role']=='Individual'))
page('remaining-photograph-requests.html','16 active source requests','<p>One new individual water-build photograph requirement and15 existing Series requests. This checklist records the gaps; it sends no new owner question.22 missing context requests and one separate Series request remain held.</p>'+''.join(taskcard(t)for t in active));page('photograph-review-walkthrough.html','Current active photograph-source walkthrough',''.join(taskcard(t)for t in active))
newbody='<p>'+link(ref['image_url'],'Whole water-scene group photograph')+' · '+link(ref['folder_url'],'Actual containing folder')+'</p><img src="images/new-msw2-water-whole-source.jpg" alt="Whole unmodified two-panel water scene"><p>'+esc(o['source_scope_notes'])+'</p><table>'+''.join('<tr><th>'+esc(f)+'</th><td>'+esc(v['display'])+'</td></tr>'for f,v in o['master_fields'].items())+'</table><small>'+esc(oid+' / '+ref['file_id']+' / '+ref['folder_id'])+'</small>'
membercards=[]
for member in members['members']:
 membercards.append(article(member['name'],'<p>'+link(members['image_url'],'Whole White water arrangement')+' · '+link(members['folder_url'],'Containing folder')+'</p><p>Owner confirms this named design and White finish in the arrangement. No panel quantity, position, same physical cast, separate water-ready build or fountain sale unit is inferred. Existing individual specifications and photo-role statuses remain unchanged.</p><small>'+esc(member['product_id']+' / '+members['file_id']+' / '+members['folder_id'])+'</small>',member['product_id']))
page('water-products-and-memberships.html','One separate water-build product and four existing arrangement members',article(o['name'],newbody,oid)+''.join(membercards))
def append_card(name,card):
 p=OUT/name;text=p.read_text();point='</main>'if'</main>'in text else'</body>';assert point in text;text=text.replace(point,card+point,1);text=text.replace('187 active','188 active').replace('187 current','188 current').replace('187-option','188-option');p.write_text(text);pages[name].update(sha256=sha(p),cards=text.count('<article'))
append_card('specifications-to-verify.html',article(o['name'],newbody,oid));append_card('selling-details.html',article(o['name'],newbody,oid));append_card('physical-evidence-review.html',article(o['name'],'<p>New four physical field groups are source-qualified estimates or hypotheses only. Actual measurements, mass, material recipe and fitted fixing remain unverified.</p>'+newbody,oid));append_card('current-context-references.html',article(o['name'],'<p>'+link(ref['image_url'],'Qualified whole water-scene context')+' · '+link(ref['folder_url'],'Actual containing folder')+'</p><p>'+esc(o['context_description'])+'</p><small>'+esc(ref['file_id']+' / '+ref['folder_id'])+'</small>',oid))
oldcsv={}
for x in src['csv_files']:
 p=Path(x['path']);assert sha(p)==x['sha256']
 with p.open(encoding='utf-8-sig',newline='')as f:r=csv.DictReader(f);fields=r.fieldnames;data=list(r)
 oldcsv[p.name]=(fields,data);d=OUT/p.name;shutil.copy2(p,d);csvs[p.name]={**x,'path':str(d)}
renames={}
def csvfile(name,data,fields,prior=None):
 if prior and prior!=name:
  csvs.pop(prior,None);(OUT/prior).unlink();renames[prior]=name
 p=OUT/name
 with p.open('w',encoding='utf-8-sig',newline='')as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows([{k:r.get(k,'')for k in fields}for r in data])
 csvs[name]={'path':str(p),'sha256':sha(p),'rows':len(data)}
fields,allrows=copy.deepcopy(oldcsv['All_Current_Picture_Actions.csv']);t=a['missing_pictures'][-1];newrow={'sequence':len(allrows)+1,'option_id':oid,'name':o['name'],'role':'Individual','action_type':t['action_type'],'status':'Open','action':t['action'],'qualification':t['qualification'],'image_url':ref['image_url'],'folder_url':ref['folder_url'],'file_id':ref['file_id'],'folder_id':ref['folder_id'],'native_source_status':'Retained current whole-group source; exact individual water build unverified','owner_response':t['owner_response']};allrows.append(newrow);csvfile('All_Current_Picture_Actions.csv',allrows,fields);req=[r for r in allrows if r['status']=='Open'];csvfile('Missing_Pictures_Required.csv',req,fields);csvfile('Missing_Individual_Images.csv',[r for r in req if r['role']=='Individual'],fields);csvfile('Separate_Individual_Photographs_Required_1.csv',[newrow],fields,'Separate_Individual_Photographs_Required_0.csv')
base={'option_id':oid,'component_id':o['canonical_component_id'],'name':o['name'],'family':o['family'],**{f:v['display']for f,v in o['master_fields'].items()},'individual_photo_status':'Group only','listing_reference_disposition':'Whole group source only; new individual listing photograph not owner-approved','individual_image':ref['image_url'],'containing_folder':ref['folder_url'],'file_id':ref['file_id'],'folder_id':ref['folder_id'],'required_picture_roles':'Individual','physical_specs_verified':'False','native_reference_status':'Retained whole group source; actual containing folder unchanged'}
for prior,name in [('Current_Individual_Options_187.csv','Current_Individual_Options_188.csv'),('Combined_Shoot_and_Measure_Checklist.csv','Combined_Shoot_and_Measure_Checklist.csv')]:
 fields,data=copy.deepcopy(oldcsv[prior]);data.append(base);csvfile(name,data,fields,prior)
fields,data=copy.deepcopy(oldcsv['Current_Selling_Details_187.csv']);selling={**base,'estimated_price_gbp':750,'estimated_price_upper_gbp':'','price_status':'estimate','sale_unit':'per individual panel; pump, basin, pipework and installation separate','lead_time_min_weeks':1,'lead_time_max_weeks':2,'earlier_working_price':'','physical_stock_quantity':''};data.append(selling);csvfile('Current_Selling_Details_188.csv',data,fields,'Current_Selling_Details_187.csv')
fields,data=copy.deepcopy(oldcsv['Specification_Verification_Checklist_1122_Fields.csv'])
for f,v in o['master_fields'].items():data.append({**base,'field':f,'working_description':v['display'],'review_state':v['state'],'basis':v['basis'],'explicit_owner_confirmation':'','physical_verification':0})
csvfile('Specification_Verification_Checklist_1128_Fields.csv',data,fields,'Specification_Verification_Checklist_1122_Fields.csv')
fields,data=copy.deepcopy(oldcsv['Physical_Verification_Input_187_Options.csv']);data.append({**base,'current_working_dimensions':o['master_fields']['Dimensions / depth']['display'],'current_working_weight':o['master_fields']['Weight']['display'],'current_working_material':o['master_fields']['Material / finish']['display'],'current_offered_fixing':o['master_fields']['Fixing']['display'],'verification_status':'Awaiting object-specific measurement or maker evidence'});csvfile('Physical_Verification_Input_188_Options.csv',data,fields,'Physical_Verification_Input_187_Options.csv')
fields,data=copy.deepcopy(oldcsv['Physical_Source_Audit_748_Field_Groups.csv'])
for f in list(o['master_fields'])[:4]:data.append({'option_id':oid,'component_id':o['canonical_component_id'],'name':o['name'],'field':f,'working_detail':o['master_fields'][f]['display'],'verification_outcome':'Qualified comparator or offered choice; no physical verification','source_assertions':0,'physical_evidence_needed':'Object-specific measurement or maker evidence for this water build. '+o['master_fields'][f]['basis'],'new_physical_verification':False,**{k:ref[k]for k in ['image_url','folder_url','file_id','folder_id']}})
csvfile('Physical_Source_Audit_752_Field_Groups.csv',data,fields,'Physical_Source_Audit_748_Field_Groups.csv')
for path in OUT.glob('*.html'):
 text=path.read_text()
 for before,after in renames.items():text=text.replace(before,after)
 if path.name not in ['index.html','individual-images.html','remaining-photograph-requests.html','photograph-review-walkthrough.html','water-products-and-memberships.html']:text=text.replace('</h1>','</h1>'+notice,1)
 path.write_text(text);pages[path.name]['sha256']=sha(path)
brief=read(m['source_photo_requests']['snapshot']);brief['requests'].append({'option_id':oid,'name':o['name'],'roles':['Individual'],'role':'Individual','required_photograph':t['action'],'image_url':ref['image_url'],'folder_url':ref['folder_url'],'file_id':ref['file_id'],'folder_id':ref['folder_id'],'qualification':t['qualification']});brief.update(recorded_utc=datetime.now(timezone.utc).isoformat(),status='CURRENT_15_SERIES_AND_ONE_NEW_INDIVIDUAL_ACTIVE');brief['counts'].update(option_records=16,missing_roles=16,series=15,individual=1);write(OUT/'remaining-photograph-requests.json',brief)
count=read(m['source_count_summary']['snapshot']);count.update(current_individual_options=188,retained_option_records=189,working_field_rows=1128,retained_working_field_rows=1134,individual_gaps=2,technical_individual_gaps=11,separate_individual_photos_required=1,active_individual_requests=1,required_picture_actions=40,latest_owner_water_product_and_members_import=summary);write(OUT/'current-count-summary.json',count)
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
 p=Path(item['path']).resolve();q=Parser();q.feed(p.read_text());assert q.cards==item['cards'];parsed[p]=q
for p,q in list(parsed.items()):
 for u in q.links:
  assert 'BOLDSTONE_BACKUP'not in u.upper()
  if u.startswith('https://'):continue
  d,_,anchor=u.partition('#');dest=(p.parent/d).resolve()if d and not Path(d).is_absolute()else(Path(d).resolve()if d else p);assert dest.is_file(),(p,u)
  if anchor and dest.suffix=='.html':
   if dest not in parsed:z=Parser();z.feed(dest.read_text());parsed[dest]=z
   assert anchor in parsed[dest].ids,(p,u)
 for u in q.images:assert(p.parent/u).is_file(),(p,u)
counts={**src['counts'],'current_options':188,'qualified_field_rows':1128,'required_actions':40,'find_capture':39,'individual_gaps':2,'technical_individual_gaps':11,'separate_individual_photos_required':1,'combined_required_option_rows':37,'active_photograph_roles':16,'active_series_requests':15,'active_individual_source_requests':1,'new_finish_options':0,'new_water_build_options':1,'current_descriptions_updated':0,'current_statuses_aligned_to_existing_available_role':0,'dated_current_reference_notes_appended':0,'new_owner_series_optionality_policies':0,'new_photo_roles_closed':0,'new_option_qualified_group_context_roles':2,'confirmed_existing_arrangement_members_added':4,'physical_options_source_audited':188,'physical_field_groups_source_audited':752,'physical_options_source_audited_this_refresh':1,'physical_field_groups_source_audited_this_refresh':4}
result={'status':'PASS_CURRENT_LINKED_REPORTS','recorded_utc':datetime.now(timezone.utc).isoformat(),'output_directory':str(OUT),'pages':list(pages.values()),'csv_files':list(csvs.values()),'thumbnail_files':images,'counts':counts,'register_sha256':sha(H/'canonical-master-register.json'),'audit_sha256':sha(H/'image-coverage-current.json'),'pixels_edited':False,'native_or_platform_writes':0,'copied_image_bytes_verified':True,'source_report_sha256':m['source_report_verification']['sha256']};write(H/'report-verification.json',result);print(json.dumps({'status':result['status'],'pages':len(pages),'current_options':188,'new_option_id':oid,'new_designs':0,'new_individual_source_cases':1}))
