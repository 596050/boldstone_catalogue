import datetime, hashlib, html, json, re, urllib.error, urllib.parse, urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parent
RAW = OUT / 'raw-public'
BASE = OUT.parent
OLD = Path('/Users/tprice/Documents/boldstone/sculpture-catalogue/components/parallel-reviews/listing-reconciliation-2026-10-20/worker-01/SQUARESPACE_SOURCE_INVENTORY.json')

def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def save(name, value):
    path = OUT / name
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    return path

def fetch(url, label):
    RAW.mkdir(exist_ok=True)
    body_path = RAW / (label + '.body')
    receipt_path = RAW / (label + '.receipt.json')
    if receipt_path.exists():
        receipt = json.loads(receipt_path.read_text())
        assert digest(body_path) == receipt['sha256'], 'Existing raw bytes changed'
        try:
            data = json.loads(body_path.read_bytes())
        except Exception:
            data = None
        return data, receipt
    receipt = {'url': url, 'method': 'GET', 'request_utc': now(), 'authentication': 'none', 'cookies_supplied': False, 'timeout_seconds': 30}
    try:
        request = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (compatible; Boldstone catalogue evidence review)', 'Accept': 'application/json'})
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read()
            receipt.update(status=response.status, final_url=response.url, headers=dict(response.headers))
    except urllib.error.HTTPError as error:
        body = error.read()
        receipt.update(status=error.code, final_url=error.url, headers=dict(error.headers), error=str(error))
    except Exception as error:
        body = b''
        receipt.update(status=None, error_type=type(error).__name__, error=str(error))
    body_path.write_bytes(body)
    receipt.update(response_utc=now(), body_path=str(body_path), bytes=len(body), sha256=digest(body_path))
    try:
        data = json.loads(body)
        receipt.update(json_parse_success=True, json_type=type(data).__name__)
    except Exception as error:
        data = None
        receipt.update(json_parse_success=False, json_parse_error=type(error).__name__)
    receipt_path.write_text(json.dumps(receipt, indent=2) + '\n')
    return data, receipt

def locator(receipt, pointer):
    return {'path': receipt['body_path'], 'json_pointer': pointer, 'body_sha256': receipt['sha256'], 'request_url': receipt['url'], 'observed_utc': receipt['response_utc']}

def plain(value):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', value or ''))).strip()

def normalized(item, receipt, pointer):
    content = item.get('structuredContent') or {}
    source_key = 'body' if item.get('body') else 'excerpt'
    variant_key = '/structuredContent/variants' if content.get('variants') else '/variants'
    variants_raw = content.get('variants') or item.get('variants') or []
    variants = []
    for index, variant in enumerate(variants_raw):
        variants.append({
            'native_product_id': item.get('id'), 'native_variant_id': variant.get('id'), 'sku': variant.get('sku'),
            'option_attributes': variant.get('attributes'), 'option_values_in_source_order': variant.get('optionValues'),
            'price': {key: variant.get(key) for key in ['priceMoney', 'salePriceMoney', 'price', 'salePrice', 'onSale']},
            'stock_setting': {key: variant.get(key) for key in ['unlimited', 'qtyInStock']},
            'raw_dimensions_and_weight': {key: variant.get(key) for key in ['len', 'width', 'height', 'weight']},
            'units_not_inferred': True, 'native_image_ids': variant.get('imageIds'), 'native_images': variant.get('images'),
            'native_record': variant, 'source_locator': locator(receipt, pointer + variant_key + '/' + str(index))})
    timestamps = {}
    for key in ['addedOn', 'updatedOn', 'publishOn']:
        value = item.get(key)
        timestamps[key] = {'native_value': value, 'utc_from_epoch_milliseconds': datetime.datetime.fromtimestamp(value / 1000, datetime.timezone.utc).isoformat() if isinstance(value, (int, float)) else None}
    return {
        'platform': 'Squarespace', 'native_product_id': item.get('id'), 'title': item.get('title'),
        'url': urllib.parse.urljoin('https://boldstonesculpture.com', item.get('fullUrl') or ''),
        'description_html': item.get(source_key), 'description_text': plain(item.get(source_key)), 'description_source_field': source_key,
        'product_type_raw': content.get('productType', item.get('productType')), 'category_ids': item.get('categoryIds'), 'categories_raw': item.get('categories'), 'tags': item.get('tags'),
        'workflow_state_raw': item.get('workflowState'), 'collection_id': item.get('collectionId'), 'timestamps': timestamps,
        'variant_option_ordering': content.get('variantOptionOrdering'), 'product_level_price_money_raw': content.get('priceMoney'),
        'primary_asset_url': item.get('assetUrl'), 'native_media_items': item.get('items') or [], 'variants': variants,
        'public_collection_observed': True, 'source_state': 'FRESH_ANONYMOUS_PUBLIC_COLLECTION_OBSERVATION',
        'source_locator': locator(receipt, pointer), 'native_record': item,
        'stock_limit': 'Raw unlimited/qtyInStock are listing settings, not verified physical stock or checked checkout availability.',
        'identity_limit': 'Native listing/variant identity is distinct from design identity, exact finish/configuration identity and physical cast identity.'}

