"""Update the authorized existing workbook once, with revision and byte guards."""
import fcntl
import hashlib
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/Users/tprice/Documents/boldstone')
OUT = Path(__file__).parent
sys.path.insert(0, str(ROOT / 'catalogue-review'))
from delete_dropbox import connection
from dropbox.files import WriteMode

read = lambda name: json.loads((OUT / name).read_text())
sha = lambda data: hashlib.sha256(data).hexdigest()
body = (OUT / 'catalogue_wall_sculptures.xlsx').read_bytes()
plan, verification, independent = read('plan.json'), read('verification.json'), read('independent-verification.json')
assert verification['status'] == independent['status'] == 'PASS'
assert verification['sha256'] == independent['sha256'] == sha(body)
assert independent['independently_verified_cells'] == len(plan['patches'])
old = read('previous-dropbox-metadata.json')
assert old['id'] == 'id:cnqzTNngPVsAAAAAAA7JEQ'
assert old['path_display'] == '/BOLDSTONE MASTER/Products/01 Wall Sculptures/_Documents_Catalogue/catalogue_wall_sculptures.xlsx'
saved_app = read('app-specifications.json')
with urllib.request.urlopen('http://127.0.0.1:8767/api/specifications', timeout=120) as response:
    current_app = json.load(response)


def relevant(app):
    return {p['id']: {k: p[k] for k in ['fields', 'listing_fields', 'costing', 'photos', 'listing_decision']} for p in app['products']}


assert relevant(current_app) == relevant(saved_app), 'App changed; reconcile before updating workbook'
pointer_path = ROOT / 'sculpture-catalogue/current-master.json'
pointer = json.loads(pointer_path.read_text())
before_pointer = read('source-pointer-before.json')
assert pointer['current_app_review_workbook'] == before_pointer['current_app_review_workbook']
receipt_path = OUT / 'dropbox-receipt.json'
assert not receipt_path.exists(), 'Reconcile the existing upload journal before any retry'
receipt = dict(status='PREPARED', started_utc=datetime.now(timezone.utc).isoformat(), previous=old, sha256=sha(body), scope=plan['scope'])
save = lambda: receipt_path.write_text(json.dumps(receipt, indent=2) + '\n')
info = lambda m: {k: str(getattr(m, k)) if k.endswith('modified') else getattr(m, k) for k in ['id', 'path_display', 'rev', 'size', 'content_hash', 'server_modified', 'client_modified']}
content_hash = sha(b''.join(hashlib.sha256(body[i:i + 4194304]).digest() for i in range(0, len(body), 4194304)))
with Path('/Users/tprice/Library/Application Support/BoldstoneReview/native-jobs/writer.lock').open('a') as lock:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    with connection(ROOT) as (db, _):
        meta = db.files_get_metadata(old['id'])
        assert meta.rev == old['rev'] and meta.path_display == old['path_display']
        download_meta, response = db.files_download('rev:' + meta.rev)
        try:
            previous = response.content
        finally:
            response.close()
        assert download_meta.id == meta.id and previous == (OUT / 'previous-catalogue.xlsx').read_bytes()
        receipt['status'] = 'SUBMITTING_REVISION_UPDATE'
        save()
        try:
            result = db.files_upload(body, meta.path_display, mode=WriteMode.update(meta.rev), autorename=False, mute=True, strict_conflict=True)
            receipt.update(status='UPLOADED_READBACK_PENDING', upload_response=info(result))
            save()
        except Exception as error:
            receipt.update(status='RESPONSE_UNCONFIRMED', error_type=type(error).__name__)
            save()
        fresh = db.files_get_metadata(meta.id)
        assert fresh.id == meta.id and fresh.path_display == meta.path_display
        assert fresh.size == len(body) and fresh.content_hash == content_hash
        download_meta, response = db.files_download('rev:' + fresh.rev)
        try:
            readback = response.content
        finally:
            response.close()
        assert download_meta.id == meta.id and sha(readback) == sha(body)
        (OUT / 'dropbox-readback.xlsx').write_bytes(readback)
        receipt.update(status='PASS_DROPBOX_REVISION_UPDATE_AND_BYTE_READBACK', current=info(fresh), sha256_readback=sha(readback), verified_utc=datetime.now(timezone.utc).isoformat())
        save()
    pointer = json.loads(pointer_path.read_text())
    assert pointer['current_app_review_workbook'] == before_pointer['current_app_review_workbook']
    updated = dict(pointer['current_app_review_workbook'])
    updated.update(path=str(OUT / 'catalogue_wall_sculptures.xlsx'), sha256=sha(body), dropbox=receipt['current'], dropbox_receipt=str(receipt_path), dropbox_receipt_sha256=sha(receipt_path.read_bytes()), verification=str(OUT / 'verification.json'), verification_sha256=sha((OUT / 'verification.json').read_bytes()))
    updated['saatchi_native_publication_update'] = dict(verified_utc=receipt['verified_utc'], scope=plan['scope'], plan=str(OUT / 'plan.json'), independent_verification=str(OUT / 'independent-verification.json'), newly_published_records=plan['new_native_publications_recorded'], held_native_drafts=plan['new_native_drafts_recorded'], whole_catalogue_publication_implied=False)
    pointer['current_app_review_workbook'] = updated
    temporary = pointer_path.with_suffix('.native-observation-update.tmp')
    temporary.write_text(json.dumps(pointer, indent=2) + '\n')
    temporary.replace(pointer_path)
print(json.dumps(receipt, indent=2))
