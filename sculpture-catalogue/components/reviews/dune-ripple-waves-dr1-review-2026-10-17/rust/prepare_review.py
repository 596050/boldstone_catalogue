"""Prepare the rust wave as a separately scoped depicted finish, keeping conflicts."""
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
REVIEWS=ROOT/'components/reviews'


def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rel(p):return str(p.relative_to(ROOT))
def write(p,d):
    t=p.with_name(p.name+'.tmp');t.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');t.replace(p)


paths={'walkthrough':REVIEWS/'walkthrough_checkpoint.json','progress':REVIEWS/'specification_review_progress.json','component':ROOT/'components/checkpoint.json','root':ROOT/'checkpoint.json'}
docs={k:read(p) for k,p in paths.items()}
cp,progress,component=[docs[k] for k in ['walkthrough','progress','component']]
out=HERE/'component-review.json'
if cp.get('current_review_record')==rel(out):
    print('ALREADY_PREPARED');raise SystemExit(0)
assert cp['current_component_id']=='BC-DR-WAVE1' and cp['current_size_finish_variant_id']=='DR1-WHITE' and cp['current_answer_recorded']
assert not cp['current_specification_answer_recorded']
approval=HERE.parent/'identity-approval.json';parent_source=HERE.parent/'component-review.json'
assert read(approval)['user_statement']=='Keep “Dune Ripple Waves — White (DR1)”'
assert read(approval)['identity_confirmed'] and not read(approval)['specifications_approved']
protected=[ROOT/'components/evidence/component_register.json',ROOT/cp['register_workbook'],REVIEWS/'user_classifications.json',approval,parent_source]
hashes={p:sha(p) for p in protected}
parent=progress['reviews']['BC-DR-WAVE1']
parent_before={k:copy.deepcopy(v) for k,v in parent.items() if k not in ['size_finish_variants','pending_size_finish_variants']}
now=datetime.now(timezone.utc).isoformat()
write(HERE/'before-rust-review.json',{'recorded_utc':now,'files':{rel(paths[k]):v for k,v in docs.items()}})
meta=read(HERE/'metadata-links.json')
file,folder=meta['primary_metadata']['file'],meta['folder_metadata']['folder']
assert file['id']=='id:cnqzTNngPVsAAAAAAAykEA' and folder['id']=='id:cnqzTNngPVsAAAAAAAykDw'
assert file['path_display'].rsplit('/',1)[0]==folder['path_display']
for listing in ['solo_listing','rust_in_situ_listing','mixed_verdigris_and_rust_listing']:
    assert not meta[listing]['has_more'] and not meta[listing]['cursor']
assert [len(meta[k]['entries']) for k in ['solo_listing','rust_in_situ_listing','mixed_verdigris_and_rust_listing']]==[4,0,12]
downloads=read(HERE/'download-receipts.json')
assert len(downloads)==4
for d in downloads:
    data=Path(d['local_path']).read_bytes()
    calculated=hashlib.sha256(b''.join(hashlib.sha256(data[i:i+4194304]).digest() for i in range(0,len(data),4194304))).hexdigest()
    assert len(data)==d['size'] and calculated==d['content_hash']==d['dropbox_content_hash_verified']
    assert hashlib.sha256(data).hexdigest()==d['sha256']
public=read(HERE/'public-page-http-receipts.json')
assert len(public)==2 and all(x['http_status']==200 for x in public)
live_offers={}
for row in public:
    assert sha(Path(row['local_path']))==row['sha256']
    assert len(row['products'])==1
    product=row['products'][0];offer=product['offers']
    assert offer['sku']=='EBAY-188654649217' and offer['priceCurrency']=='GBP'
    live_offers[row['offer_ref']]={'source_url':row['source_url'],'checked_utc':row['checked_utc'],'price_gbp':offer['price'],'sku':offer['sku'],'schema_availability':offer['availability'],'description':product.get('description'),'live_admin_checked':False}
