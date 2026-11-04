"""Replace the existing Dropbox workbook with revision and byte-readback guards."""
from datetime import datetime, timezone
from pathlib import Path
import fcntl
import hashlib
import json
import os
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'catalogue-review'))
from delete_dropbox import connection
from dropbox.files import WriteMode

OUT = Path(sys.argv[1]).resolve()
read = lambda name: json.loads((OUT / name).read_text())
sha = lambda body: hashlib.sha256(body).hexdigest()
body = (OUT / 'catalogue_wall_sculptures.xlsx').read_bytes()
verification = read('verification.json')
assert verification['status'] == 'PASS' and verification['sha256'] == sha(body)
assert read('independent-verification.json')['status'] == 'PASS'
old = read('previous-dropbox-metadata.json')
assert old['path_display'] == '/BOLDSTONE MASTER/Products/01 Wall Sculptures/_Documents_Catalogue/catalogue_wall_sculptures.xlsx'
snapshot = read('app-after.json')
with urllib.request.urlopen('http://127.0.0.1:8767/api/specifications', timeout=120) as response:
    current_app = json.load(response)
def relevant(app):
    result = {p['id']: {'fields': {f['key']: f['value'] for f in p['fields'] + p['listing_fields']},
                       'costing': p['costing']} for p in app['products']}
    if (OUT / 'completeness-plan.json').exists():
        for p in app['products']:
            result[p['id']].update(listing_decision=p['listing_decision'], photos=p['photos'],
                shipping_inputs={k:p['us_shipping'][k] for k in ('source_fingerprint','packed_cm','packed_kg')},
                shipping_quotes=[{k:q.get(k) for k in ('destination','status','charges','estimate_gbp','fuel_percent','valid_until','sources')}
                                 for q in p['us_shipping']['quotes']])
    return result
assert relevant(current_app) == relevant(snapshot), 'Catalogue values changed during preparation; reconcile before upload.'
receipt_path = OUT / 'dropbox-receipt.json'
assert not receipt_path.exists(), 'Reconcile an existing receipt before retrying an upload.'
content_hash = sha(b''.join(hashlib.sha256(body[n:n+4194304]).digest() for n in range(0, len(body), 4194304)))
info = lambda m: {k: str(getattr(m, k)) if k.endswith('modified') else getattr(m, k) for k in
    ('id', 'path_display', 'rev', 'size', 'content_hash', 'server_modified', 'client_modified')}
receipt = {'status': 'PREPARED', 'started_utc': datetime.now(timezone.utc).isoformat(),
           'previous': old, 'sha256': sha(body),
           'scope': 'Surface effects explicitly labelled Finish in retail/model/marketplace titles; 181 component rows retained; prefixed observed and catalogue-aligned Chairish/eBay fields, currency/dimension formulas, item review and eBay photo URLs added. Live platform listings not changed by this operation.'}
if (OUT / 'corrections-plan.json').exists():
    receipt['scope'] = read('corrections-plan.json')['scope']
if (OUT / 'saatchi-import-plan.json').exists():
    receipt['scope'] = read('saatchi-import-plan.json')['scope']
if (OUT / 'completeness-plan.json').exists():
    receipt['scope'] = read('completeness-plan.json')['scope']
if (OUT / 'editions-plan.json').exists():
    receipt['scope'] = read('editions-plan.json')['scope']
save = lambda: receipt_path.write_text(json.dumps(receipt, indent=2) + '\n')
with Path('/Users/tprice/Library/Application Support/BoldstoneReview/native-jobs/writer.lock').open('a') as lock:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    with connection(ROOT) as (client, _):
        meta = client.files_get_metadata(old['id'])
        assert meta.rev == old['rev'] and meta.path_display == old['path_display'], 'Dropbox revision changed; reconcile first.'
        downloaded_meta, response = client.files_download('rev:' + meta.rev)
        try:
            previous_body = response.content
        finally:
            response.close()
        assert downloaded_meta.id == meta.id and previous_body == (OUT / 'previous-catalogue.xlsx').read_bytes()
        receipt['status'] = 'SUBMITTING_REVISION_UPDATE'; save()
        try:
            result = client.files_upload(body, meta.path_display, mode=WriteMode.update(meta.rev),
                        autorename=False, mute=True, strict_conflict=True)
            receipt.update(status='UPLOADED_READBACK_PENDING', upload_response=info(result)); save()
        except Exception as exc:
            receipt.update(status='RESPONSE_UNCONFIRMED', error_type=type(exc).__name__); save()
        current = client.files_get_metadata(meta.id)
        assert current.id == meta.id and current.path_display == meta.path_display
        assert current.content_hash == content_hash and current.size == len(body)
        result_meta, response = client.files_download('rev:' + current.rev)
        try:
            readback = response.content
        finally:
            response.close()
        assert result_meta.id == meta.id and sha(readback) == sha(body)
        (OUT / 'dropbox-readback.xlsx').write_bytes(readback)
        receipt.update(status='PASS_DROPBOX_REVISION_UPDATE_AND_BYTE_READBACK', current=info(current),
                       sha256_readback=sha(readback), verified_utc=datetime.now(timezone.utc).isoformat()); save()
