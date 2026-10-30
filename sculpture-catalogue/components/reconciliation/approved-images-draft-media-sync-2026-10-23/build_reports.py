"""Current linked option, photograph and specification views from one register."""
import collections,csv,hashlib,html,json,shutil
from pathlib import Path
from html.parser import HTMLParser
from datetime import datetime,timezone
H=Path(__file__).resolve().parent;B=H.parents[2];OUT=B/'outputs/approved-images-draft-media-sync-2026-10-23';OUT.mkdir(exist_ok=True);(OUT/'images').mkdir(exist_ok=True)
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();esc=lambda z:html.escape(str(z),quote=True)
def write(p,z):Path(p).write_text(json.dumps(z,ensure_ascii=False,indent=2)+'\n')
g=read(H/'canonical-master-register.json');a=read(H/'image-coverage-current.json');old=read(H/'inputs/master_register.before');assets=read(H/'current-assets.json');cmap={x['option_id']:x for x in a['coverage']};opts={x['product_id']:x for x in g['options']};oldmap={x['product_id']:x for x in old['options']};fields=list(next(iter(opts.values()))['master_fields']);pages=[];csvs=[];copied={}
def link(url,label):return'<a href="'+esc(url)+'" target="_blank" rel="noopener">'+esc(label)+'</a>'if url else esc(label+' unavailable')
def image_url(r):return r.get('archived_original')or r.get('image_url','')
def folder_url(r):return r.get('current_family_navigation_url')or r.get('folder_url','')
def reflinks(r):return link(image_url(r),'Archived original'if r.get('archived_original')else'Dropbox image')+' · '+link(folder_url(r),'Current family navigation'if r.get('archived_original')else'Containing folder')
def thumb(r):
 fid=r.get('file_id');src=assets.get(fid,{}).get('thumb')or r.get('archived_original')
 if not src or not Path(src).is_file():return''
 if fid not in copied:
  target=OUT/'images'/(hashlib.sha256(fid.encode()).hexdigest()+Path(src).suffix.lower());shutil.copy2(src,target);assert sha(src)==sha(target);copied[fid]={'path':str(target),'sha256':sha(target),'file_id':fid,'relative_path':str(target.relative_to(OUT))}
 return'<a href="'+esc(image_url(r))+'"><img src="'+esc(copied[fid]['relative_path'])+'" alt="'+esc(r.get('name','Sculpture reference'))+'" loading="lazy"></a>'
css='body{font:16px/1.5 Arial,sans-serif;color:#28362d;background:#f5f6f3;margin:0}main{max-width:1250px;margin:auto;padding:25px}article,section{background:white;border:1px solid #d8ded4;padding:20px;margin:20px 0}h1,h2{color:#344e40}h2{font-size:21px}a{color:#245f7a}img{width:245px;height:245px;object-fit:contain;background:#f8f8f8}table{border-collapse:collapse;width:100%;table-layout:fixed}td,th{padding:10px;border:1px solid #d8ded4;text-align:left;vertical-align:top;overflow-wrap:anywhere}th{width:21%;background:#eef1ec}details,small{font-size:13px;color:#64705f}nav{padding:14px 0;border-bottom:1px solid #ced5cb}input{font:inherit;width:80%;padding:10px}.hide{display:none}.toolbar{position:sticky;top:0;background:#f5f6f3;padding:12px 0}'
nav='<nav>'+ ' · '.join(link(f,n)for f,n in [('index.html','Current actions'),('individual-images.html','6 individual/identity entries'),('accepted-listing-references.html','Accepted qualified references'),('completed-changes.html','Completed changes and links'),('in-situ-images.html','63 in situ gaps'),('series-images.html','18 series gaps'),('specifications-to-verify.html','Specifications'),('selling-details.html','Working prices')])+'</nav>'
intro='<p>188 current finish/size options across 112 working component identities. Seven complete individual images imported; five group or combined references accepted by scoped owner exception. Six individual actions remain: five separate photographs and one deferred Frozen Fish identity. Technical individual-image coverage still has eleven gaps, including those five accepted exceptions. Wider context still needs 63 in situ and 18 series images. Current Frozen Fish remain 70 × 15 cm. Acanthus detail and workshop originals are restored with their original file IDs and a new actual containing-folder ID. Estimates retain their labels; no new physical measurements or platform matches are certified.</p>'
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
assert[len(actions),len(openrows),len(individual),len(insitu),len(series),len(checks),len(resolved),len(optional)]==[208,87,6,63,18,1,67,54]
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
capture=[x for x in optionrows if byoption[x['option_id']]];csvfile('Combined_Shoot_and_Measure_Checklist.csv',capture);captureids={x['option_id']for x in individual if x['action_type']=='Find / capture'};assert len(captureids)==5;csvfile('Separate_Individual_Photographs_Required_5.csv',[x for x in optionrows if x['option_id']in captureids])
page('specifications-to-verify.html','Qualified working specifications and physical checks',''.join(spec_cards),188);page('selling-details.html','Working individual prices and availability',''.join(sell_cards),188)
refresh=read(H/'preparation-verification.json');cross=read(H/'native-current-crosswalk.json');scope=read(H/'scope.json');cards=[];acceptedrows=[]
for oid in refresh['owner_accepted_qualified_reference_exceptions']:
 x=opts[oid];approval=x['owner_accepted_listing_references'];refs=approval['references'];body=''
 for r in refs:
  rr=r['reference'];body+='<p><strong>'+esc(r.get('display_label',r['role']))+'</strong> '+esc(r.get('target_member_position',''))+'</p>'+thumb(rr)+'<p>'+reflinks(rr)+'</p>'
 cards.append('<article id="'+esc(oid)+'"><h2>'+esc(x['name'])+'</h2><p>Owner accepts these listing references. Technical '+esc(cmap[oid]['individual']['status'])+' remains; a complete separate photograph of this exact option is not verified.</p>'+body+'<p>'+esc(approval['basis'])+'</p><small>'+esc(oid)+'</small></article>');acceptedrows.append({'option_id':oid,'name':x['name'],'technical_individual_status':cmap[oid]['individual']['status'],'owner_accepted_listing_reference':True,'separate_photo_request':'Closed by scoped owner exception','reference_roles':json.dumps(refs,ensure_ascii=False)})
