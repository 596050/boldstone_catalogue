"""Prepare a narrow update of verified native marketplace observations."""
import hashlib
import json
import re
import shutil
import sys
import urllib.request
from urllib.parse import quote
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path('/Users/tprice/Documents/boldstone')
RUN = Path(__file__).parent
OUT = RUN / 'workbook'
OUT.mkdir(exist_ok=True)
sys.path.insert(0, str(ROOT / 'catalogue-review/scripts'))
from import_saatchi_snapshot import Xlsx, column_index
sys.path.insert(0, str(ROOT / 'catalogue-review'))
from delete_dropbox import connection

pointer = json.loads((ROOT / 'sculpture-catalogue/current-master.json').read_text())
source = pointer['current_app_review_workbook']
assert source['dropbox']['rev'] == '65fa75b0536e20c0dea29'
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
with urllib.request.urlopen('http://127.0.0.1:8767/api/specifications',timeout=120) as response:
    app = json.load(response)
(OUT / 'app-specifications.json').write_text(json.dumps(app,indent=2)+'\n')
x = Xlsx(OUT / 'previous-catalogue.xlsx')
sheet = 'Wall Sculptures'
headers = {x.value(sheet,a): re.sub(r'\d','',a) for a in x.cells[sheet] if re.fullmatch('[A-Z]+7',a)}
rows = {x.value(sheet,'AA'+str(n)):n for n in range(8,189)}
by_sku = {x.value(sheet,'AQ'+str(n)):n for n in range(8,189)}
patches, new_columns = [], []
def patch(pid,key,value):
    if key.endswith('_utc') and isinstance(value,str) and re.match(r'^\d{4}-\d{2}-\d{2}T',value):
        value='Checked UTC: '+value
    cell = headers[key] + str(rows[pid])
    before = x.value(sheet,cell)
    if before != value:
        patches.append(dict(sheet=sheet,cell=cell,before=before,value=value))
def column_name(number):
    result = ''
    while number:
        number,remainder = divmod(number-1,26)
        result = chr(65+remainder)+result
    return result

names = [
 ('ebay_sapr_2972_draft_id','RY8'),
 ('ebay_sapr_2972_draft_url','SA8'),
 ('ebay_sapr_2972_draft_status','SB8'),
 ('ebay_sapr_2972_draft_price_gbp','UX8'),
 ('ebay_sapr_2972_draft_height_cm','XD8'),
 ('ebay_sapr_2972_draft_width_cm','XD8'),
 ('ebay_sapr_2972_draft_depth_cm','XD8'),
 ('ebay_sapr_2972_draft_photo_count','SQ8'),
 ('ebay_sapr_2972_draft_evidence_checked_utc','SC8'),
 ('ebay_sapr_2972_draft_evidence_sha256','SN8'),
 ('ebay_sapr_2972_draft_delivery_review','SS8'),
 ('ebay_sapr_2972_draft_publication_status','SB8')]
last = max(column_index(a) for a in x.cells[sheet] if a.endswith('7') and re.fullmatch('[A-Z]+7',a))
for offset,(name,style_source) in enumerate(names,1):
    assert name not in headers
    col = column_name(last+offset)
    headers[name] = col
    patches.append(dict(sheet=sheet,cell=col+'7',before=None,value=name))
    number_format = ('"£"#,##0.00' if name.endswith('_price_gbp') else '0.00' if name.endswith('_cm') else '0' if name.endswith('_photo_count') else '@')
    new_columns.append(dict(column=col,index=last+offset,width=30,header_style_source='XH7',body_style_source=style_source,number_format=number_format))

