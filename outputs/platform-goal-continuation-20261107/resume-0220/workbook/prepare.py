"""Prepare a narrow, evidence-backed refresh of seven Saatchi observations."""
import hashlib
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/Users/tprice/Documents/boldstone')
OUT = Path(__file__).parent
sys.path.insert(0, str(ROOT / 'catalogue-review/scripts'))
sys.path.insert(0, str(ROOT / 'catalogue-review'))
from import_saatchi_snapshot import Xlsx
from delete_dropbox import connection

sha = lambda b: hashlib.sha256(b).hexdigest()
save = lambda name, value: (OUT / name).write_text(json.dumps(value, indent=2) + '\n')
pointer = json.loads((ROOT / 'sculpture-catalogue/current-master.json').read_text())
source = Path(pointer['current_app_review_workbook']['path'])
body = source.read_bytes()
assert sha(body) == pointer['current_app_review_workbook']['sha256']
assert not (OUT / 'dropbox-receipt.json').exists(), 'Reconcile any prior submission first'
(OUT / 'previous-catalogue.xlsx').write_bytes(body)
save('source-pointer-before.json', pointer)
book = Xlsx(source)
headers = {book.value('Wall Sculptures', cell): re.sub(r'\d+', '', cell)
           for cell in book.cells['Wall Sculptures']
           if re.fullmatch(r'[A-Z]+7', cell) and book.value('Wall Sculptures', cell)}
row_by_sku = {str(book.value('Wall Sculptures', 'AQ' + str(row))): row for row in range(8, 189)}
receipts = json.loads((ROOT / 'outputs/platform-goal-continuation-20261107/resume-0140/saatchi-publication-receipts.json').read_text())
assert len(receipts) == 6 and len({r['sku'] for r in receipts}) == 6
all_bindings = json.loads((ROOT / 'outputs/catalogue-marketplace-publication-20261101/saatchi-current/primary-draft-receipts.json').read_text())
assert len({r['sku'] for r in all_bindings}) == len(all_bindings)
assert len({r['artwork_id'] for r in all_bindings}) == len(all_bindings)
patches, records = [], []

def record(receipt, fields):
    row = row_by_sku[receipt['sku']]
    assert book.value('Wall Sculptures', 'AA' + str(row)) == receipt['catalogue_id']
    for name, value in fields.items():
        address = headers[name] + str(row)
        before, formula = book.value('Wall Sculptures', address), book.formula('Wall Sculptures', address)
        assert formula is None, (name, address)
        if before != value:
            patches.append(dict(sheet='Wall Sculptures', cell=address, before=before,
                                before_formula=None, value=value, formula=None))
    records.append(dict(sku=receipt['sku'], catalogue_id=receipt['catalogue_id'],
                        native_id=receipt['artwork_id'], title=receipt['title'], row=row,
                        state=receipt['status'], observed_fields=len(fields)))

