"""Freeze the individual Copper/Partial Verdigris appearance and scoped guesses."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import openpyxl

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
VID = 'DR-SPIRAL-COPPER-PARTIAL-VERDIGRIS'
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
rel = lambda p: str(p.relative_to(ROOT))


def write(name, value):
    path = HERE / name
    assert not path.exists(), f'Frozen record exists: {path}'
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + '\n')


def main():
    now = datetime.now(timezone.utc).isoformat()
    metadata = read(HERE / 'metadata-links.json')
    front, folder = metadata['primary_metadata']['file'], metadata['folder_metadata']['folder']
    assert front['id'] == 'id:cnqzTNngPVsAAAAAAAykDg' and folder['id'] == 'id:cnqzTNngPVsAAAAAAAykDQ'
    solo = metadata['listings']['solo']
    assert len(solo['entries']) == 4 and not solo['has_more'] and not solo['cursor']
    family = metadata['family_listing']
    assert len(family['entries']) == 23 and not family['has_more'] and not family['cursor']
    receipts = read(HERE / 'download-receipts.json')
    assert {x['id'] for x in receipts} == {x['file_id'] for x in solo['entries']}
    for receipt in receipts:
        path = Path(receipt['local_path'])
        assert path.stat().st_size == receipt['size'] and sha(path) == receipt['sha256']
        chunks = []
        with path.open('rb') as stream:
            while block := stream.read(4194304):
                chunks.append(hashlib.sha256(block).digest())
        assert hashlib.sha256(b''.join(chunks)).hexdigest() == receipt['content_hash'] == receipt['dropbox_content_hash_verified']
    prior = HERE.parent / 'copper/identity-approval.json'
    approval = read(prior)
    assert approval['user_statement'] == 'Keep “Dune Ripple Spiral — Copper”'
    assert approval['identity_confirmed'] and not approval['specifications_approved']
    model_path = ROOT / 'components/evidence/component_register.json'
    model = read(model_path)
    component = next(x for x in model['components'] if x['component_id'] == 'BC-DR-SPIRAL')
    candidates = [x for x in model['platform_records'] if x['offer_ref'] in component['offer_refs']]
    assert len(candidates) == 5
    assert not any(x.get('image_folder_id') == folder['id'] for x in model['platform_records'])
    source = ROOT.parent / 'Boldstone_Wall_Sculptures_Matched_All_Fields_2026-10-15.xlsx'
    source_sha = sha(source)
    assert source_sha == '7e6911a88ea9c9fd3214bdf860e24d6ad72ee755302efd6a9acc4db85c52c5c9'
    book = openpyxl.load_workbook(source, read_only=True, data_only=True)
    searches = {}
    candidate_skus = {x['sku'] for x in candidates}
    for tab in ['SS Wall Products', 'SH Wall Products']:
        ws = book[tab]
        headers = [c.value for c in next(ws.iter_rows(min_row=5, max_row=5))]
        rows = []
        for number, values in enumerate(ws.iter_rows(min_row=6, values_only=True), start=6):
            fields = dict(zip(headers, values))
            sku = fields.get('SKU', fields.get('Variant SKU'))
            text = json.dumps(fields, default=str).lower()
            if sku in candidate_skus or 'partial verdigris' in text:
                rows.append({'row': number, 'sku': sku,
                    'platform_id': fields.get('Product ID [Non Editable]', fields.get('Handle')),
                    'title': fields.get('Title'), 'partial_verdigris_text_hit': 'partial verdigris' in text})
        searches[tab] = rows
    book.close()
    assert sha(source) == source_sha
    platform_check = {'status': 'PASS', 'checked_utc': now, 'source_workbook': str(source),
        'source_sha256': source_sha, 'model_sha256': sha(model_path), 'known_spiral_offer_candidates': candidates,
        'native_search': searches, 'exact_selected_finish_offer_confirmed': False,
        'no_existing_confirmed_binding_to_selected_folder': True,
        'scope': 'Read original exports and the five known DR2 source offers. Keyword absence does not prove catalogue absence. '
            'Prior Copper, pale Verdigris, speckled Verdigris/Copper, Rust and Gold evidence retain separate finish scopes. '
            'No exact listing/SKU binding is made for this selected reference; live accounts/public pages not refreshed.'}
    write('platform-candidate-check.json', platform_check)
    white = rel(HERE.parent / 'component-review.json')
    copper = rel(HERE.parent / 'copper/component-review.json')
    image_ref = rel(HERE / 'download-receipts.json')
    items = []

    def item(suffix, field, value, display, basis, sources):
        items.append({'proposal_id': VID + '-' + suffix, 'field': field, 'value': value,
            'display': display, 'status': 'UNAPPROVED WORKING GUESS; EXACT CAST UNVERIFIED',
            'basis': basis, 'source_refs': sources, 'owner_approved': False})

    item('DIMENSIONS', 'Individual dimensions and depth',
        {'proposed_dimensions_cm': [35, 21, 6], 'actual_measured_dimensions_cm': None},
        'Approximately 35 H × 21 W × 6 D cm — guess; unmeasured',
        'Related Copper source states 35 × 21 × 6 cm; white DR2 standard has a 35 × 20 cm face and 5–7 cm side depth. '
        'Use 35 × 21 × 6 cm only as a working proposal. Similar relief appearance does not establish equal size or the same mould/cast.',
        [copper, white, image_ref])
    item('WEIGHT', 'Individual dry weight',
        {'proposed_weight_kg': 4, 'working_estimate_range_kg': [3, 5], 'actual_weighed_kg': None},
        'Approximately 4 kg (working range 3–5 kg) — guess; not weighed',
        'Related white DR2 maker row 55 calculates 3–5 kg. This specimen’s binder, thickness and filling are unknown. '
        'No other version’s raw export weight is converted or inherited; no set weight is divided.',
        [white, 'manufacture-stevensons:Sheet1!row55; analogy only'])
    item('MATERIAL', 'Material and finish',
        {'proposed_substrate': 'Plaster and sand / cast mineral composite',
         'visual_finish': 'Copper-coloured surface with partial turquoise verdigris effect',
         'actual_binder': None, 'actual_copper_content': None, 'reinforcement': None, 'sealing': None},
        'Plaster and sand / cast mineral composite with copper and partial verdigris effect — guess',
        'Plaster and sand is an analogy to the related Copper source, not an exact claim for this reference. '
        'Four current originals show turquoise patches, copper-coloured relief and workshop surface-finishing views. '
        'They do not establish actual copper, chemical patination, binder, sealer or outdoor suitability.',
        [copper, image_ref])
    item('FIXING', 'Fixing',
        {'proposed_hanging_points': 1, 'proposed_type': 'Recessed rear keyhole hanger',
         'exact_rear_available': False, 'actual_hardware': None, 'attachment': None, 'rated_load': None},
        'One recessed rear keyhole fixing — guess; exact rear and hardware unconfirmed',
        'Related Copper listing shows one keyhole plate; white maker instruction also specifies a single rear fixing. '
        'No rear appears in this four-file folder. Do not transfer hardware grade, placement, orientation or load capacity.',
        [copper, white, image_ref])
    item('PRICE', 'Individual retail price',
        {'proposed_amount': 200, 'currency': 'GBP', 'sale_unit': 'One selected Copper/Partial Verdigris panel',
         'exact_existing_offer_confirmed': False, 'owner_price_approval': False, 'finish_costing_confirmed': False},
        '£200 per individual panel — working price guess; no exact offer or quote confirmed',
        'Discussion proposal uses the dated white DR2 £175 retail draft plus an uncosted £25 finish allowance. '
        'This is not a valuation or production costing. The separately matched Copper £40.33 source offer and pale Verdigris £45 offer are not transferred.',
        [white, rel(HERE.parent / 'verdigris-copper-speckled/component-review.json')])
    item('AVAILABILITY', 'Availability',
        {'proposed_sale_policy': 'Made to order individually / enquire', 'physical_stock_quantity': None,
         'manufacture_or_reproducibility_confirmed': False, 'production_capacity': None, 'lead_time': None},
        'Made to order individually / enquire — proposal; stock, reproducibility and lead time unknown',
        'Finished-front and workshop photographs do not establish current inventory or capacity. '
        'Made-to-order is a proposed sale policy requiring owner confirmation; no related offer’s stock setting is inherited.', [image_ref])
    evidence = sorted(set([p for p in HERE.iterdir() if p.is_file()] + [prior,
        HERE.parent / 'identity-approval.json', ROOT / white, ROOT / copper,
        HERE.parent / 'verdigris-copper-speckled/component-review.json', model_path, source]))
    write('source-audit.json', {'schema_version': 1, 'status': 'PASS', 'checked_utc': now,
        'complete_selected_folder_files': 4, 'current_originals_downloaded_hash_verified_and_visually_reviewed': 4,
        'complete_current_family_child_folders': 23, 'exact_platform_offer_confirmed': False,
        'physical_cast_or_specification_verification': False,
        'visual_findings': ['001 is a complete two-curl portrait panel on a pale stone wall, with copper-coloured raised areas and partial turquoise finish.',
            '002 and 003 are edge/relief workshop close-ups; 004 shows finishing in progress beside a brush and copper-coloured coating.',
            'No rear, room/garden context or multi-panel arrangement is present in these four files.',
            'No claim that these views, the earlier Copper reference or the speckled reference are distinct physical casts, stock units or moulds.'],
        'evidence_sha256': {str(p): sha(p) for p in evidence}, 'remote_files_changed': False})
    links = {x['file_name']: x['copy_link_url'] for x in metadata['previews']}
    write('component-review.json', {'schema_version': 1, 'prepared_utc': now, 'component_id': 'BC-DR-SPIRAL',
        'canonical_design_name': 'Dune Ripple Spiral — DR2',
        'proposed_name': 'Dune Ripple Spiral — Copper and Partial Verdigris',
        'display_name': 'Dune Ripple Spiral — Copper and Partial Verdigris', 'family': 'Dune Ripple', 'review_number': 37,
        'family_review_number': 11, 'family_review_total': 14, 'size_finish_variant_id': VID,
        'variant_only_review': True, 'review_decision_mode': 'SIZE_FINISH_VARIANT_NAME_AND_SPECIFICATIONS',
        'parent_identity_approval': rel(HERE.parent / 'identity-approval.json'), 'prior_variant_identity_approval': rel(prior),
        'parent_design_relationship_status': 'Separate depicted finish reference; relationship to Copper and speckled Verdigris/Copper may be finish stage, cast or photograph and remains unresolved',
        'scope': 'Selected individual Copper and Partial Verdigris depicted name/identity only; all six specification groups are proposals. No physical count inferred.',
        'primary_image_id': front['id'], 'primary_folder_id': folder['id'],
        'primary_image_link': links[front['id']], 'primary_folder_link': links[folder['id']],
        'metadata_checked_utc': metadata['checked_utc'], 'reference_refresh': rel(HERE / 'metadata-links.json'),
        'source_audit': rel(HERE / 'source-audit.json'), 'specification_review_items': items,
        'original_download_receipts': [image_ref],
        'platform_mapping': {'status': 'EXACT SQUARESPACE/SHOPIFY OFFER UNCONFIRMED',
            'squarespace_id': None, 'shopify_handle': None, 'shared_sku': None, 'exact_existing_offer_confirmed': False,
            'candidate_check': rel(HERE / 'platform-candidate-check.json'), 'primary_file_id': front['id'], 'primary_folder_id': folder['id'],
            'related_copper_offer': {'offer_ref': 'O052', 'sku': 'EBAY-188654831217',
                'scope': 'Other Copper reference already separately kept; no exact finish, physical cast, price, SKU or stock transfer'},
            'native_platform_accounts_or_public_pages_refreshed': False},
        'photo_coverage': {'complete_individual_front': True, 'detail_views_available': True,
            'wall_mounted_front_reference': True, 'workshop_finishing_views_available': True,
            'exact_rear_available': False, 'confirmed_room_garden_or_client_installation_for_selected_reference': False,
            'confirmed_series_reference_for_selected_finish': False, 'physical_stock_inferred': False,
            'scope': 'Fresh complete four-file folder census; all four current originals downloaded/hash verified/viewed. '
                'Current 23-child-folder family listing checked. Exact rear, room/garden setting and series image remain unassigned; '
                'this is a scoped gap, not an exhaustive absence claim across all Dropbox.'},
        'identity_confirmed': False, 'specifications_approved': False, 'physical_specs_verified': False,
        'open_gaps': ['Actual height, width, maximum depth and dry weight',
            'Actual binder, copper content, patination method, reinforcement, sealer, care and exterior suitability',
            'Exact rear, hardware attachment, grade, position, orientation and load capacity',
            'Exact individual platform offer and shared SKU',
            'Owner price, current physical stock, reproducibility, capacity and lead time',
            'Confirmed room/garden context and series image; relationship to earlier Copper and speckled references'],
        'source_conflicts': ['35 × 21 × 6 cm is an analogy proposal, not an exact listing claim for this finish.',
            'White DR2 standard and related Copper claims have separate material, weight and price scopes.',
            'A separate appearance card does not establish a separate physical sculpture or stock unit.'],
        'next_review_after_keep': {'component_id': 'BC-DR-SPIRAL', 'review_number': 37,
            'size_finish_variant_id': 'DR-SPIRAL-GOLD', 'family_review_number': 12,
            'requires_exact_design_allocation_check': True}, 'next_global_component_id': 'BC-DR-WAVE3',
        'remote_files_changed': False, 'live_platform_records_changed': False})
    print(json.dumps({'status': 'PASS', 'variant': VID, 'six_unapproved_groups': len(items), 'evidence_files_hashed': len(evidence)}))


if __name__ == '__main__':
    main()
