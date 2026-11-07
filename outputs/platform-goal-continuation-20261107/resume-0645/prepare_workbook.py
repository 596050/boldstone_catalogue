"""Record the verified publication, bound draft and one qualified carrier quote."""
import hashlib
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

ROOT = Path('/Users/tprice/Documents/boldstone')
RUN = Path(__file__).parent
OUT = RUN / 'workbook'
OUT.mkdir(exist_ok=True)
sys.path.insert(0, str(ROOT / 'catalogue-review/scripts'))
from import_saatchi_snapshot import Xlsx
sys.path.insert(0, str(ROOT / 'catalogue-review'))
from delete_dropbox import connection

pointer = json.loads((ROOT / 'sculpture-catalogue/current-master.json').read_text())
source = pointer['current_app_review_workbook']
assert source['sha256'] == '40bd0450467deb09940e555c4de39b966b1faff2d2c2b4fefd452f300a4e2ace'
body = Path(source['path']).read_bytes()
assert hashlib.sha256(body).hexdigest() == source['sha256']
with connection(ROOT) as (db, _):
    meta = db.files_get_metadata(source['dropbox']['id'])
    assert meta.rev == source['dropbox']['rev'] and meta.size == len(body)
    metadata = {k: str(getattr(meta,k)) if k.endswith('modified') else getattr(meta,k)
                for k in ['id','path_display','rev','size','content_hash','server_modified','client_modified']}