for r in receipts:
    assert r['status'] == 'PUBLISHED_NATIVE_READBACK_VERIFIED'
    evidence = Path(r['native_evidence'])
    text = evidence.read_text()
    assert f"/art/{r['artwork_id']}/overview" in text
    assert 'text Visibility:  Published' in text
    price = re.search(r'text Price Artwork Price \$([\d,.]+) \(£([\d,.]+)\) Your Commission \$([\d,.]+)', text)
    dims = re.search(r'text Dimensions ([\d.]+) W x ([\d.]+) H x ([\d.]+) D centimeters', text)
    category = re.search(r'text Subject, Category, Year Subject (.+?) Category (.+?) Year (\d{4})', text)
    medium = re.search(r'text Method, Materials & Styles Method (.+?) Materials (.+?) Styles (.+)', text)
    keywords = re.search(r'text Keywords (.+)', text)
    packing = re.search(r'text Weight & Packaging Packaging Type (.+?) Shipping Weight ([\d.]+) kg', text)
    assert all([price, dims, category, medium, keywords, packing])
    assert float(price[1].replace(',', '')) == r['price_usd']
    assert packing[1] == r['packaging'] and float(packing[2]) == r['packed_weight_kg']
    assert 'text Quantity Total Run 50 Sold on Saatchi Art 0 For Sale 1' in text
    assert 'Ready to Hang Yes' in text and 'Outdoor Safe Yes' in text
    stamp = r['published_utc']
    fields = {
        'saatchi_snapshot_scope': 'Exact-ID native Studio publication and metadata readback. Full description is prepared and saved, but this overview shows a shortened preview; a separate full-description/public checkout audit is not implied.',
        'saatchi_source_file': str(evidence), 'saatchi_source_date': stamp,
        'saatchi_source_sha256': sha(evidence.read_bytes()),
        'saatchi_match_basis': 'Exact catalogue SKU and saved native creation receipt; existing artwork resumed without duplication.',
        'saatchi_catalogue_sku': r['sku'],
        'saatchi_update_state': f"Published native artwork {r['artwork_id']}, verified {stamp}. One panel available. Edition cap 50 is Saatchi only. Packing weight is an estimate and no native crate dimensions were entered. No other platform changes implied.",
        'saatchi_observed_artwork_id': r['artwork_id'], 'saatchi_observed_title': r['title'],
        'saatchi_observed_visibility': 'Published', 'saatchi_observed_availability': 'For Sale',
        'saatchi_observed_public_listing': r['public_url'], 'saatchi_observed_studio_page': r['url'],
        'saatchi_observed_category': category[2], 'saatchi_observed_subject': category[1],
        'saatchi_observed_year_produced': int(category[3]), 'saatchi_observed_medium_method': medium[1],
        'saatchi_observed_materials': medium[2], 'saatchi_observed_styles': medium[3].strip(),
        'saatchi_observed_width_cm': float(dims[1]), 'saatchi_observed_height_cm': float(dims[2]),
        'saatchi_observed_depth_cm': float(dims[3]), 'saatchi_observed_multi_panel': 'False',
        'saatchi_observed_panels': 1, 'saatchi_observed_keywords': keywords[1].strip(),
        'saatchi_observed_keyword_count': len(keywords[1].split(',')),
        'saatchi_observed_edition': 'Limited Edition; native Total Run 50 is an edition cap, not 50 physical casts',
        'saatchi_observed_units_available': 1, 'saatchi_observed_units_sold': 0,
        'saatchi_observed_installation': 'Wall-Mounted', 'saatchi_observed_ready_to_hang': 'Yes',
        'saatchi_observed_suitable_for_outdoors': 'Yes', 'saatchi_observed_packaging': r['packaging'],
        'saatchi_observed_shipping_weight_entered_kg': r['packed_weight_kg'],
        'saatchi_observed_ships_from': 'GB', 'saatchi_observed_artwork_price_usd': r['price_usd'],
        'saatchi_observed_artwork_price_approx_gbp': float(price[2].replace(',', '')),
        'saatchi_observed_your_60_share_usd': float(price[3].replace(',', '')),
        'saatchi_art_native_artwork_id': r['artwork_id'], 'saatchi_art_public_url': r['public_url'],
        'saatchi_art_studio_url': r['url'], 'saatchi_art_publication_status': r['status'],
        'saatchi_art_publication_checked_utc': stamp, 'saatchi_art_primary_photo_id': r['primary_photo_id'],
        'saatchi_art_artwork_price_usd': r['price_usd'], 'saatchi_art_packaging': r['packaging'],
        'saatchi_art_packed_weight_kg_estimate': r['packed_weight_kg'],
        'saatchi_art_packing_basis': 'Native entered shipping weight; catalogue packing model estimate, not measured or drop-tested. No native packed dimensions exposed.',
        'saatchi_art_units_available_native': 1, 'saatchi_art_year_native': 2026,
        'saatchi_art_year_basis': 'Owner-authorized estimated production-planning year; not a verified historical design or casting date.',
        'saatchi_art_ready_to_hang_native': 'Yes', 'saatchi_art_publication_evidence': str(evidence),
        'saatchi_art_edition_update_state': 'Native cap 50 and one available unit verified. Saatchi only. Physical serial numbers and actual total casts produced are not inferred.',
        'saatchi_art_upload_candidate_status': f"PUBLISHED_NATIVE_READBACK_VERIFIED; artwork {r['artwork_id']}; original selected photo accepted; app purposes and primary unchanged.",
        'saatchi_art_upload_candidate_checked_utc': stamp,
    }
    record(r, fields)

