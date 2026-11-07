"""Prepare two exact component offers from one verified archival pair photograph."""
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

from PIL import Image

ROOT = Path('/Users/tprice/Documents/boldstone')
OUT = Path(__file__).parent
sys.path[:0] = [str(ROOT / 'catalogue-review'), str(ROOT / 'catalogue-review/scripts')]
from channel_content import appearance, complete_description, has_surface_effect, product_type, saatchi_description, values
from import_saatchi_snapshot import Xlsx
from prepare_saatchi_catalogue import native_artwork_bindings

read = lambda p: json.loads(p.read_text())
sha = lambda body: hashlib.sha256(body).hexdigest()
with urlopen('http://127.0.0.1:8767/api/specifications', timeout=120) as response:
    app = json.load(response)
saved = read(OUT.parent / 'resume-0645/workbook/app-specifications.json')
relevant = lambda d: {p['id']:{k:p[k] for k in ['fields','listing_fields','costing','photos','listing_decision']} for p in d['products']}
assert relevant(app) == relevant(saved), 'Current app data changed; reconcile first'
products = {p['id']:p for p in app['products']}
pointer = read(ROOT / 'sculpture-catalogue/current-master.json')['current_app_review_workbook']
assert sha(Path(pointer['path']).read_bytes()) == pointer['sha256']
x = Xlsx(Path(pointer['path']))
sheet = 'Wall Sculptures'
columns = {x.value(sheet, a):re.sub(r'\d','',a) for a in x.cells[sheet] if re.fullmatch('[A-Z]+7', a)}
rows = {x.value(sheet,f'AA{r}'):r for r in range(8,189)}
bindings = native_artwork_bindings(ROOT / 'outputs/catalogue-marketplace-publication-20261101/saatchi-current/primary-draft-receipts.json')
packing = OUT.parent.parent / 'platform-goal-continuation-20261106/packing'
model = {r['catalogue_id']:r for r in read(packing/'plan.json')['records']}
packing_receipt = read(packing/'dropbox-receipt.json')
assert packing_receipt['status'] == 'PASS_DROPBOX_REVISION_UPDATE_AND_BYTE_READBACK'
source = next(r for r in read(OUT / 'archived-photo-headers.json') if r['id']=='id:cnqzTNngPVsAAAAAAAwrGQ')
path = OUT / 'cupringspiral-source-original.jpg'
body = path.read_bytes()
assert len(body) == source['bytes']
assert sha(b''.join(hashlib.sha256(body[i:i+4194304]).digest() for i in range(0,len(body),4194304))) == source['content_hash']
with Image.open(path) as im:
    assert im.size == (1940,1293) and im.format == 'JPEG' and im.mode == 'RGB'
    assert not im.getexif().get(34853)
