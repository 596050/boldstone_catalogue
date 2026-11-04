"""Read public Wescover product pages without downloading photographs.

Uses the previously verified native-item manifest. No browser/session access,
account mutations, or conclusions about private drafts or unpublished products.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
from urllib.error import HTTPError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]


class PublicData(HTMLParser):
    def __init__(self):
        super().__init__()
        self.active = False
        self.buffer = ''
        self.structured = []
        self.links = set()
        self.canonical = None

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if tag == 'script' and attrs.get('type') == 'application/ld+json':
            self.active, self.buffer = True, ''
        if tag == 'a' and attrs.get('href', '').startswith('/p/'):
            self.links.add(urljoin('https://www.wescover.com', attrs['href']))
        if tag == 'link' and attrs.get('rel') == 'canonical':
            self.canonical = attrs.get('href')

    def handle_data(self, text):
        if self.active:
            self.buffer += text

    def handle_endtag(self, tag):
        if tag == 'script' and self.active:
            self.active = False
            self.structured.append(json.loads(self.buffer))


def fetch(url):
    if urlparse(url).hostname != 'www.wescover.com':
        raise ValueError('Unexpected public source host')
    at = datetime.now(timezone.utc).isoformat()
    try:
        with urlopen(Request(url, headers={'User-Agent': 'Boldstone public catalogue audit'}), timeout=25) as response:
            document = response.read(3_000_001)
            if len(document) > 3_000_000:
                raise ValueError('Public document exceeds audit limit')
            parser = PublicData()
            parser.feed(document.decode('utf-8', 'replace'))
            return {'checked_utc': at, 'requested_url': url, 'resolved_url': response.url,
                    'http_status': response.status, 'canonical_url': parser.canonical,
                    'structured_data': parser.structured, 'visible_product_links': sorted(parser.links)}
    except HTTPError as error:
        return {'checked_utc': at, 'requested_url': url, 'http_status': error.code,
                'status': 'READ_FAILED_NOT_PROOF_OF_ABSENCE'}
    except Exception as error:
        return {'checked_utc': at, 'requested_url': url,
                'status': 'READ_FAILED_NOT_PROOF_OF_ABSENCE', 'error_class': type(error).__name__}


def main(out):
    out.mkdir(parents=True, exist_ok=True)
    source = json.loads((ROOT/'outputs/catalogue-marketplace-publication-20261101/wescover-current/public-176-final-audit.json').read_text())
    bindings = source['records']
    assert len(bindings) == len({r['sku'] for r in bindings}) == len({r['native_item_id'] for r in bindings}) == 176
    with urlopen('http://127.0.0.1:8767/api/specifications', timeout=25) as response:
        app = json.load(response)
    (out/'app-current.json').write_text(json.dumps(app, ensure_ascii=False, indent=2)+'\n')
    by_sku = {}
    for p in app['products']:
        fields = {f['key']: f['value'] for f in p['fields']+p['listing_fields']}
        by_sku[fields['Seller SKU']] = p
    result = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        pending = {pool.submit(fetch, r['url']): r for r in bindings}
        for future in as_completed(pending):
            binding = pending[future]
            row = {**binding, **future.result()}
            product = next((r for r in row.get('structured_data', []) if isinstance(r, dict) and r.get('@type') == 'Product'), None)
            row['product_schema_found'] = product is not None
            if product:
                text = product.get('description', '')
                row['native_id_matches'] = product.get('sku') == binding['native_item_id']
                row['catalogue_sku_in_description'] = bool(re.search(r'\('+re.escape(binding['sku'])+r'\)', text))
                row['brand_matches'] = product.get('brand', {}).get('name') == 'Boldstone'
                row['current_app_id'] = by_sku.get(binding['sku'], {}).get('id')
                row['status'] = ('PUBLIC_PRODUCT_MATCHED' if row['native_id_matches'] and row['catalogue_sku_in_description'] and row['brand_matches'] else 'IDENTITY_REVIEW_REQUIRED')
            result.append(row)
            if len(result) % 16 == 0 or len(result) == len(bindings):
                (out/'wescover-public-readbacks.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
                print(f'Checked {len(result)} of {len(bindings)} Wescover public products', flush=True)
    profile = fetch('https://www.wescover.com/creator/boldstone')
    (out/'wescover-profile-readback.json').write_text(json.dumps(profile, ensure_ascii=False, indent=2)+'\n')
    matched = {r['sku'] for r in result if r['status'] == 'PUBLIC_PRODUCT_MATCHED'}
    included = {sku: p for sku, p in by_sku.items() if p['listing_decision'] == 'include'}
    extra = [{'id': p['id'], 'sku': sku, 'name': p['name'], 'notes': p.get('notes', ''),
              'listing_photos': p['photos']['listing']['count'], 'status': 'NOT_IN_PREVIOUS_176_MANIFEST_RECONCILE_NATIVE_DRAFTS_BEFORE_CREATE'}
             for sku, p in included.items() if sku not in {r['sku'] for r in bindings}]
    summary = {'checked_utc': datetime.now(timezone.utc).isoformat(), 'public_products_checked': len(result),
               'matched_current_products': len(matched), 'read_or_identity_exceptions': [r['sku'] for r in result if r['status'] != 'PUBLIC_PRODUCT_MATCHED'],
               'included_app_records': len(included), 'additional_included_app_records': extra,
               'native_creations': 0, 'anonymous_public_readback': True,
               'scope': 'Previously verified product URLs and public schema. Private drafts and current creator completeness require native account inspection.'}
    (out/'wescover-summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main(Path(sys.argv[1]).resolve())