pointer_path = ROOT / 'sculpture-catalogue/current-master.json'
raw_pointer = pointer_path.read_bytes(); pointer = json.loads(raw_pointer)
prior = read('source-pointer-before.json')['current_app_review_workbook']
assert pointer['current_app_review_workbook'] == prior
updated = dict(prior)
updated.update(path=str(OUT / 'catalogue_wall_sculptures.xlsx'), sha256=sha(body), dropbox=receipt['current'],
    dropbox_receipt=str(receipt_path), dropbox_receipt_sha256=sha(receipt_path.read_bytes()),
    verification=str(OUT / 'verification.json'), verification_sha256=sha((OUT / 'verification.json').read_bytes()))
if (OUT / 'editions-plan.json').exists():
    updated.update(saatchi_editions_updated_utc=receipt['verified_utc'],
        saatchi_editions_scope=receipt['scope'],
        saatchi_editions_plan=str(OUT / 'editions-plan.json'),
        saatchi_editions_plan_sha256=sha((OUT / 'editions-plan.json').read_bytes()),
        saatchi_editions_verified=str(OUT / 'independent-verification.json'))
elif (OUT / 'completeness-plan.json').exists():
    updated.update(completeness_updated_utc=receipt['verified_utc'],completeness_scope=receipt['scope'],
        completeness_plan=str(OUT / 'completeness-plan.json'),
        completeness_plan_sha256=sha((OUT / 'completeness-plan.json').read_bytes()),
        completeness_verified=str(OUT / 'independent-verification.json'),
        completeness_audit=str(OUT / 'data-audit.json'))
elif (OUT / 'saatchi-import-plan.json').exists():
    updated.update(saatchi_import_utc=receipt['verified_utc'],saatchi_import_scope=receipt['scope'],
        saatchi_import=str(OUT / 'saatchi-import-plan.json'),
        saatchi_import_sha256=sha((OUT / 'saatchi-import-plan.json').read_bytes()),
        saatchi_import_verified=str(OUT / 'independent-verification.json'))
else:
    updated.update(platform_reconciliation_utc=receipt['verified_utc'], platform_reconciliation_scope=receipt['scope'],
        platform_reconciliation=str(OUT / 'matched-platform-records.json'),
        platform_reconciliation_sha256=sha((OUT / 'matched-platform-records.json').read_bytes()))
updated.update(sheets=verification.get('sheets', updated.get('sheets')),
               component_records=len(snapshot['products']))
if (OUT / 'editions-plan.json').exists():
    # A platform-only metadata edit does not refresh the full app-derived workbook.
    updated['saatchi_editions_app_snapshot_utc'] = snapshot['checked_at']
else:
    updated['app_snapshot_utc'] = snapshot['checked_at']
if (OUT / 'corrections-plan.json').exists():
    updated.update(platform_corrections=str(OUT / 'corrections-plan.json'),
                   platform_corrections_sha256=sha((OUT / 'corrections-plan.json').read_bytes()),
                   platform_corrections_verified=str(OUT / 'independent-verification.json'))
pointer['current_app_review_workbook'] = updated
temporary = pointer_path.with_name('.current-master.platform-workbook.tmp')
temporary.write_text(json.dumps(pointer, ensure_ascii=False, indent=2) + '\n')
assert pointer_path.read_bytes() == raw_pointer
os.replace(temporary, pointer_path)
print(json.dumps({'status': receipt['status'], 'revision': receipt['current']['rev'], 'bytes': len(body),
                  'same_file_id': True, 'sha256': sha(body)}))
