import hashlib
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/Users/tprice/Documents/boldstone')
OUT = ROOT / 'outputs/platform-completion-20261105'
registry = ROOT / 'outputs/catalogue-marketplace-publication-20261101/saatchi-current/primary-draft-receipts.json'
read = lambda p: json.loads(p.read_text())
prior = read(registry)
receipts = read(OUT / 'saatchi-native-receipts.json')
packets = read(OUT / 'saatchi-new-publication-packet.json') + read(OUT / 'saatchi-pair-publication-packet.json')
photos = {p['catalogue_id']: p['photo'] for p in packets}
now = datetime.now(timezone.utc).isoformat()
updated = list(prior)
for r in receipts:
    if r['action'] != 'CREATED_ONCE_AND_PUBLISHED':
        assert any(x['artwork_id'] == r['native_id'] and x['sku'] == r['sku'] for x in prior)
        continue
    proof = OUT / f"evidence/saatchi-{r['native_id']}-published.txt"
    assert proof.is_file() and 'Published' in proof.read_text()
    photo = photos[r['catalogue_id']]
    source = Path(photo['local_path'])
    row = dict(sku=r['sku'], catalogue_id=r['catalogue_id'], title=r['title'],
               artwork_id=r['native_id'], url=f"https://www.saatchiart.com/en-gb/studio/art/{r['native_id']}/overview",
               public_url=r['public_url'], primary_photo_id=r['photo_id'],
               primary_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
               status='PUBLISHED_NATIVE_READBACK_VERIFIED', verified_visibility='Published',
               publication_evidence=str(proof.relative_to(ROOT)), verified_utc=now, saved_utc=now)
    existing = [x for x in updated if x['sku'] == row['sku'] or x['artwork_id'] == row['artwork_id']]
    if existing:
        assert len(existing) == 1 and existing[0]['sku'] == row['sku'] and existing[0]['artwork_id'] == row['artwork_id']
    else:
        updated.append(row)
assert updated[:len(prior)] == prior
spec = importlib.util.spec_from_file_location('saatchi', ROOT/'catalogue-review/scripts/prepare_saatchi_catalogue.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
tmp = registry.with_suffix('.pending.json')
tmp.write_text(json.dumps(updated, indent=2)+'\n')
bindings = module.native_artwork_bindings(tmp)
assert len(bindings) == 112 and len(set(bindings.values())) == 112
tmp.replace(registry)
intents = read(OUT/'saatchi-upload-intents.json')
for intent in intents:
    match = next(r for r in receipts if r['catalogue_id'] == intent['catalogue_id'])
    assert intent['native_id'] == match['native_id']
    intent.update(result='PUBLISHED_NATIVE_READBACK_VERIFIED', public_url=match['public_url'], verified_utc=now)
(OUT/'saatchi-upload-intents.json').write_text(json.dumps(intents, indent=2)+'\n')
result = dict(status='PASS', existing_rows_preserved=len(prior), total_creation_receipts=len(updated),
              total_unique_native_bindings=len(bindings), publication_receipts=len(receipts),
              duplicate_skus=0, duplicate_native_ids=0, checked_at=now)
(OUT/'native-binding-registry-update-receipt.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(result))
