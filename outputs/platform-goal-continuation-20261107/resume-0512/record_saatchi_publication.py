"""Record an exact existing native ID only after full saved-publication evidence."""
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path('/Users/tprice/Documents/boldstone')
OUT = Path(__file__).parent


def main():
    intent_path = Path(sys.argv[1]).resolve()
    packet_path = Path(sys.argv[2]).resolve()
    intent = json.loads(intent_path.read_text())
    packet = json.loads(packet_path.read_text())
    assert intent['status'] == 'PUBLISHED_NATIVE_READBACK_VERIFIED'
    assert (intent['sku'], intent['catalogue_id'], intent['title']) == (
        packet['sku'], packet['catalogue_id'], packet['title'])
    native_id = str(intent['native_artwork_id'])
    evidence_dir = intent_path.parent / 'evidence'
    proof_path = evidence_dir / f'saatchi-{native_id}-after-publish-readback.txt'
    full_path = evidence_dir / f'saatchi-{native_id}-overview-verified.txt'
    proof = proof_path.read_text().split('Selected text:')[0]
    detail = full_path.read_text()
    assert f'saatchiart.com/en-gb/studio/art/{native_id}/overview' in proof
    assert 'text Visibility:  Published' in proof and packet['title'] in proof
    selected = re.search(r'Selected text: ```\n([\s\S]*?)\n```', detail).group(1)
    normal = lambda value: ' '.join(value.split())
    assert normal(packet['description']) in normal(selected)
    assert f'Artwork Price ${packet["target_artwork_price_usd"]:,}' in proof or f'Artwork Price ${packet["target_artwork_price_usd"]}' in proof
    assert f'Shipping Weight {packet["native_packed_weight_kg_estimate"]} kg' in proof
    assert 'Quantity Total Run 50 Sold on Saatchi Art 0 For Sale 1' in proof
    assert 'Ready to Hang No' in proof and 'Outdoor Safe Yes' in proof
    assert hashlib.sha256(Path(packet['photo']['native_upload_path']).read_bytes()).hexdigest() == packet['photo']['native_upload_sha256']
    public_path = re.search(r'link [^\n]*Value: (saatchiart\.com/[^\s]+/' + native_id + r'/view)', proof).group(1)
    public_url = 'https://www.' + public_path
    registry_path = ROOT / 'outputs/catalogue-marketplace-publication-20261101/saatchi-current/primary-draft-receipts.json'
    records = json.loads(registry_path.read_text())
    before = json.loads(json.dumps(records))
    matches = [r for r in records if r['sku'] == packet['sku'] or str(r['artwork_id']) == native_id]
    assert len(matches) == 1
    record = matches[0]
    assert record['sku'] == packet['sku'] and str(record['artwork_id']) == native_id
    record.update(status='PUBLISHED_NATIVE_READBACK_VERIFIED', verified_visibility='Published',
                  public_url=public_url, publication_evidence=str(proof_path.relative_to(ROOT)),
                  verified_utc=intent['published_verified_utc'])
    for old, new in zip(before, records):
        if str(old['artwork_id']) != native_id:
            assert old == new
    spec = importlib.util.spec_from_file_location('saatchi', ROOT / 'catalogue-review/scripts/prepare_saatchi_catalogue.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    temporary = registry_path.with_suffix('.publication.tmp.json')
    temporary.write_text(json.dumps(records, indent=2) + '\n')
    bindings = module.native_artwork_bindings(temporary)
    assert len(bindings) == len(set(bindings.values())) == len(records) + 2
    temporary.replace(registry_path)
    intent['public_url'] = public_url
    intent_path.write_text(json.dumps(intent, indent=2) + '\n')
    receipt = dict(status='PUBLISHED_NATIVE_READBACK_VERIFIED', native_id=native_id,
                   sku=packet['sku'], catalogue_id=packet['catalogue_id'], title=packet['title'],
                   public_url=public_url, verified_utc=intent['published_verified_utc'],
                   description_verified=True, dimensions_cm=packet['dimensions_cm'],
                   artwork_price_usd=packet['target_artwork_price_usd'], edition_size=50,
                   edition_scope='Saatchi Art only', creation_year=2026, creation_year_is_estimate=True,
                   available_units=1, packaging='Crate',
                   packed_weight_estimate_kg=packet['native_packed_weight_kg_estimate'],
                   packed_cm_estimate=packet['packed_dimensions_cm_estimate'],
                   photo_id=packet['photo']['image_id'], photo_sha256=packet['photo']['native_upload_sha256'],
                   publication_evidence=str(proof_path.relative_to(ROOT)),
                   description_evidence=str(full_path.relative_to(ROOT)),
                   public_purchase_route_verified=False, app_photo_changes=0)
    (OUT / f'saatchi-publication-{packet["catalogue_id"]}.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(dict(status='PASS_PUBLICATION_RECONCILED', native_id=native_id,
                          unique_bindings=len(bindings), public_url=public_url)))


if __name__ == '__main__':
    main()
