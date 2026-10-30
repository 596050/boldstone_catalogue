"""Prepare the individual Copper reference with six separately pending fields."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
VID = 'DR-SPIRAL-COPPER'
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
rel = lambda p: str(p.relative_to(ROOT))


def write(name, value):
    path = HERE / name
    assert not path.exists(), f'Frozen record exists: {path}'
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def main():
    metadata = read(HERE / 'metadata-links.json')
    front, folder = metadata['primary_metadata']['file'], metadata['folder_metadata']['folder']
    assert front['id'] == 'id:cnqzTNngPVsAAAAAAAykFA' and folder['id'] == 'id:cnqzTNngPVsAAAAAAAykCw'
    solo = metadata['listings']['solo']
    assert len(solo['entries']) == 4 and not solo['has_more'] and not solo['cursor']
    family = metadata['family_listing']
    assert len(family['entries']) == 23 and not family['has_more'] and not family['cursor']
    assert not any('copper' in x['name'].lower() and ('situ' in x['name'].lower() or 'waves' in x['name'].lower()) for x in family['entries'])
    native = read(HERE / 'native-platform-source-check.json')
    assert native['status'] == 'PASS' and not native['matches']['SH Wall Products']
    assert len(native['matches']['SS Wall Products']) == 1
    ss = native['matches']['SS Wall Products'][0]
    assert ss['row'] == 57
    fields = ss['fields']
    assert fields['SKU'] == 'EBAY-188654831217' and fields['Weight'] == '6.6'
    assert fields['Product ID [Non Editable]'] == '6a5a62191b9743318ccb1a00'
    assert sha(Path(native['source_workbook'])) == native['source_sha256']
    public = read(HERE / 'public-web-specification-check.json')
    assert public['status'] == 'PASS' and public['price'] == 40.33 and public['dimensions_cm'] == [35, 21, 6]
    blocked = read(HERE / 'public-page-http-receipt.json')
    assert blocked['http_status'] == 403 and not blocked['ordinary_get_retried']
    originals = read(HERE / 'download-receipts.json')
    assert len(originals) == 4 and {x['id'] for x in originals} == {x['file_id'] for x in solo['entries']}
    for receipt in originals:
        path = Path(receipt['local_path'])
        assert sha(path) == receipt['sha256'] and path.stat().st_size == receipt['size']
        chunks = []
        with path.open('rb') as stream:
            while block := stream.read(4194304):
                chunks.append(hashlib.sha256(block).digest())
        assert hashlib.sha256(b''.join(chunks)).hexdigest() == receipt['content_hash'] == receipt['dropbox_content_hash_verified']
    galleries = read(HERE / 'public-gallery-download-receipts.json')
    assert len(galleries) == 5
    for receipt, url in zip(galleries, public['gallery_urls']):
        path = Path(receipt['local_path'])
        assert receipt['status'] == 'PASS' and receipt['url'] == url
        assert sha(path) == receipt['sha256'] and path.stat().st_size == receipt['size']
    prior = HERE.parent / 'rust/identity-approval.json'
    approval = read(prior)
    assert approval['user_statement'] == 'Keep “Dune Ripple Spiral — Rust”'
    assert approval['identity_confirmed'] and not approval['specifications_approved']
    refs = [rel(HERE / 'native-platform-source-check.json'), rel(HERE / 'public-web-specification-check.json')]
    white = rel(HERE.parent / 'component-review.json')
    items = []

    def item(suffix, field, value, display, status, basis, sources):
        items.append({'proposal_id': VID + '-' + suffix, 'field': field, 'value': value, 'display': display,
            'status': status, 'basis': basis, 'source_refs': sources, 'owner_approved': False})

    item('DIMENSIONS', 'Individual dimensions and depth',
        {'listing_dimensions_cm': [35, 21, 6], 'axis_order': ['height', 'width', 'depth'], 'actual_measured_dimensions_cm': None},
        '35 H × 21 W × 6 D cm — individual listing claim; actual panel unmeasured',
        'SOURCE CLAIM; OWNER AND MEASUREMENT PENDING',
        'Both native and current public descriptions give 35 × 21 × 6 cm with vertical orientation. '
        'The gallery also shows a horizontal presentation; it does not establish an alternate fixing orientation. '
        'Related white 35 × 20 cm standard remains separate.', refs)
    item('WEIGHT', 'Individual dry weight',
        {'proposed_weight_kg': 4, 'working_estimate_range_kg': [3, 5], 'actual_weighed_kg': None,
         'native_raw_weight': '6.6', 'native_weight_unit': None, 'native_weight_converted': False},
        'Approximately 4 kg (working range 3–5 kg) — guess; not weighed',
        'UNAPPROVED ANALOGY ESTIMATE; NATIVE UNIT UNENCODED',
        'Related white DR2 maker standard calculates 3–5 kg, but the Copper source describes plaster and sand; '
        'its binder proportions, thickness and actual weight are unknown. Raw native 6.6 has no encoded unit '
        'and is neither converted nor treated as kilograms. No family or set weight is divided.',
        [white, 'manufacture-stevensons:Sheet1!row55; related white standard only', refs[0]])
    item('MATERIAL', 'Material and finish',
        {'listing_material': 'Plaster and sand with hand-laid copper surface effect', 'actual_substrate_verified': False,
         'actual_copper_content': None, 'reinforcement': None, 'sealing': None},
        'Plaster and sand with a hand-laid copper surface effect — listing claim; composition unverified',
        'SOURCE CLAIM; OWNER AND MATERIAL VERIFICATION PENDING',
        'Native and current public descriptions agree. The photographs show a warm copper-coloured two-curl panel. '
        'Neither surface colour nor marketing wording verifies actual copper content, leaf, binder proportions, '
        'reinforcement, sealer, care or outdoor suitability. Do not transfer AC730 from the white standard.', refs)
    item('FIXING', 'Fixing',
        {'visible_hanging_points': 1, 'visible_type': 'Recessed rear keyhole plate', 'public_gallery_index': 5,
         'dropbox_rear_for_this_reference_confirmed': False, 'physical_front_back_pair_verified': False,
         'actual_hardware_material': None, 'attachment': None, 'rated_load': None, 'alternate_orientation_verified': False},
        'One recessed keyhole plate visible in the listing’s rear photo; hardware and load capacity unconfirmed',
        'LISTING-PHOTO OBSERVATION; PHYSICAL VERIFICATION PENDING',
        'Current public gallery image 5 shows a white filled rear with one metal keyhole plate. '
        'No rear appears among the four Copper-folder files. Source association does not verify physical cast pairing, '
        'grade, attachment, load capacity or horizontal hanging. White-standard hardware/placement is not inherited.',
        [rel(HERE / 'public-gallery-download-receipts.json')])
    item('PRICE', 'Individual retail price',
        {'listing_amount': 40.33, 'currency': 'GBP', 'sale_unit': 'One listed Copper panel',
         'owner_price_approval': False, 'new_commission_quote': None},
        '£40.33 per listed individual panel — current advertised price; new commission quote unconfirmed',
        'SOURCE PRICE; OWNER AND FUTURE QUOTE PENDING',
        'Unique native Squarespace row and current public page agree on £40.33. This is an individual source offer; '
        'no family-price division, finish allowance or proposed commission price is used.', refs)
    item('AVAILABILITY', 'Availability',
        {'public_listing_for_purchase': True, 'public_schema_availability': None, 'native_historical_stock_field': 'Unlimited',
         'physical_stock_quantity': None, 'lead_time': None, 'made_to_order_confirmed': False, 'production_capacity': None},
        'Listed for purchase; physical stock and lead time unconfirmed',
        'PUBLIC PURCHASE CONTROL; PHYSICAL AVAILABILITY UNKNOWN',
        'The public page displays Add to cart. Historical native stock Unlimited is a platform setting, '
        'not unlimited physical stock or a manufacture promise. JSON-LD availability was not freshly obtained '
        'because ordinary page GET was blocked; no InStock, lead time or made-to-order claim is inferred.', refs)
    now = datetime.now(timezone.utc).isoformat()
    evidence = sorted(set([p for p in HERE.iterdir() if p.is_file()] + [prior, HERE.parent / 'identity-approval.json',
        HERE.parent / 'component-review.json', Path(native['source_workbook'])]))
    audit = {'schema_version': 1, 'status': 'PASS', 'checked_utc': now,
        'complete_copper_folder_files': 4, 'current_family_child_folders': 23, 'complete_pagination': True,
        'current_dropbox_originals_downloaded_hash_verified_and_visually_reviewed': 4,
        'current_public_gallery_originals_downloaded_hash_verified_and_visually_reviewed': 5,
        'public_page_read_via_web': True, 'ordinary_page_get_403_preserved_and_not_retried': True,
        'native_squarespace_sku_matches': 1, 'native_shopify_sku_matches': 0,
        'visual_findings': ['Public gallery 1 matches Dropbox 002 front composition; public gallery 3 matches selected Dropbox 003 angled view.',
            'Public gallery 4 matches Dropbox 001 angled composition. Copper relief, texture and stone-wall context agree visually.',
            'Public gallery 5 is a white-filled rear with one keyhole plate; no Copper-folder rear counterpart is confirmed.',
            'Dropbox 004 shows a close studio view; different lighting does not establish another cast.',
            'No confirmed room/garden installation or series image is assigned to this Copper reference. This is an open gap, not an exhaustive absence claim.'],
        'physical_cast_or_specification_verification': False,
        'evidence_sha256': {str(p): sha(p) for p in evidence}, 'remote_files_changed': False}
    write('source-audit.json', audit)
    links = {x['file_name']: x['copy_link_url'] for x in metadata['previews']}
    card = {'schema_version': 1, 'prepared_utc': now, 'component_id': 'BC-DR-SPIRAL',
        'canonical_design_name': 'Dune Ripple Spiral — DR2', 'proposed_name': 'Dune Ripple Spiral — Copper',
        'display_name': 'Dune Ripple Spiral — Copper', 'family': 'Dune Ripple', 'review_number': 37,
        'family_review_number': 10, 'family_review_total': 14, 'size_finish_variant_id': VID,
        'variant_only_review': True, 'review_decision_mode': 'SIZE_FINISH_VARIANT_NAME_AND_SPECIFICATIONS',
        'parent_identity_approval': rel(HERE.parent / 'identity-approval.json'), 'prior_variant_identity_approval': rel(prior),
        'parent_design_relationship_status': 'Source-assisted two-curl DR2 design and Copper finish reference; actual mould/cast relationship unverified',
        'scope': 'Selected individual Copper name and depicted identity only. Six specifications require separate approval; no physical count inferred.',
        'primary_image_id': front['id'], 'primary_folder_id': folder['id'],
        'primary_image_link': links[front['id']], 'primary_folder_link': links[folder['id']],
        'metadata_checked_utc': metadata['checked_utc'], 'reference_refresh': rel(HERE / 'metadata-links.json'),
        'source_audit': rel(HERE / 'source-audit.json'), 'specification_review_items': items,
        'original_download_receipts': [rel(HERE / 'download-receipts.json')],
        'platform_mapping': {'status': 'SQUARESPACE DEPICTED DESIGN/FINISH SOURCE MATCH; SHOPIFY SKU ABSENT IN SUPPLIED EXPORT',
            'offer_ref': 'O052', 'squarespace_id': fields['Product ID [Non Editable]'],
            'squarespace_variant_id': fields['Variant ID [Non Editable]'], 'squarespace_sku': fields['SKU'],
            'squarespace_source_row': 57, 'shopify_handle': None, 'shared_sku': None,
            'shopify_sku_matches_in_supplied_export': 0, 'native_source': refs[0], 'public_source_url': public['source_url'],
            'public_page_read_via_web': True, 'public_sku_freshly_verified': False, 'public_schema_availability_freshly_verified': False,
            'primary_file_id': front['id'], 'primary_folder_id': folder['id'],
            'source_photo_relationship': 'Matching two-curl design, copper-effect finish, texture, proportions and stone-wall source compositions',
            'physical_mould_or_cast_equivalence_confirmed': False, 'native_platform_admin_accounts_refreshed': False},
        'photo_coverage': {'complete_individual_front': True, 'detail_views_available': True,
            'wall_mounted_front_reference': True, 'public_listing_associated_rear_photo_available': True,
            'dropbox_rear_for_this_reference_confirmed': False, 'exact_physical_front_back_pair_verified': False,
            'confirmed_room_garden_or_client_installation_for_selected_reference': False,
            'confirmed_series_reference_for_selected_finish': False, 'physical_stock_inferred': False,
            'scope': 'Fresh complete four-file Copper-folder census; all four current originals downloaded, hash verified and visually reviewed. '
                'All five current public gallery originals verified/viewed. Current 23-child-folder family listing has no dedicated Copper context/series folder; '
                'a confirmed room/garden installation and a series photograph for this selected finish remain unassigned. Other finish images are not inherited.'},
        'public_rear_image_url': public['gallery_urls'][4], 'public_rear_gallery_index': 5,
        'identity_confirmed': False, 'specifications_approved': False, 'physical_specs_verified': False,
        'open_gaps': ['Actual face, maximum depth and dry weight', 'Actual binder proportions, copper content, reinforcement, sealer and care',
            'Exact physical rear pairing, Dropbox rear counterpart, fixing grade, attachment, load and hanging orientation',
            'Confirmed in situ setting and series image for selected Copper finish',
            'Shopify counterpart beyond supplied export; live admin state',
            'Owner individual price, physical stock, reproducibility, production capacity and lead time'],
        'source_conflicts': ['Native raw weight 6.6 has no encoded unit and is not converted.',
            'Related white standard 35 × 20 cm and 5–7 cm depth remain separate from Copper listing 35 × 21 × 6 cm.',
            'Copper listing says plaster and sand; white AC730 and hardware instructions are not transferred.',
            'Ordinary public page GET returned 403; successful independent web evidence supplies current visible claims, not raw JSON-LD.'],
        'next_review_after_keep': {'component_id': 'BC-DR-SPIRAL', 'review_number': 37,
            'size_finish_variant_id': 'DR-SPIRAL-COPPER-PARTIAL-VERDIGRIS', 'family_review_number': 11,
            'requires_exact_design_allocation_check': True}, 'next_global_component_id': 'BC-DR-WAVE3',
        'remote_files_changed': False, 'live_platform_records_changed': False}
    write('component-review.json', card)
    print(json.dumps({'status': 'PASS', 'variant': VID, 'six_unapproved_groups': len(items), 'evidence_files_hashed': len(evidence)}))


if __name__ == '__main__':
    main()
