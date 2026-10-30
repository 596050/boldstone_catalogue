"""Show the coordinated catalogue work one item at a time, with current image links."""
import argparse,hashlib,html,json
from pathlib import Path
from urllib.parse import parse_qs,unquote,urlparse
H=Path(__file__).resolve().parent;B=H.parents[1]/'sculpture-catalogue'
p=argparse.ArgumentParser();p.add_argument('--item',type=int,default=1);p.add_argument('--write-report',action='store_true');args=p.parse_args()
if args.item<1:raise SystemExit('Navigation item numbers start at1.')
def dropbox_path(url):
 u=urlparse(url);path=unquote(u.path)
 for prefix in ['/preview','/home']:
  if path.startswith(prefix+'/'):path=path[len(prefix):];break
 preview=parse_qs(u.query).get('preview');return path.rstrip('/')+('/'+preview[0]if preview else'')
read=lambda p:json.loads(Path(p).read_text());pointer=read(B/'current-master.json');raw=(B/pointer['register']).read_bytes();assert hashlib.sha256(raw).hexdigest()==pointer['register_sha256'];g=json.loads(raw);options={o['product_id']:o for o in g['options']}
source=B/'components/parallel-reviews/squarespace-admin-rust-readonly-20261024T010238Z';rust=read(source/'current-rust-audit.json')['rust_collision'];items=[];workshop_done=bool(pointer.get('latest_spiralmoon_workshop_navigation_import'));current_out=(B/pointer['current_image_review_links']['latest_native_navigation']).parent
def add(title,status,oid,details,review):
 o=options[oid];items.append({'title':title,'status':status,'option_id':oid,'name':o['name'],'image':o['image_url'],'containing_folder':o['folder_url'],'file_id':o['file_id'],'folder_id':o['folder_id'],'details':details,'review':str(review)})
