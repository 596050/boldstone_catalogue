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
from dropbox.exceptions import ApiError

read = lambda name: json.loads((OUT / name).read_text())
sha = lambda data: hashlib.sha256(data).hexdigest()
body = (OUT / 'catalogue_wall_sculptures.xlsx').read_bytes()
plan, verification, independent = read('plan.json'), read('verification.json'), read('independent-verification.json')
assert verification['status'] == independent['status'] == 'PASS'
assert verification['sha256'] == independent['sha256'] == sha(body)
assert independent['independently_verified_cells'] == len(plan['patches'])
native_check=read('google-master-verification.json')
assert native_check['status']=='PASS' and native_check['owner']=='info@boldstone.co.uk'
assert native_check['source_master_sha256']==sha(body)
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
        receipt['backups']=[]
        folder='/BOLDSTONE MASTER/Products/01 Wall Sculptures/_Documents_Catalogue/'
        for filename,local in [('catalogue_wall_sculptures_google_sheets_backup.xlsx','google-native-master-backup.xlsx'),
                               ('pinterest_wall_sculptures.csv','pinterest_wall_sculptures.csv'),
                               ('pinterest_wall_sculptures.xlsx','pinterest_wall_sculptures.xlsx')]:
            payload=(OUT/local).read_bytes()
            expected_hash=sha(b''.join(hashlib.sha256(payload[i:i+4194304]).digest() for i in range(0,len(payload),4194304)))
            target=folder+filename
            try:
                prior=db.files_get_metadata(target)
            except ApiError as error:
                if not (error.error.is_path() and error.error.get_path().is_not_found()):raise
                prior=None
            event=dict(path=target,source=local,sha256=sha(payload),status='SUBMITTING')
            receipt['backups'].append(event);save()
            if prior is None or prior.content_hash!=expected_hash:
                mode=WriteMode.update(prior.rev) if prior else WriteMode.add
                try:
                    uploaded=db.files_upload(payload,target,mode=mode,autorename=False,mute=True,strict_conflict=True)
                    event.update(status='READBACK_PENDING',upload_response=info(uploaded));save()
                except Exception as error:
                    event.update(status='RESPONSE_UNCONFIRMED',error_type=type(error).__name__);save()
            fresh_backup=db.files_get_metadata(target)
            assert fresh_backup.content_hash==expected_hash and fresh_backup.size==len(payload)
            downloaded_meta,response=db.files_download('rev:'+fresh_backup.rev)
            try:downloaded=response.content
            finally:response.close()
            assert sha(downloaded)==sha(payload) and downloaded_meta.id==fresh_backup.id
            event.update(status='PASS_BYTE_READBACK',current=info(fresh_backup),verified_utc=datetime.now(timezone.utc).isoformat());save()
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
    destinations=read('google-sheet-destinations.json')
    updated['channel_import_refresh_20261107'] = dict(verified_utc=receipt['verified_utc'],scope=plan['scope'],plan=str(OUT/'plan.json'),
        independent_verification=str(OUT/'independent-verification.json'),google_master_url=destinations['master_url'],
        google_owner=destinations['owner'],pinterest_feed_url=destinations['pinterest_url'],pinterest_feed_products=176,
        google_master_verification=str(OUT/'google-master-verification.json'),backup_receipts=receipt['backups'],
        native_publication_statuses_are_dated_observations=True)
    pointer['current_app_review_workbook'] = updated
    temporary = pointer_path.with_suffix('.native-observation-update.tmp')
    temporary.write_text(json.dumps(pointer, indent=2) + '\n')
    temporary.replace(pointer_path)
print(json.dumps(receipt, indent=2))
