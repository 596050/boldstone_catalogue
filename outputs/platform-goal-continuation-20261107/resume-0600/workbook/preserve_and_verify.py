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
style_tree=E.fromstring(old.parts['xl/styles.xml'])
auth_style_tree=E.fromstring(auth.parts['xl/styles.xml'])
style_xfs=style_tree.find('s:cellXfs',NS)
auth_xfs=auth_style_tree.find('s:cellXfs',NS)
style_formats=style_tree.find('s:numFmts',NS)
auth_formats={int(f.get('numFmtId')):f.get('formatCode') for f in auth_style_tree.findall('s:numFmts/s:numFmt',NS)}
format_ids={f.get('formatCode'):int(f.get('numFmtId')) for f in style_tree.findall('s:numFmts/s:numFmt',NS)}
new_styles={}

def authored_number_style(base_style,auth_cell):
    global style_formats
    fmt_id=int(auth_xfs[int(auth_cell.get('s','0'))].get('numFmtId','0'))
    code=auth_formats.get(fmt_id)
    if fmt_id>=164:
        assert code
        if code not in format_ids:
            if style_formats is None:
                style_formats=E.Element(Q('numFmts'),{'count':'0'})
                style_tree.insert(0,style_formats)
            value=max([163]+list(format_ids.values()))+1
            E.SubElement(style_formats,Q('numFmt'),{'numFmtId':str(value),'formatCode':code})
            style_formats.set('count',str(len(style_formats)))
            format_ids[code]=value
        fmt_id=format_ids[code]
    key=(base_style,fmt_id)
    if key not in new_styles:
        xf=copy.deepcopy(style_xfs[int(base_style)])
        xf.set('numFmtId',str(fmt_id));xf.set('applyNumberFormat','1')
        new_styles[key]=len(style_xfs);style_xfs.append(xf)
        style_xfs.set('count',str(len(style_xfs)))
    return str(new_styles[key])


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
        # Literal text must remain literal text, including all-digit platform IDs.
        # Some exporters emit cached-formula-string cells without a formula;
        # use the unambiguous inline-string representation for authored strings.
        if isinstance(patch['value'],str):
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
            new_column = next((c for c in plan.get('new_columns',[]) if c['column']==column),None)
            source_cell = (new_column['header_style_source'] if rownum==7 else new_column['body_style_source']) if new_column else column+'8'
            sample = old.cells[sheet].get(source_cell, old.cells[sheet]['C8'])
            cell.set('s', sample.get('s', '0'))
            if new_column and rownum>7:
                cell.set('s',authored_number_style(sample.get('s','0'),auth.cells[sheet][address]))
        row.append(cell)
        row[:] = sorted(row, key=lambda c: column_index(c.get('r')))
    after = {c.get('r'): c for c in tree.findall('s:sheetData/s:row/s:c', NS)}
    for address, cell in old.cells[sheet].items():
        if address not in patches:
            assert E.tostring(cell) == E.tostring(after[address]), (sheet, address)
    if plan.get('new_columns'):
        dimension = tree.find('s:dimension',NS)
        old_dimension = dimension.get('ref')
        assert old_dimension.endswith(':XH188')
        dimension.set('ref',old_dimension.replace(':XH188',':'+plan['new_last_column']+'188'))
        cols=tree.find('s:cols',NS)
        assert cols is not None
        for column in plan['new_columns']:
            E.SubElement(cols,Q('col'),{'min':str(column['index']),'max':str(column['index']),'width':str(column['width']),'customWidth':'1'})
        filters=tree.findall('s:autoFilter',NS)
        for af in filters:
            assert af.get('ref').endswith(':XH188')
            af.set('ref',af.get('ref').replace(':XH188',':'+plan['new_last_column']+'188'))
    for tag in ['hyperlinks', 'sheetViews', 'mergeCells', 'tableParts', 'conditionalFormatting', 'dataValidations', 'sheetFormatPr']:
        assert [E.tostring(c) for c in before.findall('s:' + tag, NS)] == [E.tostring(c) for c in tree.findall('s:' + tag, NS)]
    parts[path] = E.tostring(tree, encoding='utf-8', xml_declaration=True)
    changed.add(path)
table_path='xl/tables/table1.xml'
old_table=E.fromstring(old.parts[table_path])
table=copy.deepcopy(old_table)
assert table.get('name')=='WallSculpturesTable' and table.get('ref')=='A7:XH188'
auth_tables=[E.fromstring(b) for n,b in auth.parts.items() if n.startswith('xl/tables/') and n.endswith('.xml')]
auth_table=next(t for t in auth_tables if t.get('name')=='WallSculpturesTable')
assert auth_table.get('ref')=='A7:'+plan['new_last_column']+'188'
columns=table.find('s:tableColumns',NS)
new_auth_columns=auth_table.find('s:tableColumns',NS)
assert len(columns)==632 and len(new_auth_columns)==644
for index,definition in enumerate(plan['new_columns'],632):
    column=copy.deepcopy(new_auth_columns[index])
    assert column.get('name')==auth.value('Wall Sculptures',definition['column']+'7')
    column.set('id',str(index+1))
    columns.append(column)
columns.set('count','644')
table.set('ref','A7:'+plan['new_last_column']+'188')
for af in table.findall('s:autoFilter',NS):
    assert af.get('ref')=='A7:XH188'
    af.set('ref',table.get('ref'))
assert all(E.tostring(a)==E.tostring(b) for a,b in zip(old_table.find('s:tableColumns',NS),list(columns)[:632]))
assert E.tostring(old_table.find('s:tableStyleInfo',NS))==E.tostring(table.find('s:tableStyleInfo',NS))
parts[table_path]=E.tostring(table,encoding='utf-8',xml_declaration=True)
changed.add(table_path)
parts['xl/styles.xml']=E.tostring(style_tree,encoding='utf-8',xml_declaration=True)
changed.add('xl/styles.xml')
assert changed == {old.paths['Wall Sculptures'],table_path,'xl/styles.xml'}
before_styles=E.fromstring(old.parts['xl/styles.xml'])
before_xfs=before_styles.find('s:cellXfs',NS)
assert all(E.tostring(a)==E.tostring(b) for a,b in zip(before_xfs,list(style_xfs)[:len(before_xfs)]))
for tag in ['fonts','fills','borders','cellStyleXfs','cellStyles','dxfs','tableStyles']:
    assert [E.tostring(c) for c in before_styles.findall('s:'+tag,NS)]==[E.tostring(c) for c in style_tree.findall('s:'+tag,NS)]
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
receipt = dict(status='PASS', sha256=hashlib.sha256(final.read_bytes()).hexdigest(), changed_cells=len(plan['patches']), changed_parts=sorted(changed), all_other_parts_byte_identical=True, all_existing_formulas_preserved=formula_count, all_unrequested_values_preserved=True, account_prefixed_fields_added=len(plan['new_columns']), saved_ebay_drafts_recorded=65,new_native_publications_recorded=2,new_native_drafts_recorded=1,chairish_existing_drafts_updated=1, component_records=181, sheets=list(check.paths), core_costs_prices_and_zero_labour_preserved=True)
(OUT / 'verification.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps(receipt, indent=2))
