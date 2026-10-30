"""Stage one blue-toned finish reference; keep the darker reference relationship open."""
import copy
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
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
    assert cp['current_component_id'] == 'BC-FOUNTAIN-EG' and cp['current_size_finish_variant_id'] == 'FOUNTAIN-EG-WHITE'
    assert cp['current_answer_recorded'] and cp['next_review_after_keep']['variant_id'] == 'FOUNTAIN-EG-BRONZE-VERDIGRIS'
    assert docs['root']['current_component_review'] == component
    white_card_path, white_keep_path = ROOT / cp['current_review_record'], ROOT / cp['last_identity_approval']
    white, keep = read(white_card_path), read(white_keep_path)
    assert keep['user_statement'] == 'Keep “Fountain Palm Egyptian — White”' and not keep['specifications_approved']
    model_path = ROOT / 'components/evidence/component_register.json'
    model = read(model_path)
    group = next(x for x in model['groups'] if x['group_ref'] == 'G162')
    assert group['id'] == 'id:cnqzTNngPVsAAAAAAAyiew'
    fountain_offers = [x for x in model['platform_records'] if 'fountain' in (x.get('title', '') + ' ' + x.get('native_description', '')).lower()]
    assert [x['offer_ref'] for x in fountain_offers] == ['O014']
    meta = read(HERE / 'metadata-links.json')
    assert len(meta['listing']['entries']) == 83 and not meta['listing']['has_more'] and not meta['listing']['cursor']
    refs = {x['request_id']: x for x in meta['metadata']}
    primary = refs['id:cnqzTNngPVsAAAAAAAylDg']['file']
    folder = refs['id:cnqzTNngPVsAAAAAAAyiew']['folder']
    assert primary['path_display'].rsplit('/', 1)[0] == folder['path_display']
    links = {x['file_name']: x for x in meta['previews']}
    thumbnails, originals = read(HERE / 'image-review-index.json')['cached_previews'], read(HERE / 'download-receipts.json')
    assert len(thumbnails) == 83 and len(originals) == 5
    for receipt in originals:
        p = Path(receipt['local_path'])
        assert p.stat().st_size == receipt['size'] and sha(p) == receipt['sha256']
        b = p.read_bytes()
        assert hashlib.sha256(b''.join(hashlib.sha256(b[i:i+4194304]).digest() for i in range(0, len(b), 4194304))).hexdigest() == receipt['content_hash']
    appearance = {'blue_toned_references': [], 'darker_indoor_references': []}
    for file in meta['listing']['entries']:
        n = int(re.search(r'__(\d+)\.', file['name']).group(1))
        key = 'blue_toned_references' if n == 1 or 3 <= n <= 26 or n == 49 else 'darker_indoor_references'
        appearance[key].append({'file_id': file['file_id'], 'name': file['name']})
    assert {key: len(value) for key, value in appearance.items()} == {'blue_toned_references': 26, 'darker_indoor_references': 57}
    now = datetime.now(timezone.utc).isoformat()
    write(HERE / 'appearance-reference-groups.json', {'checked_utc': now, 'groups': appearance,
        'scope': 'Observed image appearances only; neither distinct physical casts nor distinct finishes/moulds are established. No entire-folder identity or colour-equivalence assertion.',
        'current_primary': primary['id'], 'blue_outdoor_reference': 'id:cnqzTNngPVsAAAAAAAsSig',
        'darker_indoor_reference': 'id:cnqzTNngPVsAAAAAAAuQFQ', 'darker_yellow_board_reference': 'id:cnqzTNngPVsAAAAAAAsSyQ',
        'relationship_status': 'PENDING OWNER COMPARISON; NO SECOND SCULPTURE CREATED',
        'possible_explanations': ['Lighting/photography', 'Different finish treatment or stage', 'Different cast'],
        'physical_cast_count_inferred': False, 'same_finished_cast_confirmed': False})
    write(HERE / 'related-white-source-reference.json', {'white_review': rel(white_card_path), 'white_review_sha256': sha(white_card_path),
        'white_identity_approval': rel(white_keep_path), 'white_identity_approval_sha256': sha(white_keep_path),
        'white_offer_ref': 'O014', 'white_source_export_dimensions_cm': [100, 50, 6], 'white_shopify_export_weight_kg': 15,
        'white_public_price_gbp_observed': 900, 'white_public_price_observed_utc': read(HERE.parent / 'public-source-check.json')['checked_utc'],
        'scope': 'Related white version supplies discussion analogies only. No exact coloured offer, actual size, weight, construction, stock or price is inherited.'})
    items = []

    def item(suffix, field, display, value, basis, refs):
        items.append({'proposal_id': 'FOUNTAIN-EG-BRONZE-VERDIGRIS-' + suffix, 'field': field,
            'display': display, 'value': value, 'status': 'UNAPPROVED WORKING PROPOSAL; COLOURED CAST APPLICABILITY UNCONFIRMED',
            'basis': basis, 'source_refs': refs, 'owner_approved': False, 'physical_specs_verified': False})

    white_ref = rel(HERE / 'related-white-source-reference.json')
    item('DIMENSIONS', 'Individual dimensions and depth', 'Approximately100 H ×50 W ×6 D cm — proposal based on white version; coloured panel unmeasured',
        {'proposed_dimensions_cm': [100, 50, 6], 'actual_measured_cm': None},
        'Same depicted dense-channel geometry suggests the white version100×50×6cm as a working size. Photographs are not calibrated; exact same mould, scale and relief depth remain unconfirmed.', [white_ref, primary['id']])
    item('WEIGHT', 'Individual dry weight', 'Approximately15kg — guess assuming comparable mineral-composite construction to white; actual mass unknown',
        {'proposed_weight_kg': 15, 'actual_weighed_kg': None, 'construction_comparable_to_white_confirmed': False},
        'Use white Shopify15kg as a conditional planning estimate only. The coloured binder, backing, metal content and thickness are unknown and could change mass. No measured coloured weight or set-weight division claimed.', [white_ref])
    item('MATERIAL', 'Material and finish', 'Cast mineral composite with bronze/verdigris surface effect — hypothesis; binder, metal content and patination recipe unknown',
        {'visible_appearance': 'Blue-green mottled surface over dark metallic-looking relief', 'proposed_substrate': 'Cast mineral composite',
            'actual_binder': None, 'actual_metal_or_powder': None, 'patination_recipe': None, 'sealer': None},
        'Folder label and blue/bronze-looking images describe appearance only. White processAC730container evidence does not certify this coloured cast, solid bronze, a metal coating, actual corrosion chemistry, sealing or outdoor suitability.', [primary['id'], folder['id'], white_ref])
    item('FIXING', 'Fixing', 'Concealed rear fixing(s) — proposal; actual type, count, attachment and capacity unknown',
        {'proposed_scheme': 'Concealed rear fixing(s)', 'hardware_type': None, 'count': None, 'rated_load': None},
        'No rear or fixing hardware appears in the83current front/detail/display views. Indoor front display and white-family evidence do not establish actual coloured-panel hardware or load.', [rel(HERE / 'metadata-links.json')])
    item('PRICE', 'Individual retail price', '£900–£1,200 per panel — discussion proposal; no exact coloured offer or owner price approval',
        {'proposed_range_gbp': [900, 1200], 'exact_existing_coloured_offer_confirmed': False, 'owner_price_approved': False},
        'The earlier same-day900GBPwhite offer loosely anchors a discussion range only; no quantitative finish-cost model or confirmed coloured selling price is available. No automatic metallic premium, set-price allocation or current source-priced coloured offer is claimed.', [white_ref])
    item('AVAILABILITY', 'Availability', 'Made to order / enquire — proposed policy; stock, reproduction capability and lead time unknown',
        {'proposed_policy': 'Made to order / enquire subject to production confirmation', 'physical_stock': None,
            'reproducibility': None, 'lead_time': None},
        'Photos record depicted display references, not current stocked casts, a usable mould, finish reproducibility, capacity or lead time. Exact physical availability requires owner confirmation.', [rel(HERE / 'metadata-links.json')])
    mapping = {'status': 'EXACT BRONZE/VERDIGRIS SQUARESPACE/SHOPIFY OFFER UNCONFIRMED IN REVIEWED EXPORTS',
        'squarespace_id': None, 'shopify_handle': None, 'shared_sku': None, 'individual_offer_confirmed': False,
        'related_white_offer_ref': 'O014', 'related_white_shared_sku': 'DF-1-100.50',
        'white_offer_transferred_to_coloured_finish': False, 'live_platform_records_refreshed': False}
    coverage = {'complete_individual_front': True, 'detail_views_available': True, 'outdoor_display_context_available': True,
        'confirmed_installed_outdoor_wall_photo': False, 'rear': False, 'coloured_series_arrangement_established': False,
        'darker_indoor_reference_available': True, 'darker_indoor_reference_same_finish_or_cast_confirmed': False,
        'actual_client_installation_provenance_confirmed': False,
        'scope': 'Fresh complete83-file census; all83previews inspected across3contact sheets. Five current originals downloaded/hash-verified/viewed: clean001, outdoor003, dark indoor002, dark detail061 and yellow-board080.26blue-toned and57dark-indoor image references retained as observed appearances only; no distinct-cast/finish count or equivalence asserted. White paired arrangement is not a coloured-series photo.'}
    comparison = {'component_id': 'BC-FOUNTAIN-EG', 'review_number': 53, 'variant_id': 'FOUNTAIN-EG-DARK-REFERENCE-RELATIONSHIP',
        'label': 'Compare darker indoor Fountain Palm Egyptian reference with blue-toned reference',
        'review_decision_mode': 'DEPICTED_REFERENCE_FINISH_RELATIONSHIP', 'does_not_create_component_or_finish_record': True,
        'reference_file_id': 'id:cnqzTNngPVsAAAAAAAuQFQ', 'blue_reference_file_id': primary['id']}
    family_order = [copy.deepcopy(cp['family_review_order'][0]), copy.deepcopy(cp['family_review_order'][1]), comparison,
        copy.deepcopy(cp['family_review_order'][-1])]
    assert family_order[-1]['component_id'] == 'BC-FOUNTAIN-MED'
    card = {'schema_version': 1, 'prepared_utc': now, 'component_id': 'BC-FOUNTAIN-EG', 'review_number': 53,
        'family': 'Fountain Palm', 'family_review_number': 2, 'family_review_total': 4,
        'family_total_scope': 'Four review references/questions across designs, finish and a relationship check; not a physical sculpture or unique-design count.',
        'size_finish_variant_id': 'FOUNTAIN-EG-BRONZE-VERDIGRIS', 'variant_only_review': True,
        'canonical_design_name': 'Fountain Palm Egyptian', 'proposed_name': 'Fountain Palm Egyptian — Bronze and Verdigris',
        'display_name': 'Fountain Palm Egyptian — Bronze and Verdigris', 'review_decision_mode': 'SIZE_FINISH_VARIANT_NAME_AND_SPECIFICATIONS',
        'scope': 'Selected blue-toned001depicted finish reference. White name/offer/specifications remain separate. Name approval does not approve all83folder images as the same finish/cast, material chemistry, specifications or stock.',
        'primary_image_id': primary['id'], 'primary_folder_id': folder['id'],
        'primary_image_link': links[primary['id']]['copy_link_url'], 'primary_folder_link': links[folder['id']]['copy_link_url'],
        'outdoor_display_image_id': 'id:cnqzTNngPVsAAAAAAAsSig', 'outdoor_display_image_link': links['id:cnqzTNngPVsAAAAAAAsSig']['copy_link_url'],
        'darker_indoor_reference_id': 'id:cnqzTNngPVsAAAAAAAuQFQ', 'darker_indoor_reference_link': links['id:cnqzTNngPVsAAAAAAAuQFQ']['copy_link_url'],
        'darker_display_reference_id': 'id:cnqzTNngPVsAAAAAAAsSyQ', 'darker_display_reference_link': links['id:cnqzTNngPVsAAAAAAAsSyQ']['copy_link_url'],
        'metadata_checked_utc': meta['selected_metadata_checked_utc'], 'reference_refresh': rel(HERE / 'metadata-links.json'),
        'appearance_reference_groups': rel(HERE / 'appearance-reference-groups.json'), 'related_white_source': white_ref,
        'specification_review_items': items, 'platform_mapping': mapping, 'photo_coverage': coverage,
        'source_conflicts': ['No exact priced coloured platform offer or coloured-cast measurements/binder/fixing record is established.',
            'Blue outdoor versus dark indoor references could reflect lighting, treatment/stage or different casts; equivalence and distinct-finish count remain unresolved.'],
        'open_gaps': ['Owner selected blue-reference name/identity', 'Actual coloured face/depth and dry weight',
            'Binder, metal/finish process, backing, reinforcement, sealing and care', 'Rear hardware/attachment/load',
            'Owner individual price and production/stock/lead time', 'Exact coloured platform offer/sharedSKU',
            'Blue-versus-dark reference relationship, exact physical cast/mould equivalence and installation provenance', 'Coloured series photograph'],
        'identity_confirmed': False, 'specifications_approved': False, 'physical_specs_verified': False,
        'next_review_after_keep': comparison, 'next_global_component_id': 'BC-FOUNTAIN-MED',
        'remote_files_changed': False, 'live_platform_records_changed': False}
    evidence = [model_path, white_card_path, white_keep_path] + [Path(x['local_path']) for x in originals] + [Path(x['preview_path']) for x in thumbnails]
    evidence += [p for p in HERE.iterdir() if p.is_file()]
    write(HERE / 'source-audit.json', {'status': 'PASS', 'checked_utc': now, 'current_files_reviewed': 83,
        'fresh_originals_hash_verified_and_viewed': 5, 'source_colour_cast_specifications_established': False,
        'darker_reference_relationship_unresolved': True, 'evidence_sha256': {str(p): sha(p) for p in sorted(set(evidence))}})
    write(card_path, card)
    protected = {str(p): sha(p) for p in [model_path, ROOT / cp['register_workbook'], REVIEWS / 'user_classifications.json',
        white_card_path, white_keep_path, card_path]}
    write(HERE / 'before-stage-review.json', {'recorded_utc': now, 'files': {rel(paths[k]): v for k, v in before.items()}, 'protected_sha256': protected})
    parent = progress['reviews']['BC-FOUNTAIN-EG']
    assert parent['identity_confirmed'] and parent['canonical_name'] == 'Fountain Palm Egyptian — White'
    assert 'FOUNTAIN-EG-BRONZE-VERDIGRIS' not in parent.get('size_finish_variants', {})
    parent.setdefault('size_finish_variants', {})['FOUNTAIN-EG-BRONZE-VERDIGRIS'] = {
        'reviewed_utc': now, 'proposed_name': card['proposed_name'], 'identity_confirmed': False,
        'specifications_approved': False, 'physical_specs_verified': False, 'specification_proposals': copy.deepcopy(items),
        'primary_image_id': primary['id'], 'primary_folder_id': folder['id'], 'review_record': rel(card_path),
        'platform_mapping': mapping, 'photo_coverage': coverage, 'gaps': card['open_gaps'],
        'unresolved_reference_relationship': comparison, 'appearance_reference_groups': card['appearance_reference_groups']}
    parent['pending_size_finish_variants'][0].update({'review_record': rel(card_path), 'review_status': 'AWAITING OWNER SELECTED-REFERENCE NAME; SIX GUESSES PENDING'})
    progress['family_review_progress']['Fountain Palm'].update({'review_reference_total': 4,
        'reference_total_is_sculpture_count': False, 'additional_relationship_question': comparison})
    progress['updated_utc'] = now
    state = 'Awaiting Fountain Palm Egyptian Bronze and Verdigris selected blue-reference name; six guesses pending'
    cp.update({'current_size_finish_variant_id': card['size_finish_variant_id'], 'proposed_name': card['proposed_name'],
        'state': state, 'current_review_record': rel(card_path), 'current_family_review_number': 2, 'current_family_review_total': 4,
        'family_review_order': family_order, 'family_first_pass_complete': False, 'current_answer_recorded': False,
        'current_specification_answer_recorded': False, 'current_dimension_answer_recorded': False, 'working_version_user_approved': False,
        'review_decision_mode': card['review_decision_mode'], 'question_scope': card['scope'],
        'answer_state': 'No coloured name or specification approval yet. Darker reference relationship remains separate.',
        'primary_image': {'file_id': primary['id'], 'name': primary['name'], 'path_display': primary['path_display'],
            'copy_link_url': card['primary_image_link'], 'open_in_dropbox_url': links[primary['id']]['open_in_dropbox_url']},
        'containing_folder': {'folder_id': folder['id'], 'name': folder['name'], 'path_display': folder['path_display'],
            'copy_link_url': card['primary_folder_link'], 'open_in_dropbox_url': links[folder['id']]['open_in_dropbox_url']},
        'family_review_evidence': card['reference_refresh'], 'metadata_checked_utc': meta['selected_metadata_checked_utc'],
        'next_review_after_keep': comparison, 'displayed_identity_evidence_file_ids': [primary['id']],
        'displayed_identity_evidence_folder_ids': [folder['id']], 'current_component_source_notes': [x['display'] for x in items], 'updated_utc': now})
    component['interactive_review_state'].update({'current_size_finish_variant_id': card['size_finish_variant_id'],
        'current_name': card['proposed_name'], 'state': state, 'family_review_number': 2, 'family_review_total': 4,
        'specification_proposals_approved': False, 'working_version_user_approved': False, 'review_decision_mode': card['review_decision_mode']})
    component['current_component_review_record'] = rel(card_path)
    component['last_family_media_review'] = {'family': 'Fountain Palm', 'finish': 'Bronze and Verdigris selected blue reference and darker comparison',
        'observed_utc': meta['selected_metadata_checked_utc'], 'files': 83, 'folders': 1, 'scope': coverage['scope'],
        'evidence': card['reference_refresh'], 'workbook_contains_this_live_media_audit': False}
    component['updated_utc'] = now
    docs['root']['current_component_review'] = copy.deepcopy(component)
    docs['root']['updated_utc'] = now
    old_parent = before['progress']['reviews']['BC-FOUNTAIN-EG']
    assert all(parent[k] == v for k, v in old_parent.items() if k not in ['pending_size_finish_variants', 'size_finish_variants'])
    assert all(progress['reviews'][k] == v for k, v in before['progress']['reviews'].items() if k != 'BC-FOUNTAIN-EG')
    assert cp['parallel_import_queue'] == before['walkthrough']['parallel_import_queue']
    assert cp['parallel_owner_reviews'] == before['walkthrough']['parallel_owner_reviews']
    assert all(sha(path) == hashes[k] for k, path in paths.items()), 'Shared writer collision'
    assert all(sha(Path(path)) == digest for path, digest in protected.items())
    for key, path in paths.items():
        write(path, docs[key])
        assert read(path) == docs[key]
    assert read(paths['root'])['current_component_review'] == read(paths['component'])
    result = {'status': 'PASS', 'current_variant': card['size_finish_variant_id'], 'six_unapproved_guesses': 6,
        'current_files_audited': 83, 'fresh_originals_verified_and_viewed': 5, 'white_name_and_source_fields_preserved': True,
        'darker_reference_not_counted_as_new_sculpture_or_finish': True, 'white_platform_offer_not_transferred': True,
        'ledger_model_workbook_prior_reviews_unchanged': True, 'checkpoint_copies_match': True}
    write(HERE / 'review-validation.json', result)
    print(json.dumps(result))
    print(json.dumps({'image': card['primary_image_link'], 'folder': card['primary_folder_link'], 'outdoor': card['outdoor_display_image_link'], 'darker': card['darker_indoor_reference_link']}))


if __name__ == '__main__':
    main()