spiralmoon_details={
 'Completed file moves':29 if workshop_done else 27,
 'Original family files preserved':82,
 'Product folder files':10,
 'In Situ folder files':54 if workshop_done else 56,
 'Workshop Views files':2 if workshop_done else 0,
 'Selected photograph':'011.JPG, same file and role; actual parent remains the existing In Situ folder',
 'Workshop filing':'Two approved images filed in Workshop Views' if workshop_done else 'Owner-approved workshop filing awaits master import'
}
spiralmoon_report='spiralmoon-workshop-current-folder-refresh-master-2026-10-24' if workshop_done else 'spiralmoon-current-folder-refresh-master-2026-10-24'
add('Spiralmoon folder update','Completed and imported','BSI-10BFED6B265B',spiralmoon_details,current_out/'spiralmoon-folder-changes.html')
add('Rust platform records','Current source verified; platform changes remain held','BSI-947F365275C5',{'Shared SKU':rust['sku'],'Current Squarespace records':[{k:r[k]for k in ['source_offer_ref','native_product_id','native_variant_id','price_raw','stock_setting_raw','visible_raw']}for r in rust['records']],'Catalogue working price':options['BSI-947F365275C5']['master_fields']['Individual price']['display'],'Scope':'Captured administrative prices and stock settings are distinct from the working estimate and physical stock.'},source/'review.html')
add('Acanthus specification review','Accepted working estimates retained; actual measurements not supplied','BSI-3635E3DC3434',{k:v['display']for k,v in options['BSI-3635E3DC3434']['master_fields'].items()},B/pointer['current_specification_verification']['review'])
add('Water-build physical audit scope','Structured scope aligned; zero new physical verifications','BSI-C3AA3700F7DA',{'Current structured audit scope':[pointer['current_specification_verification']['physical_options_source_audited'],pointer['current_specification_verification']['physical_field_groups_source_audited']],'Independent source assertions for these four water-build fields':0,'Scope':'Existing comparator estimates and offered fixing choices; whole-group listing reference remains qualified. Price covers one panel.'},B/'outputs/physical-audit-ledger-alignment-master-2026-10-24/physical-ledger-alignment.html')
leaf_image='https://www.dropbox.com/preview/BOLDSTONE%20MASTER/Products/01%20Wall%20Sculptures/Leaf%20Form/Leaf%20Form%201%20and%20Leaf%20Form%202%20White%20Together/leaf-form__two-leaf-forms-white__001.jpeg'
leaf_folder='https://www.dropbox.com/home/BOLDSTONE%20MASTER/Products/01%20Wall%20Sculptures/Leaf%20Form/Leaf%20Form%201%20and%20Leaf%20Form%202%20White%20Together'
items.append({'title':'Leaf Form owner interpretation','status':'Imported and independently verified','option_id':'BSI-6581D83760F1','name':'Leaf Form — White','image':leaf_image,'containing_folder':leaf_folder,'file_id':'id:cnqzTNngPVsAAAAAAArqDQ','folder_id':'id:cnqzTNngPVsAAAAAAAyijw','details':{'Owner correction':'One existing sculpture design shown in two wall placements; not two unique component designs.','Current count':'One BC-LEAF-FORM design retained; no design/option increment.','Preserved scope':'Historical native two-part text, SKU and price records remain source history. Physical cast count, pack sale quantity, per-copy price and image-production method remain unverified.','Owner packet lane':'Existing source-review session; no repeated question or Dropbox move.'},'review':str(B/pointer['current_image_review_links']['latest_owner_depiction'])})
asset_path=B/pointer['current_asset_reference_map']['path']if pointer.get('current_asset_reference_map')else(B/pointer['register']).parent/'current-assets.json'
if pointer.get('current_asset_reference_map'):assert hashlib.sha256(asset_path.read_bytes()).hexdigest()==pointer['current_asset_reference_map']['sha256']
assets=read(asset_path);wave=assets['id:cnqzTNngPVsAAAAAAArqLg']
items.append({'title':'Wave and Moonshadow mixed-scene filing','status':'Approved moves completed and imported','option_id':'','name':'Wave and Moonshadow / Moonspirals mixed scene','image':wave['image_url'],'containing_folder':wave['folder_url'],'file_id':wave['file_id'],'folder_id':wave['folder_id'],'details':{'Files moved':2,'Existing family originals retained':59,'Former three-panel scene folder images':5,'New mixed-scene folder images':2,'Scope':'Current navigation only; all existing individual/context selections, design identities and physical fields retained.'},'review':str(current_out/'wave-moonshadow-folder-changes.html')})
rust_option=options['BSI-947F365275C5'];items.append({'title':'Platform source comparison','status':'Captured source observations imported; read-only comparison tables exported','option_id':rust_option['product_id'],'name':'37 documented pairs;43 unpaired Squarespace sources;one unpaired historical Shopify draft','image':rust_option['image_url'],'containing_folder':rust_option['folder_url'],'file_id':rust_option['file_id'],'folder_id':rust_option['folder_id'],'details':{'Squarespace source product-ID/SKU observations':80,'Raw-field comparisons':720,'Documented historical Shopify pairs':37,'Squarespace sources without a documented historical Shopify pair':43,'Unpaired historical Shopify draft':1,'Scope':'Retained wall-sculpture source set only. Current Shopify absence, exact individual configurations and physical stock are not inferred. Image link is the Rust example; all source/related image links are in the report.'},'review':str(H/'source-comparison.html')})
if pointer.get('current_primary_navigation_health'):
 health_review=B/pointer['current_primary_navigation_health']['review']
 for oid in ['BSI-D5A939264C82','BSI-65520F070145']:
  obs=options[oid]['current_primary_navigation']
  if obs.get('deletion_observed_in_exact_id_history'):
   add('Selected primary Dropbox reference','Saved primary marked deleted in available history; historical original retained; owner hold unchanged',oid,{'Exact-ID history':obs['server_deleted_utc'],'Retained reference':'Exact local original matches latest available revision size/content hash; no restore or replacement.','Historical original':obs['existing_local_historical_original']['path'],'Scope':'Actor and reason unknown; no account-wide absence or new current image binding. Source-photo content status retained separately.'},str(health_review)+'#'+oid)
   items[-1]['historical_original']=obs['existing_local_historical_original']['path']
  else:add('Selected primary Dropbox reference','Unresolved native file; containing folder verified; identity hold retained',oid,{'Current native readback':'Stable-ID and exact-path metadata failed; saved ID/path absent from the checked direct parent listing.','Retained reference':'Saved image is source history; no replacement selected.','Scope':'No deletion, account-wide absence, web-URL failure or physical claim inferred. Source-photo coverage is retained separately.'},str(health_review)+'#'+oid)
 add('Moon Water Catcher links','Current capitalization normalized by unchanged IDs','BSI-70C7029C1DB1',{'Change':'Moonwater catcher becomes Moonwater Catcher in current navigation.','Retained':'Same selected image, IDs, source-photo roles, identity and working specifications.'},str(health_review)+'#BSI-70C7029C1DB1')
