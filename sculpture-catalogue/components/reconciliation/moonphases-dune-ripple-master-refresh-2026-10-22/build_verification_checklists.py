"""Create linked capture and physical-verification checklists from qualified records."""
import collections,csv,hashlib,html,json,re
from pathlib import Path
from datetime import datetime,timezone
from html.parser import HTMLParser
H=Path(__file__).resolve().parent;BASE=H.parents[2];OUT=BASE/'outputs/moonphases-dune-ripple-master-refresh-2026-10-22'
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
indids={x['option_id']for x in tasks if x['role']=='Individual'and x['action_type']=='Find / capture'};assert len(indids)==21
capture=[r for r in rows if r['option_id']in byoption];capture.sort(key=lambda x:(x['option_id']not in indids,x['family'],x['name']))
csvs=[csvfile('Current_Individual_Options_186.csv',rows),csvfile('Specification_Verification_Checklist_1116_Fields.csv',specrows),csvfile('Combined_Shoot_and_Measure_Checklist.csv',capture),csvfile('Separate_Individual_Photographs_Required_21.csv',[x for x in capture if x['option_id']in indids])]
def link(url,label):return'<a href="'+esc(url)+'" target="_blank" rel="noopener">'+esc(label)+'</a>'
parts=[]
for r in rows:
 cells=[]
 for z in [x for x in specrows if x['option_id']==r['option_id']]:
  cells.append('<tr><th>'+esc(z['field'])+'</th><td>'+esc(z['working_description'])+'<details><summary>Recorded state and source basis</summary><p>'+esc(z['recorded_review_state'])+'</p><p>'+esc(z['recorded_basis'])+'</p></details></td><td>'+esc(z['verification_action'])+'</td></tr>')
 parts.append('<article data-search="'+esc(' '.join(str(v)for v in r.values()).lower())+'"><h2>'+esc(r['name'])+'</h2><p>'+link(r['individual_image'],'Dropbox example image')+' · '+link(r['containing_folder'],'Containing folder')+'</p><p>Photograph gaps: '+esc(r['required_picture_roles']or'None in the required-image queue')+'</p><table><thead><tr><th>Specification</th><th>Current qualified working detail</th><th>Verification action</th></tr></thead><tbody>'+''.join(cells)+'</tbody></table><details><summary>Stable IDs</summary>'+esc(r['option_id'])+'<br>'+esc(r['component_id'])+'<br>'+esc(r['file_id'])+'<br>'+esc(r['folder_id'])+'</details></article>')
css='body{font:16px/1.5 Arial,sans-serif;background:#f5f6f3;color:#28362d;margin:0}main{max-width:1250px;padding:24px;margin:auto}article{background:#fff;border:1px solid #d8ded4;margin:22px 0;padding:20px}h1,h2{color:#344e40}a{color:#245f7a}table{border-collapse:collapse;width:100%;table-layout:fixed}th,td{border:1px solid #d8ded4;text-align:left;vertical-align:top;padding:12px;overflow-wrap:anywhere}th:first-child{width:16%}thead th{background:#344e40;color:white}details{font-size:13px;margin-top:10px;color:#64705f}input{font:inherit;padding:10px;width:80%;max-width:650px}.hide{display:none}.toolbar{position:sticky;top:0;background:#f5f6f3;padding:12px 0}@media(max-width:700px){table,thead,tbody,tr,th,td{display:block;width:auto!important}thead{display:none}main{padding:12px}}'
js="const q=document.querySelector('#search');function f(){let n=0;document.querySelectorAll('article').forEach(x=>{const on=x.dataset.search.includes(q.value.toLowerCase());x.classList.toggle('hide',!on);if(on)n++});document.querySelector('#shown').textContent=n+' sculpture options shown'}q.addEventListener('input',f);f();"
intro='<h1>Individual sculpture specifications: verification checklist</h1><p>186 current options across 112 working component identities. This checklist preserves accepted values, estimates, guesses and owner policies. It records what a physical check or a current commercial decision would establish; it is not a claim of 1,116 newly missing specifications.</p><p>The owner explicitly confirmed the labelled Fingerprint working table. Its proposal/estimate/guess labels remain. No physical measurements or weighed results were supplied in this pass. The supplied four price PDFs and fourteen page images are unchanged; dated retail/trade figures retain their separate units and source qualifications.</p><p>There are 21 separate individual photographs to obtain and one deferred Frozen Fish identity. Crops were declined. Current Frozen Fish remain 70 × 15 cm. The other required photograph gaps are 61 in situ and 18 series references.</p><p><a href="Combined_Shoot_and_Measure_Checklist.csv">Combined shoot/measure checklist</a> · <a href="Separate_Individual_Photographs_Required_21.csv">21 individual-photo requests</a> · <a href="Specification_Verification_Checklist_1116_Fields.csv">All field checks CSV</a> · <a href="individual-images.html">Linked photograph examples</a></p><div class="toolbar"><input id="search" type="search" placeholder="Search sculpture, finish or specification" aria-label="Search sculpture"><p id="shown"></p></div>'
p=OUT/'specifications-to-verify.html';p.write_text('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Individual sculpture specification checks</title><style>'+css+'</style></head><body><main>'+intro+''.join(parts)+'</main><script>'+js+'</script></body></html>')
class Parser(HTMLParser):
 def __init__(self):super().__init__();self.articles=0;self.hrefs=[]
 def handle_starttag(self,t,attrs):
  d=dict(attrs)
  if t=='article':self.articles+=1
  if t=='a':self.hrefs.append(d['href'])
