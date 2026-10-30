"""Read-only comparison tables from the published, qualified source observation."""
import csv,hashlib,html,json
from pathlib import Path
from urllib.parse import quote
H=Path(__file__).resolve().parent;B=H.parents[1]/'sculpture-catalogue'
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();esc=lambda v:html.escape(str(v),quote=True)
p=read(B/'current-master.json');assert sha(B/p['register'])==p['register_sha256'];g=read(B/p['register']);obs=g['current_authenticated_squarespace_inventory_observation'];opts={o['product_id']:o for o in g['options']};pairs=obs['historical_shopify_comparison']['pairs'];keys={(x['fresh_squarespace_variant']['product_id'],x['fresh_squarespace_variant']['sku_raw'])for x in pairs}
anti=[x for x in obs['retained_offer_observations']if(x['observed_native_source_tuple']['product_id'],x['observed_native_source_tuple']['sku_raw'])not in keys];assert len(pairs)==len(keys)==37 and len(anti)==43
rows=[];cards=[]
for x in anti:
 t=x['observed_native_source_tuple'];title=next(f['current_csv_value_raw']for f in x['fields']if f['field']=='Title');related=[opts[i]for i in x['existing_related_option_ids']];row={'offer_ref':x['offer_ref'],'squarespace_product_id':t['product_id'],'squarespace_variant_id':t['variant_id'],'source_sku_raw':t['sku_raw'],'source_title':title,'source_capture_utc':obs['squarespace_source_clock']['captured_utc'],'documented_historical_shopify_pair':False,'current_shopify_inventory_verified':False,'current_absence_inferred':False,'related_option_ids':'\n'.join(o['product_id']for o in related),'related_option_names':'\n'.join(o['name']for o in related),'catalogue_images':'\n'.join(o.get('image_url','')for o in related),'containing_folders':'\n'.join(o.get('folder_url','')for o in related),'dropbox_file_ids':'\n'.join(o.get('file_id')or''for o in related),'dropbox_folder_ids':'\n'.join(o.get('folder_id')or''for o in related),'association_scope':'Existing qualified source relationships only; no new exact individual configuration match'};rows.append(row)
 row['related_primary_navigation_status']='\n'.join(o.get('current_primary_navigation',{}).get('status','See scoped native-navigation review; unchecked options are not newly verified')for o in related)
 row['related_working_design_group_ids']='\n'.join(g.get('current_working_design_group_projection',{}).get('component_id_to_working_group',{}).get(o.get('canonical_component_id'),'')for o in related)
 links=''
 for o in related:
  if not o.get('image_url'):continue
  nav=o.get('current_primary_navigation',{});deleted=nav.get('deletion_observed_in_exact_id_history',False);label='Historical Dropbox image (deleted)'if deleted else'Saved image (unverified)'if nav and not nav.get('current_primary_verified')else'Image'
  links+='<p>'+esc(o['name'])+': <a href="'+esc(o['image_url'])+'">'+label+'</a> · <a href="'+esc(o['folder_url'])+'">Containing folder</a>'
  if deleted:links+=' · <a href="'+esc(nav['existing_local_historical_original']['path'])+'">Open exact local historical original</a>'
  links+='</p>'
 cards.append('<article><h2>'+esc(x['offer_ref'])+' '+esc(title)+'</h2><p>Captured Squarespace source SKU '+esc(t['sku_raw'])+'. No documented pair in the retained historical Shopify wall-source comparison. Current Shopify absence is not inferred.</p>'+links+'</article>')
