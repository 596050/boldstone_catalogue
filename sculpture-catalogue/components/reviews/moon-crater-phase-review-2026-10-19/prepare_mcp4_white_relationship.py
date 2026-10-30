"""Present MCP4's White depiction as a possible alias of the approved Concave Moon."""
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = HERE / 'mcp4-white'
REVIEWS = ROOT / 'components/reviews'
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
rel = lambda p: str(p.relative_to(ROOT))


def write(path, value):
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temp.replace(path)


def main():
    output = OUT / 'component-review.json'
    assert not output.exists()
    paths = {'progress': REVIEWS / 'specification_review_progress.json', 'walkthrough': REVIEWS / 'walkthrough_checkpoint.json',
        'component': ROOT / 'components/checkpoint.json', 'root': ROOT / 'checkpoint.json'}
    docs = {k: read(path) for k,path in paths.items()}
    before = copy.deepcopy(docs)
    digests = {k: sha(path) for k,path in paths.items()}
    p, cp, c = (docs[k] for k in ['progress', 'walkthrough', 'component'])
    assert cp['current_component_id'] == 'BC-MCP-3' and cp['current_answer_recorded']
    assert cp['next_review_after_keep'] == {'component_id': 'BC-MCP-4', 'review_number': 74}
    assert docs['root']['current_component_review'] == c and 'BC-MCP-4' not in p['reviews']
    assert not any(x['component_id'] == 'BC-MCP-4' for x in cp['parallel_owner_reviews'])
    concave_dir = REVIEWS / 'concave-moon-review-2026-10-17'
    old_card_path = concave_dir / 'component-review-25x25.json'
    approval_path = concave_dir / 'specification-approval.json'
    old_card, approved = read(old_card_path), read(approval_path)
    assert approved['proposals_approved'] and not approved['physical_specs_verified']
    assert approved['owner_face_dimensions_cm'] == {'height': 25, 'width': 25}
    assert approved['proposal_source_sha256'] == sha(old_card_path)
    assert len(approved['approved_proposal_ids']) == 6
    assert next(x for x in approved['approved_specification_items'] if x['proposal_id'].endswith('-PRICE'))['value']['proposed_amount'] == 175
    protected = {str(path): sha(path) for path in [REVIEWS / 'user_classifications.json', ROOT / 'components/evidence/component_register.json',
        ROOT / cp['register_workbook'], ROOT / cp['current_review_record'], ROOT / cp['last_identity_approval'],
        ROOT / cp['last_completed_family_first_pass'], approval_path, old_card_path]}
    comparison = read(OUT / 'Concave-MCP4-reference-comparison.json')
    assert comparison['same_depicted_reference_confirmed'] and comparison['visual_comparison_confirmed']
    assert comparison['Concave_cached_original_current_Dropbox_content_hash_verified']
    assert comparison['full_RGB_RMSE_0_255'] < 2 and not comparison['encoded_bytes_equal']
    metadata = {x['requested_id']: x for x in read(OUT / 'selected-metadata.json')['entries']}
    primary_id, closeup_id, folder_id = 'id:cnqzTNngPVsAAAAAAAyjMA', 'id:cnqzTNngPVsAAAAAAAuTug', 'id:cnqzTNngPVsAAAAAAAyiqw'
    primary, folder = metadata[primary_id]['file'], metadata[folder_id]['folder']
    assert primary['path_display'].rsplit('/', 1)[0] == folder['path_display']
    census = read(HERE / 'mcp4-white-initial-census.json')
    assert all(not x['result']['has_more'] and not x['result']['cursor'] for x in census['listings'])
    assert [len(x['result']['entries']) for x in census['listings']] == [7, 1]
    previews = read(OUT / 'preview-cache.json')
    assert len(previews) == 8 and all(sha(Path(x['preview'])) == x['sha256'] for x in previews)
    originals = read(OUT / 'original-download-receipts.json')['entries']
    assert len(originals) == 2
    for entry in originals:
        raw = Path(entry['local_path']).read_bytes()
        assert len(raw) == entry['size'] and hashlib.sha256(raw).hexdigest() == entry['sha256']
        assert hashlib.sha256(b''.join(hashlib.sha256(raw[i:i+4194304]).digest() for i in range(0,len(raw),4194304))).hexdigest() == entry['content_hash']
    maker = read(HERE / 'maker-source-reference.json')
    assert sha(Path(maker['source_local_path'])) == maker['source_sha256']
    row = next(x for x in maker['extracted_rows'] if x['row'] == 44)
    assert row['values']['Product Code A'] == 'MCP4-25x25'
    assert all(sha(Path(path)) == digest for path,digest in maker['labelled_image_sha256'].items())
    model = read(ROOT / 'components/evidence/component_register.json')
    source_component = next(x for x in model['components'] if x['component_id'] == 'BC-MCP-4')
    assert set(['G215','G216','G217','G218','G219','G220']).issubset(source_component['group_refs'])
    links = {x['file_name']:x for x in read(OUT / 'metadata-links.json')['results']}
    series_card = read(HERE / 'mcp3-white/component-review.json')
    old_series = {x['requested_id']:x['file'] for x in read(HERE / 'mcp3-white/selected-metadata.json')['entries'] if 'file' in x}
    for entry in read(OUT / 'series-metadata.json')['entries']:
        if 'file' in entry:
            assert all(entry['file'][k] == old_series[entry['requested_id']][k] for k in ['id','rev','size','path_display'])
    now = datetime.now(timezone.utc).isoformat()
    items = copy.deepcopy(approved['approved_specification_items'])
    for item in items:
        old_id = item['proposal_id']
        item.update({'proposal_id': 'MCP4-WHITE-RELATIONSHIP-' + old_id.rsplit('-',1)[-1],
            'previous_approved_proposal_id': old_id, 'previous_canonical_component_id': 'BC-CONCAVE',
            'previous_canonical_variant_id': 'CM-WHITE-25', 'previous_working_proposal_approved': True,
            'previous_approval_record': rel(approval_path), 'previous_approval_record_sha256': sha(approval_path),
            'owner_approved': False, 'new_specification_approval_inferred': False, 'physical_specs_verified': False,
            'scope_note': 'Previously accepted working value for the matched Concave depiction. Shown for reference; no new MCP4 specification approval requested or inferred.'})
    order = [{'component_id':'BC-MCP-4','review_number':74,'variant_id':'MCP4-WHITE','label':'Concave Moon / MCP4 White relationship'},
        {'component_id':'BC-MCP-4','review_number':74,'variant_id':'MCP4-SILVER','label':'MCP4 Silver; compare with approved Concave Moon Silver and Bronze'},
        {'component_id':'BC-MCP-4','review_number':74,'variant_id':'MCP4-VERDIGRIS','label':'MCP4 Verdigris; compare with approved Concave Moon Verdigris'},
        {'component_id':'BC-MCP-4','review_number':74,'variant_id':'MCP4-VERDIGRIS-RUST','label':'MCP4 Verdigris/Rust; depicted finish review pending'}]
    scope = 'Confirm whether the matched White depiction belongs to the already approved Concave Moon design and retain MCP4 as its series/code. No new independent sculpture, physical cast/mould, inventory, whole-family merge, other-finish approval or changed specification/price is inferred.'
    mapping = {'platform_record_level':{'squarespace_id':None,'shopify_handle':None,'shared_sku':None,
        'status':'EXACT WHITE25 OFFER AND PLATFORM PAIR UNCONFIRMED; O006 IS A SEPARATE SILVER OFFER; O01550CM TITLE/PHOTO CONFLICT REMAINS EXCLUDED'},
        'dropbox_sculpture_level':{'primary_file_id':primary_id,'folder_id':folder_id,'same_picture_Concave_file_id':old_card['primary_image_id'],
            'same_picture_Concave_folder_id':old_card['primary_folder_id'],'same_depicted_reference_confirmed':True,
            'same_encoded_file':False,'clean_image_edit_lineage_verified':False,'same_physical_cast_mould_verified':False},
        'individual_component_level':{'source_component_id':'BC-MCP-4','canonical_component_candidate':'BC-CONCAVE',
            'canonical_variant_candidate':'CM-WHITE-25','owner_relationship_confirmed':False,'new_independent_sale_unit_established':False}}
    coverage = {'complete_individual_clean_reference':True,'native_solo_closeups':True,'uncropped_native_individual_front':False,
        'original_series_reference':True,'exact_series_position':'Bottom right in exact027 and025 photographs',
        'room_presentation_reference':True,'room_reference_file_id':'id:cnqzTNngPVsAAAAAAAyjLw',
        'room_scene_origin_authenticated':False,'verified_client_installation':False,'White_rear_or_fixing_detail':False,
        'clean_image_edit_lineage_verified':False,'scope':'All7 White folder previews and1 White In Situ preview viewed; clean001 and native002 full files verified/viewed. Room reference has unknown origin; it does not establish two physical casts or size.'}
    pending = {'group_refs':['G205','G223'],'scope':'Rust quartet and2+4 member/finish attribution pending separately; no blanket merge from White picture match.'}
    card = {'schema_version':1,'prepared_utc':now,'component_id':'BC-MCP-4','review_number':74,'family':'Moon Crater Phase',
        'review_family_scope':'Moon Crater Phase 4','family_review_number':1,'family_review_total':4,
        'family_total_scope':'Four named finish reference clusters in the frozen model; White and White In Situ audited live. Other finishes and Rust arrangements remain pending. This is not a sculpture, mould or stock count.',
        'size_finish_variant_id':'MCP4-WHITE','proposed_name':'Concave Moon','source_name':'Moon Crater Phase 4 — White (MCP4)',
        'proposed_series_code':'MCP4','candidate_canonical_component_id':'BC-CONCAVE','candidate_canonical_variant_id':'CM-WHITE-25',
        'identity_decision_destination':'component_identity_relationship_decisions','review_decision_mode':'DEPICTED_DESIGN_ALIAS_RELATIONSHIP_ONLY',
        'identity_question':'Keep Concave Moon as the name, with Moon Crater Phase 4 (MCP4) as its series identity?', 'scope':scope,
        'primary_image_id':primary_id,'primary_folder_id':folder_id,'primary_image_link':links[primary_id]['copy_link_url'],
        'primary_folder_link':links[folder_id]['copy_link_url'],'primary_image_scope':'Complete clean reference; same depiction as previously approved Concave White001; different encoded bytes, unknown editing lineage.',
        'original_closeup_id':closeup_id,'original_closeup_link':links[closeup_id]['copy_link_url'],
        'comparison_image_id':old_card['primary_image_id'],'comparison_folder_id':old_card['primary_folder_id'],
        'comparison_image_link':old_card['primary_image_link'],'comparison_folder_link':old_card['primary_folder_link'],
        'series_image_id':series_card['series_image_id'],'series_folder_id':series_card['series_folder_id'],
        'series_image_link':series_card['series_image_link'],'series_folder_link':series_card['series_folder_link'],
        'series_target_position':'Bottom right in exact027 photograph', 'exhibition_image_id':series_card['exhibition_image_id'],
        'exhibition_image_link':series_card['exhibition_image_link'],'exhibition_target_position':'Bottom right in exact025 photograph; venue unverified',
        'room_reference_image_link':links['id:cnqzTNngPVsAAAAAAAyjLw']['copy_link_url'],
        'room_reference_folder_link':links['id:cnqzTNngPVsAAAAAAAyjLg']['copy_link_url'],
        'metadata_checked_utc':read(OUT / 'selected-metadata.json')['checked_utc'],'reference_refresh':rel(OUT / 'selected-metadata.json'),
        'specification_review_items':items,'specification_review_mode':'EXISTING_APPROVED_CONCAVE_WORKING_VALUES_FOR_REFERENCE_ONLY',
        'prior_canonical_specification_approval':rel(approval_path),'new_specification_approval_requested':False,
        'maker_source':rel(HERE / 'maker-source-reference.json'),'maker_row':44,
        'maker_additional_evidence':{'White_standard_face_cm':[25,25],'side_depth_cm':[4,6],'estimated_weight_kg':[2,4],
            'material':'Jesmonite AC730 White Marble Stone finish','fixing':'One small stainless rear fixing centred in upper third, aligned from top across series',
            'scope':'Historical MCP4 White template. Pictured cast composition, depth, mass, actual hardware and load unverified. Does not replace accepted Concave working values.'},
        'platform_mapping':mapping,'photo_coverage':coverage,'pending_arrangement_component_review':pending,
        'identity_confirmed':False,'specifications_approved':False,'physical_specs_verified':False,
        'open_gaps':['Owner MCP4/Concave depicted-design relationship','Actual depth, mass, composition and rear hardware/load',
            'Verified installation and clean-image lineage','Exact White25 platform record and shared SKU','Other-finish identities and Rust arrangement positions'],
        'next_review_after_keep':order[1],'after_current_family_work':'Reconcile queued peer packages and outstanding Moon Crater Rust arrangements; preserve all existing exclusive review allocations.',
        'remote_files_changed':False,'live_platform_records_changed':False}
    write(OUT / 'before-staging.json',{'recorded_utc':now,'files':{rel(paths[k]):v for k,v in before.items()},'protected_sha256':protected})
    write(output,card)
    write(OUT / 'source-audit.json',{'status':'PASS','picture_comparison':rel(OUT / 'Concave-MCP4-reference-comparison.json'),
        'maker_source':card['maker_source'],'maker_row':row,'labelled_maker_image_index':18,'all8_White_previews_viewed':True,
        'two_full_White_originals_verified_and_viewed':True,'existing_Concave_approval_preserved':rel(approval_path),
        'accepted_Concave_working_price_gbp':175,'new_independent_component_or_physical_inventory_inferred':False})
    p['reviews']['BC-MCP-4'] = {'reviewed_utc':now,'review_number':74,'proposed_name':card['proposed_name'],'size_finish_variant_id':'MCP4-WHITE',
        'identity_confirmed':False,'specifications_approved':False,'physical_specs_verified':False,'source_specifications_recorded':True,
        'specification_proposals':[],'existing_canonical_working_values':items,'existing_canonical_approval_record':rel(approval_path),
        'specification_groups_are_new_independent_proposals':False,'review_record':rel(output),'primary_image_id':primary_id,'primary_folder_id':folder_id,
        'platform_mapping':mapping,'photo_coverage':coverage,'gaps':card['open_gaps'],'pending_size_finish_variants':order[1:],
        'pending_arrangement_component_review':pending,'candidate_canonical_component_id':'BC-CONCAVE','owner_relationship_confirmed':False,
        'review_decision_mode':card['review_decision_mode']}
    p['family_review_progress']['Moon Crater Phase 4'] = {'family':'Moon Crater Phase','review_scope':card['family_total_scope'],
        'status':'WHITE_CONCAVE_ALIAS_REVIEW_PENDING','updated_utc':now,'review_reference_cards_answered':0,'review_reference_total':4,
        'reference_total_is_sculpture_count':False,'specifications_complete':False}
    state = 'Awaiting MCP4 White / approved Concave Moon relationship; same clean depiction confirmed; no separate component or changed price inferred'
    cp.update({'current_component_id':'BC-MCP-4','current_review_number':74,'current_size_finish_variant_id':'MCP4-WHITE',
        'current_component_layout_id':None,'proposed_name':card['proposed_name'],'state':state,'current_review_record':rel(output),
        'current_family_review_number':1,'current_family_review_total':4,'active_family':'Moon Crater Phase 4','family_review_order':order,
        'family_first_pass_complete':False,'current_answer_recorded':False,'current_specification_answer_recorded':False,
        'current_dimension_answer_recorded':False,'current_partial_specification_answer_recorded':False,'current_dimension_approval':None,
        'current_owner_face_dimensions_cm':None,'current_identity_relationship_answer_recorded':False,'current_identity_relationship_approval':None,
        'canonical_depicted_name':None,'candidate_canonical_depicted_name':'Concave Moon','current_separate_saleable_design':None,
        'working_version_user_approved':False,'review_decision_mode':card['review_decision_mode'],'question_scope':scope,
        'answer_state':'MCP3 names kept. Concave specifications already accepted for earlier depiction; MCP4 series relationship pending.',
        'primary_image':{'file_id':primary_id,'name':primary['name'],'path_display':primary['path_display'],'copy_link_url':card['primary_image_link'],'open_in_dropbox_url':links[primary_id]['open_in_dropbox_url']},
        'containing_folder':{'folder_id':folder_id,'name':folder['name'],'path_display':folder['path_display'],'copy_link_url':card['primary_folder_link'],'open_in_dropbox_url':links[folder_id]['open_in_dropbox_url']},
        'metadata_checked_utc':card['metadata_checked_utc'],'family_review_evidence':rel(OUT / 'source-audit.json'),
        'displayed_identity_evidence_file_ids':[primary_id,old_card['primary_image_id']],
        'displayed_identity_evidence_folder_ids':[folder_id,old_card['primary_folder_id']],
        'current_component_source_notes':[x['display'] for x in items],'family_counting_note':card['family_total_scope'],
        'next_review_after_keep':order[1],'updated_utc':now})
    c['interactive_review_state'].update({'current_component_id':'BC-MCP-4','review_number':74,'current_size_finish_variant_id':'MCP4-WHITE',
        'current_component_layout_id':None,'current_name':card['proposed_name'],'state':state,'active_family':'Moon Crater Phase 4',
        'family_review_number':1,'family_review_total':4,'specification_proposals_approved':False,
        'working_version_user_approved':False,'review_decision_mode':card['review_decision_mode']})
    c['current_component_review_record']=rel(output)
    c['last_family_media_review']={'family':'Moon Crater Phase','review_scope':'MCP4 White7 plus White In Situ1; existing Concave clean depiction comparison',
        'observed_utc':census['checked_utc'],'files':8,'folders':2,'full_new_originals':2,'evidence':rel(OUT / 'source-audit.json'),'workbook_contains_this_live_media_audit':False}
    c['updated_utc']=p['updated_utc']=now
    docs['root']['current_component_review']=copy.deepcopy(c)
    docs['root']['updated_utc']=now
    assert all(p['reviews'][k]==v for k,v in before['progress']['reviews'].items())
    assert p['offer_photo_bindings']==before['progress']['offer_photo_bindings']
    for key in ['parallel_import_queue','parallel_owner_reviews','parallel_evidence_flags','pending_specification_reviews','next_serialized_parallel_import','last_parallel_import']:
        assert cp[key]==before['walkthrough'][key],key
    assert all(sha(path)==digests[k] for k,path in paths.items()) and all(sha(Path(path))==digest for path,digest in protected.items())
    for key,path in paths.items():
        write(path,docs[key])
        assert read(path)==docs[key]
    validation={'status':'PASS','current_review_mode':card['review_decision_mode'],'same_reference_picture_confirmed':True,
        'existing_Concave_name_face_and_175GBP_working_price_preserved':True,'no_new_sculpture_count_or_specification_approval':True,
        'series_bottom_right_reference_available':True,'all8_White_previews_and2new_originals_viewed':True,
        'prior_approvals_queues_model_workbook_preserved':True,'checkpoint_copies_match':read(paths['root'])['current_component_review']==read(paths['component'])}
    write(OUT / 'review-validation.json',validation)
    print(json.dumps(validation))


if __name__=='__main__':
    main()
