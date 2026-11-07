"""Record the exact saved/reopened existing Chairish draft, without implying submission."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import re

OUT = Path(__file__).parent
before = (OUT / 'chairish-37950217-before.txt').read_text().split('Selected text:')[0]
after = (OUT / 'chairish-37950217-reopened.txt').read_text().split('Selected text:')[0]
for label in ['Title of your listing', 'SKU (Optional)', 'Asking Price', 'Width', 'Depth', 'Height', 'Shipping Charge']:
    pattern = r'^\s*\d+ (?:text field|stepper) \(settable(?:, float)?\) ' + re.escape(label) + r', Value: ([^,\n]+)'
    a, b = re.findall(pattern, before, re.M), re.findall(pattern, after, re.M)
    assert len(a) == len(b) == 1 and a == b, (label, a, b)
def photos(text):
    section = text[text.index('container PHOTOS'):text.index('container DESCRIPTION')]
    return re.findall(r'^\s*\d+ Unlabelled image (.*)$', section, re.M)
old_photos, new_photos = photos(before), photos(after)
assert len(old_photos) == 1 and len(new_photos) == 2 and old_photos[0] == new_photos[0]
ready = (OUT / 'chairish-37950217-ready.txt').read_text().split('Selected text:')[0]
assert '/70fa1441-773a-475c-bab6-ad05f1498a26' in photos(ready)[1]
assert new_photos[1] == '/boldstone-acanthus-frond-left-pewter-finish-wall-sculpture-3264?aspect=fit&size=800'
note = 'The additional close-up has a warm colour cast; this listing is for the pewter-toned finish.'
assert note in after and note not in before
photo = OUT / 'acanthus__acanthus-one-leaf-pewter__001.jpg'
assert hashlib.sha256(photo.read_bytes()).hexdigest() == '7cfcee6b8745dca304d512943463079c52b54e5dded2f39dd255cd33da3b896c'
receipt = dict(status='PASS_EXISTING_DRAFT_PHOTO_SAVE_AND_REOPEN',
               catalogue_id='BSI-3635E3DC3434', sku='BOLD-3635E3DC3434', native_id='37950217',
               studio_url='https://www.chairish.com/product/37950217/update',
               previous_photos=1, saved_photos=2, primary_unchanged=True,
               native_photo_paths=new_photos,
               native_photo_identity_evidence='Controlled one-file upload, source SHA, persisted gallery count and visual inspection of the reopened native screenshot. Native transformed image bytes were not independently hashed.',
               added_dropbox_id='id:cnqzTNngPVsAAAAAAAufFw',
               added_dropbox_rev='65ec3441cfca90c0dea29',
               added_original_sha256=hashlib.sha256(photo.read_bytes()).hexdigest(),
               visual_review='Same raised curved relief and brushed surface. The genuine close-up has a warm colour cast; the explicit description note preserves the Pewter sale scope.',
               description_photo_note=note, other_reviewed_fields_unchanged=True,
               app_primary_and_purposes_unchanged=True,
               native_status='Draft', submitted=False, published=False,
               remaining_requirement='Verify an all-in flat lower-48 US delivery quote, including taxes, duties, packing and fees, before submission.',
               evidence=str(OUT / 'chairish-37950217-reopened.txt'),
               evidence_sha256=hashlib.sha256((OUT / 'chairish-37950217-reopened.txt').read_bytes()).hexdigest(),
               verified_utc=datetime.now(timezone.utc).isoformat())
(OUT / 'chairish-37950217-photo-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps({k:receipt[k] for k in ['status','native_id','saved_photos','native_status','submitted']}, indent=2))
