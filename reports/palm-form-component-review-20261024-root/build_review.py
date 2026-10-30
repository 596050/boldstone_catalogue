"""Record Palm Form source-photo crosswalks and retain qualified component fields."""
import hashlib,html,json,math
from datetime import datetime,timezone
from pathlib import Path
from PIL import Image,ImageOps,ImageChops,ImageStat
H=Path(__file__).resolve().parent;ROOT=H.parents[1];B=ROOT/'sculpture-catalogue'
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
write=lambda p,d:Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
p=read(B/'current-master.json');g=read(B/p['register']);assets=read(B/p['current_asset_reference_map']['path'])
assert sha(B/p['current_asset_reference_map']['path'])==p['current_asset_reference_map']['sha256']
options={o['product_id']:o for o in g['options']};edges={e['offer_ref']:e for e in g['source_offer_edges']}
inventory_path=B/'components/parallel-reviews/listing-resolution-2026-10-21/worker-01/FRESH_PUBLIC_INVENTORY.json'
inventory=read(inventory_path);products={x['native_product_id']:(i,x)for i,x in enumerate(inventory['products'])}
gallery_path=Path('/Users/tprice/Library/Application Support/BoldstoneImageConsistency/product-evidence-resolution-20261016T201618Z/Public_Gallery_References.json')
cached={r['image_url']:r for r in read(gallery_path)['records']}
controls=[B/x for x in ['components/checkpoint.json','checkpoint.json','components/reviews/specification_review_progress.json']]
guards={str(x):sha(x)for x in [B/'current-master.json',B/p['register'],B/p['workbook'],B/p['current_asset_reference_map']['path'],B/p['current_native_reference_map']['path'],*controls]}
for x in controls:assert read(x)['current_master_catalogue']==p
source_records=[];pictures=[];db_by_id={}
for ref in ['O027','O047','O053','O054','O055','O056']:
 edge=edges[ref];index,record=products[edge['source_offer']['sq_id']];variants=record['variants'];assert len(variants)==1
 obs=next(x for x in g['current_authenticated_squarespace_inventory_observation']['retained_offer_observations']if x['offer_ref']==ref)
 assert variants[0]['native_variant_id']==obs['observed_native_source_tuple']['variant_id']
 assert variants[0]['sku']==edge['source_offer']['sku']==obs['observed_native_source_tuple']['sku_raw']
 media=[]
 for j,m in enumerate(record['native_media_items']):
  c=cached.get(m['assetUrl']);x={'native_media_id':m['id'],'gallery_index':j,'url':m['assetUrl'],'caption':m['title'],'cached_rendition_viewed':bool(c)}
  if c:
   assert sha(c['image_path'])==c['image_sha256'] and Path(c['image_path']).stat().st_size==c['bytes']
   x.update(path=c['image_path'],sha256=c['image_sha256'],bytes=c['bytes']);pictures.append({**x,'role':ref+' source frame '+str(j)})
  media.append(x)
 source_records.append({'offer_ref':ref,'source_offer':edge['source_offer'],'source_index':index,'source_locator':record['source_locator'],
  'source_description_text':record['description_text'],'native_product_id':record['native_product_id'],
  'native_variant_id':variants[0]['native_variant_id'],'sku':variants[0]['sku'],
  'native_variant_image_ids':variants[0]['native_image_ids'],'native_variant_attributes':variants[0]['option_attributes'],
  'media':media,'current_reference':edge['current_primary_reference'],
  'historical_shopify_handle':edge['source_offer']['sh_handle']or None,'current_live_shopify_inventory_not_inferred':True,
  'raw_source_and_member_scope_preserved':edge})
 for fid in [edge['current_primary_reference']['file_id']]:
  if fid in db_by_id:continue
  a=assets[fid];assert '/BOLDSTONE MASTER/Products/01 Wall Sculptures/'in a['path'];path=Path(a['thumb']);assert path.is_file()
  d={'file_id':fid,'folder_id':a['folder_id'],'image_url':a['image_url'],'folder_url':a['folder_url'],
   'path':str(path),'sha256':sha(path),'bytes':path.stat().st_size,'role':'Dropbox reference '+a['name'],'cached_rendition_viewed':True}
  db_by_id[fid]=d;pictures.append(d)