native = json.loads((RUN.parent / 'resume-0345/all65-metadata-independent-verification.json').read_text())
assert native['status'] == 'PASS' and len(native['records']) == 65 and not native['publication_implied']
ready_text = (RUN / 'ebay-14-current-workspace.txt').read_text()
ready_skus = re.findall(r'^\s*\d+ text field \(settable\) Custom label \(SKU\), Value: ([^\n]+)',ready_text,re.M)
assert len(ready_skus) == len(set(ready_skus)) == 14
targets = {r['sku']:r for r in json.loads((RUN.parent / 'resume-0345/full-gallery-reconciliation.json').read_text())['records']}
for r in native['records']:
    p = targets[r['sku']]
    pid = p['catalogue_id']
    assert by_sku[r['sku']] == rows[pid]
    assert p['native_draft_id'] == r['native_draft_id']
    h,w,d = r['dimensions_hwd_cm']
    fields = dict(ebay_sapr_2972_draft_id=r['native_draft_id'],
        ebay_sapr_2972_draft_url=p['native_url'],
        ebay_sapr_2972_draft_status='Saved and reopened draft; exact SKU, price, dimensions, complete copy, New condition and full selected-photo count verified. Not published.',
        ebay_sapr_2972_draft_price_gbp=r['price_gbp'],
        ebay_sapr_2972_draft_height_cm=h,ebay_sapr_2972_draft_width_cm=w,ebay_sapr_2972_draft_depth_cm=d,
        ebay_sapr_2972_draft_photo_count=r['photos'],
        ebay_sapr_2972_draft_evidence_checked_utc='Evidence checked UTC: '+native['checked_utc'],
        ebay_sapr_2972_draft_evidence_sha256=r['evidence_sha256'],
        ebay_sapr_2972_draft_delivery_review=('Reviewed Simple Delivery selection; final submission approval pending.' if r['sku'] in ready_skus
            else 'Delivery not cleared by the metadata verification. Resolve oversized shipping or collection before publication.'),
        ebay_sapr_2972_draft_publication_status='Draft only; no live listing or final legal acceptance implied.')
    for key,value in fields.items():patch(pid,key,value)

for pid in ['BSI-7B6291B7C7F9','BSI-1CDB2BAE6105']:
    r = json.loads((RUN.parent/'resume-0512'/('saatchi-publication-'+pid+'.json')).read_text())
    source_packet = RUN.parent/'resume-0512'/('strata-current-packet.json' if pid=='BSI-7B6291B7C7F9' else 'packets/'+pid+'.json')
    primary_source = json.loads(source_packet.read_text())['photo']
    assert r['status']=='PUBLISHED_NATIVE_READBACK_VERIFIED' and r['description_verified']
    evidence = ROOT / r['publication_evidence']
    assert r['title'] in evidence.read_text() and 'Published' in evidence.read_text()
    values=dict(saatchi_art_native_artwork_id=r['native_id'],saatchi_art_public_url=r['public_url'],
        saatchi_art_studio_url=f'https://www.saatchiart.com/en-gb/studio/art/{r["native_id"]}/overview',
        saatchi_art_publication_status='Published; native status, exact artwork ID and saved description verified. Public purchase route not independently verified.',
        saatchi_art_publication_checked_utc=r['verified_utc'],saatchi_art_primary_photo_id=r['photo_id'],
        saatchi_art_primary_original_url='https://www.dropbox.com/preview'+quote(primary_source['photo_path'],safe='/'),
        saatchi_art_artwork_price_usd=r['artwork_price_usd'],saatchi_art_packaging=r['packaging'],
        saatchi_art_packed_weight_kg_estimate=r['packed_weight_estimate_kg'],
        saatchi_art_packing_basis='Saatchi-only editable crate packing estimate, including the separate packaging allowance. Not a measured packed parcel or an independent carrier quote.',
        saatchi_art_units_available_native=r['available_units'],saatchi_art_year_native=r['creation_year'],
        saatchi_art_year_basis='Owner-requested Saatchi-only planning estimate; not a verified historical production date.',
        saatchi_art_ready_to_hang_native='No',saatchi_art_publication_evidence=str(evidence),
        saatchi_art_upload_candidate_status='Published on Saatchi under the existing bound artwork ID; app photo purposes and primary unchanged.',
        saatchi_art_upload_candidate_checked_utc=r['verified_utc'])
    for key,value in values.items():patch(pid,key,value)

held = json.loads((RUN.parent/'resume-0512/saatchi-upload-BSI-53239DE28BCA.json').read_text())
assert held['status']=='REVIEW_REQUIRED_DESCRIPTION_SERVER_REJECTED_CAPTCHA'
pid=held['catalogue_id']
for key,value in dict(saatchi_art_native_artwork_id=held['native_artwork_id'],
    saatchi_art_studio_url='https://www.saatchiart.com/en-gb/studio/art/14397795/overview',
    saatchi_art_publication_status='Draft primary saved; description save rejected by Saatchi verification. Complete existing artwork 14397795; do not recreate.',
    saatchi_art_publication_checked_utc=held['native_error']['checked_utc'],
    saatchi_art_primary_photo_id='id:cnqzTNngPVsAAAAAAArtyw',
    saatchi_art_primary_original_url='https://www.dropbox.com/preview'+quote(json.loads((RUN.parent/'resume-0512/packets/BSI-53239DE28BCA.json').read_text())['photo']['photo_path'],safe='/'),
    saatchi_art_publication_evidence=held['native_error']['evidence'],
    saatchi_art_upload_candidate_status='Existing draft primary accepted. Description is staged but not saved; native verification requires attention.',
    saatchi_art_upload_candidate_checked_utc=held['native_error']['checked_utc']).items():patch(pid,key,value)

