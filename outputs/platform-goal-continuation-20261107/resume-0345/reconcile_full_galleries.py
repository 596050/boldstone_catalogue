"""Reconcile native draft sources against complete app photo selections.

The /api/specifications image arrays are card previews, capped at six.
Use coverage image_ids and full component-overview records instead.
This script is read-only with respect to the app and all marketplaces.
"""
import hashlib
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from urllib.request import urlopen

ROOT = Path('/Users/tprice/Documents/boldstone')
OUT = Path(__file__).parent
BASE = 'http://127.0.0.1:8767'

def get(path):
    with urlopen(BASE + path, timeout=90) as response:
        assert response.status == 200
        return json.load(response)

def save(name, data):
    (OUT / name).write_text(json.dumps(data, indent=2) + '\n')

before = get('/api/specifications')
coverage = get('/api/coverage')
save('app-specifications.json', before)
save('app-coverage.json', coverage)
products = {p['id']: p for p in before['products']}
targets = json.loads((ROOT / 'outputs/catalogue-marketplace-publication-20261101/catalogue-copy-disclosures/ebay-sapr-66-draft-targets.json').read_text())

def fetch_target(target):
    pid = target['source']['catalogue_id']
    detail = get('/api/component-overview/' + pid)
    assert detail['product']['id'] == pid
    return pid, detail

with ThreadPoolExecutor(max_workers=3) as pool:
    details = dict(pool.map(fetch_target, targets))
save('full-component-details.json', details)
after = get('/api/specifications')
assert before['revision'] == after['revision'], 'App changed while reading full selections'

pointer = json.loads((ROOT / 'sculpture-catalogue/current-master.json').read_text())['current_app_review_workbook']
workbook = Path(pointer['path'])
assert hashlib.sha256(workbook.read_bytes()).hexdigest() == pointer['sha256']
sys.path.insert(0, str(ROOT / 'catalogue-review/scripts'))
from import_saatchi_snapshot import Xlsx
book = Xlsx(workbook)
import re
headers = {book.value('Wall Sculptures', c): re.sub(r'\d+', '', c)
           for c in book.cells['Wall Sculptures'] if re.fullmatch(r'[A-Z]+7', c) and book.value('Wall Sculptures', c)}
rows = {str(book.value('Wall Sculptures', 'AQ' + str(row))): row for row in range(8, 189)}
records = []
for target in targets:
    sku = target['sku']
    pid = target['source']['catalogue_id']
    detail, cover, preview = details[pid], coverage['products'][pid], products[pid]['photos']
    assert not cover['excluded']
    assert detail['primary_listing']['status'] == 'set'
    primary = detail['primary_listing']['image_id']
    assert primary == cover['primary_listing']['image_id']
    listing = cover['listing']['image_ids']
    situ = cover['in_situ']['image_ids']
    assert len(listing) == cover['listing']['count'] == preview['listing']['count']
    assert len(situ) == cover['in_situ']['count'] == preview['in_situ']['count']
    assert listing == detail['listing_ids'], 'Full listing order differs'
    images = {i['id']: i for i in detail['images']}
    assert primary in listing and images[primary]['primary_eligible']
    selected = list(dict.fromkeys([primary] + listing + situ))
    withheld = {aid: images[aid]['withheld_reasons'] for aid in selected if images[aid]['withheld_reasons']}
    assert not withheld, ('Current selected photo needs review', sku, withheld)
    assert all(images[aid]['source'] == 'Dropbox' and images[aid]['original'].get('dropbox_content_hash') for aid in selected)
    expected = selected[:24]
    old = target['source']['photos'][:24]
    old_ids = [i['id'] for i in old]
    changed_hashes = [i['id'] for i in old if i['id'] in images and images[i['id']]['original'].get('dropbox_content_hash') != i['content_hash']]
    difference = ('selection_changed' if set(old_ids) != set(expected) else
                  'primary_changed' if old_ids[0] != expected[0] else
                  'content_changed' if changed_hashes else
                  'order_only' if old_ids != expected else 'unchanged')
    row = rows[sku]
    value = lambda name: book.value('Wall Sculptures', headers[name] + str(row))
    assert value('Product ID') == pid
    description = value('ebay_description').replace('Within 10 working days.', 'Within 3 working days.')
    url = target['links'][0]['href']
    query = parse_qs(urlparse(url).query)
    draft_id = (query.get('draft_id') or query.get('draftId'))[0]
    packet = dict(catalogue_id=pid, sku=sku, native_draft_id=draft_id, native_url=url,
                  title=value('ebay_catalogue_title'), description=description,
                  price_gbp=value('ebay_price_gbp'), width_cm=value('ebay_width_cm'),
                  height_cm=value('ebay_height_cm'), depth_cm=value('ebay_depth_cm'),
                  desired_gallery_ids=expected, selected_photos_over_24=max(0, len(selected)-24),
                  source_app_revision=before['revision'], source_workbook_sha256=pointer['sha256'],
                  publication_authorized_by_this_plan=False, owner_existing_offer_hold=sku=='EBAY-188654392024')
    assert packet['title'] and len(packet['title']) <= 80
    assert all(isinstance(packet[k], (int,float)) and packet[k] > 0 for k in ['price_gbp','width_cm','height_cm','depth_cm'])
    records.append(dict(**packet, listing_count=len(listing), in_situ_count=len(situ),
                        preview_listing_images=len(preview['listing']['images']),
                        preview_situ_images=len(preview['in_situ']['images']),
                        historical_gallery_ids=old_ids, difference_kind=difference,
                        changed_content_hashes=changed_hashes,
                        image_sources=[images[aid] for aid in expected]))
counts = {kind: sum(r['difference_kind']==kind for r in records)
          for kind in ['unchanged','order_only','selection_changed','primary_changed','content_changed']}
result = dict(status='PASS_FULL_SELECTION_IDS_AND_COUNTS', checked_utc=datetime.now(timezone.utc).isoformat(),
              source_app_revision=before['revision'], source_workbook_sha256=pointer['sha256'],
              records=records, difference_counts=counts,
              preview_truncated_products=sum(r['listing_count']>r['preview_listing_images'] or r['in_situ_count']>r['preview_situ_images'] for r in records),
              scope='Full coverage IDs and component originals; no app or native writes. Earlier preview-derived gallery conclusions are superseded.')
save('full-gallery-reconciliation.json', result)
print(json.dumps({k:v for k,v in result.items() if k!='records'},indent=2))
print(json.dumps([dict(sku=r['sku'],draft_id=r['native_draft_id'],listing=r['listing_count'],in_situ=r['in_situ_count'],full_target=len(r['desired_gallery_ids']),difference=r['difference_kind']) for r in records if r['sku'] in ['SQ0717348','BOLD-3DEA4D29C4A2','BOLD-22B6E4FB3DD8','BOLD-5020FF47923F']],indent=2))