assert len(pictures)==15
photo_bindings=[]
for ref,j in [('O027',0),('O053',0),('O054',0),('O055',0),('O056',1)]:
 s=next(x for x in source_records if x['offer_ref']==ref);fid=s['current_reference']['file_id'];source=s['media'][j];db=db_by_id[fid]
 with Image.open(source['path'])as im:a=ImageOps.exif_transpose(im).convert('RGB')
 with Image.open(db['path'])as im:c=ImageOps.exif_transpose(im).convert('RGB')
 size=(256,round(256*c.height/c.width));r=ImageStat.Stat(ImageChops.difference(a.resize(size,Image.Resampling.LANCZOS),c.resize(size,Image.Resampling.LANCZOS))).rms
 rmse=math.sqrt(sum(x*x for x in r)/3);assert rmse<3
 photo_bindings.append({'offer_ref':ref,'native_product_id':s['native_product_id'],'native_variant_id':s['native_variant_id'],'sku':s['sku'],
  'native_media_id':source['native_media_id'],'source_gallery_index':j,'source_image_url':source['url'],
  'source_local_path':source['path'],'source_sha256':source['sha256'],**{k:db[k]for k in ['file_id','folder_id','image_url','folder_url']},
  'Dropbox_cached_path':db['path'],'Dropbox_cached_sha256':db['sha256'],'whole_frame_RGB_RMSE_0_255':rmse,
  'photo_level_correspondence_supported':True,'same_original_encoded_file_verified':False,'new_variant_assignment':False})
definitions=[('BSI-EC5966EA0C7A','O053','Palm 2 White','Single-sided fan: ribs spread mainly from the lower-left region toward the right/top edge.'),
 ('BSI-CAB0D722062D','O054','Palm 1 White','Two-sided fan: ribs spread from the lower centre toward both upper sides.'),
 ('BSI-F61AE4921B6B','O047','Spiral 2 White','Single broad spiral relief; distinct from both fan panels. Existing source association retained; no cached O047 source rendition was available for a new photo comparison.')]
components=[]
for oid,ref,folder,finding in definitions:
 o=options[oid];assert o['file_id']in db_by_id;assert o['folder_url']==assets[o['file_id']]['folder_url']
 components.append({'product_id':oid,'name':o['name'],'canonical_component_id':o['canonical_component_id'],
  'source_offer_ref':ref,'source_SKU':edges[ref]['source_offer']['sku'],'Dropbox_folder_label':folder,'finding':finding,
  'current_reference':{k:o[k]for k in ['file_id','folder_id','image_url','folder_url']},'master_fields':o['master_fields'],
  'working_field_sha256':{k:hashlib.sha256(json.dumps(v,sort_keys=True,ensure_ascii=False).encode()).hexdigest()for k,v in o['master_fields'].items()}})
observations=[
 'Palm Form One and Palm Form Two retain their accepted names. Dropbox folder numbers are reversed relative to the source product names; stable IDs and photographs determine the crosswalk.',
 'O053 has an individual front photograph plus a two-palm context image. Its second photograph does not change the accepted individual sale unit.',
 'O055 contains two triptych views and one two-palm context view. O056 opens with a spiral alone, but gallery frame1 shows the paired fan and spiral and matches the retained Dropbox pair reference.',
 'O027 states three45×40×6cm panels and total45×120×6cm excluding gaps. O055/O056 describe40×45×6cm per part; dimension order remains scoped.',
 'The Timeless Spiral standalone source O047 states45×40×5cm. Do not replace its depth with the6cm arrangement claim, allocate set weights/prices, or infer material chemistry or fitted hardware.',
 'All six source variants have no per-variant image IDs. These are source-photo correspondences and retained product relationships, not certification of every custom size/build or physical cast.',
 'O027 and O047 retain historical shared-SKU Shopify handles. The other four sources have no recorded historical Shopify counterpart; current live account inventory is not inferred.'
]
result={'status':'PALM_COMPONENT_SOURCE_REVIEW_COMPLETE_NO_SHARED_CHANGES','recorded_utc':datetime.now(timezone.utc).isoformat(),
 'baseline_protected_files':guards,'asset_map_binding':p['current_asset_reference_map'],'components':components,
 'source_records':source_records,'photo_bindings':photo_bindings,'images_viewed':pictures,'observations':observations,
 'scope':{'existing_individual_options':3,'full_qualified_working_fields':18,'retained_source_offers':6,'source_media_records':10,
  'source_renditions_viewed':9,'Dropbox_renditions_viewed':6,'photo_correspondences_checked':5,
  'new_platform_pairs':0,'new_options':0,'new_physical_verifications':0,'new_owner_questions':0,'native_or_platform_or_shared_writes':0},
 'source_inputs':{str(x):sha(x)for x in [inventory_path,gallery_path]},
 'image_analysis_method':'Entire frames EXIF-normalized and resized in memory to256px wide for RGB RMSE; all comparisons visually opened. No listing images created, edited or cropped.'}
