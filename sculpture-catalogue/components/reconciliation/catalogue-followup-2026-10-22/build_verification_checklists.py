"""Create linked capture and physical-verification checklists from qualified records."""
import collections,csv,hashlib,html,json,re
from pathlib import Path
from datetime import datetime,timezone
from html.parser import HTMLParser
H=Path(__file__).resolve().parent;BASE=H.parents[2];OUT=BASE/'outputs/catalogue-followup-2026-10-22';PRIOR=H.parent/'moonphases-dune-ripple-master-refresh-2026-10-22'
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();esc=lambda x:html.escape(str(x),quote=True)
g=read(H/'canonical-master-register.json');audit=read(H/'image-coverage-current.json');options={x['product_id']:x for x in g['options']};coverage={x['option_id']:x for x in audit['coverage']}
fields=['Dimensions / depth','Weight','Material / finish','Fixing','Individual price','Availability']
tasks=[x for x in audit['missing_pictures']if x['status']=='Open'];byoption=collections.defaultdict(list)
for x in tasks:byoption[x['option_id']].append(x)
checks={
 'Dimensions / depth':'Record the individual face height and width, maximum overall depth and units. Keep whole-set dimensions separate. Retain owner-stated figures and working estimates with their existing evidence labels until a measurement is recorded.',
 'Weight':'Weigh the individual component and record whether attached framework or fixings are included. Keep packaging and whole-set weights separate; photographs cannot establish mass.',
 'Material / finish':'Obtain the maker\'s material/binder, reinforcement and coating specification for this component and finish. A photograph establishes appearance, not chemical composition.',
 'Fixing':'Record the fixing actually fitted to this build, supported by a rear photograph: keyhole count/spacing or cleat dimensions. The offered keyhole/French-cleat choice is already recorded.',
 'Individual price':'Keep the recorded individual price, estimate or quote policy and its unit/source qualification. Confirm the actual order price and any tax/delivery treatment before selling; do not divide a set price to invent a component price.',
 'Availability':'Confirm the selling policy, current production capacity and agreed order lead time. Made-to-order policy does not establish physical stock or unlimited capacity.'}
rows=[];specrows=[]
for x in g['options']:
 oid=x['product_id'];photo=coverage[oid]['individual'].get('reference')or{};r={'option_id':oid,'component_id':x['canonical_component_id'],'name':x['name'],'family':x['family'],
  **{f:x['master_fields'][f]['display']for f in fields},'individual_photo_status':coverage[oid]['individual']['status'],
  'individual_image':photo.get('image_url')or x['image_url'],'containing_folder':photo.get('folder_url')or x['folder_url'],
  'file_id':photo.get('file_id')or x['file_id'],'folder_id':photo.get('folder_id')or x['folder_id'],
  'required_picture_roles':'; '.join(z['role']for z in byoption.get(oid,[])),'physical_specs_verified':False}
 rows.append(r)
 for f in fields:
  v=x['master_fields'][f];ap=v.get('explicit_owner_confirmation',{})
  action=checks[f]
  if f=='Individual price'and ap and 'Quote required'in v['display']:action='Owner explicitly confirms quote required per individual panel. Use that policy; agree the final custom-order quote rather than inventing a numeric selling price.'
  specrows.append({'option_id':oid,'component_id':x['canonical_component_id'],'name':x['name'],'family':x['family'],'field':f,'working_description':v['display'],'recorded_review_state':v['state'],
   'recorded_basis':v['basis'],'source_qualified_physical_verification':bool(v['physical_verification']),'explicit_working_confirmation':ap.get('decision_id',''),
   'verification_action':action,'example_image':r['individual_image'],'containing_folder':r['containing_folder'],'file_id':r['file_id'],'folder_id':r['folder_id']})
assert len(rows)==186 and len(specrows)==1116 and len({r['option_id']for r in rows})==186
def csvfile(name,data):
 p=OUT/name
 with p.open('w',encoding='utf-8-sig',newline='')as f:w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
 with p.open(encoding='utf-8-sig',newline='')as f:back=list(csv.DictReader(f))
 assert len(back)==len(data)and all(x.get('individual_image',x.get('example_image'))and x['containing_folder']and x['file_id']and x['folder_id']for x in back)
 return{'path':str(p),'rows':len(data),'sha256':sha(p)}
