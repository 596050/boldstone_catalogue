"""Publish the verified workbook pointer without changing catalogue sources."""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import hashlib, json, os

ROOT = Path('/Users/tprice/Documents/boldstone')
OUT = Path(__file__).resolve().parent
TARGET = ROOT/'sculpture-catalogue/current-master.json'
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
verification = read(OUT/'verification.json')
receipt = read(OUT/'dropbox-receipt.json')
snapshot = read(OUT/'catalogue-snapshot-latest.json')
assert verification['status'] == 'PASS'
assert receipt['status'] == 'PASS_DROPBOX_REVISION_UPDATE_AND_BYTE_READBACK'
assert verification['sha256'] == receipt['sha256_readback'] == sha(OUT/'catalogue_wall_sculptures.xlsx')
raw = TARGET.read_bytes()
current = json.loads(raw)
previous = read(OUT/'source-pointer-before.json')['current_app_review_workbook']
assert current['current_app_review_workbook'] == previous, 'Workbook publisher changed; reconcile first.'
pointer = dict(previous)
pointer.update(
    status='PASS_CURRENT_APP_REFRESH_DROPBOX_BYTE_READBACK',
    path=str(OUT/'catalogue_wall_sculptures.xlsx'),
    sha256=verification['sha256'],
    app_snapshot_utc=snapshot['created_utc'], event_cutoff=snapshot['event_cutoff'],
    active_options=len(snapshot['products']),
    sheets=len(read(OUT/'workbook-changes.json')['sheets']),
    unique_images=snapshot['summary']['unique_images'], image_rows=snapshot['summary']['image_rows'],
    specification_fields=snapshot['summary']['fields'],
    specification_and_listing_copy_rows=sum(len(p['fields'])+len(p['listing_fields']) for p in snapshot['products']),
    manufacturing_cost_rows=verification['products_costs_and_prices_reconciled'],
    hyperlinks=verification['hyperlinks_verified'],
    source_register_sha256=snapshot['source']['register_sha256'],
    source_gallery_sha256=snapshot['source']['gallery_sha256'],
    verification=str(OUT/'verification.json'), verification_sha256=sha(OUT/'verification.json'),
    preservation_verification=str(OUT/'verification.json'),
    dropbox_receipt=str(OUT/'dropbox-receipt.json'), dropbox_receipt_sha256=sha(OUT/'dropbox-receipt.json'),
    dropbox=receipt['current'],
    listing_decisions=dict(Counter(p['listing_decision'] for p in snapshot['products'])),
    costing_semantics='Manufacturing cost excludes labour. Total cost adds separate labour once; markup selling price uses total cost.',
    labour_hourly_rate=snapshot['cost_settings']['labour_hourly'],
    workbook_upload_plan=str(OUT/'website-final-plan.json'),
    squarespace_readiness=str(OUT/'website-photo-readiness.json'),
    website_verification=str(OUT/'public-website-verification.json'),
    website_public_readback=str(OUT/'public-website-verification.json'),
)
current['current_app_review_workbook'] = pointer
temp = TARGET.with_name('.current-master.workbook-refresh.tmp')
temp.write_text(json.dumps(current,ensure_ascii=False,indent=2)+'\n')
assert TARGET.read_bytes() == raw, 'Publisher changed before pointer update.'
os.replace(temp,TARGET)
after = read(TARGET)
assert after['current_app_review_workbook'] == pointer
for key,value in json.loads(raw).items():
    if key != 'current_app_review_workbook': assert after[key] == value,key
result = {'status':'PASS_POINTER_ONLY_UPDATE', 'verified_utc':datetime.now(timezone.utc).isoformat(),
          'pointer_path':str(TARGET),'event_cutoff':pointer['event_cutoff'],
          'workbook_sha256':pointer['sha256'],'dropbox_revision':pointer['dropbox']['rev']}
(OUT/'publication-receipt.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
