"""Preserve the remaining upload queue after binding the two Vine artworks."""
import hashlib
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

ROOT = Path('/Users/tprice/Documents/boldstone')
OUT = Path(__file__).parent
read = lambda p: json.loads(p.read_text())
pointer = read(ROOT / 'sculpture-catalogue/current-master.json')['current_app_review_workbook']
receipt = read(OUT / 'workbook/dropbox-receipt.json')
assert receipt['status'] == 'PASS_DROPBOX_REVISION_UPDATE_AND_BYTE_READBACK'
assert pointer['sha256'] == receipt['sha256_readback']
spec = importlib.util.spec_from_file_location('saatchi', ROOT / 'catalogue-review/scripts/prepare_saatchi_catalogue.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
bindings = module.native_artwork_bindings(ROOT / 'outputs/catalogue-marketplace-publication-20261101/saatchi-current/primary-draft-receipts.json')
assert len(bindings) == 127
assert bindings['BOLD-49CB2EDD232C'] == '14397869'
assert bindings['BOLD-53239DE28BCA'] == '14397795'
prepared, bound = [], []
for path in sorted((OUT / 'packets').glob('*.json')):
    packet = read(path)
    if packet['sku'] in bindings:
        bound.append({'sku': packet['sku'], 'native_artwork_id': bindings[packet['sku']]})
        continue
    assert not packet.get('native_artwork_id')
    photo = packet['photo']
    file = Path(photo['native_upload_path'])
    assert hashlib.sha256(file.read_bytes()).hexdigest() == photo['native_upload_sha256']
    with Image.open(file) as image:
        assert image.width >= 1500 and image.height >= 1200
        assert image.mode == 'RGB' and image.format in ('JPEG', 'PNG')
    packet['current_source_workbook_sha256'] = pointer['sha256']
    packet['native_action'] = 'RECONCILE_CURRENT_STUDIO_BEFORE_CREATE_ONCE'
    prepared.append({'packet': packet, 'validation': {'packet_path': str(path),
        'sku': packet['sku'], 'native_artwork_id': None,
        'status': 'PREPARED_NOT_UPLOADED_VERIFICATION_GATE_PENDING'}})
assert len(prepared) == 12 and len(bound) == 1
(OUT / 'remaining-native-ready-queue.json').write_text(json.dumps(prepared, ensure_ascii=False, indent=2) + '\n')
result = dict(status='PROGRESS_GOAL_INCOMPLETE', checked_utc=datetime.now(timezone.utc).isoformat(),
    current_workbook_sha256=pointer['sha256'], dropbox_revision=receipt['current']['rev'],
    publication=dict(sku='BOLD-53239DE28BCA', artwork_id='14397795',
        url='https://www.saatchiart.com/en-gb/art/Sculpture-Gleneagles-Vine-I-White/3090713/14397795/view'),
    held_draft=dict(sku='BOLD-49CB2EDD232C', artwork_id='14397869',
        reason='Explicit captchaFailure on price save. Existing filled form retained for manual save.'),
    last_complete_native_portfolio_audit=dict(published=126, before_new_held_draft=True),
    native_bindings=127, prepared_missing=12, other_missing_photo_or_review_holds=37,
    ups_quote=dict(amount_gbp=61.25, service='UPS Expedited', origin='BA2 7BX',
        sample_destination='10001', duties_taxes_included=False,
        native_chairish_shipping_changed=False),
    owner_actions_pending=['eBay 14 submits and Patina title-only revise legal acceptance',
        '51 oversized eBay drafts need a supported shipping choice', 'in6192 sign-in',
        'Saatchi 14397869 manual verification/save', 'UPS landed-cost sign-in and terms'],
    requested_furnitures_faire_instagram_deliverables='Verified complete. No duplicate products or posts created.')
(OUT / 'progress-result.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({'status': result['status'], 'remaining_prepared': len(prepared), 'bound_draft_excluded': bound}))
