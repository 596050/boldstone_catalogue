import json, re, sys, hashlib
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/Users/tprice/Documents/boldstone')
OUT = Path(__file__).parent
sys.path.insert(0, str(ROOT / 'catalogue-review/scripts'))
from import_saatchi_snapshot import Xlsx

pointer = json.loads((ROOT / 'sculpture-catalogue/current-master.json').read_text())['current_app_review_workbook']
master = Xlsx(pointer['path'])
sheet = 'Wall Sculptures'
headers = {master.value(sheet, a): re.sub(r'\d', '', a) for a in master.cells[sheet] if re.fullmatch(r'[A-Z]+7', a)}
by_sku = {str(master.value(sheet, 'AQ' + str(n))): n for n in range(8, 189)}
by_token = {str(master.value(sheet, headers['faire_native_product_token'] + str(n))): n for n in range(8, 189)}
faire = Xlsx(OUT / 'faire-products-native-export.xlsx')
frows = sorted({int(re.search(r'\d+', a)[0]) for a in faire.cells['Products'] if a.startswith('A')})
records, differences, seen = [], [], set()
for n in frows:
    if n < 3 or not str(faire.value('Products', 'C' + str(n)) or '').startswith('p_'):
        continue
    get = lambda c: faire.value('Products', c + str(n))
    token, sku = get('C'), get('V')
    target_row = by_token.get(str(token))
    assert target_row and by_sku.get(str(sku)) == target_row, (token, sku)
    assert token not in seen, token
    seen.add(token)
    entry = dict(catalogue_id=master.value(sheet, 'AA' + str(target_row)), sku=sku, token=token,
                 name=get('A'), product_status=get('B'), option_status=get('U'),
                 wholesale_gbp=float(get('AE')), retail_gbp=float(get('AF')), master_row=target_row)
    for field, key in [('faire_native_wholesale_gbp','wholesale_gbp'), ('faire_native_retail_gbp','retail_gbp'),
                       ('faire_native_product_status','product_status'), ('faire_native_option_status','option_status')]:
        value = master.value(sheet, headers[field] + str(target_row))
        actual = entry[key]
        equal = abs(float(value)-actual) < .001 if isinstance(actual, float) else value == actual
        if not equal:
            differences.append(dict(catalogue_id=entry['catalogue_id'], field=field, before=value, actual=actual))
    records.append(entry)
assert len(records) == 176
assert all(r['product_status'] == 'Published' and r['option_status'] == 'Published' for r in records)
audit = dict(checked_utc=datetime.now(timezone.utc).isoformat(), source='Fresh native Faire export downloaded through Chrome',
             export_sha256=hashlib.sha256((OUT / 'faire-products-native-export.xlsx').read_bytes()).hexdigest(),
             master_path=pointer['path'], master_sha256=hashlib.sha256(Path(pointer['path']).read_bytes()).hexdigest(),
             products=176, unique_tokens=len(seen), differences=differences, records=records)
(OUT / 'faire-price-reconciliation.json').write_text(json.dumps(audit, indent=2) + '\n')

app = json.loads((OUT / 'app-specifications.json').read_text())
candidate_ids = ['BSI-0C2CB099DDEB', 'BSI-DF3FF43C94C9', 'BSI-FE973AD4748E', 'BSI-21E7F11ACAAA']
candidate_ids += [p['id'] for p in app['products'] if 'Gleneagles' in p['retail_name'] and 'III' in p['retail_name']]
candidates = []
for p in app['products']:
    if p['id'] not in candidate_ids:
        continue
    row = next(n for n in range(8, 189) if master.value(sheet, 'AA' + str(n)) == p['id'])
    candidates.append(dict(catalogue_id=p['id'], retail_name=p['retail_name'],
                           prior_instagram_url=master.value(sheet, headers['instagram_post_url']+str(row)),
                           keys=list(p), photos=p.get('photos'), listing_fields=p.get('listing_fields')))
(OUT / 'instagram-candidates.json').write_text(json.dumps(candidates, indent=2, ensure_ascii=False) + '\n')
print(json.dumps(dict(faire_products=len(records), price_or_status_differences=len(differences),
                      candidates=[{k:c[k] for k in ['catalogue_id','retail_name','prior_instagram_url']} for c in candidates]), indent=2))