(OUT / 'previous-catalogue.xlsx').write_bytes(body)
(OUT / 'source-pointer-before.json').write_text(json.dumps(pointer,indent=2)+'\n')
(OUT / 'previous-dropbox-metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
with urllib.request.urlopen('http://127.0.0.1:8767/api/specifications', timeout=120) as response:
    app = json.load(response)
(OUT / 'app-specifications.json').write_text(json.dumps(app,indent=2)+'\n')
x = Xlsx(OUT / 'previous-catalogue.xlsx')
sheet = 'Wall Sculptures'
headers = {x.value(sheet,a): re.sub(r'\d','',a) for a in x.cells[sheet] if re.fullmatch('[A-Z]+7',a)}
rows = {x.value(sheet,'AA'+str(n)):n for n in range(8,189)}
patches = []
def patch(pid,key,value):
    if key.endswith('_utc') and isinstance(value,str) and re.match(r'^\d{4}-\d{2}-\d{2}T',value):
        value = 'Checked UTC: '+value
    cell = headers[key]+str(rows[pid])
    before = x.value(sheet,cell)
    if before != value:
        patches.append(dict(sheet=sheet,cell=cell,before=before,value=value))

pid = 'BSI-53239DE28BCA'
r = json.loads((RUN.parent / 'resume-0512' / f'saatchi-publication-{pid}.json').read_text())
packet = json.loads((RUN.parent / 'resume-0512/packets' / f'{pid}.json').read_text())
assert r['status'] == 'PUBLISHED_NATIVE_READBACK_VERIFIED' and r['description_verified']
proof = (ROOT / r['publication_evidence']).read_text()
assert 'text Visibility:  Published' in proof and r['native_id'] in proof
for key,value in dict(saatchi_art_native_artwork_id=r['native_id'],saatchi_art_public_url=r['public_url'],
    saatchi_art_studio_url=f'https://www.saatchiart.com/en-gb/studio/art/{r["native_id"]}/overview',
    saatchi_art_publication_status='Published; exact artwork ID, full saved description, price, edition and packing verified. Public purchase route not independently verified.',
    saatchi_art_publication_checked_utc=r['verified_utc'],saatchi_art_primary_photo_id=r['photo_id'],
    saatchi_art_primary_original_url='https://www.dropbox.com/preview'+quote(packet['photo']['photo_path'],safe='/'),
    saatchi_art_artwork_price_usd=r['artwork_price_usd'],saatchi_art_packaging=r['packaging'],
    saatchi_art_packed_weight_kg_estimate=r['packed_weight_estimate_kg'],
    saatchi_art_packing_basis='Saatchi-only editable crate packing estimate, including the separate packaging allowance. Not a measured parcel. Native destination shipping quoted separately.',
    saatchi_art_units_available_native=r['available_units'],saatchi_art_year_native=r['creation_year'],
    saatchi_art_year_basis='Owner-requested Saatchi-only planning estimate; not a verified historical production date.',
    saatchi_art_ready_to_hang_native='No',saatchi_art_publication_evidence=str(ROOT / r['publication_evidence']),
    saatchi_art_upload_candidate_status='Published under existing artwork14397795. App photo purposes and primary unchanged.',
    saatchi_art_upload_candidate_checked_utc=r['verified_utc']).items():
    patch(pid,key,value)

pid = 'BSI-49CB2EDD232C'
held = json.loads((RUN / f'saatchi-upload-{pid}.json').read_text())
packet = json.loads((RUN / 'packets' / f'{pid}.json').read_text())
assert held['status'] == 'REVIEW_REQUIRED_PRICE_SAVE_RECAPTCHA_REJECTED'
assert held['native_error']['captchaFailure'] and held['native_error']['http_status'] == 401
now = datetime.now(timezone.utc).isoformat()
for key,value in dict(saatchi_art_native_artwork_id=held['native_artwork_id'],
    saatchi_art_studio_url=f'https://www.saatchiart.com/en-gb/studio/art/{held["native_artwork_id"]}/overview',
    saatchi_art_publication_status='Draft14397869; primary saved and description step completed. Sale-details save rejected by Saatchi reCAPTCHA. Price and availability are not confirmed saved; complete this ID only.',
    saatchi_art_publication_checked_utc=now,saatchi_art_primary_photo_id=packet['photo']['image_id'],
    saatchi_art_primary_original_url='https://www.dropbox.com/preview'+quote(packet['photo']['photo_path'],safe='/'),
    saatchi_art_publication_evidence=held['native_error']['evidence'],
    saatchi_art_upload_candidate_status='Existing draft14397869, not published. Price form staged; manual verification/save needed. No further artwork creation for this SKU.',
    saatchi_art_upload_candidate_checked_utc=now).items():
    patch(pid,key,value)

quote_proof = (RUN / 'ups-acanthus-ny-rates.txt').read_text()
component_proof = (RUN / 'ups-acanthus-ny-rate-components.txt').read_text()
assert all(text in quote_proof for text in ['40 x 40 x 16 cm.','6 kgs.','61.25','GBP','10001'])
assert all(text in component_proof for text in ['51.37','5.00','2.00','2.88','Additional duties/taxes may apply'])
assert round(51.37+5+2+2.88,2) == 61.25
quote_record = dict(status='VERIFIED_SAMPLE_TRANSPORT_QUOTE_NOT_LANDED_COST',checked_utc=now,
    catalogue_id='BSI-3635E3DC3434',carrier='UPS',service='UPS Expedited',
    origin_postcode='BA2 7BX',destination_postcode='10001',destination_type='Residential',
    packed_cm_estimate=[40,40,16],actual_weight_estimate_kg=6,billable_kg=6,
    merchandise_customs_value_usd=232,declared_carriage_value_gbp=173,
    quotation_gbp=61.25,components_gbp=dict(transport=51.37,declared_value=5,international_processing=2,surge_residential=2.88),
    pickup_selected=False,shipment_date_used='2026-11-09',estimated_delivery_date='2026-11-13',
    duties_and_taxes_included=False,lower48_flat_rate_verified=False,in_home_service_verified=False,
    landed_cost_state='UPS sign-in required; Continue accepts Tariff/Terms and Technology Agreement. Left unsubmitted.',
    evidence=[str(RUN / 'ups-acanthus-ny-rates.txt'),str(RUN / 'ups-acanthus-ny-rate-components.txt')])
(RUN / 'ups-acanthus-ny-quotation.json').write_text(json.dumps(quote_record,indent=2)+'\n')
patch('BSI-3635E3DC3434','chairish_shipping_review',
      '7 Nov2026: UPS Expedited sample GBP61.25, BA2 7BX to10001 residential,40x40x16cm/6kg; carriage value GBP173. Duties/taxes excluded. This does not verify all-in lower48 or in-home service. Existing USD120 charge unchanged; UPS landed-cost login required.')

assert len({(p['sheet'],p['cell']) for p in patches}) == len(patches)
g1,g2 = rows['BSI-53239DE28BCA'],rows['BSI-49CB2EDD232C']
plan = dict(scope='Record the verified Gleneagles Vine I Saatchi publication, the bound Gleneagles Vine II draft whose sale-details save requires reCAPTCHA verification, and one qualified UPS sample transport quotation for Acanthus Pewter. Preserve all core app records, prices, zero labour, photography choices, existing platform data and workbook features.',
    patches=patches,new_columns=[],saved_ebay_drafts_recorded=0,new_native_publications_recorded=1,
    new_native_drafts_recorded=1,chairish_existing_drafts_updated=0,faire_products_verified=0,new_instagram_publications=0,
    previews=[dict(range=f'RY{min(g1,g2)}:SC{max(g1,g2)}',name='saatchi-gleneagles'),
              dict(range=f'{headers["chairish_shipping_review"]}12:{headers["chairish_shipping_review"]}12',name='chairish-shipping')])
(OUT / 'plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n')

templates = ROOT / 'outputs/furnitures-faire-instagram-20261107-additional/workbook'
for name in ['build.mjs','preserve_and_verify.py']:
    text = (templates / name).read_text()
    if name == 'build.mjs':
        text = text.replace("const previews=[{range:'UX7:UY11',name:'faire-prices'},{range:'VD7:VD10',name:'faire-checked'}];", "const previews=JSON.parse(await fs.readFile(out+'/plan.json','utf8')).previews;")
    else:
        text = text.replace("if cell.get('t') == 's':", "if isinstance(patch['value'], str):")
    (OUT / name).write_text(text)
for name in ['independent_verify.py','publish.py']:
    text = (RUN.parent / 'resume-0600/workbook' / name).read_text()
    if name == 'publish.py':
        text = text.replace("updated['marketplace_progress_refresh']", "updated['saatchi_and_carrier_refresh']")
    (OUT / name).write_text(text)
print(json.dumps(dict(prepared_patches=len(patches),new_prefixed_columns=0,source_sha256=source['sha256'],rows=[g1,g2])))
