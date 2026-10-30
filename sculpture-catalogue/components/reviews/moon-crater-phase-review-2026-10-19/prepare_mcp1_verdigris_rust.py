"""Stage the individual MCP1 coloured reference with six conditional specification groups."""
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


def write(p, j):
    p.parent.mkdir(parents=True, exist_ok=True)
    t = p.with_name(p.name + '.tmp')
    t.write_text(json.dumps(j, ensure_ascii=False, indent=2) + '\n')
    t.replace(p)


def main():
    output = HERE / 'mcp1-verdigris-rust/component-review.json'
    assert not output.exists()
    paths = {'progress': REVIEWS / 'specification_review_progress.json',
        'walkthrough': REVIEWS / 'walkthrough_checkpoint.json',
        'component': ROOT / 'components/checkpoint.json', 'root': ROOT / 'checkpoint.json'}
    docs = {k: read(p) for k, p in paths.items()}
    before = copy.deepcopy(docs)
    hashes = {k: sha(p) for k, p in paths.items()}
    p, cp, c = (docs[k] for k in ['progress', 'walkthrough', 'component'])
    assert cp['current_component_id'] == 'BC-MCP-1' and cp['current_size_finish_variant_id'] == 'MCP1-WHITE'
    assert cp['current_answer_recorded'] and docs['root']['current_component_review'] == c
    assert read(ROOT / cp['last_identity_approval'])['user_statement'] == 'Keep “Moon Crater Phase 1 — White (MCP1)”'
    assert cp['next_review_after_keep']['variant_id'] == 'MCP1-VERDIGRIS-RUST'
    target = p['reviews']['BC-MCP-1']
    assert target['identity_confirmed'] and target['canonical_name'] == 'Moon Crater Phase 1 — White (MCP1)'
    assert 'MCP1-VERDIGRIS-RUST' not in target.get('size_finish_variants', {})
    protected_paths = [REVIEWS / 'user_classifications.json', ROOT / 'components/evidence/component_register.json',
        ROOT / cp['register_workbook'], ROOT / cp['current_review_record'], ROOT / cp['last_identity_approval'],
        ROOT / 'components/reviews/parallel-import-2026-10-19-batch7/import-receipt.json',
        ROOT / 'components/reviews/parallel-import-2026-10-19-batch7/independent-shared-readback.json']
    protected = {str(x): sha(x) for x in protected_paths}
    fresh = read(HERE / 'owner-keep-current-reference.json')
    metadata = {x['requested_id']: x['result'] for x in fresh['metadata']['entries']}
    primary_id, rear_id, folder_id = 'id:cnqzTNngPVsAAAAAAAygZw', 'id:cnqzTNngPVsAAAAAAAygbg', 'id:cnqzTNngPVsAAAAAAAygcA'
    primary, rear, folder = metadata[primary_id]['file'], metadata[rear_id]['file'], metadata[folder_id]['folder']
    for file in [primary, rear]:
        expected = next(x['file'] for x in read(HERE / 'selected-metadata.json')['entries'] if x['requested_id'] == file['id'])
        assert all(file[k] == expected[k] for k in ['id', 'rev', 'size', 'path_display'])
        assert file['path_display'].rsplit('/', 1)[0] == folder['path_display']
    listing = fresh['verdigris_rust_listing']
    assert not listing['has_more'] and not listing['cursor'] and len(listing['entries']) == 12
    old = next(x['result'] for x in read(HERE / 'media-census.json')['listings'] if x['path'].endswith('/Moon Crater Phase 1 Verdigris Rust'))
    assert {x['file_id']: (x['name'], x['file']['size']) for x in listing['entries']} == {x['file_id']: (x['name'], x['file']['size']) for x in old['entries']}
    for file in [primary, rear]:
        receipt = next(x for x in read(HERE / 'download-receipts.json') if Path(x['local_path']).name == file['name'])
        assert sha(Path(receipt['local_path'])) == receipt['sha256'] and Path(receipt['local_path']).stat().st_size == file['size']
    links = {x['file_name']: x for x in read(HERE / 'metadata-links.json')['results']}
    now = datetime.now(timezone.utc).isoformat()
    maker, dated = rel(HERE / 'maker-source-reference.json'), rel(HERE / 'dated-price-source-scope.json')
    public = {'observed_utc': now, 'method': 'Public web reader; page marked crawled today',
        'url': 'https://boldstonesculpture.com/buy/p/moon-crater-phase-verdigris-spherical-wall-sculpture',
        'observed_listing_fields': {'retail_price_gbp': 150, 'dimensions_cm': [25, 25, 6],
            'finish_description': 'Hand-painted faux verdigris on copper', 'geometry_description': 'Spherical convex relief'},
        'primary_image_url': 'https://images.squarespace-cdn.com/content/v1/66abcbd768fd043d92325d96/ea4f8e9b-3efb-4a10-8b7f-69093de80378/IMG_6168.jpeg',
        'normal_page_get_status': 403, 'normal_primary_image_get_status': 200,
        'public_primary_image_sha256': sha(HERE / 'public-o007/IMG_6168.jpeg'),
        'visual_comparison': 'Recovered full primary photograph has a different surface pattern/composition from reviewed MCP1native002. The additional MCP2native003comparison also does not establish an exact photograph match. No exact public-to-Dropbox photo binding or physical cast identity certified.',
        'photo_binding_status': 'EXACT PHOTO AND FINISH-OFFER BINDING PENDING',
        'targeted_followup': 'MCP2Verdigris/Rust folder census21files and one original inspected; generic unnumbered Verdigris/Rust folder empty. This is not a full review of the remaining family folders.',
        'stock_and_Shopify_account_verified': False}
    public_path = HERE / 'public-o007/current-public-source-observations.json'
    write(public_path, public)
    def item(suffix, field, display, value, status, basis, refs):
        return {'proposal_id': 'MCP1-VERDIGRIS-RUST-' + suffix, 'field': field,
            'display': display, 'value': value, 'status': status, 'basis': basis,
            'source_refs': refs, 'owner_approved': False, 'physical_specs_verified': False}
    items = [
        item('DIMENSIONS', 'Individual dimensions and depth',
            '25 × 25 cm, approximately6cm deep — conditional estimate; historical White MCP1side depth4–6cm',
            {'proposed_face_cm': [25, 25], 'proposed_depth_cm': 6, 'historical_White_depth_cm': [4, 6], 'actual_measured_cm': None},
            'CONDITIONAL SAME-DESIGN WHITE-TEMPLATE ESTIMATE',
            'Use the labelled historical MCP1individual25×25cm standard and4–6cm depth only as a conditional size template for this green/rust reference. The related public25×25×6cm claim has no exact photo binding and is not a measurement of this panel. No set dimension divided.', [maker, dated, rel(public_path)]),
        item('WEIGHT', 'Individual dry weight',
            'Approximately4kg — conditional White-standard estimate; actual coloured panel unweighed',
            {'proposed_dry_weight_kg': 4, 'related_White_maker_estimate_kg': [2, 4],
                'related_White_trade_2025_estimate_kg': 4, 'related_White_retail_2025_estimate_kg': 5, 'actual_weighed_kg': None},
            'CONDITIONAL WHITE-CONSTRUCTION ANALOGY; SEPARATE SOURCES RETAINED',
            '4kg is a discussion estimate conditional on similar geometry and construction to the White standard. Maker2–4kg calculation, trade4kg and retail5kg remain separate historical White estimates; no average, actual coloured mass or pounds conversion from unit-unencoded8.8is established.', [maker, dated]),
        item('MATERIAL', 'Material and finish',
            'Cast mineral composite, possibly JesmoniteAC730, with verdigris-green and rust effects — substrate and finish recipe unconfirmed',
            {'proposed_substrate': 'Cast mineral composite; Jesmonite AC730 is a White-standard analogy only',
                'visible_finish': 'Blue/green and rust-brown surface effect', 'actual_binder': None,
                'actual_copper_or_iron_content': None, 'sealer': None, 'exposure_suitability': None},
            'VISIBLE APPEARANCE PLUS CONDITIONAL WHITE-SUBSTRATE ANALOGY',
            'The front and rear references suggest a cast panel with applied colour, but images do not establish AC730, metal content, a chemical patina or wet/outdoor suitability. The related publicfaux-verdigris-on-copper description is a listing claim with unresolved exact photo binding.', [primary_id, rear_id, maker, rel(public_path)]),
        item('FIXING', 'Fixing',
            'One keyhole-like rear plate visible on candidate rear011; exact front/back pairing, alloy, attachment and load unknown',
            {'candidate_rear_file_id': rear_id, 'observed_plate_count': 1,
                'observed_type': 'Rectangular gold-coloured keyhole-like plate', 'observed_position': 'Centre of upper third',
                'front_back_same_cast_verified': False, 'actual_metal': None, 'rated_load': None},
            'ACTUAL VISIBLE CANDIDATE REAR; PAIRING AND ENGINEERING DETAILS UNVERIFIED',
            '011is a real rear reference in this finish folder, with one plate, not an inference of unseen hardware. Folder proximity does not prove it is the back of002. The White maker stainless instruction does not certify this gold-coloured plate. No hardware is transferred to White.', [rear_id, maker]),
        item('PRICE', 'Individual retail price',
            '£150 per panel — unapproved proposal using a related coloured-series retail reference; exact offer unconfirmed',
            {'proposed_price_gbp': 150, 'related_public_offer_price_gbp': 150,
                'exact_MCP1_verdigris_rust_offer_price_gbp': None, 'costing_verified': False},
            'UNAPPROVED INDIVIDUAL PRICE PROPOSAL FROM RELATED OFFER',
            'Current public reader shows150GBPfor the related convex verdigris listing, but its exact Dropbox photo/finish binding is unresolved.150GBPis a discussion proposal for this one panel, not a confirmed price or a fraction of a quartet price.', [rel(public_path), dated]),
        item('AVAILABILITY', 'Availability',
            'Made to order / enquire — proposal; stock, usable mould, reproducibility and lead time unknown',
            {'proposed_policy': 'Made to order / enquiry subject to production confirmation',
                'physical_stock': None, 'mould_condition': None, 'finish_reproducibility': None, 'lead_time': None},
            'PROPOSED SALE POLICY; CURRENT PRODUCTION UNVERIFIED',
            'Images and a related AddToCart control do not establish a ready-to-sell cast, usable mould, reproducible finish or delivery date. Historical White made-to-order conditions are context only.', [dated, rel(public_path)])]
    mapping = {'platform_record_level': {'candidate_offer_ref': 'O007',
        'squarespace_id': '6a413a26870e0e6bc1e0e00c', 'candidate_sku': 'SQ6715979',
        'shopify_handle': None, 'confirmed_shared_sku': None,
        'status': 'RELATED SQUARESPACE-ONLY OFFER; NO CONFIRMED SHOPIFY PAIR OR EXACT FINISH-OFFER BINDING'},
        'dropbox_sculpture_level': {'primary_file_id': primary_id, 'folder_id': folder_id,
            'candidate_rear_file_id': rear_id, 'public_photo_match_confirmed': False,
            'status': 'MCP1FOLDER AND WHITE-DESIGN COMPARISON; OWNER FINISH IDENTITY PENDING',
            'same_physical_cast_between_front_rear_or_public_images_verified': False},
        'individual_component_level': {'component_id': 'BC-MCP-1', 'quantity': 1,
            'whole_quartet_dimensions_weight_or_price_transferred': False}, 'public_source': rel(public_path)}
    coverage = {'complete_individual_original_front': True, 'native_detail_and_side_views': True,
        'clean_complete_reference': True, 'clean_image_edit_lineage_verified': False,
        'candidate_rear_reference': True, 'rear_paired_to_selected_front': False,
        'in_situ_room_references': 5, 'verified_client_installation': False,
        'matching_finish_series_arrangement_identified': False,
        'scope': '12finish files inspected plus5separate room references previously reviewed; fresh finish census unchanged. Room-composite/source history unverified. Rust quartet exists but exact MCP1member/finish binding remains pending.'}
    gaps = ['Owner Verdigris and Rust finish name and depicted MCP1identity',
        'Actual dimensions/depth, dry mass and applicable binder/finish/sealer',
        'Front/back cast pairing and actual hardware/attachment/load',
        'Approved individual price, stock, mould condition, reproducibility and lead time',
        'Exact Squarespace photo/finish mapping, shared SKU and Shopify handle',
        'Authenticated installation and matching-finish series photographs; clean-image lineage',
        'Exact Rust-quartet component positions remain separate pending work']
    card = {'schema_version': 1, 'prepared_utc': now, 'component_id': 'BC-MCP-1',
        'review_number': 71, 'family': 'Moon Crater Phase', 'review_family_scope': 'Moon Crater Phase 1',
        'family_review_number': 2, 'family_review_total': 2,
        'family_total_scope': cp['family_counting_note'], 'size_finish_variant_id': 'MCP1-VERDIGRIS-RUST',
        'proposed_name': 'Moon Crater Phase 1 — Verdigris and Rust (MCP1)',
        'identity_decision_destination': 'size_finish_variant_decisions',
        'review_decision_mode': 'FINISH_NAME_AND_DEPICTED_IDENTITY_ONLY',
        'scope': 'One coloured MCP1panel reference. White approval is retained separately; six specification groups shown for review remain conditional and unapproved.',
        'primary_image_id': primary_id, 'primary_folder_id': folder_id,
        'primary_image_link': links[primary_id]['copy_link_url'], 'primary_folder_link': links[folder_id]['copy_link_url'],
        'primary_image_scope': 'Complete native single-panel front on stone wall',
        'candidate_rear_file_id': rear_id, 'candidate_rear_image_link': links[rear_id]['copy_link_url'],
        'candidate_rear_same_physical_panel_verified': False,
        'in_situ_image_id': 'id:cnqzTNngPVsAAAAAAAuRAQ',
        'in_situ_image_link': links['id:cnqzTNngPVsAAAAAAAuRAQ']['copy_link_url'],
        'in_situ_folder_id': 'id:cnqzTNngPVsAAAAAAAyipw',
        'in_situ_folder_link': links['id:cnqzTNngPVsAAAAAAAyipw']['copy_link_url'],
        'metadata_checked_utc': fresh['metadata']['checked_utc'],
        'reference_refresh': rel(HERE / 'owner-keep-current-reference.json'),
        'specification_review_items': items, 'platform_mapping': mapping, 'photo_coverage': coverage,
        'pending_arrangement_component_review': copy.deepcopy(target['pending_arrangement_component_review']),
        'identity_confirmed': False, 'specifications_approved': False, 'physical_specs_verified': False,
        'individual_sale_unit': {'quantity': 1, 'description': 'One MCP1Verdigris/Rust panel', 'live_listing_prepared_or_published': False},
        'open_gaps': gaps, 'next_review_after_keep': {'component_id': 'BC-MCP-2', 'review_number': 72},
        'remote_files_changed': False, 'live_platform_records_changed': False}
    write(HERE / 'mcp1-verdigris-rust/before-staging.json', {'recorded_utc': now,
        'files': {rel(paths[k]): value for k, value in before.items()}, 'protected_sha256': protected})
    write(output, card)
    target.setdefault('size_finish_variants', {})['MCP1-VERDIGRIS-RUST'] = {
        'proposed_name': card['proposed_name'], 'size_finish_variant_id': 'MCP1-VERDIGRIS-RUST',
        'identity_confirmed': False, 'specifications_approved': False, 'physical_specs_verified': False,
        'review_record': rel(output), 'reviewed_utc': now, 'primary_image_id': primary_id,
        'primary_folder_id': folder_id, 'specification_proposals': copy.deepcopy(items),
        'platform_mapping': mapping, 'photo_coverage': coverage, 'gaps': gaps}
    state = 'Awaiting MCP1 Verdigris and Rust name; six conditional groups unapproved; exact platform photo binding pending'
    cp.update({'current_size_finish_variant_id': 'MCP1-VERDIGRIS-RUST', 'current_component_layout_id': None,
        'proposed_name': card['proposed_name'], 'state': state, 'current_review_record': rel(output),
        'current_family_review_number': 2, 'current_family_review_total': 2, 'current_answer_recorded': False,
        'current_specification_answer_recorded': False, 'current_dimension_answer_recorded': False,
        'current_partial_specification_answer_recorded': False, 'working_version_user_approved': False,
        'review_decision_mode': card['review_decision_mode'], 'question_scope': card['scope'],
        'answer_state': 'White MCP1name saved; coloured finish identity and all six groups unapproved.',
        'primary_image': {'file_id': primary_id, 'name': primary['name'], 'path_display': primary['path_display'],
            'copy_link_url': card['primary_image_link'], 'open_in_dropbox_url': links[primary_id]['open_in_dropbox_url']},
        'containing_folder': {'folder_id': folder_id, 'name': folder['name'], 'path_display': folder['path_display'],
            'copy_link_url': card['primary_folder_link'], 'open_in_dropbox_url': links[folder_id]['open_in_dropbox_url']},
        'metadata_checked_utc': fresh['metadata']['checked_utc'],
        'displayed_identity_evidence_file_ids': [primary_id], 'displayed_identity_evidence_folder_ids': [folder_id],
        'current_component_source_notes': [x['display'] for x in items],
        'next_review_after_keep': card['next_review_after_keep'], 'updated_utc': now})
    c['interactive_review_state'].update({'current_size_finish_variant_id': 'MCP1-VERDIGRIS-RUST',
        'current_component_layout_id': None, 'current_name': card['proposed_name'], 'state': state,
        'family_review_number': 2, 'family_review_total': 2, 'specification_proposals_approved': False,
        'working_version_user_approved': False, 'review_decision_mode': card['review_decision_mode']})
    c['current_component_review_record'] = rel(output)
    c.setdefault('additional_review_evidence', []).append({
        'scope': 'MCP1-related O007public-photo followup; exact binding pending',
        'evidence': rel(public_path), 'recorded_utc': now})
    c['updated_utc'] = p['updated_utc'] = now
    docs['root']['current_component_review'] = copy.deepcopy(c)
    docs['root']['updated_utc'] = now
    for key, value in before['progress']['reviews'].items():
        if key != 'BC-MCP-1':
            assert p['reviews'][key] == value
    expected_target = copy.deepcopy(before['progress']['reviews']['BC-MCP-1'])
    expected_target.setdefault('size_finish_variants', {})['MCP1-VERDIGRIS-RUST'] = target['size_finish_variants']['MCP1-VERDIGRIS-RUST']
    assert target == expected_target
    for key in ['parallel_import_queue', 'parallel_owner_reviews', 'parallel_evidence_flags',
                'pending_specification_reviews', 'next_serialized_parallel_import', 'last_parallel_import']:
        assert cp[key] == before['walkthrough'][key]
    assert p['family_review_progress'] == before['progress']['family_review_progress']
    assert all(sha(path) == hashes[k] for k, path in paths.items()), 'Shared writer collision'
    assert all(sha(Path(path)) == digest for path, digest in protected.items())
    for key, path in paths.items():
        write(path, docs[key])
        assert read(path) == docs[key]
    result = {'status': 'PASS', 'current_name': card['proposed_name'], 'all_six_groups_unapproved': True,
        'fresh_finish_folder_files': 12, 'source_originals_and_candidate_rear_inspected': True,
        'White_owner_approval_and_sources_preserved': True, 'exact_platform_photo_binding_pending': True,
        'same_front_back_cast_unverified': True, 'Rust_quartet_attribution_still_pending': True,
        'previous_reviews_counts_queues_model_workbook_and_batch7_import_preserved': True,
        'checkpoint_copies_match': read(paths['root'])['current_component_review'] == read(paths['component'])}
    write(HERE / 'mcp1-verdigris-rust/review-validation.json', result)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
