"""Preserve the catalogue package while adding artifact-authored packing cells."""
import copy
import hashlib
import json
import math
import posixpath
import re
import sys
import xml.etree.ElementTree as E
import zipfile
from pathlib import Path

OUT = Path(__file__).parent
ROOT = OUT.parents[2]
sys.path.insert(0, str(ROOT / 'catalogue-review/scripts'))
from import_saatchi_snapshot import Xlsx, Q, NS, U, R, column, column_index

read = lambda name: json.loads((OUT / name).read_text())
plan = read('plan.json')
assert read('calculation-verification.json')['status'] == 'PASS'
old = Xlsx(OUT / 'previous-catalogue.xlsx')
auth = Xlsx(OUT / 'authored.xlsx')
assert hashlib.sha256((OUT / 'previous-catalogue.xlsx').read_bytes()).hexdigest() == plan['source_sha256']
E.register_namespace('', U)
E.register_namespace('r', R)
parts = dict(old.parts)
changed = set()
patchset = {(p['sheet'], p['cell']) for p in plan['patches']}
assert len(patchset) == len(plan['patches'])


def close(a, b):
    if isinstance(b, (int, float)) and not isinstance(b, bool):
        return isinstance(a, (int, float)) and math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-6)
    return a == b


# Append/rebase imported styles; every existing style definition keeps its ID.
styles = E.fromstring(old.parts['xl/styles.xml'])
auth_styles = E.fromstring(auth.parts['xl/styles.xml'])
original_style_parts = {e.tag: [E.tostring(c) for c in e] for e in styles}


def section(tree, name):
    node = tree.find('s:' + name, NS)
    if node is None:
        node = E.Element(Q(name))
        order = ['numFmts', 'fonts', 'fills', 'borders', 'cellStyleXfs', 'cellXfs', 'cellStyles', 'dxfs', 'tableStyles', 'colors', 'extLst']
        index = next((i for i, e in enumerate(tree) if order.index(e.tag.split('}')[-1]) > order.index(name)), len(tree))
        tree.insert(index, node)
    return node


def merge_elements(name, transform=lambda e: e):
    target, source = section(styles, name), section(auth_styles, name)
    result = {}
    seen = {E.tostring(e): i for i, e in enumerate(target)}
    for i, value in enumerate(source):
        value = transform(copy.deepcopy(value))
        key = E.tostring(value)
        if key not in seen:
            seen[key] = len(target)
            target.append(value)
        result[i] = seen[key]
    target.set('count', str(len(target)))
    return result


numfmts = section(styles, 'numFmts')
numfmt_by_code = {e.get('formatCode'): int(e.get('numFmtId')) for e in numfmts}
used_numfmt_ids = {int(e.get('numFmtId')) for e in numfmts}
numfmt_map = {i: i for i in range(164)}
for e in section(auth_styles, 'numFmts'):
    old_id, code = int(e.get('numFmtId')), e.get('formatCode')
    if code not in numfmt_by_code:
        new_id = max({163} | used_numfmt_ids) + 1
        node = copy.deepcopy(e)
        node.set('numFmtId', str(new_id))
        numfmts.append(node)
        used_numfmt_ids.add(new_id)
        numfmt_by_code[code] = new_id
    numfmt_map[old_id] = numfmt_by_code[code]
numfmts.set('count', str(len(numfmts)))

maps = {name: merge_elements(name) for name in ['fonts', 'fills', 'borders']}


def rebase_xf(e, include_base=False):
    for attr, name in [('fontId', 'fonts'), ('fillId', 'fills'), ('borderId', 'borders')]:
        if attr in e.attrib:
            e.set(attr, str(maps[name][int(e.get(attr))]))
    if 'numFmtId' in e.attrib:
        e.set('numFmtId', str(numfmt_map[int(e.get('numFmtId'))]))
    if include_base and 'xfId' in e.attrib:
        e.set('xfId', str(base_xfs[int(e.get('xfId'))]))
    return e


