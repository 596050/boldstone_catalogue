"""Keep original workbook features; transplant only artifact-authored cells."""
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

ROOT=Path('/Users/tprice/Documents/boldstone')
OUT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'catalogue-review/scripts'))
from import_saatchi_snapshot import Xlsx,Q,NS,U,R,column,column_index
read=lambda name:json.loads((OUT/name).read_text())
plan=read('plan.json')
old,auth=Xlsx(OUT/'previous-catalogue.xlsx'),Xlsx(OUT/'authored.xlsx')
same=lambda a,b:math.isclose(a,b,rel_tol=1e-10,abs_tol=1e-6) if isinstance(a,(int,float)) and isinstance(b,(int,float)) and not isinstance(a,bool) and not isinstance(b,bool) else a==b
E.register_namespace('',U);E.register_namespace('r',R)
parts=dict(old.parts)
styles=E.fromstring(parts['xl/styles.xml'])
formats=styles.find('s:numFmts',NS)
if formats is None:
    formats=E.Element(Q('numFmts'),dict(count='0'));styles.insert(0,formats)
format_id=max([163]+[int(c.get('numFmtId')) for c in formats])+1
E.SubElement(formats,Q('numFmt'),dict(numFmtId=str(format_id),formatCode='yyyy-mm-dd hh:mm:ss.000 "UTC"'))
formats.set('count',str(len(formats)))
xfs=styles.find('s:cellXfs',NS)
date_style=len(xfs)
xf=copy.deepcopy(xfs[int(old.cells['Wall Sculptures']['C8'].get('s','0'))])
xf.set('numFmtId',str(format_id));xf.set('applyNumberFormat','1')
xfs.append(xf);xfs.set('count',str(len(xfs)))
text_style=len(xfs)
text_xf=copy.deepcopy(xfs[int(old.cells['Wall Sculptures']['C8'].get('s','0'))])
text_xf.set('numFmtId','49');text_xf.set('applyNumberFormat','1');text_xf.set('applyAlignment','1')
align=text_xf.find('s:alignment',NS)
if align is None:align=E.SubElement(text_xf,Q('alignment'))
align.set('vertical','top');align.set('wrapText','1')
xfs.append(text_xf);xfs.set('count',str(len(xfs)))
parts['xl/styles.xml']=E.tostring(styles,encoding='utf-8',xml_declaration=True)
changes=[]
for sheet,cells in old.cells.items():
    for address in cells:
        if old.formula(sheet,address) is not None and not same(old.value(sheet,address),auth.value(sheet,address)):
            changes.append(dict(sheet=sheet,cell=address,before=old.value(sheet,address),authored=auth.value(sheet,address),formula=old.formula(sheet,address)))
(OUT/'formula-cache-comparison.json').write_text(json.dumps(changes,indent=2)+'\n')
assert not changes,'Unexpected recalculation differences require review before publication'
assert list(old.paths)==list(auth.paths)

path=old.paths['Wall Sculptures']
before=E.fromstring(old.parts[path]);tree=copy.deepcopy(before)
data=tree.find('s:sheetData',NS);rows={int(r.get('r')):r for r in data}
patchset={p['cell']:p for p in plan['patches']}
assert len(patchset)==len(plan['patches'])
for address,patch in patchset.items():
    assert same(old.value('Wall Sculptures',address),patch['before'])
    assert old.formula('Wall Sculptures',address) is None
    assert same(auth.value('Wall Sculptures',address),patch['value'])
    assert auth.formula('Wall Sculptures',address) == patch.get('formula')
    cell=copy.deepcopy(auth.cells['Wall Sculptures'].get(address,E.Element(Q('c'),dict(r=address))))
    if isinstance(patch['value'],str) and not patch.get('formula'):
        cell.set('t','inlineStr')
        for child in list(cell):cell.remove(child)
        text=E.SubElement(E.SubElement(cell,Q('is')),Q('t'));text.text=patch['value']
        if '\n' in patch['value'] or patch['value']!=patch['value'].strip():text.set('{http://www.w3.org/XML/1998/namespace}space','preserve')
    number=int(re.search(r'\d+',address).group());row=rows[number]
    previous=next((c for c in row if c.get('r')==address),None)
    if previous is not None:
        cell.set('s',str(date_style) if patch.get('style')=='utc' else previous.get('s','0'));row.remove(previous)
        if patch.get('style')=='text' and isinstance(patch['value'],str) and patch['value'].isdecimal():cell.set('s',str(text_style))
    else:
        if patch.get('style')=='utc':cell.set('s',str(date_style))
        elif patch.get('style')=='text':cell.set('s',str(text_style))
        else:
            sample={'header':'A7','money':'H8','ratio':'UZ8','integer':'A8','text':'C8'}[patch.get('style','text')]
            cell.set('s',old.cells['Wall Sculptures'][sample].get('s','0'))
    row.append(cell);row[:]=sorted(row,key=lambda c:column_index(c.get('r')))