elif args.item>7:raise SystemExit('Navigation-health continuation has not been published yet.')
if pointer.get('current_working_design_group_projection'):
 for oid in ['BSI-612EF4DBB555','BSI-8CC6C8AABCB7']:
  add('Decowaves1 owner-confirmed design relationship','Same relief design; separate individual finish option retained',oid,{'Owner approval':'Exact number1 Verdigris/White pair; the number2 relationship has its own separate answer and evidence.','Retained component ID records':112,'Current working design groups':pointer['current_working_design_group_projection']['grouped_working_design_identity_count'],'Active individual finish/size/build options':188,'Preserved scope':'All existing names, option IDs, source SKUs, six working field objects, prices and Dropbox IDs retained. No physical cast/mould/stock or new Terracotta photograph approval.'},current_out/'decowaves1-owner-design-equivalence.html')
elif args.item>10:raise SystemExit('Owner design-group continuation has not been published yet.')
if pointer.get('latest_decowaves2_owner_design_equivalence_import'):
 for oid in ['BSI-FE830AE502C3','BSI-837E9B0B3B36']:
  add('Decowaves2 recovered owner-confirmed relationship','Exact duplicate replies recovered as one owner decision',oid,{'Owner answer':'wYes twice in the source session, recorded once as Yes to the exact Number2 comparison.','Retained component ID records':112,'Current working design groups':pointer['current_working_design_group_projection']['grouped_working_design_identity_count'],'Active individual finish/size/build options':188,'Preserved scope':'Separate individual finish options, all six field objects, prices and Dropbox/source IDs retained. No physical mould, cast, stock or SKU inference.'},B/pointer['current_working_design_group_projection']['review'])
elif args.item>12:raise SystemExit('Number2 owner answer has not been published yet.')
if pointer.get('latest_moonspirals_pair_native_navigation_import'):
 for ident in ['id:cnqzTNngPVsAAAAAAAucCw','id:cnqzTNngPVsAAAAAAAuR4Q','id:cnqzTNngPVsAAAAAAAuigw']:
  x=assets[ident];items.append({'title':'Moonspiral pair photograph filing','status':'Approved native move verified and imported into current master','option_id':'','name':x['name'],'image':x['image_url'],'containing_folder':x['folder_url'],'file_id':ident,'folder_id':x['folder_id'],'details':{'Current folder':'Moonspiral1 and Moonspiral2 White In Situ','Family originals retained':148,'Source folder images':19,'Pair folder images':31,'Scope':'Same original pixels/file ID. This unselected arrangement reference does not add a component, listing, photo role or physical cast.'},'review':str(current_out/'moonspirals-pair-folder-changes.html')})
elif args.item>14:raise SystemExit('Moonspiral pair folder update has not been published yet.')
if pointer.get('latest_current_url_case_normalization'):
 for oid in ['BSI-CF0CC1EB8F96','BSI-FBD125528AEC','BSI-65A93033A200','BSI-4515726BBC18','BSI-9AF26B8CF780','BSI-207102CFD25C']:
  add('Current image and folder URL correction','Same file and parent IDs; recorded capitalization imported',oid,{k:v['display']for k,v in options[oid]['master_fields'].items()},str(current_out/'six-current-link-corrections.html')+'#'+oid)
if pointer.get('latest_moonwave_approved_native_navigation'):
 overlay=read(pointer['latest_moonwave_approved_native_navigation']['overlay'])
 for o in sorted((o for o in overlay['objects']if o['old_path']!=o['current_path']),key=lambda x:x['current_path']):
  x=assets[o['file_id']];items.append({'title':'Approved Moonwave photo filing','status':'Native move verified and imported; original ID/pixels retained','option_id':'','name':o['current_name'],'image':x['image_url'],'containing_folder':x['folder_url'],'file_id':o['file_id'],'folder_id':x['folder_id'],'details':{'Verified family counts':'84White/15InSitu;99originals','Scope':'Folder navigation only; primary033/context005, original source rows, image roles and specification objects retained.','Source locator':'O016 at source_offer_edges[15]'if o['file_id']=='id:cnqzTNngPVsAAAAAAArp1g'else'Coverage163 own-file navigation'if o['file_id']=='id:cnqzTNngPVsAAAAAAArp2Q'else'Additional arrangement/display photograph'},'review':str(current_out/'moonwave-approved-folder-changes.html')+'#'+o['file_id'].split(':')[1]})
