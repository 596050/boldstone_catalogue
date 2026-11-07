"""Independently reconcile each saved native form against its SKU-bound target."""
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import hashlib, json, re

OUT = Path(__file__).parent
PRIOR = OUT.parent
read = lambda p: json.loads(p.read_text())
targets = read(PRIOR / 'furnitures-upload-plan.json')['records']
bindings = {r['sku']: r for r in read(PRIOR / 'furnitures-native-bindings.json')}
receipts = {r['sku']: r for r in read(PRIOR / 'furnitures-field-receipts.json') if r['status'] == 'VERIFIED_SAVED'}
assert len(receipts) == len(targets) == len(bindings) == 176

def value(text, field):
    matches = re.findall(r'^\s*\d+ text field \(settable\) ' + re.escape(field) + r',[^\n]*?Value: (.*?)(?:, Placeholder:.*)?$', text, re.M)
    assert len(matches) == 1, (field, len(matches))
    return matches[0]

rows = []
for target in targets:
    sku, pid = target['sku'], target['catalogue_id']
    binding, receipt = bindings[sku], receipts[sku]
    assert binding['catalogue_id'] == receipt['catalogue_id'] == pid
    assert receipt['edit_url'] == binding['edit_url']
    evidence = PRIOR / 'evidence' / ('furnitures-' + pid + '-saved.txt')
    text = evidence.read_text()
    route = re.search(r'Address and search bar[^\n]*Value: (furnitures\.co\.uk/dashboard/products/[a-z0-9-]+)', text)
    assert route and 'https://' + route[1] == binding['edit_url'], pid
    assert value(text, 'Product name') == target['title']
    assert Decimal(value(text, 'Price (£)')) == Decimal(str(target['price_gbp']))
    for field, key in [('Material', 'material'), ('Dimensions', 'dimensions'), ('Colour', 'colour')]:
        assert value(text, field) == target[key], (pid, field)
    assert 'Saved — changes are live.' in text
    assert 'Value: Active — visible in the marketplace' in text
    images = re.search(r'text entry area[^\n]*Images \(one URL per line, up to 6\).*?Value: ([\s\S]*?)(?=\n\s*\d+ )', text)
    assert images and images[1].strip().split('\n') == target['image_urls'], pid
    assert receipt['description_verified'] and receipt['image_count'] == len(target['image_urls'])
    rows.append(dict(catalogue_id=pid, sku=sku, native_id=binding['native_id'],
                     public_url=binding['public_url'], native_save_utc=receipt['utc'],
                     evidence_sha256=hashlib.sha256(evidence.read_bytes()).hexdigest(),
                     status='PASS_NATIVE_FIELDS_PRICE_STATUS_AND_GALLERY'))
report = dict(status='PASS_ALL_176_NATIVE_SPECIFICATION_FORMS',
              evidence_independently_read_utc=datetime.now(timezone.utc).isoformat(),
              count=len(rows), pending=0, records=rows)
(OUT / 'furnitures-final-native-verification.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({k:v for k,v in report.items() if k != 'records'}))