held = next(r for r in all_bindings if r['artwork_id'] == '14397527')
evidence = ROOT / 'outputs/platform-goal-continuation-20261107/resume-0140/saatchi-14397527-verification-failure.txt'
assert evidence.exists() and 'captchaFailure' in evidence.read_text()
stamp = datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
record(held, {
    'saatchi_snapshot_scope': 'Exact-ID native primary-only draft receipt; description save rejected by site verification. Prepared form content is not a persisted description.',
    'saatchi_source_file': str(evidence), 'saatchi_source_date': stamp,
    'saatchi_source_sha256': sha(evidence.read_bytes()),
    'saatchi_match_basis': 'Saved exact-ID native creation receipt binds this artwork to the catalogue SKU. Preserve and resume; do not recreate.',
    'saatchi_catalogue_sku': held['sku'],
    'saatchi_update_state': 'Existing draft 14397527: primary photograph saved; description save rejected with HTTP401 and captchaFailure. Human verification/save requested. Not published; price and packing remain targets.',
    'saatchi_observed_artwork_id': held['artwork_id'], 'saatchi_observed_title': held['title'],
    'saatchi_observed_visibility': 'Draft', 'saatchi_observed_studio_page': held['url'],
    'saatchi_art_native_artwork_id': held['artwork_id'], 'saatchi_art_studio_url': held['url'],
    'saatchi_art_publication_status': 'DRAFT_PRIMARY_SAVED_SITE_VERIFICATION_HOLD',
    'saatchi_art_publication_checked_utc': stamp, 'saatchi_art_primary_photo_id': held['primary_photo_id'],
    'saatchi_art_publication_evidence': str(evidence),
    'saatchi_art_upload_candidate_status': 'DRAFT_PRIMARY_SAVED_SITE_VERIFICATION_HOLD; exact artwork 14397527; no publication.',
    'saatchi_art_upload_candidate_checked_utc': stamp,
})

assert len(records) == 7 and len({(p['sheet'], p['cell']) for p in patches}) == len(patches)
plan = dict(scope='Record six verified Saatchi publications and the existing Strata primary-only verification hold. Preserve all app specifications, core and other-platform prices, photo purposes, formulas and workbook features. Edition caps and production years remain Saatchi-only planning metadata.',
            created_utc=stamp, source_sha256=sha(body), headers=headers, patches=patches,
            records=records[:6], held_drafts=records[6:], component_records=181,
            new_native_publications_recorded=6, new_native_drafts_recorded=1, all_native_ids_unique=True)
save('plan.json', plan)
with urllib.request.urlopen('http://127.0.0.1:8767/api/specifications', timeout=120) as response:
    app = json.load(response)
save('app-specifications.json', app)
with connection(ROOT) as (db, _):
    meta = db.files_get_metadata('id:cnqzTNngPVsAAAAAAA7JEQ')
    assert meta.rev == pointer['current_app_review_workbook']['dropbox']['rev']
    download_meta, response = db.files_download('rev:' + meta.rev)
    try:
        previous = response.content
    finally:
        response.close()
    assert previous == body and download_meta.id == meta.id
    save('previous-dropbox-metadata.json', {k: str(getattr(meta, k)) if k.endswith('modified') else getattr(meta, k)
          for k in ['id', 'path_display', 'rev', 'size', 'content_hash', 'server_modified', 'client_modified']})
print(json.dumps(dict(status='PREPARED', records=len(records), patches=len(patches), rows=[r['row'] for r in records], source_sha256=sha(body))))
