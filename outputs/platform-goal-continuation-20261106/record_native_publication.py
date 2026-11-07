"""Reconcile an existing bound artwork from its native Published readback."""
import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path('/Users/tprice/Documents/boldstone')
OUT = Path(__file__).parent
intent_path = Path(sys.argv[1])
intent = json.loads(intent_path.read_text())
native_id, sku = intent['native_artwork_id'], intent['sku']
assert intent['status'] == 'PUBLISHED_NATIVE_READBACK_VERIFIED'
proof_path = OUT / f'evidence/saatchi-{native_id}-after-publish-readback.txt'
proof = proof_path.read_text().split('Selected text:')[0]
assert f'saatchiart.com/en-gb/studio/art/{native_id}/overview' in proof
assert 'text Visibility:  Published' in proof and intent['title'] in proof
public_path = re.search(r'link [^\n]*Value: (saatchiart\.com/[^\s]+/' + native_id + r'/view)', proof).group(1)
public_url = 'https://www.' + public_path
assert f'Artwork Price ${intent["price_target_usd"]:,}' in proof or f'Artwork Price ${intent["price_target_usd"]}' in proof
assert f'Shipping Weight {intent["packed_weight_estimate_kg"]} kg' in proof
assert 'Quantity Total Run 50 Sold on Saatchi Art 0 For Sale 1' in proof
assert 'Ready to Hang No' in proof and 'Outdoor Safe Yes' in proof
packet_paths = [OUT / n for n in ['context-upload-packets.json', 'ammonite-upload-packet.json', 'moon-fish-upload-packet.json', 'lunar-phase-iv-upload-packet.json']]
found = [(path, records, record) for path in packet_paths for records in [json.loads(path.read_text())] for record in records if record['sku'] == sku]
assert len(found) == 1
packet_path, packets, packet = found[0]
assert packet['native_artwork_id'] == native_id
detail_path = OUT / f'evidence/saatchi-{native_id}-overview-verified.txt'
detail = detail_path.read_text()
selected = re.search(r'Selected text: ```\n([\s\S]*?)\n```', detail).group(1)
normal = lambda s: ' '.join(s.split())
assert normal(packet['description']) in normal(selected)
registry_path = ROOT / 'outputs/catalogue-marketplace-publication-20261101/saatchi-current/primary-draft-receipts.json'
rows = json.loads(registry_path.read_text())
before = json.loads(json.dumps(rows))
matches = [r for r in rows if r['sku'] == sku or r['artwork_id'] == native_id]
assert len(matches) == 1 and matches[0]['sku'] == sku and matches[0]['artwork_id'] == native_id
row = matches[0]
row.update(status='PUBLISHED_NATIVE_READBACK_VERIFIED', verified_visibility='Published', public_url=public_url, publication_evidence=str(proof_path.relative_to(ROOT)), verified_utc=intent['published_verified_utc'])
for previous, current in zip(before, rows):
    if previous['artwork_id'] != native_id:
        assert previous == current
spec = importlib.util.spec_from_file_location('saatchi', ROOT / 'catalogue-review/scripts/prepare_saatchi_catalogue.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
temporary = registry_path.with_suffix('.publication.tmp.json')
temporary.write_text(json.dumps(rows, indent=2) + '\n')
bindings = module.native_artwork_bindings(temporary)
assert len(bindings) == len(set(bindings.values())) == len(rows) + 2
temporary.replace(registry_path)
packet.update(native_action='UPDATE_EXISTING_NATIVE_ID_ONLY', publication_status='PUBLISHED_VERIFIED', native_public_url=public_url)
packet_path.write_text(json.dumps(packets, ensure_ascii=False, indent=2) + '\n')
intent['public_url'] = public_url
intent_path.write_text(json.dumps(intent, indent=2) + '\n')
receipt = dict(status='PUBLISHED_NATIVE_READBACK_VERIFIED', native_id=native_id, catalogue_id=intent['catalogue_id'], sku=sku, title=intent['title'], public_url=public_url, verified_utc=intent['published_verified_utc'], description_verified=True, dimensions_cm=packet['dimensions_cm'], creation_year=2026, creation_year_is_estimate=True, edition_size=50, available_units=1, artwork_price_usd=intent['price_target_usd'], packing_allowance_gbp=packet['packing_allowance_gbp'], packed_weight_estimate_kg=packet['native_packed_weight_kg_estimate'], packed_cm_estimate=packet['packed_dimensions_cm_estimate'], packaging='Crate', ready_to_hang=False, outdoor_safe=True, photo_id=packet['photo']['image_id'], native_photo_path=packet['photo']['native_upload_path'], photo_sha256=packet['photo']['native_upload_sha256'], app_photo_changes=0, publication_evidence=str(proof_path.relative_to(ROOT)), description_evidence=str(detail_path.relative_to(ROOT)), public_purchase_route_verified=False)
(OUT / f'saatchi-publication-{intent["catalogue_id"]}.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(dict(status='PASS_EXISTING_NATIVE_ID_PUBLICATION_RECONCILED', native_id=native_id, sku=sku, unique_native_bindings=len(bindings), public_url=public_url)))
