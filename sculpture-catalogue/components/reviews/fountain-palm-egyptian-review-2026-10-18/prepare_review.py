"""Stage the individual white Egyptian Fountain Palm and retain all source scopes."""
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
    assert cp['current_component_id'] == 'BC-FACET-MOUND' and cp['current_answer_recorded']
    assert cp['next_review_after_keep']['component_id'] == 'BC-FOUNTAIN-EG' and not cp['next_review_after_keep']['requires_pending_parallel_import']
    assert cp['next_serialized_parallel_import']['status'] == 'APPLIED_AND_VERIFIED'
    assert read(ROOT / cp['last_parallel_import']['receipt'])['source_owner_receipts'] == 8
    assert read(ROOT / 'components/reviews/parallel-import-2026-10-18-batch5/independent-readback.json')['status'] == 'PASS'
    assert docs['root']['current_component_review'] == component
    prior_keep = ROOT / cp['last_identity_approval']
    assert read(prior_keep)['user_statement'] == 'Keep “Faceted Mound — Gold Leaf”'
    model_path = ROOT / 'components/evidence/component_register.json'
    model = read(model_path)
    source_component = next(x for x in model['components'] if x['component_id'] == 'BC-FOUNTAIN-EG')
    offer = next(x for x in model['platform_records'] if x['offer_ref'] == 'O014')
    assert offer['sku'] == 'DF-1-100.50' and offer['sh_handle'] == 'copy-of-concave-moon'
    assert offer['sq_id'] == '6a5559cf7b54f252fef70728' and offer['native_parts'] == 1
    claims = [x for x in model['claims'] if x.get('component_id') == 'BC-FOUNTAIN-EG']
    packet_path = ROOT / 'components/parallel-preparation/20261017T164751Z/worker-01/packets.json'
    packet = next(x for x in read(packet_path)['entries'] if x['component_id'] == 'BC-FOUNTAIN-EG')
    write(HERE / 'advisory-packet-used.json', {'source': rel(packet_path), 'source_sha256': sha(packet_path), 'packet': packet})
    meta = read(HERE / 'metadata-links.json')
    listings = {x['key']: x for x in meta['listings']}
    assert {key: len(x['entries']) for key, x in listings.items()} == {'family': 5, 'white': 127, 'moulding': 68, 'pair': 2}
    assert all(not x['has_more'] and not x['cursor'] for x in listings.values())
    refs = {x['request_id']: x for x in meta['metadata']}
    primary = refs['id:cnqzTNngPVsAAAAAAAylDQ']['file']
    folder = refs['id:cnqzTNngPVsAAAAAAAyieg']['folder']
    assert primary['path_display'].rsplit('/', 1)[0] == folder['path_display']
    links = {x['file_name']: x for x in meta['previews']}
    thumbs = read(HERE / 'image-review-index.json')['cached_previews']
    originals = read(HERE / 'download-receipts.json')
    assert len(thumbs) == 197 and len(originals) == 6
    for receipt in originals:
        path = Path(receipt['local_path'])
        assert path.stat().st_size == receipt['size'] and sha(path) == receipt['sha256']
        b = path.read_bytes()
        assert hashlib.sha256(b''.join(hashlib.sha256(b[i:i+4194304]).digest() for i in range(0, len(b), 4194304))).hexdigest() == receipt['content_hash']
    public = read(HERE / 'public-source-check.json')
    assert public['http_status'] == 200 and sha(HERE / 'public-page.html') == public['sha256']
    product = next(x for x in read(HERE / 'public-jsonld.json') if isinstance(x, dict) and x.get('@type') == 'Product')
    assert product['offers']['sku'] == offer['sku'] and product['offers']['price'] == 900 and product['offers']['priceCurrency'] == 'GBP'
    public_image = read(HERE / 'public-image-receipt.json')
    assert sha(HERE / 'public-primary-image.jpg') == public_image['sha256']
    trade = read(HERE / 'trade-source-receipt.json')
    assert sha(Path(trade['source_path'])) == trade['source_sha256'] and sha(Path(trade['render_path'])) == trade['render_sha256']
    assert trade['draft_estimated_kg_each'] == 16 and trade['draft_individual_trade_gbp'] == 625
    process = next(x for x in originals if x['name'].endswith('moulding-process__025.jpg'))
    flat_process = next(x for x in originals if x['name'].endswith('moulding-process__066.jpg'))
    public_comparison = {'status': 'VISUALLY CONFIRMED SAME DEPICTED DESIGN / PHOTOGRAPHIC REFERENCE',
        'public_image': rel(HERE / 'public-primary-image.jpg'), 'dropbox_native_source_image_id': 'id:cnqzTNngPVsAAAAAAAucQA',
        'dropbox_clean_primary_id': primary['id'], 'observed_basis': 'Same dense fan of carved rising plumes and stems, same outline. Public brick-wall photo corresponds to the Dropbox118source-photo reference; clean001depicts that same design.',
        'same_physical_cast_independently_verified': False, 'specification_applicability_to_every_cast_verified': False}
    write(HERE / 'listing-image-comparison.json', public_comparison)
    process_scope = {'scope': 'Moulding folder is process evidence and includes differing channel studies; no whole-folder finished-product, material or mould allocation.',
        'AC730_label_observation': {'file_id': process['id'], 'folder_id': 'id:cnqzTNngPVsAAAAAAAyiiw',
            'observation': 'A workshop bucket labelledAC730is visible beside the rough carved/plume-pattern process piece. This supports a material candidate, not proof that this bucket was used in the photographed finished panel.',
            'actual_finished_cast_binder_confirmed': False},
        'flat_stage_is_not_finished_rear_evidence': {'file_id': flat_process['id'], 'reason': 'White sheet/stage on a clay support in a casting frame; no installed finished-panel fixing hardware visible.'},
        'white101_is_process_reference': next(x['file_id'] for x in listings['white']['entries'] if x['name'].endswith('__101.jpg')),
        'moulding_component_allocation_pending': True, 'material_recipe_reinforcement_sealing_unconfirmed': True}
    write(HERE / 'process-image-scope.json', process_scope)
    now = datetime.now(timezone.utc).isoformat()
    items = []

    def item(suffix, field, display, value, status, basis, source_refs):
        items.append({'proposal_id': 'FOUNTAIN-EG-WHITE-' + suffix, 'field': field, 'display': display, 'value': value,
            'status': status, 'basis': basis, 'source_refs': source_refs, 'owner_approved': False, 'physical_specs_verified': False})

    item('DIMENSIONS', 'Individual dimensions and depth', '100 H ×50 W ×6 D cm — current listing claim; selected cast unmeasured',
        {'listing_dimensions_cm': [100, 50, 6], 'draft_face_cm': [100, 50], 'actual_measured_cm': None},
        'SINGLE-PANEL SOURCE DIMENSIONS; CAST APPLICABILITY PENDING',
        'Fresh public page states one carved/cast wall sculpture100×50×6cm. Draft Reed Fountain photograph/row gives100×50each. These are source claims, not owner-confirmed physical measurements or dimensions divided from a set.',
        [offer['source_url'], 'O014', rel(HERE / 'trade-source-receipt.json')])
    item('WEIGHT', 'Individual dry weight', '15kg in Shopify export;16kg in dated draft estimate — unresolved; actual panel unweighed',
        {'shopify_export_kg': 15, 'draft_estimated_kg': 16, 'actual_weighed_kg': None},
        'TWO DISTINCT SOURCE VALUES; NO ACTUAL WEIGHING',
        'Shopify row9records15000grams. Visually matching Reed Fountain draft row estimates16kg per single panel. Retain both; neither is a measured mass for this pictured cast, and no set mass is divided.',
        ['SH Wall Products!row9/Variant Grams', rel(HERE / 'trade-source-receipt.json')])
    item('MATERIAL', 'Material and finish', 'White marble stone finish — listing; Jesmonite AC730 is a supported working hypothesis, exact cast composition unknown',
        {'listing_finish': 'White marble stone finish', 'proposed_binder': 'Jesmonite AC730', 'actual_binder': None,
            'reinforcement': None, 'sealer': None, 'process_container_id': process['id']},
        'LISTING FINISH CLAIM + IMAGE-SUPPORTED BINDER HYPOTHESIS',
        'Public copy establishes the stated finish. AC730label in process025supports an AC730candidate only; nearby workshop materials do not certify the finished panel recipe, reinforcement, sealer, care, weather suitability or water-feature performance.',
        [offer['source_url'], rel(HERE / 'process-image-scope.json'), process['id']])
    item('FIXING', 'Fixing', 'Concealed rear fixing(s) — proposal; actual type, number, attachment and rated load unknown',
        {'proposed_scheme': 'Concealed rear fixing(s)', 'hardware_type': None, 'count': None, 'rated_load': None},
        'UNAPPROVED FIXING PROPOSAL; NO FINISHED REAR FOUND',
        'No finished-panel rear/installed-hardware image established across127white,68process and2pair views. Flat process066is a mould/casting stage, not certified rear hardware. No keyhole detail transferred from Gleneagles or another design.',
        [rel(HERE / 'metadata-links.json'), rel(HERE / 'process-image-scope.json')])
    item('PRICE', 'Individual retail price', '£900 per panel — current public listing; separate dated trade candidate£625; intended owner price unapproved',
        {'current_source_retail_gbp': 900, 'dated_candidate_trade_gbp': 625, 'sale_unit': 'One panel', 'owner_price_approved': False},
        'FRESH SINGLE-PANEL PUBLIC RETAIL SOURCE; DATED TRADE CLASS SEPARATE',
        'One ordinary public GET200and JSON-LD confirm900GBP andDF-1-100.50. Draft Reed Fountain625GBP is a dated trade reference for the matching design candidate, not a competing current retail price. No pumping/plumbing equipment is included by name alone.',
        [offer['source_url'], rel(HERE / 'public-source-check.json'), rel(HERE / 'trade-source-receipt.json')])
    item('AVAILABILITY', 'Availability', 'Made to order / enquire — proposal; actual stock, reproduction capacity and lead time unknown',
        {'proposed_policy': 'Made to order / enquire subject to production confirmation', 'physical_stock': None,
            'reproducibility': None, 'lead_time': None, 'public_platform_flag': product['offers']['availability']},
        'UNAPPROVED SALE POLICY; PHYSICAL INVENTORY UNVERIFIED',
        'PublicInStock and historicalUnlimited/activeflags are platform records. Photographs of past carving/casting do not establish current stock, usable mould inventory, production capacity or delivery dates.',
        [offer['source_url'], 'O014', rel(HERE / 'process-image-scope.json')])
    mapping = {'status': 'EXPORTED SHARED-SKU PAIR CONFIRMED; CURRENT SQUARESPACE SKU/PHOTO VERIFIED',
        'offer_ref': 'O014', 'squarespace_id': offer['sq_id'], 'shopify_handle': offer['sh_handle'], 'shared_sku': offer['sku'],
        'squarespace_source_row': 19, 'shopify_source_row': 9, 'sale_unit': 'One individual white panel',
        'public_source_url': offer['source_url'], 'current_squarespace_sku_verified': True,
        'current_squarespace_price_gbp': 900, 'public_http_check': rel(HERE / 'public-source-check.json'),
        'dropbox_listing_design_status': public_comparison['status'], 'listing_photo_file_id': 'id:cnqzTNngPVsAAAAAAAucQA',
        'primary_file_id': primary['id'], 'primary_folder_id': folder['id'], 'same_physical_cast_verified': False,
        'shopify_live_account_refreshed': False, 'component_specifications_owner_approved': False,
        'coloured_finish_inherits_white_offer': False, 'draft_Reed_Fountain_alias_owner_confirmed': False}
    coverage = {'complete_individual_front': True, 'detail_views_available': True, 'standalone_outdoor_wall_display': True,
        'workshop_context_available': True, 'paired_display_available': True, 'paired_display_contains_different_designs': True,
        'rear_of_finished_panel': False, 'indoor_room_setting_established': False, 'actual_client_installation_provenance_confirmed': False,
        'same_physical_cast_in_all_references_verified': False,
        'scope': 'Fresh complete197-file census:127white,68moulding/process,2paired display; all197cached previews viewed in7contact sheets. Six current Dropbox originals and one public listing original downloaded/hash-verified/viewed. Bronze83-file folder reserved for its own finish review; Mediterranean solo folder not audited here. Paired display shows dense Egyptian on wall and a different sparse-channel Mediterranean panel on grass, not two copies counted as separate Egyptian designs.'}
    next_review = {'component_id': 'BC-FOUNTAIN-EG', 'review_number': 53,
        'variant_id': 'FOUNTAIN-EG-BRONZE-VERDIGRIS', 'label': 'Fountain Palm Egyptian — Bronze and Verdigris', 'variant_only_review': True}
    family_order = [{'component_id': 'BC-FOUNTAIN-EG', 'review_number': 53, 'variant_id': 'FOUNTAIN-EG-WHITE', 'label': 'Fountain Palm Egyptian — White'},
        next_review, {'component_id': 'BC-FOUNTAIN-MED', 'review_number': 54, 'variant_id': 'FOUNTAIN-MED-WHITE', 'label': 'Fountain Palm Mediterranean — White'}]
    card = {'schema_version': 1, 'prepared_utc': now, 'component_id': 'BC-FOUNTAIN-EG', 'review_number': 53,
        'family': 'Fountain Palm', 'family_review_number': 1, 'family_review_total': 3,
        'size_finish_variant_id': 'FOUNTAIN-EG-WHITE', 'canonical_design_name': 'Fountain Palm Egyptian / Deco Fountain',
        'proposed_name': 'Fountain Palm Egyptian — White', 'display_name': 'Fountain Palm Egyptian — White',
        'review_decision_mode': 'COMPONENT_NAME_AND_SPECIFICATIONS',
        'scope': 'One depicted individual dense/plume-channel white wall relief. Name/identity approval does not approve source dimensions/weight/finish, current retail intention, stock or physical manufacture. Reed Fountain remains a draft-source naming candidate.',
        'primary_image_id': primary['id'], 'primary_folder_id': folder['id'],
        'primary_image_link': links[primary['id']]['copy_link_url'], 'primary_folder_link': links[folder['id']]['copy_link_url'],
        'native_listing_image_id': 'id:cnqzTNngPVsAAAAAAAucQA', 'native_listing_image_link': links['id:cnqzTNngPVsAAAAAAAucQA']['copy_link_url'],
        'series_image_id': 'id:cnqzTNngPVsAAAAAAAugew', 'series_folder_id': 'id:cnqzTNngPVsAAAAAAAyiiQ',
        'series_image_link': links['id:cnqzTNngPVsAAAAAAAugew']['copy_link_url'],
        'series_folder_link': links['id:cnqzTNngPVsAAAAAAAyiiQ']['copy_link_url'],
        'series_position': 'Dense-channel Egyptian mounted on brick wall; sparse-channel Mediterranean on grass remains separate component54',
        'metadata_checked_utc': meta['checked_utc'], 'reference_refresh': rel(HERE / 'metadata-links.json'),
        'specification_review_items': items, 'platform_mapping': mapping, 'photo_coverage': coverage,
        'source_claims': claims, 'source_component_snapshot': source_component, 'advisory_packet': rel(HERE / 'advisory-packet-used.json'),
        'source_conflicts': ['Native/Shopify15kg versus dated draft16kgestimate; actual cast unweighed.',
            'Deco Fountain exported/current listing and Egyptian Dropbox geometry match. Reed Fountain draft photograph supplies an alias candidate awaiting owner naming reconciliation.',
            '900GBPcurrent retail and625GBPdated trade are different price classes, not interchangeable.',
            'AC730label is nearby process evidence only; actual finished-cast binder remains unconfirmed.',
            'Moulding folder includes process stages and differing groove studies; no wholesale finished-cast or mould allocation.'],
        'open_gaps': ['Owner depicted name/identity', 'Actual height/width/maximum projection and weighed dry mass',
            'Binder, reinforcement, backing, sealant, care and exterior suitability', 'Finished-panel rear photograph and fixing details/load',
            'Owner individual price, physical stock, reproducibility and lead time', 'Draft Reed Fountain naming reconciliation',
            'Exact same-cast and actual installation provenance; indoor room image', 'Separate bronze/verdigris review; separate Mediterranean component review'],
        'identity_confirmed': False, 'specifications_approved': False, 'physical_specs_verified': False,
        'next_review_after_keep': next_review, 'next_global_component_id': 'BC-FOUNTAIN-MED',
        'remote_files_changed': False, 'live_platform_records_changed': False}
    evidence = [model_path, packet_path, prior_keep, Path(trade['source_path'])]
    evidence += [Path(x['local_path']) for x in originals] + [Path(x['preview_path']) for x in thumbs]
    evidence += [p for p in HERE.iterdir() if p.is_file()]
    write(HERE / 'source-audit.json', {'status': 'PASS', 'checked_utc': now, 'current_file_references_reviewed': 197,
        'fresh_Dropbox_originals_hash_verified_and_viewed': 6, 'public_image_viewed': True,
        'public_page_GET200_sku_price_verified': True, 'draft_page11_rendered_and_viewed': True,
        'evidence_sha256': {str(p): sha(p) for p in sorted(set(evidence))}})
    write(card_path, card)
    protected = {str(p): sha(p) for p in [model_path, ROOT / cp['register_workbook'], REVIEWS / 'user_classifications.json',
        ROOT / cp['current_review_record'], prior_keep, card_path]}
    write(HERE / 'before-stage-review.json', {'recorded_utc': now, 'files': {rel(paths[k]): v for k, v in before.items()}, 'protected_sha256': protected})
    assert 'BC-FOUNTAIN-EG' not in progress['reviews']
    progress['reviews']['BC-FOUNTAIN-EG'] = {'reviewed_utc': now, 'review_number': 53, 'proposed_name': card['proposed_name'],
        'size_finish_variant_id': card['size_finish_variant_id'], 'identity_confirmed': False, 'specifications_approved': False,
        'physical_specs_verified': False, 'source_specifications_recorded': True, 'specification_proposals': copy.deepcopy(items),
        'primary_image_id': primary['id'], 'primary_folder_id': folder['id'], 'review_record': rel(card_path),
        'platform_mapping': mapping, 'photo_coverage': coverage, 'gaps': card['open_gaps'],
        'pending_size_finish_variants': [next_review]}
    progress['updated_utc'] = now
    state = 'Awaiting Fountain Palm Egyptian White name/identity; six source/proposal groups unapproved'
    cp.update({'current_component_id': 'BC-FOUNTAIN-EG', 'current_review_number': 53,
        'current_size_finish_variant_id': card['size_finish_variant_id'], 'proposed_name': card['proposed_name'],
        'state': state, 'current_review_record': rel(card_path), 'active_family': 'Fountain Palm',
        'current_family_review_number': 1, 'current_family_review_total': 3, 'family_review_order': family_order,
        'family_first_pass_complete': False, 'current_answer_recorded': False, 'current_specification_answer_recorded': False,
        'current_dimension_answer_recorded': False, 'current_dimension_approval': None, 'current_owner_face_dimensions_cm': None,
        'current_partial_specification_answer_recorded': False, 'current_identity_relationship_answer_recorded': False,
        'current_identity_relationship_approval': None, 'canonical_depicted_name': None, 'working_version_user_approved': False,
        'review_decision_mode': card['review_decision_mode'], 'question_scope': card['scope'],
        'answer_state': 'No answer yet; source claims/guesses remain distinct and owner-unapproved.',
        'primary_image': {'file_id': primary['id'], 'name': primary['name'], 'path_display': primary['path_display'],
            'copy_link_url': card['primary_image_link'], 'open_in_dropbox_url': links[primary['id']]['open_in_dropbox_url']},
        'containing_folder': {'folder_id': folder['id'], 'name': folder['name'], 'path_display': folder['path_display'],
            'copy_link_url': card['primary_folder_link'], 'open_in_dropbox_url': links[folder['id']]['open_in_dropbox_url']},
        'family_review_evidence': card['reference_refresh'], 'metadata_checked_utc': meta['checked_utc'],
        'next_review_after_keep': next_review, 'after_main_family_next_unclaimed': {'component_id': cp['review_order'][65], 'review_number': 66},
        'displayed_identity_evidence_file_ids': [primary['id']], 'displayed_identity_evidence_folder_ids': [folder['id']],
        'current_component_source_notes': [x['display'] for x in items], 'updated_utc': now})
    component['interactive_review_state'].update({'current_component_id': card['component_id'], 'review_number': 53,
        'current_size_finish_variant_id': card['size_finish_variant_id'], 'current_name': card['proposed_name'], 'state': state,
        'family_review_number': 1, 'family_review_total': 3, 'specification_proposals_approved': False,
        'working_version_user_approved': False, 'review_decision_mode': card['review_decision_mode'],
        'current_dimension_answer_recorded': False, 'current_owner_face_dimensions_cm': None})
    component['current_component_review_record'] = rel(card_path)
    component['last_family_media_review'] = {'family': 'Fountain Palm', 'observed_utc': meta['checked_utc'],
        'files': 197, 'folders': 3, 'scope': coverage['scope'], 'evidence': card['reference_refresh'], 'workbook_contains_this_live_media_audit': False}
    component['updated_utc'] = now
    docs['root']['current_component_review'] = copy.deepcopy(component)
    docs['root']['updated_utc'] = now
    assert all(progress['reviews'][k] == v for k, v in before['progress']['reviews'].items())
    assert cp['parallel_import_queue'] == before['walkthrough']['parallel_import_queue']
    assert cp['parallel_owner_reviews'] == before['walkthrough']['parallel_owner_reviews']
    assert cp.get('parallel_evidence_flags') == before['walkthrough'].get('parallel_evidence_flags')
    assert all(sha(path) == hashes[k] for k, path in paths.items()), 'Shared writer collision'
    assert all(sha(Path(path)) == digest for path, digest in protected.items())
    for key, path in paths.items():
        write(path, docs[key])
        assert read(path) == docs[key]
    assert read(paths['root'])['current_component_review'] == read(paths['component'])
    result = {'status': 'PASS', 'current_component': card['component_id'], 'review_number': 53,
        'current_finish': 'White', 'six_unapproved_groups': 6, 'current_files_audited': 197,
        'fresh_Dropbox_originals_hash_verified_and_viewed': 6, 'public_price_and_sku_GET200_verified': True,
        'listed_design_visually_matches_Dropbox': True, 'actual_binder_and_weight_unconfirmed': True,
        'prior_Faceted_name_and_bounded_import_preserved': True, 'model_ledger_workbook_unchanged': True,
        'pending_flags_and_reservations_preserved': True, 'checkpoint_copies_match': True}
    write(HERE / 'review-validation.json', result)
    print(json.dumps(result))
    print(json.dumps({'image': card['primary_image_link'], 'folder': card['primary_folder_link'], 'paired_display': card['series_image_link']}))


if __name__ == '__main__':
    main()