indids={x['option_id']for x in tasks if x['role']=='Individual'and x['action_type']=='Find / capture'};assert len(indids)==18
capture=[r for r in rows if r['option_id']in byoption];capture.sort(key=lambda x:(x['option_id']not in indids,x['family'],x['name']))
csvs=[csvfile('Current_Individual_Options_186.csv',rows),csvfile('Specification_Verification_Checklist_1116_Fields.csv',specrows),csvfile('Combined_Shoot_and_Measure_Checklist.csv',capture),csvfile('Separate_Individual_Photographs_Required_18.csv',[x for x in capture if x['option_id']in indids])]
def link(url,label):return'<a href="'+esc(url)+'" target="_blank" rel="noopener">'+esc(label)+'</a>'
parts=[]
for r in rows:
 cells=[]
 for z in [x for x in specrows if x['option_id']==r['option_id']]:
  cells.append('<tr><th>'+esc(z['field'])+'</th><td>'+esc(z['working_description'])+'<details><summary>Recorded state and source basis</summary><p>'+esc(z['recorded_review_state'])+'</p><p>'+esc(z['recorded_basis'])+'</p></details></td><td>'+esc(z['verification_action'])+'</td></tr>')
 parts.append('<article data-search="'+esc(' '.join(str(v)for v in r.values()).lower())+'"><h2>'+esc(r['name'])+'</h2><p>'+link(r['individual_image'],'Dropbox example image')+' · '+link(r['containing_folder'],'Containing folder')+'</p><p>Photograph gaps: '+esc(r['required_picture_roles']or'None in the required-image queue')+'</p><table><thead><tr><th>Specification</th><th>Current qualified working detail</th><th>Verification action</th></tr></thead><tbody>'+''.join(cells)+'</tbody></table><details><summary>Stable IDs</summary>'+esc(r['option_id'])+'<br>'+esc(r['component_id'])+'<br>'+esc(r['file_id'])+'<br>'+esc(r['folder_id'])+'</details></article>')
css='body{font:16px/1.5 Arial,sans-serif;background:#f5f6f3;color:#28362d;margin:0}main{max-width:1250px;padding:24px;margin:auto}article{background:#fff;border:1px solid #d8ded4;margin:22px 0;padding:20px}h1,h2{color:#344e40}a{color:#245f7a}table{border-collapse:collapse;width:100%;table-layout:fixed}th,td{border:1px solid #d8ded4;text-align:left;vertical-align:top;padding:12px;overflow-wrap:anywhere}th:first-child{width:16%}thead th{background:#344e40;color:white}details{font-size:13px;margin-top:10px;color:#64705f}input{font:inherit;padding:10px;width:80%;max-width:650px}.hide{display:none}.toolbar{position:sticky;top:0;background:#f5f6f3;padding:12px 0}@media(max-width:700px){table,thead,tbody,tr,th,td{display:block;width:auto!important}thead{display:none}main{padding:12px}}'
js="const q=document.querySelector('#search');function f(){let n=0;document.querySelectorAll('article').forEach(x=>{const on=x.dataset.search.includes(q.value.toLowerCase());x.classList.toggle('hide',!on);if(on)n++});document.querySelector('#shown').textContent=n+' sculpture options shown'}q.addEventListener('input',f);f();"
intro='<h1>Individual sculpture specifications: verification checklist</h1><p>186 current options across 112 working component identities. Accepted values, estimates, guesses and owner policies retain their labels. The 1,116 rows below describe six working fields per option and their verification actions; they are not 1,116 newly missing values.</p><p>The owner authorized price estimates, made-to-order supply and a 1–2 week lead-time policy where unresolved. Specific earlier instructions take precedence: Moon Crater Phase 4 — Verdigris and Rust retains £175 per panel and a one-week policy. Historical retail/trade values and whole-set units remain separate from current estimated individual prices. No new physical measurements or weighed results were supplied.</p><p>Three complete images are accepted for standalone listings, with origin unverified. There are 18 separate individual photographs to obtain and one deferred Frozen Fish identity. Crops remain declined. Current Frozen Fish remain 70 × 15 cm. Other photograph gaps are 61 in situ and 18 series images.</p><p><a href="Combined_Shoot_and_Measure_Checklist.csv">Combined shoot/measure checklist</a> · <a href="Separate_Individual_Photographs_Required_18.csv">18 individual-photo requests</a> · <a href="Specification_Verification_Checklist_1116_Fields.csv">All field checks CSV</a> · <a href="individual-images.html">Linked photograph examples</a> · <a href="selling-details.html">Current working prices and selling policies</a></p><div class="toolbar"><input id="search" type="search" placeholder="Search sculpture, finish or specification" aria-label="Search sculpture"><p id="shown"></p></div>'
p=OUT/'specifications-to-verify.html';p.write_text('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Individual sculpture specification checks</title><style>'+css+'</style></head><body><main>'+intro+''.join(parts)+'</main><script>'+js+'</script></body></html>')
class Parser(HTMLParser):
 def __init__(self):super().__init__();self.articles=0;self.hrefs=[]
 def handle_starttag(self,t,attrs):
  d=dict(attrs)
  if t=='article':self.articles+=1
  if t=='a':self.hrefs.append(d['href'])