def outcsv(name,data):
 f=H/name
 with f.open('w',encoding='utf-8-sig',newline='')as s:w=csv.DictWriter(s,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
 return f
ss=outcsv('Squarespace_Source_Offers_Without_Historical_Shopify_Pair_43.csv',rows)
draft=next(x['source_offer']for x in g['source_offer_edges']if x['offer_ref']=='SH-DRAFT')
native=read(B/p['current_native_reference_map']['path']);family=next(x for x in native['current_objects'].values()if x.get('object_type')=='folder'and x.get('path','').endswith('/Frozen Fish'));family_url='https://www.dropbox.com/home'+quote(family['display_path'],safe='/')
sh=outcsv('Historical_Shopify_Unpaired_Draft_1.csv',[{'offer_ref':'SH-DRAFT','historical_shopify_handle':draft.get('sh_handle',''),'historical_title':draft.get('title',''),'historical_sku_raw':draft.get('sku',''),'documented_squarespace_pair':False,'current_shopify_inventory_verified':False,'current_squarespace_absence_inferred':False,'identity_status':'Existing Frozen Fish legacy identity deferred','current_frozen_fish_face':'70 cm high ×15 cm wide; standing owner policy','family_review_folder':family_url,'family_folder_id':family['file_id'],'exact_individual_image':'Unconfirmed; do not assign a candidate as an exact draft match','scope':'Retained historical wall-source draft only; no new exact identity or physical claim'}])
cards.append('<article><h2>SH-DRAFT Frozen Fish</h2><p>Historical blank-SKU draft. Exact identity remains deferred; current Frozen Fish face remains70cm high by15cm wide.</p><p><a href="'+esc(family_url)+'">Frozen Fish family review folder</a>. No exact individual image assigned to the draft by this comparison.</p></article>')
review=B/p['current_authenticated_squarespace_inventory_observation']['review'];matched=review.parent/'Historical_Shopify_Current_Squarespace_Source_Pairs_37.csv';assert matched.is_file()
page=H/'source-comparison.html';page.write_text('<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Platform source comparison</title><style>body{font:17px Arial;line-height:1.5;max-width:1000px;margin:40px auto;padding:0 20px}article{border-top:1px solid #aaa;margin-top:25px;padding-top:12px}</style></head><body><h1>Platform source comparison</h1><p>Within the retained wall-sculpture source set:37 documented pairs,43 Squarespace source offers without a historical Shopify pair, and one unpaired historical Shopify draft. This compares80 retained Squarespace source records with the historical Shopify wall-source subset. It does not establish present-day Shopify absence or an exact individual sculpture configuration.</p><ul><li><a href="'+esc(matched)+'">Download37 documented source pairs</a></li><li><a href="'+ss.name+'">Download43 unpaired Squarespace source offers</a></li><li><a href="'+sh.name+'">Download one unpaired historical Shopify draft</a></li><li><a href="'+esc(review)+'">Full captured-source observations and qualifications</a></li></ul><p>Source capture: '+esc(obs['squarespace_source_clock']['captured_utc'])+'. Current catalogue image links below retain their existing qualified relationship scope.</p>'+''.join(cards)+'</body></html>')
if p.get('current_primary_navigation_health'):
 health=B/p['current_primary_navigation_health']['review'];wording='2 saved primaries marked deleted in available history'if p['current_primary_navigation_health'].get('saved_primary_ids_marked_deleted_in_available_history')else'2 selected references unresolved';page.write_text(page.read_text().replace('</ul>','<li><a href="'+esc(health)+'">Scoped48-option Dropbox image/folder health:46 files verified;'+wording+'</a></li></ul>',1))
if p.get('current_working_design_group_projection'):
 design=B/p['current_working_design_group_projection']['review'];page.write_text(page.read_text().replace('</ul>','<li><a href="'+esc(design)+'">Both owner-confirmed Decowaves design relationships; no new platform match or specification transfer</a></li></ul>',1))
if (H/'ready-source-triage.json').is_file():
 ready=read(H/'ready-source-triage.json')
 if ready['baseline_register_sha256']==p['register_sha256'] and sha(ready['review'])==ready['review_sha256']:
  link='<li><a href="'+esc(ready['review'])+'">Prepared next comparison for each of the43 unpaired source records</a></li>'
  page.write_text(page.read_text().replace('</ul>',link+'</ul>',1))
receipt={'status':'PASS_READ_ONLY_SNAPSHOT_COMPARISON','register_sha256':p['register_sha256'],'workbook_sha256':p['workbook_sha256'],'counts':{'retained_squarespace_source_records':80,'documented_pairs':37,'unpaired_squarespace_source_records':43,'unpaired_historical_shopify_draft':1},'current_shopify_inventory_verified':False,'new_configuration_or_physical_matches':0,'files':{str(x):sha(x)for x in [page,ss,sh,matched]}}
(H/'source-comparison-readback.json').write_text(json.dumps(receipt,indent=2)+'\n');assert sha(B/p['register'])==p['register_sha256'];print(json.dumps({'status':receipt['status'],'counts':receipt['counts']}))
