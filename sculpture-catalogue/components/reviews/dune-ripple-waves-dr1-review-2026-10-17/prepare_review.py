"""Prepare the individual white wave; preserve mixed-folder and mould uncertainty."""
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
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
assert cp['current_component_id']=='BC-FDW-2' and cp['current_answer_recorded']
assert cp['next_serialized_parallel_import']['status']=='APPLIED_AND_VERIFIED'
assert read(ROOT/cp['next_serialized_parallel_import']['receipt'])['status']=='APPLIED_AND_VERIFIED'
assert cp['review_order'][35]=='BC-DR-WAVE1' and 'BC-DR-WAVE1' not in progress['reviews']
prior=REVIEWS/'frozen-decowaves-2-review-2026-10-17/identity-approval.json'
assert read(prior)['user_statement']=='Keep “Frozen Decowaves 2 — White”' and not read(prior)['specifications_approved']
protected=[ROOT/'components/evidence/component_register.json',ROOT/cp['register_workbook'],REVIEWS/'user_classifications.json',prior,ROOT/cp['current_review_record']]
hashes={p:sha(p) for p in protected}
now=datetime.now(timezone.utc).isoformat()
write(HERE/'before-dr1-white-review.json',{'recorded_utc':now,'files':{rel(paths[k]):v for k,v in docs.items()}})
meta=read(HERE/'metadata-links.json')
f,g=meta['primary_metadata']['file'],meta['folder_metadata']['folder']
assert f['id']=='id:cnqzTNngPVsAAAAAAAykwg' and g['id']=='id:cnqzTNngPVsAAAAAAArseQ'
assert f['path_display'].rsplit('/',1)[0]==g['path_display']
assert all(not x['listing']['has_more'] and not x['listing']['cursor'] for x in meta['white_folder_census'])
assert sorted(len(x['listing']['entries']) for x in meta['white_folder_census'])==[0,7,20,23]
download=read(HERE/'download-receipt.json')
assert sha(Path(download['local_path']))==download['sha256']
assert download['content_hash']==download['dropbox_content_hash_verified']=='00a108d2b2f8b746ea25cb1a9ee5cdf2c39502edcbb0dab6d6fdd5a59ddbee74'
assert download['size']==f['size']
series=read(HERE/'series-links.json');series_receipts=read(HERE/'series-download-receipts.json')
assert len(series_receipts)==2 and all(sha(Path(x['local_path']))==x['sha256'] for x in series_receipts)
model=read(ROOT/'components/evidence/component_register.json')
maker=[x for x in model['claims'] if x['component_id']=='BC-DR-WAVE1' and 'row54/' in x.get('source_ref','')]
assert len(maker)==5
packets=read(ROOT/'components/parallel-preparation/20261017T164751Z/Prepared_Catalogue_Packets.json')
packet=next(x for x in packets['entries'] if x['component_id']=='BC-DR-WAVE1')
write(HERE/'advisory-packet-used.json',packet)
label_path=Path('/Users/tprice/Library/Application Support/BoldstoneImageConsistency/product-evidence-resolution-20261016T201618Z/Manufacturing_Labelled_References.json')
labels=[x for x in read(label_path) if x['row'] in [54,56]]
assert len(labels)==2
primary,folder=meta['previews']
name='Dune Ripple Waves — White (DR1)'
items=[
 {'proposal_id':'DR1-WHITE-DIMENSIONS','field':'Individual dimensions and depth','value':{'source_face_height_cm':35,'source_face_width_cm':20,'source_side_depth_range_cm':[5,7],'actual_measured_dimensions_cm':None},'display':'Approximately35 H ×20 W ×5–7 Dcm — historical maker standard; actual panel unmeasured','status':'HISTORICAL WHITE STANDARD; ACTUAL CAST UNMEASURED','basis':'Maker row54 specifies approximately350×200mm with50–70mm side measurement. Related coloured listing35×20×6 and recent35×21×6 values are different finish/version source claims and do not measure this pictured white panel.','source_refs':['manufacture-stevensons:Sheet1!row54']},
 {'proposal_id':'DR1-WHITE-WEIGHT','field':'Individual dry weight','value':{'maker_calculated_range_kg':[3,5],'dated_individual_estimates_kg':[4.5,5],'actual_weighed_kg':None},'display':'Approximately3–5kg — historical calculated estimate; dated price drafts give4.5 or5kg','status':'ESTIMATE; NOT WEIGHED','basis':'Maker row54 calculates3–5kg for a white AC730 panel. Dated white retail references estimate4.5/5kg. Coloured offer values are not proof of this cast or a basis for dividing arrangement totals.','source_refs':['manufacture-stevensons:Sheet1!row54',rel(HERE/'advisory-packet-used.json')+':specifications.weight']},
 {'proposal_id':'DR1-WHITE-MATERIAL','field':'Material and finish','value':{'historical_standard_substrate':'Jesmonite AC730','historical_standard_finish':'White marble stone finish','actual_binder':None,'actual_reinforcement':None,'actual_sealing':None},'display':'Jesmonite AC730,white marble stone finish — historical maker specification','status':'SOURCE STANDARD; PICTURED CAST COMPOSITION UNVERIFIED','basis':'Maker row54 names AC730 and white marble stone finish. Texture and colour alone do not identify composition,reinforcement or sealing. Plaster/sand and metallic-effect wording in coloured offers is not transferred to this white panel.','source_refs':['manufacture-stevensons:Sheet1!row54']},
 {'proposal_id':'DR1-WHITE-FIXING','field':'Fixing','value':{'historical_hanging_points':1,'historical_material':'Stainless steel','historical_position':'Centre rear,upper third','actual_hardware':None,'actual_attachment':None,'rated_load':None},'display':'One small stainless fixing,centre rear in upper third — historical maker instruction','status':'SOURCE INSTRUCTION; REAR AND LOAD DETAILS UNVERIFIED','basis':'Maker row54 gives one small stainless fixing at centre back in the upper third,aligned with other series members. No rear appears in the50reviewed white-group thumbnails; actual attachment,wall fixing and rated load remain unknown.','source_refs':['manufacture-stevensons:Sheet1!row54']},
 {'proposal_id':'DR1-WHITE-PRICE','field':'Individual retail price','value':{'proposed_amount':175,'currency':'GBP','sale_unit':'One depicted white Dune Ripple wave panel','dated_white_retail_references_gbp':[146.09,175],'dated_white_trade_reference_gbp':87,'existing_individual_white_offer_confirmed':False},'display':'£175 per individual white panel — proposed,from the2025retail draft','status':'UNAPPROVED PRICE PROPOSAL; NO CURRENT WHITE OFFER CONFIRMED','basis':'Named2025retail draft gives175each; earlier146.09retail and87trade are separately dated price classes. Propose175within the prepared170–220discussion range. Do not overwrite coloured35.33/45/65.33/250 source prices or allocate a set price.','source_refs':[rel(HERE/'advisory-packet-used.json')+':specifications.individual_price']},
 {'proposal_id':'DR1-WHITE-AVAILABILITY','field':'Availability','value':{'proposed_sale_status':'Made to order individually / enquire','physical_stock_quantity':None,'production_capacity':None,'lead_time':None},'display':'Made to order individually / enquire — proposal; stock and lead time unknown','status':'PROPOSED SALE POLICY; PHYSICAL AVAILABILITY UNKNOWN','basis':'Photographs and historical maker templates establish neither current finished stock nor reproducibility/lead time. A SOLD statement versus Unlimited/InStock flags in the related green offer remains a coloured-offer conflict,not a white stock assertion.','source_refs':[rel(HERE/'advisory-packet-used.json')+':specifications.availability']},
]
related=[copy.deepcopy(x) for x in model['platform_records'] if x['offer_ref'] in ['O004','O038','O051','O067']]
mapping={'scope':'Selected white wave panel only','squarespace_id':None,'shopify_handle':None,'shared_sku':None,'individual_offer_confirmed':False,'status':'EXACT WHITE COMPONENT OFFER UNCONFIRMED IN REVIEWED EXPORTS','related_coloured_offer_refs':['O004','O038','O051','O067'],'related_unique_platform_pair':{'offer_ref':'O038','squarespace_id':'6a555a757b54f252fef707d1','shopify_handle':'verdigris-dune-ripple','shared_sku':'VDR-1-35.20','scope':'Verdigris/copper/rust individual offer only; exact DR1vsDR3 mould allocation provisional'},'duplicate_related_sku':'EBAY-188654649217 occurs inO051andO067; retain collision','related_source_prices_are_dated':True,'white_component_not_automatically_bound_to_coloured_offers':True,'live_account_records_refreshed':False}
coverage={'complete_individual_front':True,'detail':True,'oblique_views':True,'series_arrangement':True,'room_context_in_series':True,'garden_context_in_series':True,'standalone_white_in_situ_folder_files':0,'confirmed_standalone_installation_photo':False,'rear':False,'installation_provenance':'UNCONFIRMED; context scenes do not establish actual client installation,date or stock','solo_folder_contains_multiple_wave_designs':True,'scope':'Fresh complete50file census across4white folders:20mixed solo/comparison/detail,23arrangement,7context and0standalone context. All50cached thumbnails inspected; primary plus clean arrangement and room context originals newly downloaded/hash-verified. Other47originals not newly downloaded. The folder includes DR1andDR3and must not be mapped wholesale to one sculpture.'}
planned=[
 {'component_id':'BC-DR-WAVE1','review_number':36,'variant_id':'DR1-WHITE','label':'Selected individual white wave; proposedDR1'},
 {'component_id':'BC-DR-WAVE1','review_number':36,'variant_id':'DR-WAVES-RUST','label':'Rust wave candidate; exact DR1/DR3allocation to check','group_ref':'G115'},
 {'component_id':'BC-DR-WAVE1','review_number':36,'variant_id':'DR-WAVES-VERDIGRIS','label':'Verdigris wave candidate; split any distinct shapes before approval','group_ref':'G116'},
 {'component_id':'BC-DR-SPIRAL','review_number':37,'variant_id':'DR2-WHITE','label':'White spiral'},
 {'component_id':'BC-DR-SPIRAL','review_number':37,'variant_id':'DR-SPIRAL-VERDIGRIS','label':'Verdigris spiral'},
 {'component_id':'BC-DR-SPIRAL','review_number':37,'variant_id':'DR-SPIRAL-RUST','label':'Rust spiral'},
 {'component_id':'BC-DR-SPIRAL','review_number':37,'variant_id':'DR-SPIRAL-COPPER','label':'Copper spiral'},
 {'component_id':'BC-DR-SPIRAL','review_number':37,'variant_id':'DR-SPIRAL-COPPER-PARTIAL-VERDIGRIS','label':'Copper and partial verdigris spiral'},
 {'component_id':'BC-DR-SPIRAL','review_number':37,'variant_id':'DR-SPIRAL-GOLD','label':'Gold spiral'},
 {'component_id':'BC-DR-SPIRAL','review_number':37,'variant_id':'DR-SPIRAL-BRONZE-VERDIGRIS','label':'Misnamed bronze verdigris group: inspect actual solo design'},
 {'component_id':'BC-DR-WAVE3','review_number':38,'variant_id':'DR3-WHITE','label':'Other individual white wave; distinguish separately labelledDR3'},
]
next_review={'component_id':'BC-DR-WAVE1','review_number':36,'size_finish_variant_id':'DR-WAVES-RUST','family_review_number':2,'requires_exact_design_allocation_check':True}
review={'schema_version':1,'prepared_utc':now,'component_id':'BC-DR-WAVE1','canonical_design_name':'Dune Ripple Waves — DR1','proposed_name':name,'display_name':name,'family':'Dune Ripple','maker_code':'DR1-35x20','review_number':36,'family_review_number':1,'family_review_total':len(planned),'family_total_scope':'Planned component/finish review cards; provisional source-group assignments may split or move after visual review. This is not a physical sculpture/stock count.','size_finish_variant_id':'DR1-WHITE','variant_only_review':False,'review_decision_mode':'COMPONENT_NAME_AND_SPECIFICATIONS','scope':'One depicted white wave panel. Maker row54 is the working DR1standard; DR1vsDR3code/colour/cast relationships remain distinct evidence questions. A named Keep confirms depicted name and identity only.','primary_image_id':f['id'],'primary_folder_id':g['id'],'primary_image_link':primary['copy_link_url'],'primary_folder_link':folder['copy_link_url'],'metadata_checked_utc':meta['checked_utc'],'reference_refresh':rel(HERE/'metadata-links.json'),'primary_original_receipt':rel(HERE/'download-receipt.json'),'series_original_receipts':rel(HERE/'series-download-receipts.json'),'image_review_index':rel(HERE/'image-review-index.json'),'series_image_id':series['examples'][0]['id'],'series_folder_id':series['examples'][0]['folder_id'],'series_image_link':series['previews'][0]['copy_link_url'],'series_position':'Right panel in selected clean three-part photograph; this positional visual match does not prove physical stock or all maker aliases.','room_context_image_id':series['examples'][1]['id'],'room_context_image_link':series['previews'][1]['copy_link_url'],'garden_context_image_id':series['examples'][2]['id'],'garden_context_image_link':series['previews'][2]['copy_link_url'],'maker_claims':maker,'maker_labelled_references':labels,'maker_labelled_reference_source':str(label_path),'maker_design_association':'PROVISIONAL SOURCE-ASSISTED DR1ASSOCIATION; small labelled DR1andDR3images compared; no all-colour mould equivalence asserted','advisory_preparation':rel(HERE/'advisory-packet-used.json'),'specification_review_items':items,'platform_mapping':mapping,'related_coloured_offer_snapshots':related,'photo_coverage':coverage,'family_review_plan':planned,'identity_confirmed':False,'specifications_approved':False,'physical_specs_verified':False,'open_gaps':['Confirm individual depicted name and DR1/DR3maker-code relationship; mixed folder is not one component','Measure face dimensions and maximum projection; white35×20standard versus coloured35×21source versions remain separate','Weigh actual cast;3–5kg is calculated estimate','Confirm actual AC730 binder,reinforcement,sealing and care instructions','Rear fixing photograph and exact attachment/wall hardware/rated load','Approve175GBPindividual white price and made-to-order policy; establish stock/capacity/lead time','Exact white Squarespace/Shopify individual offer remains unconfirmed; coloured native IDs/SKUcollision retained separately','Confirm context provenance and obtain actual standalone installation photograph; care/packing dimensions/weight remain open'],'next_review_after_keep':next_review,'next_global_component_id':'BC-DR-SPIRAL','remote_files_changed':False,'live_platform_records_changed':False}
write(out,review)
progress['reviews']['BC-DR-WAVE1']={'reviewed_utc':now,'identity_confirmed':False,'specifications_approved':False,'physical_specs_verified':False,'proposed_name':name,'size_finish_variant_id':'DR1-WHITE','specification_proposals':copy.deepcopy(items),'source_specifications_recorded':True,'maker_claims':maker,'platform_mapping':mapping,'primary_image_id':f['id'],'primary_folder_id':g['id'],'review_record':rel(out),'photo_coverage':coverage,'gaps':review['open_gaps'],'pending_size_finish_variants':[{'variant_id':x['variant_id'],'status':'AWAITING INDIVIDUAL VISUAL/DESIGN ALLOCATION REVIEW','group_ref':x.get('group_ref')} for x in planned[1:3]]}
progress['updated_utc']=now
cp.update({'current_component_id':'BC-DR-WAVE1','current_review_number':36,'current_size_finish_variant_id':'DR1-WHITE','proposed_name':name,'state':'Awaiting individual white Dune Ripple wave name/identity; six source/working specification groups separately open','primary_image':{'file_id':f['id'],'name':f['name'],'path_display':f['path_display'],'copy_link_url':primary['copy_link_url'],'open_in_dropbox_url':primary['open_in_dropbox_url']},'containing_folder':{'folder_id':g['id'],'name':g['name'],'path_display':g['path_display'],'copy_link_url':folder['copy_link_url'],'open_in_dropbox_url':folder['open_in_dropbox_url']},'answer_state':'No answer yet. Named Keep approves depicted name/identity only. Source claims and guesses remain separately open.','question_scope':'Keep the proposed individual white Dune Ripple Waves name/identity. Source35×20cmface and5–7cmside;3–5kgcalculatedweight;historicalAC730white standard;one rearSSfixing historical;175GBPindividual pricePROPOSAL;made-to-order/enquiryPROPOSAL. Mixed white folder and related coloured offers are not wholesale component/offer equivalence.','metadata_checked_utc':meta['checked_utc'],'current_answer_recorded':False,'current_specification_answer_recorded':False,'current_dimension_answer_recorded':False,'working_version_user_approved':False,'current_review_record':rel(out),'review_decision_mode':'COMPONENT_NAME_AND_SPECIFICATIONS','active_family':'Dune Ripple','current_family_review_number':1,'current_family_review_total':len(planned),'family_review_order':planned,'family_review_evidence':rel(HERE/'metadata-links.json'),'next_review_after_keep':next_review,'displayed_identity_evidence_file_ids':[f['id']],'displayed_identity_evidence_folder_ids':[g['id']],'current_component_source_notes':[x['display'] for x in items],'main_family_review_reservation':{'component_ids':['BC-DR-WAVE1','BC-DR-SPIRAL','BC-DR-WAVE3'],'global_reviews':[36,37,38],'status':'MAIN DUNE RIPPLE FAMILY, ALL FINISHES; EXACT COLOURED MOULD ALLOCATION REMAINS OPEN'},'after_main_family_next_unclaimed':{'component_id':'BC-EMBED-SHELLS','review_number':45},'updated_utc':now})
# Later receipts remain outside the completed bounded import.
later=[('BC-EG-4','EG-4-WHITE','components/parallel-reviews/egyptian-2026-10-17/palm-four-extended-white/identity-approval.json'),('BC-SHELL-I',None,'components/parallel-reviews/shellmoon-2026-10-17/islington-water-feature/review-approval.json'),(None,None,'components/parallel-reviews/egyptian-2026-10-17/IMPORT_PACKAGE.json'),(None,None,'components/parallel-reviews/shellmoon-2026-10-17/IMPORT_PACKAGE.json')]
for cid,vid,receipt in later:
    if (ROOT/receipt).exists() and not any(x['receipt']==receipt for x in cp['parallel_import_queue']):
        cp['parallel_import_queue'].append({'component_id':cid,'variant_id':vid,'scope_kind':'REVIEW_IMPORT_PACKAGE' if cid is None else 'NAME_ONLY_IDENTITY_RECEIPT','receipt':receipt,'receipt_sha256':sha(ROOT/receipt),'status':'RECEIVED AFTER BATCH2 CUTOFF; PENDING NEXT SERIALIZED VERIFICATION','approval_imported':False,'recorded_utc':now,'scope':'Exact owner/name-only scope,original proposal snapshot and current stable references must be independently checked. Packages overlap prior imported receipts and must be deduplicated.'})
