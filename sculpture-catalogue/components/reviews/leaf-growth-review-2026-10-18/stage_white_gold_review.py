"""Stage the separate detail-only White/Gold reference with six conditional proposals."""
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
    output = HERE / 'white-gold/component-review.json'
    assert not output.exists(), 'White/Gold reference already staged'
    paths = {'progress': REVIEWS / 'specification_review_progress.json',
        'walkthrough': REVIEWS / 'walkthrough_checkpoint.json',
        'component': ROOT / 'components/checkpoint.json', 'root': ROOT / 'checkpoint.json'}
    docs = {key: read(path) for key, path in paths.items()}
    before = copy.deepcopy(docs)
    hashes = {key: sha(path) for key, path in paths.items()}
    p, cp, c = (docs[key] for key in ['progress', 'walkthrough', 'component'])
    assert cp['current_component_id'] == 'BC-LEAF-GROWTH' and cp['current_answer_recorded']
    assert cp['current_size_finish_variant_id'] == 'LEAF-GROWTH-WHITE'
    assert cp['next_review_after_keep']['variant_id'] == 'LEAF-GROWTH-WHITE-GOLD'
    assert docs['root']['current_component_review'] == c
    white_path, keep_path = HERE / 'component-review.json', HERE / 'identity-approval.json'
    white, keep = read(white_path), read(keep_path)
    assert keep['user_statement'] == 'Keep “Leaf Growth — White (Magnolia Leaves)”' and not keep['specifications_approved']
    protected_paths = [REVIEWS / 'user_classifications.json', ROOT / 'components/evidence/component_register.json',
        ROOT / cp['register_workbook'], white_path, keep_path, HERE / 'source-audit.json',
        HERE / 'dated-price-source-scope.json', ROOT / cp['last_completed_family_first_pass']]
    protected = {str(path): sha(path) for path in protected_paths}
    refresh_path = HERE / 'white-keep-gold-refresh.json'
    fresh = read(refresh_path)
    listing = fresh['gold_listing']
    assert not listing['has_more'] and not listing['cursor'] and len(listing['entries']) == 8
    previous = next(x['result']['entries'] for x in read(HERE / 'media-census.json')['listings'] if x['path'].endswith('/Leaf Growth White and Gold Leaf'))
    old = {x['file_id']: x for x in previous}
    assert set(old) == {x['file_id'] for x in listing['entries']}
    previews = {x['file_id']: x for x in read(HERE / 'image-review-index.json')['cached_previews']}
    for entry in listing['entries']:
        assert entry['object_type'] == 'file'
        assert all(entry[key] == old[entry['file_id']][key] for key in ['name', 'path', 'modified_time', 'file'])
        assert sha(Path(previews[entry['file_id']]['preview_path'])) == previews[entry['file_id']]['sha256']
    file_id, folder_id = 'id:cnqzTNngPVsAAAAAAAuhkg', 'id:cnqzTNngPVsAAAAAAAydGg'
    file = next(x['result']['file'] for x in fresh['metadata'] if x['requested_id'] == file_id)
    folder = next(x['result']['folder'] for x in fresh['metadata'] if x['requested_id'] == folder_id)
    previous_file = next(x['file'] for x in read(HERE / 'selected-metadata.json')['entries'] if x['requested_id'] == file_id)
    assert all(file[key] == previous_file[key] for key in ['id', 'rev', 'size', 'path_display'])
    assert file['path_display'].rsplit('/', 1)[0] == folder['path_display']
    receipt = next(x for x in read(HERE / 'download-receipts.json') if x['id'] == file_id)
    local = Path(receipt['local_path'])
    assert local.stat().st_size == receipt['size'] == file['size'] and sha(local) == receipt['sha256']
    raw = local.read_bytes()
    assert hashlib.sha256(b''.join(hashlib.sha256(raw[i:i+4*1024*1024]).digest() for i in range(0,len(raw),4*1024*1024))).hexdigest() == receipt['content_hash']
    links = {x['file_name']: x for x in read(HERE / 'metadata-links.json')['results']}
    now = datetime.now(timezone.utc).isoformat()
    evidence_path = HERE / 'white-gold/image-and-source-evidence.json'
    write(evidence_path, {'recorded_utc': now, 'current_complete_folder_census': rel(refresh_path),
        'file_ids': [x['file_id'] for x in listing['entries']], 'folder_id': folder_id,
        'primary_file_id': file_id, 'primary_rev': file['rev'], 'primary_bytes': file['size'],
        'primary_sha256': receipt['sha256'], 'primary_Dropbox_content_hash': receipt['content_hash'],
        'viewed': [rel(HERE / 'file-review-3.jpg'), rel(local)],
        'observations': 'Eight close-ups show a pale/grey ground with irregular gold-coloured leaf-like flakes across the relief. None establishes the entire panel outline, scale, rear or an installed scene. Cropped relief/folder association supports a provisional Leaf Growth finish reference; exact complete-design identity awaits owner.',
        'real_gold_leaf_composition_confirmed': False, 'full_component_outline_verified': False,
        'same_size_or_cast_as_White_confirmed': False, 'current_physical_stock_confirmed': False,
        'missing_photos': ['Complete-panel front', 'In-situ installation', 'Series/context arrangement', 'Finished rear/fixing detail'],
        'counting_scope': 'Eight media files do not establish eight sculptures or multiple moulds.'})
    variant = 'LEAF-GROWTH-WHITE-GOLD'
    def item(suffix, field, display, value, basis, refs):
        return {'proposal_id': variant + '-' + suffix, 'field': field, 'display': display, 'value': value,
            'status': 'UNAPPROVED CONDITIONAL FINISH PROPOSAL', 'basis': basis, 'source_refs': refs,
            'owner_approved': False, 'physical_specs_verified': False}
    items = [
        item('DIMENSIONS', 'Individual dimensions and depth', 'Approximately100×30×6cm — conditional proposal if this is the same panel format as White',
            {'proposed_cm': [100, 30, 6], 'actual_measured_cm': None, 'assumed_White_size_relationship_confirmed': False},
            'Use related White single-offer dimensions as a discussion proposal only. The Gold detail crops have no complete outline or reliable scale; no full Gold panel size or White/Gold dimensional equivalence is established.',
            [rel(white_path), rel(evidence_path)]),
        item('WEIGHT', 'Individual dry weight', 'Approximately18kg — conditional working estimate assuming the White export build; related12kg historical difference remains unresolved',
            {'conditional_proposed_weight_kg': 18, 'related_White_export_kg': 18,
             'related_White_historical_estimate_kg': 12, 'actual_weighed_kg': None,
             'source_difference_is_measured_range': False},
            '18kg is a conditional Gold discussion estimate only if size and construction match the related White export. White itself has18kgexport versus12kgdated estimates and is unweighed. Do not average those sources or treat them as measured Gold weight bounds.',
            [rel(white_path), rel(HERE / 'dated-price-source-scope.json')]),
        item('MATERIAL', 'Material and finish', 'White cast mineral-composite base with a gold-leaf-effect surface — proposal; binder and actual gold content unknown',
            {'proposed_base': 'White cast mineral composite', 'visible_surface': 'Irregular gold-coloured leaf-like patches',
             'actual_binder': None, 'actual_gold_leaf': None, 'metal_composition': None,
             'reinforcement': None, 'sealer': None, 'care': None},
            'The folder is named White and Gold Leaf and the native close-up shows patchy metallic-looking leaf-like flakes. Mineral-composite base is a working proposal. A photograph/name does not certify genuine gold, alloy/purity, binder, adhesion, backing, sealant or weather suitability.',
            [rel(evidence_path), file_id]),
        item('FIXING', 'Fixing', 'Two concealed rear hanging points — proposal for the assumed long panel; actual hardware and rated load unknown',
            {'proposed_count': 2, 'proposed_position': 'Upper back, subject to actual orientation and rear construction',
             'actual_count': None, 'actual_hardware': None, 'rated_load': None},
            'This is a geometry-based discussion proposal for the assumed100×30cm format. The White fixing is also unapproved; no fixing hardware/count is transferred as fact. Gold has no finished rear view or attachment/load record.',
            [rel(evidence_path), rel(white_path)]),
        item('PRICE', 'Individual retail price', '£900 per panel — uncosted proposal; no exact Gold offer or quote verified',
            {'proposed_price_gbp': 900, 'related_White_price_gbp': 800, 'uncosted_provisional_finish_allowance_gbp': 100,
             'actual_Gold_offer_price_gbp': None, 'owner_individual_price_approved': False},
            'Proposal uses the related White800GBPlisting plus an arbitrary100GBP finish allowance for owner discussion. It is not a sourced Gold price, production costing, margin calculation or quote; Gold material and complete size remain unconfirmed.',
            [rel(HERE / 'white-gold/related-white-public-source.json')]),
        item('AVAILABILITY', 'Availability', 'Made to order / enquire — proposal; physical stock, reproduction and lead time unknown',
            {'proposed_policy': 'Made to order / enquire subject to production confirmation',
             'physical_stock': None, 'reproducibility': None, 'lead_time': None},
            'Detail photos and dated White made-to-order policy do not establish a current complete Gold cast, usable mould, Gold production capability, stock or delivery date. No live availability is changed.',
            [rel(evidence_path), rel(HERE / 'dated-price-source-scope.json')])]
    mapping = {'platform_record_level': {'squarespace_id': None, 'shopify_handle': None, 'shared_sku': None,
        'status': 'EXACT WHITE/GOLD FINISH OFFER AND PLATFORM PAIR UNCONFIRMED'},
        'dropbox_listing_level': {'file_id': file_id, 'folder_id': folder_id,
            'status': 'DETAIL-ONLY FINISH REFERENCE; EXACT COMPLETE DESIGN/LISTING IMAGE UNVERIFIED'},
        'individual_component_level': {'proposed_quantity': 1, 'complete_component_outline_verified': False,
            'same_size_or_physical_cast_as_White_confirmed': False,
            'whole_set_dimensions_weight_price_transferred': False},
        'related_White_offer_only': white['platform_mapping']['platform_record_level'] | {
            'scope': 'White evidence only; no Gold SKU, size, weight, stock or price confirmation'},
        'live_Shopify_account_refreshed': False, 'current_native_public_SKUs_reparsed': False}
    coverage = {'detail_images': 8, 'complete_individual_front': False, 'in_situ': False,
        'series_arrangement_reference': False, 'finished_rear': False, 'rear_fixing_detail': False,
        'verified_client_installation': False, 'scope': 'All eight current finish images are cropped details. White full-front, brick-wall and red-board references remain White evidence.'}
    card = {'schema_version': 1, 'prepared_utc': now, 'component_id': 'BC-LEAF-GROWTH', 'review_number': 68,
        'family': 'Leaf Growth', 'family_review_number': 2, 'family_review_total': 2,
        'family_total_scope': white['family_total_scope'], 'size_finish_variant_id': variant, 'variant_only_review': True,
        'proposed_name': 'Leaf Growth — White and Gold Leaf', 'display_name': 'Leaf Growth — White and Gold Leaf',
        'review_decision_mode': 'SIZE_FINISH_VARIANT_NAME_AND_SPECIFICATIONS',
        'identity_decision_destination': 'size_finish_variant_decisions',
        'scope': 'Owner review of the depicted cropped White/Gold finish reference and intended Leaf Growth identity. Complete panel outline, size, binder/real-gold composition, physical cast/mould and offer relationship remain unverified. Six conditional discussion proposals are separate from name approval.',
        'primary_image_id': file_id, 'primary_folder_id': folder_id,
        'primary_image_link': links[file_id]['copy_link_url'], 'primary_folder_link': links[folder_id]['copy_link_url'],
        'second_detail_image_id': 'id:cnqzTNngPVsAAAAAAAuYYw',
        'second_detail_image_link': links['id:cnqzTNngPVsAAAAAAAuYYw']['copy_link_url'],
        'metadata_checked_utc': fresh['checked_utc'], 'reference_refresh': rel(refresh_path),
        'identity_evidence': rel(evidence_path), 'related_White_review': rel(white_path),
        'specification_review_items': items, 'platform_mapping': mapping, 'photo_coverage': coverage,
        'identity_confirmed': False, 'specifications_approved': False, 'physical_specs_verified': False,
        'individual_sale_unit': {'quantity': 1, 'description': 'Proposed one White/Gold Leaf Growth panel; complete silhouette requires verification',
            'live_listing_prepared_or_published': False},
        'source_conflicts': ['Related White18kgexport versus12kghistorical estimate is unresolved; Gold mass is unweighed.',
            'White source size and800GBPprice are analogies only; Gold100×30×6cm/18kg/900GBPare unapproved conditional proposals.',
            'Only cropped Gold details exist; whole-panel identity and actual gold-leaf composition require confirmation.'],
        'open_gaps': ['Owner detail-reference name and intended Leaf Growth identity', 'Complete-panel front and actual face/depth measurements',
            'Actual weighed Gold mass; related White18kgversus12kgdifference', 'Binder, real gold/alloy, reinforcement, sealer and care',
            'Finished rear/fixings, attachments and rated load', 'Individual Gold price, physical stock, reproduction and lead time',
            'Exact Gold Squarespace/Shopify counterpart/shared SKU', 'Gold installation and series/context photographs', 'Current cast/mould inventory'],
        'next_review_after_keep': white['next_global_component'], 'next_global_scope': white['next_global_scope'],
        'remote_files_changed': False, 'live_platform_records_changed': False}
    write(HERE / 'white-gold/before-stage-review.json', {'recorded_utc': now,
        'files': {rel(paths[key]): value for key, value in before.items()}, 'protected_sha256': protected})
    write(output, card)
    parent = p['reviews']['BC-LEAF-GROWTH']
    assert parent['identity_confirmed'] and parent['identity_approval'] == rel(keep_path)
    assert variant not in parent.get('size_finish_variants', {})
    parent.setdefault('size_finish_variants', {})[variant] = {'reviewed_utc': now, 'review_number': 68,
        'proposed_name': card['proposed_name'], 'size_finish_variant_id': variant, 'identity_confirmed': False,
        'specifications_approved': False, 'physical_specs_verified': False, 'specification_proposals': copy.deepcopy(items),
        'primary_image_id': file_id, 'primary_folder_id': folder_id, 'review_record': rel(output),
        'platform_mapping': mapping, 'photo_coverage': coverage, 'gaps': card['open_gaps']}
    assert len(parent['pending_size_finish_variants']) == 1 and parent['pending_size_finish_variants'][0]['variant_id'] == variant
    parent['pending_size_finish_variants'] = []
    assert p['family_review_progress']['Leaf Growth']['review_reference_cards_answered'] == 1
    state = 'Awaiting Leaf Growth White and Gold Leaf detail-reference identity; all six conditional proposals pending'
    cp.update({'current_size_finish_variant_id': variant, 'current_component_layout_id': None,
        'proposed_name': card['proposed_name'], 'state': state, 'current_review_record': rel(output),
        'current_family_review_number': 2, 'current_answer_recorded': False, 'current_specification_answer_recorded': False,
        'current_dimension_answer_recorded': False, 'current_partial_specification_answer_recorded': False,
        'current_dimension_approval': None, 'current_owner_face_dimensions_cm': None,
        'current_identity_relationship_answer_recorded': False, 'current_identity_relationship_approval': None,
        'canonical_depicted_name': None, 'current_separate_saleable_design': None, 'working_version_user_approved': False,
        'review_decision_mode': card['review_decision_mode'], 'question_scope': card['scope'],
        'answer_state': 'White name kept; White/Gold detail name and six conditional proposals unapproved.',
        'primary_image': {'file_id': file_id, 'name': file['name'], 'path_display': file['path_display'],
            'copy_link_url': card['primary_image_link'], 'open_in_dropbox_url': links[file_id]['open_in_dropbox_url']},
        'containing_folder': {'folder_id': folder_id, 'name': folder['name'], 'path_display': folder['path_display'],
            'copy_link_url': card['primary_folder_link'], 'open_in_dropbox_url': links[folder_id]['open_in_dropbox_url']},
        'metadata_checked_utc': fresh['checked_utc'], 'family_review_evidence': rel(evidence_path),
        'displayed_identity_evidence_file_ids': [file_id], 'displayed_identity_evidence_folder_ids': [folder_id],
        'current_component_source_notes': [x['display'] for x in items], 'next_review_after_keep': card['next_review_after_keep'], 'updated_utc': now})
    cp['family_review_order'][1]['label'] = card['proposed_name']
    c['interactive_review_state'].update({'current_size_finish_variant_id': variant, 'current_component_layout_id': None,
        'current_name': card['proposed_name'], 'state': state, 'family_review_number': 2,
        'specification_proposals_approved': False, 'working_version_user_approved': False,
        'review_decision_mode': card['review_decision_mode']})
    c['current_component_review_record'] = rel(output)
    c['updated_utc'] = p['updated_utc'] = now
    docs['root']['current_component_review'] = copy.deepcopy(c)
    docs['root']['updated_utc'] = now
    for key in before['progress']['reviews']['BC-LEAF-GROWTH']:
        if key != 'pending_size_finish_variants':
            assert parent[key] == before['progress']['reviews']['BC-LEAF-GROWTH'][key], key
    assert all(p['reviews'][key] == value for key, value in before['progress']['reviews'].items() if key != 'BC-LEAF-GROWTH')
    for key in ['parallel_import_queue', 'parallel_owner_reviews', 'parallel_evidence_flags', 'pending_specification_reviews']:
        assert cp[key] == before['walkthrough'][key]
    assert len(items) == 6 and all(not x['owner_approved'] for x in items)
    assert all(sha(path) == hashes[key] for key, path in paths.items()), 'Shared writer collision'
    assert all(sha(Path(path)) == digest for path, digest in protected.items())
    for key, path in paths.items():
        write(path, docs[key])
        assert read(path) == docs[key]
    result = {'status': 'PASS', 'current_name': card['proposed_name'], 'current_complete_Gold_detail_census': 8,
        'all_six_groups_unapproved': True, 'White_approval_and_specification_conflict_preserved': True,
        'Gold_full_outline_size_material_price_stock_and_platform_offer_not_confirmed': True,
        'previous_approvals_imports_reservations_model_workbook_and_source_cards_preserved': True,
        'checkpoint_copies_match': read(paths['root'])['current_component_review'] == read(paths['component'])}
    write(HERE / 'white-gold/review-validation.json', result)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
