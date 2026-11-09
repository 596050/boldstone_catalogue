"""Read-only audit of the public Pinterest CSV, product pages and image headers.

No browser cookies, authentication or image files are used. Image bodies are
stopped as soon as a size header is decoded, with a 256 KiB hard cap.
"""
import concurrent.futures
import csv
import hashlib
import html
import io
import json
import re
import sys
from decimal import Decimal
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from PIL import ImageFile

OUT = Path(__file__).parent
FEED = 'https://docs.google.com/spreadsheets/d/1PVhR1H-GFaojV_G7Khh0Vt3IwFL1RBHyLLzvXGIT-BQ/export?format=csv'
HEADERS = {'User-Agent': 'BoldstoneCatalogueAudit/1.0'}

def normalize_comparisons(result):
    # Squarespace appends its site name to the Product.name in JSON-LD.
    title = html.unescape(result.get('structured_product', {}).get('name', ''))
    title = re.sub(r'\s+[—–-]\s+boldstone$', '', title, flags=re.I)
    result['landing_product_title_without_site_suffix'] = title
    result['exact_title_match'] = title == result['title']
    amount, currency = result['feed_price'].split()
    result['price_currency_match'] = any(
        Decimal(str(o.get('price', '-1'))) == Decimal(amount) and o.get('priceCurrency') == currency
        for o in result.get('offers', []))

def write_result(products, results, status, raw):
    summary = dict(checked_utc=datetime.now(timezone.utc).isoformat(), products=len(products),
                   feed_http=status, feed_sha256=hashlib.sha256(raw).hexdigest(),
                   page_errors=sum('page_error' in r for r in results),
                   image_errors=sum('image_error' in r for r in results),
                   structured_products=sum(bool(r.get('structured_product')) for r in results),
                   title_mismatches=sum(r.get('exact_title_match') is False for r in results),
                   price_mismatches=sum(r.get('price_currency_match') is False for r in results),
                   stock_mismatches=sum(r.get('stock_match') is False for r in results),
                   images_below_documented_size=sum(r.get('image',{}).get('meets_pinterest_documented_1000x1500') is False for r in results),
                   images_size_unresolved=sum(r.get('image',{}).get('status') == 'SIZE_UNRESOLVED' for r in results),
                   qualification='Documented image-size check and observed discrepancies; not a Pinterest diagnosis or approval result')
    (OUT/'pinterest-public-audit.json').write_text(json.dumps(dict(summary=summary, products=results), indent=2)+'\n')
    print(json.dumps(summary, indent=2))

def read_url(url, cap=6_000_000):
    with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=35) as r:
        b = r.read(cap + 1)
        if len(b) > cap:
            raise ValueError('Response exceeded bounded read')
        return r.status, r.url, b

def image_size(url):
    parser = ImageFile.Parser()
    consumed = 0
    with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=35) as r:
        content_type = r.headers.get('Content-Type')
        while consumed < 262144:
            chunk = r.read(min(4096, 262144-consumed))
            if not chunk:
                break
            consumed += len(chunk)
            parser.feed(chunk)
            if parser.image:
                return dict(status=r.status, width=parser.image.width,
                            height=parser.image.height, bytes_read=consumed,
                            content_type=content_type,
                            meets_pinterest_documented_1000x1500=(parser.image.width >= 1000 and parser.image.height >= 1500))
    return dict(status='SIZE_UNRESOLVED', bytes_read=consumed)

def audit_product(p):
    result = dict(id=p['id'], title=p['title'], link=p['link'],
                  image_link=p['image_link'], feed_price=p['price'],
                  feed_availability=p['availability'])
    try:
        status, final, body = read_url(p['link'])
        source = body.decode('utf-8')
        schemas = []
        for raw in re.findall(r'<script[^>]*type=[\"\']application/ld\+json[\"\'][^>]*>(.*?)</script>', source, re.S | re.I):
            try:
                parsed = json.loads(raw)
                schemas.extend(parsed if isinstance(parsed, list) else [parsed])
            except json.JSONDecodeError:
                pass
        product = next((x for x in schemas if x.get('@type') == 'Product'), None)
        if product is None:
            for x in schemas:
                product = next((y for y in x.get('@graph', []) if y.get('@type') == 'Product'), None)
                if product:
                    break
        result.update(http_status=status, final_url=final, html_sha256=hashlib.sha256(body).hexdigest(),
                      structured_product=product)
        if product:
            result['landing_title'] = product.get('name')
            result['exact_title_match'] = html.unescape(product.get('name', '')) == p['title']
            offers = product.get('offers', [])
            offers = offers if isinstance(offers, list) else [offers]
            result['offers'] = [{k:o.get(k) for k in ['price','priceCurrency','availability','sku']} for o in offers]
            amount, currency = p['price'].split()
            result['price_currency_match'] = any(str(o.get('price')) == amount and o.get('priceCurrency') == currency for o in offers)
            result['stock_match'] = any(('InStock' in str(o.get('availability'))) == (p['availability'] == 'in stock') for o in offers)
    except Exception as e:
        result['page_error'] = type(e).__name__ + ': ' + str(e)
    try:
        result['image'] = image_size(p['image_link'])
    except Exception as e:
        result['image_error'] = type(e).__name__ + ': ' + str(e)
    return result

if __name__ == '__main__':
    status, final, raw = read_url(FEED)
    products = list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
    if '--reconcile' in sys.argv:
        existing = json.loads((OUT/'pinterest-public-audit.json').read_text())
        results = existing['products']
        previous = json.loads((OUT/'pinterest-public-feed.json').read_text())
        assert previous == products, 'Public feed changed during the check'
        def reconcile(r):
            normalize_comparisons(r)
            if r['image']['status'] == 'SIZE_UNRESOLVED':
                try:
                    r['image'] = image_size(r['image_link'])
                except Exception as e:
                    r['image_error'] = type(e).__name__ + ': ' + str(e)
            return r
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(reconcile, results))
        write_result(products, results, status, raw)
        sys.exit(0)
    assert len(products) == 176
    assert len({p['id'] for p in products}) == len(products)
    required = ['id','title','description','link','image_link','price','availability']
    missing = [{k:p['id'] for k in required if not p.get(k)} for p in products]
    assert not any(missing)
    (OUT/'pinterest-public-feed.json').write_text(json.dumps(products, indent=2)+'\n')
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for r in pool.map(audit_product, products):
            results.append(r)
            if len(results) % 25 == 0:
                print(json.dumps({'checked':len(results)}), flush=True)
    for result in results:
        normalize_comparisons(result)
    write_result(products, results, status, raw)
