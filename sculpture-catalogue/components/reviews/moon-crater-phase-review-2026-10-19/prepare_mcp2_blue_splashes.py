"""Stage the native blue/white/dark MCP2 reference without inheriting a green listing."""
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REVIEWS = ROOT / 'components/reviews'
OUT = HERE / 'mcp2-blue-splashes'
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
rel = lambda p: str(p.relative_to(ROOT))


def write(p, j):
    p.parent.mkdir(parents=True, exist_ok=True)
    t = p.with_name(p.name + '.tmp')
    t.write_text(json.dumps(j, ensure_ascii=False, indent=2) + '\n')
    t.replace(p)


def main():
    output = OUT / 'component-review.json'
    assert not output.exists()
    paths = {'progress': REVIEWS / 'specification_review_progress.json', 'walkthrough': REVIEWS / 'walkthrough_checkpoint.json',
        'component': ROOT / 'components/checkpoint.json', 'root': ROOT / 'checkpoint.json'}
    docs = {k: read(p) for k, p in paths.items()}; before = copy.deepcopy(docs)
    hashes = {k: sha(p) for k, p in paths.items()}
    p, cp, c = (docs[k] for k in ['progress', 'walkthrough', 'component'])
    assert cp['current_component_id'] == 'BC-MCP-2' and cp['current_size_finish_variant_id'] == 'MCP2-WHITE'
    assert cp['current_answer_recorded'] and cp['next_review_after_keep']['variant_id'] == 'MCP2-BLUE-SPLASHES'
    assert read(ROOT / cp['last_identity_approval'])['user_statement'] == 'Keep “Moon Crater Phase 2 — White (MCP2)”'
    assert docs['root']['current_component_review'] == c
    parent = p['reviews']['BC-MCP-2']; vid = 'MCP2-BLUE-SPLASHES'
    assert parent['identity_confirmed'] and vid not in parent.get('size_finish_variants', {})
    protected_paths = [REVIEWS / 'user_classifications.json', ROOT / 'components/evidence/component_register.json',
        ROOT / cp['register_workbook'], ROOT / cp['current_review_record'], ROOT / cp['last_identity_approval'],
        HERE / 'mcp1-known-reference-first-pass.json']
    protected = {str(x): sha(x) for x in protected_paths}
    census, metadata = read(OUT / 'current-census.json'), read(OUT / 'selected-metadata.json')
    assert not census['result']['has_more'] and not census['result']['cursor'] and len(census['result']['entries']) == 6
    old_census = next(x['result'] for x in read(HERE / 'mcp2-initial-census.json')['listings'] if x['path'].endswith('/Moon Crater Phase 2 Blue Splashes'))
    assert {x['file_id']: (x['name'], x['file']['size']) for x in census['result']['entries']} == {x['file_id']: (x['name'], x['file']['size']) for x in old_census['entries']}
    previews = read(OUT / 'preview-cache.json')
    assert len(previews) == 6 and all(sha(Path(x['preview'])) == x['sha256'] for x in previews)
    originals = read(OUT / 'original-download-receipts.json')['entries']
    assert len(originals) == 2
    for x in originals:
        raw = Path(x['local_path']).read_bytes()
        assert len(raw) == x['size'] and sha(Path(x['local_path'])) == x['sha256']
        assert hashlib.sha256(b''.join(hashlib.sha256(raw[i:i+4194304]).digest() for i in range(0, len(raw), 4194304))).hexdigest() == x['content_hash']
    primary_id, angled_id, folder_id = 'id:cnqzTNngPVsAAAAAAAyg2Q', 'id:cnqzTNngPVsAAAAAAAyg2w', 'id:cnqzTNngPVsAAAAAAAyg1w'
    primary = next(x['file'] for x in metadata['entries'] if x['requested_id'] == primary_id)
    folder = next(x['result']['folder'] for x in read(HERE / 'mcp2-white/keep-current-reference.json')['metadata']['entries'] if x['requested_id'] == folder_id)
    assert primary['path_display'].rsplit('/', 1)[0] == folder['path_display']
    links = {x['file_name']: x for x in read(OUT / 'metadata-links.json')['results']}
    maker = read(HERE / 'maker-source-reference.json')
    assert sha(Path(maker['source_local_path'])) == maker['source_sha256']
    model = read(ROOT / 'components/evidence/component_register.json')
    related = next(x for x in model['platform_records'] if x['offer_ref'] == 'O008')
    cached = read(OUT / 'cached-public-primary-reference.json')
    assert sha(Path(cached['image_path'])) == cached['image_sha256']
    now = datetime.now(timezone.utc).isoformat()
    public = {'observed_utc': now, 'url': related['source_url'], 'offer_ref': 'O008',
        'source_record_title': related['title'], 'squarespace_id': related['sq_id'], 'sku': related['sku'],
        'shopify_handle': None, 'observed_reader_price_gbp': 350, 'observed_reader_dimensions_cm': [25, 25, 6],
        'observed_reader_material_description': 'Hand-painted faux verdigris on copper',
        'web_reader_freshness': 'Reader page marked crawled3months ago; not a verified current account/price/stock capture',
        'normal_page_get_status': read(OUT / 'public-page-normal-get.json')['status'],
        'reader_primary_image_click_status': '404false; not proof a private Dropbox file is missing',
        'cached_primary_photo_source': rel(OUT / 'cached-public-primary-reference.json'),
        'cached_primary_photo_snapshot_date': '2026-10-16',
        'cached_primary_photo_sha256': cached['image_sha256'],
        'visual_finding': 'Source primary IMG_6177shows turquoise/green and rust-brown MCP2relief. Its pattern matches the previously viewed MCP2Verdigris/Rust front, not the blue/white/dark markings in the present Blue Splashes originals. Historical native image binding also points into the Verdigris/Rust folder.',
        'cached_photo_visual_comparison_only': True, 'encoded_original_identity_verified': False,
        'Blue_Splashes_exact_listing_match_confirmed': False,
        'do_not_transfer_to_Blue_Splashes': ['Copper/verdigris material claim', 'Exact photographed item', 'Current price or stock'],
        'price_proposal_scope': '350GBPmay be considered only as an unapproved related-coloured-MCP2reference; no Blue-specific price has been established.'}
    public_path = OUT / 'related-offer-finish-mismatch.json'; write(public_path, public)
    maker_ref, dated_ref = rel(HERE / 'maker-source-reference.json'), rel(HERE / 'dated-price-source-scope.json')
    fields = [
        ('DIMENSIONS', 'Individual dimensions and depth', '25 × 25 cm, approximately6cm deep — conditional White-standard estimate; actual Blue panel unmeasured',
         {'proposed_face_cm': [25, 25], 'proposed_depth_cm': 6, 'historical_White_depth_cm': [4, 6], 'actual_measured_cm': None},
         'CONDITIONAL SAME-DESIGN WHITE-TEMPLATE ESTIMATE',
         'Historical maker row42gives one White MCP2cast25×25cm with4–6cm side depth. Use this as an explicit same-design estimate for Blue only; the photographs have no calibrated scale. Related listing25×25×6cm has a different pictured finish. No set dimensions divided.', [maker_ref, dated_ref, rel(public_path)]),
        ('WEIGHT', 'Individual dry weight', 'Approximately4kg — conditional estimate from the White standard; actual Blue panel unweighed',
         {'proposed_dry_weight_kg': 4, 'related_White_maker_estimate_kg': [2, 4], 'related_White_trade_2025_estimate_kg': 4,
          'related_White_retail_2025_estimate_kg': 5, 'actual_weighed_kg': None},
         'CONDITIONAL CONSTRUCTION ANALOGY; SOURCE DIFFERENCES RETAINED',
         '4kg is a working estimate conditional on similar size and construction to the White standard. Maker2–4kg, trade4kg and retail5kg remain separate dated White estimates. No measured range, set-weight division or conversion from raw unit-unencoded8.8is established.', [maker_ref, dated_ref]),
        ('MATERIAL', 'Material and finish', 'Cast mineral composite, possibly JesmoniteAC730, with painted blue, white and dark markings — composition unconfirmed',
         {'proposed_substrate': 'Cast mineral composite; Jesmonite AC730 is a White-standard analogy only',
          'visible_finish': 'Blue, light blue, white/off-white and dark surface markings', 'actual_binder': None,
          'paint_type': None, 'sealer': None, 'reinforcement': None, 'outdoor_suitability': None},
         'VISIBLE PAINTED APPEARANCE PLUS CONDITIONAL SUBSTRATE GUESS',
         'Native001and003show a textured cast relief with applied multicolour markings. Images do not establish binder, paint chemistry, reinforcement, sealer or weather suitability. Related offer copper/verdigris description is not applied to this blue/white/dark panel.', [primary_id, angled_id, maker_ref, rel(public_path)]),
        ('FIXING', 'Fixing', 'One rear wall fixing centred in the upper third — proposal from the White maker instruction; Blue rear unseen',
         {'proposed_count': 1, 'proposed_position': 'Centre of upper third, aligned from top edge',
          'historical_White_instruction': 'One small stainless-steel fixing', 'actual_Blue_hardware': None,
          'actual_attachment': None, 'rated_load': None},
         'HISTORICAL WHITE INSTRUCTION USED AS A PROPOSAL ONLY',
         'All six Blue references show front/side views or a clean front. No Blue rear or fixing detail is present. Do not transfer the unpaired MCP1coloured rear plate or assume the White stainless instruction proves this cast hardware.', [maker_ref]),
        ('PRICE', 'Individual retail price', '£350 per panel — unapproved proposal using a related coloured-MCP2listing reference; exact Blue offer unconfirmed',
         {'proposed_price_gbp': 350, 'related_reader_price_gbp': 350, 'exact_Blue_offer_price_gbp': None, 'costing_verified': False},
         'RELATED-COLOURED-OFFER PRICE REFERENCE; BLUE-SPECIFIC PRICE UNESTABLISHED',
         'The supplied Squarespace title includesBlue and the reader shows350GBP, but its source photograph and description refer to verdigris/rust.350GBPis therefore only a discussion proposal for this panel. It is not a confirmed Blue selling price and no quartet price is divided.', [rel(public_path)]),
        ('AVAILABILITY', 'Availability', 'Made to order / enquiry — proposal; stock, usable mould, finish reproducibility and lead time unknown',
         {'proposed_policy': 'Made to order / enquiry subject to production confirmation', 'physical_stock': None,
          'mould_condition': None, 'finish_reproducibility': None, 'lead_time': None},
         'PROPOSED POLICY; CURRENT PRODUCTION AND STOCK UNVERIFIED',
         'Product photographs show the design/finish reference, not current stock, usable mould, repeatable painted pattern or delivery time. Related cart/Unlimitedflags do not establish Blue availability.', [dated_ref, rel(public_path)])]
    items = [{'proposal_id': vid + '-' + suffix, 'field': field, 'display': display, 'value': value,
        'status': status, 'basis': basis, 'source_refs': refs, 'owner_approved': False, 'physical_specs_verified': False}
        for suffix, field, display, value, status, basis, refs in fields]
    mapping = {'platform_record_level': {'squarespace_id': None, 'shopify_handle': None, 'shared_sku': None,
        'status': 'EXACT BLUE SPLASHES OFFER AND PLATFORM PAIR UNCONFIRMED'},
        'related_offer_title_and_finish_mismatch': {'offer_ref': 'O008', 'squarespace_id': related['sq_id'],
            'sku': related['sku'], 'title': related['title'], 'shopify_handle': None,
            'native_bound_file_id': related['image_file_id'], 'native_bound_folder_id': related['image_folder_id'],
            'source_photo_finish': 'Verdigris/Rust', 'not_an_exact_Blue_match': True, 'review': rel(public_path)},
        'dropbox_sculpture_level': {'primary_file_id': primary_id, 'folder_id': folder_id, 'angled_file_id': angled_id,
            'status': 'NATIVE COMPLETE BLUE REFERENCE; MCP2FOLDER/WHITE-DESIGN COMPARISON; OWNER IDENTITY PENDING',
            'same_physical_cast_between_views_verified': False},
        'individual_component_level': {'component_id': 'BC-MCP-2', 'quantity': 1,
            'whole_set_dimensions_weight_or_price_transferred': False}}
    coverage = {'complete_individual_native_front': True, 'native_side_view': True, 'clean_complete_reference': True,
        'clean_image_edit_lineage_verified': False, 'product_on_stone_wall_photo': True,
        'wider_room_or_garden_installation_reference': False, 'verified_client_installation': False,
        'matching_finish_series_arrangement': False, 'Blue_finished_rear': False, 'Blue_fixing_detail': False,
        'scope': 'All6current previews viewed, including five native product views and one clean reference. Native001and003full originals independently hash-verified and viewed. Wider installation, series and rear/fixing photographs not found in this finish folder.'}
    gaps = ['Owner Blue Splashes name and depicted MCP2identity', 'Actual face/depth, dry mass and applicable construction',
        'Paint/binder/sealer/finish reproducibility and care', 'Actual Blue rear hardware/attachment/load',
        'Approved Blue-specific price, stock, usable mould and lead time', 'Exact Blue Squarespace offer/shared SKU/Shopify handle',
        'Wider installation, matching-finish series and rear/fixing photographs; clean-image lineage']
    card = {'schema_version': 1, 'prepared_utc': now, 'component_id': 'BC-MCP-2', 'review_number': 72,
        'family': 'Moon Crater Phase', 'review_family_scope': 'Moon Crater Phase 2', 'family_review_number': 2, 'family_review_total': 3,
        'family_total_scope': cp['family_counting_note'], 'size_finish_variant_id': vid,
        'proposed_name': 'Moon Crater Phase 2 — Blue Splashes (MCP2)',
        'identity_decision_destination': 'size_finish_variant_decisions', 'review_decision_mode': 'FINISH_NAME_AND_DEPICTED_IDENTITY_ONLY',
        'scope': 'One Blue Splashes MCP2panel reference; separate from White and Verdigris/Rust. Name approval does not approve six conditional specification groups or an exact platform offer.',
        'primary_image_id': primary_id, 'primary_folder_id': folder_id,
        'primary_image_link': links[primary_id]['copy_link_url'], 'primary_folder_link': links[folder_id]['copy_link_url'],
        'primary_image_scope': 'Complete native individual product photograph on stone wall',
        'angled_image_id': angled_id, 'angled_image_link': links[angled_id]['copy_link_url'],
        'metadata_checked_utc': metadata['checked_utc'], 'reference_refresh': rel(OUT / 'selected-metadata.json'),
        'specification_review_items': items, 'platform_mapping': mapping, 'photo_coverage': coverage,
        'pending_arrangement_component_review': copy.deepcopy(parent['pending_arrangement_component_review']),
        'identity_confirmed': False, 'specifications_approved': False, 'physical_specs_verified': False,
        'individual_sale_unit': {'quantity': 1, 'description': 'One MCP2Blue Splashes panel', 'live_listing_prepared_or_published': False},
        'open_gaps': gaps, 'next_review_after_keep': {'component_id': 'BC-MCP-2', 'review_number': 72,
            'variant_id': 'MCP2-VERDIGRIS-RUST', 'variant_only_review': True, 'label': 'Moon Crater Phase 2 — Verdigris and Rust (MCP2)'},
        'next_global_component': {'component_id': 'BC-MCP-3', 'review_number': 73},
        'remote_files_changed': False, 'live_platform_records_changed': False}
    write(OUT / 'before-staging.json', {'recorded_utc': now,
        'files': {rel(paths[k]): value for k, value in before.items()}, 'protected_sha256': protected})
    write(output, card)
    write(OUT / 'source-audit.json', {'scope': 'MCP2Blue Splashes six-file finish folder only',
        'census': rel(OUT / 'current-census.json'), 'previews_viewed': 6, 'full_originals_viewed': [primary_id, angled_id],
        'hash_receipts': rel(OUT / 'original-download-receipts.json'), 'maker_White_template': rel(HERE / 'maker-source-reference.json'),
        'maker_row': 42, 'White_source_and_owner_name_approval': rel(HERE / 'mcp2-white/identity-approval.json'),
        'all_White_specifications_still_unapproved': True, 'related_offer_finish_mismatch': rel(public_path),
        'component_and_photo_inventory_not_inferred_from_six_files': True})
    parent.setdefault('size_finish_variants', {})[vid] = {'proposed_name': card['proposed_name'], 'size_finish_variant_id': vid,
        'identity_confirmed': False, 'specifications_approved': False, 'physical_specs_verified': False,
        'review_record': rel(output), 'reviewed_utc': now, 'primary_image_id': primary_id, 'primary_folder_id': folder_id,
        'specification_proposals': copy.deepcopy(items), 'platform_mapping': mapping, 'photo_coverage': coverage, 'gaps': gaps}
    state = 'Awaiting MCP2Blue Splashes name; all six groups unapproved; related Blue-title listing depicts another finish'
    cp.update({'current_size_finish_variant_id': vid, 'proposed_name': card['proposed_name'], 'state': state,
        'current_review_record': rel(output), 'current_family_review_number': 2, 'current_family_review_total': 3,
        'current_answer_recorded': False, 'current_specification_answer_recorded': False, 'current_dimension_answer_recorded': False,
        'current_partial_specification_answer_recorded': False, 'working_version_user_approved': False,
        'review_decision_mode': card['review_decision_mode'], 'question_scope': card['scope'],
        'answer_state': 'MCP2White name saved; Blue finish name and all six specification groups unapproved.',
        'primary_image': {'file_id': primary_id, 'name': primary['name'], 'path_display': primary['path_display'],
            'copy_link_url': card['primary_image_link'], 'open_in_dropbox_url': links[primary_id]['open_in_dropbox_url']},
        'containing_folder': {'folder_id': folder_id, 'name': folder['name'], 'path_display': folder['path_display'],
            'copy_link_url': card['primary_folder_link'], 'open_in_dropbox_url': links[folder_id]['open_in_dropbox_url']},
        'metadata_checked_utc': metadata['checked_utc'], 'family_review_evidence': rel(OUT / 'source-audit.json'),
        'displayed_identity_evidence_file_ids': [primary_id], 'displayed_identity_evidence_folder_ids': [folder_id],
        'current_component_source_notes': [x['display'] for x in items], 'next_review_after_keep': card['next_review_after_keep'], 'updated_utc': now})
    c['interactive_review_state'].update({'current_size_finish_variant_id': vid, 'current_name': card['proposed_name'],
        'state': state, 'family_review_number': 2, 'family_review_total': 3, 'specification_proposals_approved': False,
        'working_version_user_approved': False, 'review_decision_mode': card['review_decision_mode']})
    c['current_component_review_record'] = rel(output)
    c['last_family_media_review'] = {'family': 'Moon Crater Phase', 'review_scope': 'MCP2Blue Splashes only',
        'observed_utc': census['checked_utc'], 'files': 6, 'folders': 1, 'full_new_originals': 2,
        'evidence': rel(OUT / 'source-audit.json'), 'workbook_contains_this_live_media_audit': False}
    c.setdefault('additional_review_evidence', []).append({'scope': 'O008Blue title versus Verdigris/Rust source-photo mismatch',
        'evidence': rel(public_path), 'recorded_utc': now})
    c['updated_utc'] = p['updated_utc'] = now
    docs['root']['current_component_review'] = copy.deepcopy(c); docs['root']['updated_utc'] = now
    expected_parent = copy.deepcopy(before['progress']['reviews']['BC-MCP-2'])
    expected_parent.setdefault('size_finish_variants', {})[vid] = parent['size_finish_variants'][vid]
    assert parent == expected_parent
    assert all(p['reviews'][k] == value for k, value in before['progress']['reviews'].items() if k != 'BC-MCP-2')
    assert p['family_review_progress'] == before['progress']['family_review_progress']
    for k in ['parallel_import_queue', 'parallel_owner_reviews', 'parallel_evidence_flags', 'pending_specification_reviews',
              'next_serialized_parallel_import', 'last_parallel_import']:
        assert cp[k] == before['walkthrough'][k], k
    assert all(sha(path) == hashes[k] for k, path in paths.items())
    assert all(sha(Path(path)) == digest for path, digest in protected.items())
    for k, path in paths.items():
        write(path, docs[k]); assert read(path) == docs[k]
    result = {'status': 'PASS', 'current_name': card['proposed_name'], 'all_six_groups_unapproved': True,
        'complete_native_front_selected': True, 'previews_viewed': 6, 'hash_verified_full_originals_viewed': 2,
        'White_approval_and_all_previous_reviews_preserved': True, 'related_offer_finish_mismatch_recorded': True,
        'exact_Blue_platform_pair_unconfirmed': True, 'in_situ_series_rear_photo_gaps_recorded': True,
        'queues_reservations_ledger_model_and_workbook_preserved': True,
        'checkpoint_copies_match': read(paths['root'])['current_component_review'] == read(paths['component'])}
    write(OUT / 'review-validation.json', result); print(json.dumps(result))


if __name__ == '__main__':
    main()
