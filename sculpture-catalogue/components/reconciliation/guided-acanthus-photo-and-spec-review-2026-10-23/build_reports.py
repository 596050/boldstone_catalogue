"""Current linked option, photograph and specification views from one register."""
import collections,csv,hashlib,html,json,shutil
from pathlib import Path
from html.parser import HTMLParser
from datetime import datetime,timezone
H=Path(__file__).resolve().parent;B=H.parents[2];OUT=B/'outputs/guided-acanthus-photo-and-spec-review-2026-10-23';OUT.mkdir(exist_ok=True);(OUT/'images').mkdir(exist_ok=True)
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();esc=lambda z:html.escape(str(z),quote=True)
def write(p,z):Path(p).write_text(json.dumps(z,ensure_ascii=False,indent=2)+'\n')
g=read(H/'canonical-master-register.json');a=read(H/'image-coverage-current.json');old=read(H/'inputs/master_register.before');assets=read(H/'current-assets.json');cmap={x['option_id']:x for x in a['coverage']};opts={x['product_id']:x for x in g['options']};oldmap={x['product_id']:x for x in old['options']};fields=list(next(iter(opts.values()))['master_fields']);pages=[];csvs=[];copied={}
def link(url,label):return'<a href="'+esc(url)+'" target="_blank" rel="noopener">'+esc(label)+'</a>'if url else esc(label+' unavailable')
def image_url(r):return r.get('image_url','')
def folder_url(r):return r.get('current_family_navigation_url')or r.get('folder_url','')
def reflinks(r):return link(image_url(r),'Dropbox image')+' · '+link(folder_url(r),'Master family navigation'if r.get('current_family_navigation_url')else'Containing folder')
def thumb(r):
 fid=r.get('file_id');src=assets.get(fid,{}).get('thumb')
 if not src or not Path(src).is_file():return''
 if fid not in copied:
  target=OUT/'images'/(hashlib.sha256(fid.encode()).hexdigest()+Path(src).suffix.lower());shutil.copy2(src,target);assert sha(src)==sha(target);copied[fid]={'path':str(target),'sha256':sha(target),'file_id':fid,'relative_path':str(target.relative_to(OUT))}
 return'<a href="'+esc(image_url(r))+'"><img src="'+esc(copied[fid]['relative_path'])+'" alt="'+esc(r.get('name','Sculpture reference'))+'" loading="lazy"></a>'