# The selling review uses current image IDs and the sealed source price decisions.
packet={x['product_id']:x for x in read(H/'inputs/commercial_packet.before')['entries']};selling=[];sellcards=[]
for r in rows:
 x=options[r['option_id']];s=x['selling_details'];source=packet[r['option_id']]
 z={**r,'estimated_price_gbp':s['estimated_price'],'estimated_price_upper_gbp':s['estimated_price_upper'],'sale_unit':s['sale_unit'],'price_status':s['price_status'],'lead_time_min_weeks':s['lead_time_min_weeks'],'lead_time_max_weeks':s['lead_time_max_weeks'],'physical_stock_quantity':None,'earlier_working_price':source['before_master_fields']['Individual price']['display'],'price_basis':source['after']['Individual price']['basis']};selling.append(z)
 sellcards.append('<article data-search="'+esc(' '.join(map(str,z.values())).lower())+'"><h2>'+esc(r['name'])+'</h2><p>'+link(r['individual_image'],'Dropbox image')+' · '+link(r['containing_folder'],'Containing folder')+'</p><p><strong>Current price:</strong> '+esc(r['Individual price'])+'</p><p><strong>Availability:</strong> '+esc(r['Availability'])+'</p><p><strong>Unit:</strong> '+esc(s['sale_unit'])+'</p><details><summary>Earlier working price and source basis</summary><p>'+esc(z['earlier_working_price'])+'</p><p>'+esc(z['price_basis'])+'</p></details><p>'+esc(r['option_id'])+' · '+esc(r['file_id'])+' · '+esc(r['folder_id'])+'</p></article>')
sellpath=OUT/'selling-details.html';sellpath.write_text('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Individual working prices and availability</title><style>'+css+'</style></head><body><main><h1>Individual working prices and availability</h1><p>185 estimated prices or ranges, plus the specific owner-accepted Moon Crater Phase 4 — Verdigris and Rust price of £175 per panel. Unresolved availability uses the owner\'s made-to-order and 1–2 week policy. Earlier specific one-week instructions are retained. Actual stock and production capacity remain unverified. Historical one-off and whole-set offers retain their separate scope.</p><p><a href="Current_Selling_Details_186.csv">Download current selling details</a> · <a href="specifications-to-verify.html">Specification checks</a> · <a href="individual-images.html">Individual image gaps</a></p><div class="toolbar"><input id="search" type="search" placeholder="Search sculpture or price" aria-label="Search selling details"><p id="shown"></p></div>'+''.join(sellcards)+'</main><script>'+js+'</script></body></html>')
csvs.append(csvfile('Current_Selling_Details_186.csv',selling))
for page in [p,sellpath]:
 parser=Parser();parser.feed(page.read_text());assert parser.articles==186 and all(u.startswith('https://www.dropbox.com/')or(OUT/u).is_file()for u in parser.hrefs)
priorchecks=read(PRIOR/'capture-and-specification-verification.json');sourceprice=PRIOR/'current-price-source-text-check.json';assert sha(sourceprice)==priorchecks['source_price_check']['sha256']
manifest={'status':'PASS_QUALIFIED_CAPTURE_AND_SPECIFICATION_CHECKLISTS','recorded_utc':datetime.now(timezone.utc).isoformat(),'current_options':186,'working_component_identities':112,'qualified_field_rows':1116,'individual_photographs_required':18,'deferred_identity_records':1,'combined_required_option_rows':len(capture),'in_situ_gaps':61,'series_gaps':18,'new_acceptable_image_roles_closed':3,'cropped_images_created':0,'new_physical_measurements_or_weighed_results_added':0,
 'prior_wall_scan_retained':priorchecks['current_wall_scan'],'prior_scan_reused_without_claiming_new_complete_scan':True,'native_followup':{'path':str(H/'native-and-originals-verification.json'),'sha256':sha(H/'native-and-originals-verification.json')},
 'csv_files':csvs,'pages':[{'path':str(z),'sha256':sha(z),'option_cards':186}for z in [p,sellpath]],'source_price_check':{'path':str(sourceprice),'sha256':sha(sourceprice)},'commercial_field_changes_by_root':370,'working_estimated_prices':185,'specific_owner_commercial_exception':1}
write=lambda p,x:Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
write(H/'capture-and-specification-verification.json',manifest)
write(OUT/'current-count-summary.json',{'status':'VERIFIED_CURRENT_WORKING_COUNT_DATA','current_working_component_identities':112,'current_individual_options':186,'working_field_rows':1116,'individual_gaps':19,'separate_individual_photos_required':18,'deferred_identity':1,'in_situ_gaps':61,'series_gaps':18,'physical_stock_quantity':None,'physical_mould_count':None,'current_option_list':csvs[0]})
print(json.dumps({k:manifest[k]for k in ['status','current_options','qualified_field_rows','combined_required_option_rows','individual_photographs_required','new_acceptable_image_roles_closed']}))
