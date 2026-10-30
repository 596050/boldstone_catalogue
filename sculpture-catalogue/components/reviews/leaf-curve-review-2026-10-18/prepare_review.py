"""Prepare an individual Leaf Curve review from a complete bounded two-folder census."""
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
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temp.replace(path)


def main():
    card_path = HERE / 'component-review.json'
    assert not card_path.exists(), 'Already frozen'
    paths = {'walkthrough': REVIEWS / 'walkthrough_checkpoint.json', 'progress': REVIEWS / 'specification_review_progress.json',
        'component': ROOT / 'components/checkpoint.json', 'root': ROOT / 'checkpoint.json'}
    docs = {key: read(path) for key, path in paths.items()}
    before = copy.deepcopy(docs)
    hashes = {key: sha(path) for key, path in paths.items()}
    cp, progress, component = (docs[key] for key in ['walkthrough', 'progress', 'component'])
    assert cp['current_component_id'] == 'BC-FOUNTAIN-MED' and cp['current_answer_recorded']
    assert cp['next_review_after_keep']['component_id'] == 'BC-LEAF-CURVE'
    assert docs['root']['current_component_review'] == component and 'BC-LEAF-CURVE' not in progress['reviews']
    assert not any(x['component_id'] == 'BC-LEAF-CURVE' for x in cp['parallel_owner_reviews'])
    med_keep_path = ROOT / cp['last_identity_approval']
    assert read(med_keep_path)['confirmed_name'] == 'Fountain Palm Mediterranean — White'
    model_path = ROOT / 'components/evidence/component_register.json'
    model = read(model_path)
    native = next(x for x in model['components'] if x['component_id'] == 'BC-LEAF-CURVE')
    assert native['offer_refs'] == [] and native['group_refs'] == ['G181', 'G182']
    index = cp['review_order'].index('BC-LEAF-CURVE')
    assert index + 1 == 66 and cp['review_order'][index+1] == 'BC-LEAF-FORM'
    meta_path = HERE / 'metadata-links.json'
    meta = read(meta_path)
    assert [len(x['entries']) for x in meta['listings']] == [80, 8]
    assert all(not x['has_more'] and not x['cursor'] for x in meta['listings'])
    metadata = {x['request_id']: x for x in meta['metadata']}
    primary = metadata['id:cnqzTNngPVsAAAAAAAylMQ']['file']
    folder = metadata['id:cnqzTNngPVsAAAAAAAyijQ']['folder']
    context_id, context_folder_id = 'id:cnqzTNngPVsAAAAAAAuY0w', 'id:cnqzTNngPVsAAAAAAAyijg'
    links = {x['file_name']: x for x in meta['previews']}
    image_index = read(HERE / 'image-review-index.json')
    previews, originals = image_index['cached_previews'], read(HERE / 'download-receipts.json')
    assert len(previews) == 88 and len(originals) == 5
    assert all(sha(Path(x['preview_path'])) == x['sha256'] for x in previews)
    for receipt in originals:
        path = Path(receipt['local_path'])
        data = path.read_bytes()
        assert len(data) == receipt['size'] == metadata[receipt['id']]['file']['size'] and sha(path) == receipt['sha256']
        assert hashlib.sha256(b''.join(hashlib.sha256(data[i:i+4194304]).digest() for i in range(0, len(data), 4194304))).hexdigest() == receipt['content_hash']
    now = datetime.now(timezone.utc).isoformat()
    source_dir = ROOT / 'components/evidence/price-source-review-2026-10-17'
    text_checks = []
    for path in sorted(source_dir.glob('*.txt')):
        hits = [{'line': i+1, 'text': line} for i, line in enumerate(path.read_text().splitlines())
            if 'leaf curve' in line.lower() or 'curve leaf' in line.lower()]
        text_checks.append({'path': str(path), 'sha256': sha(path), 'exact_name_hits': hits})
    source_check_path = HERE / 'source-platform-check.json'
    write(source_check_path, {'checked_utc': now, 'baseline_component': native,
        'component_source_claims': [x for x in model['claims'] if x.get('component_id') == 'BC-LEAF-CURVE'],
        'price_document_text_checks': text_checks,
        'targeted_public_search_queries': ['site:boldstonesculpture.com "Leaf Curve"', 'site:boldstonesculpture.com "Golden Palm" sculpture'],
        'related_named_records': [{'offer_ref': x['offer_ref'], 'title': x['title'], 'source_url': x['source_url'],
            'existing_image_path': x.get('image_path'), 'existing_image_file_id': x.get('image_file_id')}
            for x in model['platform_records'] if x['offer_ref'] in ['O028', 'O042', 'O058']],
        'conclusion': 'No exact Leaf Curve platform pair or specification row established in reviewed sources. Golden Palm, Leaf Form and Two Leaf Forms have existing image associations to different designs/folders; no title-only transfer.',
        'scope': 'Bounded source review, not an exhaustive live commerce-account audit. Leaf Growth100×30price rows belong to another design and are not transferred.'})
    observed = {'complete_fronts_and_details': 'Square white ground with irregular metallic gold-coloured leaf-like patches across intersecting broad curved relief.',
        'brick_context': 'Tile appears approximately3brick courses tall, supporting a loose25cm-square hypothesis; brick/course size and perspective are uncalibrated.',
        'two_visible_display_supports': {'file_ids': ['id:cnqzTNngPVsAAAAAAAuSdw', 'id:cnqzTNngPVsAAAAAAAub3g'],
            'description': 'Two metal support pegs project below the displayed panel. These do not expose or identify finished rear hardware, anchorage or rated load.'},
        'monochrome_reference': {'file_id': 'id:cnqzTNngPVsAAAAAAAuXxw', 'filename_suffix': '069.jpg',
            'observation': 'A monochrome-looking photograph; no separate plain-white finish is established from it.'},
        'counting_scope': 'Repeated complete fronts, crops, rotations and lighting views are image evidence, not extra component, finish, mould or physical-stock records.'}
    write(HERE / 'image-observations.json', {'checked_utc': now, 'all_previews_inspected': 88,
        'originals_hash_verified_and_viewed': 5, 'observations': observed, 'contact_sheets': image_index['contact_sheets']})
    items = []

    def item(suffix, field, display, value, basis, sources):
        items.append({'proposal_id': 'LEAF-CURVE-WHITE-GOLD-' + suffix, 'field': field, 'display': display,
            'value': value, 'status': 'UNAPPROVED WORKING GUESS; ACTUAL COMPONENT SPECIFICATION UNKNOWN',
            'basis': basis, 'source_refs': sources, 'owner_approved': False, 'physical_specs_verified': False})

    item('DIMENSIONS', 'Individual dimensions and depth', 'Approximately25 H ×25 W ×5 D cm — visual scale and depth guess; unmeasured',
        {'proposed_dimensions_cm': [25, 25, 5], 'actual_measured_cm': None},
        'Near-square front spans about3brick courses in native wall references.25cmis a rough photographic scale hypothesis, not calibrated brick measurement.5cmmaximum projection is a discussion assumption; no ruler/side specification establishes depth.', [primary['id'], context_id, 'id:cnqzTNngPVsAAAAAAAuSdw'])
    weight_low, weight_high = 0.25**2 * 0.02 * 1700, 0.25**2 * 0.04 * 1900
    item('WEIGHT', 'Individual dry weight', 'Approximately3kg; tentative2–5kg range conditional on proposed size and mineral-composite construction',
        {'proposed_weight_kg': 3, 'proposed_range_kg': [2, 5], 'actual_weighed_kg': None,
         'hypothetical_face_cm': [25, 25], 'hypothetical_average_solid_thickness_cm': [2, 4],
         'assumed_density_kg_m3': [1700, 1900], 'scenario_mass_range_kg': [weight_low, weight_high]},
        'Scenario only: proposed25×25cmface × assumed2–4cmaverage solid thickness × assumed1700–1900kg/m3density gives2.125–4.75kg, rounded2–5kg. Actual size, thickness, binder/density, backing and cavities are unknown.3kgis an illustrative working number, not a measurement or material-certified calculation.', [rel(HERE / 'image-observations.json')])
    item('MATERIAL', 'Material and finish', 'Cast mineral composite with white ground and gold-leaf effect — hypothesis; binder and actual leaf composition unknown',
        {'visible_finish': 'White with irregular metallic gold-coloured leaf-like surface patches',
         'proposed_substrate': 'Cast mineral composite', 'actual_binder': None, 'actual_leaf_metal_or_purity': None, 'sealer': None},
        'Rough pale surface and wrinkled reflective patches support a leaf-applied appearance. Photographs/folder label do not certify gypsum/cement/resin binder, real gold versus imitation leaf, purity, size/adhesive, sealer, backing, reinforcement or weather suitability.', [primary['id'], 'id:cnqzTNngPVsAAAAAAAui9w'])
    item('FIXING', 'Fixing', 'Concealed rear fixing(s) proposed; two display support pegs visible; actual rear hardware and load unknown',
        {'proposed_scheme': 'Concealed rear fixing(s)', 'visible_display_support_pegs': 2,
         'permanent_hardware_type': None, 'permanent_hardware_count': None, 'rated_load': None},
        'Native brick-wall views show two rods supporting the bottom of the displayed panel. This is display/support evidence, not a finished rear-hardware specification. No rear was found in88reviewed front/detail/outdoor views; count, attachment and safe load remain unknown.', ['id:cnqzTNngPVsAAAAAAAuSdw', 'id:cnqzTNngPVsAAAAAAAub3g', rel(meta_path)])
    item('PRICE', 'Individual retail price', '£250–£350 per panel — discussion range; no exact source-priced offer or owner price approval',
        {'proposed_range_gbp': [250, 350], 'owner_price_approved': False, 'exact_existing_offer_confirmed': False},
        'An editorial owner-review range for a small assumed25cm-square decorated relief. It is not a recovered Leaf Curve selling price or a costed valuation. No price or SKU is inherited from Golden Palm, Leaf Form, a multi-piece set or another finish.', [rel(source_check_path)])
    item('AVAILABILITY', 'Availability', 'Made to order / enquire — policy proposal; stock, reproducibility and lead time unknown',
        {'proposed_policy': 'Made to order / enquire subject to production confirmation', 'physical_stock': None,
         'reproducibility': None, 'lead_time': None},
        'Photographed past objects do not establish current stock, a usable mould, repeatable surface treatment, capacity or delivery date.', [rel(meta_path)])
    coverage = {'complete_individual_front': True, 'detail_views_available': True, 'outdoor_wall_display': True,
        'outdoor_context_folder_id': context_folder_id, 'outdoor_context_reference_id': context_id,
        'outdoor_context_reference_link': links[context_id]['copy_link_url'],
        'indoor_room_setting_established': False, 'series_arrangement_established': False,
        'finished_rear': False, 'rear_fixing_detail': False, 'actual_client_installation_provenance_confirmed': False,
        'scope': 'Fresh complete80individual/detail and8context file census;88previews inspected in3contact sheets. Five originals downloaded/hash-verified/viewed. In Situ folder contains brick-wall displays; an actual room setting or series arrangement was not established. A wall-front rendering and monochrome photograph do not create separate finishes or verify installations.'}
    mapping = {'status': 'EXACT LEAF CURVE PLATFORM OFFER UNCONFIRMED IN REVIEWED SOURCES',
        'squarespace_id': None, 'shopify_handle': None, 'shared_sku': None,
        'individual_offer_confirmed': False, 'live_platform_account_refreshed': False}
    next_review = {'component_id': 'BC-LEAF-FORM', 'review_number': 67, 'label': 'Leaf Form — review individual designs and finishes'}
    card = {'schema_version': 1, 'prepared_utc': now, 'component_id': 'BC-LEAF-CURVE', 'review_number': 66,
        'family': 'Leaf Curve', 'family_review_number': 1, 'family_review_total': 1,
        'family_total_scope': 'One selected individual design/finish review card; image count is not physical stock.',
        'size_finish_variant_id': 'LEAF-CURVE-WHITE-GOLD', 'proposed_name': 'Leaf Curve — White and Gold Leaf',
        'display_name': 'Leaf Curve — White and Gold Leaf', 'review_decision_mode': 'INDIVIDUAL_COMPONENT_NAME_AND_SPECIFICATIONS',
        'scope': 'One square component with intersecting broad curves and mixed white/gold-coloured surface. Owner name approval is separate from six guesses, exact finish chemistry, cast identity, stock and platform mapping.',
        'primary_image_id': primary['id'], 'primary_folder_id': folder['id'],
        'primary_image_link': links[primary['id']]['copy_link_url'], 'primary_folder_link': links[folder['id']]['copy_link_url'],
        'native_front_reference_id': 'id:cnqzTNngPVsAAAAAAAuSdw',
        'native_front_reference_link': links['id:cnqzTNngPVsAAAAAAAuSdw']['copy_link_url'],
        'context_image_id': context_id, 'context_folder_id': context_folder_id,
        'context_image_link': links[context_id]['copy_link_url'], 'context_folder_link': links[context_folder_id]['copy_link_url'],
        'metadata_checked_utc': meta['selected_metadata_checked_utc'], 'reference_refresh': rel(meta_path),
        'specification_review_items': items, 'platform_mapping': mapping, 'photo_coverage': coverage,
        'source_check': rel(source_check_path), 'image_observations': rel(HERE / 'image-observations.json'),
        'identity_confirmed': False, 'specifications_approved': False, 'physical_specs_verified': False,
        'open_gaps': ['Owner depicted name/identity', 'Actual face size, maximum projection and dry weight',
            'Binder, backing, reinforcement, leaf composition/purity, adhesive, sealing and care',
            'Finished rear, actual fixing type/count/attachment and load', 'Owner individual price, physical stock, reproducibility and lead time',
            'Exact Squarespace/Shopify pair/shared SKU', 'Indoor room setting, series image and installation provenance',
            'Exact physical cast and mould identity'],
        'next_review_after_keep': next_review, 'remote_files_changed': False, 'live_platform_records_changed': False}
    write(card_path, card)
    evidence = [model_path, source_check_path, meta_path, HERE / 'download-receipts.json', HERE / 'image-review-index.json',
        HERE / 'image-observations.json'] + [Path(x['local_path']) for x in originals] + [Path(x['preview_path']) for x in previews]
    write(HERE / 'source-audit.json', {'status': 'PASS', 'checked_utc': now, 'current_files_audited': 88,
        'fresh_originals_hash_verified_and_viewed': 5, 'owner_approvals_inferred': False,
        'evidence_sha256': {str(path): sha(path) for path in sorted(set(evidence))}})
    protected = {str(path): sha(path) for path in [REVIEWS / 'user_classifications.json', model_path,
        ROOT / cp['register_workbook'], med_keep_path, ROOT / cp['current_review_record'], card_path]}
    write(HERE / 'before-stage-review.json', {'recorded_utc': now,
        'files': {rel(paths[key]): value for key, value in before.items()}, 'protected_sha256': protected})
    progress['reviews']['BC-LEAF-CURVE'] = {'reviewed_utc': now, 'review_number': 66,
        'proposed_name': card['proposed_name'], 'size_finish_variant_id': card['size_finish_variant_id'],
        'identity_confirmed': False, 'specifications_approved': False, 'physical_specs_verified': False,
        'specification_proposals': copy.deepcopy(items), 'primary_image_id': primary['id'], 'primary_folder_id': folder['id'],
        'review_record': rel(card_path), 'platform_mapping': mapping, 'photo_coverage': coverage, 'gaps': card['open_gaps']}
    progress['family_review_progress']['Leaf Curve'] = {'family': 'Leaf Curve', 'status': 'FIRST_PASS_IN_PROGRESS',
        'updated_utc': now, 'review_reference_cards_answered': 0, 'review_reference_total': 1,
        'reference_total_is_sculpture_count': False, 'specifications_complete': False}
    progress['updated_utc'] = now
    state = 'Awaiting Leaf Curve White and Gold Leaf individual name; all six guesses pending'
    order = [{'component_id': 'BC-LEAF-CURVE', 'review_number': 66, 'variant_id': card['size_finish_variant_id'], 'label': card['proposed_name']}]
    cp.update({'current_component_id': 'BC-LEAF-CURVE', 'current_review_number': 66,
        'current_size_finish_variant_id': card['size_finish_variant_id'], 'proposed_name': card['proposed_name'],
        'state': state, 'current_review_record': rel(card_path), 'current_family_review_number': 1, 'current_family_review_total': 1,
        'active_family': 'Leaf Curve', 'family_review_order': order, 'family_first_pass_complete': False,
        'current_answer_recorded': False, 'current_identity_relationship_answer_recorded': False,
        'current_identity_relationship_approval': None, 'canonical_depicted_name': None, 'current_separate_saleable_design': None,
        'current_specification_answer_recorded': False, 'current_dimension_answer_recorded': False,
        'current_partial_specification_answer_recorded': False, 'current_dimension_approval': None,
        'current_owner_face_dimensions_cm': None, 'working_version_user_approved': False,
        'review_decision_mode': card['review_decision_mode'], 'question_scope': card['scope'],
        'answer_state': 'No Leaf Curve name or specification approval yet; Fountain Palm reference first pass complete with specification gaps retained.',
        'primary_image': {'file_id': primary['id'], 'name': primary['name'], 'path_display': primary['path_display'],
            'copy_link_url': card['primary_image_link'], 'open_in_dropbox_url': links[primary['id']]['open_in_dropbox_url']},
        'containing_folder': {'folder_id': folder['id'], 'name': folder['name'], 'path_display': folder['path_display'],
            'copy_link_url': card['primary_folder_link'], 'open_in_dropbox_url': links[folder['id']]['open_in_dropbox_url']},
        'family_review_evidence': rel(meta_path), 'metadata_checked_utc': meta['selected_metadata_checked_utc'],
        'next_review_after_keep': next_review, 'displayed_identity_evidence_file_ids': [primary['id']],
        'displayed_identity_evidence_folder_ids': [folder['id']], 'current_component_source_notes': [x['display'] for x in items],
        'family_counting_note': card['family_total_scope'], 'updated_utc': now})
    component['interactive_review_state'].update({'current_component_id': 'BC-LEAF-CURVE', 'review_number': 66,
        'current_size_finish_variant_id': card['size_finish_variant_id'], 'current_name': card['proposed_name'],
        'state': state, 'active_family': 'Leaf Curve', 'family_review_number': 1, 'family_review_total': 1,
        'current_identity_relationship_answer_recorded': False, 'canonical_depicted_name': None,
        'current_separate_saleable_design': None, 'current_dimension_answer_recorded': False,
        'current_owner_face_dimensions_cm': None, 'specification_proposals_approved': False,
        'working_version_user_approved': False, 'review_decision_mode': card['review_decision_mode']})
    component['current_component_review_record'] = rel(card_path)
    component['last_family_media_review'] = {'family': 'Leaf Curve', 'observed_utc': meta['selected_metadata_checked_utc'],
        'files': 88, 'folders': 2, 'scope': coverage['scope'], 'evidence': rel(meta_path), 'workbook_contains_this_live_media_audit': False}
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
    result = {'status': 'PASS', 'current_component': 'BC-LEAF-CURVE', 'six_unapproved_guesses': 6,
        'fresh_complete_file_census': 88, 'originals_verified_and_viewed': 5, 'Fountain_Palm_decisions_preserved': True,
        'exact_platform_offer_unconfirmed': True, 'ledger_model_workbook_prior_reviews_unchanged': True,
        'checkpoint_copies_match': read(paths['root'])['current_component_review'] == read(paths['component'])}
    write(HERE / 'review-validation.json', result)
    print(json.dumps(result))
    print(json.dumps({'image': card['primary_image_link'], 'folder': card['primary_folder_link'], 'context': card['context_image_link']}))


if __name__ == '__main__':
    main()
