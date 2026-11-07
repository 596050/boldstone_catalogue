"""Transplant only native observations; preserve workbook features and formulas."""
import copy
import hashlib
import json
import math
import re
import sys
import xml.etree.ElementTree as E
import zipfile
from pathlib import Path

OUT = Path(__file__).parent
ROOT = Path('/Users/tprice/Documents/boldstone')
sys.path.insert(0, str(ROOT / 'catalogue-review/scripts'))
from import_saatchi_snapshot import Xlsx, Q, NS, U, R, column_index

read = lambda name: json.loads((OUT / name).read_text())
plan = read('plan.json')
old, auth = Xlsx(OUT / 'previous-catalogue.xlsx'), Xlsx(OUT / 'authored.xlsx')
E.register_namespace('', U)
E.register_namespace('r', R)
parts = dict(old.parts)
changed = set()
cache_changes = []


def same(a, b):
    if isinstance(b, (int, float)) and not isinstance(b, bool):
        return isinstance(a, (int, float)) and math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-6)
    return a == b


for sheet in old.paths:
    for address in old.cells[sheet]:
        formula = old.formula(sheet, address)
        if formula is not None and not same(auth.value(sheet, address), old.value(sheet, address)):
            cache_changes.append(dict(sheet=sheet, cell=address, before=old.value(sheet, address), before_formula=formula, value=auth.value(sheet, address), formula=formula, kind='RECALCULATED_CACHE_SAME_FORMULA'))
(OUT / 'recalculated-cache-changes.json').write_text(json.dumps(cache_changes, indent=2) + '\n')
for row in range(8, 189):
    for column in ['H', 'AF', 'AG', 'AH', 'AI', 'AJ', 'AK', 'AL', 'AM', 'AO', 'AP', 'AQ', 'BA']:
        assert same(old.value('Wall Sculptures', column + str(row)), auth.value('Wall Sculptures', column + str(row))), ('Unrelated core value recalculated differently', column, row)
assert not cache_changes, 'Review every changed formula cache before allowing a broader update'

for sheet, path in old.paths.items():
    patches = {p['cell']: p for p in plan['patches'] if p['sheet'] == sheet}
    if not patches:
        continue
    before = E.fromstring(old.parts[path])
    tree = copy.deepcopy(before)
    data = tree.find('s:sheetData', NS)
    rows = {int(r.get('r')): r for r in data}
    for address, patch in patches.items():
        assert old.value(sheet, address) == patch['before'] and old.formula(sheet, address) is None
        assert same(auth.value(sheet, address), patch['value']) and auth.formula(sheet, address) is None
        cell = copy.deepcopy(auth.cells[sheet][address])
        if isinstance(patch['value'], str):
            value = auth.value(sheet, address)
            cell.set('t', 'inlineStr')
            for child in list(cell):
                cell.remove(child)
            text = E.SubElement(E.SubElement(cell, Q('is')), Q('t'))
            text.text = value
            if value != value.strip() or '\n' in value:
                text.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
        rownum = int(re.search(r'\d+', address).group())
        row = rows[rownum]
        previous = next((c for c in row if c.get('r') == address), None)
        if previous is not None:
            cell.set('s', previous.get('s', '0'))
            row.remove(previous)
        else:
            column = re.sub(r'\d', '', address)
            sample = old.cells[sheet].get(column + '8', old.cells[sheet]['C8'])
            cell.set('s', sample.get('s', '0'))
        row.append(cell)
        row[:] = sorted(row, key=lambda c: column_index(c.get('r')))
    for change in plan.get('row_heights', []):
        if change['sheet'] == sheet:
            authored_row = E.fromstring(auth.parts[path]).find(f"s:sheetData/s:row[@r='{change['row']}']", NS)
            assert float(authored_row.get('ht')) == change['value']
            rows[change['row']].set('ht', authored_row.get('ht'))
            rows[change['row']].set('customHeight', authored_row.get('customHeight', '1'))
    allowed_heights = {str(c['row']): c['value'] for c in plan.get('row_heights', []) if c['sheet'] == sheet}
    for original_row in before.findall('s:sheetData/s:row', NS):
        expected_attributes = dict(original_row.attrib)
        row_number = original_row.get('r')
        if row_number in allowed_heights:
            expected_attributes.update(ht=str(allowed_heights[row_number]), customHeight='1')
        assert expected_attributes == rows[int(row_number)].attrib, ('Unrequested row layout change', row_number)
    after = {c.get('r'): c for c in tree.findall('s:sheetData/s:row/s:c', NS)}
    for address, cell in old.cells[sheet].items():
        if address not in patches:
            assert E.tostring(cell) == E.tostring(after[address]), (sheet, address)
    for tag in ['hyperlinks', 'sheetViews', 'mergeCells', 'tableParts', 'conditionalFormatting', 'dataValidations', 'dimension', 'cols', 'sheetFormatPr']:
        assert [E.tostring(c) for c in before.findall('s:' + tag, NS)] == [E.tostring(c) for c in tree.findall('s:' + tag, NS)]
    parts[path] = E.tostring(tree, encoding='utf-8', xml_declaration=True)
    changed.add(path)
assert changed == {old.paths['Wall Sculptures']}
assert all(parts[name] == body for name, body in old.parts.items() if name not in changed)
final = OUT / 'catalogue_wall_sculptures.xlsx'
with zipfile.ZipFile(final, 'w', zipfile.ZIP_DEFLATED) as z:
    for name, body in parts.items():
        z.writestr(name, body)
check = Xlsx(final)
assert list(check.paths) == list(old.paths) and set(check.parts) == set(old.parts)
patchset = {(p['sheet'], p['cell']) for p in plan['patches']}
for patch in plan['patches']:
    assert same(check.value(patch['sheet'], patch['cell']), patch['value'])
formula_count = 0
for sheet in old.paths:
    for address in old.cells[sheet]:
        assert old.formula(sheet, address) == check.formula(sheet, address)
        formula_count += old.formula(sheet, address) is not None
        if (sheet, address) not in patchset:
            assert old.value(sheet, address) == check.value(sheet, address)
    assert all(c.get('t') != 'e' for c in check.cells[sheet].values())
assert len({check.value('Wall Sculptures', 'AA' + str(row)) for row in range(8, 189)}) == 181
receipt = dict(status='PASS', sha256=hashlib.sha256(final.read_bytes()).hexdigest(), changed_cells=len(plan['patches']), fitted_rows=plan.get('row_heights', []), changed_parts=sorted(changed), all_other_parts_byte_identical=True, all_existing_formulas_preserved=formula_count, all_unrequested_values_preserved=True, faire_products_verified=plan['faire_products_verified'], new_instagram_publications=plan['new_instagram_publications'], component_records=181, sheets=list(check.paths), core_costs_prices_and_zero_labour_preserved=True)
(OUT / 'verification.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps(receipt, indent=2))
