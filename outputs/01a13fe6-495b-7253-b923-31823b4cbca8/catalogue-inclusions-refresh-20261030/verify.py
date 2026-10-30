"""Independent readback of all requested rows, flags, values and native hyperlinks."""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import math
import re
import zipfile
import xml.etree.ElementTree as ET

root = Path(__file__).resolve().parent
path = root / 'catalogue_wall_sculptures.xlsx'
expected = json.loads((root / 'expected-workbook.json').read_text())
snapshot = json.loads((root / 'catalogue-snapshot.json').read_text())
links = json.loads((root / 'hyperlinks.json').read_text())
NS = {'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
      'r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
      'p':'http://schemas.openxmlformats.org/package/2006/relationships'}


def column(index):
    out = ''
    index += 1
    while index:
        index, rem = divmod(index - 1, 26)
        out = chr(65 + rem) + out
    return out


checks = []
with zipfile.ZipFile(path) as z:
    assert z.testzip() is None
    strings = []
    if 'xl/sharedStrings.xml' in z.namelist():
        strings = [''.join(node.itertext()) for node in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('s:si',NS)]
    workbook = ET.fromstring(z.read('xl/workbook.xml'))
    assert [s.attrib['name'] for s in workbook.findall('s:sheets/s:sheet', NS)] == [s['name'] for s in expected['sheets']]
    for index, sheet in enumerate(expected['sheets'], 1):
        xml = ET.fromstring(z.read(f'xl/worksheets/sheet{index}.xml'))
        cells = {c.attrib['r']:c for c in xml.findall('s:sheetData/s:row/s:c', NS)}

        def value(address):
            c = cells.get(address)
            if c is None:
                return None
            assert c.attrib.get('t') != 'e', ('Excel error', sheet['name'], address, ET.tostring(c))
            node = c.find('s:v', NS)
            raw = node.text if node is not None else None
            kind = c.attrib.get('t')
            if kind == 's':
                return strings[int(raw)]
            if kind == 'inlineStr':
                return ''.join(c.find('s:is',NS).itertext())
            if kind == 'str':
                return raw or ''
            if kind == 'b':
                return raw == '1'
            if kind == 'd':
                return (datetime.fromisoformat(raw.replace('Z','+00:00')) - datetime(1899,12,30,tzinfo=timezone.utc)).total_seconds()/86400
            return float(raw) if raw not in (None, '') else None

        for j, name in enumerate(sheet['headers']):
            assert value(column(j)+'7') == name, (sheet['name'], 'header', name)
        for i, row in enumerate(sheet['rows'], 8):
            for j, wanted in enumerate(row):
                address = column(j)+str(i)
                actual = value(address)
                if sheet['name'] == 'Images' and j == 19:
                    wanted = row[18] / 1048576 if row[18] is not None else None
                if sheet['name'] == 'Specification Sources' and j == 13 and wanted:
                    wanted = (datetime.fromisoformat(wanted.replace('Z','+00:00')) - datetime(1899,12,30,tzinfo=timezone.utc)).total_seconds()/86400
                if wanted in (None, ''):
                    assert actual in (None, ''), (sheet['name'],address,actual,wanted)
                elif isinstance(wanted,(int,float)):
                    assert isinstance(actual,(int,float)) and math.isclose(actual,wanted,rel_tol=1e-10,abs_tol=1e-8), (sheet['name'],address,actual,wanted)
                else:
                    assert actual == wanted, (sheet['name'],address,str(actual)[:120],str(wanted)[:120])
        for address in cells:
            value(address)
        pane = xml.find('s:sheetViews/s:sheetView/s:pane',NS)
        assert pane.attrib['xSplit'] == '3' and pane.attrib['ySplit'] == '7' and pane.attrib['state'] == 'frozen'
        rname = f'xl/worksheets/_rels/sheet{index}.xml.rels'
        rels = {r.attrib['Id']:r.attrib for r in ET.fromstring(z.read(rname))} if rname in z.namelist() else {}
        savedlinks = {}
        for link in xml.findall('s:hyperlinks/s:hyperlink',NS):
            ident = link.attrib.get('{'+NS['r']+'}id')
            savedlinks[link.attrib['ref']] = (rels[ident]['Target'] if ident else link.attrib['location'])
        expectedlinks = {l['cell']:l['url'] for l in links if l['sheet'] == sheet['name']}
        assert savedlinks == expectedlinks, (sheet['name'], 'hyperlink mismatch')
        table_parts = xml.findall('s:tableParts/s:tablePart',NS)
        assert len(table_parts) == 1
        table_target = rels[table_parts[0].attrib['{'+NS['r']+'}id']]['Target']
        import posixpath
        target = table_target.lstrip('/') if table_target.startswith('/') else posixpath.normpath('xl/worksheets/'+table_target)
        table = ET.fromstring(z.read(target))
        assert table.attrib['ref'] == 'A7:'+column(len(sheet['headers'])-1)+str(sheet['row_count']+7)
        assert table.find('s:autoFilter',NS) is not None
        checks.append({'sheet':sheet['name'], 'rows':sheet['row_count'], 'columns':len(sheet['headers']),
                       'hyperlinks':len(savedlinks), 'all_values_matched':True, 'filter_and_panes':True})

# Independently reconcile flags and row counts against the captured app projection.
image_sheet = expected['sheets'][1]
product_sheet = expected['sheets'][0]
listing = Counter(r[2] for r in image_sheet['rows'] if r[8]=='Yes')
primary = Counter(r[2] for r in image_sheet['rows'] if r[7]=='Yes')
for p in snapshot['products']:
    assert listing[p['id']] == len(p['photos']['listing_ids'])
    assert primary[p['id']] == bool(p['photos']['primary_id'])
assert len({r[29] for r in image_sheet['rows']}) == snapshot['summary']['unique_images']
assert len({r[26] for r in product_sheet['rows']}) == 181
assert all(len(p['fields']) == 7 and all(f['value'] for f in p['fields'] + p['listing_fields']) for p in snapshot['products'])
assert all(p['costing']['status'] == 'calculated' for p in snapshot['products'])
with zipfile.ZipFile(path) as z:
    cost_xml = ET.fromstring(z.read('xl/worksheets/sheet4.xml'))
    cost_cells = {c.attrib['r']: c for c in cost_xml.findall('s:sheetData/s:row/s:c', NS)}
    for row in range(8, 189):
        for column_name in ('J','N','O','P','Q','R','S','T','U','V','W','X','Y','Z','AA','AB'):
            assert cost_cells[column_name + str(row)].find('s:f',NS) is not None
    assert len(cost_xml.findall('s:dataValidations/s:dataValidation',NS)) >= 6
assert json.loads((root/'recalculation-checks.json').read_text())['status'] == 'PASS'
assert all('—' not in str(value) for sheet in expected['sheets'] for row in sheet['rows'] for value in row)
report = {'status':'PASS', 'verified_utc':datetime.now(timezone.utc).isoformat(), 'file':str(path),
          'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
          'app_snapshot_utc':snapshot['created_utc'], 'event_cutoff':snapshot['event_cutoff'],
          'summary':snapshot['summary'],'sheets':checks,'hyperlinks':len(links),
          'native_hyperlinks_over_255_characters':sum(len(l['url'])>255 for l in links),
          'primary_and_listing_assignments_match':True, 'all_181_production_costs_match_app':True, 'editable_formula_recalculation_passed':True}
(root/'verification.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
