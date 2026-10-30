import json, urllib.parse
from capture_public_inventory import OUT, BASE, OLD, digest, fetch, locator, normalized, now, save

WANTED = ['O051', 'O067', 'O004', 'O038', 'O015', 'O059', 'O002', 'O039', 'O003', 'O064']

def capture():
    master = json.loads((BASE / 'inputs/master-register.json').read_text())
    inventory = json.loads((OUT / 'FRESH_PUBLIC_INVENTORY.json').read_text())
    historical = json.loads(OLD.read_text())
    by = {p['native_product_id']: p for p in inventory['products']}
    old_by = {p['native_product_id']: p for p in historical['products']}
    records = []
    for offer_ref in WANTED:
        edge_index, edge = next((i, e) for i, e in enumerate(master['source_offer_edges']) if e['offer_ref'] == offer_ref)
        coverage_index, coverage = next((i, e) for i, e in enumerate(master['source_platform_offer_coverage']) if e['offer_ref'] == offer_ref)
        source = edge['source_offer']
        native_id = source['sq_id']
        record = {'offer_ref': offer_ref, 'native_product_id': native_id, 'frozen_master_source_offer': source,
            'frozen_master_source_locator': {'path': str(BASE / 'inputs/master-register.json'), 'json_pointer': '/source_offer_edges/' + str(edge_index), 'sha256': digest(BASE / 'inputs/master-register.json')},
            'frozen_master_coverage': coverage, 'frozen_master_coverage_locator': {'path': str(BASE / 'inputs/master-register.json'), 'json_pointer': '/source_platform_offer_coverage/' + str(coverage_index), 'sha256': digest(BASE / 'inputs/master-register.json')},
            'current_primary_reference': edge.get('current_primary_reference'), 'fresh_collection_product': by.get(native_id),
            'sealed_2026_10_20_product': old_by.get(native_id), 'historical_inventory_sha256': digest(OLD)}
        url = source['source_url']
        parsed = urllib.parse.urlparse(url)
        query = [(k, v) for k, v in urllib.parse.parse_qsl(parsed.query) if k != 'format'] + [('format', 'json')]
        url = urllib.parse.urlunparse(parsed._replace(query=urllib.parse.urlencode(query)))
        data, receipt = fetch(url, 'product-' + offer_ref + '-' + native_id)
        detail = None
        if receipt.get('status') == 200 and isinstance(data, dict):
            item = data.get('item')
            if isinstance(item, dict):
                detail = normalized(item, receipt, '/item')
                detail['public_collection_observed'] = False
                detail['source_state'] = 'FRESH_ANONYMOUS_PUBLIC_PRODUCT_OBSERVATION'
        record['direct_product_check'] = {'receipt': receipt, 'top_level_keys': list(data) if isinstance(data, dict) else None, 'detail_product': detail,
            'requested_native_id_matches': detail.get('native_product_id') == native_id if detail else None,
            'limit': 'HTTP response establishes this canonical URL state at capture time, not authenticated account deletion/hidden inventory state.'}
        records.append(record)
        print(json.dumps({'offer_ref': offer_ref, 'native_product_id': native_id, 'title': source['title'], 'current_status': receipt.get('status'), 'detail_id': detail.get('native_product_id') if detail else None, 'collection_present': native_id in by}), flush=True)
    result = {'schema': 'boldstone.listing-overlap-case-source-records.v1', 'created_utc': now(), 'offer_refs': WANTED, 'case_source_records': records, 'remote_writes': 0}
    save('CASE_SOURCE_RECORDS.json', result)
    print(json.dumps({'path': str(OUT / 'CASE_SOURCE_RECORDS.json'), 'sha256': digest(OUT / 'CASE_SOURCE_RECORDS.json')}))

if __name__ == '__main__':
    capture()
