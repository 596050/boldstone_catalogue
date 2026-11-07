"""Reconcile the final workbook to exact native Faire/Furnitures and post receipts."""
from pathlib import Path
from decimal import Decimal
import hashlib, json, sys

ROOT = Path('/Users/tprice/Documents/boldstone')
OUT = Path(__file__).parent
PRIOR = ROOT / 'outputs/furnitures-faire-instagram-20261106'
sys.path.insert(0, str(ROOT / 'catalogue-review/scripts'))
from import_saatchi_snapshot import Xlsx

read = lambda p: json.loads(p.read_text())
plan = read(OUT / 'plan.json')
x = Xlsx(OUT / 'catalogue_wall_sculptures.xlsx')
sheet = 'Wall Sculptures'
rows = {x.value(sheet, f'AA{r}'): r for r in range(8, 189)}
assert len(rows) == 181
get = lambda pid, header: x.value(sheet, plan['headers'][header] + str(rows[pid]))
assert read(PRIOR / 'followup/furnitures-final-native-verification.json')['count'] == 176
furnitures = read(PRIOR / 'furnitures-upload-plan.json')['records']
for record in furnitures:
    pid = record['catalogue_id']
    assert get(pid, 'furnitures_sku') == record['sku']
    assert get(pid, 'furnitures_specification_fields_status') == 'Saved and read back in native editor'
    for field in ['material', 'dimensions', 'colour']:
        assert get(pid, 'furnitures_' + field) == record[field], (pid, field)
    assert Decimal(str(get(pid, 'furnitures_native_price_gbp'))) == Decimal(str(record['price_gbp']))
faire = read(PRIOR / 'followup/faire-export-reconciliation.json')['records']
for record in faire:
    pid = record['catalogue_id']
    assert get(pid, 'faire_native_product_token') == record['native_product_token']
    assert get(pid, 'faire_native_product_status') == get(pid, 'faire_native_option_status') == 'Published'
    for field in ['wholesale_gbp', 'retail_gbp']:
        assert Decimal(str(get(pid, 'faire_native_' + field))) == Decimal(str(record[field]))
posts = read(PRIOR / 'followup/completion.json')['instagram_published']
assert len(posts) == 5
for post in posts:
    pid = post['catalogue_id']
    assert get(pid, 'instagram_post_url') == post['permalink']
    assert str(get(pid, 'instagram_native_post_id')) == post['native_id']
    assert get(pid, 'instagram_product_tag_sku') == post['sku']
    assert post['status'] == 'PUBLISHED_VERIFIED' and post['product_tag_saved'] and post['caption_verified']
report = dict(status='PASS_EXACT_CHANNEL_RECORDS',
              sha256=hashlib.sha256((OUT / 'catalogue_wall_sculptures.xlsx').read_bytes()).hexdigest(),
              component_records=181, furnitures_complete_records=len(furnitures),
              faire_native_records=len(faire), instagram_published_tagged_posts=len(posts))
(OUT / 'channel-record-verification.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report))