parser=Parser();parser.feed(p.read_text());assert parser.articles==186 and all(u.startswith('https://www.dropbox.com/')or(OUT/u).is_file()for u in parser.hrefs)
files=[x for p0 in sorted((H/'native-wall-scan').glob('page-*.json'))for x in read(p0)['entries']if x and x['object_type']=='file'];oldassets=read(H/'inputs/report_assets.before')
new=[x for x in files if x['file_id']not in oldassets];assert len(new)==40 and all(any('/'+family+'/'in x['path']for family in ['Fingerprint','Lava Moon','Gleneagles Vine and Tendril'])for x in new)
after=[x for x in files if x.get('modified_time','')>read(H/'inputs/audit.before')['recorded_utc']];deco=read(H/'inputs/deco_overlay.before');changeddeco={x['file_id']for x in deco['objects']if x['object_type']=='file'and x['old_path']!=x['current_path']};assert {x['file_id']for x in after}==changeddeco and len(after)==55
manifest={'status':'PASS_QUALIFIED_CAPTURE_AND_SPECIFICATION_CHECKLISTS','recorded_utc':datetime.now(timezone.utc).isoformat(),'current_options':186,'working_component_identities':112,'qualified_field_rows':1116,'individual_photographs_required':21,'deferred_identity_records':1,'combined_required_option_rows':len(capture),'in_situ_gaps':61,'series_gaps':18,'new_acceptable_image_roles_closed':0,'cropped_images_created':0,'new_physical_measurements_or_weighed_results_added':0,
 'current_wall_scan':read(H/'native-wall-scan/manifest.json'),'forty_files_new_to_older_asset_index':'Previously verified Fingerprint sources and qualified Gleneagles/Lava candidates only; no additional gap-eligible source identified.',
 'fiftyfive_modified_native_files':'Exactly the preserved files in three approved Deco folder changes; stable IDs, sizes and actual file parents verified.',
 'csv_files':csvs,'pages':[{'path':str(p),'sha256':sha(p),'option_cards':186}],'source_price_check':{'path':str(H/'current-price-source-text-check.json'),'sha256':sha(H/'current-price-source-text-check.json')},'commercial_field_changes_by_root':0}
write=lambda p,x:Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
write(H/'capture-and-specification-verification.json',manifest)
write(OUT/'current-count-summary.json',{'status':'VERIFIED_CURRENT_WORKING_COUNT_DATA','current_working_component_identities':112,'current_individual_options':186,'working_field_rows':1116,'individual_gaps':22,'separate_individual_photos_required':21,'deferred_identity':1,'in_situ_gaps':61,'series_gaps':18,'physical_stock_quantity':None,'physical_mould_count':None,'current_option_list':csvs[0]})
print(json.dumps({k:manifest[k]for k in ['status','current_options','qualified_field_rows','combined_required_option_rows','individual_photographs_required','new_acceptable_image_roles_closed']}))
