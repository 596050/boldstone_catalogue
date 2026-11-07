"""Prepare exact-ID native observations without overwriting catalogue truth."""
import hashlib
import json
import re
import shutil
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/Users/tprice/Documents/boldstone')
OUT = Path(__file__).parent
BOOK = OUT / 'native-workbook'
BOOK.mkdir(exist_ok=True)
sys.path.insert(0, str(ROOT / 'catalogue-review/scripts'))
from import_saatchi_snapshot import Xlsx, column

read = lambda path: json.loads(path.read_text())
sha = lambda body: hashlib.sha256(body).hexdigest()
stamp = lambda value: datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
pointer = read(ROOT / 'sculpture-catalogue/current-master.json')
source = pointer['current_app_review_workbook']
source_path = Path(source['path'])
assert sha(source_path.read_bytes()) == source['sha256']
shutil.copyfile(source_path, BOOK / 'previous-catalogue.xlsx')
(BOOK / 'source-pointer-before.json').write_text(json.dumps(pointer, indent=2) + '\n')
(BOOK / 'previous-dropbox-metadata.json').write_text(json.dumps(source['dropbox'], indent=2) + '\n')
with urllib.request.urlopen('http://127.0.0.1:8767/api/specifications', timeout=120) as response:
    app = json.load(response)
(BOOK / 'app-specifications.json').write_text(json.dumps(app, indent=2) + '\n')
old = Xlsx(BOOK / 'previous-catalogue.xlsx')
headers = {old.value('Wall Sculptures', column(n) + '7'): column(n) for n in range(1, 633)}
assert None not in headers and len(headers) == 632
row_by_id = {old.value('Wall Sculptures', 'AA' + str(r)): r for r in range(8, 189)}
packets = [r for name in ['context-upload-packets.json', 'ammonite-upload-packet.json', 'moon-fish-upload-packet.json', 'lunar-phase-iv-upload-packet.json'] for r in read(OUT / name)]
packet_by_sku = {r['sku']: r for r in packets}
registry = read(ROOT / 'outputs/catalogue-marketplace-publication-20261101/saatchi-current/primary-draft-receipts.json')
patches = []
updates = []


def put(row, name, value):
    address = headers[name] + str(row)
    before = old.value('Wall Sculptures', address)
    if before == value:
        return
    assert old.formula('Wall Sculptures', address) is None, (name, 'refusing to overwrite a formula')
    patches.append(dict(sheet='Wall Sculptures', cell=address, before=before, before_formula=None, value=value, formula=None))


