"""Prepare one depicted Gold reference while retaining distinct source offers."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
VID = 'DR-SPIRAL-GOLD'
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
    assert front['id'] == 'id:cnqzTNngPVsAAAAAAAygjg' and folder['id'] == 'id:cnqzTNngPVsAAAAAAAygjA'
    assert {k: len(v['entries']) for k, v in meta['listings'].items()} == {'solo': 179, 'context': 17}
    assert all(not v['has_more'] and not v['cursor'] for v in meta['listings'].values())
    cache = read(HERE / 'image-review-index.json')['cached_previews']
    assert len(cache) == len({x['id'] for x in cache}) == 196
    originals = read(HERE / 'download-receipts.json')
    assert len(originals) == 5
    for r in originals:
        path = Path(r['local_path'])
        assert sha(path) == r['sha256'] and path.stat().st_size == r['size']
        chunks = []
        with path.open('rb') as stream:
            while block := stream.read(4194304):
                chunks.append(hashlib.sha256(block).digest())
        assert hashlib.sha256(b''.join(chunks)).hexdigest() == r['content_hash'] == r['dropbox_content_hash_verified']
    native = read(HERE / 'native-platform-source-check.json')
    assert native['status'] == 'PASS' and sha(Path(native['source_workbook'])) == native['source_sha256']
    ss = {x['fields']['SKU']: x for x in native['matches']['SS Wall Products']}
    assert set(ss) == {'SQ6244576', 'GDRS-1-35.20'}
    sh_rows = native['matches']['SH Wall Products']
    assert len(sh_rows) == 1 and sh_rows[0]['fields']['Variant SKU'] == 'GDRS-1-35.20'
    primary, related, sh = ss['SQ6244576']['fields'], ss['GDRS-1-35.20']['fields'], sh_rows[0]['fields']
    assert ss['SQ6244576']['row'] == 7 and ss['GDRS-1-35.20']['row'] == 44 and sh_rows[0]['row'] == 34
    assert primary['Price'] == '299.00' and related['Price'] == '200.00'
    assert sh['Variant Grams'] == '5000' and sh['Variant Price'] == '200'
    assert sh['Handle'] == 'golden-spiral-dune-ripple'
    public = read(HERE / 'public-web-result.json')
    assert isinstance(public, str) and '£299.00' in public and '35 cm x 21 cm x 6 cm' in public
    assert 'hand-leafed gold' in public and '(404) Not Found' in public
    pages = read(HERE / 'public-source-receipts.json')
    assert [x['http_status'] for x in pages] == [403, 403]
    assert all(not x['retried_or_bypassed'] for x in pages)
    galleries = read(HERE / 'public-gallery-download-receipts.json')
    assert len(galleries) == 5
    for r in galleries:
        assert r['status'] == 'PASS' and r['http_status'] == 200
        assert sha(Path(r['local_path'])) == r['sha256']
    prior = HERE.parent / 'copper-partial-verdigris/identity-approval.json'
    approval = read(prior)
    assert approval['user_statement'] == 'Keep “Dune Ripple Spiral — Copper and Partial Verdigris”'
    assert approval['identity_confirmed'] and not approval['specifications_approved']
    rear = HERE / 'dune-ripple__dune-ripple-spiral-gold__172.jpeg'
    copper_rear = HERE.parent / 'copper/public-gallery-05.jpg'
    write('rear-source-comparison.json', {'status': 'VISUAL CROSS-SOURCE ASSOCIATION ONLY',
        'gold_dropbox_file_id': 'id:cnqzTNngPVsAAAAAAAygkw', 'gold_rear_sha256': sha(rear),
        'related_copper_public_rear_sha256': sha(copper_rear), 'exact_bytes_equal': rear.read_bytes() == copper_rear.read_bytes(),
        'scope': 'Gold folder rear172 has the same-looking white fill, edge, plate and cracked filling features as the separate Copper public rear. '
            'Different JPEG bytes; no numeric image identity test or physical cast pairing certification. The Gold public five-image gallery contains no rear.',
        'physical_gold_front_back_pair_verified': False, 'hardware_material_or_load_verified': False})
    source_refs = [rel(HERE / 'native-platform-source-check.json'), rel(HERE / 'public-web-result.json')]
    white = rel(HERE.parent / 'component-review.json')
    items = []

    def item(suffix, field, value, display, status, basis, refs):
        items.append({'proposal_id': VID + '-' + suffix, 'field': field, 'value': value, 'display': display,
            'status': status, 'basis': basis, 'source_refs': refs, 'owner_approved': False})

    item('DIMENSIONS', 'Individual dimensions and depth',
        {'listing_dimensions_cm': [35, 21, 6], 'related_offer_dimensions_cm': [35, 20, 5], 'actual_measured_dimensions_cm': None},
        '35 H × 21 W × 6 D cm — primary listing claim; related offer states 35 × 20 × 5 cm',
        'SOURCE CLAIM WITH DISTINCT OFFER DIMENSIONS; OWNER/MEASUREMENT PENDING',
        'Primary SQ6244576 native/public description gives 35 × 21 × 6 cm and its gallery matches selected167. '
        'GDRS-1-35.20 is a separate shared-SKU offer stating 35 × 20 × 5 cm. No silent harmonization or exact mould/cast equivalence.', source_refs)
    item('WEIGHT', 'Individual dry weight',
        {'proposed_weight_kg': 5, 'related_shopify_weight_grams': 5000, 'related_offer_ref': 'O039',
         'historical_white_calculated_range_kg': [3, 5], 'actual_weighed_kg': None,
         'primary_native_raw_weight': '11.0', 'primary_native_weight_unit': None, 'raw_squarespace_weight_converted': False},
        'Approximately 5 kg — working estimate using the related Shopify record; actual selected panel unweighed',
        'UNAPPROVED RELATED-SOURCE ESTIMATE; NOT AN EXACT CAST WEIGHT',
        'Unit-qualified Shopify GDRS-1-35.20 gives 5000 grams, equal to 5 kg for that offer. Use 5 kg only as a proposal '
        'for selected167, at the upper end of related white calculated 3–5 kg. Different offered dimensions prevent exact transfer. '
        'Squarespace raw weights 11.0/11.023 have no encoded unit and are not converted.', [source_refs[0], white])
    item('MATERIAL', 'Material and finish',
        {'listing_substrate': 'Plaster with natural/mineral materials', 'listing_finish': 'Hand-applied gold leaf',
         'actual_binder': None, 'leaf_composition_or_purity': None, 'reinforcement': None, 'sealing': None},
        'Plaster-based cast with applied gold leaf — listing claim; composition and sealing unverified',
        'SOURCE MATERIAL/FINISH CLAIM; PHYSICAL VERIFICATION PENDING',
        'Primary source explicitly describes plaster/natural materials and hand-leafed gold; related offer also describes gold leaf. '
        'Photographs support a broken metallic gold appearance, not leaf purity, actual binder, reinforcement, sealer, care or outdoor suitability.', source_refs)
    item('FIXING', 'Fixing',
        {'proposed_hanging_points': 1, 'proposed_type': 'Recessed rear keyhole plate',
         'candidate_rear_file_id': 'id:cnqzTNngPVsAAAAAAAygkw', 'exact_physical_front_back_pair_verified': False,
         'actual_hardware_material': None, 'attachment': None, 'rated_load': None, 'orientation_verified': False},
        'One recessed keyhole fixing — proposal; candidate rear shows one plate, exact Gold pairing unconfirmed',
        'UNAPPROVED GUESS FROM CANDIDATE REAR AND RELATED STANDARD',
        'Folder172 shows one metal keyhole plate but resembles a rear used in the separate Copper listing. '
        'No rear is in the Gold public gallery. White DR2 maker instruction specifies a single rear fixing; '
        'do not inherit its grade, upper-third position, attachment, load or hanging orientation.',
        [rel(HERE / 'rear-source-comparison.json'), white])
    item('PRICE', 'Individual retail price',
        {'primary_listing_amount': 299, 'related_offer_amount': 200, 'currency': 'GBP', 'sale_unit': 'One individual Gold panel',
         'owner_price_approval': False, 'new_commission_quote': None},
        '£299 per listed individual panel — primary source price; separate shared-SKU offer is £200',
        'DISTINCT SOURCE OFFER PRICES; OWNER RECONCILIATION PENDING',
        'Primary export and public web evidence show £299. The separately linked SS/Shopify offer gives £200 in both exports. '
        'No family price division or decision that either price supersedes the other. Ordinary page GETs were403; '
        'web primary result was crawled six days before this review and is not proof of a fresh live checkout price.', source_refs)
    item('AVAILABILITY', 'Availability',
        {'primary_web_purchase_control_observed': True, 'primary_native_visible': 'Yes', 'native_historical_stock_setting': 'Unlimited',
         'related_ss_native_visible': 'No', 'related_shopify_export_status': 'active', 'physical_stock_quantity': None,
         'current_live_checkout_or_native_admin_state_verified': False, 'lead_time': None, 'made_to_order_confirmed': False},
        'Advertised for purchase; physical stock and lead time unconfirmed',
        'SOURCE PLATFORM STATES; CURRENT PHYSICAL AVAILABILITY UNKNOWN',
        'Primary web evidence displays Add to cart. Related Squarespace export is hidden while Shopify export is active; '
        'its public page could not be read (web404, ordinaryGET403). Unlimited/active settings and source photos '
        'do not establish a current physical count, reproducibility, lead time or made-to-order promise.', source_refs)
    evidence = sorted(set([p for p in HERE.iterdir() if p.is_file()] + [prior, ROOT / white,
        HERE.parent / 'identity-approval.json', HERE.parent / 'copper/collect_sources.py', copper_rear,
        Path(native['source_workbook'])] + [Path(x['preview_path']) for x in cache]))
    write('source-audit.json', {'schema_version': 1, 'status': 'PASS', 'checked_utc': now,
        'complete_current_source_files': 196, 'folders': 2, 'cached_source_file_previews_visually_reviewed': 196,
        'current_dropbox_originals_downloaded_hash_verified_and_viewed': 5,
        'current_public_gallery_originals_downloaded_hash_verified_and_viewed': 5,
        'primary_ss_sku_matches': 1, 'primary_shopify_sku_matches': 0, 'related_shared_sku_ss_matches': 1, 'related_shared_sku_sh_matches': 1,
        'access_conditions': 'Primary web result available/crawled six days ago; related web404; ordinaryGET403 for both retained/no retry; five CDN image GETs200.',
        'visual_findings': ['Public gallery image2 matches selected Dropbox167 composition, design, texture, gold finish and wall context.',
            '165 is the earlier shared-offer reference on black/gold decorative display backing; no actual same-cast or mould equivalence established.',
            'Source files contain several lighting/presentation/finish-stage appearances, not 196 sculptures or proof of multiple physical units.',
            'Room references and a freestanding display-board photograph exist. Same-cast/client-installation/compositing provenance is unverified.',
            'No multi-panel sculpture arrangement confirmed in the196 files. Rear172 remains an unassigned Gold candidate with cross-source Copper association.'],
        'physical_specification_or_stock_verification': False, 'evidence_sha256': {str(p): sha(p) for p in evidence},
        'remote_files_changed': False})
    links = {x['file_name']: x['copy_link_url'] for x in meta['previews']}
    write('component-review.json', {'schema_version': 1, 'prepared_utc': now, 'component_id': 'BC-DR-SPIRAL',
        'canonical_design_name': 'Dune Ripple Spiral — DR2', 'proposed_name': 'Dune Ripple Spiral — Gold',
        'display_name': 'Dune Ripple Spiral — Gold', 'family': 'Dune Ripple', 'review_number': 37,
        'family_review_number': 12, 'family_review_total': 14, 'size_finish_variant_id': VID,
        'variant_only_review': True, 'review_decision_mode': 'SIZE_FINISH_VARIANT_NAME_AND_SPECIFICATIONS',
        'parent_identity_approval': rel(HERE.parent / 'identity-approval.json'), 'prior_variant_identity_approval': rel(prior),
        'parent_design_relationship_status': 'Two-curl Gold design/finish reference; source offers and other folder appearances retained separately; physical mould/cast relationship unverified',
        'scope': 'Selected Gold167 depicted name/identity only; all six specification groups remain separately pending. No physical inventory count inferred.',
        'primary_image_id': front['id'], 'primary_folder_id': folder['id'], 'primary_image_link': links[front['id']],
        'primary_folder_link': links[folder['id']], 'metadata_checked_utc': meta['checked_utc'],
        'reference_refresh': rel(HERE / 'metadata-links.json'), 'source_audit': rel(HERE / 'source-audit.json'),
        'specification_review_items': items, 'original_download_receipts': [rel(HERE / 'download-receipts.json')],
        'platform_mapping': {'status': 'PRIMARY SQUARESPACE PHOTO/FINISH MATCH; RELATED EXACT SHARED-SKU PAIR RETAINED AS A SEPARATE OFFER',
            'offer_ref': 'O002', 'squarespace_id': primary['Product ID [Non Editable]'],
            'squarespace_variant_id': primary['Variant ID [Non Editable]'], 'squarespace_sku': 'SQ6244576',
            'squarespace_source_row': 7, 'shopify_handle': None, 'shared_sku': None, 'shopify_sku_matches_in_supplied_export': 0,
            'public_source_url': 'https://boldstonesculpture.com/buy/p/gold-leaf-wave-relief-sculpture',
            'public_web_result_crawled_days_before_review': 6, 'ordinary_public_page_get_result': 403,
            'related_platform_pair': {'offer_ref': 'O039', 'shared_sku': 'GDRS-1-35.20',
                'squarespace_id': related['Product ID [Non Editable]'], 'squarespace_variant_id': related['Variant ID [Non Editable]'],
                'squarespace_source_row': 44, 'shopify_handle': sh['Handle'], 'shopify_source_row': 34,
                'source_dimensions_cm': [35, 20, 5], 'source_weight_grams': 5000, 'source_price_gbp': 200,
                'dropbox_image_id': 'id:cnqzTNngPVsAAAAAAArqYA', 'dropbox_folder_id': folder['id'],
                'dropbox_image_link': links['id:cnqzTNngPVsAAAAAAArqYA'],
                'scope': 'Shared SKU establishes platform pair.165is a Gold design/finish photo reference; actual relationship to selected167and different claims remains unresolved.'},
            'primary_file_id': front['id'], 'primary_folder_id': folder['id'], 'native_source': source_refs[0],
            'physical_mould_or_cast_equivalence_confirmed': False, 'live_platform_admin_accounts_refreshed': False},
        'photo_coverage': {'complete_individual_front': True, 'detail_views_available': True, 'wall_mounted_front_reference': True,
            'room_setting_reference_available': True, 'display_board_reference_available': True,
            'candidate_rear_available': True, 'exact_physical_front_back_pair_verified': False,
            'same_physical_cast_in_context_verified': False, 'confirmed_client_installation_provenance': False,
            'composite_or_mockup_provenance_confirmed': False, 'confirmed_series_reference_for_selected_finish': False,
            'physical_stock_inferred': False,
            'scope': 'Complete current179solo/17context census.196dated cached previews reviewed with IDs/paths/sizes checked; '
                'five current Dropbox originals and five current public gallery originals downloaded/hash verified/viewed. '
                'Setting/display photographs available; installation/same-cast provenance unverified, rear candidate unassigned, no series arrangement confirmed.'},
        'context_image_id': 'id:cnqzTNngPVsAAAAAAAylGw', 'context_folder_id': 'id:cnqzTNngPVsAAAAAAAyj9Q',
        'context_image_link': links['id:cnqzTNngPVsAAAAAAAylGw'], 'context_folder_link': links['id:cnqzTNngPVsAAAAAAAyj9Q'],
        'display_image_id': 'id:cnqzTNngPVsAAAAAAAsSdA', 'display_folder_id': 'id:cnqzTNngPVsAAAAAAAyj9Q',
        'display_image_link': links['id:cnqzTNngPVsAAAAAAAsSdA'],
        'candidate_rear_image_id': 'id:cnqzTNngPVsAAAAAAAygkw', 'candidate_rear_folder_id': folder['id'],
        'candidate_rear_image_link': links['id:cnqzTNngPVsAAAAAAAygkw'],
        'identity_confirmed': False, 'specifications_approved': False, 'physical_specs_verified': False,
        'open_gaps': ['Actual selected-cast dimensions and dry weight', 'Which Gold source offer/claims apply to selected cast; relationship of165and167',
            'Actual binder, leaf composition/purity, reinforcement, sealer, care and outdoor suitability',
            'Exact Gold rear pairing, hardware attachment, grade, position, orientation and load',
            'Owner retail decision, physical stock, reproducibility, capacity and lead time',
            'Confirmed client installation/same-cast provenance and multi-panel series image'],
        'source_conflicts': ['Primary35×21×6cm/£299versus related shared-offer35×20×5cm/£200; retained separately.',
            'Related Shopify5000g is unit-qualified but not an actual weighing of selected167; raw Squarespace weights remain unencoded.',
            'Rear172has a same-looking Copper-source counterpart and is not uniquely allocated to the Gold front.',
            'Public page access and native visibility/status fields do not establish current physical availability.'],
        'next_review_after_keep': {'component_id': 'BC-DR-SPIRAL', 'review_number': 37,
            'size_finish_variant_id': 'DR-SPIRAL-BRONZE-VERDIGRIS', 'family_review_number': 13,
            'requires_exact_design_allocation_check': True}, 'next_global_component_id': 'BC-DR-WAVE3',
        'remote_files_changed': False, 'live_platform_records_changed': False})
    print(json.dumps({'status': 'PASS', 'variant': VID, 'six_unapproved_groups': len(items), 'evidence_files_hashed': len(evidence)}))


if __name__ == '__main__':
    main()