write(H/'review.json',result)
esc=lambda x:html.escape(str(x),quote=True)
cards=[]
for c in components:
 x=c['current_reference'];rows=''.join('<tr><th>'+esc(k)+'</th><td>'+esc(v['display'])+'<p class="qualification">'+esc(v['state'])+'</p></td></tr>'for k,v in c['master_fields'].items())
 cards.append('<article id="'+esc(c['product_id'])+'"><h2>'+esc(c['name'])+'</h2><p>'+esc(c['finding'])+'</p><p><a href="'+esc(x['image_url'])+'">Dropbox image</a> · <a href="'+esc(x['folder_url'])+'">Containing folder</a></p><p>Source '+esc(c['source_offer_ref'])+', SKU '+esc(c['source_SKU'])+'; Dropbox folder '+esc(c['Dropbox_folder_label'])+'.</p><img class="primary" src="'+esc(db_by_id[x['file_id']]['path'])+'"><table>'+rows+'</table><p><small>'+esc(x['file_id'])+' / '+esc(x['folder_id'])+'</small></p></article>')
source_rows=''.join('<tr><td>'+esc(s['offer_ref'])+'</td><td>'+esc(s['source_offer']['title'])+'</td><td>'+esc(s['sku'])+'</td><td>'+esc(s['historical_shopify_handle']or'No recorded historical pair')+'</td><td>'+str(len(s['media']))+'</td></tr>'for s in source_records)
images=''.join('<figure><img loading="lazy" src="'+esc(x['path'])+'"><figcaption>'+esc(x['role'])+'</figcaption></figure>'for x in pictures)
binding_rows=''.join('<tr><td>'+esc(x['offer_ref'])+'</td><td>'+str(x['source_gallery_index'])+'</td><td><a href="'+esc(x['image_url'])+'">Matched image</a> · <a href="'+esc(x['folder_url'])+'">Folder</a></td><td>'+f"{x['whole_frame_RGB_RMSE_0_255']:.2f}"+'</td></tr>'for x in photo_bindings)
page='<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Palm Form individual components and source photographs</title><style>body{font:17px Arial;line-height:1.5;max-width:1100px;margin:40px auto;padding:0 20px;color:#222}article{border-top:1px solid #bbb;padding:24px 0}table{width:100%;border-collapse:collapse}td,th{padding:10px;text-align:left;vertical-align:top;border-bottom:1px solid #ddd;overflow-wrap:anywhere}.primary{max-width:450px;width:100%}.qualification{font-size:13px;color:#555}.images{display:flex;gap:18px;flex-wrap:wrap}figure{width:300px;margin:0}figure img{width:100%;max-height:400px;object-fit:contain}figcaption{font-size:14px}</style></head><body><h1>Palm Form individual components</h1><p>Three existing individually described components. The photographs support the accepted name-to-folder crosswalk. Working specifications and source differences retain their qualifications.</p><ul>'+''.join('<li>'+esc(x)+'</li>'for x in observations)+'</ul>'+''.join(cards)+'<h2>Retained platform source records</h2><table><tr><th>Reference</th><th>Title</th><th>SKU</th><th>Historical Shopify handle</th><th>Media records</th></tr>'+source_rows+'</table><h2>Photograph correspondences</h2><p>Gallery indices are zero-based. RGB differences compare whole saved renditions; original encoded-file equality is not claimed.</p><table><tr><th>Source</th><th>Gallery index</th><th>Dropbox reference</th><th>RGB RMSE</th></tr>'+binding_rows+'</table><h2>Viewed source and Dropbox photographs</h2><div class="images">'+images+'</div></body></html>'
(H/'index.html').write_text(page)
assert all(sha(path)==expected for path,expected in guards.items())
verification={'status':'PASS','existing_individual_options':3,'qualified_working_fields':18,'native_source_tuples_checked':6,
 'photo_correspondences_checked':5,'viewed_local_images':15,'all_source_gallery_records_accounted_for':10,
 'one_O047_source_rendition_unavailable_not_claimed_viewed':True,'all_protected_files_unchanged':True,
 'new_physical_verifications_or_platform_pairs':0,'review_sha256':sha(H/'review.json'),'page_sha256':sha(H/'index.html')}
write(H/'verification.json',verification)
write(H/'sealed-handoff.json',{'status':'SEALED_LOCAL_COMPONENT_REVIEW','recorded_utc':result['recorded_utc'],
 'files':{str(x):sha(x)for x in [Path(__file__),H/'review.json',H/'verification.json',H/'index.html']}})
for i,c in enumerate(components,1):
 print('ITEM',i,c['name']);print(c['finding']);print('Image:',c['current_reference']['image_url']);print('Containing folder:',c['current_reference']['folder_url']);print('Source SKU:',c['source_SKU'])
 for k,v in c['master_fields'].items():print(k+': '+v['display'])
print(json.dumps(verification))
