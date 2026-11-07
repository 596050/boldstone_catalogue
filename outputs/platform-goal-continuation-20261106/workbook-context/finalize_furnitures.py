"""Extend the unsubmitted catalogue patch with completed native field receipts."""
import hashlib, json, re, sys
from pathlib import Path

ROOT = Path('/Users/tprice/Documents/boldstone')
OUT = Path(__file__).parent
PRIOR = ROOT / 'outputs/furnitures-faire-instagram-20261106'
sys.path.insert(0, str(ROOT / 'catalogue-review/scripts'))
from import_saatchi_snapshot import Xlsx

read = lambda p: json.loads(p.read_text())
assert not (OUT / 'dropbox-receipt.json').exists(), 'Reconcile an existing upload first'
plan = read(OUT / 'plan.json')
assert not plan.get('furnitures_completion_added'), 'Native completion already incorporated'
pointer = read(ROOT / 'sculpture-catalogue/current-master.json')['current_app_review_workbook']
assert hashlib.sha256((OUT / 'previous-catalogue.xlsx').read_bytes()).hexdigest() == pointer['sha256']
x = Xlsx(OUT / 'previous-catalogue.xlsx')
sheet = 'Wall Sculptures'
rows = {x.value(sheet, f'AA{r}'): r for r in range(8, 189)}
targets = {r['catalogue_id']: r for r in read(PRIOR / 'furnitures-upload-plan.json')['records']}
bindings = {r['catalogue_id']: r for r in read(PRIOR / 'furnitures-native-bindings.json')}
receipts = {r['catalogue_id']: r for r in read(PRIOR / 'furnitures-field-receipts.json') if r['status'] == 'VERIFIED_SAVED'}
assert set(receipts) == set(targets) == set(bindings) and len(receipts) == 176
pending = read(PRIOR / 'followup/furnitures-pending-fields.json')
assert len(pending) == 52
patches = list(plan['patches'])
for record in pending:
    pid = record['catalogue_id']
    target, receipt, binding = targets[pid], receipts[pid], bindings[pid]
    assert target['sku'] == receipt['sku'] == binding['sku'] == record['sku']
    assert receipt['edit_url'] == binding['edit_url']
    assert receipt['price_gbp'] == target['price_gbp'] and receipt['description_verified']
    assert receipt['image_count'] == len(target['image_urls'])
    row = rows[pid]
    assert x.value(sheet, f'AQ{row}') == target['sku']
    values = {
        'furnitures_material': target['material'],
        'furnitures_dimensions': target['dimensions'],
        'furnitures_colour': target['colour'],
        'furnitures_specification_fields_status': 'Saved and read back in native editor',
        'furnitures_native_status': 'Active. Public page, exact native identity, GBP price, InStock availability, full description and all ordered selected gallery URLs independently verified. Separate specification fields saved and read back in the native editor.',
        'furnitures_checked_utc': 'Checked UTC: ' + receipt['utc'],
    }
    for header, value in values.items():
        address = plan['headers'][header] + str(row)
        before = x.value(sheet, address)
        if value != before:
            patches.append(dict(sheet=sheet, cell=address, before=before, value=value))
assert len({(p['sheet'], p['cell']) for p in patches}) == len(patches)
plan.update(patches=patches, furnitures_completion_added=True,
            furnitures_separate_specification_fields_verified=176,
            furnitures_separate_specification_fields_pending=0)
plan['scope'] += ' Complete the 52 remaining Furnitures material, dimensions and colour observations from verified native saves. All 176 native specification forms are now complete. Existing Faire prices, app retail, manufacturing costs, labour and profit-protection models preserved.'
r = rows[pending[0]['catalogue_id']]
start = plan['headers']['furnitures_material']
end = plan['headers']['furnitures_colour']
plan['furnitures_preview_range'] = f'{start}{r}:{end}{r}'
plan['furnitures_preview_headers'] = f'{start}7:{end}7'
(OUT / 'plan.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2) + '\n')
(OUT / 'furnitures-completion-receipts.json').write_text(json.dumps(list(receipts.values()), ensure_ascii=False, indent=2) + '\n')
print(json.dumps(dict(patches=len(patches), completed=176, pending=0)))