receipts = [read(path) for path in sorted(OUT.glob('saatchi-publication-*.json'))]
crater = read(OUT / 'saatchi-crater-publication-receipt.json')
crater.update(native_id=crater['artwork_id'], publication_evidence=crater['identity_evidence'], description_verified=False)
receipts.append(crater)
assert len({r['sku'] for r in receipts}) == len(receipts)
for receipt in receipts:
    sku, native_id = receipt['sku'], receipt['native_id']
    packet = packet_by_sku[sku]
    row = row_by_id[receipt['catalogue_id']]
    assert old.value('Wall Sculptures', 'AQ' + str(row)) == sku
    assert packet['native_artwork_id'] == native_id and packet['publication_status'] == 'PUBLISHED_VERIFIED'
    binding = next(r for r in registry if r['sku'] == sku)
    assert binding['artwork_id'] == native_id and binding['status'] == 'PUBLISHED_NATIVE_READBACK_VERIFIED'
    proof_path = ROOT / receipt['publication_evidence']
    proof = proof_path.read_text().split('Selected text:')[0]
    assert f'studio/art/{native_id}/overview' in proof and 'text Visibility:  Published' in proof
    dims = [float(x) for x in re.search(r'text Dimensions ([\d.]+) W x ([\d.]+) H x ([\d.]+) D centimeters', proof).groups()]
    assert dims == packet['dimensions_cm']
    prices = re.search(r'Artwork Price \$([\d,.]+) \(£([\d,.]+)\) Your Commission \$([\d,.]+) \(£([\d,.]+)\)', proof)
    assert prices, (sku, 'native price readback missing')
    price_usd, approx_gbp, commission_usd, commission_approx_gbp = [float(x.replace(',', '')) for x in prices.groups()]
    assert price_usd == packet['target_artwork_price_usd']
    weight = float(re.search(r'Packaging Type Crate Shipping Weight ([\d.]+) kg', proof).group(1))
    assert weight == packet['native_packed_weight_kg_estimate']
    keywords = re.search(r'text Keywords ([^\n]+)', proof).group(1)
    public_url = binding['public_url']
    assert public_url.endswith('/' + native_id + '/view')
    observed = {
        'saatchi_snapshot_scope': 'Current exact-ID native Studio readback and full description verification where recorded; native/public purchase verification scopes are separate.',
        'saatchi_source_file': str(proof_path),
        'saatchi_source_date': stamp(receipt['verified_utc']),
        'saatchi_source_sha256': sha(proof_path.read_bytes()),
        'saatchi_match_basis': 'Existing saved creation receipt binds this exact native artwork ID to the catalogue SKU; publication read back without recreation.',
        'saatchi_catalogue_sku': sku,
        'saatchi_update_state': f'Published native artwork {native_id}, verified {receipt["verified_utc"]}. One supplied panel; 50-edition Saatchi cap and one available unit. Crate dimensions/weight and packing budget remain planning estimates. Other platform changes are not implied.',
        'saatchi_observed_artwork_id': native_id,
        'saatchi_observed_title': packet['title'],
        'saatchi_observed_visibility': 'Published',
        'saatchi_observed_availability': 'For Sale',
        'saatchi_observed_public_listing': public_url,
        'saatchi_observed_studio_page': f'https://www.saatchiart.com/en-gb/studio/art/{native_id}/overview',
        'saatchi_observed_category': 'Sculpture',
        'saatchi_observed_subject': 'Abstract',
        'saatchi_observed_year_produced': 2026,
        'saatchi_observed_medium_method': 'Relief',
        'saatchi_observed_materials': 'Plaster',
        'saatchi_observed_styles': 'Abstract',
        'saatchi_observed_width_cm': dims[0],
        'saatchi_observed_height_cm': dims[1],
        'saatchi_observed_depth_cm': dims[2],
        'saatchi_observed_multi_panel': False,
        'saatchi_observed_panels': 1,
        'saatchi_observed_keywords': keywords,
        'saatchi_observed_keyword_count': len(keywords.split(', ')),
        'saatchi_observed_edition': 'Limited Edition; native Total Run 50 (edition cap, not 50 physical casts)',
        'saatchi_observed_units_available': 1,
        'saatchi_observed_units_sold': 0,
        'saatchi_observed_installation': 'Wall-Mounted',
        'saatchi_observed_ready_to_hang': 'No',
        'saatchi_observed_suitable_for_outdoors': 'Yes',
        'saatchi_observed_packaging': 'Crate',
        'saatchi_observed_shipping_weight_entered_kg': weight,
        'saatchi_observed_ships_from': 'GB',
        'saatchi_observed_artwork_price_usd': price_usd,
        'saatchi_observed_artwork_price_approx_gbp': approx_gbp,
        'saatchi_observed_your_60_share_usd': commission_usd,
        'saatchi_art_edition_update_state': f'Native cap 50 and one available unit verified for artwork {native_id}. Saatchi only. Year 2026 remains an estimated production planning year; physical edition serials and actual total casts produced are not inferred.',
        'saatchi_art_upload_candidate_status': f'PUBLISHED_NATIVE_READBACK_VERIFIED; exact artwork {native_id}; original photo accepted without resizing, app photo purposes and catalogue primary preserved.',
        'saatchi_art_upload_candidate_checked_utc': stamp(receipt['verified_utc']),
    }
    if receipt.get('description_verified'):
        observed.update(saatchi_observed_description=packet['description'], saatchi_observed_description_length_characters=len(packet['description']))
    if receipt.get('native_shipping_uk_usd') is not None:
        observed.update(saatchi_observed_shipping_to_uk_usd=receipt['native_shipping_uk_usd'], saatchi_observed_list_price_to_uk_buyers_usd=price_usd + receipt['native_shipping_uk_usd'], saatchi_observed_shipping_to_us_usd=receipt['native_shipping_us_usd'], saatchi_observed_list_price_to_us_buyers_usd=price_usd + receipt['native_shipping_us_usd'])
    if receipt.get('public_uk_all_in_price_gbp') is not None:
        observed['saatchi_observed_list_price_to_uk_buyers_approx_gbp'] = receipt['public_uk_all_in_price_gbp']
    for name, value in observed.items():
        put(row, name, value)
    updates.append(dict(catalogue_id=receipt['catalogue_id'], sku=sku, native_id=native_id, title=packet['title'], row=row, observed_fields=len(observed), public_url=public_url, description_verified=receipt.get('description_verified', False)))

