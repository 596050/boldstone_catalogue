"""Stage MCP1White as one individual sale component, preserving source and media limitations."""
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REVIEWS = ROOT / 'components/reviews'
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
rel = lambda p: str(p.relative_to(ROOT))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    tmp.replace(path)


def main():
    output = HERE / 'mcp1-white/component-review.json'
    assert not output.exists(), 'MCP1White already staged'
    paths = {'progress': REVIEWS / 'specification_review_progress.json',
        'walkthrough': REVIEWS / 'walkthrough_checkpoint.json',
        'component': ROOT / 'components/checkpoint.json', 'root': ROOT / 'checkpoint.json'}
    docs = {key: read(path) for key, path in paths.items()}
    before = copy.deepcopy(docs)
    hashes = {key: sha(path) for key, path in paths.items()}
    p, cp, c = (docs[key] for key in ['progress', 'walkthrough', 'component'])
    assert cp['current_component_id'] == 'BC-LEAF-GROWTH' and cp['current_answer_recorded']
    assert cp['next_review_after_keep'] == {'component_id':'BC-MCP-1','review_number':71}
    assert docs['root']['current_component_review'] == c and 'BC-MCP-1' not in p['reviews']
    assert not any(x['component_id'] == 'BC-MCP-1' for x in cp['parallel_owner_reviews'])
    assert p['family_review_progress']['Leaf Growth']['first_pass_reference_review_complete']
    keep_path, preceding_card = ROOT / cp['last_identity_approval'], ROOT / cp['current_review_record']
    assert read(keep_path)['user_statement'] == 'Keep “Leaf Growth — White and Gold Leaf”'
    protected_paths = [REVIEWS / 'user_classifications.json', ROOT / 'components/evidence/component_register.json',
        ROOT / cp['register_workbook'], keep_path, preceding_card, ROOT / cp['last_completed_family_first_pass']]
    protected = {str(path):sha(path) for path in protected_paths}
    census, index = read(HERE / 'media-census.json'), read(HERE / 'image-review-index.json')
    assert len(census['listings']) == 6 and all(not x['result']['has_more'] and not x['result']['cursor'] for x in census['listings'])
    assert len(index['cached_previews']) == 69 and len(index['contact_sheets']) == 6
    for preview in index['cached_previews']:
        assert sha(Path(preview['preview_path'])) == preview['sha256']
    originals = read(HERE / 'download-receipts.json')
    assert len(originals) == 7
    for receipt in originals:
        path = Path(receipt['local_path'])
        data = path.read_bytes()
        assert len(data) == receipt['size'] and sha(path) == receipt['sha256']
        assert hashlib.sha256(b''.join(hashlib.sha256(data[i:i+4194304]).digest() for i in range(0,len(data),4194304))).hexdigest() == receipt['content_hash']
    maker_path, prices_path = HERE / 'maker-source-reference.json', HERE / 'dated-price-source-scope.json'
    maker = read(maker_path)
    assert sha(Path(maker['source_local_path'])) == maker['source_sha256']
    for path,digest in maker['labelled_image_sha256'].items():
        assert sha(Path(path)) == digest
    links = {x['file_name']:x for x in read(HERE / 'metadata-links.json')['results']}
    meta = read(HERE / 'selected-metadata.json')
    primary_id, folder_id = 'id:cnqzTNngPVsAAAAAAAylPQ', 'id:cnqzTNngPVsAAAAAAAyirA'
    original_id, series_id, series_folder = 'id:cnqzTNngPVsAAAAAAAuX6g','id:cnqzTNngPVsAAAAAAAugDQ','id:cnqzTNngPVsAAAAAAAyiow'
    primary = next(x['file'] for x in meta['entries'] if x['requested_id'] == primary_id)
    folder = next(x['result']['folder'] for x in read(HERE / 'initial-metadata-and-listings.json')['metadata'] if x['requested_id'] == folder_id)
    assert primary['path_display'].rsplit('/',1)[0] == folder['path_display']
    now = datetime.now(timezone.utc).isoformat()
    family_order = [
        {'component_id':'BC-MCP-1','review_number':71,'variant_id':'MCP1-WHITE','label':'Moon Crater Phase 1 — White (MCP1)'},
        {'component_id':'BC-MCP-1','review_number':71,'variant_id':'MCP1-VERDIGRIS-RUST','variant_only_review':True,
         'label':'Moon Crater Phase 1 — Verdigris and Rust (MCP1)'}]
    def item(suffix,field,display,value,status,basis,refs):
        return {'proposal_id':'MCP1-WHITE-'+suffix,'field':field,'display':display,'value':value,'status':status,
            'basis':basis,'source_refs':refs,'owner_approved':False,'physical_specs_verified':False}
    items = [
        item('DIMENSIONS','Individual dimensions and depth','25×25cm face,4–6cm side depth — historical maker standard; actual cast unmeasured',
            {'maker_face_cm':[25,25],'maker_side_depth_cm':[4,6],'actual_measured_cm':None},'HISTORICAL INDIVIDUAL SOURCE STANDARD',
            'Maker row41explicitly gives250×250mm and40–60mm side depth for one MCP1cast. Numbered trade row1and retail family row independently say25×25cm each. No quartet dimension is divided; related coloured listing6cmdoes not measure White.',[rel(maker_path),rel(prices_path)]),
        item('WEIGHT','Individual dry weight','2–4kg maker calculation; dated trade4kg and retail5kg — actual cast unweighed',
            {'maker_estimate_kg_each':[2,4],'dated_trade_estimate_kg_each':4,'dated_retail_estimate_kg_each':5,'actual_weighed_kg':None},
            'SEPARATE HISTORICAL ESTIMATES; SOURCE DIFFERENCE UNRESOLVED',
            'Retain the historical maker calculation and both owner PDF estimate versions separately. Do not average them, turn them into a measured2–5kgrange or infer packed-versus-net explanations.',[rel(maker_path),rel(prices_path)]),
        item('MATERIAL','Material and finish','Jesmonite AC730 / White marble stone finish — historical maker specification; pictured cast composition unconfirmed',
            {'maker_standard_binder':'Jesmonite AC730','maker_standard_finish':'White Marble Stone Finish','actual_binder':None,'reinforcement':None,'sealer':None,'care':None},
            'HISTORICAL WHITE STANDARD; CAST APPLICABILITY PENDING',
            'Row41documents the White standard. Actual binder, backing, reinforcement, sealer, weather suitability and care of the pictured panel remain unverified; no coloured-treatment chemistry is inherited.',[rel(maker_path)]),
        item('FIXING','Fixing','One small stainless-steel rear fixing centred in upper third — maker instruction; actual White hardware/load unknown',
            {'maker_instruction_count':1,'maker_instruction_type':'Small stainless-steel fixing','maker_instruction_position':'Centre back in upper third, aligned from top edge across series','actual_hardware':None,'rated_load':None},
            'HISTORICAL PER-COMPONENT FIXING INSTRUCTION; WHITE REAR UNSEEN',
            'Maker row41specifies one fixing and position. A rear candidate exists only in the Verdigris/Rust folder, with one visible keyhole-like plate; its front/back pairing, alloy and capacity are unverified and are not transferred to White.',[rel(maker_path),'id:cnqzTNngPVsAAAAAAAygbg']),
        item('PRICE','Individual retail price','£150 per White panel — proposal rounded from dated£156.25White retail reference; no exact White offer confirmed',
            {'proposed_price_gbp':150,'dated_White_retail_2025_gbp':156.25,'dated_White_trade_2025_gbp':78,'current_exact_White_offer_price_gbp':None,'owner_price_approved':False},
            'UNAPPROVED CURRENT PRICE PROPOSAL; DATED WHITE PRICE REFERENCES',
            '150GBPis a discussion proposal rounded from owner Retail2025individual156.25GBP. Trade78and the draft130.84/78/62stack retain their distinct source scope. No set price is divided and the related coloured150GBPlisting is not adopted as a White price.',[rel(prices_path)]),
        item('AVAILABILITY','Availability','Made to order / enquire — proposed current policy; stock, usable mould and lead time unknown',
            {'proposed_policy':'Made to order / enquire subject to production confirmation','physical_stock':None,'reproducibility':None,'lead_time':None},
            'HISTORICAL WHITE POLICY; CURRENT AVAILABILITY UNVERIFIED',
            'Historical White price conditions describe made-to-order work. Historical mould instructions, photographs and a related coloured cart/Unlimitedflag do not establish current White stock, usable mould, production capability or delivery date.',[rel(prices_path),rel(maker_path)])]
    mapping = {'platform_record_level':{'squarespace_id':None,'shopify_handle':None,'shared_sku':None,'status':'EXACT WHITE OFFER AND PLATFORM PAIR UNCONFIRMED'},
        'related_coloured_candidate_only':{'offer_ref':'O007','squarespace_id':'6a413a26870e0e6bc1e0e00c','sku':'SQ6715979','shopify_handle':None,
            'status':'SQUARESPACE-ONLY COLOURED CANDIDATE; EXACT SOURCE IMAGE UNRESOLVED; NOT A WHITE OFFER',
            'public_reader_scope':'Retrieved cached page was crawled three months ago; primary click resolved404false. Current price/availability/image binding not certified.'},
        'dropbox_component_level':{'clean_reference_file_id':primary_id,'folder_id':folder_id,'original_closeup_file_id':original_id,
            'series_file_id':series_id,'series_folder_id':series_folder,'target_position':'Top left in exact027photograph',
            'maker_code':'MCP1-25x25','status':'LABELLED SOURCE AND DEPICTED DESIGN COMPARISON; OWNER IDENTITY PENDING',
            'render_edit_lineage_verified':False,'same_physical_cast_between_images_verified':False},
        'individual_component_level':{'component_id':'BC-MCP-1','quantity':1,'separate_from_other_three_quartet_designs':True,
            'whole_set_dimensions_weight_price_transferred':False},'live_Shopify_account_refreshed':False,'current_native_public_SKUs_reparsed':False}
    coverage = {'complete_individual_clean_reference':True,'original_solo_closeup':True,'uncropped_original_individual_front':False,
        'original_series_reference':True,'indoor_exhibition_reference':True,'verified_client_home_or_garden_installation':False,
        'White_finished_rear':False,'White_fixing_detail':False,'clean_reference_edit_lineage_verified':False,
        'scope':'69files across five MCP1-related folders inspected; not all20catalogue-family folders. Native White001/002/004are close-ups;003is a clean complete reference. Original027/exhibition025show MCP1top-left. Warm indoor light does not create a Gold finish. Other clean quartet member assignments and Rust positions remain pending.'}
    pending_arrangement = {'source_record':rel(HERE / 'media-scope-and-pending.json'),'folder_id':'id:cnqzTNngPVsAAAAAAAyiqA',
        'reference_file_id':'id:cnqzTNngPVsAAAAAAAsSaw','component_id':'BC-MCP-1','target_position':None,
        'status':'RUST QUARTET MEMBER IDENTIFICATION PENDING; NOT AN APPROVED MCP1RUST FINISH OR STANDALONE OFFER'}
    card = {'schema_version':1,'prepared_utc':now,'component_id':'BC-MCP-1','review_number':71,'family':'Moon Crater Phase',
        'review_family_scope':'Moon Crater Phase 1','family_review_number':1,'family_review_total':2,
        'family_total_scope':'Two identified individual MCP1finish references:White and Verdigris/Rust. Rust quartet attribution and other Moon Crater designs are separate pending work; not physical sculpture counts.',
        'size_finish_variant_id':'MCP1-WHITE','proposed_name':family_order[0]['label'],'review_decision_mode':'COMPONENT_NAME_AND_SPECIFICATIONS','identity_decision_destination':'decisions',
        'scope':'One White MCP1panel, separately saleable from the three other quartet designs. Historical maker specifications and conditional current commercial proposals remain separate from name approval.',
        'primary_image_id':primary_id,'primary_folder_id':folder_id,'primary_image_link':links[primary_id]['copy_link_url'],'primary_folder_link':links[folder_id]['copy_link_url'],
        'primary_image_scope':'Complete clean reference; editing/production provenance unverified',
        'original_closeup_id':original_id,'original_closeup_link':links[original_id]['copy_link_url'],
        'series_image_id':series_id,'series_folder_id':series_folder,'series_image_link':links[series_id]['copy_link_url'],
        'series_folder_link':links[series_folder]['copy_link_url'],'series_target_position':'Top left in exact027photograph',
        'exhibition_image_id':'id:cnqzTNngPVsAAAAAAA512A','exhibition_image_link':links['id:cnqzTNngPVsAAAAAAA512A']['copy_link_url'],
        'metadata_checked_utc':meta['checked_utc'],'reference_refresh':rel(HERE / 'selected-metadata.json'),
        'specification_review_items':items,'platform_mapping':mapping,'photo_coverage':coverage,
        'pending_arrangement_component_review':pending_arrangement,'identity_confirmed':False,'specifications_approved':False,'physical_specs_verified':False,
        'individual_sale_unit':{'quantity':1,'description':'One MCP1White component panel','live_listing_prepared_or_published':False},
        'open_gaps':['Owner White MCP1name and depicted identity','Actual measured face/depth and weighed mass;2–4/4/5kgsource differences',
            'Actual binder, reinforcement, sealer and care','White rear fixing hardware/attachment/load','Current individual price, physical stock, mould condition and lead time',
            'Exact White Squarespace/Shopify offer/shared SKU','Uncropped native individual front, verified client installation and clean-image lineage',
            'Exact Rust-quartet member attribution and remaining clean quartet member comparisons'],
        'next_review_after_keep':family_order[1],'next_global_component':{'component_id':'BC-MCP-2','review_number':72},
        'remote_files_changed':False,'live_platform_records_changed':False}
    write(output,card)
    audit_files = [HERE/name for name in ['media-census.json','metadata-links.json','selected-metadata.json','image-review-index.json',
        'maker-source-reference.json','dated-price-source-scope.json','component-position-observations.json','media-scope-and-pending.json','source-platform-and-component-records.json','related-offer-public-reader.json']]
    write(HERE / 'mcp1-white/source-audit.json',{'status':'PASS','checked_utc':now,'MCP1_related_files_inspected':69,'folders_inspected':5,
        'catalogue_family_root_folders':20,'contact_sheets_viewed':6,'originals_hash_verified_and_viewed':7,
        'maker_labelled_images_viewed':4,'numbered_price_PDF_pages_viewed':3,'pagination_complete_for_scoped_folders':True,
        'source_sha256':{rel(path):sha(path) for path in audit_files},'full_catalogue_family_audit_complete':False,'White_platform_offer_confirmed':False})
    write(HERE / 'mcp1-white/before-stage-review.json',{'recorded_utc':now,'files':{rel(paths[key]):value for key,value in before.items()},'protected_sha256':protected})
    p['reviews']['BC-MCP-1'] = {'reviewed_utc':now,'review_number':71,'proposed_name':card['proposed_name'],'size_finish_variant_id':'MCP1-WHITE',
        'identity_confirmed':False,'specifications_approved':False,'physical_specs_verified':False,'source_specifications_recorded':True,
        'specification_proposals':copy.deepcopy(items),'primary_image_id':primary_id,'primary_folder_id':folder_id,'review_record':rel(output),
        'platform_mapping':mapping,'photo_coverage':coverage,'gaps':card['open_gaps'],'pending_size_finish_variants':[family_order[1]],
        'pending_arrangement_component_review':pending_arrangement,'review_family_scope':card['review_family_scope']}
    p['family_review_progress']['Moon Crater Phase 1'] = {'family':'Moon Crater Phase','review_scope':'MCP1individual White and Verdigris/Rust references only; Rust quartet attribution and other designs pending',
        'status':'FIRST_PASS_IN_PROGRESS','updated_utc':now,'review_reference_cards_answered':0,'review_reference_total':2,
        'reference_total_is_sculpture_count':False,'specifications_complete':False}
    state = 'Awaiting Moon Crater Phase1White MCP1name; all six groups pending; weight-source differences retained'
    cp.update({'current_component_id':'BC-MCP-1','current_review_number':71,'current_size_finish_variant_id':'MCP1-WHITE','current_component_layout_id':None,
        'proposed_name':card['proposed_name'],'state':state,'current_review_record':rel(output),'current_family_review_number':1,'current_family_review_total':2,
        'active_family':'Moon Crater Phase 1','family_review_order':family_order,'family_first_pass_complete':False,'current_answer_recorded':False,
        'current_specification_answer_recorded':False,'current_dimension_answer_recorded':False,'current_partial_specification_answer_recorded':False,
        'current_dimension_approval':None,'current_owner_face_dimensions_cm':None,'current_identity_relationship_answer_recorded':False,
        'current_identity_relationship_approval':None,'canonical_depicted_name':None,'current_separate_saleable_design':None,'working_version_user_approved':False,
        'review_decision_mode':card['review_decision_mode'],'question_scope':card['scope'],'answer_state':'Leaf Growth names kept; MCP1White name and specifications unapproved.',
        'primary_image':{'file_id':primary_id,'name':primary['name'],'path_display':primary['path_display'],'copy_link_url':card['primary_image_link'],'open_in_dropbox_url':links[primary_id]['open_in_dropbox_url']},
        'containing_folder':{'folder_id':folder_id,'name':folder['name'],'path_display':folder['path_display'],'copy_link_url':card['primary_folder_link'],'open_in_dropbox_url':links[folder_id]['open_in_dropbox_url']},
        'metadata_checked_utc':meta['checked_utc'],'family_review_evidence':rel(HERE / 'mcp1-white/source-audit.json'),
        'displayed_identity_evidence_file_ids':[primary_id],'displayed_identity_evidence_folder_ids':[folder_id],
        'current_component_source_notes':[x['display'] for x in items],'family_counting_note':card['family_total_scope'],'next_review_after_keep':family_order[1],'updated_utc':now})
    c['interactive_review_state'].update({'current_component_id':'BC-MCP-1','review_number':71,'current_size_finish_variant_id':'MCP1-WHITE','current_component_layout_id':None,
        'current_name':card['proposed_name'],'state':state,'active_family':'Moon Crater Phase 1','family_review_number':1,'family_review_total':2,
        'specification_proposals_approved':False,'working_version_user_approved':False,'review_decision_mode':card['review_decision_mode']})
    c['current_component_review_record'] = rel(output)
    c['last_family_media_review'] = {'family':'Moon Crater Phase','review_scope':'MCP1-related folders only','observed_utc':census['checked_utc'],'files':69,'folders':5,
        'evidence':rel(HERE / 'mcp1-white/source-audit.json'),'remaining_family_work':rel(HERE / 'media-scope-and-pending.json'),'workbook_contains_this_live_media_audit':False}
    c['updated_utc'] = p['updated_utc'] = now
    docs['root']['current_component_review'] = copy.deepcopy(c)
    docs['root']['updated_utc'] = now
    assert all(p['reviews'][key] == value for key,value in before['progress']['reviews'].items())
    assert p['family_review_progress']['Leaf Growth'] == before['progress']['family_review_progress']['Leaf Growth']
    for key in ['parallel_import_queue','parallel_owner_reviews','parallel_evidence_flags','pending_specification_reviews']:
        assert cp[key] == before['walkthrough'][key]
    assert len(items) == 6 and all(not x['owner_approved'] for x in items)
    assert all(sha(path) == hashes[key] for key,path in paths.items()),'Shared writer collision'
    assert all(sha(Path(path)) == digest for path,digest in protected.items())
    for key,path in paths.items():
        write(path,docs[key])
        assert read(path) == docs[key]
    result = {'status':'PASS','current_name':card['proposed_name'],'all_six_groups_unapproved':True,
        'MCP1_is_one_component_separate_from_quartet':True,'weight_estimate_versions_preserved':True,
        'White_exact_platform_offer_unconfirmed':True,'clean_image_and_native_solo_limits_retained':True,
        'Rust_member_positions_and_remaining15folders_pending':True,'previous_reviews_ledger_model_workbook_and_parallel_state_preserved':True,
        'checkpoint_copies_match':read(paths['root'])['current_component_review'] == read(paths['component'])}
    write(HERE / 'mcp1-white/review-validation.json',result)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