base_xfs = merge_elements('cellStyleXfs', rebase_xf)
cell_xfs = merge_elements('cellXfs', lambda e: rebase_xf(e, True))
for tag, originals in original_style_parts.items():
    assert [E.tostring(e) for e in styles.find(tag)][:len(originals)] == originals, tag
parts['xl/styles.xml'] = E.tostring(styles, encoding='utf-8', xml_declaration=True)
changed.add('xl/styles.xml')

for sheet, path in old.paths.items():
    patches = {p['cell']: p for p in plan['patches'] if p['sheet'] == sheet}
    if not patches:
        continue
    original_tree = E.fromstring(old.parts[path])
    tree = copy.deepcopy(original_tree)
    data = tree.find('s:sheetData', NS)
    rows = {int(r.get('r')): r for r in data}
    for address, p in patches.items():
        assert close(old.value(sheet, address), p['before']), (sheet, address, 'before value')
        assert old.formula(sheet, address) == p['before_formula'], (sheet, address, 'before formula')
        assert close(auth.value(sheet, address), p['value']), (sheet, address, auth.value(sheet, address), p['value'])
        expected_formula = p['formula'].removeprefix('=') if p.get('formula') else None
        assert auth.formula(sheet, address) == expected_formula, (sheet, address, 'authored formula')
        cell = copy.deepcopy(auth.cells[sheet][address])
        if cell.get('t') == 's':
            value = auth.value(sheet, address)
            assert expected_formula is None
            cell.set('t', 'inlineStr')
            for child in list(cell):
                cell.remove(child)
            text = E.SubElement(E.SubElement(cell, Q('is')), Q('t'))
            text.text = value
            if value != value.strip() or '\n' in value:
                text.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
        rownum = int(re.search(r'\d+', address).group())
        if rownum not in rows:
            attrs = {'r': str(rownum)}
            if sheet == 'Channel Details' and rownum >= 188:
                attrs.update(ht='22', customHeight='1')
            rows[rownum] = E.Element(Q('row'), attrs)
            data.append(rows[rownum])
        row = rows[rownum]
        previous = next((e for e in row if e.get('r') == address), None)
        if previous is not None:
            cell.set('s', previous.get('s', '0'))
            row.remove(previous)
        else:
            cell.set('s', str(cell_xfs[int(cell.get('s', '0'))]))
        row.append(cell)
        row[:] = sorted(row, key=lambda e: column_index(e.get('r')))
    data[:] = sorted(data, key=lambda e: int(e.get('r')))
    dimension = tree.find('s:dimension', NS)
    if dimension is None:
        dimension = E.Element(Q('dimension'))
        tree.insert(1 if len(tree) and tree[0].tag == Q('sheetPr') else 0, dimension)
    cols = tree.find('s:cols', NS)
    if cols is None:
        cols = E.Element(Q('cols'))
        tree.insert(list(tree).index(data), cols)
    if sheet == 'Wall Sculptures':
        dimension.set('ref', 'A1:' + column(plan['last_column']) + '188')
        first, last, width = plan['first_added_column'], plan['last_column'], '32'
    else:
        assert sheet == 'Channel Details'
        dimension.set('ref', 'A1:AK194')
        first, last, width = 16, 37, '28'
    assert all(int(c.get('max')) < first for c in cols), (sheet, 'existing columns overlap')
    E.SubElement(cols, Q('col'), {'min': str(first), 'max': str(last), 'width': width, 'customWidth': '1'})
    after = {c.get('r'): c for c in tree.findall('s:sheetData/s:row/s:c', NS)}
    for address, cell in old.cells[sheet].items():
        if address not in patches:
            assert E.tostring(cell) == E.tostring(after[address]), (sheet, address, 'unrequested cell')
    for tag in ['hyperlinks', 'sheetViews', 'mergeCells', 'tableParts', 'conditionalFormatting', 'dataValidations', 'autoFilter', 'sheetProtection', 'drawing']:
        assert [E.tostring(e) for e in original_tree.findall('s:' + tag, NS)] == [E.tostring(e) for e in tree.findall('s:' + tag, NS)], (sheet, tag)
    for oldrow in original_tree.findall('s:sheetData/s:row', NS):
        assert oldrow.attrib == rows[int(oldrow.get('r'))].attrib, (sheet, oldrow.get('r'), 'row attributes')
    parts[path] = E.tostring(tree, encoding='utf-8', xml_declaration=True)
    changed.add(path)

