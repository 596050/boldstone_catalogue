"""Reconcile the one saved native ID and its verified publication in place."""
import hashlib
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/Users/tprice/Documents/boldstone')
OUT = Path(__file__).parent
read = lambda path: json.loads(path.read_text())
intent_path = OUT / 'saatchi-crater-iii-create-intent.json'
intent = read(intent_path)
native_id = intent['native_artwork_id']
assert native_id == '14396897' and intent['sku'] == 'SQ6211184'
proof_path = OUT / 'evidence/saatchi-14396897-after-publish-readback.txt'
proof = proof_path.read_text()
assert f'saatchiart.com/en-gb/studio/art/{native_id}/overview' in proof
assert 'text Visibility:  Published' in proof and intent['title'] in proof
assert 'Artwork Price $205' in proof and 'Shipping Weight 13 kg' in proof
assert 'Quantity Total Run 50 Sold on Saatchi Art 0 For Sale 1' in proof
public_path = OUT / 'evidence/saatchi-14396897-public-page.txt'
public = public_path.read_text()
public_url = 'https://www.saatchiart.com/en-gb/art/Sculpture-Crater-Moon-III-Verdigris-and-Rust-Finish/3090713/14396897/view'
assert '/3090713/14396897/view' in public and 'button ADD TO CART' in public and 'heading £293' in public
for country, usd in [('uk', 191), ('us', 201)]:
    text = (OUT / f'evidence/saatchi-14396897-saved-{country}-shipping-preview.txt').read_text()
    assert 'Artwork Price' in text and f'Paid by Collector US$ {usd}' in text
registry_path = ROOT / 'outputs/catalogue-marketplace-publication-20261101/saatchi-current/primary-draft-receipts.json'
rows = read(registry_path)
old_rows = json.loads(json.dumps(rows))
matches = [r for r in rows if r['sku'] == intent['sku'] or r['artwork_id'] == native_id]
assert len(matches) == 1 and matches[0]['sku'] == intent['sku'] and matches[0]['artwork_id'] == native_id
row = matches[0]
receipt = dict(catalogue_id=intent['catalogue_id'], sku=intent['sku'], title=intent['title'], artwork_id=native_id, status='PUBLISHED_NATIVE_AND_PUBLIC_BUYING_ROUTE_VERIFIED', public_url=public_url, artwork_price_usd=205, packing_allowance_gbp=35, packed_weight_estimate_kg=13, packed_dimensions_cm_estimate=[44, 44, 25], packaging='Crate', edition_size=50, available_units=1, creation_year=2026, creation_year_is_estimate=True, ready_to_hang=False, outdoor_safe=True, public_uk_all_in_price_gbp=293, native_shipping_uk_usd=191, native_shipping_us_usd=201, app_photo_changes=0, photo_id=row['primary_photo_id'], photo_sha256=row['primary_sha256'], verified_utc=datetime.now(timezone.utc).isoformat(), identity_evidence=str(proof_path.relative_to(ROOT)), public_evidence=str(public_path.relative_to(ROOT)), screenshot=str((OUT / 'evidence/saatchi-14396897-public-page.png').relative_to(ROOT)))
if row['status'] != 'PUBLISHED_NATIVE_READBACK_VERIFIED':
    (OUT / 'primary-draft-registry-before-crater-publication.json').write_text(json.dumps(old_rows, indent=2) + '\n')
row.update(status='PUBLISHED_NATIVE_READBACK_VERIFIED', public_url=public_url, verified_visibility='Published', publication_evidence=str(proof_path.relative_to(ROOT)), verified_utc=receipt['verified_utc'], publication_receipt=str((OUT / 'saatchi-crater-publication-receipt.json').relative_to(ROOT)), published_verified_utc=receipt['verified_utc'])
for before, after in zip(old_rows, rows):
    if before['artwork_id'] != native_id:
        assert before == after
spec = importlib.util.spec_from_file_location('saatchi', ROOT / 'catalogue-review/scripts/prepare_saatchi_catalogue.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
temporary = registry_path.with_suffix('.publication.tmp.json')
temporary.write_text(json.dumps(rows, indent=2) + '\n')
bindings = module.native_artwork_bindings(temporary)
assert len(bindings) == len(set(bindings.values())) == 113
temporary.replace(registry_path)
packet_path = OUT / 'context-upload-packets.json'
packets = read(packet_path)
packet = next(p for p in packets if p['sku'] == intent['sku'])
packet.update(native_artwork_id=native_id, native_action='UPDATE_EXISTING_NATIVE_ID_ONLY', publication_status='PUBLISHED_VERIFIED', native_public_url=public_url, publication_receipt=str(OUT / 'saatchi-crater-publication-receipt.json'))
packet_path.write_text(json.dumps(packets, ensure_ascii=False, indent=2) + '\n')
intent.update(status='PUBLISHED_NATIVE_AND_PUBLIC_VERIFIED', published_verified_utc=receipt['verified_utc'], public_url=public_url)
intent_path.write_text(json.dumps(intent, indent=2) + '\n')
(OUT / 'saatchi-crater-publication-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps(dict(status='PASS_SAME_ID_PUBLICATION_RECONCILED', artwork_id=native_id, unique_bindings=len(bindings), published=113, public_add_to_cart=True)))
