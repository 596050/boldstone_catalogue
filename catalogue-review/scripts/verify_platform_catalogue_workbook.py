"""Independently check item joins, raw imported values and canonical title readback."""
from pathlib import Path
import json
import re
import sys
import xml.etree.ElementTree as E
import zipfile

OUT = Path(sys.argv[1]).resolve()
read = lambda name: json.loads((OUT / name).read_text())
NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
q = lambda name: '{' + NS['s'] + '}' + name
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
slug = lambda text: re.sub(r'[^a-z0-9]+', '_', str(text).lower().replace('£', 'gbp').replace('$', 'usd')).strip('_')
app = read('app-after.json')
products = {p['id']: p for p in app['products']}
with zipfile.ZipFile(OUT / 'catalogue_wall_sculptures.xlsx') as z:
    strings = [''.join(t.text or '' for t in s.iter(q('t'))) for s in E.fromstring(z.read('xl/sharedStrings.xml'))]
    relationships = {r.get('Id'): 'xl/' + r.get('Target').lstrip('/').removeprefix('xl/') for r in E.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
    sheets = {s.get('name'): relationships[s.get('{' + R + '}id')] for s in E.fromstring(z.read('xl/workbook.xml')).find('s:sheets', NS)}
    cells = {name: {c.get('r'): c for c in E.fromstring(z.read(path)).findall('s:sheetData/s:row/s:c', NS)} for name, path in sheets.items()}
    def value(sheet, address):
        c = cells[sheet].get(address)
        if c is None:
            return None
        if c.get('t') == 'inlineStr':
            return ''.join(t.text or '' for t in c.iter(q('t')))
        v = c.find('s:v', NS); v = v.text if v is not None else None
        assert c.get('t') != 'e', (sheet, address, v)
        if c.get('t') == 's':
            return strings[int(v)]
        return float(v) if v is not None and c.get('t', 'n') == 'n' else v
    rows = {value('Wall Sculptures', 'AA' + str(r)): r for r in range(8, 189)}
    assert set(rows) == set(products) and len(rows) == 181
    headers = {value('Wall Sculptures', address): re.sub(r'\d', '', address) for address in cells['Wall Sculptures'] if re.fullmatch('[A-Z]+7', address)}
    assert len(headers) == len([a for a in cells['Wall Sculptures'] if re.fullmatch('[A-Z]+7', a)])
    imported = 0; mapped = {'chairish': set(), 'ebay': set()}
    for record in read('matched-platform-records.json'):
        platform = record['platform']
        if len(record['catalogue_ids']) == 1:
            p = products[record['catalogue_ids'][0]]
            actual_sku = next(f['value'] for f in p['fields'] if f['key'] == 'Seller SKU')
            assert record['source']['SKU' if platform == 'chairish' else 'Custom label (SKU)'] == actual_sku
        else:
            assert record['sku'] == 'BOLD-ECHO-VERDIGRIS-PAIR'
            assert set(record['catalogue_ids']) == {'BSI-0BE032939501', 'BSI-EF421C1D2C92'}
        for pid in record['catalogue_ids']:
            row = rows[pid]; mapped[platform].add(pid)
            for field, expected in record['source'].items():
                column = headers[platform + '_observed_' + slug(field)]
                actual = value('Wall Sculptures', column + str(row))
                if expected in ('', None):
                    assert actual in ('', None), (platform, pid, field)
                elif field in ('Chairish ID', 'Item ID', 'Category ID', 'Condition ID'):
                    assert actual == str(expected)
                elif isinstance(expected, (int, float)):
                    assert isinstance(actual, (int, float)) and abs(actual - expected) < .0000001, (pid, field, actual, expected)
                else:
                    assert actual == expected, (pid, field, actual, expected)
                imported += 1
            if len(record['catalogue_ids']) > 1:
                assert value('Wall Sculptures', headers['ebay_catalogue_price_gbp'] + str(row)) is None
                assert value('Wall Sculptures', headers['ebay_catalogue_components_total_gbp'] + str(row)) == 98.4
                assert 'pair' in value('Wall Sculptures', headers['ebay_sale_unit_scope'] + str(row))
    for platform in ('chairish', 'ebay'):
        for pid in set(products) - mapped[platform]:
            assert value('Wall Sculptures', headers[platform + '_snapshot_scope'] + str(rows[pid])) == 'Not included in supplied platform snapshot'
            for header, col in headers.items():
                if str(header).startswith(platform + '_observed_'):
                    assert value('Wall Sculptures', col + str(rows[pid])) in (None, '')
    effects = 0
    for pid, row in rows.items():
        f = {f['key']: f['value'] for f in products[pid]['fields'] + products[pid]['listing_fields']}
        assert value('Wall Sculptures', 'AV' + str(row)) == f['Retail name']
        assert value('Wall Sculptures', 'AD' + str(row)) == f['Description']
        assert value('Website Copy', 'A' + str(row)) == f['Retail name']
        for column, key in [('D', 'Dimensions / depth'), ('E', 'Weight'), ('F', 'Material / finish'), ('G', 'Fixing'), ('I', 'Price')]:
            assert value('Wall Sculptures', column + str(row)) == f[key], (pid, key)
        assert value('Wall Sculptures', 'AM' + str(row)) == products[pid]['costing']['manufacturing_cost']
        if any(x['id'] != 'white' for x in products[pid]['costing']['inputs']['finishes']):
            assert 'finish' in value('Wall Sculptures', 'AV' + str(row)).lower()
            effects += 1
    assert effects == 73
    calc = read('calculation-verification.json')
    assert calc['status'] == 'PASS'
    receipt = {'status': 'PASS', 'components': 181, 'surface_effect_titles_checked': effects,
               'raw_platform_field_associations_checked': imported, 'chairish_component_matches': len(mapped['chairish']),
               'ebay_component_associations': len(mapped['ebay']), 'pair_price_not_overwritten': True,
               'nonmatched_components_not_given_invented_platform_values': True,
               'formula_cells_verified': calc['formula_cells_checked'], 'worksheets': len(sheets)}
    (OUT / 'independent-verification.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt))