# Expand the original main table; preserve every old field and relationship.
master = old.paths['Wall Sculptures']
rid = E.fromstring(old.parts[master]).find('s:tableParts/s:tablePart', NS).get('{' + R + '}id')
relpath = posixpath.dirname(master) + '/_rels/' + posixpath.basename(master) + '.rels'
target = next(e.get('Target') for e in E.fromstring(old.parts[relpath]) if e.get('Id') == rid)
tablepath = target.lstrip('/') if target.startswith('/') else posixpath.normpath(posixpath.dirname(master) + '/' + target)
table = E.fromstring(old.parts[tablepath])
columns = table.find('s:tableColumns', NS)
assert len(columns) == plan['first_added_column'] - 1
old_columns = [E.tostring(e) for e in columns]
for name in plan['added_headers']:
    index = column_index(plan['headers'][name])
    E.SubElement(columns, Q('tableColumn'), {'id': str(index), 'name': name})
columns.set('count', str(len(columns)))
assert [E.tostring(e) for e in columns][:len(old_columns)] == old_columns
table.set('ref', 'A7:' + column(plan['last_column']) + '188')
auto = table.find('s:autoFilter', NS)
if auto is not None:
    auto.set('ref', table.get('ref'))
parts[tablepath] = E.tostring(table, encoding='utf-8', xml_declaration=True)
changed.add(tablepath)
assert changed == {'xl/styles.xml', old.paths['Wall Sculptures'], old.paths['Channel Details'], tablepath}
assert all(parts[k] == v for k, v in old.parts.items() if k not in changed)
final = OUT / 'catalogue_wall_sculptures.xlsx'
with zipfile.ZipFile(final, 'w', zipfile.ZIP_DEFLATED) as z:
    for name, body in parts.items():
        z.writestr(name, body)

check = Xlsx(final)
assert list(check.paths) == list(old.paths)
assert len(check.parts) == len(old.parts)
for p in plan['patches']:
    assert close(check.value(p['sheet'], p['cell']), p['value']), (p['sheet'], p['cell'], 'final value')
    assert check.formula(p['sheet'], p['cell']) == (p['formula'].removeprefix('=') if p.get('formula') else None)
preserved_formulas = changed_formulas = 0
for sheet in old.paths:
    for address in old.cells[sheet]:
        if (sheet, address) not in patchset:
            assert check.formula(sheet, address) == old.formula(sheet, address)
            assert check.value(sheet, address) == old.value(sheet, address)
            preserved_formulas += old.formula(sheet, address) is not None
        elif old.formula(sheet, address) is not None:
            changed_formulas += 1
    for address, cell in check.cells[sheet].items():
        assert cell.get('t') != 'e', (sheet, address)
assert len({check.value('Wall Sculptures', f'AA{r}') for r in range(8, 189)}) == 181
receipt = dict(status='PASS', sha256=hashlib.sha256(final.read_bytes()).hexdigest(), cells_updated=len(plan['patches']), original_parts=len(old.parts), changed_parts=sorted(changed), all_other_parts_byte_identical=True, existing_style_definitions_and_ids_preserved=True, all_unrequested_values_and_formulas_preserved=True, preserved_existing_formulas=preserved_formulas, intentionally_updated_existing_formulas=changed_formulas, component_records=181, valid_packing_estimates=180, missing_dimension_holds=1, core_retail_manufacturing_and_labour_preserved=True, native_platform_observations_preserved=True, sheets=list(check.paths))
(OUT / 'verification.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps(receipt, indent=2))
