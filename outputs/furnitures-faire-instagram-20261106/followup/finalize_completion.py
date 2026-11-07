"""Publish local completion receipts only after verified native and Dropbox readback."""
from pathlib import Path
import hashlib, json

ROOT = Path('/Users/tprice/Documents/boldstone')
OUT = Path(__file__).parent
PRIOR = OUT.parent
WORK = ROOT / 'outputs/platform-goal-continuation-20261106/workbook-context'
read = lambda p: json.loads(p.read_text())
receipt = read(WORK / 'dropbox-receipt.json')
channel = read(WORK / 'channel-record-verification.json')
independent = read(WORK / 'independent-verification.json')
native = read(OUT / 'furnitures-final-native-verification.json')
assert receipt['status'] == 'PASS_DROPBOX_REVISION_UPDATE_AND_BYTE_READBACK'
assert channel['status'] == 'PASS_EXACT_CHANNEL_RECORDS'
assert native['status'] == 'PASS_ALL_176_NATIVE_SPECIFICATION_FORMS' and native['count'] == 176
assert independent['status'] == 'PASS' and independent['readers_agree']
sha = hashlib.sha256((WORK / 'catalogue_wall_sculptures.xlsx').read_bytes()).hexdigest()
assert sha == receipt['sha256_readback'] == channel['sha256'] == independent['sha256']
pointer = read(ROOT / 'sculpture-catalogue/current-master.json')['current_app_review_workbook']
assert pointer['sha256'] == sha and pointer['dropbox']['rev'] == receipt['current']['rev']
assert pointer['furnitures_separate_specification_fields_verified'] == 176
completion = read(OUT / 'completion.json')
assert len(completion['instagram_published']) == 5
completion.update(status='PASS_REQUESTED_PUBLICATIONS_AND_CATALOGUE_WITH_PLATFORM_LIMITATIONS_RECORDED',
                  furnitures_separate_fields_verified=176, furnitures_separate_fields_pending=0,
                  dropbox_revision=receipt['current']['rev'], dropbox_verified_utc=receipt['verified_utc'],
                  workbook=str(WORK / 'catalogue_wall_sculptures.xlsx'), workbook_sha256=sha,
                  verification=independent, native_field_verification=str(OUT / 'furnitures-final-native-verification.json'),
                  channel_record_verification=str(WORK / 'channel-record-verification.json'),
                  followup_completion=str(OUT / 'final-completion.json'),
                  limitations=[
                      'Faire native prices differ from app retail and other recorded wholesale prices; actual native values and protected models remain separate.',
                      'Faire requests a UK bank account for GBP payouts; owner action required.',
                      'Furnitures payout readiness is unverified: its dashboard says Stripe payouts arrive in a future release.',
                      'Furnitures checkout previously quoted GBP49 UK delivery and advertises free delivery over GBP500; no seller delivery controls were exposed.',
                  ])
for directory in [OUT, PRIOR]:
    current = directory / 'completion.json'
    history = directory / 'completion-before-final-specifications.json'
    if not history.exists(): history.write_bytes(current.read_bytes())
    current.write_text(json.dumps(completion, ensure_ascii=False, indent=2) + '\n')
    pending = directory / 'furnitures-pending-fields.json'
    previous = directory / 'furnitures-pending-fields-before-final.json'
    if pending.exists() and not previous.exists(): previous.write_bytes(pending.read_bytes())
    pending.write_text('[]\n')
(OUT / 'final-completion.json').write_text(json.dumps(completion, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(dict(status=completion['status'], furnitures=176, separate_fields=176,
                      faire=176, instagram=5, dropbox_revision=receipt['current']['rev'],
                      workbook_sha256=sha)))
