"""Stage the separate Gold finish reference; preserve white position approvals and source scope."""
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


def dbx_hash(path):
    chunks = []
    with path.open('rb') as f:
        while block := f.read(4 * 1024 * 1024):
            chunks.append(hashlib.sha256(block).digest())
    return hashlib.sha256(b''.join(chunks)).hexdigest()


def main():
    output = HERE / 'gold/component-review.json'
    assert not output.exists(), 'Gold reference already staged'
    paths = {'progress': REVIEWS / 'specification_review_progress.json',
        'walkthrough': REVIEWS / 'walkthrough_checkpoint.json',
        'component': ROOT / 'components/checkpoint.json', 'root': ROOT / 'checkpoint.json'}
    docs = {key: read(path) for key, path in paths.items()}
    before = copy.deepcopy(docs)
    hashes = {key: sha(path) for key, path in paths.items()}
    p, cp, c = (docs[key] for key in ['progress', 'walkthrough', 'component'])
    assert cp['current_component_layout_id'] == 'LEAF-FORM-LF2-WHITE' and cp['current_answer_recorded']
    assert cp['next_review_after_keep']['variant_id'] == 'LEAF-FORM-GOLD'
    assert docs['root']['current_component_review'] == c
    keep_path = ROOT / cp['last_identity_approval']
    keep = read(keep_path)
    assert keep['user_statement'] == 'Keep “Leaf Form 2 — White (LF2)”' and not keep['specifications_approved']
    protected_paths = [REVIEWS / 'user_classifications.json', ROOT / 'components/evidence/component_register.json',
        ROOT / cp['register_workbook'], HERE / 'source-audit.json', HERE / 'maker-source-reference.json',
        HERE / 'lf1-white/identity-approval.json', HERE / 'lf1-white/component-review.json',
        keep_path, HERE / 'lf2-white/component-review.json', HERE / 'lf2-white/component-review.draft.json']
    protected = {str(path): sha(path) for path in protected_paths}
    now = datetime.now(timezone.utc).isoformat()
    refresh_path = HERE / 'gold/current-reference-refresh.json'
    refresh = read(refresh_path)
    metadata = {x['requested_id']: x['result'] for x in refresh['entries']}
    file_id, folder_id = 'id:cnqzTNngPVsAAAAAAAuROg', 'id:cnqzTNngPVsAAAAAAAyilg'
    file, folder = metadata[file_id]['file'], metadata[folder_id]['folder']
    assert file['id'] == file_id and folder['id'] == folder_id
    assert file['path_display'].rsplit('/', 1)[0] == folder['path_display']
    meta = read(HERE / 'metadata-links.json')
    prior_file = next(x['file'] for x in meta['metadata'] if x['request_id'] == file_id)
    assert all(file[key] == prior_file[key] for key in ['id', 'rev', 'size', 'path_display'])
    receipt = next(x for x in read(HERE / 'download-receipts.json') if x['id'] == file_id)
    local = Path(receipt['local_path'])
    assert local.stat().st_size == file['size'] == receipt['size']
    assert sha(local) == receipt['sha256'] and dbx_hash(local) == receipt['content_hash']
    census_path = HERE / 'gold/current-folder-census.json'
    census = read(census_path)
    assert not census['has_more'] and not census['cursor'] and len(census['entries']) == 7
    old_gold = next(x for x in read(HERE / 'media-census.json')['listings'] if 'Leaf Form Gold' in json.dumps(x))
    old_entries = old_gold.get('entries', old_gold.get('result', {}).get('entries', []))
    if not old_entries:
        old_entries = old_gold.get('listing', {}).get('entries', [])
    assert old_entries, 'Gold previous listing structure requires inspection'
    old = {x['file_id']: x for x in old_entries}
    assert set(old) == {x['file_id'] for x in census['entries']}
    index = read(HERE / 'image-review-index.json')
    for entry in census['entries']:
        assert entry['object_type'] == 'file'
        previous = old[entry['file_id']]
        assert all(entry[key] == previous[key] for key in ['name', 'modified_time', 'file', 'path'])
        preview = next(x for x in index['cached_previews'] if x['file_id'] == entry['file_id'])
        assert sha(Path(preview['preview_path'])) == preview['sha256']
    links = {x['file_name']: x for x in meta['previews']}
    maker = rel(HERE / 'maker-source-reference.json')
    white_public = rel(HERE / 'gold/related-white-public-source.json')
    photo_audit_path = HERE / 'gold/photo-and-identity-evidence.json'
    write(photo_audit_path, {'recorded_utc': now, 'complete_Gold_folder_files': 7,
        'folder_census': rel(census_path), 'all_seven_cached_previews_rechecked': True,
        'viewed_surfaces': [rel(HERE / 'file-review-1.jpg'), rel(local), rel(HERE / 'leaf-form__leaf-form-white__001.png')],
        'observation': 'All seven Gold references depict a single square gold-coloured leaf panel in room settings, at varying presentation scales. The leaf convergence toward the bottom and broad leaf at the right visually correspond to LF2/Position B.',
        'proposed_name': 'Leaf Form 2 — Gold (LF2)', 'position_relationship_status': 'VISUAL PROPOSAL AWAITING OWNER',
        'room_images_appear_to_be_mockups': True, 'scene_provenance_confirmed': False,
        'same_physical_cast_or_mould_confirmed': False, 'actual_gold_leaf_confirmed': False,
        'primary_file_id': file_id, 'primary_folder_id': folder_id, 'primary_rev': file['rev'],
        'primary_sha256': receipt['sha256'], 'primary_dropbox_content_hash': receipt['content_hash'],
        'photo_gaps': ['Verified physical Gold sculpture photograph or authenticated installation',
            'Gold series/paired arrangement reference', 'Finished rear and fixing detail'],
        'counting_scope': 'Seven images are seven media records; no physical sculpture or mould count inferred.'})
    def item(suffix, field, display, value, basis, sources):
        return {'proposal_id': 'LEAF-FORM-GOLD-' + suffix, 'field': field, 'display': display,
            'value': value, 'status': 'UNAPPROVED CONDITIONAL GOLD PROPOSAL', 'basis': basis,
            'source_refs': sources, 'owner_approved': False, 'physical_specs_verified': False}
    items = [
        item('DIMENSIONS', 'Individual dimensions and depth', 'Approximately35×35×6cm — proposal from related White standard; Gold reference has no measured scale',
            {'proposed_cm': [35, 35, 6], 'related_white_maker_side_depth_cm': [5, 7], 'actual_measured_cm': None},
            'Square format is visible. Proposed size uses the related LF2White historical35×35cm standard and pair-listing6cm depth only; room furnishings and rendered artwork scale do not measure Gold. The related LF1single40×20cm conflict remains separate.',
            [maker, rel(HERE / 'public-reader-source.json'), rel(photo_audit_path)]),
        item('WEIGHT', 'Individual dry weight', '6–8kg per panel — conditional estimate only if Gold uses the proposed White-standard size and construction',
            {'conditional_estimate_kg': [6, 8], 'actual_weighed_kg': None,
             'assumptions': ['Approximately35×35cm cast', 'Construction and backing comparable to historical LF2White standard']},
            'Historical LF2White maker estimate is6–8kg each. This is a conditional Gold working estimate, not a measured Gold mass; different binder, thickness or backing changes it. No pair weight is divided.',
            [maker, rel(HERE / 'gold/local-price-source-check.json')]),
        item('MATERIAL', 'Material and finish', 'Cast mineral composite with a gold-coloured surface — proposal; binder and actual gold-leaf content unknown',
            {'proposed_base': 'Cast mineral composite', 'visible_appearance': 'Gold-coloured metallic surface',
             'actual_binder': None, 'actual_gold_leaf': None, 'metal_content': None, 'reinforcement': None, 'sealer': None,
             'related_white_standard_only': 'Jesmonite AC730 / White Marble Stone Finish'},
            'Relief and metallic-looking appearance are visible. A cast mineral base is a family-based proposal. AC730 is documented for historical White only; photos do not identify Gold binder, actual leaf, alloy, coating, backing, sealing or weather suitability.',
            [maker, rel(photo_audit_path)]),
        item('FIXING', 'Fixing', 'One concealed stainless-steel rear fixing centred in upper third — proposal from White instruction; Gold hardware unverified',
            {'proposed_count': 1, 'proposed_type': 'Small stainless-steel rear fixing',
             'proposed_position': 'Centre back in upper third', 'actual_hardware': None, 'rated_load': None},
            'Use historical White instruction as a discussion proposal only. Gold has no verified finished rear image, so count/type/attachment, wall anchorage and rated load remain unconfirmed.',
            [maker, rel(photo_audit_path)]),
        item('PRICE', 'Individual retail price', '£400 per panel — working proposal; no exact Gold offer or quote established',
            {'proposed_price_gbp': 400, 'related_white_offer_price_gbp': 350,
             'uncosted_provisional_finish_allowance_gbp': 50, 'actual_gold_offer_price_gbp': None,
             'owner_individual_price_approved': False},
            'Proposal uses350GBP related White single-offer reference plus an arbitrary50GBP finish allowance for owner discussion; it is not a sourced Gold price, production costing, margin calculation or quote. White size conflict persists;600GBPpair price is not allocated.',
            [white_public]),
        item('AVAILABILITY', 'Availability', 'Made to order / enquire — proposal subject to reproduction confirmation; stock and lead time unknown',
            {'proposed_policy': 'Made to order / enquire subject to production confirmation',
             'physical_stock': None, 'reproducibility': None, 'lead_time': None},
            'Room references and historical White sources do not prove a finished Gold cast, usable current mould, production capability, stock or delivery date. No live listing or stock setting is changed.',
            [rel(photo_audit_path), maker])]
    card = {'schema_version': 1, 'prepared_utc': now, 'component_id': 'BC-LEAF-FORM', 'review_number': 67,
        'family': 'Leaf Form', 'family_review_number': 3, 'family_review_total': 3,
        'family_total_scope': 'LF1White position, LF2White position, and Gold finish reference; review cards are not physical sculpture counts.',
        'size_finish_variant_id': 'LEAF-FORM-GOLD', 'variant_only_review': True,
        'proposed_name': 'Leaf Form 2 — Gold (LF2)', 'display_name': 'Leaf Form 2 — Gold (LF2)',
        'review_decision_mode': 'SIZE_FINISH_VARIANT_NAME_AND_SPECIFICATIONS',
        'identity_decision_destination': 'size_finish_variant_decisions',
        'scope': 'One depicted Gold-finish Leaf Form component reference, visually proposed as LF2/Position B. White identities, specifications, physical casts, moulds and offers remain separate. No Gold manufacture or usable mould is established.',
        'primary_image_id': file_id, 'primary_folder_id': folder_id,
        'primary_image_link': links[file_id]['copy_link_url'], 'primary_folder_link': links[folder_id]['copy_link_url'],
        'metadata_checked_utc': refresh['checked_utc'], 'reference_refresh': rel(refresh_path),
        'identity_evidence': rel(photo_audit_path), 'specification_review_items': items,
        'identity_confirmed': False, 'specifications_approved': False, 'physical_specs_verified': False,
        'platform_mapping': {'single_offer': {'squarespace_id': None, 'shopify_handle': None, 'sku': None,
            'status': 'EXACT GOLD STANDALONE OFFER UNCONFIRMED IN REVIEWED EVIDENCE'},
            'related_white_offers': {'single_offer_ref': 'O058', 'pair_offer_ref': 'O028',
                'scope': 'White source references only; no Gold price, SKU, stock or specification transfer confirmed'},
            'individual_component_level': {'depicted_position_candidate': 'LF2/Position B',
                'candidate_comparison_reference_id': 'id:cnqzTNngPVsAAAAAAAylMg',
                'owner_position_relationship_confirmed': False, 'same_physical_cast_or_mould_confirmed': False},
            'live_Shopify_account_refreshed': False, 'current_native_public_SKUs_reparsed': False},
        'photo_coverage': {'room_setting_reference_images': 7, 'complete_depicted_front_in_room_reference': True,
            'isolated_native_front_of_physical_Gold_cast_confirmed': False,
            'Gold_series_arrangement_reference': False, 'verified_physical_installation': False,
            'finished_rear': False, 'rear_fixing_detail': False,
            'scope': 'Seven room references appear to reuse the same Gold artwork; their provenance is unverified. White pair/garden photographs remain White evidence.'},
        'individual_sale_unit': {'quantity': 1, 'description': 'One Gold-finish Leaf Form panel, visually proposed as LF2',
            'live_listing_prepared_or_published': False},
        'open_gaps': ['Owner Gold name and depicted LF2position identity', 'Measured face/depth and weighed Gold mass',
            'Actual binder, leaf/metal/paint composition, backing, sealer and care',
            'Rear hardware, attachment and rated load', 'Individual Gold price, stock, reproducibility and lead time',
            'Exact standalone Gold Squarespace/Shopify counterpart/shared SKU',
            'Verified physical Gold front/installation, Gold arrangement and finished-rear photographs', 'Physical cast and current mould inventory'],
        'next_review_after_keep': {'component_id': 'BC-LEAF-GROWTH', 'review_number': 68},
        'remote_files_changed': False, 'live_platform_records_changed': False}
    write(HERE / 'gold/before-stage-review.json', {'recorded_utc': now,
        'files': {rel(paths[key]): value for key, value in before.items()}, 'protected_sha256': protected})
    write(output, card)
    parent = p['reviews']['BC-LEAF-FORM']
    assert all(parent['component_layouts'][x]['identity_confirmed'] for x in ['LEAF-FORM-LF1-WHITE', 'LEAF-FORM-LF2-WHITE'])
    assert 'LEAF-FORM-GOLD' not in parent.get('size_finish_variants', {})
    parent.setdefault('size_finish_variants', {})['LEAF-FORM-GOLD'] = {
        'reviewed_utc': now, 'review_number': 67, 'proposed_name': card['proposed_name'],
        'size_finish_variant_id': 'LEAF-FORM-GOLD', 'identity_confirmed': False,
        'specifications_approved': False, 'physical_specs_verified': False,
        'specification_proposals': copy.deepcopy(items), 'review_record': rel(output),
        'primary_image_id': file_id, 'primary_folder_id': folder_id, 'platform_mapping': card['platform_mapping'],
        'photo_coverage': card['photo_coverage'], 'individual_sale_unit': card['individual_sale_unit'], 'gaps': card['open_gaps']}
    assert len(parent['pending_size_finish_variants']) == 1
    assert parent['pending_size_finish_variants'][0]['variant_id'] == 'LEAF-FORM-GOLD'
    parent['pending_size_finish_variants'] = []
    assert p['family_review_progress']['Leaf Form']['review_reference_cards_answered'] == 2
    state = 'Awaiting Leaf Form2Gold depicted finish/name; all six conditional proposals pending'
    cp.update({'current_component_layout_id': None, 'current_size_finish_variant_id': 'LEAF-FORM-GOLD',
        'proposed_name': card['proposed_name'], 'state': state, 'current_review_record': rel(output),
        'current_family_review_number': 3, 'current_family_review_total': 3, 'current_answer_recorded': False,
        'current_specification_answer_recorded': False, 'current_dimension_answer_recorded': False,
        'current_partial_specification_answer_recorded': False, 'current_dimension_approval': None,
        'current_owner_face_dimensions_cm': None, 'current_identity_relationship_answer_recorded': False,
        'current_identity_relationship_approval': None, 'canonical_depicted_name': None, 'current_separate_saleable_design': None,
        'working_version_user_approved': False, 'question_scope': card['scope'], 'review_decision_mode': card['review_decision_mode'],
        'answer_state': 'Both White position names kept; Gold name/position and all six groups unapproved.',
        'primary_image': {'file_id': file_id, 'name': file['name'], 'path_display': file['path_display'],
            'copy_link_url': card['primary_image_link'], 'open_in_dropbox_url': links[file_id]['open_in_dropbox_url']},
        'containing_folder': {'folder_id': folder_id, 'name': folder['name'], 'path_display': folder['path_display'],
            'copy_link_url': card['primary_folder_link'], 'open_in_dropbox_url': links[folder_id]['open_in_dropbox_url']},
        'family_review_evidence': rel(photo_audit_path), 'metadata_checked_utc': refresh['checked_utc'],
        'displayed_identity_evidence_file_ids': [file_id], 'displayed_identity_evidence_folder_ids': [folder_id],
        'current_component_source_notes': [x['display'] for x in items],
        'next_review_after_keep': card['next_review_after_keep'], 'updated_utc': now})
    cp['family_review_order'][2]['label'] = card['proposed_name']
    c['interactive_review_state'].update({'current_component_layout_id': None, 'current_size_finish_variant_id': 'LEAF-FORM-GOLD',
        'current_name': card['proposed_name'], 'state': state, 'family_review_number': 3,
        'specification_proposals_approved': False, 'working_version_user_approved': False,
        'review_decision_mode': card['review_decision_mode']})
    c['current_component_review_record'] = rel(output)
    c['updated_utc'] = p['updated_utc'] = now
    docs['root']['current_component_review'] = copy.deepcopy(c)
    docs['root']['updated_utc'] = now
    assert parent['component_layouts'] == before['progress']['reviews']['BC-LEAF-FORM']['component_layouts']
    assert not parent['identity_confirmed']
    for key in ['parallel_import_queue', 'parallel_owner_reviews', 'parallel_evidence_flags', 'pending_specification_reviews']:
        assert cp[key] == before['walkthrough'][key]
    assert all(p['reviews'][key] == value for key, value in before['progress']['reviews'].items() if key != 'BC-LEAF-FORM')
    assert len(items) == 6 and all(not x['owner_approved'] for x in items)
    assert all(sha(path) == hashes[key] for key, path in paths.items()), 'Shared writer collision'
    assert all(sha(Path(path)) == digest for path, digest in protected.items())
    for key, path in paths.items():
        write(path, docs[key])
        assert read(path) == docs[key]
    result = {'status': 'PASS', 'current_name': card['proposed_name'], 'Gold_files': 7,
        'all_six_groups_unapproved': True, 'both_White_position_approvals_preserved': True,
        'Gold_manufacture_cast_mould_leaf_composition_and_platform_offer_not_inferred': True,
        'price_is_uncosted_working_proposal': True, 'all_previous_approvals_reservations_imports_preserved': True,
        'model_workbook_source_cards_unchanged': True,
        'checkpoint_copies_match': read(paths['root'])['current_component_review'] == read(paths['component'])}
    write(HERE / 'gold/review-validation.json', result)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
