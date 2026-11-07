"""Reconcile the prepared queue and persistent blockers without native writes."""
import copy
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

ROOT = Path('/Users/tprice/Documents/boldstone')
RUN = Path(__file__).parent
OUT = RUN/'verified-price-closeout'
sys.path[:0] = [str(ROOT/'catalogue-review'),str(ROOT/'catalogue-review/scripts')]
from import_saatchi_snapshot import Xlsx
from prepare_saatchi_catalogue import native_artwork_bindings

read = lambda p: json.loads(p.read_text())
sha = lambda b: hashlib.sha256(b).hexdigest()
pointer = read(ROOT/'sculpture-catalogue/current-master.json')['current_app_review_workbook']
assert sha(Path(pointer['path']).read_bytes()) == pointer['sha256']
assert Path(pointer['path']).parent == OUT
receipt = read(Path(pointer['dropbox_receipt']))
assert receipt['status'] == 'PASS_DROPBOX_REVISION_UPDATE_AND_BYTE_READBACK'
assert (OUT/'dropbox-readback.xlsx').read_bytes() == Path(pointer['path']).read_bytes()
x = Xlsx(Path(pointer['path']))
s = 'Wall Sculptures'
cols = {x.value(s,a):re.sub(r'\d','',a) for a in x.cells[s] if re.fullmatch('[A-Z]+7',a)}
rows = {x.value(s,'AA'+str(r)):r for r in range(8,189)}
publication = read(ROOT/'outputs/catalogue-marketplace-publication-20261101/current-prepared-catalogue.json')
products = publication['records'] if isinstance(publication,dict) and 'records' in publication else publication
if isinstance(products,dict):
    products = products['products']
scope_skus = {p['sku'] for p in products}
assert len(scope_skus) == 176
bindings = native_artwork_bindings(ROOT/'outputs/catalogue-marketplace-publication-20261101/saatchi-current/primary-draft-receipts.json')
assert len(bindings) == 127 and set(bindings) <= scope_skus
whole = read(RUN/'resume-0720/saatchi-fresh-whole-portfolio.json')
assert whole['published'] == 126 and whole['drafts'] == 1 and whole['qualified_queue_absent'] == 14
stamp = datetime.now(timezone.utc).isoformat()
normalize = lambda v:re.sub('[^a-z0-9]','',v.casefold())
native_titles = {normalize(r['title']) for r in whole['records']}
queue = copy.deepcopy(read(RUN/'resume-0720/remaining-native-ready-queue.json'))
assert len(queue) == 14
(OUT/'packets').mkdir(exist_ok=True)
photo_checks = []
for entry in queue:
    p = entry['packet']
    assert p['sku'] in scope_skus and p['sku'] not in bindings and not p['native_artwork_id']
    assert normalize(p['title']) not in native_titles
    r = rows[p['catalogue_id']]
    assert x.value(s,'AQ'+str(r)) == p['sku']
    assert x.value(s,cols['saatchi_asking_price_usd']+str(r)) == p['target_artwork_price_usd']
    assert p['dimensions_cm'] == [x.value(s,cols[h]+str(r)) for h in ['saatchi_width_cm','saatchi_height_cm','saatchi_depth_cm']]
    assert p['edition_cap'] == 50 and p['edition_scope'] == 'Saatchi Art only' and p['quantity_per_sale'] == 1
    assert 0 < len(p['description']) <= 1000 and p['app_photo_changes'] == 0
    assert all(q in p['description'] for q in ['gypsum-based','Sally Price','3 working days'])
    photo = p['photo']
    original, upload = Path(photo['local_path']), Path(photo['native_upload_path'])
    assert sha(original.read_bytes()) == photo['sha256']
    assert sha(upload.read_bytes()) == photo['native_upload_sha256']
    with Image.open(upload) as im:
        assert im.width >= 1500 and im.height >= 1200 and im.format in ['JPEG','PNG']
        assert (im.width,im.height) == (photo['width'],photo['height'])
        gps = im.getexif().get_ifd(34853) if im.getexif().get(34853) else {}
        assert set(gps) <= {0}, 'Review GPS fields before any image transmission'
        gps_version_only = bool(gps)
        image_size, image_format = im.size, im.format
        if upload != original:
            with Image.open(original) as source:
                assert source.size == im.size and source.convert('RGB').tobytes() == im.convert('RGB').tobytes()
    p['current_source_workbook_sha256'] = pointer['sha256']
    p['whole_native_portfolio_audit'] = str(RUN/'resume-0720/saatchi-fresh-whole-portfolio.json')
    p['current_preflight_utc'] = stamp
    p['save_verification_gate'] = 'Owner verification required: Saatchi explicitly returned captchaFailure=true. No automated save or create retry until resolved and freshly reconciled.'
    photo['gps_location_metadata_present'] = False
    photo['gps_ifd_version_only'] = gps_version_only
    target = OUT/'packets'/f"{p['catalogue_id']}.json"
    target.write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n')
    entry['validation'].update(packet_path=str(target),status='PREPARED_NOT_UPLOADED_OWNER_VERIFICATION_REQUIRED',checked_utc=stamp)
    photo_checks.append(dict(sku=p['sku'],width=image_size[0],height=image_size[1],format=image_format,sha256=photo['native_upload_sha256'],gps_location_metadata_present=False,gps_ifd_version_only=gps_version_only))
