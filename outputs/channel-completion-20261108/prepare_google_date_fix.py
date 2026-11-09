"""Preserve every timestamp while replacing Google-incompatible OOXML date cells."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import shutil
import sys
import urllib.request

ROOT = Path('/Users/tprice/Documents/boldstone')
PACKET = Path(__file__).parent
OUT = PACKET / 'catalogue-google-dates'
OUT.mkdir(exist_ok=True)
sys.path[:0] = [str(ROOT / 'catalogue-review'), str(ROOT / 'catalogue-review/scripts')]
from import_saatchi_snapshot import Xlsx
from delete_dropbox import connection
load = lambda p: json.loads(Path(p).read_text())
sha = lambda b: hashlib.sha256(b).hexdigest()
pointer = load(ROOT / 'sculpture-catalogue/current-master.json')
source = pointer['current_app_review_workbook']
assert source['dropbox']['rev'] == '65fcb5250a2fd0c0dea29'
body = Path(source['path']).read_bytes()
assert sha(body) == source['sha256']
(OUT / 'previous-catalogue.xlsx').write_bytes(body)
(OUT / 'source-pointer-before.json').write_text(json.dumps(pointer, indent=2)+'\n')
with connection(ROOT) as (db, _):
    m = db.files_get_metadata(source['dropbox']['id'])
    assert m.rev == source['dropbox']['rev'] and m.path_display == source['dropbox']['path_display']
    dm, response = db.files_download('rev:'+m.rev)
    try:
        assert dm.id == m.id and response.content == body
    finally:
        response.close()
    meta = {k: str(getattr(m, k)) if k.endswith('modified') else getattr(m, k)
            for k in ['id', 'path_display', 'rev', 'size', 'content_hash', 'server_modified', 'client_modified']}
(OUT / 'previous-dropbox-metadata.json').write_text(json.dumps(meta, indent=2)+'\n')
with urllib.request.urlopen('http://127.0.0.1:8767/api/specifications', timeout=120) as r:
    app = json.load(r)
(OUT / 'app-specifications.json').write_text(json.dumps(app)+'\n')
x = Xlsx(OUT / 'previous-catalogue.xlsx')
patches = []
for sheet, cells in x.cells.items():
    for cell, node in cells.items():
        if node.get('t') != 'd':
            continue
        original = x.value(sheet, cell)
        dt = datetime.fromisoformat(original.replace('Z', '+00:00'))
        assert dt.tzinfo is not None and dt.utcoffset().total_seconds() == 0
        serial = (dt - datetime(1899, 12, 30, tzinfo=timezone.utc)).total_seconds() / 86400
        patches.append(dict(sheet=sheet, cell=cell, before=original, value=serial, style='utc', original_utc=original))
assert len(patches) == 1832
for sheet in ['Wall Sculptures', 'Images', 'Specification Sources', 'Manufacturing Costs', 'Cost Rates', 'Cost Finishes', 'Upload Plan', 'Website Copy']:
    old = x.value(sheet, 'A4')
    if sheet == 'Wall Sculptures':
        text = ('Channel evidence recorded 8 November 2026. Product facts follow saved app decisions. '
                'See per-platform status and checked-UTC fields; prepared targets alone do not establish publication. '
                'Workbook edits do not publish changes to the app or websites.')
    else:
        text = old.replace('App snapshot:', 'Base app export:')
        if sheet in ['Specification Sources', 'Website Copy']:
            text += ' Later verified channel observations are recorded in the master platform fields.'
    assert text != old
    patches.append(dict(sheet=sheet, cell='A4', before=old, value=text, style='text'))
old = x.value('Platform Review', 'N2')
patches.append(dict(sheet='Platform Review', cell='N2', before=old,
    value=old.replace('Fresh data audit:', 'Retained data audit:')+' Later live-channel evidence is dated separately in the master platform fields.', style='text'))
assert len(patches) == 1841
plan = dict(created_utc=datetime.now(timezone.utc).isoformat(), source_sha256=sha(body),
    scope='Convert 1,832 existing UTC typed-date cells to numeric Excel dates for lossless Google Sheets import; clarify nine retained snapshot/lineage labels. '
          'Original timestamp strings retained in this exact patch manifest. No prices, labour, GTINs, product identities, stock, selections, formulas or platform publication changed.',
    patches=patches, new_headers=[], first_added_column=889, last_added_column=888,
    counts=dict(instagram_published=0, facebook_published=0, linkedin_published=0, utc_date_cells_normalized=1832,
                snapshot_lineage_labels_clarified=9, gtins_assigned=0, pinterest_appeals_used=0),
    previews=[dict(name='master-lineage', sheet='Wall Sculptures', range='A2:F7'),
              dict(name='source-date', sheet='Specification Sources', range='M7:N10')])
(OUT / 'plan.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2)+'\n')
shutil.copy2(PACKET / 'catalogue-consent-followup/publish.py', OUT / 'publish.py')
p = OUT / 'publish.py'
s = p.read_text().replace("updated['consent_and_photo_review_followup_20261108']=", "updated['google_date_compatibility_and_lineage_20261108']=")
p.write_text(s)
dependency = Path('/Users/tprice/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules')
if not (OUT / 'node_modules').exists():
    (OUT / 'node_modules').symlink_to(dependency, target_is_directory=True)
print(json.dumps(dict(patches=len(patches), date_cells=1832, source_revision=meta['rev'])))
