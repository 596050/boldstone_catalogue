"""Bind an accepted native draft immediately; never recreate an uncertain save."""
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path('/Users/tprice/Documents/boldstone')
OUT = Path(__file__).parent
intent_path = Path(sys.argv[1])
intent = json.loads(intent_path.read_text())
assert intent['status'] == 'SAVED_PRIMARY_DRAFT_NATIVE_ID_VERIFIED'
native_id = intent['native_artwork_id']
assert native_id.isdecimal()
proof_path = OUT / f'evidence/saatchi-{native_id}-description-initial.txt'
proof = proof_path.read_text()
assert f'saatchiart.com/en-gb/studio/art/{native_id}/description' in proof
assert intent['title'] in proof and 'text DRAFT' in proof
assert hashlib.sha256(Path(intent['photo_path']).read_bytes()).hexdigest() == intent['photo_sha256']
packet_paths = [OUT / n for n in ['context-upload-packets.json', 'ammonite-upload-packet.json', 'moon-fish-upload-packet.json', 'lunar-phase-iv-upload-packet.json']]
found = [(path, records, record) for path in packet_paths for records in [json.loads(path.read_text())] for record in records if record['sku'] == intent['sku']]
assert len(found) == 1
packet_path, packets, packet = found[0]
assert packet['catalogue_id'] == intent['catalogue_id']
registry_path = ROOT / 'outputs/catalogue-marketplace-publication-20261101/saatchi-current/primary-draft-receipts.json'
rows = json.loads(registry_path.read_text())
before = json.loads(json.dumps(rows))
matches = [r for r in rows if r['sku'] == intent['sku'] or r['artwork_id'] == native_id]
if matches:
    assert len(matches) == 1 and matches[0]['sku'] == intent['sku'] and matches[0]['artwork_id'] == native_id
else:
    rows.append(dict(sku=intent['sku'], catalogue_id=intent['catalogue_id'], title=intent['title'], artwork_id=native_id, url=f'https://www.saatchiart.com/en-gb/studio/art/{native_id}/overview', primary_photo_id=packet['photo']['image_id'], primary_sha256=intent['photo_sha256'], primary_original_app_use=packet['photo'].get('app_use', 'Additional Listing; catalogue primary unchanged'), status='DRAFT_PRIMARY_ONLY_NOT_PUBLISHED', saved_utc=intent['saved_utc'], identity_evidence=str(proof_path.relative_to(ROOT))))
spec = importlib.util.spec_from_file_location('saatchi', ROOT / 'catalogue-review/scripts/prepare_saatchi_catalogue.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
temporary = registry_path.with_suffix('.register.tmp.json')
temporary.write_text(json.dumps(rows, indent=2) + '\n')
bindings = module.native_artwork_bindings(temporary)
assert len(bindings) == len(set(bindings.values())) == len(rows) + 2
assert rows[:len(before)] == before
temporary.replace(registry_path)
packet.update(native_artwork_id=native_id, native_action='COMPLETE_EXISTING_DRAFT_ONLY', publication_status='DRAFT_PRIMARY_UPLOADED_NOT_PUBLISHED')
packet['photo'].update(native_image_upload_test_still_required=False, native_image_format_accepted=True, native_upload_dimensions_verified=[packet['photo']['width'], packet['photo']['height']])
packet_path.write_text(json.dumps(packets, ensure_ascii=False, indent=2) + '\n')
receipt = dict(status='PASS_APPEND_ONLY_NATIVE_BINDING', sku=intent['sku'], catalogue_id=intent['catalogue_id'], native_id=native_id, previous_rows_preserved=len(before), unique_bindings=len(bindings))
(OUT / f'native-binding-{intent["catalogue_id"]}.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps(receipt))
