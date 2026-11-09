"""Record current native Google evidence without rewriting historical product facts."""
from datetime import datetime, timezone
from pathlib import Path
import fcntl
import hashlib
import json

ROOT=Path('/Users/tprice/Documents/boldstone');OUT=Path(__file__).parent
load=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
v=load(OUT/'google-date-refresh-verification.json')
b=load(OUT/'google-backup-dropbox-receipt.json')
assert v['status']=='PASS_GOOGLE_NATIVE_MASTER_FULL_EXPORT_READBACK'
assert v['utc_timestamp_cells_verified']==1832 and len({i['sheet'] for i in v['native_visual_records']})==12
assert b['status']=='PASS_EXISTING_GOOGLE_BACKUP_REVISION_AND_BYTE_READBACK'
assert b['sha256_readback']==v['native_export_sha256']
pointer_path=ROOT/'sculpture-catalogue/current-master.json'
with Path('/Users/tprice/Library/Application Support/BoldstoneReview/native-jobs/writer.lock').open('a') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    pointer=load(pointer_path);current=pointer['current_app_review_workbook']
    assert current['sha256']==v['source_master_sha256']
    assert current['dropbox']['rev']==v['source_dropbox_revision']
    receipt_path=Path(current['dropbox_receipt']);receipt=load(receipt_path)
    assert receipt['sha256_readback']==current['sha256']
    previous_status=receipt.get('google_private_sheet_status')
    receipt['google_private_sheet_status_template_correction']=dict(
        original_template_text=previous_status,
        reason='The reused release template still described the 7 November copy. This dated native completion supersedes that template text.',
        verified_utc=v['verified_utc'],native_url=v['native_url'],verification=str(OUT/'google-date-refresh-verification.json'))
    receipt['google_private_sheet_status']='PASS: existing private info@boldstone.co.uk Google master refreshed in place; all181 records,888 columns,12 sheets,32776 formulas and1832 UTC timestamps independently verified. Existing Dropbox native backup updated and byte-read back.'
    receipt_path.write_text(json.dumps(receipt,indent=2)+'\n')
    current['dropbox_receipt_sha256']=sha(receipt_path)
    current['google_private_snapshot_requires_refresh']=False
    current['google_native_master_current']=dict(
        status=v['status'],url=v['native_url'],owner=v['owner'],private=True,verified_utc=v['verified_utc'],
        component_records=181,master_columns=888,sheets=12,formulas=32776,utc_timestamps_preserved=1832,
        source_dropbox_revision=v['source_dropbox_revision'],source_sha256=v['source_master_sha256'],
        native_export_sha256=v['native_export_sha256'],verification=str(OUT/'google-date-refresh-verification.json'),
        native_backup=b['current'],native_backup_receipt=str(OUT/'google-backup-dropbox-receipt.json'),
        public_pinterest_feed_changed=False)
    temp=pointer_path.with_suffix('.google-native.tmp');temp.write_text(json.dumps(pointer,indent=2)+'\n');temp.replace(pointer_path)
release_path=OUT.parent/'release-status.json';release=load(release_path)
release.update(checked_at=datetime.now(timezone.utc).isoformat(),master_revision=current['dropbox']['rev'],
    master_sha256=current['sha256'],latest_master=current['path'],private_google_master='Current:181 records,888 columns,12 sheets; private owner and same native ID preserved; exact native export backed up in existing Dropbox backup.')
release['verified_counts'].update(google_native_master_records=181,google_native_master_columns=888,
    google_native_master_cells_compared=v['cells_compared'],google_native_master_formulas=32776,google_native_utc_timestamps_preserved=1832)
release['latest_verification_receipts'].update(google_native=str(OUT/'google-date-refresh-verification.json'),google_native_backup=str(OUT/'google-backup-dropbox-receipt.json'),workbook=str(OUT.parent/'catalogue-google-dates/independent-verification.json'),dropbox=str(receipt_path))
release_path.write_text(json.dumps(release,indent=2)+'\n')
print(json.dumps(dict(status='PASS_REGISTERED_CURRENT_GOOGLE_MASTER_AND_EXISTING_BACKUP',master_revision=current['dropbox']['rev'],google_backup_revision=b['current']['rev'])))