if pointer.get('latest_read_only_source_photo_review'):
 packet=pointer['latest_read_only_source_photo_review'];assert hashlib.sha256(Path(packet['path']).read_bytes()).hexdigest()==packet['sha256'];review=read(packet['path'])
 for c in review['cases']:
  assert options[c['option_id']]['master_fields']==c['master_fields']
  add('Source photograph and finish comparison','Existing appearance association checked; specifications retain qualifications',c['option_id'],{'Finding':c['finding'],'Source tuple':c['native_tuple'],'Source clock':c['source_photo_scope'],**{k:v['display']for k,v in c['master_fields'].items()}},packet['review']+'#'+c['offer_ref'])
if pointer.get('latest_echo_sound_approved_native_navigation'):
 packet=pointer['latest_echo_sound_approved_native_navigation'];assert hashlib.sha256(Path(packet['overlay']).read_bytes()).hexdigest()==packet['overlay_sha256'];overlay=read(packet['overlay'])
 for o in sorted((o for o in overlay['objects']if o['old_path']!=o['current_path']),key=lambda x:x['current_path']):
  x=assets[o['file_id']];items.append({'title':'Approved Echo Sound photo filing','status':'Verified actual folder imported; original ID/name/format/bytes retained','option_id':'','name':o['current_name'],'image':x['image_url'],'containing_folder':x['folder_url'],'file_id':o['file_id'],'folder_id':x['folder_id'],'details':{'Verified family counts':'93White/25InSitu;180originals across9folders','Scope':'Additional gallery navigation. Four selected catalogue options, photo roles and all working specifications retained.','Previous containing folder':o['old_path'].rsplit('/',1)[0]},'review':packet['moved_image_review']})
if pointer.get('current_source_photo_review_index'):
 packet=pointer['current_source_photo_review_index'];index_path=B/packet['path'];assert hashlib.sha256(index_path.read_bytes()).hexdigest()==packet['sha256'];photo_index=read(index_path)
 assert hashlib.sha256((B/packet['review']).read_bytes()).hexdigest()==packet['review_sha256']
 assert photo_index['current_asset_map']['sha256']==pointer['current_asset_reference_map']['sha256']
 palm_review_path=H.parent/'palm-form-component-review-20261024-root/review.json'
 palm_packet=next(x for x in photo_index['review_packets']if Path(x['review_json'])==palm_review_path)
 assert hashlib.sha256(palm_review_path.read_bytes()).hexdigest()==palm_packet['review_sha256'];palms=read(palm_review_path)
 for c in palms['components']:
  oid=c['product_id'];o=options[oid];assert c['master_fields']==o['master_fields'];assert all(c['current_reference'][k]==o[k]==assets[o['file_id']][k]for k in ['file_id','folder_id','image_url','folder_url'])
  details={'Design finding':c['finding'],'Retained source offer':c['source_offer_ref'],'Source SKU':c['source_SKU'],'Actual Dropbox folder label':c['Dropbox_folder_label'],'Numbering crosswalk':'Source Palm Form One is filed under Palm 2 White; source Palm Form Two is filed under Palm 1 White. Exact photographs and stable IDs retain the connection.','Component and arrangement scope':'Each option remains individually specified. Timeless Spiral retains its individual 5 cm depth; 6 cm arrangement claims remain separate.'}
  details.update({k:v['display']+'\n'+v['state']for k,v in c['master_fields'].items()})
  add('Palm and spiral individual component review','Source comparison complete; existing field qualifications retained',oid,details,palm_packet['review']+'#'+oid);items[-1]['master_fields']=c['master_fields']
