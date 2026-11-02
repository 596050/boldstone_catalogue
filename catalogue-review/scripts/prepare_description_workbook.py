"""Prepare a description-only patch against the current Dropbox revision."""
import hashlib
import json
from datetime import datetime
from pathlib import Path
import sys
import urllib.request
import zipfile
import xml.etree.ElementTree as E

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'catalogue-review'))
from delete_dropbox import connection

out = Path(sys.argv[1]).resolve()
out.mkdir(parents=True, exist_ok=True)
assert not (out / 'dropbox-receipt.json').exists(), 'This workbook update already has an upload receipt.'
write = lambda name, value: (out / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
pointer = json.loads((ROOT / 'sculpture-catalogue/current-master.json').read_text())
write('source-pointer-before.json', pointer)
prior = pointer['current_app_review_workbook']
with connection(ROOT) as (client, _):
    meta = client.files_get_metadata(prior['dropbox']['id'])
    assert meta.path_display == '/BOLDSTONE MASTER/Products/01 Wall Sculptures/_Documents_Catalogue/catalogue_wall_sculptures.xlsx'
    downloaded, response = client.files_download('rev:' + meta.rev)
    try: body = response.content
    finally: response.close()
    assert downloaded.id == meta.id and downloaded.rev == meta.rev
    assert hashlib.sha256(body).hexdigest() == prior['sha256'], 'Current workbook differs from verified source.'
    (out / 'previous-catalogue.xlsx').write_bytes(body)
    write('previous-dropbox-metadata.json', {k: str(getattr(meta, k)) if k.endswith('modified') else getattr(meta, k)
        for k in ('id', 'path_display', 'rev', 'size', 'content_hash', 'server_modified', 'client_modified')})
with urllib.request.urlopen('http://127.0.0.1:8767/api/specifications', timeout=120) as response:
    snapshot = json.load(response)
write('app-snapshot.json', snapshot)
products = {p['id']: p for p in snapshot['products']}
fields = {pid: {f['key']: f for f in p['fields'] + p['listing_fields']} for pid, p in products.items()}
U = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
ns = {'s': U}; q = lambda x: '{' + U + '}' + x
with zipfile.ZipFile(out / 'previous-catalogue.xlsx') as z:
    sheets = [s.get('name') for s in E.fromstring(z.read('xl/workbook.xml')).find('s:sheets', ns)]
    ss = [''.join(t.text or '' for t in s.iter(q('t'))) for s in E.fromstring(z.read('xl/sharedStrings.xml'))] if 'xl/sharedStrings.xml' in z.namelist() else []
    cells = {name: {c.get('r'): c for c in E.fromstring(z.read(f'xl/worksheets/sheet{i+1}.xml')).findall('s:sheetData/s:row/s:c', ns)} for i, name in enumerate(sheets)}
    def value(sheet, address):
        cell = cells[sheet].get(address)
        if cell is None: return None
        if cell.get('t') == 'inlineStr': return ''.join(t.text or '' for t in cell.iter(q('t')))
        v = cell.find('s:v', ns); v = v.text if v is not None else ''
        return ss[int(v)] if cell.get('t') == 's' else v
    patches = []
    def put(sheet, address, new):
        old = value(sheet, address)
        if old != new:
            patches.append({'sheet': sheet, 'cell': address, 'before': old, 'value': new})
    seen = set()
    for row in range(8, 189):
        pid = value('Wall Sculptures', f'AA{row}')
        assert pid in products and pid not in seen
        assert value('Website Copy', f'E{row}') == pid
        seen.add(pid)
        put('Wall Sculptures', f'AD{row}', fields[pid]['Description']['value'])
        put('Website Copy', f'B{row}', fields[pid]['Description']['value'])
    assert seen == set(products) and len(seen) == 181
    source_rows = set()
    for address in cells['Specification Sources']:
        if not address.startswith('C') or not address[1:].isdigit() or int(address[1:]) < 8: continue
        row = int(address[1:]); pid = value('Specification Sources', address)
        if pid in fields and value('Specification Sources', f'E{row}') in ('Description', 'Listing description'):
            source_rows.add(pid)
            for col, key in [('F', 'value'), ('G', 'decision'), ('H', 'certainty'), ('L', 'evidence'), ('M', 'notes'), ('N', 'updated_at')]:
                new_value = fields[pid]['Description'].get(key) or ''
                if key == 'updated_at' and new_value:
                    # Spreadsheet dates preserve milliseconds; full source precision
                    # remains in app-snapshot.json alongside the workbook.
                    new_value = datetime.fromisoformat(new_value).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
                put('Specification Sources', f'{col}{row}', new_value)
    assert source_rows == set(products)
    write('patches.json', {'sheets': sheets, 'patches': patches, 'products': 181, 'new_sheets': [],
        'scope': 'Owner-requested handmade finish variation, named companion pieces and Sally Price customisation/commissions. Descriptions and their audit records only.'})
    print(json.dumps({'products': 181, 'patches': len(patches), 'revision': meta.rev}))
