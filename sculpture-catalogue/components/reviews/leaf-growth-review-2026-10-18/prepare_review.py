"""Prepare the individual White Leaf Growth review with exact source and photograph scope."""
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
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    tmp.replace(path)


def main():
    output = HERE / 'component-review.json'
    assert not output.exists(), 'Leaf Growth already prepared'
    paths = {'progress': REVIEWS / 'specification_review_progress.json',
        'walkthrough': REVIEWS / 'walkthrough_checkpoint.json',
        'component': ROOT / 'components/checkpoint.json', 'root': ROOT / 'checkpoint.json'}
    docs = {key: read(path) for key, path in paths.items()}
    before = copy.deepcopy(docs)
    hashes = {key: sha(path) for key, path in paths.items()}
    p, cp, c = (docs[key] for key in ['progress', 'walkthrough', 'component'])
    assert cp['current_size_finish_variant_id'] == 'LEAF-FORM-GOLD' and cp['current_answer_recorded']
    assert cp['next_review_after_keep'] == {'component_id': 'BC-LEAF-GROWTH', 'review_number': 68}
    assert docs['root']['current_component_review'] == c and 'BC-LEAF-GROWTH' not in p['reviews']
    assert not any(x['component_id'] == 'BC-LEAF-GROWTH' for x in cp['parallel_owner_reviews'])
    assert p['family_review_progress']['Leaf Form']['first_pass_reference_review_complete']
    gold_keep = ROOT / cp['last_identity_approval']
    assert read(gold_keep)['user_statement'] == 'Keep “Leaf Form 2 — Gold (LF2)”'
    model_path = ROOT / 'components/evidence/component_register.json'
    model = read(model_path)
    source_component = next(x for x in model['components'] if x['component_id'] == 'BC-LEAF-GROWTH')
    source_offer = next(x for x in model['platform_records'] if x['offer_ref'] == 'O037')
    assert source_offer['sku'] == 'ML-1-100.30' and source_offer['sh_handle'] == 'magnolia-leaves'
    assert source_offer['sq_id'] == '6a555a6eb48e7b64b82e550a'
    assert source_offer['native_parts'] == source_offer['proposed_bom_pieces'] == 1
    protected_paths = [REVIEWS / 'user_classifications.json', model_path, ROOT / cp['register_workbook'], gold_keep,
        ROOT / cp['current_review_record'], ROOT / p['family_review_progress']['Leaf Form']['first_pass_record']]
    protected = {str(path): sha(path) for path in protected_paths}
    census = read(HERE / 'media-census.json')
    assert len(census['listings']) == 5 and all(not row['result']['has_more'] and not row['result']['cursor'] for row in census['listings'])
    assert all(x['object_type'] == 'folder' for x in census['listings'][0]['result']['entries'])
    files = [x for row in census['listings'][1:] for x in row['result']['entries']]
    assert len(files) == 116 and len({x['file_id'] for x in files}) == 116
    image_index = read(HERE / 'image-review-index.json')
    assert len(image_index['cached_previews']) == 116 and len(image_index['contact_sheets']) == 5
    for preview in image_index['cached_previews']:
        assert sha(Path(preview['preview_path'])) == preview['sha256']
    originals = read(HERE / 'download-receipts.json')
    assert len(originals) == 6
    for receipt in originals:
        local = Path(receipt['local_path'])
        assert sha(local) == receipt['sha256'] and local.stat().st_size == receipt['size']
    assert sha(Path(image_index['public_primary']['local_path'])) == image_index['public_primary']['sha256']
    selected = read(HERE / 'selected-metadata.json')
    primary_id, folder_id = 'id:cnqzTNngPVsAAAAAAAsG_Q', 'id:cnqzTNngPVsAAAAAAAyikQ'
    context_id, context_folder_id = 'id:cnqzTNngPVsAAAAAAArqWw', 'id:cnqzTNngPVsAAAAAAAyikg'
    primary = next(x['file'] for x in selected['entries'] if x['requested_id'] == primary_id)
    folder = next(x['result']['folder'] for x in read(HERE / 'folder-metadata.json')['entries'] if x['requested_id'] == folder_id)
    assert primary['path_display'].rsplit('/', 1)[0] == folder['path_display']
    links = {x['file_name']: x for x in read(HERE / 'metadata-links.json')['results']}
    now = datetime.now(timezone.utc).isoformat()
    native_context = next(x for x in originals if x['id'] == context_id)
    comparison_path = HERE / 'listing-image-comparison.json'
    write(comparison_path, {'checked_utc': now, 'source_page': source_offer['source_url'],
        'listing_reference_file_id': context_id, 'listing_reference_folder_id': context_folder_id,
        'public_primary_sha256': image_index['public_primary']['sha256'], 'dropbox_original_sha256': native_context['sha256'],
        'encoded_bytes_equal': image_index['public_primary']['sha256'] == native_context['sha256'],
        'visual_result': 'Same depicted photograph: complete single White leaf panel on the same red display board, with matching relief, background and shadows.',
        'primary_individual_photo_id': primary_id, 'primary_individual_relationship': 'Same depicted design/White appearance in a different brick-wall photograph; exact physical cast equivalence is unconfirmed.',
        'scope': 'Visual photograph/design matching, not a measurement, current stock, binder, mould or physical-cast identity proof.'})
    local_prices = read(HERE / 'local-price-source-check.json')
    for doc in local_prices['documents']:
        assert sha(Path(doc['source_path'])) == doc['source_sha256']
    price_scope_path = HERE / 'dated-price-source-scope.json'
    write(price_scope_path, {'checked_utc': now, 'text_source_check': rel(HERE / 'local-price-source-check.json'),
        'viewed_pages': [rel(HERE / name) for name in ['retail-2025-page2.png', 'trade-2025-page11.png', 't-prices-2025-page2.png']],
        'retail_2025': {'each_face_cm': [100, 30], 'estimated_weight_kg_each': 12, 'price_gbp_each': 750,
            'scope': 'Owner-provided Retail PRICE List2025; single White standard, made to order; extra finishes and delivery/packaging separately quoted.'},
        'trade_2025': {'each_face_cm': [100, 30], 'estimated_weight_kg_each': 12, 'price_gbp_each': 375,
            'source_page': 11, 'scope': 'Owner-provided SCULPTURE TRADE PRICE List2025, single Leaf Growth standard; not current retail.'},
        'illustrative_trade_reference': {'source_page': 5, 'estimated_weight_kg_each': 12, 'price_gbp_each': 375},
        'estimated_T_price_draft': {'source_page': 2, 'estimated_weight_kg_each': 12,
            'stacked_GBP_values': [569.49, 375, 300], 'individual_stack_roles_confirmed': False,
            'scope': 'All three draft figures retained; no retail/trade/cost interpretation assigned to individual stacked values.'},
        'baseline_historic_price_field': source_component['historic_individual_price'],
        'clarification': 'Baseline569.49historic retail label does not replace the owner-provided Retail2025row750. Different dated drafts/pricing classes remain separate. No baseline source is overwritten.',
        'applied_as_current_Gold_or_White_price': False, 'actual_cast_weighing_established': False})
    source_path = HERE / 'source-records.json'
    write(source_path, {'checked_utc': now, 'model_sha256': sha(model_path), 'component': source_component,
        'platform_offer': source_offer, 'native_claims': [x for x in model['claims'] if x['component_id'] == 'BC-LEAF-GROWTH'],
        'source_scope': 'Frozen supplied export evidence; current public text checked separately. No live account/SKU reparse.'})
    public_ref = rel(HERE / 'public-reader-source.json')
    def item(suffix, field, display, value, status, basis, refs):
        return {'proposal_id': 'LEAF-GROWTH-WHITE-' + suffix, 'field': field, 'display': display,
            'value': value, 'status': status, 'basis': basis, 'source_refs': refs,
            'owner_approved': False, 'physical_specs_verified': False}
    items = [
        item('DIMENSIONS', 'Individual dimensions and depth', '100×30×6cm per single panel — public/native listing claim; actual panel unmeasured',
            {'listing_each_cm': [100, 30, 6], 'historical_face_cm': [100, 30], 'actual_measured_cm': None},
            'SOURCE SINGLE-COMPONENT DIMENSIONS; OWNER ADOPTION PENDING',
            'The offer explicitly describes one100×30×6cm sculpture and both price-list types name100×30cm each. Integral leaves belong to one continuous panel; no set total is divided. Photograph scale does not measure the pictured cast.',
            [public_ref, rel(source_path), rel(price_scope_path)]),
        item('WEIGHT', 'Individual dry weight', '18kg Shopify export versus12kg historical estimate — unresolved source difference; actual panel unweighed',
            {'Shopify_variant_grams': 18000, 'Shopify_export_weight_kg': 18, 'historical_estimate_kg_each': 12,
             'Squarespace_raw_weight_units_unencoded': '39.683', 'actual_weighed_kg': None},
            'CONFLICTING PER-PANEL SOURCE VALUES; NOT A MEASURED RANGE',
            'Shopify has explicit18000g for the single offer. Owner-provided2025price lists estimate12kg each. Preserve both without averaging, interpreting the difference as packaging, or presenting12–18kg as a measured range. Squarespace raw units remain unencoded.',
            [rel(source_path), rel(price_scope_path)]),
        item('MATERIAL', 'Material and finish', 'White marble stone finish — listing claim; cast mineral-composite base proposed; actual binder unknown',
            {'listing_finish': 'White marble stone finish', 'proposed_base': 'Cast mineral composite',
             'actual_binder': None, 'reinforcement': None, 'sealer': None, 'care': None},
            'LISTING FINISH; BASE-MATERIAL PROPOSAL UNAPPROVED',
            'Public wording states carved/cast and White marble stone finish. Mineral-composite base is a working proposal. No Leaf Growth-specific maker AC730entry was established; do not import another family binder. Workshop carving/mould images do not certify this finished cast recipe or current mould inventory.',
            [public_ref, rel(source_path), 'id:cnqzTNngPVsAAAAAAAucqg']),
        item('FIXING', 'Fixing', 'Two concealed rear hanging points — proposal; exact hardware, attachment and rated load unknown',
            {'proposed_hanging_points': 2, 'proposed_position': 'Upper back, suitable for the approved hanging orientation',
             'actual_count': None, 'actual_hardware': None, 'rated_load': None},
            'UNAPPROVED FIXING PROPOSAL; NO FINISHED REAR VIEW',
            'Two rear hanging points are a discussion proposal for the tall panel. Two visible pegs beneath the front in the brick-wall photograph are display supports and do not prove rear-fixing count/type. Actual back, attachments, load rating and alternate-orientation compatibility remain unknown.',
            [primary_id, rel(HERE / 'media-census.json')]),
        item('PRICE', 'Individual retail price', '£800 for one White panel — current public listing reference; owner adoption pending',
            {'public_single_price_gbp': 800, 'historical_retail_2025_gbp': 750, 'historical_trade_2025_gbp': 375,
             'owner_individual_price_approved': False},
            'CURRENT PUBLIC SINGLE-OFFER PRICE; NOT OWNER APPROVED',
            'Current public page states800GBP and depicts this individual design. Dated retail750and trade375GBP remain separate source references; neither is averaged with the current price or transferred to Gold. No whole-set price is divided.',
            [public_ref, rel(price_scope_path)]),
        item('AVAILABILITY', 'Availability', 'Made to order / enquire — proposed current policy; stock, reproducibility and lead time unknown',
            {'proposed_policy': 'Made to order / enquire subject to production confirmation', 'physical_stock': None,
             'reproducibility': None, 'lead_time': None, 'historical_white_policy': 'Made to order'},
            'HISTORICAL WHITE POLICY; CURRENT PHYSICAL AVAILABILITY UNVERIFIED',
            'Owner price-list conditions say White standard made to order. Native Unlimited/active and public cart controls do not establish a physical cast, usable current mould, production date or delivery time. Current policy remains an owner-review proposal.',
            [public_ref, rel(price_scope_path), rel(source_path)])]
    coverage = {'complete_individual_front': True, 'native_brick_wall_display': True,
        'indoor_red_board_display': True, 'clean_front_reference': True,
        'verified_client_home_or_garden_installation': False, 'finished_rear': False, 'rear_fixing_detail': False,
        'fixed_multi_component_series_established': False,
        'scope': 'All116files inspected through five contact sheets; six originals and public primary viewed. White has63front/detail files plus25display references.20workshop images are process references, not finished rear/fixing proof. Horizontal and rotated White views preserve the same continuous leaf pattern; no extra component is inferred. Gold has eight detail-only images and is a separate pending finish review.'}
    mapping = {'platform_record_level': {'offer_ref': 'O037', 'squarespace_id': source_offer['sq_id'],
        'shopify_handle': source_offer['sh_handle'], 'shared_sku': source_offer['sku'],
        'status': 'SUPPLIED EXPORT PAIR CONFIRMED THROUGH UNIQUE SHARED SKU'},
        'dropbox_listing_level': {'file_id': context_id, 'folder_id': context_folder_id,
            'status': 'VISUALLY CONFIRMED SAME DEPICTED PUBLIC PRIMARY PHOTOGRAPH; ENCODED BYTES DIFFER',
            'comparison_receipt': rel(comparison_path)},
        'individual_component_level': {'component_id': 'BC-LEAF-GROWTH', 'quantity': 1,
            'integral_leaf_forms_split_into_sale_components': False,
            'whole_set_dimensions_weight_price_transferred': False,
            'physical_cast_equivalence_between_photos_confirmed': False, 'Gold_offer_applicability_confirmed': False},
        'live_Shopify_account_refreshed': False, 'current_native_public_SKUs_reparsed': False}
    family_order = [
        {'component_id': 'BC-LEAF-GROWTH', 'review_number': 68, 'variant_id': 'LEAF-GROWTH-WHITE', 'label': 'Leaf Growth — White (Magnolia Leaves)'},
        {'component_id': 'BC-LEAF-GROWTH', 'review_number': 68, 'variant_id': 'LEAF-GROWTH-WHITE-GOLD',
            'variant_only_review': True, 'label': 'Leaf Growth — White and Gold Leaf; detail-only reference'}]
    card = {'schema_version': 1, 'prepared_utc': now, 'component_id': 'BC-LEAF-GROWTH', 'review_number': 68,
        'family': 'Leaf Growth', 'family_review_number': 1, 'family_review_total': 2,
        'family_total_scope': 'White component and White/Gold finish reference; two review cards do not establish two physical casts or moulds.',
        'size_finish_variant_id': 'LEAF-GROWTH-WHITE', 'proposed_name': family_order[0]['label'],
        'review_decision_mode': 'COMPONENT_NAME_AND_SPECIFICATIONS', 'identity_decision_destination': 'decisions',
        'scope': 'Name/depicted identity of one continuous White leaf-relief panel. The leaves are integral motifs; Gold detail reference is separate. All six source/proposal groups need owner review.',
        'primary_image_id': primary_id, 'primary_folder_id': folder_id,
        'primary_image_link': links[primary_id]['copy_link_url'], 'primary_folder_link': links[folder_id]['copy_link_url'],
        'public_matching_image_id': context_id, 'public_matching_folder_id': context_folder_id,
        'public_matching_image_link': links[context_id]['copy_link_url'],
        'indoor_display_image_id': 'id:cnqzTNngPVsAAAAAAAsS4w',
        'indoor_display_image_link': links['id:cnqzTNngPVsAAAAAAAsS4w']['copy_link_url'],
        'metadata_checked_utc': selected['checked_utc'], 'reference_refresh': rel(HERE / 'selected-metadata.json'),
        'specification_review_items': items, 'platform_mapping': mapping, 'photo_coverage': coverage,
        'identity_confirmed': False, 'specifications_approved': False, 'physical_specs_verified': False,
        'individual_sale_unit': {'quantity': 1, 'description': 'One continuous Leaf Growth/Magnolia Leaves White panel',
            'live_listing_prepared_or_published': False},
        'source_conflicts': ['18kgShopify single-offer export versus12kg2025estimated mass; actual cast unweighed.',
            '800GBPcurrent public retail,750GBPowner Retail2025,375GBPTrade2025 and unqualified T-draft stack remain distinct.',
            'No exact finished-cast binder/rear-fixing record; Gold full-panel/offer relationship unconfirmed.'],
        'open_gaps': ['Owner White name and depicted identity', 'Actual face/depth measurement and resolution of18kgversus12kgmass',
            'Actual binder, reinforcement, sealer and care/weather suitability', 'Finished rear/fixings and rated load',
            'Owner current individual price, physical stock, reproduction and lead time', 'Verified home/garden installation provenance',
            'Gold complete-panel and in-situ images, identity/specifications and exact offer', 'Current physical cast/mould inventory'],
        'next_review_after_keep': family_order[1], 'next_global_component': {'component_id': 'BC-MCP-1', 'review_number': 71},
        'next_global_scope': 'Reviews69–70 remain reserved for the existing Moon/Shellwave owner lane.',
        'remote_files_changed': False, 'live_platform_records_changed': False}
    write(output, card)
    source_files = [HERE / 'media-census.json', HERE / 'metadata-links.json', HERE / 'selected-metadata.json',
        HERE / 'image-review-index.json', HERE / 'public-reader-source.json', HERE / 'local-price-source-check.json',
        source_path, comparison_path, price_scope_path]
    write(HERE / 'source-audit.json', {'status': 'PASS', 'recorded_utc': now,
        'current_file_census': 116, 'folders': 4, 'all_pagination_complete': True, 'previews_inspected': 116,
        'contact_sheets_viewed': 5, 'Dropbox_originals_hash_verified_and_viewed': 6,
        'public_primary_viewed': True, 'relevant_price_PDF_pages_viewed': 3,
        'source_sha256': {rel(path): sha(path) for path in source_files},
        'physical_specification_verification_inferred': False})
    write(HERE / 'before-stage-review.json', {'recorded_utc': now,
        'files': {rel(paths[key]): value for key, value in before.items()}, 'protected_sha256': protected})
    p['reviews']['BC-LEAF-GROWTH'] = {'reviewed_utc': now, 'review_number': 68, 'proposed_name': card['proposed_name'],
        'size_finish_variant_id': card['size_finish_variant_id'], 'identity_confirmed': False,
        'specifications_approved': False, 'physical_specs_verified': False, 'source_specifications_recorded': True,
        'specification_proposals': copy.deepcopy(items), 'primary_image_id': primary_id, 'primary_folder_id': folder_id,
        'review_record': rel(output), 'platform_mapping': mapping, 'photo_coverage': coverage,
        'gaps': card['open_gaps'], 'pending_size_finish_variants': [family_order[1]]}
    p['family_review_progress']['Leaf Growth'] = {'family': 'Leaf Growth', 'status': 'FIRST_PASS_IN_PROGRESS',
        'updated_utc': now, 'review_reference_cards_answered': 0, 'review_reference_total': 2,
        'reference_total_is_sculpture_count': False, 'specifications_complete': False}
    state = 'Awaiting Leaf Growth White/Magnolia Leaves name; all six groups pending,18kgversus12kgunresolved'
    cp.update({'current_component_id': 'BC-LEAF-GROWTH', 'current_review_number': 68,
        'current_size_finish_variant_id': card['size_finish_variant_id'], 'current_component_layout_id': None,
        'proposed_name': card['proposed_name'], 'state': state, 'current_review_record': rel(output),
        'current_family_review_number': 1, 'current_family_review_total': 2, 'active_family': 'Leaf Growth',
        'family_review_order': family_order, 'family_first_pass_complete': False, 'current_answer_recorded': False,
        'current_specification_answer_recorded': False, 'current_dimension_answer_recorded': False,
        'current_partial_specification_answer_recorded': False, 'current_dimension_approval': None,
        'current_owner_face_dimensions_cm': None, 'current_identity_relationship_answer_recorded': False,
        'current_identity_relationship_approval': None, 'canonical_depicted_name': None, 'current_separate_saleable_design': None,
        'working_version_user_approved': False, 'review_decision_mode': card['review_decision_mode'],
        'question_scope': card['scope'], 'answer_state': 'Leaf Form names kept; Leaf Growth White name and six specifications unapproved.',
        'primary_image': {'file_id': primary_id, 'name': primary['name'], 'path_display': primary['path_display'],
            'copy_link_url': card['primary_image_link'], 'open_in_dropbox_url': links[primary_id]['open_in_dropbox_url']},
        'containing_folder': {'folder_id': folder_id, 'name': folder['name'], 'path_display': folder['path_display'],
            'copy_link_url': card['primary_folder_link'], 'open_in_dropbox_url': links[folder_id]['open_in_dropbox_url']},
        'metadata_checked_utc': selected['checked_utc'], 'family_review_evidence': rel(HERE / 'source-audit.json'),
        'displayed_identity_evidence_file_ids': [primary_id], 'displayed_identity_evidence_folder_ids': [folder_id],
        'current_component_source_notes': [x['display'] for x in items], 'family_counting_note': card['family_total_scope'],
        'next_review_after_keep': family_order[1], 'updated_utc': now})
    c['interactive_review_state'].update({'current_component_id': 'BC-LEAF-GROWTH', 'review_number': 68,
        'current_size_finish_variant_id': card['size_finish_variant_id'], 'current_component_layout_id': None,
        'current_name': card['proposed_name'], 'state': state, 'active_family': 'Leaf Growth',
        'family_review_number': 1, 'family_review_total': 2, 'specification_proposals_approved': False,
        'working_version_user_approved': False, 'review_decision_mode': card['review_decision_mode']})
    c['current_component_review_record'] = rel(output)
    c['last_family_media_review'] = {'family': 'Leaf Growth', 'observed_utc': census['checked_utc'],
        'files': 116, 'folders': 4, 'scope': coverage['scope'], 'evidence': rel(HERE / 'source-audit.json'),
        'workbook_contains_this_live_media_audit': False}
    c['updated_utc'] = p['updated_utc'] = now
    docs['root']['current_component_review'] = copy.deepcopy(c)
    docs['root']['updated_utc'] = now
    assert all(p['reviews'][key] == value for key, value in before['progress']['reviews'].items())
    assert p['family_review_progress']['Leaf Form'] == before['progress']['family_review_progress']['Leaf Form']
    for key in ['parallel_import_queue', 'parallel_owner_reviews', 'parallel_evidence_flags', 'pending_specification_reviews']:
        assert cp[key] == before['walkthrough'][key]
    assert len(items) == 6 and all(not x['owner_approved'] for x in items)
    assert all(sha(path) == hashes[key] for key, path in paths.items()), 'Shared writer collision'
    assert all(sha(Path(path)) == digest for path, digest in protected.items())
    for key, path in paths.items():
        write(path, docs[key])
        assert read(path) == docs[key]
    result = {'status': 'PASS', 'current_name': card['proposed_name'], 'all_six_groups_unapproved': True,
        'shared_SKU_platform_match_preserved': True, 'exact_public_photo_visually_matched_to_stable_ID': context_id,
        'one_continuous_sale_component': True, '18kg_and12kg_source_difference_preserved': True,
        'full_family_files_inspected': 116, 'Gold_detail_only_reference_separate': True,
        'ledger_workbook_model_Gold_keep_previous_approvals_and_parallel_reservations_preserved': True,
        'checkpoint_copies_match': read(paths['root'])['current_component_review'] == read(paths['component'])}
    write(HERE / 'review-validation.json', result)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