assert live_offers['O051']['price_gbp']==35.33 and live_offers['O067']['price_gbp']==65.33
public_images=read(HERE/'public-image-http-receipts.json')+read(HERE/'O067-image-http-receipts.json')
assert all(sha(Path(x['local_path']))==x['sha256'] for x in public_images)
model=read(ROOT/'components/evidence/component_register.json')
source_offers=[copy.deepcopy(x) for x in model['platform_records'] if x['offer_ref'] in ['O051','O067']]
assert len(source_offers)==2 and len({x['sq_id'] for x in source_offers})==2
assert all(not x['sh_handle'] for x in source_offers)
packet=read(HERE.parent/'advisory-packet-used.json')
write(HERE/'advisory-packet-used.json',packet)
links={x['file_name']:x for x in meta['previews']}
primary=links[file['id']];containing=links[folder['id']]
vid='DR-WAVES-RUST';name='Dune Ripple Waves — Rust'
items=[
 {'proposal_id':vid+'-DIMENSIONS','field':'Individual dimensions and depth','value':{'listing_dimensions_cm':[35,21,6],'dimension_order':'Height, width, depth as working listing interpretation','actual_measured_dimensions_cm':None,'related_white_face_cm':[35,20]},'display':'35 H × 21 W × 6 D cm — both rust listings state this size; actual cast unmeasured','status':'CURRENT LISTING CLAIM; NOT OWNER MEASURED','basis':'Both rust listing descriptions give35×21×6cm. Retain the separate35×20cm historical white standard. Photographs have no reliable scale; no dimensions are inferred from wall blocks or perspective.','source_refs':[live_offers['O051']['source_url'],live_offers['O067']['source_url']]},
 {'proposal_id':vid+'-WEIGHT','field':'Individual dry weight','value':{'proposed_range_kg':[3,5],'actual_weighed_kg':None,'raw_export_values':{'O051':6.6,'O067':11.02},'raw_export_units':'Unencoded','related_white_maker_range_kg':[3,5]},'display':'Approximately 3–5 kg — working guess; actual cast unweighed','status':'GUESS; SOURCE WEIGHT VALUES HAVE UNENCODED UNITS','basis':'Use the similarly sized Dune Ripple white3–5kg maker estimate as a broad analogy only. Rust plaster/sand composition and density may differ. Native raw6.6and11.02weights have no encoded units and must not be presented as3or5kg measurements or harmonized as one confirmed mass.','source_refs':['manufacture-stevensons:Sheet1!row54 analogy only','SS Wall Products!row56/Weight','SS Wall Products!row72/Weight']},
 {'proposal_id':vid+'-MATERIAL','field':'Material and finish','value':{'listed_substrate':'Plaster and sand','listed_finish':'Hand-painted faux rust-on-iron surface effect','actual_binder':None,'actual_metal_content':None,'actual_reinforcement':None,'actual_sealing':None},'display':'Plaster and sand with a faux rust/iron surface effect — listing described; actual recipe unverified','status':'SOURCE MATERIAL CLAIM AND VISIBLE FINISH; ACTUAL COMPOSITION UNVERIFIED','basis':'Both current descriptions name plaster/sand and a faux rust/iron surface. The brown textured front supports the appearance,not solid-iron composition. O051 lists hand-painted finish; actual pigments,metal content,reinforcement and sealing remain unknown. Do not carry whiteAC730into this finish.','source_refs':[live_offers['O051']['source_url'],live_offers['O067']['source_url']]},
 {'proposal_id':vid+'-FIXING','field':'Fixing','value':{'associated_listing_rear_observation':'One recessed metal keyhole plate','proposed_hanging_points':1,'actual_pictured_rust_cast_to_rear_correspondence':None,'metal_grade':None,'attachment':None,'rated_load':None},'display':'One rear metal keyhole plate — proposal from associated listing rear photograph; exact cast/load unverified','status':'LISTING REAR OBSERVED; APPLICATION TO EXACT RUST CAST PROVISIONAL','basis':'The O051 rear photograph and O067 small duplicate show one metal keyhole plate in a white recessed back. Green edge traces mean it may show another finish/cast; the source gallery association does not independently prove this exact brown front and rear belong to one cast. None of4Dropbox rust originals shows the reverse. Do not call the plate stainless or assign the white-template upper-third position/load rating.','source_refs':['O051 public rear image','O067 additional small gallery image',rel(HERE/'public-image-http-receipts.json'),rel(HERE/'O067-image-http-receipts.json')]},
 {'proposal_id':vid+'-PRICE','field':'Individual retail price','value':{'current_listed_prices_gbp':{'O051':35.33,'O067':65.33},'shared_duplicate_sku':'EBAY-188654649217','proposed_selected_price_gbp':None,'currency':'GBP','sale_unit':'One rust wave panel','intended_price_owner_confirmed':False},'display':'£35.33 and £65.33 — two current individual listings; intended price unresolved','status':'TWO LIVE SOURCE PRICES; NO OWNER PRICE SELECTION OR REPRICING','basis':'Both public pages currently show the sameSKUwith different prices. Retain both original Squarespace IDs and offers. Their sharedSKUis a duplicate collision,not proof of a Shopify match,extra physical sculpture or an instruction to choose/correct a price.','source_refs':[live_offers['O051']['source_url'],live_offers['O067']['source_url']]},
 {'proposal_id':vid+'-AVAILABILITY','field':'Availability','value':{'public_listing_status':'Both pages display an offer with InStock schema flag','proposed_individual_sale_policy':'Enquire / made to order subject to confirmation','physical_stock_quantity':None,'production_capacity':None,'lead_time':None},'display':'Enquire / made to order — proposal; actual stock and lead time unknown','status':'PROPOSED ENQUIRY POLICY; LIVE OFFER FLAGS ARE NOT PHYSICAL STOCK','basis':'The two pages have purchase offers and InStock schema flags; native O051Unlimited versus O067quantity1flags are platform settings. They do not establish current physical stock,availability of this exact cast,mould readiness or lead time. Keep proposed enquiry/made-to-order policy separate from listed availability.','source_refs':[live_offers['O051']['source_url'],live_offers['O067']['source_url']]},
]
mapping=[]
for offer in source_offers:
    mapping.append({'offer_ref':offer['offer_ref'],'squarespace_id':offer['sq_id'],'shopify_handle':None,'sku':offer['sku'],'platform_status':'SQUARESPACE OFFER IDENTIFIED; SHOPIFY COUNTERPART UNCONFIRMED','dropbox_status':'CURRENT PUBLIC FRONT VISUALLY MATCHES THE RUST WAVE DEPICTED IN THE FOUR SOLO ORIGINALS','primary_file_id':file['id'],'primary_folder_id':folder['id'],'front_comparison_file_id':'id:cnqzTNngPVsAAAAAAAykEg','sale_unit':'One rust wave panel','observed_designs_in_solo_folder':1,'duplicate_sku_collision_preserved':True,'source_native_weight_raw':offer['raw_weight'],'source_native_weight_units':'Unencoded','current_public_offer':live_offers[offer['offer_ref']],'live_platform_accounts_refreshed':False,'exact_DR1_DR3_mould_relationship_confirmed':False})