def capture():
    master = BASE / 'inputs/master-register.json'
    expected = '7760b44a4d52ff3b78c893d5b86ef174814b48c29f7e41814c8a01a42af5326d'
    assert digest(master) == expected
    gate = json.loads((BASE / 'FAKE_ADAPTER_GATE.json').read_text())
    assert gate['status'] == 'PASS' and gate['tests_passed'] == 74
    url = 'https://boldstonesculpture.com/buy?format=json'
    seen = set()
    pages = []
    products = []
    for index in range(21):
        assert url not in seen, 'Pagination loop'
        seen.add(url)
        label = 'collection-initial' if index == 0 else 'collection-page-' + format(index, '02d')
        data, receipt = fetch(url, label)
        page = {'page_index': index, 'source_locator': locator(receipt, ''), 'http_status': receipt.get('status')}
        if receipt.get('status') != 200 or not isinstance(data, dict):
            page['error'] = 'SUCCESSFUL_JSON_OBJECT_NOT_RETURNED'
            pages.append(page)
            break
        items = data.get('items') or []
        pagination = data.get('pagination') or {}
        page.update(item_count=len(items), native_product_ids=[item.get('id') for item in items], pagination=pagination, collection_claimed_item_count=(data.get('collection') or {}).get('itemCount'))
        pages.append(page)
        products.extend(normalized(item, receipt, '/items/' + str(j)) for j, item in enumerate(items))
        if not pagination.get('nextPage') or not pagination.get('nextPageUrl'):
            break
        parsed = urllib.parse.urlparse(urllib.parse.urljoin(url, pagination['nextPageUrl']))
        assert parsed.scheme == 'https' and parsed.netloc == 'boldstonesculpture.com'
        query = [(k, v) for k, v in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True) if k != 'format'] + [('format', 'json')]
        url = urllib.parse.urlunparse(parsed._replace(query=urllib.parse.urlencode(query)))
    ids = [p['native_product_id'] for p in products]
    pagination_receipt = {'schema': 'boldstone.squarespace-public-pagination.v2', 'created_utc': now(), 'pages': pages, 'received_item_count': len(ids), 'unique_product_count': len(set(ids)), 'duplicate_returned_ids': sorted({i for i in ids if ids.count(i) > 1}), 'terminal_no_next_link': bool(pages and not (pages[-1].get('pagination') or {}).get('nextPageUrl')), 'account_authenticated': False, 'account_hidden_draft_completeness_verified': False}
    pagination_path = save('PUBLIC_PAGINATION.json', pagination_receipt)
    result = {
        'schema': 'boldstone.squarespace-fresh-public-native-inventory.v2', 'created_utc': now(),
        'frozen_master': {'path': str(master), 'sha256': expected}, 'fake_adapter_gate': {'path': str(BASE / 'FAKE_ADAPTER_GATE.json'), 'sha256': digest(BASE / 'FAKE_ADAPTER_GATE.json'), 'reported': gate},
        'scope': 'One anonymous official public /buy collection pagination chain; all products and variants returned, no account/admin/draft/hidden completeness claim.',
        'pagination_receipt': str(pagination_path), 'counts': {'returned_product_rows': len(products), 'unique_product_ids': len(set(ids)), 'variant_rows': sum(len(p['variants']) for p in products), 'unique_variant_ids': len({v['native_variant_id'] for p in products for v in p['variants']})},
        'limits': ['Server itemCount and returned pagination count must be assessed separately.', 'Public collection absence does not establish account deletion or global absence.', 'Descriptions are source claims, not measured facts.', 'PriceMoney is retained per variant; product-level price zero is not substituted for variant price.', 'Stock settings are not physical stock counts.', 'No remote writes or Dropbox calls.'],
        'historical_inventory': {'path': str(OLD), 'sha256': digest(OLD), 'state': 'SEALED_2026_10_20_SOURCE_ONLY_DO_NOT_REDATE'},
        'products': products}
    output = save('FRESH_PUBLIC_INVENTORY.json', result)
    save('SCHEMA_SAMPLE.json', {'schema': result['schema'], 'counts': result['counts'], 'product_keys': list(products[0]) if products else [], 'variant_keys': list(products[0]['variants'][0]) if products and products[0]['variants'] else [], 'inventory_path': str(output), 'inventory_sha256': digest(output), 'description_locator_rule': 'products[].source_locator + /description_source_field; native_record contains exact parsed JSON object.', 'raw_bytes_rule': 'Use source_locator.path/json_pointer/body_sha256; original raw bytes are preserved unmodified.'})
    print(json.dumps({'path': str(output), 'sha256': digest(output), 'counts': result['counts'], 'pagination': pagination_receipt}, indent=2))

if __name__ == '__main__':
    capture()
