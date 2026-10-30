"""Stage MCP2 Verdigris/Rust and record the verified public photograph binding."""
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REVIEWS = ROOT / 'components/reviews'
OUT = HERE / 'mcp2-verdigris-rust'
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
rel = lambda p: str(p.relative_to(ROOT))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temp.replace(path)


def main():
    output = OUT / 'component-review.json'; assert not output.exists()
    paths = {'progress': REVIEWS / 'specification_review_progress.json', 'walkthrough': REVIEWS / 'walkthrough_checkpoint.json',
        'component': ROOT / 'components/checkpoint.json', 'root': ROOT / 'checkpoint.json'}
    docs = {k: read(path) for k, path in paths.items()}; before = copy.deepcopy(docs)
    hashes = {k: sha(path) for k, path in paths.items()}
    p, cp, c = (docs[k] for k in ['progress', 'walkthrough', 'component'])
    cid, vid = 'BC-MCP-2', 'MCP2-VERDIGRIS-RUST'
    assert cp['current_component_id'] == cid and cp['current_size_finish_variant_id'] == 'MCP2-BLUE-SPLASHES'
    assert cp['current_answer_recorded'] and cp['next_review_after_keep']['variant_id'] == vid
    assert read(ROOT / cp['last_identity_approval'])['user_statement'] == 'Keep “Moon Crater Phase 2 — Blue Splashes (MCP2)”'
    assert docs['root']['current_component_review'] == c
    parent = p['reviews'][cid]; assert vid not in parent.get('size_finish_variants', {})
    protected = {str(path): sha(path) for path in [REVIEWS / 'user_classifications.json',
        ROOT / 'components/evidence/component_register.json', ROOT / cp['register_workbook'],
        ROOT / cp['current_review_record'], ROOT / cp['last_identity_approval'], HERE / 'mcp2-white/identity-approval.json']}
    census, metadata = read(OUT / 'current-census.json'), read(OUT / 'selected-metadata.json')
    assert len(census['result']['entries']) == 21 and not census['result']['has_more'] and not census['result']['cursor']
    old = read(HERE / 'public-o007/phase2-targeted-census.json')['listing']
    assert {x['file_id']: (x['name'], x['file']['size']) for x in census['result']['entries']} == {x['file_id']: (x['name'], x['file']['size']) for x in old['entries']}
    previews = read(OUT / 'preview-cache.json'); assert len(previews) == 21
    assert all(sha(Path(x['preview'])) == x['sha256'] for x in previews)
    originals = read(OUT / 'original-download-receipts.json')['entries']; assert len(originals) == 3
    for x in originals:
        assert sha(Path(x['local_path'])) == x['sha256'] and Path(x['local_path']).stat().st_size == x['size']
    primary_id, side_id, rear_id, folder_id = 'id:cnqzTNngPVsAAAAAAAygcw', 'id:cnqzTNngPVsAAAAAAAygdQ', 'id:cnqzTNngPVsAAAAAAAygeA', 'id:cnqzTNngPVsAAAAAAAygcQ'
    primary = next(x['file'] for x in metadata['entries'] if x['requested_id'] == primary_id)
    folder = next(x['result']['folder'] for x in read(HERE / 'mcp2-blue-splashes/keep-current-reference.json')['entries'] if x['requested_id'] == folder_id)
    assert primary['path_display'].rsplit('/', 1)[0] == folder['path_display']
    links = {x['file_name']: x for x in read(OUT / 'metadata-links.json')['results']}
    match = read(OUT / 'public-photo-comparison.json')
    assert match['photo_level_match_confirmed'] and match['native_file_id'] == primary_id
    assert match['resized_RGB_RMSE_0_255'] < 2 and not match['encoded_bytes_equal']
    assert sha(OUT / 'IMG_6177.jpeg') == match['public_sha256']
    model = read(ROOT / 'components/evidence/component_register.json')
    offer = next(x for x in model['platform_records'] if x['offer_ref'] == 'O008')
    assert offer['sq_id'] == '6a4173a2870e0e6bc1e10bf2' and offer['sku'] == 'SQ5572436' and not offer['sh_handle']
    now = datetime.now(timezone.utc).isoformat()
    source_path = OUT / 'current-public-source.json'
    source = {'checked_utc': now, 'page_url': offer['source_url'], 'reader_freshness': 'Crawled today',
        'source_product_title': 'Moon Crater Phase Blue Wall Sculpture', 'listing_dimensions_cm': [25, 25, 6],
        'listing_price_gbp': 350, 'listing_material_description': 'Hand-painted faux verdigris on copper',
        'current_primary_image_url': read(OUT / 'public-primary-download-receipt.json')['url'],
        'current_primary_image_sha256': match['public_sha256'], 'photo_comparison': rel(OUT / 'public-photo-comparison.json'),
        'matched_native_primary_file_id': primary_id, 'matched_native_folder_id': folder_id,
        'photo_level_match_confirmed': True, 'same_original_encoded_file': False,
        'platform_id_and_SKU_source': 'Supplied native Squarespace export; current account SKU not independently reparsed',
        'squarespace_id_from_export': offer['sq_id'], 'SKU_from_export': offer['sku'], 'shopify_handle_confirmed': None,
        'title_finish_mismatch': 'The product title says Blue; its current primary photograph is MCP2 Verdigris/Rust, not the separately reviewed Blue Splashes finish.',
        'actual_dimensions_material_mass_stock_and_rear_pairing_verified': False}
    write(source_path, source)
    maker_ref, dated_ref = rel(HERE / 'maker-source-reference.json'), rel(HERE / 'dated-price-source-scope.json')
    entries = [
        ('DIMENSIONS', 'Individual dimensions and depth', '25 × 25 × 6 cm — matched listing claim; actual panel unmeasured',
         {'source_listing_cm': [25, 25, 6], 'historical_White_MCP2_side_depth_cm': [4, 6], 'actual_measured_cm': None},
         'PHOTO-MATCHED LISTING CLAIM; NOT A MEASUREMENT',
         'The current page gives 25 × 25 × 6 cm for the photographed panel. Historical White maker row42 gives 25 × 25 cm with 4–6 cm side depth. Preserve the scopes; no whole-set dimension is divided.', [rel(source_path), maker_ref]),
        ('WEIGHT', 'Individual dry weight', 'Approximately 4 kg — conditional White-standard estimate; actual coloured panel unweighed',
         {'proposed_dry_weight_kg': 4, 'White_maker_estimate_kg': [2, 4], 'White_trade_2025_estimate_kg': 4,
          'White_retail_2025_estimate_kg': 5, 'actual_weighed_kg': None, 'native_export_raw_weight_unit_unencoded': 8.8},
         'CONDITIONAL CONSTRUCTION ANALOGY; SOURCE DIFFERENCES RETAINED',
         'Four kilograms is a discussion estimate conditional on construction similar to the White standard. Its maker 2–4 kg, trade4 kg and retail5 kg are separate historical estimates. Raw export8.8 has no encoded unit and is not silently converted to kilograms.', [maker_ref, dated_ref]),
        ('MATERIAL', 'Material and finish', 'Possibly a Jesmonite AC730 cast base with copper/verdigris and rust effects; actual composition unconfirmed',
         {'listing_description': source['listing_material_description'], 'proposed_substrate': 'Cast mineral composite; possibly Jesmonite AC730 from the White standard',
          'visible_surface': 'Turquoise/green and rust brown', 'actual_binder': None, 'actual_metal_content': None,
          'sealer': None, 'reinforcement': None, 'outdoor_suitability': None},
         'LISTING FINISH DESCRIPTION PLUS CONDITIONAL SUBSTRATE GUESS',
         'The matched listing describes faux verdigris on copper. That does not establish a solid-copper panel, binder, metal loading, sealer or outdoor suitability. AC730 is a historical White-standard analogy, not a certificate for the dark-backed coloured cast.', [rel(source_path), maker_ref, rear_id]),
        ('FIXING', 'Fixing', 'One silver-coloured keyhole plate visible on candidate rear012; exact pairing, alloy, attachment and load unknown',
         {'candidate_rear_file_id': rear_id, 'observed_plate_count': 1, 'observed_type': 'Rectangular keyhole-like metal plate',
          'observed_position': 'Centre of upper third on raised patch', 'front_back_same_cast_verified': False,
          'actual_alloy': None, 'attachment_method': None, 'rated_load': None},
         'VISIBLE CANDIDATE REAR; FRONT/BACK PAIRING UNCONFIRMED',
         'Full rear012 shows one metal plate in a raised dark-grey patch. File grouping and edge colours support a candidate association only. No rated load, exact alloy or attachment specification is visible. Hardware is not transferred to White or Blue Splashes.', [rear_id]),
        ('PRICE', 'Individual retail price', '£350 per panel — current matched listing price; owner price adoption unconfirmed',
         {'source_listing_price_gbp': 350, 'proposed_current_catalogue_price_gbp': 350, 'owner_price_approved': False},
         'CURRENT PHOTO-MATCHED PUBLIC PRICE; NOT OWNER APPROVAL',
         'The refreshed public page displays £350 for one photographed panel. Its title remains Blue despite the green/rust photograph. This is a source selling-price claim, not cost verification, owner approval or a divided quartet price.', [rel(source_path)]),
        ('AVAILABILITY', 'Availability', 'Made to order / enquire — proposed policy; stock, usable mould, reproducibility and lead time unknown',
         {'proposed_policy': 'Made to order / enquiry subject to production confirmation', 'physical_stock': None,
          'mould_condition': None, 'finish_reproducibility': None, 'lead_time': None},
         'PROPOSED POLICY; PHYSICAL AVAILABILITY UNVERIFIED',
         'An Add To Cart control and historical Unlimited/InStock fields do not verify current finished stock, a usable mould, reproducible patina or a delivery date.', [rel(source_path), dated_ref])]
    items = [{'proposal_id': vid + '-' + suffix, 'field': field, 'display': display, 'value': value,
        'status': status, 'basis': basis, 'source_refs': refs, 'owner_approved': False, 'physical_specs_verified': False}
        for suffix, field, display, value, status, basis, refs in entries]
    binding = {'offer_ref': 'O008', 'squarespace_id': offer['sq_id'], 'SKU_from_export': offer['sku'],
        'component_id': cid, 'size_finish_variant_id': vid, 'public_page_url': offer['source_url'],
        'public_primary_image_url': source['current_primary_image_url'], 'primary_file_id': primary_id,
        'additional_native_export_image_file_id': side_id, 'folder_id': folder_id,
        'native_rev': primary['rev'], 'native_bytes': primary['size'], 'native_sha256': match['native_sha256'],
        'public_sha256': match['public_sha256'], 'photo_level_match_confirmed': True,
        'same_original_encoded_file': False, 'current_account_SKU_reparsed': False, 'shopify_handle': None,
        'owner_finish_name_confirmed': False, 'source_evidence': rel(source_path), 'checked_utc': now}
    mapping = {'platform_record_level': {'squarespace_id': offer['sq_id'], 'SKU_from_export': offer['sku'],
        'shopify_handle': None, 'shared_sku_pair_confirmed': False,
        'status': 'SUPPLIED SQUARESPACE RECORD BOUND THROUGH CURRENT PHOTOGRAPH; NO CONFIRMED SHOPIFY PAIR'},
        'dropbox_sculpture_level': {'primary_file_id': primary_id, 'folder_id': folder_id, 'side_file_id': side_id,
            'candidate_rear_file_id': rear_id, 'photo_level_match_confirmed': True,
            'status': 'CURRENT PUBLIC PRIMARY PHOTOGRAPH MATCHED; OWNER FINISH NAME AND REAR PAIRING PENDING',
            'same_physical_cast_front_back_verified': False},
        'individual_component_level': {'component_id': cid, 'quantity': 1, 'whole_set_values_transferred': False},
        'source_title_finish_mismatch': source['title_finish_mismatch'], 'public_source': rel(source_path)}
    coverage = {'complete_individual_native_front': True, 'native_side_views': True, 'clean_complete_reference': True,
        'clean_image_edit_lineage_verified': False, 'product_on_stone_wall_photo': True,
        'plain_background_native_product_views': True, 'wider_installation_reference': False,
        'verified_client_installation': False, 'matching_finish_series_arrangement_identified': False,
        'candidate_rear_reference': True, 'candidate_rear_paired_to_selected_front': False,
        'scope': 'All21 current previews reviewed; originals003,006,012 viewed and hash-verified. Older001/002/013–020 images are warmer/rustier product views; no extra finish, stock or cast is inferred from colour variation. Rust arrangements in other folders remain separately pending.'}
    gaps = ['Owner MCP2 Verdigris and Rust name and depicted identity', 'Actual face/depth, dry mass and cast-specific composition',
        'Front/rear pairing and fixing alloy, attachment and load', 'Owner price adoption, stock, usable mould and lead time',
        'Current account SKU verification and Shopify counterpart', 'Wider installation and matching-finish series images; clean-image lineage']
    card = {'schema_version': 1, 'prepared_utc': now, 'component_id': cid, 'review_number': 72,
        'family': 'Moon Crater Phase', 'review_family_scope': 'Moon Crater Phase 2', 'family_review_number': 3, 'family_review_total': 3,
        'family_total_scope': cp['family_counting_note'], 'size_finish_variant_id': vid,
        'proposed_name': 'Moon Crater Phase 2 — Verdigris and Rust (MCP2)',
        'identity_decision_destination': 'size_finish_variant_decisions', 'review_decision_mode': 'FINISH_NAME_AND_DEPICTED_IDENTITY_ONLY',
        'scope': 'One green/rust MCP2panel, separately saleable from a set. The current Squarespace photograph is linked; name approval remains separate from six source/proposal groups and actual manufacture.',
        'primary_image_id': primary_id, 'primary_folder_id': folder_id, 'primary_image_link': links[primary_id]['copy_link_url'],
        'primary_folder_link': links[folder_id]['copy_link_url'], 'primary_image_scope': 'Complete native individual front; matches current public primary image',
        'side_image_id': side_id, 'side_image_link': links[side_id]['copy_link_url'],
        'candidate_rear_file_id': rear_id, 'candidate_rear_image_link': links[rear_id]['copy_link_url'],
        'candidate_rear_same_physical_panel_verified': False, 'metadata_checked_utc': metadata['checked_utc'],
        'reference_refresh': rel(OUT / 'selected-metadata.json'), 'specification_review_items': items,
        'platform_mapping': mapping, 'photo_coverage': coverage, 'pending_arrangement_component_review': copy.deepcopy(parent['pending_arrangement_component_review']),
        'identity_confirmed': False, 'specifications_approved': False, 'physical_specs_verified': False,
        'individual_sale_unit': {'quantity': 1, 'description': 'One MCP2 Verdigris/Rust panel', 'live_listing_prepared_or_published': False},
        'open_gaps': gaps, 'next_review_after_keep': {'component_id': 'BC-MCP-3', 'review_number': 73},
        'remote_files_changed': False, 'live_platform_records_changed': False}
    write(OUT / 'before-staging.json', {'recorded_utc': now, 'files': {rel(paths[k]): value for k, value in before.items()}, 'protected_sha256': protected})
    write(output, card); write(OUT / 'public-offer-photo-binding.json', binding)
    write(OUT / 'source-audit.json', {'current_files': 21, 'all_previews_viewed': True, 'full_originals_viewed': [primary_id, side_id, rear_id],
        'original_hash_receipts': rel(OUT / 'original-download-receipts.json'), 'public_photo_comparison': rel(OUT / 'public-photo-comparison.json'),
        'public_source': rel(source_path), 'maker_White_row': 42, 'whole_family_complete': False, 'physical_cast_mould_totals_inferred': False})
    parent.setdefault('size_finish_variants', {})[vid] = {'proposed_name': card['proposed_name'], 'size_finish_variant_id': vid,
        'identity_confirmed': False, 'specifications_approved': False, 'physical_specs_verified': False,
        'review_record': rel(output), 'reviewed_utc': now, 'primary_image_id': primary_id, 'primary_folder_id': folder_id,
        'specification_proposals': copy.deepcopy(items), 'platform_mapping': mapping, 'photo_coverage': coverage, 'gaps': gaps}
    assert 'O008' not in p.get('offer_photo_bindings', {})
    p.setdefault('offer_photo_bindings', {})['O008'] = binding
    state = 'Awaiting MCP2Verdigris/Rust name; current Squarespace photograph matched; six groups unapproved'
    cp.update({'current_size_finish_variant_id': vid, 'proposed_name': card['proposed_name'], 'state': state,
        'current_review_record': rel(output), 'current_family_review_number': 3, 'current_family_review_total': 3,
        'current_answer_recorded': False, 'current_specification_answer_recorded': False, 'current_dimension_answer_recorded': False,
        'current_partial_specification_answer_recorded': False, 'working_version_user_approved': False,
        'review_decision_mode': card['review_decision_mode'], 'question_scope': card['scope'],
        'answer_state': 'Blue Splashes name saved; Verdigris/Rust name and six groups unapproved.',
        'primary_image': {'file_id': primary_id, 'name': primary['name'], 'path_display': primary['path_display'],
            'copy_link_url': card['primary_image_link'], 'open_in_dropbox_url': links[primary_id]['open_in_dropbox_url']},
        'containing_folder': {'folder_id': folder_id, 'name': folder['name'], 'path_display': folder['path_display'],
            'copy_link_url': card['primary_folder_link'], 'open_in_dropbox_url': links[folder_id]['open_in_dropbox_url']},
        'metadata_checked_utc': metadata['checked_utc'], 'family_review_evidence': rel(OUT / 'source-audit.json'),
        'displayed_identity_evidence_file_ids': [primary_id], 'displayed_identity_evidence_folder_ids': [folder_id],
        'current_component_source_notes': [x['display'] for x in items], 'next_review_after_keep': card['next_review_after_keep'], 'updated_utc': now})
    c['interactive_review_state'].update({'current_size_finish_variant_id': vid, 'current_name': card['proposed_name'],
        'state': state, 'family_review_number': 3, 'family_review_total': 3, 'specification_proposals_approved': False,
        'working_version_user_approved': False, 'review_decision_mode': card['review_decision_mode']})
    c['current_component_review_record'] = rel(output)
    c['last_family_media_review'] = {'family': 'Moon Crater Phase', 'review_scope': 'MCP2 Verdigris/Rust only',
        'observed_utc': census['checked_utc'], 'files': 21, 'folders': 1, 'full_originals': 3,
        'evidence': rel(OUT / 'source-audit.json'), 'workbook_contains_this_live_media_audit': False}
    c.setdefault('additional_review_evidence', []).append({'scope': 'O008 current public photograph bound to MCP2 Verdigris/Rust stable file/folder IDs', 'evidence': rel(OUT / 'public-offer-photo-binding.json'), 'recorded_utc': now})
    c['updated_utc'] = p['updated_utc'] = now
    docs['root']['current_component_review'] = copy.deepcopy(c); docs['root']['updated_utc'] = now
    expected_parent = copy.deepcopy(before['progress']['reviews'][cid]); expected_parent.setdefault('size_finish_variants', {})[vid] = parent['size_finish_variants'][vid]
    assert parent == expected_parent and p['family_review_progress'] == before['progress']['family_review_progress']
    assert all(p['reviews'][k] == value for k, value in before['progress']['reviews'].items() if k != cid)
    for k in ['parallel_import_queue', 'parallel_owner_reviews', 'parallel_evidence_flags', 'pending_specification_reviews', 'next_serialized_parallel_import', 'last_parallel_import']:
        assert cp[k] == before['walkthrough'][k], k
    assert all(sha(path) == hashes[k] for k, path in paths.items()) and all(sha(Path(path)) == digest for path, digest in protected.items())
    for k, path in paths.items():
        write(path, docs[k]); assert read(path) == docs[k]
    result = {'status': 'PASS', 'current_name': card['proposed_name'], 'all_six_groups_unapproved': True,
        'current_Squarespace_photo_match_confirmed': True, 'stable_native_primary_and_folder_ids': [primary_id, folder_id],
        'source_title_Blue_finish_mismatch_preserved': True, 'rear_pairing_and_alloy_load_unconfirmed': True,
        'all21previews_and3native_originals_reviewed': True, 'previous_approvals_queues_model_and_workbook_preserved': True,
        'checkpoint_copies_match': read(paths['root'])['current_component_review'] == read(paths['component'])}
    write(OUT / 'review-validation.json', result); print(json.dumps(result))


if __name__ == '__main__':
    main()
