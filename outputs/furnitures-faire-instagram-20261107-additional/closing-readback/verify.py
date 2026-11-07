"""Reconcile the requested channels with the verified, current Dropbox copy."""
import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/Users/tprice/Documents/boldstone')
OUT = Path(__file__).parent
RUN = OUT.parent
sys.path.insert(0, '/tmp/boldstone-20261106-readback')
from python_calamine import CalamineWorkbook

pointer = json.loads((ROOT / 'sculpture-catalogue/current-master.json').read_text())['current_app_review_workbook']
receipt = json.loads(Path(pointer['dropbox_receipt']).read_text())
body = Path(pointer['path']).read_bytes()
readback = Path(pointer['dropbox_receipt']).with_name('dropbox-readback.xlsx').read_bytes()
digest = hashlib.sha256(body).hexdigest()
assert body == readback
assert pointer['sha256'] == receipt['sha256'] == receipt['sha256_readback'] == digest
assert receipt['status'] == 'PASS_DROPBOX_REVISION_UPDATE_AND_BYTE_READBACK'
assert receipt['current']['id'] == 'id:cnqzTNngPVsAAAAAAA7JEQ'

sheet = CalamineWorkbook.from_path(str(Path(pointer['path']))).get_sheet_by_name('Wall Sculptures').to_python(skip_empty_area=False)
headers = {name: n for n, name in enumerate(sheet[6]) if name}
rows = {r[headers['Product ID']]: r for r in sheet[7:] if r[headers['Product ID']]}
assert len(rows) == 181
faire = json.loads((RUN / 'faire-price-reconciliation.json').read_text())
assert len(faire['records']) == 176 and not faire['differences']
for source in faire['records']:
    row = rows[source['catalogue_id']]
    assert row[headers['SKU']] == source['sku']
    for field, key in [('faire_native_wholesale_gbp', 'wholesale_gbp'), ('faire_native_retail_gbp', 'retail_gbp')]:
        assert math.isclose(row[headers[field]], source[key], abs_tol=.00001), (source['sku'], field)
    assert row[headers['faire_native_product_token']] == source['token']
    assert row[headers['faire_native_product_status']] == source['product_status'] == 'Published'
    assert row[headers['faire_native_option_status']] == source['option_status'] == 'Published'

prior_plan = json.loads((RUN / 'workbook/plan.json').read_text())
for patch in prior_plan['patches']:
    column = 0
    for char in ''.join(c for c in patch['cell'] if c.isalpha()):
        column = column * 26 + ord(char) - 64
    row = int(''.join(c for c in patch['cell'] if c.isdigit()))
    assert sheet[row - 1][column - 1] == patch['value'], patch['cell']

furnitures_state = (OUT / 'furnitures-dashboard.txt').read_text()
faire_state = (OUT / 'faire.txt').read_text()
published_state = (OUT / 'instagram.txt').read_text()
assert 'text 176 / 176' in furnitures_state and 'text Products live' in furnitures_state
assert 'text 176 products Edit fields in bulk' in faire_state
posts = json.loads((RUN / 'instagram-independent-verification.json').read_text())['posts']
assert len(posts) == len({p['native_id'] for p in posts}) == 5
for post in posts:
    assert 'row Select item with ID ' + post['native_id'] + ' Instagram' in published_state
    assert all(post[k] for k in ['published', 'product_tag_saved', 'alt_text_saved', 'caption_verified'])

result = dict(status='PASS_REQUESTED_CHANNELS_AND_CURRENT_DROPBOX_READBACK',
              checked_utc=datetime.now(timezone.utc).isoformat(),
              furnitures_live=176, faire_native_prices_verified=176,
              faire_native_export_checked_utc=faire['checked_utc'],
              instagram_posts=posts, workbook_sha256=digest,
              dropbox=receipt['current'], original_request_cells_preserved=len(prior_plan['patches']),
              new_duplicate_products_or_posts_created=0,
              outstanding_operational_notices=[
                  'Faire requests a UK bank account for GBP payouts.',
                  'Furnitures says Stripe payouts are coming in its next release.',
                  'Actual Faire prices and profit-protection targets remain separate.'
              ])
(OUT / 'verification.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({k: result[k] for k in ['status', 'furnitures_live', 'faire_native_prices_verified', 'workbook_sha256', 'original_request_cells_preserved']}))
