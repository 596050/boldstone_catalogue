"""Stage one gold-coloured Faceted Mound with source-limited discussion guesses."""
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


def write(p, value):
    t = p.with_name(p.name + '.tmp')
    t.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    t.replace(p)


def main():
    card_path = HERE / 'component-review.json'
    assert not card_path.exists(), 'Already frozen'
    paths = {'walkthrough': REVIEWS / 'walkthrough_checkpoint.json', 'progress': REVIEWS / 'specification_review_progress.json',
        'component': ROOT / 'components/checkpoint.json', 'root': ROOT / 'checkpoint.json'}
    docs = {k: read(p) for k, p in paths.items()}
    before = copy.deepcopy(docs)
    hashes = {k: sha(p) for k, p in paths.items()}
    cp, progress, component = (docs[k] for k in ['walkthrough', 'progress', 'component'])
    assert cp['current_component_id'] == 'BC-EMBED-SHELLS' and cp['current_answer_recorded']
    assert cp['next_review_after_keep']['component_id'] == 'BC-FACET-MOUND'
    assert docs['root']['current_component_review'] == component
    prior_approval = ROOT / cp['last_identity_approval']
    assert read(prior_approval)['user_statement'] == 'Keep “Embedded Shells — White”'
    assert progress['reviews']['BC-EMBED-SHELLS']['owner_face_dimensions_cm'] == {'height': 70, 'width': 15, 'depth': None}
    model_path = ROOT / 'components/evidence/component_register.json'
    model = read(model_path)
    source_component = next(x for x in model['components'] if x['component_id'] == 'BC-FACET-MOUND')
    assert source_component['offer_refs'] == [] and source_component['maker_rows'] == []
    assert not any(x.get('component_id') == 'BC-FACET-MOUND' for x in model['claims'])
    packet_path = ROOT / 'components/parallel-preparation/20261017T164751Z/worker-01/packets.json'
    packet = next(x for x in read(packet_path)['entries'] if x['component_id'] == 'BC-FACET-MOUND')
    write(HERE / 'advisory-packet-used.json', {'source': rel(packet_path), 'source_sha256': sha(packet_path), 'packet': packet,
        'fresh_review_adjustment': 'Use approximate70×30cmface as a discussion guess from roughly2.3-to-1complete-photo proportions. The advisory70×25guess was not an owner-approved dimension. Absolute scale and depth remain unknown.'})
    meta = read(HERE / 'metadata-links.json')
    assert [(x['key'], len(x['entries']), x['has_more'], x['cursor']) for x in meta['listings']] == [('solo', 1, False, ''), ('context', 7, False, '')]
    refs = {x['request_id']: x for x in meta['metadata']}
    file = refs['id:cnqzTNngPVsAAAAAAAyk2Q']['file']
    folder = refs['id:cnqzTNngPVsAAAAAAAykCg']['folder']
    assert file['path_display'].rsplit('/', 1)[0] == folder['path_display']
    links = {x['file_name']: x for x in meta['previews']}
    thumbnails = read(HERE / 'image-review-index.json')['cached_previews']
    originals = read(HERE / 'download-receipts.json')
    assert len(thumbnails) == 8 and len(originals) == 3
    for receipt in originals:
        p = Path(receipt['local_path'])
        assert p.stat().st_size == receipt['size'] and sha(p) == receipt['sha256']
        b = p.read_bytes()
        assert hashlib.sha256(b''.join(hashlib.sha256(b[i:i+4194304]).digest() for i in range(0, len(b), 4194304))).hexdigest() == receipt['content_hash']
    analogies = [x for x in model['platform_records'] if x['offer_ref'] in ['O042', 'O047']]
    assert {x['offer_ref']: float(x['native_price']) for x in analogies} == {'O042': 600, 'O047': 500}
    write(HERE / 'other-design-analogy-sources.json', {'source_model': rel(model_path), 'source_model_sha256': sha(model_path),
        'records': analogies, 'scope': 'Preserved exports/public-source snapshot for different Golden Palm and Timeless Spiral designs. No current live price, Faceted Mound identity, SKU, material, stock or exact offer is inferred.'})
    now = datetime.now(timezone.utc).isoformat()
    items = []

    def item(suffix, field, display, value, basis, refs):
        items.append({'proposal_id': 'FACET-MOUND-GOLD-LEAF-' + suffix, 'field': field, 'display': display,
            'value': value, 'status': 'UNAPPROVED WORKING GUESS; NO OBJECT-SPECIFIC SOURCE SPECIFICATION',
            'basis': basis, 'source_refs': refs, 'owner_approved': False, 'physical_specs_verified': False})

    item('DIMENSIONS', 'Individual dimensions and depth', 'Approximately70 H ×30 W ×7–10 D cm — planning guess; unmeasured',
        {'proposed_height_cm': 70, 'proposed_width_cm': 30, 'proposed_depth_range_cm': [7, 10], 'measured_dimensions_cm': None},
        'The complete primary shows an approximately2.3-to-1portrait rectangle with pronounced curved facets.70×30matches those proportions but supplies no calibrated absolute scale.7–10cmmaximum projection is a separate weak planning guess, not a side measurement.', [file['id'], rel(HERE / 'advisory-packet-used.json')])
    item('WEIGHT', 'Individual dry weight', 'Approximately6–10kg — weak guess assuming mineral-composite construction; actual mass unknown',
        {'proposed_range_kg': [6, 10], 'actual_weighed_kg': None, 'construction_confirmed': False},
        'Discussion range only, conditional on proposed size and a relatively thin-backed or hollowed mineral-composite relief. Actual average material thickness, hollowing and binder are unknown; a solid or denser construction could be heavier. No set-mass division or certified density calculation claimed.', [rel(HERE / 'advisory-packet-used.json')])
    item('MATERIAL', 'Material and finish', 'Cast mineral/gypsum composite with an applied gold-leaf or gold-effect finish — hypothesis; binder and metal unknown',
        {'visible_appearance': 'Gold-coloured mottled metallic-looking surface over curved/angular relief', 'folder_finish_label': 'Gold Leaf',
            'proposed_substrate': 'Cast mineral/gypsum composite', 'actual_binder': None, 'actual_leaf_or_coating': None, 'gold_grade': None, 'sealer': None},
        'Gold Leaf is the Dropbox finish label. Viewed originals support gold colour and surface texture only; they cannot establish real gold leaf, alloy, purity, binder, backing, reinforcement, coating or outdoor suitability.', [file['id'], folder['id']])
    item('FIXING', 'Fixing', 'Concealed rear fixing — proposal; type, number, attachment and capacity unknown',
        {'proposed_scheme': 'Concealed rear fixing', 'hardware_type': None, 'count': None, 'rated_load': None},
        'All8current views show fronts or setting imagery; no rear or exact fixing instruction found. Concealed fixing is a planning placeholder, not an installation instruction or load approval.', [rel(HERE / 'metadata-links.json')])
    item('PRICE', 'Individual retail price', '£500–£800 per individual panel — discussion guess; no matched offer or owner price approval',
        {'proposed_range_gbp': [500, 800], 'exact_existing_offer_confirmed': False, 'owner_price_approved': False},
        'Other-design preserved records show Golden Palm600GBP and Timeless Spiral500GBP. These loosely inform a discussion range only; Faceted Mound has no exact priced offer, and actual finish labour/metal content are unknown. Analogues were not freshly repriced and no set price is divided.', [rel(HERE / 'other-design-analogy-sources.json')])
    item('AVAILABILITY', 'Availability', 'Made to order / enquire — policy proposal; production, stock and lead time unconfirmed',
        {'proposed_policy': 'Made to order / enquire subject to production confirmation', 'physical_stock': None, 'reproducibility': None, 'lead_time': None},
        'The images and folder names do not establish current cast stock, a usable mould, production capacity or a lead time. Owner must confirm whether an individual sale or reproduction can be offered.', [rel(HERE / 'advisory-packet-used.json')])
    coverage = {'complete_individual_front': True, 'room_setting_available': True, 'detail_visible_in_primary': True,
        'rear': False, 'separate_series_or_multi_component_arrangement_found': False,
        'same_physical_cast_in_settings_confirmed': False, 'actual_client_installation_provenance_confirmed': False,
        'scope': 'Fresh complete1solo+7context census. All8previews viewed; primary, brick-wall setting001 and blue-wall setting006 originals freshly downloaded/hash-verified/viewed. Matching depicted faceted motif in settings; scene provenance, actual cast and physical installation unconfirmed. No rear or separate series arrangement found.'}
    mapping = {'status': 'EXACT SQUARESPACE/SHOPIFY INDIVIDUAL OFFER UNCONFIRMED IN REVIEWED EXPORTS',
        'squarespace_id': None, 'shopify_handle': None, 'shared_sku': None, 'source_component_offer_refs': [],
        'analogy_offer_refs': ['O042', 'O047'], 'analogies_are_product_matches': False, 'live_platform_records_refreshed': False}
    next_review = {'component_id': cp['review_order'][52], 'review_number': 53, 'requires_pending_parallel_import': True}
    assert next_review['component_id'] == 'BC-FOUNTAIN-EG'
    card = {'schema_version': 1, 'prepared_utc': now, 'component_id': 'BC-FACET-MOUND', 'review_number': 46,
        'family': 'Faceted Mound', 'family_review_number': 1, 'family_review_total': 1,
        'size_finish_variant_id': 'FACET-MOUND-GOLD-LEAF', 'canonical_design_name': 'Faceted Mound',
        'proposed_name': 'Faceted Mound — Gold Leaf', 'display_name': 'Faceted Mound — Gold Leaf',
        'review_decision_mode': 'COMPONENT_NAME_AND_SPECIFICATIONS',
        'scope': 'One depicted complete individual gold-coloured faceted relief. Gold Leaf is a folder-based name proposal, not a material certificate. Name approval is separate from all six guesses and physical manufacture/stock.',
        'primary_image_id': file['id'], 'primary_folder_id': folder['id'],
        'primary_image_link': links[file['id']]['copy_link_url'], 'primary_folder_link': links[folder['id']]['copy_link_url'],
        'context_image_id': 'id:cnqzTNngPVsAAAAAAAyk2A', 'context_folder_id': 'id:cnqzTNngPVsAAAAAAAyigg',
        'context_image_link': links['id:cnqzTNngPVsAAAAAAAyk2A']['copy_link_url'],
        'context_folder_link': links['id:cnqzTNngPVsAAAAAAAyigg']['copy_link_url'],
        'alternate_setting_image_id': 'id:cnqzTNngPVsAAAAAAAuRPw',
        'alternate_setting_image_link': links['id:cnqzTNngPVsAAAAAAAuRPw']['copy_link_url'],
        'metadata_checked_utc': meta['checked_utc'], 'reference_refresh': rel(HERE / 'metadata-links.json'),
        'specification_review_items': items, 'platform_mapping': mapping, 'photo_coverage': coverage,
        'source_component_snapshot': source_component, 'advisory_packet': rel(HERE / 'advisory-packet-used.json'),
        'source_conflicts': ['Gold Leaf folder wording and gold appearance do not certify gold composition or substrate.',
            'Absolute size, maximum projection, mass and price are unapproved discussion guesses. No object-specific source specifications or exact platform offer are bound to this component.'],
        'open_gaps': ['Owner name and depicted identity', 'Measured height/width/maximum projection', 'Actual dry weight',
            'Substrate, backing, reinforcement, actual gold leaf/effect, sealer and care', 'Rear photograph and fixing hardware/count/attachment/load',
            'Individual price and current sale/stock/reproducibility/lead time', 'Exact individual platform IDs and sharedSKU',
            'Scene provenance and any intended series relationship'],
        'identity_confirmed': False, 'specifications_approved': False, 'physical_specs_verified': False,
        'next_review_after_keep': next_review, 'next_global_component_id': 'BC-FOUNTAIN-EG',
        'remote_files_changed': False, 'live_platform_records_changed': False}
    evidence = [model_path, packet_path, prior_approval] + [Path(x['local_path']) for x in originals] + [Path(x['preview_path']) for x in thumbnails]
    evidence += [p for p in HERE.iterdir() if p.is_file()]
    write(HERE / 'source-audit.json', {'status': 'PASS', 'checked_utc': now, 'current_files_audited': 8,
        'current_file_and_folder_metadata_checked': 10, 'fresh_originals_hash_verified_and_viewed': 3,
        'object_specific_six_fields_established': False, 'evidence_sha256': {str(p): sha(p) for p in sorted(set(evidence))}})
    write(card_path, card)
    protected = {str(p): sha(p) for p in [model_path, ROOT / cp['register_workbook'], REVIEWS / 'user_classifications.json',
        ROOT / cp['current_review_record'], prior_approval, card_path]}
    write(HERE / 'before-stage-review.json', {'recorded_utc': now, 'files': {rel(paths[k]): v for k, v in before.items()}, 'protected_sha256': protected})
    assert 'BC-FACET-MOUND' not in progress['reviews']
    progress['reviews']['BC-FACET-MOUND'] = {'reviewed_utc': now, 'review_number': 46, 'proposed_name': card['proposed_name'],
        'size_finish_variant_id': card['size_finish_variant_id'], 'identity_confirmed': False,
        'specifications_approved': False, 'physical_specs_verified': False, 'source_specifications_recorded': False,
        'working_guesses_recorded': True, 'specification_proposals': copy.deepcopy(items),
        'primary_image_id': file['id'], 'primary_folder_id': folder['id'], 'review_record': rel(card_path),
        'platform_mapping': mapping, 'photo_coverage': coverage, 'gaps': card['open_gaps']}
    progress['updated_utc'] = now
    state = 'Awaiting Faceted Mound Gold Leaf name/identity; six specification guesses separately pending'
    cp.update({'current_component_id': 'BC-FACET-MOUND', 'current_review_number': 46,
        'current_size_finish_variant_id': card['size_finish_variant_id'], 'proposed_name': card['proposed_name'],
        'state': state, 'current_review_record': rel(card_path), 'active_family': 'Faceted Mound',
        'current_family_review_number': 1, 'current_family_review_total': 1,
        'family_review_order': [{'component_id': 'BC-FACET-MOUND', 'review_number': 46, 'variant_id': card['size_finish_variant_id'], 'label': card['proposed_name']}],
        'family_first_pass_complete': False, 'current_answer_recorded': False, 'current_specification_answer_recorded': False,
        'current_dimension_answer_recorded': False, 'current_dimension_approval': None,
        'current_owner_face_dimensions_cm': None, 'current_partial_specification_answer_recorded': False,
        'current_identity_relationship_answer_recorded': False, 'current_identity_relationship_approval': None,
        'canonical_depicted_name': None, 'working_version_user_approved': False,
        'review_decision_mode': card['review_decision_mode'], 'question_scope': card['scope'],
        'answer_state': 'No answer yet; all six fields are unapproved guesses with source and assumption limits.',
        'primary_image': {'file_id': file['id'], 'name': file['name'], 'path_display': file['path_display'],
            'copy_link_url': card['primary_image_link'], 'open_in_dropbox_url': links[file['id']]['open_in_dropbox_url']},
        'containing_folder': {'folder_id': folder['id'], 'name': folder['name'], 'path_display': folder['path_display'],
            'copy_link_url': card['primary_folder_link'], 'open_in_dropbox_url': links[folder['id']]['open_in_dropbox_url']},
        'family_review_evidence': card['reference_refresh'], 'metadata_checked_utc': meta['checked_utc'],
        'next_review_after_keep': next_review, 'after_main_family_next_unclaimed': next_review,
        'displayed_identity_evidence_file_ids': [file['id']], 'displayed_identity_evidence_folder_ids': [folder['id']],
        'current_component_source_notes': [x['display'] for x in items], 'updated_utc': now})
    cp['next_serialized_parallel_import'] = {'trigger': 'AFTER_FACETED_MOUND_FIRST_PASS_BEFORE_MAIN_REVIEW53',
        'status': 'PENDING_NEXT_BOUNDED_EXACT_TRANSCRIPT_AND_CURRENT_REFERENCE_VERIFICATION',
        'source_queue': 'parallel_import_queue', 'approval_inferred': False,
        'scope': 'Completed packages received after batch4cutoff; ongoing reserved reviews need not wait for main owner answer or import.'}
    component['interactive_review_state'].update({'current_component_id': card['component_id'], 'review_number': 46,
        'current_size_finish_variant_id': card['size_finish_variant_id'], 'current_name': card['proposed_name'], 'state': state,
        'family_review_number': 1, 'family_review_total': 1, 'specification_proposals_approved': False,
        'working_version_user_approved': False, 'review_decision_mode': card['review_decision_mode'],
        'current_dimension_answer_recorded': False, 'current_owner_face_dimensions_cm': None})
    component['current_component_review_record'] = rel(card_path)
    component['last_family_media_review'] = {'family': 'Faceted Mound', 'observed_utc': meta['checked_utc'],
        'files': 8, 'folders': 2, 'scope': coverage['scope'], 'evidence': card['reference_refresh'], 'workbook_contains_this_live_media_audit': False}
    component['updated_utc'] = now
    docs['root']['current_component_review'] = copy.deepcopy(component)
    docs['root']['updated_utc'] = now
    assert all(progress['reviews'][k] == v for k, v in before['progress']['reviews'].items())
    assert cp['parallel_import_queue'] == before['walkthrough']['parallel_import_queue']
    assert cp['parallel_owner_reviews'] == before['walkthrough']['parallel_owner_reviews']
    assert all(sha(path) == hashes[k] for k, path in paths.items()), 'Shared writer collision'
    assert all(sha(Path(path)) == digest for path, digest in protected.items())
    for key, path in paths.items():
        write(path, docs[key])
        assert read(path) == docs[key]
    assert read(paths['root'])['current_component_review'] == read(paths['component'])
    result = {'status': 'PASS', 'current_component': card['component_id'], 'review_number': 46,
        'six_unapproved_working_guesses': 6, 'files_audited': 8, 'fresh_originals_hash_verified_and_viewed': 3,
        'Embedded_Shells_name_and70x15face_preserved': True, 'prior_owner_decisions_model_workbook_unchanged': True,
        'pending_imports_and_reservations_preserved': True, 'checkpoint_copies_match': True}
    write(HERE / 'review-validation.json', result)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