echo_ready_path=H/'ready-echo-pattern-source-review.json';echo_reader=None
if echo_ready_path.is_file():
 echo_reader=read(echo_ready_path)
 assert echo_reader['baseline_register_sha256']==pointer['register_sha256']and echo_reader['baseline_workbook_sha256']==pointer['workbook_sha256']
 echo_baseline=echo_reader['current_asset_reference_map'];assert hashlib.sha256((B/echo_baseline['path']).read_bytes()).hexdigest()==echo_baseline['sha256']
 if echo_baseline['sha256']!=pointer['current_asset_reference_map']['sha256']:assert pointer['current_asset_reference_map'].get('preceding_reference')==echo_baseline
 for path_key,hash_key in [('seal','seal_sha256'),('review','review_sha256'),('review_json','review_json_sha256'),('verification','verification_sha256')]:assert hashlib.sha256(Path(echo_reader[path_key]).read_bytes()).hexdigest()==echo_reader[hash_key]
 for path,expected in read(echo_reader['seal'])['files'].items():assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==expected
 ev=read(echo_reader['verification']);assert ev['status']=='PASS'and ev['checks_passed']==ev['checks_total']
 er=read(echo_reader['review_json']);assert er['summary']['individual_working_options']==4 and er['summary']['qualified_working_fields']==24
 for c in er['individual_options']:
  oid=c['product_id'];o=options[oid];assert c['qualified_working_fields']==o['master_fields'];assert all(c[k]==o[k]==assets[o['file_id']][k]for k in ['file_id','folder_id','image_url','folder_url'])
  case=next(x for x in er['cases']if oid in x['option_ids'])
  details={'Retained source offer':case['offer_ref'],'Photograph finding':case['finding'],'Source variant scope':case['configuration_limit'],'Source and individual prices':case['commercial_limit'],'Source and individual weights':case['weight_limit'],'Review coverage':'One White group frame and three of twenty-one Verdigris gallery frames checked. Eighteen Verdigris frames retain metadata only.'}
  details.update({k:v['display']+'\n'+v['state']for k,v in c['qualified_working_fields'].items()})
  add('Echo Pattern individual component review','Sealed source evidence linked locally; current individual fields retained',oid,details,echo_reader['review']+'#'+oid);items[-1]['master_fields']=c['qualified_working_fields']
def append_source_continuation(c):
  o=options[c['option_id']];assert all(o[k]==assets[o['file_id']][k]for k in ['file_id','folder_id']);assert all(dropbox_path(o[k])==dropbox_path(assets[o['file_id']][k])for k in ['image_url','folder_url'])
  details={'Photograph finding':c['finding'],'Review packet source records':', '.join(c['offer_refs']),'Evidence scope':c['scope']}
  details.update({k:v['display']+'\n'+v['state']for k,v in o['master_fields'].items()})
  add(c['title'],'Completed source/component review; original qualifications retained',o['product_id'],details,c['review']);items[-1]['master_fields']=o['master_fields']
if pointer.get('current_source_photo_review_index'):
 for c in photo_index.get('continuation_components',[])[:12]:append_source_continuation(c)
if pointer.get('latest_acanthus_flower_case_navigation'):
 packet=pointer['latest_acanthus_flower_case_navigation'];assert hashlib.sha256(Path(packet['path']).read_bytes()).hexdigest()==packet['sha256'];case=read(packet['path']);a=assets[case['file_id']]
 items.append({'title':'Acanthus Flower display-folder link correction','status':'Same file and parent IDs; capitalization refreshed from native metadata','option_id':'','name':a['name'],'image':a['image_url'],'containing_folder':a['folder_url'],'file_id':a['file_id'],'folder_id':a['folder_id'],'details':{'Previous path':case['previous_reference']['path'],'Current path':case['fresh_reference']['path'],'Actual parent changes':0,'Scope':'Current navigation only. The original photograph, selected individual image, component identity, source roles and qualified specifications remain retained.'},'review':str(B/pointer['current_source_photo_review_index']['review'])})
if pointer.get('current_source_photo_review_index'):
 for c in photo_index.get('continuation_components',[])[12:]:append_source_continuation(c)
