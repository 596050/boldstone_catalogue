"""Freeze the evidence and six separately pending proposals for the Rust card."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
CID, VID = 'BC-DR-SPIRAL', 'DR-SPIRAL-RUST'


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative(path):
    return str(path.relative_to(ROOT))


def write(path, value):
    assert not path.exists(), f'Frozen review already exists: {path}'
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def verify_original(receipt):
    path = Path(receipt['local_path'])
    assert path.stat().st_size == receipt['size']
    assert sha(path) == receipt['sha256']
    chunks = []
    with path.open('rb') as stream:
        while block := stream.read(4 * 1024 * 1024):
            chunks.append(hashlib.sha256(block).digest())
    content_hash = hashlib.sha256(b''.join(chunks)).hexdigest()
    assert content_hash == receipt['content_hash'] == receipt['dropbox_content_hash_verified']
    return path


def main():
    assert ROOT.name == 'sculpture-catalogue'
    metadata = read(HERE / 'metadata-links.json')
    links = {x['file_name']: x['copy_link_url'] for x in metadata['previews']}
    front, folder = metadata['primary_metadata']['file'], metadata['folder_metadata']['folder']
    assert front['id'] == 'id:cnqzTNngPVsAAAAAAAygCg'
    assert folder['id'] == 'id:cnqzTNngPVsAAAAAAAygCQ'
    expected_census = {'solo': 19, 'solo_context': 1, 'mixed': 12}
    assert {key: len(value['entries']) for key, value in metadata['listings'].items()} == expected_census
    assert all(not value['cursor'] and not value['has_more'] for value in metadata['listings'].values())
    cache = read(HERE / 'image-review-index.json')['cached_previews']
    assert len(cache) == len({x['id'] for x in cache}) == 32
    assert all(Path(x['preview_path']).is_file() for x in cache)
    originals = read(HERE / 'download-receipts.json') + [read(HERE / 'rear-download-receipt.json')]
    reuse = read(HERE / 'series-original-reuse-check.json')
    assert reuse['status'] == 'PASS' and reuse['mixed12file_census_unchanged']
    originals.append(reuse['original_receipt'])
    original_paths = [verify_original(x) for x in originals]
    assert {x['id'] for x in originals} == {
        front['id'], 'id:cnqzTNngPVsAAAAAAAylFg', 'id:cnqzTNngPVsAAAAAAAygEQ', 'id:cnqzTNngPVsAAAAAAAsS6Q'}
    native = read(HERE / 'native-platform-source-check.json')
    assert native['status'] == 'PASS'
    source_workbook = Path(native['source_workbook'])
    assert sha(source_workbook) == native['source_sha256']
    ss = native['matches']['SS Wall Products']
    assert len(ss) == 1 and ss[0]['row'] == 73 and not native['matches']['SH Wall Products']
    fields = ss[0]['fields']
    assert fields['SKU'] == 'EBAY-188682535224'
    assert fields['Product ID [Non Editable]'] == '6aa01ab77f3077314dd71e8f'
    assert fields['Weight'] == '11.02' and fields['Stock'] == '1'
    public = read(HERE / 'public-page-http-receipt.json')
    assert public['status'] == 'PASS' and public['http_status'] == 200
    assert sha(Path(public['local_path'])) == public['sha256']
    offer = public['products'][0]['offers']
    assert offer['sku'] == fields['SKU'] and offer['price'] == 60.33 and offer['priceCurrency'] == 'GBP'
    assert offer['availability'] == 'InStock'
    text = (HERE / 'public-page-visible-text.txt').read_text()
    assert '35 cm x 21 cm x 6 cm' in text and 'faux rust-on-iron' in text
    assert 'fixing recessed into the back' in text
    gallery = read(HERE / 'public-gallery-download-receipts.json')
    assert len(gallery) == len(public['gallery_urls']) == 8
    for receipt, url in zip(gallery, public['gallery_urls']):
        path = Path(receipt['local_path'])
        assert receipt['status'] == 'PASS' and receipt['http_status'] == 200 and receipt['url'] == url
        assert path.stat().st_size == receipt['size'] and sha(path) == receipt['sha256']
    rear = read(HERE / 'rear-public-photo-comparison.json')
    assert not rear['numeric_photo_identity_confirmed']
    assert not rear['physical_front_back_cast_pair_verified'] and not rear['rear_photo_orientation_confirmed']
    previous = HERE.parent / 'verdigris-copper-speckled/identity-approval.json'
    approval = read(previous)
    assert approval['user_statement'] == 'Keep “Dune Ripple Spiral — Verdigris and Copper”'
    assert approval['identity_confirmed'] and not approval['specifications_approved']
    now = datetime.now(timezone.utc).isoformat()
    public_ref = relative(HERE / 'public-page-http-receipt.json')
    native_ref = relative(HERE / 'native-platform-source-check.json')
    white_ref = relative(HERE.parent / 'component-review.json')
    items = []

    def item(suffix, field, value, display, status, basis, refs):
        items.append({'proposal_id': VID + '-' + suffix, 'field': field, 'value': value,
            'display': display, 'status': status, 'basis': basis, 'source_refs': refs, 'owner_approved': False})

    item('DIMENSIONS', 'Individual dimensions and depth',
        {'listing_dimensions_cm': [35, 21, 6], 'axis_order': ['height', 'width', 'depth'],
         'actual_measured_dimensions_cm': None},
        '35 H × 21 W × 6 D cm — individual listing claim; actual panel unmeasured',
        'SOURCE CLAIM; OWNER AND PHYSICAL MEASUREMENT PENDING',
        'Native description and current public page both state 35 × 21 × 6 cm for one listed panel. '
        'The portrait image supports the height/width interpretation. Related white 35 × 20 cm and 5–7 cm depth remain separate.',
        [native_ref, public_ref])
    item('WEIGHT', 'Individual dry weight',
        {'proposed_weight_kg': 4, 'working_estimate_range_kg': [3, 5], 'actual_weighed_kg': None,
         'native_raw_weight': '11.02', 'native_weight_unit': None, 'native_weight_converted': False},
        'Approximately 4 kg (working range 3–5 kg) — guess; not weighed',
        'UNAPPROVED ANALOGY ESTIMATE; NATIVE WEIGHT UNIT UNENCODED',
        'Related white DR2 maker standard calculates 3–5 kg. This rust panel’s binder, thickness and filling are unverified. '
        'Raw native weight 11.02 has no encoded unit and is not converted or treated as kilograms. No set weight is divided.',
        [white_ref, 'manufacture-stevensons:Sheet1!row55; related white standard only', native_ref])
    item('MATERIAL', 'Material and finish',
        {'proposed_substrate': 'Cast mineral composite', 'listing_finish': 'Hand-painted faux rust-on-iron effect',
         'actual_binder': None, 'actual_iron_content': None, 'reinforcement': None, 'sealing': None},
        'Cast mineral composite — guess; hand-painted faux rust-on-iron finish stated by listing',
        'UNAPPROVED SUBSTRATE GUESS; FINISH IS A SOURCE CLAIM',
        'The source explicitly describes a painted faux rust effect. Cast mineral composite is an analogy guess from related works. '
        'The rear shows yellow outer material and white filling but does not identify either binder. Actual iron, plaster, resin, '
        'AC730, reinforcement, sealer and care are unconfirmed. Outdoor suitability is advertised, not independently certified.',
        [native_ref, public_ref, relative(HERE / 'rear-download-receipt.json')])
    item('FIXING', 'Fixing',
        {'visible_hanging_points': 1, 'visible_type': 'One recessed rear keyhole plate',
         'listing_rear_file_id': 'id:cnqzTNngPVsAAAAAAAygEQ', 'public_gallery_index': 8,
         'exact_physical_front_back_pair_verified': False, 'photo_orientation_confirmed': False,
         'actual_hardware_material': None, 'attachment': None, 'rated_load': None},
        'One recessed keyhole plate visible in listing-associated rear photo; grade, orientation and load unknown',
        'SOURCE-PHOTO OBSERVATION; PHYSICAL HARDWARE VERIFICATION PENDING',
        'Dropbox rear 008 and public gallery image 8 show compatible white fill, edge/crack patterns and one metal keyhole plate. '
        'The numeric photo comparison does not establish identity; source association and visible features only. '
        'Exact cast pairing, attachment and hanging orientation are unverified. Do not transfer the white standard’s stainless grade or upper-third placement.',
        [public_ref, relative(HERE / 'rear-download-receipt.json'), relative(HERE / 'rear-public-photo-comparison.json')])
    item('PRICE', 'Individual retail price',
        {'listing_amount': 60.33, 'currency': 'GBP', 'sale_unit': 'One listed individual rust panel',
         'owner_price_approval': False, 'new_commission_quote': None},
        '£60.33 per listed individual panel — current public/native price; new commission quote unconfirmed',
        'SOURCE PRICE; OWNER APPROVAL AND FUTURE QUOTE PENDING',
        'Unique native Squarespace source and current public page agree on £60.33. This is the advertised individual offer, '
        'not a family price or an inferred commission price.', [native_ref, public_ref])
    item('AVAILABILITY', 'Availability',
        {'public_listing_for_purchase': True, 'public_schema_availability': 'InStock',
         'native_historical_stock_field': '1', 'physical_stock_quantity': None,
         'lead_time': None, 'made_to_order_confirmed': False, 'production_capacity': None},
        'Listed for purchase; actual stock and lead time unconfirmed',
        'PUBLIC LISTING STATE; PHYSICAL AVAILABILITY UNKNOWN',
        'The current public page has InStock markup and an Add to cart control. The source export’s stock 1 is historical platform data. '
        'Neither establishes a present physical count, reproducibility or lead time. No made-to-order promise is inferred.',
        [native_ref, public_ref])
    assert len(items) == 6
    evidence = [p for p in HERE.iterdir() if p.is_file() and p.suffix in {'.json', '.jpg', '.png', '.html', '.txt', '.py'}]
    evidence += [previous, HERE.parent / 'identity-approval.json', HERE.parent / 'component-review.json', source_workbook]
    evidence += original_paths + [Path(x['preview_path']) for x in cache]
    evidence = sorted(set(evidence))
    audit = {'schema_version': 1, 'status': 'PASS', 'checked_utc': now,
        'dropbox_census': expected_census, 'complete_pagination': True, 'cached_images_visually_reviewed': 32,
        'current_originals_downloaded_hash_verified_and_viewed': 3,
        'previous_series_original_freshly_rehashed_and_viewed': 1,
        'public_gallery_images_downloaded_hash_verified_and_visually_reviewed': 8,
        'native_squarespace_sku_matches': 1, 'native_shopify_sku_matches': 0,
        'public_source_http_status': 200, 'web_tool_internal_failure_preserved': True,
        'physical_specification_or_stock_verification': False,
        'visual_findings': ['Rust portrait two-curl design agrees between the selected Dropbox front and public gallery.',
            'One metal keyhole plate appears in the source-associated rear photograph; physical pairing and photo orientation remain unverified.',
            'Garden image shows the rust spiral on the wall above/left of a separate rust wave panel.',
            'Indoor selected two-panel display shows the rust spiral above a separate verdigris/rust wave.',
            'Presentation and lighting differences across files are not counted as physical sculptures or stock.'],
        'evidence_sha256': {str(p): sha(p) for p in evidence},
        'remote_files_changed': False, 'live_platform_records_changed': False}
    audit_path = HERE / 'source-audit.json'
    write(audit_path, audit)
    review = {'schema_version': 1, 'prepared_utc': now, 'component_id': CID,
        'canonical_design_name': 'Dune Ripple Spiral — DR2', 'proposed_name': 'Dune Ripple Spiral — Rust',
        'display_name': 'Dune Ripple Spiral — Rust', 'family': 'Dune Ripple', 'review_number': 37,
        'family_review_number': 9, 'family_review_total': 14, 'size_finish_variant_id': VID,
        'variant_only_review': True, 'review_decision_mode': 'SIZE_FINISH_VARIANT_NAME_AND_SPECIFICATIONS',
        'parent_identity_approval': relative(HERE.parent / 'identity-approval.json'),
        'prior_variant_identity_approval': relative(previous),
        'parent_design_relationship_status': 'Source-assisted two-curl DR2 design and rust-finish reference; actual mould/cast relationship unverified',
        'scope': 'Selected individual rust-finish name and depicted identity. Six source/working specification groups require separate approval; no physical sculpture count inferred.',
        'primary_image_id': front['id'], 'primary_folder_id': folder['id'],
        'primary_image_link': links[front['id']], 'primary_folder_link': links[folder['id']],
        'metadata_checked_utc': metadata['checked_utc'], 'reference_refresh': relative(HERE / 'metadata-links.json'),
        'source_audit': relative(audit_path), 'specification_review_items': items,
        'original_download_receipts': [relative(HERE / x) for x in ['download-receipts.json', 'rear-download-receipt.json']],
        'series_original_reuse_check': relative(HERE / 'series-original-reuse-check.json'),
        'platform_mapping': {
            'status': 'SQUARESPACE SOURCE OFFER MATCHED TO DEPICTED DESIGN/FINISH; NO SHOPIFY SKU COUNTERPART IN SUPPLIED EXPORT',
            'offer_ref': 'O068', 'squarespace_id': fields['Product ID [Non Editable]'],
            'squarespace_variant_id': fields['Variant ID [Non Editable]'], 'squarespace_sku': fields['SKU'],
            'squarespace_source_row': 73, 'shopify_handle': None, 'shared_sku': None,
            'shopify_sku_matches_in_supplied_export': 0, 'native_source': native_ref,
            'public_source_url': public['url'], 'public_source_checked_utc': public['checked_utc'],
            'source_photo_relationship': 'Visual design, proportions and painted rust finish compatible; physical cast identity not independently verified',
            'primary_file_id': front['id'], 'primary_folder_id': folder['id'],
            'physical_mould_or_cast_equivalence_confirmed': False,
            'native_platform_admin_accounts_refreshed': False,
            'public_asset_url_ids_treated_as_product_ids': False},
        'photo_coverage': {
            'complete_individual_front': True, 'detail_views_available': True, 'wall_mounted_front_reference': True,
            'listing_associated_rear_photo_available': True, 'exact_physical_front_back_pair_verified': False,
            'garden_context_reference_available': True, 'series_arrangement_reference_available': True,
            'selected_indoor_series_depicted_panels': 2, 'selected_indoor_series_spiral_position': 'Upper panel',
            'same_physical_cast_in_context_or_series_verified': False,
            'confirmed_client_installation_provenance': False, 'physical_stock_inferred': False,
            'scope': 'Fresh complete 32-file census over 3 folders; all 32 dated cached images reviewed with current IDs/paths/sizes. '
                'Three current Dropbox originals downloaded/hash verified/viewed, one unchanged indoor original freshly rehashed/viewed, '
                'and all eight current public gallery images verified/viewed. Compatible photographs do not certify same cast, client installation, hardware or physical stock.'},
        'garden_image_id': 'id:cnqzTNngPVsAAAAAAAylFg', 'garden_folder_id': 'id:cnqzTNngPVsAAAAAAAyj9g',
        'garden_image_link': links['id:cnqzTNngPVsAAAAAAAylFg'],
        'garden_folder_link': links['id:cnqzTNngPVsAAAAAAAyj9g'],
        'garden_position': 'Rust spiral on wall above/left; separate rust wave panel in foreground',
        'series_image_id': 'id:cnqzTNngPVsAAAAAAAsS6Q', 'series_folder_id': 'id:cnqzTNngPVsAAAAAAAyiaw',
        'series_image_link': links['id:cnqzTNngPVsAAAAAAAsS6Q'],
        'series_folder_link': links['id:cnqzTNngPVsAAAAAAAyiaw'],
        'series_position': 'Rust spiral is the upper panel in selected two-panel indoor arrangement',
        'rear_image_id': 'id:cnqzTNngPVsAAAAAAAygEQ', 'rear_folder_id': folder['id'],
        'rear_image_link': links['id:cnqzTNngPVsAAAAAAAygEQ'],
        'identity_confirmed': False, 'specifications_approved': False, 'physical_specs_verified': False,
        'open_gaps': ['Actual height, width, maximum depth and dry weight',
            'Actual binder, filling, reinforcement, metal content, sealing, care and outdoor suitability',
            'Exact physical front/back pairing; fixing orientation, grade, attachment and load',
            'Shopify counterpart beyond supplied export; live native admin state',
            'Owner retail price decision, current physical quantity, reproducibility and lead time',
            'Same-cast relationship and actual client-installation provenance for context/series references'],
        'source_conflicts': ['Native weight 11.02 has no encoded unit; retain raw and do not convert.',
            'Related white DR2 standard is 35 × 20 cm with 5–7 cm depth; rust listing states 35 × 21 × 6 cm.',
            'Source InStock and historic stock 1 are platform fields, not verified current physical quantity.',
            'Public rear and Dropbox rear have different bytes; visual association does not establish numeric photo identity.'],
        'next_review_after_keep': {'component_id': CID, 'review_number': 37,
            'size_finish_variant_id': 'DR-SPIRAL-COPPER', 'family_review_number': 10,
            'requires_exact_design_allocation_check': True},
        'next_global_component_id': 'BC-DR-WAVE3', 'remote_files_changed': False,
        'live_platform_records_changed': False}
    write(HERE / 'component-review.json', review)
    print(json.dumps({'status': 'PASS', 'prepared_review': relative(HERE / 'component-review.json'),
        'six_unapproved_groups': len(items), 'evidence_files_hashed': len(evidence)}))


if __name__ == '__main__':
    main()
