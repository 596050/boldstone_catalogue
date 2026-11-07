"""Refresh native Faire observations and newly completed Furnitures fields."""
from pathlib import Path
from datetime import datetime, timezone
import json, sys, re, shutil, hashlib, urllib.request
from decimal import Decimal

ROOT = Path('/Users/tprice/Documents/boldstone')
OUT = Path(__file__).parent
PRIOR = OUT.parent
sys.path.insert(0, str(ROOT / 'catalogue-review/scripts'))
from import_saatchi_snapshot import Xlsx, column, column_index

read = lambda p: json.loads(p.read_text())
save = lambda n, d: (OUT / n).write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n')
now = datetime.now(timezone.utc).isoformat()
pointer = read(ROOT / 'sculpture-catalogue/current-master.json')
source = pointer['current_app_review_workbook']
assert source['dropbox']['id'] == 'id:cnqzTNngPVsAAAAAAA7JEQ'
body = Path(source['path']).read_bytes()
assert hashlib.sha256(body).hexdigest() == source['sha256']
if (OUT / 'previous-catalogue.xlsx').exists():
    assert (OUT / 'previous-catalogue.xlsx').read_bytes() == body
else:
    (OUT / 'previous-catalogue.xlsx').write_bytes(body)
save('source-pointer-before.json', pointer)
save('previous-dropbox-metadata.json', source['dropbox'])
with urllib.request.urlopen('http://127.0.0.1:8767/api/specifications', timeout=120) as r:
    app = json.load(r)
save('app-specifications.json', app)

x = Xlsx(OUT / 'previous-catalogue.xlsx')
sheet = 'Wall Sculptures'
headers = {x.value(sheet, a): re.sub(r'\d', '', a) for a in x.cells[sheet] if re.fullmatch('[A-Z]+7', a)}
rows = {x.value(sheet, f'AQ{r}'): r for r in range(8, 189)}
native = Xlsx(PRIOR / 'faire-products-native-export.xlsx')
furniture = {r['catalogue_id']: r for r in read(PRIOR / 'furnitures-upload-plan.json')['records']}
receipts = {r['catalogue_id']: r for r in read(PRIOR / 'furnitures-field-receipts.json') if r['status'] == 'VERIFIED_SAVED'}
public = read(OUT / 'furnitures-public-verification.json')
assert public['status'] == 'PASS_ALL_176_PUBLIC_PRODUCTS' and public['images_verified'] == 680
observed = {r['sku']: r for r in read(PRIOR / 'faire-observed-prices.json')['records']}
assert len(observed) == 176
added = ['faire_native_product_token', 'faire_native_product_status', 'faire_native_option_status', 'faire_native_payout_action']
assert not set(added) & set(headers)
first = max(map(column_index, headers.values())) + 1
headers.update({h: column(first + i) for i, h in enumerate(added)})
patches = [dict(sheet=sheet, cell=headers[h] + '7', before=None, value=h) for h in added]
export_records = []
seen = set()
for n in range(4, 180):
    sku = native.value('Products', f'V{n}')
    assert sku in rows and sku in observed and sku not in seen
    seen.add(sku)
    r = rows[sku]
    pid = x.value(sheet, f'AA{r}')
    w = native.value('Products', f'AE{n}')
    retail = native.value('Products', f'AF{n}')
    status = native.value('Products', f'B{n}')
    option_status = native.value('Products', f'U{n}')
    token = native.value('Products', f'C{n}')
    assert status == option_status == 'Published'
    assert isinstance(token, str) and token.startswith('p_')
    assert w == observed[sku]['wholesale_gbp'] and retail == observed[sku]['retail_gbp']
    assert Decimal(str(w))*Decimal('1.25') <= Decimal(str(retail)) <= Decimal(str(w))*10
    vals = {
        'faire_native_product_name': native.value('Products', f'A{n}'),
        'faire_native_wholesale_gbp': w, 'faire_native_retail_gbp': retail,
        'faire_native_product_token': token, 'faire_native_product_status': status,
        'faire_native_option_status': option_status,
        'faire_native_shop_status': '176 products marked Published in the native manager and export. Public retailer purchase route not independently tested.',
        'faire_native_editor_status': 'Native product manager and complete product export are accessible. Earlier review lock no longer displayed.',
        'faire_native_checked_utc': 'Checked UTC: ' + now,
        'faire_native_payout_action': 'Faire requests a UK bank account to continue receiving GBP payouts. Owner must complete banking details.',
        'faire_native_price_source': 'https://www.faire.com/brand-portal/my-shop/products ; native all-products export downloaded 6 November 2026, matched by exact SKU and product token.',
        'faire_pricing_action': '6 November native export: all 176 products Published. Recorded native RRP exceeds app retail; wholesale is below the protected model and recorded Brandboom wholesale. Reconcile genuine retail and wholesale parity. Existing app prices and protected model preserved.',
        'furnitures_native_status': 'Active. Public page, exact native identity, GBP price, InStock availability, full description and all ordered selected gallery URLs independently verified. ' + ('Separate specification fields saved and read back in the native editor.' if pid in receipts else 'Separate specification fields remain pending; their details are already present in the verified public description.'),
        'furnitures_checked_utc': 'Checked UTC: ' + public['checked_utc'],
    }
    if pid in receipts:
        f = furniture[pid]
        receipt = receipts[pid]
        assert receipt['price_gbp'] == f['price_gbp'] and receipt['image_count'] == len(f['image_urls'])
        vals.update({
            'furnitures_material': f['material'], 'furnitures_dimensions': f['dimensions'], 'furnitures_colour': f['colour'],
            'furnitures_specification_fields_status': 'Saved and read back in native editor',
        })
    for h, v in vals.items():
        cell = headers[h] + str(r)
        before = x.value(sheet, cell)
        if before != v:
            patches.append(dict(sheet=sheet, cell=cell, before=before, value=v))
    export_records.append(dict(catalogue_id=pid, sku=sku, native_product_token=token, product_status=status, option_status=option_status, wholesale_gbp=w, retail_gbp=retail))
assert seen == set(observed)
assert len({r['native_product_token'] for r in export_records}) == 176
save('faire-export-reconciliation.json', dict(status='PASS_176_NATIVE_PUBLISHED_SKUS_TOKENS_AND_PRICES', checked_utc=now, count=176, price_changes_from_prior_capture=0, records=export_records))
scope = 'Refresh all 176 Faire records from the native product export: Published product and option status, stable product tokens, current accessibility and UK-bank payout requirement. Preserve native prices, app retail and protected pricing models. Record any additional Furnitures specification saves from the guarded native journal. No new products or Instagram posts are created.'
plan = dict(scope=scope, patches=patches, headers=headers, added_headers=added, first_added_column=first, last_column=first+len(added)-1, numeric_headers=[], preview_range=headers['faire_native_shop_status']+'7:'+headers['faire_native_editor_status']+'9', furnitures_separate_specification_fields_verified=len(receipts), furnitures_separate_specification_fields_pending=176-len(receipts))
save('plan.json', plan)
bindings=read(PRIOR/'furnitures-native-bindings.json')
save('furnitures-pending-fields.json',[dict(**b,material=furniture[b['catalogue_id']]['material'],dimensions=furniture[b['catalogue_id']]['dimensions'],colour=furniture[b['catalogue_id']]['colour']) for b in bindings if b['catalogue_id'] not in receipts])
print(json.dumps(dict(patches=len(patches), native_published=176, added_fields=len(added), furnitures_fields_verified=len(receipts))))