local_platform=H.parent/'local-platform-crosswalk-corrected-20261024-root'
if(local_platform/'sealed-handoff.json').is_file():
 seal=read(local_platform/'sealed-handoff.json');assert all(hashlib.sha256(Path(path).read_bytes()).hexdigest()==expected for path,expected in seal['files'].items())
 lp=read(local_platform/'local-platform-crosswalk.json');lv=read(local_platform/'verification.json');assert lv['status']=='PASS'and lv['checks_passed']==lv['checks_total'];assert lp['baseline_pointer_sha256']==hashlib.sha256((B/'current-master.json').read_bytes()).hexdigest()
 row=next(x for x in lp['squarespace_source_records']if x['offer_ref']=='O029');reference=row['source_image_reference']['fresh_scoped_native_reference']or row['source_image_reference']['saved_catalogue_reference']
 items.append({'title':'Local Shopify and Squarespace product/variant/image matching','status':'Requested local records compared; no account access required','option_id':'','name':'37 local source pairs,43 Squarespace-only sources and1 blank-SKU Shopify wall draft','image':reference['image_url'],'containing_folder':reference['folder_url'],'file_id':reference['file_id'],'folder_id':reference['folder_id'],'details':{'Local Shopify records':'136 products,160 variants,416 gallery rows;38 wall products and117 wall gallery rows','Local Squarespace records':'80 exact product/variant/SKU tuples with445 complete gallery entries','Source authority':'Local Shopify CSV; the two CSV copies differ only in17 Vendor trailing spaces. Source dates and the dated2024 workbook remain recorded.','Image and variant scope':'Numeric Shopify IDs and explicit Variant Image values are not exported. Exact local handles, option tuples, raw SKUs and hash-bound rows retained; product gallery membership is separate from individual configuration.','Unmatched scope':'43 Squarespace sources lack a nonempty SKU match in the local Shopify data. The Shopify draft has a blank SKU. No platform absence, stock or new product inference.','Illustrated source':'Brancusi BM-2P-50.50 → local Shopify handle copy-of-ammonite; two-panel arrangement remains distinct from individual component options.'},'review':str(local_platform/'index.html')})
gallery_work=H.parent/'shopify-wall-gallery-review-20261024-root'
if(gallery_work/'sealed-handoff.json').is_file():
 gallery_seal=read(gallery_work/'sealed-handoff.json');assert all(hashlib.sha256(Path(path).read_bytes()).hexdigest()==expected for path,expected in gallery_seal['files'].items())
 gallery=read(gallery_work/'shopify-wall-gallery-visual-review.json');assert gallery['baseline_pointer_sha256']==hashlib.sha256((B/'current-master.json').read_bytes()).hexdigest()
 example=next(r for r in gallery['records']if r['review_id']=='S112');reference=example['native_photo_correspondence']['native_reference']
 items.append({'title':'Complete local Shopify wall-gallery visual review','status':'117 frames reviewed;114 qualified photograph correspondences and3 exact-photo uncertainties','option_id':'','name':'38 exported products with per-image roles and current Dropbox links','image':reference['image_url'],'containing_folder':reference['folder_url'],'file_id':reference['file_id'],'folder_id':reference['folder_id'],'details':{'Source gallery roles':gallery['counts']['source_role_counts'],'Dropbox photograph correspondences':114,'Exact photograph uncertainties':'S016 Moonwave room view;S021/S022 Ammonite full pair and detail. Same-scene/design candidates retained.','Squarespace image comparison':'115 Shopify frames have visually corresponding SQ frames;two additional frames have no same-frame correspondence established in the reviewed445 entries.','Scope':'Stable native file and actual parent IDs retained. Product galleries do not establish explicit variant images or physical specifications. Group, cross-finish and crop/exposure qualifications retained.','Walkthrough command':'python3 reports/shopify-wall-gallery-review-20261024-root/walkthrough.py --product 1 (product numbers 1–38). Add --specifications for all qualified existing option fields.','Illustrated source':'Swan Wing Folds → current Fold Unfold1 White001; portrait/wide crop correspondence, no byte-identity or new design claim.'},'review':str(gallery_work/'index.html')})