audit=json.loads((RUN/'saatchi-primary-file-verification.json').read_text())
for r in audit['records']:
    packet=json.loads(Path(r['packet_path']).read_text())
    photo=packet['photo']
    for key,value in dict(saatchi_art_upload_candidate_photo_id=photo['image_id'],
        saatchi_art_upload_candidate_original_url='https://www.dropbox.com/preview'+quote(photo['photo_path'],safe='/'),
        saatchi_art_upload_candidate_width_px=r['width'],saatchi_art_upload_candidate_height_px=r['height'],
        saatchi_art_upload_candidate_description=photo['visual_review'],
        saatchi_art_upload_candidate_app_use=photo['app_use'],
        saatchi_art_upload_candidate_original_file_format=photo['format'],
        saatchi_art_upload_candidate_original_sha256=photo['sha256'],
        saatchi_art_upload_candidate_upload_file_format=r['format'],
        saatchi_art_upload_candidate_upload_sha256=r['sha256'],
        saatchi_art_upload_candidate_pixel_verification=('Original bytes unchanged.' if photo['sha256']==r['sha256'] else 'Container normalized; retained decoded-pixel SHA256 '+photo['decoded_pixel_sha256']+' confirms identical pixels; no resize, crop or generated content.')).items():patch(r['catalogue_id'],key,value)
    if r['native_artwork_id']:continue
    status=('Prepared RGB original meets native primary dimensions; not uploaded. Existing account verification must be resolved before creation.'
            if r['native_dimensions_pass'] else 'Held: genuine source is 1200 pixels wide; native primary minimum is 1500 wide by 1200 high. No artwork created. Do not upscale or pad.')
    patch(r['catalogue_id'],'saatchi_art_upload_candidate_status',status)
    patch(r['catalogue_id'],'saatchi_art_upload_candidate_checked_utc',audit['checked_utc'])

chairish=json.loads((RUN/'chairish-37950217-photo-receipt.json').read_text())
for key,value in dict(chairish_native_listing_id=chairish['native_id'],
    chairish_gallery_checked_utc=chairish['verified_utc'],chairish_photo_count_verified=2,
    chairish_current_native_status='Draft; two photographs saved and reopened. Not submitted or active.',
    chairish_photo_completion_note='Added the genuine associated Pewter detail photograph. Original primary retained. The description explains the warm colour cast. Other reviewed fields unchanged; all-in lower-48 US shipping quote still unverified. App purposes and primary unchanged.').items():patch(chairish['catalogue_id'],key,value)

assert len({(p['sheet'],p['cell']) for p in patches})==len(patches)
plan=dict(scope='Record 65 saved sapr_2972 drafts in distinct account-prefixed fields; two verified Saatchi publications, one primary-only verification-held draft, the corrected primary-photo qualification queue, and the existing Acanthus Pewter Chairish draft with its second photograph. Preserve dated source exports, current app records, all core prices and zero labour, other platform observations and workbook features. No additional listing publication is implied.',
          patches=patches,new_columns=new_columns,new_last_column=new_columns[-1]['column'],
          saved_ebay_drafts_recorded=65,new_native_publications_recorded=2,new_native_drafts_recorded=1,
          chairish_existing_drafts_updated=1,saatchi_ready_uncreated=13,saatchi_native_photo_holds=1,
          faire_products_verified=0,new_instagram_publications=0,
          previews=[dict(range='SO7:SS12',name='chairish-photo'),dict(range='XI7:XM12',name='ebay-native-observations'),dict(range='RY145:SC148',name='saatchi-botanical')])
(OUT/'plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(dict(patches=len(patches),new_prefixed_fields=len(new_columns),ebay_drafts=65,saatchi_publications=2,saatchi_drafts=1,chairish_photo_updates=1)))