last=column(plan['last_added_column'])
dimension=tree.find('s:dimension',NS)
if dimension is None:
    dimension=E.Element(Q('dimension'));tree.insert(1 if tree.find('s:sheetPr',NS) is not None else 0,dimension)
dimension.set('ref','A1:'+last+'188')
cols=tree.find('s:cols',NS)
assert cols is not None
E.SubElement(cols,Q('col'),dict(min=str(plan['first_added_column']),max=str(plan['last_added_column']),width='32',customWidth='1'))
after={c.get('r'):c for c in tree.findall('s:sheetData/s:row/s:c',NS)}
for address,cell in old.cells['Wall Sculptures'].items():
    if address not in patchset:assert E.tostring(cell)==E.tostring(after[address]),address
for tag in ['hyperlinks','sheetViews','mergeCells','tableParts','conditionalFormatting','dataValidations','sheetFormatPr']:
    assert [E.tostring(c) for c in before.findall('s:'+tag,NS)]==[E.tostring(c) for c in tree.findall('s:'+tag,NS)],tag
for row in before.findall('s:sheetData/s:row',NS):assert row.attrib==rows[int(row.get('r'))].attrib
parts[path]=E.tostring(tree,encoding='utf-8',xml_declaration=True)

# Preserve and extend the existing native catalogue table and its filter bounds.
relpath=posixpath.dirname(path)+'/_rels/'+posixpath.basename(path)+'.rels'
relations={e.get('Id'):e.get('Target') for e in E.fromstring(old.parts[relpath])}
tableid=before.find('s:tableParts/s:tablePart',NS).get('{'+R+'}id')
target=relations[tableid].lstrip('/')
tablepath=target if target.startswith('xl/') else posixpath.normpath(posixpath.dirname(path)+'/'+target)
table=E.fromstring(old.parts[tablepath]);tablecols=table.find('s:tableColumns',NS)
assert len(tablecols)==plan['first_added_column']-1
for i,h in enumerate(plan['new_headers'],plan['first_added_column']):E.SubElement(tablecols,Q('tableColumn'),dict(id=str(i),name=h))
tablecols.set('count',str(len(tablecols)));table.set('ref','A7:'+last+'188')
autofilter=table.find('s:autoFilter',NS)
if autofilter is not None:autofilter.set('ref',table.get('ref'))
parts[tablepath]=E.tostring(table,encoding='utf-8',xml_declaration=True)
changed={path,tablepath,'xl/styles.xml'}
assert all(parts[n]==body for n,body in old.parts.items() if n not in changed)
final=OUT/'catalogue_wall_sculptures.xlsx'
with zipfile.ZipFile(final,'w',zipfile.ZIP_DEFLATED) as archive:
    for name,body in parts.items():archive.writestr(name,body)
check=Xlsx(final)
assert old.paths==check.paths and set(old.parts)==set(check.parts)
for patch in plan['patches']:assert same(check.value(patch['sheet'],patch['cell']),patch['value']),patch['cell']
preserved=0;formulas=0
for sheet,cells in old.cells.items():
    for address in cells:
        assert old.formula(sheet,address)==check.formula(sheet,address),(sheet,address)
        formulas+=old.formula(sheet,address) is not None
        if sheet!='Wall Sculptures' or address not in patchset:
            assert old.value(sheet,address)==check.value(sheet,address),(sheet,address)
            preserved+=1
    assert not any(c.get('t')=='e' for c in check.cells[sheet].values()),sheet
assert len({check.value('Wall Sculptures','AA'+str(n)) for n in range(8,189)})==181
receipt=dict(status='PASS',sha256=hashlib.sha256(final.read_bytes()).hexdigest(),changed_cells=len(plan['patches']),
    added_columns=len(plan['new_headers']),component_records=181,publication_records=176,sheets=list(check.paths),
    all_existing_formulas_preserved=formulas,unrequested_cells_preserved=preserved,
    changed_parts=sorted(changed),all_other_parts_byte_identical=True,
    core_costs_prices_and_zero_labour_preserved=True,
    new_formula_cells=sum(bool(p.get('formula')) for p in plan['patches']),
    counts=plan['counts'], scope=plan['scope'],
    product_facts_prices_costs_stock_gtins_and_photo_choices_preserved=True,
    google_private_sheet_copy_requires_refresh=True,
    private_google_sheet_id='1T-t6Mgy_TiMKzV8P45o1hvH2tpndicPO8Pq05KG8ZAs',
    master_columns=plan['last_added_column'])
(OUT/'verification.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt,indent=2))
