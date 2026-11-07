"""Record one saved Saatchi price without projecting unsaved or queued changes."""
import hashlib
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path('/Users/tprice/Documents/boldstone')
RUN = Path(__file__).parent
OUT = RUN / 'verified-price-closeout'
OUT.mkdir(exist_ok=True)
sys.path[:0] = [str(ROOT/'catalogue-review'), str(ROOT/'catalogue-review/scripts')]
from delete_dropbox import connection
from import_saatchi_snapshot import Xlsx

read = lambda path: json.loads(path.read_text())
pointer = read(ROOT/'sculpture-catalogue/current-master.json')
source = pointer['current_app_review_workbook']
assert source['sha256'] == '38416426f23c43d53b0dbcf6e4297d8582d98a576c0f7390223cf44eba2bb415'
body = Path(source['path']).read_bytes()
assert hashlib.sha256(body).hexdigest() == source['sha256']
receipt = read(RUN/'resume-0720/saatchi-price-update-14393365.json')
assert receipt['status'] == 'PASS_PRICE_ONLY_SAVE_AND_RELOAD'
assert receipt['source_workbook_sha256'] == source['sha256']
assert receipt['before_price_usd'] == 168 and receipt['after_price_usd'] == 307
assert receipt['other_displayed_sale_fields_unchanged'] is True
proof = Path(receipt['evidence']).read_text()
assert '14393365' in proof and '307' in proof
with connection(ROOT) as (db, _):
    meta = db.files_get_metadata(source['dropbox']['id'])
    assert meta.rev == source['dropbox']['rev'] and meta.size == len(body)
    metadata = {k: str(getattr(meta,k)) if k.endswith('modified') else getattr(meta,k)
                for k in ['id','path_display','rev','size','content_hash','server_modified','client_modified']}
(OUT/'previous-catalogue.xlsx').write_bytes(body)
(OUT/'source-pointer-before.json').write_text(json.dumps({'current_app_review_workbook':source},indent=2)+'\n')
(OUT/'previous-dropbox-metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
with urllib.request.urlopen('http://127.0.0.1:8767/api/specifications',timeout=120) as response:
    app = json.load(response)
(OUT/'app-specifications.json').write_text(json.dumps(app,indent=2)+'\n')
x = Xlsx(OUT/'previous-catalogue.xlsx')
s = 'Wall Sculptures'
headers = {x.value(s,a):re.sub(r'\d','',a) for a in x.cells[s] if re.fullmatch('[A-Z]+7',a)}
row = next(r for r in range(8,189) if x.value(s,'AA'+str(r)) == receipt['catalogue_id'])
assert row == 23 and x.value(s,'AQ23') == receipt['sku']
assert x.value(s,headers['saatchi_art_native_artwork_id']+str(row)) == receipt['native_id']
assert x.value(s,headers['saatchi_art_artwork_price_usd']+str(row)) == receipt['before_price_usd']
assert x.value(s,headers['saatchi_art_packed_weight_kg_estimate']+str(row)) == 28
old_evidence = x.value(s,headers['saatchi_art_publication_evidence']+str(row))
values = {
    'saatchi_art_artwork_price_usd':307,
    'saatchi_art_publication_checked_utc':'UTC | '+receipt['verified_utc'],
    'saatchi_art_publication_evidence':old_evidence+'\nPrice-only save and reload: '+str(Path(receipt['evidence']).relative_to(ROOT)),
}
patches = [dict(sheet=s,cell=headers[k]+str(row),before=x.value(s,headers[k]+str(row)),value=v)
           for k,v in values.items()]
assert len(patches) == 3
plan = dict(scope='Record only the verified Bone Spiral I Narrow White native Saatchi price correction from USD 168 to USD 307. The Ammonite USD 265 form remains unsaved and is not projected. Preserve all other prices, photo alternatives, platform observations, app choices, zero labour, formulas and workbook features.',
            patches=patches,new_columns=[],row_heights=[],previews=[dict(range='SB23:SN23',name='verified-bone-spiral-price')],
            saved_ebay_drafts_recorded=0,new_native_publications_recorded=0,new_native_drafts_recorded=0,
            chairish_existing_drafts_updated=0,faire_products_verified=0,new_instagram_publications=0,
            verified_price_corrections_recorded=1,unresolved_price_differences=111)
(OUT/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
template = RUN/'resume-0720/workbook'
for name in ['build.mjs','preserve_and_verify.py','independent_verify.py','publish.py']:
    text = (template/name).read_text()
    if name == 'publish.py':
        text = text.replace("updated['saatchi_photo_alternative_refresh']", "updated['saatchi_verified_price_refresh']")
    (OUT/name).write_text(text)
print(json.dumps(dict(patches=3,verified_native_price=307,unsaved_ammonite_price_excluded=True)))