css='body{font:16px/1.5 Arial,sans-serif;color:#28362d;background:#f5f6f3;margin:0}main{max-width:1250px;margin:auto;padding:25px}article,section{background:white;border:1px solid #d8ded4;padding:20px;margin:20px 0}h1,h2{color:#344e40}h2{font-size:21px}a{color:#245f7a}img{width:245px;height:245px;object-fit:contain;background:#f8f8f8}table{border-collapse:collapse;width:100%;table-layout:fixed}td,th{padding:10px;border:1px solid #d8ded4;text-align:left;vertical-align:top;overflow-wrap:anywhere}th{width:21%;background:#eef1ec}details,small{font-size:13px;color:#64705f}nav{padding:14px 0;border-bottom:1px solid #ced5cb}input{font:inherit;width:80%;padding:10px}.hide{display:none}.toolbar{position:sticky;top:0;background:#f5f6f3;padding:12px 0}'
nav='<nav>'+ ' · '.join(link(f,n)for f,n in [('index.html','Current actions'),('individual-images.html','2 individual/identity entries'),('accepted-listing-references.html','Accepted qualified references'),('imported-approvals.html','New context image bindings'),('in-situ-images.html','50 in situ gaps'),('series-images.html','18 series gaps'),('specifications-to-verify.html','Specifications'),('selling-details.html','Working prices')])+'</nav>'
intro='<p>Current image evidence uses BOLDSTONE MASTER only.188 individual finish/size options across112 working component identities retain their specifications and working values. Fountain Palm082 is a qualified owner-designated display context;14 existing files have verified current containing folders. The photograph shows a display board, with no authenticated permanent installation claim. Acanthus Two Leaves — Bronze uses the owner-approved RIGHT-HAND SQUARE PANEL in the courtyard photograph; the other panel stays context. Acanthus brochure conflicts are recorded separately; no physical values are upgraded. Current gaps:2 individual/identity entries,50 in situ and18 series. Sandstone needs a current Master photograph; existing deferrals remain in force.</p>'
def page(name,title,body,count):
 p=OUT/name;js="const q=document.querySelector('#search');if(q)q.addEventListener('input',()=>document.querySelectorAll('article').forEach(x=>x.classList.toggle('hide',!x.textContent.toLowerCase().includes(q.value.toLowerCase()))));"
 p.write_text('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+esc(title)+'</title><style>'+css+'</style></head><body><main><h1>'+esc(title)+'</h1>'+intro+nav+'<div class="toolbar"><input id="search" type="search" placeholder="Search sculpture, finish or specification" aria-label="Search"></div>'+body+'</main><script>'+js+'</script></body></html>');pages.append({'path':str(p),'sha256':sha(p),'cards':count})
def csvfile(name,rows):
 p=OUT/name
 with p.open('w',encoding='utf-8-sig',newline='')as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 with p.open(encoding='utf-8-sig',newline='')as f:assert len(list(csv.DictReader(f)))==len(rows)
 z={'path':str(p),'sha256':sha(p),'rows':len(rows)};csvs.append(z);return z
actions=[]
for i,x in enumerate(a['missing_pictures'],1):
 r=x['reference'];actions.append({'sequence':i,'option_id':x['option_id'],'name':x['name'],'role':x['role'],'action_type':x['action_type'],'status':x['status'],'action':x['action'],'qualification':x['qualification'],'image_url':image_url(r),'folder_url':folder_url(r),'file_id':r['file_id'],'folder_id':r['folder_id'],'native_source_status':r.get('native_reference_status','Prior verified reference retained'),'owner_response':x.get('owner_response','')})
openrows=[x for x in actions if x['status']=='Open'];individual=[x for x in openrows if x['role']=='Individual'];insitu=[x for x in openrows if x['role']=='In situ'];series=[x for x in openrows if x['role']=='Series'];checks=[x for x in openrows if x['action_type']=='Verify existing image'];resolved=[x for x in actions if x['status']=='Resolved'];optional=[x for x in actions if x['status']=='Optional']
assert[len(actions),len(openrows),len(individual),len(insitu),len(series),len(checks),len(resolved),len(optional)]==[208,70,2,50,18,1,84,54]
for name,rs in [('All_Current_Picture_Actions.csv',actions),('Missing_Pictures_Required.csv',openrows),('Missing_Individual_Images.csv',individual),('Missing_In_Situ_Images.csv',insitu),('Missing_Series_Images.csv',series),('Existing_Images_to_Check.csv',checks),('Resolved_Image_Associations.csv',resolved),('Optional_Series_Images.csv',optional)]:csvfile(name,rs)
def actioncard(x):
 ref=next(z for z in a['missing_pictures']if z['option_id']==x['option_id']and z['role']==x['role'])['reference']
 return'<article><h2>'+esc(x['name'])+'</h2><p>'+esc(x['role']+' · '+x['status'])+'</p>'+thumb(ref)+'<p>'+reflinks(ref)+'</p><p>'+esc(x['action'])+'</p><p>'+esc(x['qualification'])+'</p><small>'+esc(x['option_id']+' / '+x['file_id']+' / '+x['folder_id'])+'</small></article>'
for name,title,rs in [('index.html','Current photograph and identity actions',openrows),('individual-images.html','Individual image and identity gaps',individual),('in-situ-images.html','Wider in situ photographs to find',insitu),('series-images.html','Series photographs to find',series),('existing-images-to-check.html','Deferred legacy identity',checks),('resolved-image-associations.html','Resolved image actions',resolved)]:page(name,title,''.join(actioncard(x)for x in rs),len(rs))
optionrows=[];specrows=[];selling=[];spec_cards=[];sell_cards=[];byoption=collections.defaultdict(list)
for x in openrows:byoption[x['option_id']].append(x['role'])
for oid,x in opts.items():
 ref=cmap[oid]['individual'].get('reference')or{k:x.get(k,'')for k in ['file_id','folder_id','image_url','folder_url']};r={'option_id':oid,'component_id':x['canonical_component_id'],'name':x['name'],'family':x['family'],**{f:v['display']for f,v in x['master_fields'].items()},'individual_photo_status':cmap[oid]['individual']['status'],'listing_reference_disposition':x.get('owner_image_review_disposition','Complete individual reference'if cmap[oid]['individual']['status']=='Available'else'Pending'),'individual_image':image_url(ref),'containing_folder':folder_url(ref),'file_id':ref.get('file_id',''),'folder_id':ref.get('folder_id',''),'required_picture_roles':'; '.join(byoption[oid]),'physical_specs_verified':x['physical_specifications_verified'],'native_reference_status':ref.get('native_reference_status','Prior reference retained')};optionrows.append(r);trs=[]
 for f,v in x['master_fields'].items():
  sr={**{k:r[k]for k in ['option_id','component_id','name','family','individual_image','containing_folder','file_id','folder_id']},'field':f,'working_description':v['display'],'review_state':v['state'],'basis':v['basis'],'explicit_owner_confirmation':v.get('explicit_owner_confirmation',{}).get('decision_id',''),'physical_verification':v['physical_verification']};specrows.append(sr);trs.append('<tr><th>'+esc(f)+'</th><td>'+esc(v['display'])+'<details><summary>Recorded state and source basis</summary><p>'+esc(v['state'])+'</p><p>'+esc(v['basis'])+'</p></details></td></tr>')
 card='<article id="'+esc(oid)+'"><h2>'+esc(x['name'])+'</h2><p>'+reflinks(ref)+'</p><p>Required picture work: '+esc(r['required_picture_roles']or'None in this queue')+'</p><p>Physical check: measure width, height and maximum projection in cm; weigh the bare panel in kg; record maker material recipe and inspect the fitted fixing type/count. Keep the current working description until object-specific evidence is recorded. '+link('Physical_Verification_Input_188_Options.csv','Enter actual measurements and evidence')+'</p><table>'+''.join(trs)+'</table><small>'+esc(oid+' / '+str(x['canonical_component_id']))+'</small></article>';spec_cards.append(card)
 s=x['selling_details'];oldprice=oldmap.get(oid,{}).get('master_fields',{}).get('Individual price',{}).get('display','New finish comparator proposal')
 selling.append({**r,'estimated_price_gbp':s['estimated_price'],'estimated_price_upper_gbp':s['estimated_price_upper'],'price_status':s['price_status'],'sale_unit':s['sale_unit'],'lead_time_min_weeks':s['lead_time_min_weeks'],'lead_time_max_weeks':s['lead_time_max_weeks'],'earlier_working_price':oldprice,'physical_stock_quantity':None});sell_cards.append('<article><h2>'+esc(x['name'])+'</h2><p>'+reflinks(ref)+'</p><p><strong>Price:</strong> '+esc(r['Individual price'])+'</p><p><strong>Availability:</strong> '+esc(r['Availability'])+'</p><details><summary>Price basis</summary>'+esc(x['master_fields']['Individual price']['basis'])+'</details></article>')
assert len(optionrows)==188 and len(specrows)==1128
optioncsv=csvfile('Current_Individual_Options_188.csv',optionrows);csvfile('Specification_Verification_Checklist_1128_Fields.csv',specrows);csvfile('Current_Selling_Details_188.csv',selling)
capture=[x for x in optionrows if byoption[x['option_id']]];csvfile('Combined_Shoot_and_Measure_Checklist.csv',capture);captureids={x['option_id']for x in individual if x['action_type']=='Find / capture'};assert len(captureids)==1;csvfile('Separate_Individual_Photographs_Required_1.csv',[x for x in optionrows if x['option_id']in captureids])
page('specifications-to-verify.html','Qualified working specifications and physical checks',''.join(spec_cards),188);page('selling-details.html','Working individual prices and availability',''.join(sell_cards),188)
refresh=read(H/'preparation-verification.json');cards=[];acceptedrows=[]
for oid in refresh['owner_accepted_qualified_reference_exceptions']:
 x=opts[oid];approval=x['owner_accepted_listing_references'];refs=approval['references'];body=''
 for r in refs:
  rr=r['reference'];body+='<p><strong>'+esc(r.get('display_label',r['role']))+'</strong> '+esc(r.get('target_member_position',''))+'</p>'+thumb(rr)+'<p>'+reflinks(rr)+'</p>'
 cards.append('<article id="'+esc(oid)+'"><h2>'+esc(x['name'])+'</h2><p>Owner accepts these listing references. Technical '+esc(cmap[oid]['individual']['status'])+' remains; a complete separate photograph of this exact option is not verified.</p>'+body+'<p>'+esc(approval['basis'])+'</p><small>'+esc(oid)+'</small></article>');acceptedrows.append({'option_id':oid,'name':x['name'],'technical_individual_status':cmap[oid]['individual']['status'],'owner_accepted_listing_reference':True,'separate_photo_request':'Closed by scoped owner exception','reference_roles':json.dumps(refs,ensure_ascii=False)})
page('accepted-listing-references.html','Accepted group and combined listing references',''.join(cards),len(cards));csvfile('Owner_Accepted_Qualified_Listing_References.csv',acceptedrows)
cards=[]
for oid in refresh['previously_approved_complete_individual_images']:
 x=opts[oid];rr=cmap[oid]['individual']['reference'];cards.append('<article><h2>'+esc(x['name'])+'</h2>'+thumb(rr)+'<p>'+reflinks(rr)+'</p><p>'+esc(cmap[oid]['individual']['basis'])+'</p><small>'+esc(oid+' / '+rr['file_id']+' / '+rr['folder_id'])+'</small></article>')
page('approved-individual-images.html','Previously approved complete individual images',''.join(cards),7)
cards=[]
for oid in ['BSI-3635E3DC3434','BSI-449C4421ABD0','BSI-1774B82C6518']:
 x=opts[oid];rr=cmap[oid]['individual']['reference'];table=''.join('<tr><th>'+esc(f)+'</th><td>'+esc(v['display'])+'</td></tr>'for f,v in x['master_fields'].items());cards.append('<article><h2>'+esc(x['name'])+'</h2>'+thumb(rr)+'<p>'+reflinks(rr)+'</p><p>'+('The owner explicitly accepted these six qualified working details for One Leaf only.'if oid=='BSI-3635E3DC3434'else'This option retains its own comparator estimates and standing policies. The One Leaf table was not transferred.')+'</p><table>'+table+'</table></article>')
page('pewter-review.html','Current Pewter options and scoped working details',''.join(cards),3)
cards=[]
for item in refresh['imported_approvals']:
 body=''
 for role in item['references']:
  rr=role['reference'];body+='<p><strong>'+esc(role.get('display_label',role['role']))+'</strong> '+esc(role.get('target_member_position',''))+'</p>'+thumb(rr)+'<p>'+reflinks(rr)+'</p><small>'+esc(rr['file_id']+' / '+rr['folder_id'])+'</small>'
 cards.append('<article id="'+esc(item['option_id'])+'"><h2>'+esc(item['name'])+'</h2><p>'+esc(item['role'])+' · Technical individual coverage: '+esc(item['technical_individual_status'])+'</p>'+body+'<p>'+esc(item['basis'])+'</p><p>'+(link(item['approval']['path'],'Recorded owner context designation')if item['approval']else'Visual match to the kept individual references; source-qualified series association')+'</p><small>'+esc(item['option_id'])+'</small></article>')
page('imported-approvals.html','Fountain display context and approved Bronze courtyard reference',''.join(cards),len(cards))
foldercards=[]
for name,p in read(H/'scope.json')['overlays'].items():
 d=read(p);body=''.join('<p>'+esc(z['old_name'])+' to '+link(z['current_native_url'],z['current_name'])+'<br><small>'+esc(z['file_id'])+'</small></p>'for z in d['prefix_maps'])
 if d.get('specific_file_maps'):body+='<p>'+str(len(d['specific_file_maps']))+' individually verified file-parent mappings override the old group-folder prefix.</p>'
 foldercards.append('<article><h2>'+esc(name)+'</h2>'+body+'<p>Stable native file IDs retained; source/specification roles unchanged.</p></article>')

foldercards.append('<article><h2>Fountain Palm — Bronze and Verdigris</h2><p>14 existing photographs now have verified containing-folder ID id:cnqzTNngPVsAAAAAAA6Vqw;83 original file IDs retained. Individual image001 remains in its original product folder. No native changes performed by this import.</p></article>')
page('completed-changes.html','Current folder changes and live references',''.join(foldercards),len(foldercards))
ledger=read(H/'context-review-ledger.json');rows=[]
for item in ledger['tasks']:
 rr=item['current_reference'];rows.append('<article><h2>'+esc(item['name'])+' — '+esc(item['role'])+'</h2>'+thumb(rr)+'<p>'+reflinks(rr)+'</p><p>'+esc(item['status_after']+' / '+item['outcome'])+'</p><p>'+esc(item['current_finding'])+'</p><p>'+esc(item.get('review_note',''))+'</p></article>')
page('context-review-walkthrough.html','Individual context-image review outcomes',''.join(rows),len(rows))
csvfile('Individual_Context_Review_Outcomes_78.csv',[{'option_id':x['option_id'],'name':x['name'],'role':x['role'],'outcome':x['outcome'],'status_after':x['status_after'],'qualification':x['current_finding'],'image_url':x['current_reference']['image_url'],'folder_url':x['current_reference']['folder_url'],'file_id':x['current_reference']['file_id'],'folder_id':x['current_reference']['folder_id']}for x in ledger['tasks']])

csvfile('Imported_Context_Image_Bindings_2.csv',[{'option_id':x['option_id'],'name':x['name'],'role':x['role'],'technical_individual_status':x['technical_individual_status'],'qualification':x['basis'],'references_with_stable_ids':json.dumps(x['references'],ensure_ascii=False),'approval_path':x['approval']['path']if x['approval']else'','approval_sha256':x['approval']['sha256']if x['approval']else''}for x in refresh['imported_approvals']])

actual=[]
for x in optionrows:actual.append({**{k:x[k]for k in ['option_id','component_id','name','family','individual_image','containing_folder','file_id','folder_id']},'current_working_dimensions':x['Dimensions / depth'],'current_working_weight':x['Weight'],'current_working_material':x['Material / finish'],'current_offered_fixing':x['Fixing'],'actual_width_cm':'','actual_height_cm':'','actual_maximum_depth_cm':'','bare_panel_measured_weight_kg':'','maker_material_recipe':'','fitted_fixing_type':'','fitted_fixing_count':'','measured_or_inspected_by':'','measurement_date':'','measurement_method':'','object_or_batch_reference':'','supporting_evidence_reference':'','verification_status':'Awaiting object-specific measurement or maker evidence'})
csvfile('Physical_Verification_Input_188_Options.csv',actual)
count={'status':'VERIFIED_CURRENT_WORKING_COUNT_DATA','current_working_component_identities':112,'current_individual_options':188,'working_field_rows':1128,'individual_gaps':2,'technical_individual_gaps':11,'owner_accepted_reference_exceptions':9,'separate_individual_photos_required':1,'deferred_identity':1,'in_situ_gaps':50,'series_gaps':18,'physical_stock_quantity':None,'physical_mould_count':None,'current_option_list':optioncsv};write(OUT/'current-count-summary.json',count)
class Parser(HTMLParser):
 def __init__(self):super().__init__();self.hrefs=[];self.images=[];self.cards=0
 def handle_starttag(self,t,attrs):
  d=dict(attrs)
  if t=='a':self.hrefs.append(d.get('href',''))
  if t=='img':self.images.append(d.get('src',''))
  if t=='article':self.cards+=1
correctioncards=''.join('<article id="'+esc(oid)+'"><h2>'+esc(opts[oid]['name'])+'</h2><p>'+link('https://www.dropbox.com/home/BOLDSTONE%20MASTER/Products/01%20Wall%20Sculptures/Acanthus','Current Master Acanthus folder')+'</p><p>'+esc(g['latest_master_only_source_correction']['scope_note'])+'</p></article>'for oid in ['BSI-C41824131174','BSI-3635E3DC3434'])
page('source-scope-correction.html','Current Master source correction',correctioncards,2)
spec_review=read(H/'specification-evidence-review.json');body='<section><h2>Acanthus brochure evidence</h2><p>'+esc(spec_review['conclusion'])+'</p><table><tr><th>Master source</th><th>Page</th><th>Source claim</th><th>Scope</th></tr>'
for x in spec_review['sources']:
 dp='/' + x['path'].split('//',1)[1].lstrip('/');u='https://www.dropbox.com/preview'+__import__('urllib.parse',fromlist=['quote']).quote(dp,safe='/');body+='<tr><td>'+link(u,Path(dp).name)+'<br><small>'+esc(x['file_id'])+'</small></td><td>2</td><td>30 × 30 cm face; '+str(x['listed_weight_kg'])+' kg</td><td>'+esc(x['scope'])+'</td></tr>'
body+='</table><p>'+esc(spec_review['rear_observation']['visible_fixing']+' '+spec_review['rear_observation']['limits'])+'</p><p>Still pending: Sandstone individual photograph and Sandstone/Pewter series photographs. Bronze Two Leaves courtyard image is approved and imported in this release. Source review is bounded and does not prove global absence.</p></section>'
page('specification-evidence-review.html','Acanthus source evidence and unresolved physical checks',body,0)
for p in pages:
 z=Parser();z.feed(Path(p['path']).read_text());assert z.cards==p['cards'];assert all('BOLDSTONE_BACKUP'not in u.upper() for u in z.hrefs);assert all('/BOLDSTONE%20MASTER/' in u.upper() or '/BOLDSTONE MASTER/' in u.upper() for u in z.hrefs if u.startswith('https://www.dropbox.com/'));assert all(u and(u.startswith('https://')or Path(u.split('#')[0]).is_file()or(OUT/u.split('#')[0]).is_file())for u in z.hrefs);assert all((OUT/u).is_file()for u in z.images)
manifest={'status':'PASS_CURRENT_LINKED_REPORTS','recorded_utc':datetime.now(timezone.utc).isoformat(),'output_directory':str(OUT),'pages':pages,'csv_files':csvs,'thumbnail_files':list(copied.values()),'counts':{'current_options':188,'working_component_identities':112,'qualified_field_rows':1128,'required_actions':70,'find_capture':69,'existing_image_checks':1,'individual_gaps':2,'technical_individual_gaps':11,'owner_accepted_reference_exceptions':9,'separate_individual_photos_required':1,'in_situ_gaps':50,'series_gaps':18,'resolved_actions':84,'optional':54,'combined_required_option_rows':len(capture),'new_individual_roles_closed':0,'new_owner_reference_exceptions':0,'new_finish_options':0,'in_situ_roles_closed':2,'owner_approval_packets_imported':1,'new_series_roles_closed':0,'archived_native_files_not_found':0,'restored_original_file_ids':0,'new_physical_verifications':0},'register_sha256':sha(H/'canonical-master-register.json'),'audit_sha256':sha(H/'image-coverage-current.json'),'pixels_edited':False,'native_file_revision_restores':0,'native_parent_folder_renames':0};write(H/'report-verification.json',manifest)
print(json.dumps({'status':manifest['status'],'counts':manifest['counts']}))