page('accepted-listing-references.html','Accepted group and combined listing references',''.join(cards),len(cards));csvfile('Owner_Accepted_Qualified_Listing_References.csv',acceptedrows)
cards=[]
for oid in refresh['complete_individual_images_added']:
 x=opts[oid];rr=cmap[oid]['individual']['reference'];cards.append('<article><h2>'+esc(x['name'])+'</h2>'+thumb(rr)+'<p>'+reflinks(rr)+'</p><p>'+esc(cmap[oid]['individual']['basis'])+'</p><small>'+esc(oid+' / '+rr['file_id']+' / '+rr['folder_id'])+'</small></article>')
page('approved-individual-images.html','Seven approved complete individual images',''.join(cards),7)
cards=[]
for oid in ['BSI-3635E3DC3434','BSI-449C4421ABD0','BSI-1774B82C6518']:
 x=opts[oid];rr=cmap[oid]['individual']['reference'];table=''.join('<tr><th>'+esc(f)+'</th><td>'+esc(v['display'])+'</td></tr>'for f,v in x['master_fields'].items());cards.append('<article><h2>'+esc(x['name'])+'</h2>'+thumb(rr)+'<p>'+reflinks(rr)+'</p><p>'+('The owner explicitly accepted these six qualified working details for One Leaf only.'if oid=='BSI-3635E3DC3434'else'This option retains its own comparator estimates and standing policies. The One Leaf table was not transferred.')+'</p><table>'+table+'</table></article>')
page('pewter-review.html','Current Pewter options and scoped working details',''.join(cards),3)
cards=[]
for name,p in scope['overlays'].items():
 o=read(p);maps=o['prefix_maps'];text=''.join('<p>'+esc(z['old_name'])+' → '+link(z.get('current_native_url',''),'Current folder: '+z['current_name'])+'<br><small>'+esc(z['file_id'])+'</small></p>'for z in maps)
 if o.get('specific_file_maps'):text+='<h3>Per-file containing folders override the old pair-folder name</h3>'+''.join('<p>'+link(z['current_native_url'],z['name'])+' · '+esc(z['current_parent_id'])+'</p>'for z in o['specific_file_maps'])
 cards.append('<article><h2>'+esc(name.replace('-',' ').title())+'</h2>'+text+'<p>Stable original file and folder IDs retained. Current actual parent IDs verified. Historical names and source qualifications preserved.</p></article>')