stamp = datetime.now(timezone.utc).isoformat()
packets = []
(OUT / 'packets').mkdir(exist_ok=True)
for pid, position in [('BSI-70BDE00F2855','left-hand spiral'),('BSI-ADD5F3BEFCF5','right-hand cup-ring')]:
    product = products[pid]
    sku = values(product)['Seller SKU']
    assert sku not in bindings
    row, case = rows[pid], model[pid]
    assert sku == case['sku'] == x.value(sheet, f'AQ{row}')
    dims = [x.value(sheet, columns[h]+str(row)) for h in ['saatchi_width_cm','saatchi_height_cm','saatchi_depth_cm']]
    assert all(isinstance(v,(int,float)) and v>0 for v in dims)
    assert case['asking_usd'] == x.value(sheet, columns['saatchi_asking_price_usd']+str(row))
    disclosure = f'Only the {position} panel in this two-panel photograph is supplied. The companion panel is sold separately. Cool studio lighting is shown; the offered finish is White.'
    content = dict(sku=sku, description_text=complete_description(product,sku,dispatch_days=3,channel='saatchi'),
        colour=appearance(product),surface_effect=has_surface_effect(product),product_type=product_type(product))
    description = disclosure+'\n\n'+saatchi_description(content,limit=1000-len(disclosure)-2)
    assert len(description)<=1000 and all(s in description for s in ['Sally Price','gypsum-based','3 working days'])
    photo = dict(image_id=source['id'],photo_path=source['path'],content_hash=source['content_hash'],
        sha256=sha(body),revision=source['revision'],bytes=len(body),width=1940,height=1293,format='JPEG',
        local_path=str(path),native_upload_path=str(path),native_upload_sha256=sha(body),
        visual_review=f'Both complete textured square panels match the current catalogue primaries. This offer supplies the {position} panel only. The original has cool studio lighting, explicitly disclosed. Source is an archival company product photograph. No crop, upscaling, rotation, padding or generated details.',
        comparison_evidence=str(OUT/'archived-photo-comparison.jpg'),gps_metadata_present=False,
        app_use='Saatchi-only archival alternative. No app image associations, purposes or primaries changed.',checked_utc=stamp)
    packet = dict(catalogue_id=pid,sku=sku,title=product['retail_name'],native_artwork_id=None,
        native_action='RECONCILE_CURRENT_STUDIO_BEFORE_CREATE_ONCE',description=description,
        description_characters=len(description),quantity_per_sale=1,dimensions_cm=dims,
        target_artwork_price_usd=case['asking_usd'],native_packaging='Crate',
        native_packed_weight_kg_estimate=case['packed_kg'],packed_dimensions_cm_estimate=case['packed_cm'],
        packing_allowance_gbp=case['packing_allowance_gbp'],packing_model_source=str(packing/'catalogue_wall_sculptures.xlsx'),
        packing_model_source_sha256=packing_receipt['sha256'],packing_model_dropbox_revision=packing_receipt['current']['rev'],
        packing_estimate_qualification='Editable Saatchi-only crate planning estimate. Not measured. Carrier charges are separate.',
        edition_type=x.value(sheet,columns['saatchi_art_edition_type']+str(row)),
        edition_cap=x.value(sheet,columns['saatchi_art_edition_size']+str(row)),edition_scope='Saatchi Art only',
        creation_year=x.value(sheet,columns['saatchi_art_creation_year']+str(row)),
        creation_year_is_estimate=True,photo=photo,publication_status='PREPARED_CONTEXT_PRIMARY_NATIVE_ACCEPTANCE_PENDING',
        app_photo_changes=0,current_source_workbook_sha256=pointer['sha256'],source_app_revision=app['revision'],
        current_preflight_utc=stamp,required_native_checks=['Resolve current Saatchi save verification before creation',
            'Fresh whole-portfolio identity reconciliation before create once','Native contextual-primary acceptance',
            'Full saved description, price, edition, quantity and packing readback before publication'])
    target = OUT/'packets'/f'{pid}.json'
    target.write_text(json.dumps(packet,ensure_ascii=False,indent=2)+'\n')
    packets.append(dict(packet=packet,validation=dict(packet_path=str(target),sku=sku,native_artwork_id=None,
        status='PREPARED_NOT_UPLOADED_VERIFICATION_GATE_PENDING')))
old_queue = read(OUT.parent/'resume-0645/remaining-native-ready-queue.json')
assert len(old_queue)==12 and len({r['packet']['sku'] for r in old_queue+packets})==14
(OUT/'remaining-native-ready-queue.json').write_text(json.dumps(old_queue+packets,ensure_ascii=False,indent=2)+'\n')
holds = read(OUT/'current-37-photo-holds.json')
remaining = [r for r in holds if r['catalogue_id'] not in {p['packet']['catalogue_id'] for p in packets}]
assert len(remaining)==35
(OUT/'current-35-photo-holds.json').write_text(json.dumps(remaining,indent=2)+'\n')
(OUT/'cup-ring-photo-qualification.json').write_text(json.dumps(dict(status='PASS_VISUAL_AND_ORIGINAL_FILE_REVIEW',
    reviewed_utc=stamp,source=photo,products=[dict(sku=p['packet']['sku'],title=p['packet']['title']) for p in packets],
    app_photo_changes=0,native_uploads=0,remaining_prepared=14,remaining_photo_holds=35),indent=2)+'\n')
print(json.dumps(dict(status='PREPARED_TWO_MATCHED_COMPONENTS',new_packets=2,total_prepared=14,photo_holds=35,
    native_uploads=0,app_photo_changes=0)))
