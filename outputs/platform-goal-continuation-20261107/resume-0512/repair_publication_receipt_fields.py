"""Complete six legacy receipt fields from their retained native publication proof."""
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path('/Users/tprice/Documents/boldstone')
OUT = Path(__file__).parent
path = ROOT / 'outputs/catalogue-marketplace-publication-20261101/saatchi-current/primary-draft-receipts.json'
before = path.read_bytes()
rows = json.loads(before)
patches = []
for row in rows:
    if row.get('status') != 'PUBLISHED_NATIVE_READBACK_VERIFIED' or row.get('verified_visibility') == 'Published':
        continue
    native_id = row['artwork_id']
    proof_path = Path(row['native_evidence'])
    if not proof_path.is_absolute():
        proof_path = ROOT / proof_path
    proof = proof_path.read_text().split('Selected text:')[0]
    assert f'saatchiart.com/en-gb/studio/art/{native_id}/overview' in proof
    assert 'text Visibility:  Published' in proof and row['title'] in proof
    assert f'Artwork Price ${row["price_usd"]:,}' in proof or f'Artwork Price ${row["price_usd"]}' in proof
    assert f'Shipping Weight {row["packed_weight_kg"]} kg' in proof
    assert 'Quantity Total Run 50 Sold on Saatchi Art 0 For Sale 1' in proof
    assert row['public_url'].endswith('/' + native_id + '/view')
    row.update(verified_visibility='Published', publication_evidence=str(proof_path.relative_to(ROOT)),
               verified_utc=row['published_utc'])
    patches.append(dict(native_id=native_id, sku=row['sku'], evidence=str(proof_path),
                        evidence_sha256=hashlib.sha256(proof_path.read_bytes()).hexdigest()))
assert len(patches) == 6
backup = OUT / 'saatchi-native-receipts-before-schema-repair.json'
assert not backup.exists()
backup.write_bytes(before)
spec = importlib.util.spec_from_file_location('saatchi', ROOT / 'catalogue-review/scripts/prepare_saatchi_catalogue.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
temporary = OUT / 'saatchi-native-receipts-repaired.json'
temporary.write_text(json.dumps(rows, indent=2) + '\n')
bindings = module.native_artwork_bindings(temporary)
assert len(bindings) == len(set(bindings.values())) == len(rows) + 2
assert path.read_bytes() == before
path.write_bytes(temporary.read_bytes())
audit = dict(status='PASS_SIX_NATIVE_RECEIPT_SCHEMAS_REPAIRED', native_bindings=len(bindings),
             previous_sha256=hashlib.sha256(before).hexdigest(),
             repaired_sha256=hashlib.sha256(path.read_bytes()).hexdigest(), patches=patches,
             native_platform_writes=0, binding_changes=0)
(OUT / 'receipt-schema-repair-verification.json').write_text(json.dumps(audit, indent=2) + '\n')
print(json.dumps({k:v for k,v in audit.items() if k!='patches'}))
