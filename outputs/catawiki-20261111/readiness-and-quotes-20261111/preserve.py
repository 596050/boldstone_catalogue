"""Transplant only the requested Artifact-authored cells, retaining all other features."""
from pathlib import Path
import copy, hashlib, json, math, re, sys, xml.etree.ElementTree as E, zipfile
ROOT=Path('/Users/tprice/Documents/boldstone'); OUT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'catalogue-review/scripts'))
from import_saatchi_snapshot import Xlsx,Q,NS,U,R,column_index
plan=json.loads((OUT/'plan.json').read_text())
old=Xlsx(OUT/'previous-catalogue.xlsx'); auth=Xlsx(OUT/'authored.xlsx')
assert old.paths==auth.paths
same=lambda a,b: math.isclose(a,b,rel_tol=1e-10,abs_tol=1e-6) if isinstance(a,(float,int)) and isinstance(b,(float,int)) else a==b
parts=dict(old.parts); sheet='Wall Sculptures'; sp=old.paths[sheet]
E.register_namespace('',U); E.register_namespace('r',R)
tree=E.fromstring(parts[sp]); rows={int(r.get('r')):r for r in tree.find('s:sheetData',NS)}
changed={p['cell'] for p in plan['patches']}
for p in plan['patches']:
    a=p['cell']; assert same(old.value(sheet,a),p['before'])
    assert same(auth.value(sheet,a),p['value']),a
    assert auth.formula(sheet,a)==p.get('formula'),a
    cell=copy.deepcopy(auth.cells[sheet][a]); cell.set('s',old.cells[sheet][a].get('s','0'))
    if isinstance(p['value'],str):
        for child in list(cell):
            if child.tag!=Q('f'):cell.remove(child)
        if p.get('formula'):cell.set('t','str');E.SubElement(cell,Q('v')).text=p['value']
        else:
            cell.set('t','inlineStr'); text=E.SubElement(E.SubElement(cell,Q('is')),Q('t'));text.text=p['value'];text.set('{http://www.w3.org/XML/1998/namespace}space','preserve')
    row=rows[int(re.search(r'\d+',a)[0])]
    previous=next(c for c in row if c.get('r')==a);row.remove(previous);row.append(cell);row[:]=sorted(row,key=lambda c:column_index(c.get('r')))
parts[sp]=E.tostring(tree,encoding='utf-8',xml_declaration=True)
target=OUT/'catalogue_wall_sculptures.xlsx'
with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
    for name,body in parts.items():z.writestr(name,body)
result=Xlsx(target); formulas=0;preserved=0
for s,cells in old.cells.items():
    assert set(cells)==set(result.cells[s])
    for a,c in cells.items():
        assert old.formula(s,a)==result.formula(s,a),(s,a)
        formulas+=bool(old.formula(s,a))
        if s!=sheet or a not in changed:
            assert E.tostring(c)==E.tostring(result.cells[s][a]),(s,a)
            preserved+=1
for p in plan['patches']:assert same(result.value(sheet,p['cell']),p['value']),p['cell']
assert all(parts[n]==body for n,body in old.parts.items() if n!=sp)
# Independent reader, used only for readback; no openpyxl authoring.
from openpyxl import load_workbook
from datetime import datetime
book=load_workbook(target,read_only=True,data_only=True)
expected={(int(re.search(r'\d+',p['cell'])[0]),column_index(p['cell'])):p for p in plan['patches']}
independent_count=0
for ri,values in enumerate(book[sheet].iter_rows(min_row=8,max_row=188,values_only=True),8):
    for ci,v in enumerate(values,1):
        if (ri,ci) not in expected:continue
        p=expected[(ri,ci)]
        if isinstance(v,datetime):v=(v-datetime(1899,12,30)).total_seconds()/86400
        assert same(v,p['value']),p['cell']
        independent_count+=1
book.close()
assert independent_count==len(plan['patches'])
receipt={'status':'PASS','sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'patched_cells':len(changed),
         'all_existing_formulas_preserved':formulas,'unrequested_cells_preserved':preserved,
         'all_other_parts_byte_identical':True,'independent_reader':'openpyxl 3.1.5 read-only','readers_agree':True,
         'sheets':len(result.paths),'core_prices_costs_labour_and_other_platforms_unchanged':True,'counts':plan['counts']}
(OUT/'verification.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt,indent=2))