queue_skus = {e['packet']['sku'] for e in queue}
holds = read(RUN/'resume-0720/current-35-photo-holds.json')
hold_skus = {x.value(s,'AQ'+str(rows[h['catalogue_id']])) for h in holds}
assert len(hold_skus) == 35 and not (queue_skus & hold_skus)
assert not (set(bindings) & (queue_skus|hold_skus))
assert set(bindings)|queue_skus|hold_skus == scope_skus
(OUT/'remaining-native-ready-queue.json').write_text(json.dumps(queue,ensure_ascii=False,indent=2)+'\n')
(OUT/'current-35-photo-holds.json').write_text(json.dumps(holds,indent=2)+'\n')
pending = read(RUN/'resume-0720/price-updates/14393353.json')
assert pending['phase'] == 'OWNER_VERIFICATION_REQUIRED_RECAPTCHA_REJECTED' and pending['explicit_captcha_failure']
bone = read(RUN/'resume-0720/saatchi-price-update-14393365.json')
assert bone['status'] == 'PASS_PRICE_ONLY_SAVE_AND_RELOAD'
assert x.value(s,'SF23') == 307 and x.value(s,'SH23') == 28
ammonite_row = next(r for r in range(8,189) if x.value(s,cols['saatchi_art_native_artwork_id']+str(r)) == '14393353')
assert x.value(s,cols['saatchi_art_artwork_price_usd']+str(ammonite_row)) == 138
result = dict(status='VERIFIED_PROGRESS_WITH_OWNER_AND_PHOTOGRAPHY_GATES',checked_utc=stamp,
    workbook_sha256=pointer['sha256'],dropbox_revision=receipt['current']['rev'],
    saatchi=dict(published=126,existing_drafts=1,ready_not_uploaded=14,photo_review_holds=35,
                 scope_total=176,verified_native_price_corrections=1,unresolved_native_price_differences=111,
                 manual_save_pending_artwork='14393353',manual_save_pending_value_usd=265,
                 manual_save_current_saved_value_usd=138,explicit_captcha_rejection=True,
                 contextual_primary_acceptance_pending=True),
    ebay_sapr_2972=dict(exact_current_active_skus=110,ready_saved_drafts=14,oversized_saved_drafts=51,
                      condition_overlap_held=1,ready_batch_acceptance_pending=True,
                      frozen_fish_existing_used_item='840091837816',frozen_fish_new_draft='5456511570411'),
    ebay_in6192=dict(prior_saved_drafts=176,prior_verified_date='2026-11-01',current_readback='Owner sign-in required',business_conversion=False,payout_setup=False),
    chairish=dict(pending_review=152,drafts=24,active=0,flat_all_in_lower_48_shipping_unresolved=True,single_photo_drafts=2),
    wescover=dict(last_verified_public=176,verified_date='2026-11-06T17:41:00Z',scope='Public exact ID, SKU, brand, positive available Product schema; not a checkout or whole-gallery audit.'),
    prepared_photo_checks=photo_checks,
    native_writes_from_this_final_reconciliation=0,
    whole_goal_complete=False)
(OUT/'platform-progress-and-handoff.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ['status','workbook_sha256','native_writes_from_this_final_reconciliation','whole_goal_complete']}))