coverage={'complete_individual_front':True,'detail':True,'oblique_views':True,'single_wall_display':True,'room_or_garden_context':False,'exact_rust_wave_series_picture':False,'rust_in_situ_folder_files':0,'dropbox_rear_picture_in_reviewed_folders':False,'associated_platform_rear_available':True,'associated_platform_rear_cast_match':'UNCONFIRMED; green edge traces may indicate another finish/cast','rear_stable_dropbox_file_id':None,'client_installation_provenance':'UNCONFIRMED','physical_stock_inferred':False,'scope':'Fresh4solo+0rust-context+12mixed-group census,pagination complete. All4rust originals downloaded/hash-verified/viewed;12mixed-group cached thumbnails checked by current stableID/path/size and viewed. Mixed group depicts green waves with rust/verdigris spirals,not this plain rust wave. Current O051andO067fronts and associated rear images also downloaded/viewed. No family-wide or library-wide absence claim.'}
next_review={'component_id':'BC-DR-WAVE1','review_number':36,'size_finish_variant_id':'DR-WAVES-VERDIGRIS','family_review_number':3,'requires_exact_design_allocation_check':True}
review={'schema_version':1,'prepared_utc':now,'component_id':'BC-DR-WAVE1','canonical_design_name':'Dune Ripple Waves','proposed_name':name,'display_name':name,'family':'Dune Ripple','review_number':36,'family_review_number':2,'family_review_total':cp['current_family_review_total'],'size_finish_variant_id':vid,'variant_only_review':True,'review_decision_mode':'SIZE_FINISH_VARIANT_NAME_AND_SPECIFICATIONS','parent_identity_approval':rel(approval),'parent_design_relationship_status':'PROVISIONAL organizational bucket from source register; exact DR1versusDR3mould and cast relationship remain unconfirmed. A Rust name Keep must not approve mould equivalence or white specifications.','scope':'One depicted rust-effect plain-wave panel with its own listing dimensions,substrate and fixing uncertainty. Preserve one design/finish identity across four photographs and two duplicate-SKUoffers; do not count two offers as two stock sculptures.','primary_image_id':file['id'],'primary_folder_id':folder['id'],'primary_image_link':primary['copy_link_url'],'primary_folder_link':containing['copy_link_url'],'clean_front_image_id':'id:cnqzTNngPVsAAAAAAAylFQ','clean_front_image_link':links['id:cnqzTNngPVsAAAAAAAylFQ']['copy_link_url'],'metadata_checked_utc':meta['checked_utc'],'reference_refresh':rel(HERE/'metadata-links.json'),'original_download_receipts':rel(HERE/'download-receipts.json'),'mixed_series_review_index':rel(HERE/'mixed-series-review-index.json'),'public_page_receipts':rel(HERE/'public-page-http-receipts.json'),'public_image_receipts':[rel(HERE/'public-image-http-receipts.json'),rel(HERE/'O067-image-http-receipts.json')],'associated_public_rear_image_url':public_images[1]['url'],'advisory_preparation':rel(HERE/'advisory-packet-used.json'),'specification_review_items':items,'platform_mapping':mapping,'source_offer_snapshots':source_offers,'photo_coverage':coverage,'identity_confirmed':False,'specifications_approved':False,'physical_specs_verified':False,'open_gaps':['Confirm name and depicted rust variant identity; exactDR1/DR3mould relationship remains provisional','Measure actual35×21×6cm dimensions and depth; do not silently use white35×20cm','Weigh actual cast; raw6.6and11.02export weights have no encoded units','Confirm plaster/sand recipe,metal content,reinforcement,sealing and care requirements','Confirm exact rust cast rear and keyhole attachment/metal grade/wall fastener/load rating; associated platform rear has green edge traces','Resolve duplicate-SKU35.33GBPvs65.33GBPoffers and choose intended individual price','Confirm current stock,production capacity,lead time and enquiry/made-to-order policy','Identify exact individual Shopify counterpart if any','Obtain room/garden context and series image for this exact rust wave; no exact rear stableDropboxIDmapped in reviewed folders'],'next_review_after_keep':next_review,'next_global_component_id':'BC-DR-SPIRAL','remote_files_changed':False,'live_platform_records_changed':False}
write(out,review)
parent.setdefault('size_finish_variants',{})[vid]={'reviewed_utc':now,'identity_confirmed':False,'specifications_approved':False,'proposals_approved':False,'physical_specs_verified':False,'proposed_name':name,'size_finish_variant_id':vid,'review_record':rel(out),'primary_image_id':file['id'],'primary_folder_id':folder['id'],'specification_proposals':copy.deepcopy(items),'platform_mapping':mapping,'photo_coverage':coverage,'parent_design_relationship_status':review['parent_design_relationship_status']}
for row in parent.get('pending_size_finish_variants',[]):
    if row['variant_id']==vid:row.update({'review_status':'AWAITING RUST NAME/IDENTITY; SIX SOURCE/WORKING GROUPS PENDING','review_record':rel(out)})