if args.item>len(items):raise SystemExit('Requested navigation item is not published yet.')
item=items[args.item-1];print(f"ITEM {args.item}: {item['title']}\n{item['status']}\n{item['name']}\nImage: {item['image']}\nContaining folder: {item['containing_folder']}\nFile ID: {item['file_id']}\nFolder ID: {item['folder_id']}")
for k,v in item['details'].items():print(k+': '+(v if isinstance(v,str)else json.dumps(v,ensure_ascii=False)))
print('Review: '+item['review'])
if args.write_report:
 esc=lambda x:html.escape(str(x),quote=True);cards=[]
 for i,x in enumerate(items,1):
  rows=''.join('<tr><th>'+esc(k)+'</th><td>'+esc(v if isinstance(v,str)else json.dumps(v,ensure_ascii=False))+'</td></tr>'for k,v in x['details'].items());cards.append('<article id="item-'+str(i)+'"><h2>'+str(i)+'. '+esc(x['title'])+'</h2><p>'+esc(x['status'])+'</p><p>'+esc(x['name'])+'</p><p><a href="'+esc(x['image'])+'">Image</a> · <a href="'+esc(x['containing_folder'])+'">Containing folder</a> · <a href="'+esc(x['review'])+'">Detailed review</a></p><table>'+rows+'</table><p><small>'+esc(x['file_id'])+' / '+esc(x['folder_id'])+'</small></p></article>')
 for i,x in enumerate(items):
  if x.get('historical_original'):cards[i]=cards[i].replace('>Image</a>','>Saved Dropbox image (deleted)</a>',1).replace('</h2>','</h2><p><a href="'+esc(x['historical_original'])+'">Open exact local historical original</a></p>',1)
 text='<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Catalogue terminal walkthrough</title><style>body{font:17px Arial;line-height:1.5;max-width:1000px;margin:40px auto;padding:0 20px;color:#202020}article{margin:35px 0;padding-top:15px;border-top:1px solid #bbb}table{border-collapse:collapse;width:100%}td,th{text-align:left;vertical-align:top;padding:10px;border-bottom:1px solid #ddd;overflow-wrap:anywhere}th{width:28%}</style></head><body><h1>Catalogue terminal walkthrough</h1><p>Current master:188 active options;112 retained component IDs;110 working design groups. Folder updates are coordinated with the directory session. Platform matching uses the requested local Squarespace and Shopify records. Other sessions own the remaining image and identity reviews. Existing photograph deferrals remain in place.</p>'+''.join(cards)+'</body></html>'
 if(local_platform/'sealed-handoff.json').is_file():text=text.replace('</h1>','</h1><nav><a href="'+esc(local_platform/'index.html')+'">Local Shopify/Squarespace matched and unmatched records, complete galleries and Dropbox links</a></nav>',1)
 if(gallery_work/'sealed-handoff.json').is_file():text=text.replace('</h1>','</h1><nav><a href="'+esc(gallery_work/'index.html')+'">All117 local Shopify wall-gallery frames: roles, current Dropbox files and containing folders</a></nav>',1)
 if(H/'decowaves-component-review.html').is_file():text=text.replace('</h1>','</h1><nav><a href="decowaves-component-review.html">All six Decowaves options: images, folders and specifications</a> · <a href="decowaves2-terracotta-source-review.html">Terracotta Number2 source comparison</a></nav>',1)
 if pointer.get('latest_scoped_water_feature_coverage'):text=text.replace('</h1>','</h1><nav><a href="'+esc(pointer['latest_scoped_water_feature_coverage']['review'])+'">Water-feature coverage: 19 existing options and component references</a></nav>',1)
 if pointer.get('current_source_photo_review_index'):text=text.replace('</h1>','</h1><nav><a href="'+esc(B/pointer['current_source_photo_review_index']['review'])+'">Completed source-photograph reviews: images, folders and qualified specifications</a></nav>',1)
 if pointer.get('current_source_photo_review_index')and photo_index.get('read_only_directory_review'):text=text.replace('</h1>','</h1><nav><a href="'+esc(photo_index['read_only_directory_review']['review'])+'">Leaf Growth and Fountain Palm: 316 image/folder links and read-only filing observations</a></nav>',1)
 if pointer.get('current_source_photo_review_index'):
  for directory in photo_index.get('additional_read_only_directory_reviews',[]):text=text.replace('</h1>','</h1><nav><a href="'+esc(directory['review'])+'">'+esc(', '.join(directory['families']))+': '+str(directory['originals'])+' image/folder links and read-only filing observations</a></nav>',1)
 if echo_reader:text=text.replace('</h1>','</h1><nav><a href="'+esc(echo_reader['review'])+'">Next completed review: four Echo Pattern individual options and source-gallery limits</a></nav>',1)
 extra=B/'components/parallel-reviews/o006-o007-source-photo-review-20261024-B'
 if(extra/'verification.json').is_file():
  ev=read(extra/'verification.json');er=read(extra/'review.json')
  if ev['status']=='PASS'and ev['passed']==ev['total']and hashlib.sha256((extra/'review.json').read_bytes()).hexdigest()==ev['review_sha256']and er['asset_navigation_binding']['sha256']==pointer.get('current_asset_reference_map',{}).get('sha256'):text=text.replace('</h1>','</h1><nav><a href="'+esc(extra/'index.html')+'">Two further Moon Crater source-photo comparisons</a></nav>',1)
 if(H/'ready-source-triage.json').is_file():
  ready=read(H/'ready-source-triage.json')
  if ready['baseline_register_sha256']==pointer['register_sha256']and hashlib.sha256(Path(ready['review']).read_bytes()).hexdigest()==ready['review_sha256']:text=text.replace('</h1>','</h1><nav><a href="'+esc(ready['review'])+'">43 source records: current images, folders, specifications and next evidence needed</a></nav>',1)
 if pointer.get('latest_moonwave_approved_native_navigation'):
  text=text.replace('</h1>','</h1><section><strong>Approved Moonwave revision imported:</strong> Six photographs moved to In Situ and four close views to White;84White/15InSitu,all99originals preserved. The earlier nine-photo plan remains withdrawn history. These numbered review items include files and source records; they are not sculpture counts.</section>',1)
 elif pointer.get('latest_moonwave_proposal_withdrawal'):
  d=pointer['latest_moonwave_proposal_withdrawal'];text=text.replace('</h1>','</h1><section><strong>Moonwave proposal withdrawn:</strong> The owner rejected the nine-photo selection. No Moonwave moves were applied. The proposed folder-count changes are withdrawn. The directory session owns the replacement review; current selected image roles are retained. <a href="https://www.dropbox.com/home/BOLDSTONE%20MASTER/Products/01%20Wall%20Sculptures/Moonwave/Moonwave%20White">Moonwave White folder</a> · <a href="https://www.dropbox.com/home/BOLDSTONE%20MASTER/Products/01%20Wall%20Sculptures/Moonwave/Moonwave%20White%20In%20Situ">In Situ folder</a>.</section>',1)
 if pointer.get('latest_echo_sound_approved_native_navigation'):text=text.replace('</h1>','</h1><section><strong>Echo Sound filing imported:</strong> 23 approved photograph moves;93White/25InSitu,all180originals preserved. Catalogue records and workbook data are byte-identical.</section>',1)
 (H/'index.html').write_text(text);(H/'walkthrough-state.json').write_text(json.dumps({'register_sha256':pointer['register_sha256'],'workbook_sha256':pointer['workbook_sha256'],'items':items,'pending_physical_item':'BSI-3635E3DC3434','pending_shopify_question_owned_by_thread':'01a13fe6-495b-7253-b923-31823b4cbca8','pending_physical_question_owned_by_thread':'01a16dbc-036d-7003-8ebd-34cb76b5b667'},ensure_ascii=False,indent=2)+'\n')
 if pointer.get('latest_moonwave_proposal_withdrawal'):
  state=read(H/'walkthrough-state.json');state['moonwave_proposal_status']=pointer['latest_moonwave_proposal_withdrawal'];state['current_pointer_sha256']=hashlib.sha256((B/'current-master.json').read_bytes()).hexdigest();(H/'walkthrough-state.json').write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n')
 if pointer.get('latest_moonwave_approved_native_navigation'):
  state=read(H/'walkthrough-state.json');state['current_moonwave_approved_navigation']=pointer['latest_moonwave_approved_native_navigation'];state['current_pointer_sha256']=hashlib.sha256((B/'current-master.json').read_bytes()).hexdigest();(H/'walkthrough-state.json').write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n')
 if pointer.get('latest_echo_sound_approved_native_navigation'):
  state=read(H/'walkthrough-state.json');state['current_echo_sound_approved_navigation']=pointer['latest_echo_sound_approved_native_navigation'];state['current_asset_reference_map']=pointer['current_asset_reference_map'];(H/'walkthrough-state.json').write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n')
 if pointer.get('current_source_photo_review_index'):
  state=read(H/'walkthrough-state.json');state['current_source_photo_review_index']=pointer['current_source_photo_review_index'];state['current_pointer_sha256']=hashlib.sha256((B/'current-master.json').read_bytes()).hexdigest();(H/'walkthrough-state.json').write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n')
 if echo_reader:
  state=read(H/'walkthrough-state.json');state['local_echo_pattern_review']=echo_reader;(H/'walkthrough-state.json').write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n')
 if(local_platform/'sealed-handoff.json').is_file():
  state=read(H/'walkthrough-state.json');state.pop('pending_shopify_question_owned_by_thread',None);state['local_shopify_source_authority']='Requested existing local export; no live account-choice question';(H/'walkthrough-state.json').write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n')
 if(gallery_work/'sealed-handoff.json').is_file():
  state=read(H/'walkthrough-state.json');state['local_shopify_gallery_review']={'review':str(gallery_work/'index.html'),'seal':str(gallery_work/'sealed-handoff.json'),'seal_sha256':hashlib.sha256((gallery_work/'sealed-handoff.json').read_bytes()).hexdigest(),'counts':gallery['counts']};(H/'walkthrough-state.json').write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n')
