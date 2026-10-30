"""Prepare the single Bronze/Verdigris spiral reference with scoped guesses."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
VID = 'DR-SPIRAL-BRONZE-VERDIGRIS'
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
rel = lambda p: str(p.relative_to(ROOT))


def write(name, value):
    path = HERE / name
    assert not path.exists(), f'Frozen record exists: {path}'
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def main():
    now = datetime.now(timezone.utc).isoformat()
    meta = read(HERE / 'metadata-links.json')
    front, folder = meta['primary_metadata']['file'], meta['folder_metadata']['folder']
    assert front['id'] == 'id:cnqzTNngPVsAAAAAAAykwQ' and folder['id'] == 'id:cnqzTNngPVsAAAAAAAyevA'
    assert {k: len(v['entries']) for k, v in meta['listings'].items()} == {'solo': 39, 'context': 2}
    assert all(not v['has_more'] and not v['cursor'] for v in meta['listings'].values())
    cache = read(HERE / 'image-review-index.json')['cached_previews']
    assert len(cache) == len({x['id'] for x in cache}) == 41
    receipts = read(HERE / 'download-receipts.json')
    assert len(receipts) == 3 and {x['id'] for x in receipts} == {
        front['id'], 'id:cnqzTNngPVsAAAAAAAylGg', 'id:cnqzTNngPVsAAAAAAAylGQ'}
    for r in receipts:
        path = Path(r['local_path'])
        assert sha(path) == r['sha256'] and path.stat().st_size == r['size']
        chunks = []
        with path.open('rb') as stream:
            while block := stream.read(4194304):
                chunks.append(hashlib.sha256(block).digest())
        assert hashlib.sha256(b''.join(chunks)).hexdigest() == r['content_hash'] == r['dropbox_content_hash_verified']
    prior = HERE.parent / 'gold/identity-approval.json'
    approval = read(prior)
    assert approval['user_statement'] == 'Keep “Dune Ripple Spiral — Gold”'
    assert approval['identity_confirmed'] and not approval['specifications_approved']
    source = ROOT.parent / 'Boldstone_Wall_Sculptures_Matched_All_Fields_2026-10-15.xlsx'
    source_sha = sha(source)
    assert source_sha == '7e6911a88ea9c9fd3214bdf860e24d6ad72ee755302efd6a9acc4db85c52c5c9'
    model_path = ROOT / 'components/evidence/component_register.json'
    model = read(model_path)
    component = next(x for x in model['components'] if x['component_id'] == 'BC-DR-SPIRAL')
    candidates = [x for x in model['platform_records'] if x['offer_ref'] in component['offer_refs']]
    assert len(candidates) == 5
    assert not any(x.get('image_folder_id') == folder['id'] for x in model['platform_records'])
    write('platform-candidate-check.json', {'status': 'PASS', 'checked_utc': now,
        'source_workbook_sha256': source_sha, 'source_model_sha256': sha(model_path),
        'known_spiral_source_offers': [{k: x.get(k) for k in ['offer_ref', 'sq_id', 'sh_handle', 'sku', 'title', 'image_file_id', 'image_folder_id']} for x in candidates],
        'exact_selected_finish_offer_confirmed': False,
        'scope': 'Five known DR2 source offers and prior read-only source checks retained. '
            'No confirmed binding to the selected Bronze/Verdigris folder; exact match remains unresolved, '
            'not a claim that no platform listing exists. Current native admins/public pages not refreshed.'})
    white = rel(HERE.parent / 'component-review.json')
    copper = rel(HERE.parent / 'copper/component-review.json')
    pale = rel(HERE.parent / 'verdigris/component-review.json')
    cluster = rel(HERE.parent / 'verdigris/appearance-reference-clusters.json')
    image_ref = rel(HERE / 'download-receipts.json')
    items = []

    def item(suffix, field, value, display, basis, refs):
        items.append({'proposal_id': VID + '-' + suffix, 'field': field, 'value': value, 'display': display,
            'status': 'UNAPPROVED WORKING GUESS; EXACT CAST UNVERIFIED', 'basis': basis,
            'source_refs': refs, 'owner_approved': False})

    item('DIMENSIONS', 'Individual dimensions and depth',
        {'proposed_dimensions_cm': [35, 21, 6], 'actual_measured_dimensions_cm': None},
        'Approximately 35 H × 21 W × 6 D cm — guess; unmeasured',
        'Related coloured DR2 listings state 35 × 21 × 6 cm; white maker standard has a 35 × 20 cm face and 5–7 cm side depth. '
        'Use only as an analogy proposal. The photographed tin is not a calibrated ruler: can size and camera geometry are unverified.',
        [white, copper, pale, image_ref])
    item('WEIGHT', 'Individual dry weight',
        {'proposed_weight_kg': 4, 'working_estimate_range_kg': [3, 5], 'actual_weighed_kg': None},
        'Approximately 4 kg (working range 3–5 kg) — guess; not weighed',
        'Related white DR2 maker row55 calculates 3–5 kg. Binder, filling and thickness of this specimen are unknown. '
        'No other finish’s raw export mass is converted and no arrangement mass is divided. The Gold shared-offer5kg is not inherited.',
        [white, 'manufacture-stevensons:Sheet1!row55; analogy only'])
    item('MATERIAL', 'Material and finish',
        {'proposed_substrate': 'Cast mineral composite', 'visual_finish': 'Dark blue/green verdigris effect over bronze-coloured highlights',
         'actual_binder': None, 'actual_bronze_or_copper_content': None, 'reinforcement': None, 'sealing': None},
        'Cast mineral composite with bronze and verdigris effect — guess; metal content unknown',
        'Three current originals and dated detail references show a dark textured two-curl panel with blue/green and metallic-coloured highlights. '
        'Plaster/sand is one related-work possibility, not an exact material claim. Colour does not verify bronze alloy, copper, '
        'chemical patination, AC730, reinforcement, sealing, care or exterior suitability.', [image_ref, copper, cluster])
    item('FIXING', 'Fixing',
        {'proposed_hanging_points': 1, 'proposed_type': 'Recessed rear keyhole hanger', 'exact_rear_available': False,
         'actual_hardware': None, 'attachment': None, 'rated_load': None, 'alternate_orientation_verified': False},
        'One recessed rear keyhole fixing — guess; exact rear, hardware and load unconfirmed',
        'Related DR2 instructions and other scoped source photographs suggest one rear fixing. No rear was identified among these41files. '
        'Horizontal and vertical front views do not establish a reversible hanging system, fixing grade, location, attachment or rated load.',
        [white, copper, image_ref])
    item('PRICE', 'Individual retail price',
        {'proposed_amount': 200, 'currency': 'GBP', 'sale_unit': 'One selected Bronze/Verdigris spiral panel',
         'exact_existing_offer_confirmed': False, 'owner_price_approval': False, 'finish_costing_confirmed': False},
        '£200 per individual panel — working price guess; no exact offer or quote confirmed',
        'Discussion proposal based on the dated white DR2 £175 draft plus an uncosted £25 finish allowance. '
        'This is neither production costing nor a matched current listing price. Other finish prices are not transferred.', [white])
    item('AVAILABILITY', 'Availability',
        {'proposed_sale_policy': 'Made to order individually / enquire', 'physical_stock_quantity': None,
         'manufacture_or_reproducibility_confirmed': False, 'production_capacity': None, 'lead_time': None},
        'Made to order individually / enquire — proposal; stock, reproducibility and lead time unknown',
        'Solo and room-setting images do not establish present inventory or production capacity. '
        'Made-to-order is an owner-review proposal, not a verified availability promise; no related stock setting is inherited.', [image_ref])
    evidence = sorted(set([p for p in HERE.iterdir() if p.is_file()] + [prior, ROOT / white, ROOT / copper, ROOT / pale,
        ROOT / cluster, HERE.parent / 'identity-approval.json', model_path, source] + [Path(x['preview_path']) for x in cache]))
    write('source-audit.json', {'schema_version': 1, 'status': 'PASS', 'checked_utc': now,
        'complete_current_source_files': 41, 'folders': 2, 'cached_source_previews_visually_reviewed': 41,
        'current_originals_downloaded_hash_verified_and_viewed': 3, 'physical_specification_or_stock_verification': False,
        'visual_findings': ['The plural folder label does not represent an arrangement: all selected complete views depict one two-curl spiral panel.',
            'Solo views include portrait/landscape orientations, details and tin-scale illustrations. No rear or multi-sculpture arrangement found in41files.',
            'Two compatible kitchen/room-setting references exist; actual installation, same-cast and compositing provenance remain unverified.',
            'Earlier blue/bronze references in the Verdigris folder retain a relationship question; no extra physical cast/mould/stock inferred.'],
        'evidence_sha256': {str(p): sha(p) for p in evidence}, 'remote_files_changed': False})
    links = {x['file_name']: x['copy_link_url'] for x in meta['previews']}
    write('component-review.json', {'schema_version': 1, 'prepared_utc': now, 'component_id': 'BC-DR-SPIRAL',
        'canonical_design_name': 'Dune Ripple Spiral — DR2', 'proposed_name': 'Dune Ripple Spiral — Bronze and Verdigris',
        'display_name': 'Dune Ripple Spiral — Bronze and Verdigris', 'family': 'Dune Ripple', 'review_number': 37,
        'family_review_number': 13, 'family_review_total': 14, 'size_finish_variant_id': VID,
        'variant_only_review': True, 'review_decision_mode': 'SIZE_FINISH_VARIANT_NAME_AND_SPECIFICATIONS',
        'parent_identity_approval': rel(HERE.parent / 'identity-approval.json'), 'prior_variant_identity_approval': rel(prior),
        'parent_design_relationship_status': 'Single two-curl spiral appearance reference; exact relationship to earlier blue/bronze images, mould and physical cast remains unverified',
        'scope': 'Selected individual Bronze/Verdigris depicted name/identity only. All six fields are proposals; plural source-folder name is not a set or component count.',
        'primary_image_id': front['id'], 'primary_folder_id': folder['id'], 'primary_image_link': links[front['id']],
        'primary_folder_link': links[folder['id']], 'metadata_checked_utc': meta['checked_utc'],
        'reference_refresh': rel(HERE / 'metadata-links.json'), 'source_audit': rel(HERE / 'source-audit.json'),
        'specification_review_items': items, 'original_download_receipts': [image_ref],
        'platform_mapping': {'status': 'EXACT SQUARESPACE/SHOPIFY OFFER UNCONFIRMED',
            'squarespace_id': None, 'shopify_handle': None, 'shared_sku': None, 'exact_existing_offer_confirmed': False,
            'candidate_check': rel(HERE / 'platform-candidate-check.json'), 'primary_file_id': front['id'], 'primary_folder_id': folder['id'],
            'related_pale_offer': {'offer_ref': 'O009', 'sku': 'SQ0059342',
                'scope': 'Pale027source retained separately; no exact dark Bronze/Verdigris binding or price/stock/specification transfer'},
            'native_platform_accounts_or_public_pages_refreshed': False},
        'photo_coverage': {'complete_individual_front': True, 'detail_views_available': True, 'wall_mounted_front_reference': True,
            'room_setting_reference_available': True, 'exact_rear_available': False, 'confirmed_series_reference_for_selected_finish': False,
            'same_physical_cast_in_context_verified': False, 'confirmed_client_installation_provenance': False,
            'composite_or_mockup_provenance_confirmed': False, 'physical_stock_inferred': False,
            'scope': 'Fresh complete39solo/2context census with IDs/paths/sizes matched to dated cached images; all41previews viewed. '
                'Three current originals downloaded/hash verified/viewed. Room references available, actual-installation provenance unknown, '
                'no exact rear or series image confirmed in this scope.'},
        'context_image_id': 'id:cnqzTNngPVsAAAAAAAylGg', 'context_folder_id': 'id:cnqzTNngPVsAAAAAAAyj-A',
        'context_image_link': links['id:cnqzTNngPVsAAAAAAAylGg'], 'context_folder_link': links['id:cnqzTNngPVsAAAAAAAyj-A'],
        'context_detail_image_id': 'id:cnqzTNngPVsAAAAAAAylGQ', 'context_detail_folder_id': 'id:cnqzTNngPVsAAAAAAAyj-A',
        'context_detail_image_link': links['id:cnqzTNngPVsAAAAAAAylGQ'],
        'identity_confirmed': False, 'specifications_approved': False, 'physical_specs_verified': False,
        'open_gaps': ['Actual face size, maximum depth and dry weight',
            'Actual binder, bronze/copper content, patination, reinforcement, sealer, care and exterior suitability',
            'Exact rear, hardware, attachment, grade, orientation and load', 'Exact individual platform offer and shared SKU',
            'Owner price, physical stock, reproducibility, capacity and lead time',
            'Series photograph and verified installation/same-cast provenance; relationship to prior blue/bronze references'],
        'source_conflicts': ['Source folder saysSpiral andWaves but selected imagery is one spiral panel, not a set.',
            'Related coloured35×21×6cm and white35×20cm/5–7depth standards are separate; actual selected measurements unknown.',
            'Dark bronze/verdigris appearance does not establish metal chemistry or a paleSQ0059342offer match.',
            'Separate photographs, orientations and appearance cards are not physical inventory units.'],
        'next_review_after_keep': {'component_id': 'BC-DR-WAVE3', 'review_number': 38,
            'size_finish_variant_id': 'DR3-WHITE', 'family_review_number': 14,
            'requires_exact_design_allocation_check': True}, 'next_global_component_id': 'BC-DR-WAVE3',
        'remote_files_changed': False, 'live_platform_records_changed': False})
    print(json.dumps({'status': 'PASS', 'variant': VID, 'six_unapproved_groups': len(items), 'evidence_files_hashed': len(evidence)}))


if __name__ == '__main__':
    main()
