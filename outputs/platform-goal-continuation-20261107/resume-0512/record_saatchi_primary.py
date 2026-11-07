"""Append one observed native artwork ID immediately after its first saved primary."""
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path('/Users/tprice/Documents/boldstone')
intent_path, packet_path = [Path(p).resolve() for p in sys.argv[1:3]]
intent = json.loads(intent_path.read_text())
packet = json.loads(packet_path.read_text())
assert intent['status'] == 'SAVED_PRIMARY_DRAFT_NATIVE_ID_VERIFIED'
native_id = intent['native_artwork_id']
assert native_id.isdecimal()
assert (intent['sku'], intent['catalogue_id'], intent['title']) == (packet['sku'], packet['catalogue_id'], packet['title'])
proof_path = intent_path.parent / 'evidence' / f'saatchi-{native_id}-description-initial.txt'
proof = proof_path.read_text().split('Selected text:')[0]
assert f'saatchiart.com/en-gb/studio/art/{native_id}/description' in proof
assert packet['title'] in proof and 'text DRAFT' in proof
assert hashlib.sha256(Path(packet['photo']['native_upload_path']).read_bytes()).hexdigest() == packet['photo']['native_upload_sha256']
registry_path = ROOT / 'outputs/catalogue-marketplace-publication-20261101/saatchi-current/primary-draft-receipts.json'
before = registry_path.read_bytes()
records = json.loads(before)
assert not any(r['sku'] == packet['sku'] or str(r['artwork_id']) == native_id for r in records)
records.append(dict(sku=packet['sku'], catalogue_id=packet['catalogue_id'], title=packet['title'],
                    artwork_id=native_id, url=f'https://www.saatchiart.com/en-gb/studio/art/{native_id}/overview',
                    primary_photo_id=packet['photo']['image_id'], primary_sha256=packet['photo']['native_upload_sha256'],
                    primary_original_app_use=packet['photo'].get('app_use','Existing reviewed photograph; app primary and purposes unchanged'),
                    status='DRAFT_PRIMARY_ONLY_NOT_PUBLISHED', saved_utc=intent['saved_utc'],
                    identity_evidence=str(proof_path.relative_to(ROOT))))
spec = importlib.util.spec_from_file_location('saatchi', ROOT / 'catalogue-review/scripts/prepare_saatchi_catalogue.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
temporary = intent_path.parent / f'bindings-{native_id}.json'
temporary.write_text(json.dumps(records,indent=2)+'\n')
bindings = module.native_artwork_bindings(temporary)
assert len(bindings) == len(set(bindings.values())) == len(records)+2
assert registry_path.read_bytes() == before
registry_path.write_bytes(temporary.read_bytes())
packet.update(native_artwork_id=native_id,native_action='COMPLETE_EXISTING_DRAFT_ONLY')
packet_path.write_text(json.dumps(packet,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(dict(status='PASS_NEW_NATIVE_ID_BOUND_ONCE',native_id=native_id,sku=packet['sku'],native_bindings=len(bindings))))