cp['completed_serialized_parallel_import']=copy.deepcopy(cp['next_serialized_parallel_import'])
cp['next_serialized_parallel_import']={'trigger':'AFTER_DUNE_RIPPLE_FAMILY_FIRST_PASS_BEFORE_MAIN_REVIEW45','status':'PENDING_EXACT_TRANSCRIPT_SNAPSHOT_AND_CURRENT_REFERENCE_VERIFICATION','source_queue':'parallel_import_queue','approval_inferred':False}
component['interactive_review_state'].update({'current_component_id':'BC-DR-WAVE1','review_number':36,'current_size_finish_variant_id':'DR1-WHITE','current_name':name,'state':cp['state'],'family_review_number':1,'specification_proposals_approved':False,'working_version_user_approved':False,'review_decision_mode':'COMPONENT_NAME_AND_SPECIFICATIONS'})
component['current_component_review_record']=rel(out)
component['last_family_media_review']={'family':'Dune Ripple','finish':'White wave and shared series/context','observed_utc':meta['checked_utc'],'scope':coverage['scope'],'files':50,'folders':4,'evidence':rel(HERE/'metadata-links.json'),'workbook_contains_this_live_media_audit':False}
for key in ['parallel_import_queue','parallel_owner_reviews','main_family_review_reservation','after_main_family_next_unclaimed']:
    component[key]=copy.deepcopy(cp[key])
component['updated_utc']=now
docs['root']['current_component_review']=copy.deepcopy(component)
for k,p in paths.items():write(p,docs[k])
assert all(sha(p)==h for p,h in hashes.items())
assert read(paths['root'])['current_component_review']==read(paths['component'])
validation={'status':'PASS','component_id':'BC-DR-WAVE1','review_number':36,'primary_complete_single_original_verified':True,'current_white_file_census':50,'all50cached_thumbnails_reviewed':True,'three_current_originals_hash_verified':True,'white_waves_folder_mixed_design_warning_preserved':True,'DR1_DR3_source_mould_and_coloured_aliases_not_merged':True,'exact_white_platform_offer_unconfirmed':True,'six_specification_groups':6,'identity_or_specification_approval_inferred':False,'source_model_workbook_owner_decisions_and_prior_review_unchanged':True,'bounded_parallel_import_verified_before_review36':True,'later_parallel_receipts_queued_not_imported':True,'remote_files_changed':False}
write(HERE/'review-validation.json',validation)
print(json.dumps(validation))