repair='<article><h2>Acanthus restored originals</h2><p>The checked family parent is still named Acanthus Two Leaves Pewter. Its family ID remains id:cnqzTNngPVsAAAAAAAt_GA; the catalogue family remains Acanthus.</p>'
for z in cross['restored_sources']:
 rr=next(v['reference']for v in [cmap['BSI-C41824131174']['individual'],cmap['BSI-C41824131174']['series']]if v.get('reference',{}).get('file_id')==z['file_id'])if any(v.get('reference',{}).get('file_id')==z['file_id']for v in [cmap['BSI-C41824131174']['individual'],cmap['BSI-C41824131174']['series']])else None
 obj=cross['current_objects'][z['file_id']]
 from urllib.parse import quote
 rr=rr or{'file_id':z['file_id'],'name':obj['name'],'image_url':'https://www.dropbox.com/preview'+quote(obj['display_path'],safe='/'),'folder_url':'https://www.dropbox.com/home'+quote(str(Path(obj['display_path']).parent),safe='/')}
 repair+=thumb(rr)+'<p>'+reflinks(rr)+'</p><p>Original file ID '+esc(z['file_id'])+' restored with byte-identical archived contents. Actual parent '+esc(z['current_parent_id'])+' replaces historical deleted parent '+esc(z['historical_parent_id'])+'.</p>'
repair+='<p>Only the two named file revisions were restored. The 95 pre-existing Acanthus descendants were unchanged. Reversal would remove those two restored files after separate explicit deletion confirmation; the recreated folder could be removed only once verified empty and separately approved. '+link('https://help.dropbox.com/delete-restore/recover-older-versions','Dropbox version recovery help')+'</p></article>';cards.append(repair)
page('completed-changes.html','Completed folder refreshes and restored Acanthus sources',''.join(cards),len(cards))
actual=[]
for x in optionrows:actual.append({**{k:x[k]for k in ['option_id','component_id','name','family','individual_image','containing_folder','file_id','folder_id']},'current_working_dimensions':x['Dimensions / depth'],'current_working_weight':x['Weight'],'current_working_material':x['Material / finish'],'current_offered_fixing':x['Fixing'],'actual_width_cm':'','actual_height_cm':'','actual_maximum_depth_cm':'','bare_panel_measured_weight_kg':'','maker_material_recipe':'','fitted_fixing_type':'','fitted_fixing_count':'','measured_or_inspected_by':'','measurement_date':'','measurement_method':'','object_or_batch_reference':'','supporting_evidence_reference':'','verification_status':'Awaiting object-specific measurement or maker evidence'})
csvfile('Physical_Verification_Input_188_Options.csv',actual)
count={'status':'VERIFIED_CURRENT_WORKING_COUNT_DATA','current_working_component_identities':112,'current_individual_options':188,'working_field_rows':1128,'individual_gaps':6,'technical_individual_gaps':11,'owner_accepted_reference_exceptions':5,'separate_individual_photos_required':5,'deferred_identity':1,'in_situ_gaps':63,'series_gaps':18,'physical_stock_quantity':None,'physical_mould_count':None,'current_option_list':optioncsv};write(OUT/'current-count-summary.json',count)
class Parser(HTMLParser):
 def __init__(self):super().__init__();self.hrefs=[];self.images=[];self.cards=0
 def handle_starttag(self,t,attrs):
  d=dict(attrs)
  if t=='a':self.hrefs.append(d.get('href',''))
  if t=='img':self.images.append(d.get('src',''))
  if t=='article':self.cards+=1
for p in pages:
 z=Parser();z.feed(Path(p['path']).read_text());assert z.cards==p['cards'];assert all(u and(u.startswith('https://')or Path(u.split('#')[0]).is_file()or(OUT/u.split('#')[0]).is_file())for u in z.hrefs);assert all((OUT/u).is_file()for u in z.images)
manifest={'status':'PASS_CURRENT_LINKED_REPORTS','recorded_utc':datetime.now(timezone.utc).isoformat(),'output_directory':str(OUT),'pages':pages,'csv_files':csvs,'thumbnail_files':list(copied.values()),'counts':{'current_options':188,'working_component_identities':112,'qualified_field_rows':1128,'required_actions':87,'find_capture':86,'existing_image_checks':1,'individual_gaps':6,'technical_individual_gaps':11,'owner_accepted_reference_exceptions':5,'separate_individual_photos_required':5,'in_situ_gaps':63,'series_gaps':18,'resolved_actions':67,'optional':54,'combined_required_option_rows':len(capture),'new_individual_roles_closed':7,'new_owner_reference_exceptions':5,'new_finish_options':0,'archived_native_files_not_found':0,'restored_original_file_ids':2,'new_physical_verifications':0},'register_sha256':sha(H/'canonical-master-register.json'),'audit_sha256':sha(H/'image-coverage-current.json'),'pixels_edited':False,'native_file_revision_restores':2,'native_parent_folder_renames':0};write(H/'report-verification.json',manifest)
print(json.dumps({'status':manifest['status'],'counts':manifest['counts']}))
