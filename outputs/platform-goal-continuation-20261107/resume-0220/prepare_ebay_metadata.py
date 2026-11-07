"""Plan exact-ID updates to remaining eBay drafts, without publication."""
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from urllib.request import urlopen

ROOT = Path('/Users/tprice/Documents/boldstone')
OUT = Path(__file__).parent
assert not (OUT / 'ebay-remaining-metadata-queue.json').exists(), 'Preserve the existing queue and its native receipts; prepare a new generation instead'
sys.path.insert(0, str(ROOT / 'catalogue-review/scripts'))
from import_saatchi_snapshot import Xlsx

pointer = json.loads((ROOT / 'sculpture-catalogue/current-master.json').read_text())['current_app_review_workbook']
workbook = Path(pointer['path'])
assert hashlib.sha256(workbook.read_bytes()).hexdigest() == pointer['sha256']
book = Xlsx(workbook)
headers = {book.value('Wall Sculptures', c): re.sub(r'\d+', '', c)
           for c in book.cells['Wall Sculptures'] if re.fullmatch(r'[A-Z]+7', c) and book.value('Wall Sculptures', c)}
rows = {str(book.value('Wall Sculptures', 'AQ' + str(row))): row for row in range(8, 189)}
targets = json.loads((ROOT / 'outputs/catalogue-marketplace-publication-20261101/catalogue-copy-disclosures/ebay-sapr-66-draft-targets.json').read_text())
already = json.loads((ROOT / 'outputs/platform-goal-continuation-20261107/resume-0041/ebay-draft-receipts.json').read_text())
assert isinstance(already, list)
done = {r['sku'] for r in already}
with urlopen('http://127.0.0.1:8767/api/specifications', timeout=90) as response:
    app = json.load(response)
with urlopen('http://127.0.0.1:8767/api/coverage', timeout=90) as response:
    full_coverage = json.load(response)['products']
with urlopen('http://127.0.0.1:8767/api/specifications', timeout=90) as response:
    assert json.load(response)['revision'] == app['revision'], 'Photo source changed while reading complete selections'
products = {p['id']: p for p in app['products']}
queue = []
for target in targets:
    sku = target['sku']
    if sku in done:
        continue
    row = rows[sku]
    get = lambda key: book.value('Wall Sculptures', headers[key] + str(row))
    catalogue_id = get('Product ID')
    product = products[catalogue_id]
    url = target['links'][0]['href']
    query = parse_qs(urlparse(url).query)
    draft_id = (query.get('draft_id') or query.get('draftId'))[0]
    assert draft_id.isdigit() and sku == target['source']['sku']
    title, description = get('ebay_catalogue_title'), get('ebay_description')
    assert title and len(title) <= 80 and description and len(description) > 200
    description = description.replace('Within 10 working days.', 'Within 3 working days.')
    description = re.sub(r'Dispatch time: Within 10 working days', 'Dispatch time: Within 3 working days', description)
    # Specifications embeds bounded card previews, not complete galleries.
    # Coverage has the full, ordered image_ids with independently stated totals.
    full = full_coverage[catalogue_id]
    assert full['primary_listing']['status'] == 'set'
    photos = [full['primary_listing']['image_id']]
    assert photos[0] == product['photos']['primary_listing']['image_id']
    for kind in ['listing', 'in_situ']:
        ids = full[kind]['image_ids']
        assert len(ids) == full[kind]['count'] == product['photos'][kind]['count']
        for aid in ids:
            if aid not in photos:
                photos.append(aid)
    data = dict(catalogue_id=catalogue_id, sku=sku, native_draft_id=draft_id, native_url=url,
                title=title, description=description, price_gbp=get('ebay_price_gbp'),
                width_cm=get('ebay_width_cm'), height_cm=get('ebay_height_cm'), depth_cm=get('ebay_depth_cm'),
                desired_gallery_ids=photos[:24], selected_photos_over_24=max(0, len(photos) - 24),
                source_app_revision=app['revision'], source_workbook_sha256=pointer['sha256'],
                shipping_status='OVERSIZE_DELIVERY_DECISION_PENDING',
                publication_authorized_by_this_plan=False,
                owner_existing_offer_hold=sku == 'EBAY-188654392024')
    assert all(isinstance(data[k], (int, float)) and data[k] > 0 for k in ['price_gbp','width_cm','height_cm','depth_cm'])
    queue.append(data)
assert len(queue) == 52 and len({r['native_draft_id'] for r in queue}) == len(queue)
(OUT / 'ebay-remaining-metadata-queue.json').write_text(json.dumps(queue, indent=2) + '\n')
legacy = [
    dict(native_id='840091837900', title='Frozen Deco Terracotta', condition='Used',
         state='OUTSIDE_CURRENT_PUBLICATION_FINISH_SCOPE', reason='Current catalogue has Frozen Deco Wave I and II in White. Preserve the existing Terracotta offer.'),
    dict(native_id='840091837829', catalogue_sku='EBAY-188654831217', title='Dune Ripple II Copper Finish', condition='Used',
         state='EXISTING_DESIGN_OVERLAP_DIFFERENT_CONDITION', canonical_current_offer='840091837850',
         reason='Same copper wave design and 35 x 21 x 6 cm dimensions as the catalogue; Used offer differs from current canonical listing. No deletion or change authorized by this record.'),
    dict(native_id='840091837816', catalogue_sku='EBAY-188654392024', title='Frozen Fish Terracotta Finish', condition='Used',
         state='OVERLAPPING_DRAFT_PUBLICATION_HELD',
         reason='Existing Used offer depicts the same terracotta fish design and 70 x 15 x 7 cm dimensions. Keep its overlapping new-product draft unpublished until stock and condition are resolved.'),
]
(OUT / 'ebay-legacy-offer-reconciliation.json').write_text(json.dumps(dict(checked_utc=datetime.now(timezone.utc).isoformat(), native_or_app_writes=0, records=legacy), indent=2) + '\n')
print(json.dumps(dict(planned_existing_drafts=len(queue), new_drafts_created=0, previously_prepared=len(done), overlap_holds=sum(r['owner_existing_offer_hold'] for r in queue))))
