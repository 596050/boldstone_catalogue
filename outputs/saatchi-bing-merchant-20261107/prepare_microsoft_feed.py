"""Prepare a current, exact-scope Merchant Center text feed. No platform writes."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlsplit
import csv
import hashlib
import json
import re
import sys
import urllib.request

ROOT = Path('/Users/tprice/Documents/boldstone')
OUT = Path(__file__).parent
sys.path.insert(0, str(ROOT / 'catalogue-review'))
from channel_content import values, complete_description, marketplace_title, appearance

read = lambda name: json.loads((OUT / name).read_text())
app = read('app-specifications.json')
products = {p['id']: p for p in app['products']}
coverage = read('app-coverage.json')['products']
images = {im['id']: im for im in read('app-library.json')['images']}
public_images = read('microsoft-public-image-bindings.json')
scope = json.loads((ROOT / 'outputs/catalogue-marketplace-publication-20261101/current-prepared-catalogue.json').read_text())['records']
assert len(scope) == len({r['catalogue_id'] for r in scope}) == len({r['sku'] for r in scope}) == 176

def key(url):
    s = urlsplit(url)
    return s.netloc.lower(), s.path.replace('/content/v1/', '/content/')

def fetch_product(record):
    url = record['source_website_url']
    assert urlsplit(url).hostname == 'boldstonesculpture.com' and '/buy/p/' in urlsplit(url).path
    req = urllib.request.Request(url + '?format=json', headers={'User-Agent': 'Mozilla/5.0 (Boldstone read-only merchant-feed verification)', 'Accept': 'application/json'})
    result = {'catalogue_id': record['catalogue_id'], 'sku': record['sku'], 'url': url, 'checked_utc': datetime.now(timezone.utc).isoformat()}
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            raw = json.load(response)
        item = raw.get('item')
        assert item, 'Public product item absent'
        result.update(status='READ_PUBLIC_PRODUCT', native_product_id=item.get('id'), title=item.get('title'), workflow_state=item.get('workflowState'), variants=item.get('variants', []), image_urls=[im.get('assetUrl', '') for im in item.get('items', [])])
    except Exception as error:
        result.update(status='READ_FAILED', error_type=type(error).__name__)
    return result

readback_path = OUT / 'microsoft-public-product-readbacks.json'
if '--reuse-public-readbacks' in sys.argv:
    public = json.loads(readback_path.read_text())
    assert {(p['catalogue_id'], p['sku'], p['url']) for p in public} == {(r['catalogue_id'], r['sku'], r['source_website_url']) for r in scope}
else:
    public = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        pending = [pool.submit(fetch_product, r) for r in scope]
        for future in as_completed(pending):
            public.append(future.result())
            if len(public) % 44 == 0:
                print(f'Checked {len(public)} of 176 website product records', flush=True)
    readback_path.write_text(json.dumps(public, indent=2) + '\n')
public = {p['catalogue_id']: p for p in public}

headers = ['id', 'title', 'description', 'link', 'image_link', 'additional_image_link', 'price', 'availability', 'condition', 'brand', 'identifier_exists', 'product_type', 'color', 'material', 'custom_label_0']
rows, manifest, issues, missing_extra_images = [], [], [], []
for retained in scope:
    p = products[retained['catalogue_id']]
    f = values(p)
    c = coverage[p['id']]
    sku = f['Seller SKU']
    assert sku == retained['sku'] and p['listing_decision'] == 'include'
    price = Decimal(str(p['costing']['pricing']['marked_up_price'])).quantize(Decimal('.01'))
    assert price == Decimal(re.sub(r'[^0-9.]', '', f['Price'])) > 0
    primary = c['primary_listing']['image_id']
    assert c['primary_listing']['status'] == 'set' and primary in public_images
    ordered = list(dict.fromkeys([primary] + c['listing']['image_ids'] + c['in_situ']['image_ids']))
    available = []
    for aid in ordered:
        binding = public_images.get(aid)
        if not binding:
            missing_extra_images.append({'catalogue_id': p['id'], 'sku': sku, 'image_id': aid, 'name': images[aid]['name']})
            continue
        assert binding['hash'] == images[aid]['original']['dropbox_content_hash']
        assert urlsplit(binding['url']).scheme == 'https'
        available.append(aid)
    assert available[0] == primary
    website = public[p['id']]
    if website['status'] != 'READ_PUBLIC_PRODUCT':
        issues.append({'catalogue_id': p['id'], 'issue': 'WEBSITE_READ_FAILED', 'detail': website})
    else:
        matches = [v for v in website['variants'] if v.get('sku') == sku]
        if len(matches) != 1:
            issues.append({'catalogue_id': p['id'], 'issue': 'WEBSITE_SKU_MISMATCH'})
        else:
            v = matches[0]
            money = v['salePriceMoney'] if v.get('onSale') else v['priceMoney']
            if money.get('currency') != 'GBP' or Decimal(money['value']) != price:
                issues.append({'catalogue_id': p['id'], 'issue': 'WEBSITE_PRICE_MISMATCH', 'observed': money, 'expected_gbp': str(price)})
        if key(public_images[primary]['url']) not in {key(u) for u in website['image_urls']}:
            issues.append({'catalogue_id': p['id'], 'issue': 'PRIMARY_NOT_IN_CURRENT_WEBSITE_GALLERY'})
        if website['workflow_state'] != 1:
            issues.append({'catalogue_id': p['id'], 'issue': 'WEBSITE_PRODUCT_NOT_PUBLIC'})
    title = marketplace_title(p, limit=150)
    description = re.sub(r'\s+', ' ', complete_description(p, sku, dispatch_days=10)).strip()
    assert len(sku) <= 50 and len(title) <= 150 and len(description) <= 10000
    assert not re.search(r'\bGFRC\b|Royal Mail', description, re.I)
    assert 'gypsum-based material' in description and 'Sally Price' in description
    urls = [public_images[aid]['url'] for aid in available[:11]]
    row = [sku, title, description, retained['source_website_url'], urls[0], ','.join(urls[1:]), f'{price:.2f} GBP', 'in stock', 'new', 'Boldstone', 'FALSE', 'Wall Sculptures > ' + p['family'], appearance(p), 'Gypsum-based material', p['id']]
    assert len(row) == len(headers) and all('\t' not in cell and '\n' not in cell and '\r' not in cell for cell in row)
    rows.append(row)
    manifest.append({'catalogue_id': p['id'], 'sku': sku, 'title': title, 'price_gbp': str(price), 'website_url': retained['source_website_url'], 'native_website_product_id': website.get('native_product_id'), 'primary_image_id': primary, 'primary_content_hash': public_images[primary]['hash'], 'additional_images_submitted': len(urls)-1, 'selected_image_count': len(ordered), 'public_image_ids_used': available[:11]})

(OUT / 'microsoft-feed-validation-issues.json').write_text(json.dumps(issues, indent=2) + '\n')
(OUT / 'microsoft-missing-public-images.json').write_text(json.dumps(missing_extra_images, indent=2) + '\n')
assert not issues, f'{len(issues)} website checks need attention; inspect microsoft-feed-validation-issues.json before publishing'
target = OUT / 'boldstone_wall_sculptures_microsoft.txt'
with target.open('w', encoding='utf-8', newline='') as stream:
    writer = csv.writer(stream, delimiter='\t', lineterminator='\n')
    writer.writerow(headers)
    writer.writerows(rows)
with target.open(encoding='utf-8', newline='') as stream:
    reread = list(csv.reader(stream, delimiter='\t'))
assert reread == [headers] + rows and len(target.read_text().splitlines()) == 177
receipt = {
    'status': 'PREPARED_LOCAL_VALIDATION_PASSED_NOT_UPLOADED',
    'prepared_utc': datetime.now(timezone.utc).isoformat(),
    'country': 'GB', 'language': 'en', 'currency': 'GBP',
    'products': 176, 'unique_ids': 176,
    'source_app_revision': app['revision'],
    'file': str(target), 'sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
    'size': target.stat().st_size,
    'website_price_sku_and_primary_checks_passed': 176,
    'additional_images_included': sum(r['additional_images_submitted'] for r in manifest),
    'unmapped_additional_image_associations': len(missing_extra_images),
    'identifier_policy': 'No GTIN or manufacturer MPN recorded. identifier_exists FALSE for handmade products; no barcode or MPN invented.',
    'shipping_policy': 'No shipping cost or free-shipping claim introduced. GB sculpture feed shipping is optional in the Microsoft product schema. Native store settings and actual checkout charges still require review.',
    'image_policy': 'Current app primary and available exact-hash public images only. Additional image URLs are supplied for compatibility; Microsoft says it currently does not use those additional images.',
    'paid_campaigns_created': 0,
    'native_approval': 'Not checked; owner sign-in verification pending',
    'sources': ['https://learn.microsoft.com/en-us/advertising/shopping-content/products-resource', 'https://learn.microsoft.com/en-us/answers/questions/2289088/missing-brand-gtin-or-mpn-for-custom-products'],
    'records': manifest,
}
(OUT / 'microsoft-feed-manifest.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps({k: v for k, v in receipt.items() if k != 'records'}, indent=2))