held = []
for path in sorted(OUT.glob('saatchi-upload-BSI-*.json')):
    intent = read(path)
    if intent['status'] != 'REVIEW_REQUIRED_DESCRIPTION_NOT_SAVED':
        continue
    native_id, sku = intent['native_artwork_id'], intent['sku']
    assert sku not in {r['sku'] for r in receipts}
    packet = packet_by_sku[sku]
    row = row_by_id[intent['catalogue_id']]
    assert old.value('Wall Sculptures', 'AQ' + str(row)) == sku and packet['native_artwork_id'] == native_id
    proof_path = OUT / f'evidence/saatchi-{native_id}-server-overview-before-recovery.txt'
    proof = proof_path.read_text()
    assert intent['title'] in proof and 'text Dimensions -' in proof and 'Visibility:  Draft' in proof
    values = {
        'saatchi_snapshot_scope': 'Exact-ID native draft creation and separate server overview. Description remains blank; no native publication.',
        'saatchi_source_file': str(proof_path),
        'saatchi_source_date': stamp(intent['review_required_utc']),
        'saatchi_source_sha256': sha(proof_path.read_bytes()),
        'saatchi_match_basis': 'Saved native creation receipt binds this artwork ID to the catalogue SKU. Do not recreate.',
        'saatchi_catalogue_sku': sku,
        'saatchi_observed_artwork_id': native_id,
        'saatchi_observed_title': intent['title'],
        'saatchi_observed_visibility': 'Draft',
        'saatchi_observed_studio_page': f'https://www.saatchiart.com/en-gb/studio/art/{native_id}/overview',
        'saatchi_update_state': 'Existing draft primary photograph is saved. Description form does not persist; native server overview remains blank. No publication attempted. Reconcile and complete this exact ID; do not recreate.',
        'saatchi_art_upload_candidate_status': f'DRAFT_PRIMARY_SAVED_DESCRIPTION_SAVE_REQUIRES_REVIEW; exact native artwork {native_id}; no publication.',
        'saatchi_art_upload_candidate_checked_utc': stamp(intent['review_required_utc']),
    }
    for name, value in values.items():
        put(row, name, value)
    held.append(dict(catalogue_id=intent['catalogue_id'], sku=sku, native_id=native_id, title=intent['title'], row=row, observed_fields=len(values), state='DRAFT_PRIMARY_SAVED_DESCRIPTION_SAVE_REQUIRES_REVIEW'))

assert len({p['cell'] for p in patches}) == len(patches)
plan = dict(scope='Record newly published Saatchi artworks and held drafts by exact native ID and SKU, preserving app specifications, core/other-channel prices, all formulas, image purposes and packing estimates. Actual native observations remain separate from pricing targets and estimated production/packing information.', created_utc=datetime.now(timezone.utc).isoformat(), source_sha256=source['sha256'], headers=headers, patches=patches, records=updates, held_drafts=held, component_records=181, new_native_publications_recorded=len(updates), new_native_drafts_recorded=len(held), all_native_ids_unique=True)
(BOOK / 'plan.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(dict(status='PREPARED_EXACT_ID_NATIVE_OBSERVATION_UPDATE', published_records=len(updates), cells=len(patches), source_sha256=source['sha256'])))
