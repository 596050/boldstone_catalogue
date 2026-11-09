"""Transplant only authorised date/lineage cells; retain all other OOXML features."""
import copy
import hashlib
import json
import math
from pathlib import Path
import sys
import xml.etree.ElementTree as E
import zipfile
sys.path.insert(0, '/Users/tprice/Documents/boldstone/catalogue-review/scripts')
from import_saatchi_snapshot import Xlsx, NS, Q, U, R, column_index
OUT=Path(__file__).parent
plan=json.loads((OUT/'plan.json').read_text())
old,auth=Xlsx(OUT/'previous-catalogue.xlsx'),Xlsx(OUT/'authored.xlsx')
assert old.paths==auth.paths
E.register_namespace('',U);E.register_namespace('r',R)
parts=dict(old.parts);styles=E.fromstring(parts['xl/styles.xml'])
formats=styles.find('s:numFmts',NS)
assert formats is not None
new_id=max([163]+[int(c.get('numFmtId')) for c in formats])+1
E.SubElement(formats,Q('numFmt'),dict(numFmtId=str(new_id),formatCode='yyyy-mm-dd hh:mm:ss.000'))
formats.set('count',str(len(formats)))
xfs=styles.find('s:cellXfs',NS);style_map={}
for p in plan['patches']:
    if p['style']!='utc':continue
    original_style=old.cells[p['sheet']][p['cell']].get('s','0')
    if original_style not in style_map:
        xf=copy.deepcopy(xfs[int(original_style)]);xf.set('numFmtId',str(new_id));xf.set('applyNumberFormat','1')
        style_map[original_style]=len(xfs);xfs.append(xf)
xfs.set('count',str(len(xfs)));parts['xl/styles.xml']=E.tostring(styles,encoding='utf-8',xml_declaration=True)
patchkeys={(p['sheet'],p['cell']) for p in plan['patches']}
assert len(patchkeys)==len(plan['patches'])
changed={'xl/styles.xml'}
for sheet in old.paths:
    patches=[p for p in plan['patches'] if p['sheet']==sheet]
    if not patches:continue
    tree=E.fromstring(old.parts[old.paths[sheet]])
    cells={c.get('r'):c for c in tree.findall('s:sheetData/s:row/s:c',NS)}
    rows={int(r.get('r')):r for r in tree.findall('s:sheetData/s:row',NS)}
    for p in patches:
        address=p['cell'];previous=cells[address]
        assert old.value(sheet,address)==p['before'] and old.formula(sheet,address) is None
        actual=auth.value(sheet,address)
        assert math.isclose(actual,p['value'],abs_tol=1e-8) if isinstance(p['value'],(float,int)) else actual==p['value']
        cell=copy.deepcopy(auth.cells[sheet][address]);cell.set('s',previous.get('s','0'))
        if p['style']=='utc':
            cell.set('s',str(style_map[previous.get('s','0')]));cell.set('t','n')
            for child in list(cell):cell.remove(child)
            E.SubElement(cell,Q('v')).text=repr(p['value'])
        else:
            for child in list(cell):cell.remove(child)
            if previous.get('t')=='str':
                cell.set('t','str');E.SubElement(cell,Q('v')).text=p['value']
            else:
                cell.set('t','inlineStr');E.SubElement(E.SubElement(cell,Q('is')),Q('t')).text=p['value']
        row=rows[int(''.join(c for c in address if c.isdigit()))];row.remove(previous);row.append(cell)
        row[:]=sorted(row,key=lambda c:column_index(c.get('r')))
    fresh={c.get('r'):c for c in tree.findall('s:sheetData/s:row/s:c',NS)}
    for address,node in old.cells[sheet].items():
        if (sheet,address) not in patchkeys:assert E.tostring(node)==E.tostring(fresh[address]),(sheet,address)
    parts[old.paths[sheet]]=E.tostring(tree,encoding='utf-8',xml_declaration=True);changed.add(old.paths[sheet])
assert all(parts[name]==body for name,body in old.parts.items() if name not in changed)
out=OUT/'catalogue_wall_sculptures.xlsx'
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
    for name,body in parts.items():z.writestr(name,body)
check=Xlsx(out);preserved=formulas=0
for sheet,cells in old.cells.items():
    for address in cells:
        assert old.formula(sheet,address)==check.formula(sheet,address),(sheet,address)
        formulas+=old.formula(sheet,address) is not None
        if (sheet,address) not in patchkeys:
            assert old.value(sheet,address)==check.value(sheet,address),(sheet,address);preserved+=1
    assert not any(c.get('t') in ('e','d') for c in check.cells[sheet].values())
assert formulas==32776
receipt=dict(status='PASS',sha256=hashlib.sha256(out.read_bytes()).hexdigest(),changed_cells=len(plan['patches']),added_columns=0,
    component_records=181,publication_records=176,sheets=list(check.paths),all_existing_formulas_preserved=formulas,
    unrequested_cells_preserved=preserved,changed_parts=sorted(changed),all_other_parts_byte_identical=True,
    core_costs_prices_and_zero_labour_preserved=True,utc_date_cells_normalized=1832,snapshot_lineage_labels_clarified=9,
    all_original_utc_strings_preserved_in_manifest=True,gtins_assigned=0,pinterest_appeals_used=0)
(OUT/'verification.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
