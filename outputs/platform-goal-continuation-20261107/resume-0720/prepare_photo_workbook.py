"""Record two qualified Saatchi photo alternatives without changing product selections."""
import hashlib
import json
import re
import sys
import urllib.request
from pathlib import Path
from urllib.parse import quote

ROOT = Path('/Users/tprice/Documents/boldstone')
RUN = Path(__file__).parent
OUT = RUN/'workbook'
OUT.mkdir(exist_ok=True)
sys.path[:0] = [str(ROOT/'catalogue-review'),str(ROOT/'catalogue-review/scripts')]
from delete_dropbox import connection
from import_saatchi_snapshot import Xlsx

read = lambda path: json.loads(path.read_text())
pointer = read(ROOT/'sculpture-catalogue/current-master.json')
source = pointer['current_app_review_workbook']
assert source['sha256'] == '2175d0bfa721fbbfbd58508e709bbfc04a2b868436e10df4a6f2627032e272ca'
body = Path(source['path']).read_bytes()
assert hashlib.sha256(body).hexdigest() == source['sha256']
with connection(ROOT) as (db,_):
    meta = db.files_get_metadata(source['dropbox']['id'])
    assert meta.rev == source['dropbox']['rev'] and meta.size == len(body)
    metadata = {k:str(getattr(meta,k)) if k.endswith('modified') else getattr(meta,k)
        for k in ['id','path_display','rev','size','content_hash','server_modified','client_modified']}
(OUT/'previous-catalogue.xlsx').write_bytes(body)
(OUT/'source-pointer-before.json').write_text(json.dumps(pointer,indent=2)+'\n')
(OUT/'previous-dropbox-metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
with urllib.request.urlopen('http://127.0.0.1:8767/api/specifications',timeout=120) as response:
    app=json.load(response)
(OUT/'app-specifications.json').write_text(json.dumps(app,indent=2)+'\n')
x=Xlsx(OUT/'previous-catalogue.xlsx')
sheet='Wall Sculptures'
headers={x.value(sheet,a):re.sub(r'\d','',a) for a in x.cells[sheet] if re.fullmatch('[A-Z]+7',a)}
rows={x.value(sheet,'AA'+str(r)):r for r in range(8,189)}
patches,heights,previews=[],[],[]
proof=read(RUN/'cup-ring-photo-qualification.json')
assert proof['status']=='PASS_VISUAL_AND_ORIGINAL_FILE_REVIEW' and proof['native_uploads']==0
for pid in ['BSI-ADD5F3BEFCF5','BSI-70BDE00F2855']:
    p=read(RUN/'packets'/f'{pid}.json')
    assert not p['native_artwork_id'] and p['app_photo_changes']==0
    photo=p['photo']
    assert hashlib.sha256(Path(photo['native_upload_path']).read_bytes()).hexdigest()==photo['native_upload_sha256']
    values=dict(saatchi_art_upload_candidate_photo_id=photo['image_id'],
        saatchi_art_upload_candidate_original_url='https://www.dropbox.com/preview'+quote(photo['photo_path'],safe='/'),
        saatchi_art_upload_candidate_width_px=photo['width'],saatchi_art_upload_candidate_height_px=photo['height'],
        saatchi_art_upload_candidate_description=p['description'],
        saatchi_art_upload_candidate_status='Prepared Saatchi-only alternative. Complete matching single panel identified in a genuine two-panel photograph. Upload and contextual-primary acceptance pending account verification.',
        saatchi_art_upload_candidate_checked_utc='Checked UTC: '+photo['checked_utc'],
        saatchi_art_upload_candidate_app_use=photo['app_use'],
        saatchi_art_upload_candidate_original_file_format='JPEG',saatchi_art_upload_candidate_original_sha256=photo['sha256'],
        saatchi_art_upload_candidate_upload_file_format='JPEG',saatchi_art_upload_candidate_upload_sha256=photo['native_upload_sha256'],
        saatchi_art_upload_candidate_pixel_verification='Unaltered original bytes verified against Dropbox content hash. No crop, resize, rotation, padding or generated detail. Cool lighting and supplied panel position disclosed.')
    row=rows[pid]
    assert x.value(sheet,'AQ'+str(row))==p['sku']
    for key,value in values.items():
        cell=headers[key]+str(row)
        old=x.value(sheet,cell)
        if old!=value:
            patches.append(dict(sheet=sheet,cell=cell,before=old,value=value))
    heights.append(dict(sheet=sheet,row=row,value=420))
    previews.append(dict(range=f'WM{row}:WS{row}',name=pid.lower()))
assert len(patches)==26 and len({p['cell'] for p in patches})==26
plan=dict(scope='Record two reviewed archival Cup Ring and Spiral photo alternatives for Saatchi only. They are prepared, not uploaded. Preserve all native publication states, app image associations and purposes, prices, zero labour, other platform fields and workbook features.',
    patches=patches,new_columns=[],row_heights=heights,saved_ebay_drafts_recorded=0,new_native_publications_recorded=0,
    new_native_drafts_recorded=0,chairish_existing_drafts_updated=0,faire_products_verified=0,new_instagram_publications=0,
    qualified_photo_alternatives_recorded=2,previews=previews)
(OUT/'plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n')
template=RUN.parent/'resume-0645/workbook'
for name in ['build.mjs','preserve_and_verify.py','independent_verify.py','publish.py']:
    text=(template/name).read_text()
    if name=='build.mjs':
        text=text.replace("await book.recalculate();", "for(const r of plan.row_heights||[])book.worksheets.getItem(r.sheet).getRange('A'+r.row+':XB'+r.row).format.rowHeight=r.value;\n    await book.recalculate();")
    elif name=='preserve_and_verify.py':
        text=text.replace("    after = {c.get('r'): c for c in tree.findall", "    for change in plan.get('row_heights', []):\n        if change['sheet'] == sheet:\n            authored_row = E.fromstring(auth.parts[path]).find(f\"s:sheetData/s:row[@r='{change['row']}']\", NS)\n            assert float(authored_row.get('ht')) == change['value']\n            rows[change['row']].set('ht', authored_row.get('ht'))\n            rows[change['row']].set('customHeight', authored_row.get('customHeight', '1'))\n    after = {c.get('r'): c for c in tree.findall")
    elif name=='publish.py':
        text=text.replace("updated['saatchi_and_carrier_refresh']", "updated['saatchi_photo_alternative_refresh']")
    (OUT/name).write_text(text)
print(json.dumps(dict(patches=len(patches),qualified_photos=2,rows=[r['row'] for r in heights],new_columns=0)))
