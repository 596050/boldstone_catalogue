"""Preserve maker, dated price and exact-photo scope without promoting physical specifications."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
MAKER = Path('/Users/tprice/Library/Application Support/BoldstoneImageConsistency/product-evidence-resolution-20261016T201618Z')
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
rel = lambda p: str(p.relative_to(ROOT))


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def main():
    assert not (HERE / 'maker-source-reference.json').exists()
    now = datetime.now(timezone.utc).isoformat()
    initial = read(HERE / 'initial-metadata-and-listings.json')
    head = next(x['result']['file'] for x in initial['metadata'] if x['requested_id'] == 'id:cnqzTNngPVsAAAAAAAuDJA')
    receipt_path = MAKER / 'documents/manufacture-stevensons.receipt.json'
    receipt = read(receipt_path)
    source = Path(receipt['local_path'])
    assert head['id'] == receipt['head']['id'] and head['rev'] == receipt['head']['rev']
    assert source.stat().st_size == receipt['fingerprint']['size'] == head['size']
    assert sha(source) == receipt['fingerprint']['backup_sha256']
    raw = source.read_bytes()
    assert hashlib.sha256(b''.join(hashlib.sha256(raw[i:i+4194304]).digest() for i in range(0,len(raw),4194304))).hexdigest() == receipt['fingerprint']['content_hash']
    row_path, labels_path = MAKER / 'Manufacturing_Sheet_Extract.json', MAKER / 'Manufacturing_Labelled_References.json'
    rows = [x for x in read(row_path) if x['row'] in [39,41,42,43,44]]
    labels = [x for x in read(labels_path) if x['code'] in ['MCP1-25x25','MCP2-25x25','MCP3-25x25','MCP4-25x25']]
    assert len(rows) == 5 and len(labels) == 4
    write(HERE / 'maker-source-reference.json', {'checked_utc': now, 'source_file_id': head['id'], 'source_rev': head['rev'],
        'source_local_path': str(source), 'source_sha256': sha(source), 'source_receipt': str(receipt_path),
        'source_receipt_sha256': sha(receipt_path), 'extracted_rows': rows, 'labelled_reference_images': labels,
        'cached_extract_sha256': {str(row_path):sha(row_path),str(labels_path):sha(labels_path)},
        'labelled_image_sha256': {x['picture']['preview']:sha(Path(x['picture']['preview'])) for x in labels},
        'scope': 'Historical White standard, four labelled designs and per-component instructions. No current usable mould inventory, cast measurements, binder, mass or hardware certification.'})
    prices = read(HERE / 'local-price-source-check.json')
    for doc in prices['documents']:
        assert sha(Path(doc['source_path'])) == doc['sha256']
    write(HERE / 'dated-price-source-scope.json', {'checked_utc': now, 'raw_source_check': rel(HERE / 'local-price-source-check.json'),
        'rendered_pages_viewed': [rel(HERE/name) for name in ['retail-2025-page1.png','trade-2025-page1.png','t-price-2025-page1.png']],
        'retail_2025_White': {'each_face_cm':[25,25], 'estimated_weight_kg_each':5, 'retail_price_gbp_each':156.25},
        'trade_2025_White': {'each_face_cm':[25,25], 'estimated_weight_kg_each':4, 'trade_price_gbp_each':78,
            'quartet_price_gbp':312, 'component_price_source':'Explicit numbered individual rows; not divided from set price.'},
        'illustrative_White_trade': {'each_face_cm':[25,25], 'estimated_weight_kg_each':4, 'trade_price_gbp_each':78},
        'estimated_T_draft': {'estimated_weight_kg_each':4, 'stacked_GBP_values':[130.84,78,62], 'individual_stack_roles_confirmed':False},
        'scope': 'Different dated White price classes/versions remain separate. No current quote, price adoption, actual weighing or coloured-finish applicability inferred.'})
    model = read(ROOT / 'components/evidence/component_register.json')
    write(HERE / 'source-platform-and-component-records.json', {'checked_utc':now,
        'model_sha256':sha(ROOT / 'components/evidence/component_register.json'),
        'components':[x for x in model['components'] if x['component_id'] in ['BC-MCP-1','BC-MCP-2','BC-MCP-3','BC-MCP-4']],
        'related_coloured_offer_candidate':next(x for x in model['platform_records'] if x['offer_ref']=='O007'),
        'scope':'O007 is Squarespace-only related coloured offer evidence with unresolved exact photograph binding; no White SKU/price or shared Shopify counterpart is confirmed.'})
    write(HERE / 'component-position-observations.json', {'checked_utc':now,
        'MCP1_White':{'primary_clean_reference_id':'id:cnqzTNngPVsAAAAAAAylPQ',
            'original_closeup_id':'id:cnqzTNngPVsAAAAAAAuX6g','maker_code':'MCP1-25x25','maker_row':41,
            'numbered_trade_reference':'Owner Trade2025p1, individual row labelled1',
            'geometry':'Rounded central convex form with a surrounding circular raised/recessed collar and broad lower rim.',
            'series_file_id':'id:cnqzTNngPVsAAAAAAAugDQ','series_position':'Top left in this exact original square quartet photograph',
            'exhibition_file_id':'id:cnqzTNngPVsAAAAAAA512A','exhibition_position':'Top left in this exact exhibition quartet photograph',
            'original_exact_surface_or_cast_equivalence_of_clean_reference_confirmed':False},
        'related_Verdigris_Rust_rear_candidate':{'file_id':'id:cnqzTNngPVsAAAAAAAygbg',
            'visible_feature':'One small rectangular keyhole-like metal plate near centre of upper back',
            'front_back_pairing_confirmed':False,'actual_alloy_or_load_rating_confirmed':False,'applied_to_White':False},
        'unresolved_renditions':{'folder_id':'id:cnqzTNngPVsAAAAAAAyiow','file_numbers':['015','016','017'],
            'scope':'Do not force all four component identities onto clean quartet renditions; editing lineage and remaining per-member geometry comparisons pending.'},
        'Rust_quartet':{'folder_id':'id:cnqzTNngPVsAAAAAAAyiqA','reference_file_id':'id:cnqzTNngPVsAAAAAAAsSaw',
            'MCP1_exact_position_verified':False,'status':'Per-member Rust attribution remains queued; not a confirmed isolated MCP1Rust offer.'},
        'scope':'Positions refer to exact photographs only. Four historical labelled designs are not a current cast/mould count.'})
    census = read(HERE / 'media-census.json')
    reviewed_paths={x['path'] for x in census['listings'][1:]}
    write(HERE / 'media-scope-and-pending.json', {'checked_utc':now,'catalogue_family':'Moon Crater Phase',
        'root_child_folders':20,'MCP1_related_folders_inspected':5,'MCP1_related_files_inspected':69,
        'remaining_root_folders_not_inspected_in_this_pass':[x for x in census['listings'][0]['result']['entries'] if x['path'] not in reviewed_paths],
        'pending_arrangement_component_identification':{'folder_id':'id:cnqzTNngPVsAAAAAAAyiqA',
            'component_ids':['BC-MCP-1','BC-MCP-2','BC-MCP-3','BC-MCP-4'], 'exact_per_position_order_confirmed':False},
        'scope':'Two known individual MCP1finish-reference reviews are White and Verdigris/Rust. Rust arrangement attribution is separate unfinished work. Other MCPdesign/finish folders remain for later incremental reviews.'})
    print(json.dumps({'status':'PASS','maker_rows':len(rows),'labelled_design_images':len(labels),
        'White_weight_sources_kg':['2–4 maker','4 dated trade','5 dated retail'],
        'MCP1_exact_White_series_position':'027 top left','Rust_member_positions_still_pending':True}))


if __name__ == '__main__':
    main()