progress['updated_utc']=now
cp.update({'current_size_finish_variant_id':vid,'proposed_name':name,'state':'Awaiting individual rust-wave name/identity; specifications and duplicate-offer price conflict remain open','primary_image':{'file_id':file['id'],'name':file['name'],'path_display':file['path_display'],'copy_link_url':primary['copy_link_url'],'open_in_dropbox_url':primary['open_in_dropbox_url']},'containing_folder':{'folder_id':folder['id'],'name':folder['name'],'path_display':folder['path_display'],'copy_link_url':containing['copy_link_url'],'open_in_dropbox_url':containing['open_in_dropbox_url']},'current_answer_recorded':False,'current_specification_answer_recorded':False,'current_dimension_answer_recorded':False,'working_version_user_approved':False,'current_review_record':rel(out),'review_decision_mode':review['review_decision_mode'],'current_family_review_number':2,'family_review_evidence':rel(HERE/'metadata-links.json'),'answer_state':'No answer yet. Named Keep approves rust variant name/depicted identity only. Six groups,white mould equivalence,physical stock and duplicate price selection remain unapproved.','question_scope':'Keep Dune Ripple Waves — Rust as the depicted individual variant name/identity; six source/working groups supplied. Do not infer full specification or price selection from named Keep.','metadata_checked_utc':meta['checked_utc'],'next_review_after_keep':next_review,'displayed_identity_evidence_file_ids':[file['id']],'displayed_identity_evidence_folder_ids':[folder['id']],'current_component_source_notes':[x['display'] for x in items],'updated_utc':now})
for cid,vid2,receipt in [('BC-SPICE',None,'components/parallel-reviews/spice-spiralfish-2026-10-17/spice-white/review-approval.json'),('BC-FOLD-1','FOLD-1-WHITE','components/parallel-reviews/foldings-2026-10-17/swan-wing-folds-white/identity-approval.json')]:
    if (ROOT/receipt).exists() and not any(x['receipt']==receipt for x in cp['parallel_import_queue']):
        cp['parallel_import_queue'].append({'component_id':cid,'variant_id':vid2,'receipt':receipt,'receipt_sha256':sha(ROOT/receipt),'status':'RECEIVED NAME ONLY; PENDING NEXT BOUNDED SERIALIZED IMPORT','approval_imported':False,'scope':'Verify exact owner transcript and proposal snapshot/current IDs before import. Spice panel layouts and Foldings source conflicts remain separate from named Keep.','recorded_utc':now})
