"""Review one Leaf Form component position separately from the pair, retaining source conflicts."""
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REVIEWS = ROOT / 'components/reviews'
MAKER = Path('/Users/tprice/Library/Application Support/BoldstoneImageConsistency/product-evidence-resolution-20261016T201618Z')
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
rel = lambda p: str(p.relative_to(ROOT))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temp.replace(path)


def main():
    card_path = HERE / 'lf1-white/component-review.json'
    assert not card_path.exists(), 'Already frozen'
    paths = {'walkthrough': REVIEWS / 'walkthrough_checkpoint.json', 'progress': REVIEWS / 'specification_review_progress.json',
        'component': ROOT / 'components/checkpoint.json', 'root': ROOT / 'checkpoint.json'}
    docs = {key: read(path) for key, path in paths.items()}
    before = copy.deepcopy(docs)
    hashes = {key: sha(path) for key, path in paths.items()}
    cp, progress, component = (docs[key] for key in ['walkthrough', 'progress', 'component'])
    assert cp['current_component_id'] == 'BC-LEAF-CURVE' and cp['current_answer_recorded']
    assert cp['next_review_after_keep']['component_id'] == 'BC-LEAF-FORM'
    assert docs['root']['current_component_review'] == component and 'BC-LEAF-FORM' not in progress['reviews']
    assert not any(x['component_id'] == 'BC-LEAF-FORM' for x in cp['parallel_owner_reviews'])
    curve_keep_path, curve_card_path = ROOT / cp['last_identity_approval'], ROOT / cp['current_review_record']
    assert read(curve_keep_path)['confirmed_name'] == 'Leaf Curve — White and Gold Leaf'
    model_path = ROOT / 'components/evidence/component_register.json'
    model = read(model_path)
    native = next(x for x in model['components'] if x['component_id'] == 'BC-LEAF-FORM')
    offers = {x['offer_ref']: x for x in model['platform_records'] if x['offer_ref'] in ['O028', 'O058']}
    assert offers['O028']['sku'] == 'LF-2P-35.70' and offers['O028']['match_status'] == 'Unique shared SKU confirmed'
    assert offers['O058']['sku'] == 'LF-1-40.20' and not offers['O058']['sh_handle']
    census, meta = read(HERE / 'media-census.json'), read(HERE / 'metadata-links.json')
    assert not census['root']['has_more'] and not census['root']['cursor']
    assert len(census['listings']) == 6 and sorted(len(x['entries']) for x in census['listings']) == [0, 3, 7, 9, 56, 60]
    assert all(not x['has_more'] and not x['cursor'] for x in census['listings'])
    selected = {x['label']: x for x in meta['selected']}
    metadata = {x['request_id']: x for x in meta['metadata']}
    links = {x['file_name']: x for x in meta['previews']}
    primary_id, folder_id = selected['LF1_A']['file']['file_id'], selected['LF1_A']['folder']['file_id']
    primary, folder = metadata[primary_id]['file'], metadata[folder_id]['folder']
    index, originals = read(HERE / 'image-review-index.json'), read(HERE / 'download-receipts.json')
    assert len(index['cached_previews']) == 135 and len(originals) == 6
    for item in index['cached_previews']:
        assert sha(Path(item['preview_path'])) == item['sha256']
    for receipt in originals:
        path = Path(receipt['local_path'])
        data = path.read_bytes()
        assert len(data) == receipt['size'] == metadata[receipt['id']]['file']['size'] and sha(path) == receipt['sha256']
        assert hashlib.sha256(b''.join(hashlib.sha256(data[i:i+4194304]).digest() for i in range(0, len(data), 4194304))).hexdigest() == receipt['content_hash']
    maker_receipt_path = MAKER / 'documents/manufacture-stevensons.receipt.json'
    maker_receipt = read(maker_receipt_path)
    maker_source_path = Path(maker_receipt['local_path'])
    current_maker = read(HERE / 'maker-current-metadata.json')['metadata']['file']
    assert current_maker['id'] == maker_receipt['head']['id'] and current_maker['rev'] == maker_receipt['head']['rev']
    assert maker_source_path.stat().st_size == current_maker['size'] == maker_receipt['fingerprint']['size']
    assert sha(maker_source_path) == maker_receipt['fingerprint']['backup_sha256']
    maker_data = maker_source_path.read_bytes()
    assert hashlib.sha256(b''.join(hashlib.sha256(maker_data[i:i+4194304]).digest() for i in range(0, len(maker_data), 4194304))).hexdigest() == maker_receipt['fingerprint']['content_hash']
    rows = [x for x in read(MAKER / 'Manufacturing_Sheet_Extract.json') if x['row'] in [34, 36, 37]]
    assert len(rows) == 3
    labels = [x for x in read(MAKER / 'Manufacturing_Labelled_References.json') if x['code'] in ['LF1-35x35', 'LF2-35x35']]
    now = datetime.now(timezone.utc).isoformat()
    maker_ref = HERE / 'maker-source-reference.json'
    write(maker_ref, {'checked_utc': now, 'source_file_id': current_maker['id'], 'source_rev': current_maker['rev'],
        'source_local_path': str(maker_source_path), 'source_sha256': sha(maker_source_path),
        'source_receipt': str(maker_receipt_path), 'source_receipt_sha256': sha(maker_receipt_path),
        'extracted_rows': rows, 'labelled_reference_images': labels,
        'scope': 'Historical maker standard describes one mould in opposite directions A/B, two casts for the diptych and separate LF1/LF2 component instructions. This does not verify current physical mould inventory, actual cast composition, weight or hardware.'})
    public_receipts = read(HERE / 'public-image-receipts.json')
    for receipt in public_receipts:
        assert receipt['status'] == 'GET200' and sha(Path(receipt['local_path'])) == receipt['sha256']
    matches = []
    for label, source_id in [('single', primary_id), ('pair', selected['pair']['file']['file_id'])]:
        public = next(x for x in public_receipts if x['label'] == label)
        local = next(x for x in originals if x['id'] == source_id)
        matches.append({'listing': label, 'dropbox_file_id': source_id, 'public_image_sha256': public['sha256'],
            'dropbox_original_sha256': local['sha256'], 'exact_bytes_equal': public['sha256'] == local['sha256'],
            'visual_result': 'Same depicted photograph/design/background; encoded image bytes differ',
            'same_physical_cast_in_other_photographs_verified': False})
    write(HERE / 'listing-image-comparison.json', {'checked_utc': now, 'comparisons': matches,
        'source_public_text': rel(HERE / 'public-reader-source.json'),
        'direct_HTML_GET_status': '403; no retry. Public reader and normal CDN assets inspected.',
        'single_size_conflict_unresolved': True})
    observations = {'LF1_A': {'primary_file_id': primary_id, 'maker_row': 36, 'maker_picture': 'picture-037.preview.png',
        'geometry': 'Broad leaf sweeps through the left half, with narrower rising bands at the right; leaf convergence toward the top.',
        'pair001_position': 'Right', 'garden003_position': 'Right', 'exhibition039_position': 'Left'},
        'LF2_B': {'reference_file_id': selected['LF2_B']['file']['file_id'], 'maker_row': 37,
            'maker_picture': 'picture-038.preview.png', 'geometry': 'Opposite orientation with broad curve toward the right and convergence toward the bottom.',
            'pair001_position': 'Left', 'garden003_position': 'Left', 'exhibition039_position': 'Right'},
        'scope': 'Positions are bound to those exact photographs, not every arrangement. Same historical pattern in opposite orientations; no owner identity, current physical cast/mould or rotation-compatible rear fixing approval inferred.',
        'gold': 'Seven interior-room reference renderings show a gold-coloured Leaf Form motif. Their source/provenance and physical gold finish are unverified; reserved for a separate finish review.'}
    write(HERE / 'component-position-observations.json', {'checked_utc': now, 'observations': observations,
        'previews_inspected': 135, 'fresh_Dropbox_originals_viewed': 6, 'public_originals_viewed': 2, 'maker_reference_images_viewed': 2})
    items = []

    def item(suffix, field, display, value, status, basis, sources):
        items.append({'proposal_id': 'LEAF-FORM-LF1-WHITE-' + suffix, 'field': field, 'display': display,
            'value': value, 'status': status, 'basis': basis, 'source_refs': sources,
            'owner_approved': False, 'physical_specs_verified': False})

    public_ref = rel(HERE / 'public-reader-source.json')
    item('DIMENSIONS', 'Individual dimensions and depth', '35×35×6cm per panel in pair listing; maker side-depth5–7cm; single listing40×20×6cm conflicts',
        {'pair_listing_each_dimensions_cm': [35, 35, 6], 'maker_approx_face_cm': [35, 35],
         'maker_side_depth_range_cm': [5, 7], 'single_listing_dimensions_cm': [40, 20, 6], 'actual_measured_cm': None},
        'CONFLICTING SOURCE DIMENSIONS; SQUARE COMPONENT APPLICABILITY PENDING',
        'Maker rows34/36 and pair offer explicitly give35×35cm for each panel. Pair page states6cmdepth; maker says approximate50–70mmside. O058single-page photo matches this square panel but its40×20×6text conflicts; no independent40×20version, typo or correction is assumed. No overall dimensions are divided.', [rel(maker_ref), public_ref, primary_id])
    item('WEIGHT', 'Individual dry weight', '6–8kg per panel — historical maker calculated estimate; actual cast unweighed',
        {'maker_calculated_range_kg_each': [6, 8], 'actual_weighed_kg': None, 'pair_export_weight_kg_not_allocated': 16},
        'HISTORICAL PER-COMPONENT CALCULATED RANGE; NOT A WEIGHING',
        'Maker row36explicitly states6–8kg each for the standard white cast. Keep the source estimate with its standard-size/material assumptions;16kgpair export is whole-offer evidence and is not divided.', [rel(maker_ref), 'O028'])
    item('MATERIAL', 'Material and finish', 'White marble stone finish / Jesmonite AC730 — maker standard; single listing says gypsum composite; actual cast recipe unconfirmed',
        {'maker_standard_binder': 'Jesmonite AC730', 'maker_standard_finish': 'White Marble Stone Finish',
         'single_listing_material_claim': 'gypsum composite, stone finish', 'actual_binder': None, 'reinforcement': None, 'sealer': None},
        'DISTINCT MAKER AND LISTING CLAIMS; CAST APPLICABILITY UNCONFIRMED',
        'Row36names AC730for the historical white standard. O058has a broader gypsum-composite description. Record both source claims without certifying the pictured cast composition, backing, reinforcement, sealing, weather suitability or care.', [rel(maker_ref), public_ref])
    item('FIXING', 'Fixing', 'One small stainless-steel rear fixing centred in upper third — maker instruction; actual hardware and load unverified',
        {'maker_instruction_type': 'small stainless steel fixing', 'maker_instruction_count': 1,
         'maker_instruction_position': 'centre back in top one third, aligned from top edge with series', 'actual_hardware': None, 'rated_load': None},
        'HISTORICAL PER-PANEL FIXING INSTRUCTION; NO REAR INSPECTION',
        'Maker row36provides one fixing and its intended position. No finished rear/fixing image was established across135front/context/detail references. Visible front-wall support pegs do not certify this rear fitting, attachment, anchorage, load or alternate hanging orientation compatibility.', [rel(maker_ref), rel(HERE / 'media-census.json')])
    item('PRICE', 'Individual retail price', '£350 in single listing — price reference;35cm-square applicability and owner intention unconfirmed',
        {'single_listing_price_gbp': 350, 'single_listing_size_applicability_confirmed': False,
         'pair_listing_price_gbp_not_allocated': 600, 'owner_individual_price_approved': False},
        'SOURCE SINGLE-OFFER PRICE WITH UNRESOLVED SIZE; NOT OWNER APPROVED',
        'O058single offer is350GBP and its primary photograph matches this depicted LF1orientation. Its40×20description conflicts with square35×35source specifications, so correct-size price applicability remains open.600GBPpair price is kept separately and never divided.', [public_ref, 'O058', 'O028'])
    item('AVAILABILITY', 'Availability', 'Made to order / enquire — proposal; actual stock, reproduction capability and lead time unknown',
        {'proposed_policy': 'Made to order / enquire subject to production confirmation', 'physical_stock': None,
         'reproducibility': None, 'lead_time': None},
        'UNAPPROVED SALE POLICY; PHYSICAL INVENTORY UNVERIFIED',
        'Public cart controls and historicUnlimited/activeflags do not establish a stocked cast, usable mould, current production or delivery date. This individual-position record is prepared for separate purchasing under the owner catalogue brief, without a live publication or stock claim.', [public_ref, rel(maker_ref)])
    family_order = [
        {'component_id': 'BC-LEAF-FORM', 'review_number': 67, 'variant_id': 'LEAF-FORM-LF1-WHITE',
         'component_layout_id': 'LEAF-FORM-LF1-WHITE', 'label': 'Leaf Form 1 — White (LF1)'},
        {'component_id': 'BC-LEAF-FORM', 'review_number': 67, 'variant_id': 'LEAF-FORM-LF2-WHITE',
         'component_layout_id': 'LEAF-FORM-LF2-WHITE', 'label': 'Leaf Form 2 — White (LF2)'},
        {'component_id': 'BC-LEAF-FORM', 'review_number': 67, 'variant_id': 'LEAF-FORM-GOLD',
         'variant_only_review': True, 'label': 'Leaf Form — Gold reference'}]
    coverage = {'complete_individual_front': True, 'native_outdoor_brick_wall_display': True,
        'paired_series_reference': True, 'garden_pair_reference': True, 'indoor_exhibition_reference': True,
        'confirmed_indoor_home_setting': False, 'finished_rear': False, 'rear_fixing_detail': False,
        'actual_named_client_installation_provenance_confirmed': False,
        'opposite_LF2_clean_front_inherited_as_LF1': False,
        'scope': 'Six-folder current census complete:135files and one empty folder. All135previews viewed in5contact sheets;6Dropbox originals,2public listing originals and2labelled maker images viewed. LF1A is right in pair001/garden003 and left in exhibition039; the clean white001PNG is opposite LF2B and is not assigned as the LF1primary. Gold room references remain a separate review with unverified provenance.'}
    mapping = {'platform_record_level': {'pair_offer_ref': 'O028', 'squarespace_id': offers['O028']['sq_id'],
        'shopify_handle': offers['O028']['sh_handle'], 'shared_sku': offers['O028']['sku'],
        'status': 'SUPPLIED EXPORT PAIR CONFIRMED THROUGH UNIQUE SHARED SKU'},
        'single_offer': {'offer_ref': 'O058', 'squarespace_id': offers['O058']['sq_id'], 'sku': offers['O058']['sku'],
            'shopify_handle': None, 'status': 'SQUARESPACE ONLY IN REVIEWED EXPORT; SIZE CONFLICT RETAINED'},
        'dropbox_listing_level': {'single_public_image_file_id': primary_id,
            'pair_public_image_file_id': selected['pair']['file']['file_id'],
            'status': 'VISUALLY CONFIRMED SAME DEPICTED PHOTOGRAPH/DESIGN; ENCODED BYTES DIFFER',
            'image_comparison_receipt': rel(HERE / 'listing-image-comparison.json')},
        'individual_component_level': {'component_layout_id': 'LEAF-FORM-LF1-WHITE', 'maker_code': 'LF1-35x35',
            'maker_position': 'A', 'source_role': 'One component cast/position of a two-cast arrangement',
            'whole_set_dimensions_weight_price_transferred': False, 'exact_size_price_and_cast_specs_confirmed': False},
        'live_Shopify_account_refreshed': False, 'current_native_public_SKUs_reparsed': False}
    card = {'schema_version': 1, 'prepared_utc': now, 'component_id': 'BC-LEAF-FORM', 'review_number': 67,
        'family': 'Leaf Form', 'family_review_number': 1, 'family_review_total': 3,
        'family_total_scope': 'Three review references:LF1White individual position, LF2White individual position, and a separate Gold finish reference. Not a count of distinct physical sculptures, unique patterns or moulds.',
        'component_layout_id': 'LEAF-FORM-LF1-WHITE', 'size_finish_variant_id': 'LEAF-FORM-LF1-WHITE',
        'proposed_name': 'Leaf Form 1 — White (LF1)', 'display_name': 'Leaf Form 1 — White (LF1)',
        'review_decision_mode': 'INDIVIDUAL_COMPONENT_LAYOUT_NAME_AND_SPECIFICATIONS',
        'identity_decision_destination': 'component_layout_identity_decisions',
        'scope': 'Individual LF1/PositionA orientation, separately reviewable/purchasable as one panel. LF2/PositionB has a separate component-position record. Same historical pattern/mould orientation does not merge two sale-unit components or certify a current physical mould/cast. Name and six source/proposal groups remain separate approvals.',
        'primary_image_id': primary_id, 'primary_folder_id': folder_id,
        'primary_image_link': links[primary_id]['copy_link_url'], 'primary_folder_link': links[folder_id]['copy_link_url'],
        'pair_image_id': selected['pair']['file']['file_id'], 'pair_folder_id': selected['pair']['folder']['file_id'],
        'pair_image_link': links[selected['pair']['file']['file_id']]['copy_link_url'],
        'pair_folder_link': links[selected['pair']['folder']['file_id']]['copy_link_url'], 'pair_target_position': 'Right',
        'garden_image_id': selected['garden']['file']['file_id'], 'garden_folder_id': selected['garden']['folder']['file_id'],
        'garden_image_link': links[selected['garden']['file']['file_id']]['copy_link_url'], 'garden_target_position': 'Right',
        'exhibition_image_id': selected['exhibition']['file']['file_id'],
        'exhibition_image_link': links[selected['exhibition']['file']['file_id']]['copy_link_url'], 'exhibition_target_position': 'Left',
        'opposite_position_reference_id': selected['LF2_B']['file']['file_id'],
        'metadata_checked_utc': meta['selected_metadata_checked_utc'], 'reference_refresh': rel(HERE / 'metadata-links.json'),
        'specification_review_items': items, 'platform_mapping': mapping, 'photo_coverage': coverage,
        'source_conflicts': ['Single40×20×6cm versus square35×35cmcomponent and5–7cmmaker side depth.',
            'MakerAC730standard versus broader single-listinggypsum description; actual cast binder unknown.',
            'Single350GBPprice exact square-size applicability unresolved; pair600GBPseparate.',
            'Current usable mould inventory, exact physical cast identity and rear orientation compatibility unknown.'],
        'identity_confirmed': False, 'specifications_approved': False, 'physical_specs_verified': False,
        'individual_sale_unit': {'quantity': 1, 'description': 'One LF1/PositionA panel', 'live_listing_prepared_or_published': False},
        'open_gaps': ['Owner LF1name and depicted component-position identity', 'Resolve actual face size/depth and single-listing version conflict',
            'Actual weighed dry mass, binder/backing/reinforcement/sealer/care', 'Rear fixing hardware/attachment/load and alternate orientation compatibility',
            'Correct-size standalone price, physical stock, reproducibility and lead time', 'Standalone Shopify counterpart/shared SKU',
            'Indoor home-setting image, finished rear and named client-installation provenance', 'Physical cast/mould inventory'],
        'next_review_after_keep': family_order[1], 'next_global_component': {'component_id': 'BC-LEAF-GROWTH', 'review_number': 68},
        'remote_files_changed': False, 'live_platform_records_changed': False}
    write(card_path, card)
    evidence = [model_path, maker_ref, maker_source_path, MAKER / 'Manufacturing_Sheet_Extract.json',
        MAKER / 'Manufacturing_Labelled_References.json', HERE / 'media-census.json', HERE / 'metadata-links.json',
        HERE / 'maker-current-metadata.json', HERE / 'public-reader-source.json', HERE / 'public-source-check.json',
        HERE / 'listing-image-comparison.json', HERE / 'component-position-observations.json', HERE / 'image-review-index.json']
    evidence += [Path(x['local_path']) for x in originals + public_receipts] + [Path(x['preview_path']) for x in index['cached_previews']]
    evidence += [MAKER / 'manufacturing-images' / x for x in ['picture-037.preview.png', 'picture-038.preview.png']]
    write(HERE / 'source-audit.json', {'status': 'PASS', 'checked_utc': now, 'fresh_census_files': 135,
        'previews_inspected': 135, 'DropBox_originals_viewed': 6, 'public_originals_viewed': 2, 'maker_reference_images_viewed': 2,
        'single_size_conflict_preserved': True, 'source_sha256': {str(path): sha(path) for path in sorted(set(evidence))}})
    protected = {str(path): sha(path) for path in [REVIEWS / 'user_classifications.json', model_path,
        ROOT / cp['register_workbook'], curve_keep_path, curve_card_path, card_path]}
    write(HERE / 'before-stage-review.json', {'recorded_utc': now, 'files': {rel(paths[key]): value for key, value in before.items()}, 'protected_sha256': protected})
    progress['reviews']['BC-LEAF-FORM'] = {'identity_confirmed': False, 'specifications_approved': False, 'physical_specs_verified': False,
        'scope': 'Same base pattern; individual component positions and finishes are reviewed separately.',
        'component_layouts': {'LEAF-FORM-LF1-WHITE': {'reviewed_utc': now, 'review_number': 67,
            'proposed_name': card['proposed_name'], 'component_layout_id': card['component_layout_id'],
            'identity_confirmed': False, 'specifications_approved': False, 'physical_specs_verified': False,
            'specification_proposals': copy.deepcopy(items), 'primary_image_id': primary_id, 'primary_folder_id': folder_id,
            'review_record': rel(card_path), 'platform_mapping': mapping, 'photo_coverage': coverage,
            'individual_sale_unit': card['individual_sale_unit'], 'gaps': card['open_gaps']}},
        'pending_component_layouts': [family_order[1]], 'pending_size_finish_variants': [family_order[2]]}
    progress['family_review_progress']['Leaf Form'] = {'family': 'Leaf Form', 'status': 'FIRST_PASS_IN_PROGRESS',
        'updated_utc': now, 'review_reference_cards_answered': 0, 'review_reference_total': 3,
        'reference_total_is_sculpture_count': False, 'specifications_complete': False}
    progress['updated_utc'] = now
    state = 'Awaiting Leaf Form1White LF1/PositionA individual name; size conflict and all six groups pending'
    cp.update({'current_component_id': 'BC-LEAF-FORM', 'current_review_number': 67,
        'current_component_layout_id': card['component_layout_id'], 'current_size_finish_variant_id': card['size_finish_variant_id'],
        'proposed_name': card['proposed_name'], 'state': state, 'current_review_record': rel(card_path),
        'current_family_review_number': 1, 'current_family_review_total': 3, 'active_family': 'Leaf Form',
        'family_review_order': family_order, 'family_first_pass_complete': False, 'current_answer_recorded': False,
        'current_identity_relationship_answer_recorded': False, 'current_identity_relationship_approval': None,
        'canonical_depicted_name': None, 'current_separate_saleable_design': None,
        'current_specification_answer_recorded': False, 'current_dimension_answer_recorded': False,
        'current_partial_specification_answer_recorded': False, 'current_dimension_approval': None,
        'current_owner_face_dimensions_cm': None, 'working_version_user_approved': False,
        'review_decision_mode': card['review_decision_mode'], 'question_scope': card['scope'],
        'answer_state': 'No LF1name or specification approval yet. LF2position and Gold finish will be reviewed separately; Leaf Curve name is kept.',
        'primary_image': {'file_id': primary_id, 'name': primary['name'], 'path_display': primary['path_display'],
            'copy_link_url': card['primary_image_link'], 'open_in_dropbox_url': links[primary_id]['open_in_dropbox_url']},
        'containing_folder': {'folder_id': folder_id, 'name': folder['name'], 'path_display': folder['path_display'],
            'copy_link_url': card['primary_folder_link'], 'open_in_dropbox_url': links[folder_id]['open_in_dropbox_url']},
        'family_review_evidence': rel(HERE / 'metadata-links.json'), 'metadata_checked_utc': meta['selected_metadata_checked_utc'],
        'next_review_after_keep': family_order[1], 'displayed_identity_evidence_file_ids': [primary_id],
        'displayed_identity_evidence_folder_ids': [folder_id], 'current_component_source_notes': [x['display'] for x in items],
        'family_counting_note': card['family_total_scope'], 'updated_utc': now})
    component['interactive_review_state'].update({'current_component_id': 'BC-LEAF-FORM', 'review_number': 67,
        'current_component_layout_id': card['component_layout_id'], 'current_size_finish_variant_id': card['size_finish_variant_id'],
        'current_name': card['proposed_name'], 'state': state, 'active_family': 'Leaf Form', 'family_review_number': 1, 'family_review_total': 3,
        'specification_proposals_approved': False, 'working_version_user_approved': False, 'review_decision_mode': card['review_decision_mode']})
    component['current_component_review_record'] = rel(card_path)
    component['last_family_media_review'] = {'family': 'Leaf Form', 'observed_utc': meta['selected_metadata_checked_utc'],
        'files': 135, 'folders': 6, 'scope': coverage['scope'], 'evidence': rel(HERE / 'metadata-links.json'), 'workbook_contains_this_live_media_audit': False}
    component['updated_utc'] = now
    docs['root']['current_component_review'] = copy.deepcopy(component)
    docs['root']['updated_utc'] = now
    assert all(progress['reviews'][key] == value for key, value in before['progress']['reviews'].items())
    for key in ['parallel_import_queue', 'parallel_owner_reviews', 'parallel_evidence_flags', 'pending_specification_reviews']:
        assert cp[key] == before['walkthrough'][key]
    assert all(sha(path) == hashes[key] for key, path in paths.items()), 'Shared writer collision'
    assert all(sha(Path(path)) == digest for path, digest in protected.items())
    for key, path in paths.items():
        write(path, docs[key])
        assert read(path) == docs[key]
    result = {'status': 'PASS', 'current_component': 'BC-LEAF-FORM', 'current_layout': card['component_layout_id'],
        'six_groups_unapproved': True, 'fresh_complete_file_census': 135, 'source_size_conflict_preserved': True,
        'pair_price_and_mass_not_divided': True, 'LF1_and_LF2_have_separate_individual_position_records': True,
        'ledger_model_workbook_previous_owner_reviews_unchanged': True, 'checkpoint_copies_match': read(paths['root'])['current_component_review'] == read(paths['component'])}
    write(HERE / 'review-validation.json', result)
    print(json.dumps(result))
    print(json.dumps({'image': card['primary_image_link'], 'folder': card['primary_folder_link'], 'pair': card['pair_image_link'], 'garden': card['garden_image_link']}))


if __name__ == '__main__':
    main()