cp['next_serialized_parallel_import']['trigger']='AFTER_DUNE_RIPPLE_WAVES_FINISH_REVIEWS_BEFORE_MAIN_REVIEW37'
component['interactive_review_state'].update({'current_component_id':'BC-DR-WAVE1','review_number':36,'current_size_finish_variant_id':vid,'current_name':name,'state':cp['state'],'family_review_number':2,'review_decision_mode':review['review_decision_mode'],'specification_proposals_approved':False,'working_version_user_approved':False,'components_with_any_identity_scope':read(REVIEWS/'user_classifications.json')['identity_confirmation_counts']['components_with_any_identity_scope']})
component['current_component_review_record']=rel(out)
component['last_family_media_review']={'family':'Dune Ripple','finish':'Rust wave','observed_utc':meta['checked_utc'],'files':16,'folders':3,'scope':coverage['scope'],'evidence':rel(HERE/'metadata-links.json'),'workbook_contains_this_live_media_audit':False}
component['parallel_import_queue']=copy.deepcopy(cp['parallel_import_queue']);component['updated_utc']=now
docs['root']['current_component_review']=copy.deepcopy(component)
assert {k:v for k,v in parent.items() if k not in ['size_finish_variants','pending_size_finish_variants']}==parent_before
for key,path in paths.items():write(path,docs[key])
assert all(sha(p)==h for p,h in hashes.items())
assert read(paths['root'])['current_component_review']==read(paths['component'])
validation={'status':'PASS','component_id':'BC-DR-WAVE1','variant_id':vid,'four_current_rust_originals_hash_verified_and_viewed':True,'twelve_mixed_group_cached_previews_reviewed':True,'context_folder_empty_and_exact_series_gap_preserved':True,'current_two_public_offer_prices_35_33_and_65_33_verified':True,'duplicate_sku_does_not_create_two_sculptures_or_Shopify_match':True,'platform_rear_observed_but_exact_cast_relation_unconfirmed':True,'white_parent_approval_and_specifications_unchanged':True,'source_model_workbook_classifications_unchanged':True,'six_specification_groups':6,'name_or_specification_approval_inferred':False,'remote_files_changed':False}
write(HERE/'review-validation.json',validation);print(json.dumps(validation))
