"""Independent all-cell, formula-result and hyperlink reconciliation."""
from pathlib import Path
from datetime import datetime,date,timezone
import hashlib,json,zipfile,xml.etree.ElementTree as E
import openpyxl
OUT=Path(__file__).resolve().parent
read=lambda name:json.loads((OUT/name).read_text())
changes=read('workbook-changes.json');snap=read('catalogue-snapshot-latest.json')
def norm(v):return v.isoformat() if isinstance(v,(date,datetime)) else None if v=='' else v
def cells(book):return {s.title:{c.coordinate:norm(c.value) for row in s.iter_rows() for c in row if norm(c.value) is not None} for s in book}
a=openpyxl.load_workbook(OUT/'previous-catalogue.xlsx',read_only=True,data_only=False)
b=openpyxl.load_workbook(OUT/'catalogue_wall_sculptures.xlsx',read_only=True,data_only=False)
assert a.sheetnames==b.sheetnames==changes['sheets']
before,after=cells(a),cells(b);expected={s:dict(v) for s,v in before.items()}
for p in changes['patches']:
    assert expected[p['sheet']].get(p['cell'])==norm(p['before']),p
    if norm(p['value']) is None:expected[p['sheet']].pop(p['cell'],None)
    else:expected[p['sheet']][p['cell']]=norm(p['value'])
for cell in list(expected['Images']):
    if int(''.join(c for c in cell if c.isdigit()))>=8:expected['Images'].pop(cell)
for row,values in enumerate(changes['image_rows'],8):
    for col,value in enumerate(values,1):
        if norm(value) is not None:expected['Images'][f'{openpyxl.utils.get_column_letter(col)}{row}']=norm(value)
def eq(sheet,cell,left,right):
    if left==right:return True
    if sheet=='Specification Sources' and cell.startswith('N'):
        try:return abs((datetime.fromisoformat(left)-datetime.fromisoformat(right)).total_seconds())<.001
        except (ValueError,TypeError):pass
    return False
errors=[(s,c,expected[s].get(c),after[s].get(c)) for s in expected for c in expected[s].keys()|after[s].keys() if not eq(s,c,expected[s].get(c),after[s].get(c))]
(OUT/'cell-differences.json').write_text(json.dumps(errors,indent=2))
assert not errors,(len(errors),errors[:4])
cached=openpyxl.load_workbook(OUT/'catalogue_wall_sculptures.xlsx',read_only=True,data_only=True)
values={s.title:{c.coordinate:c.value for row in s.iter_rows() for c in row if c.value is not None} for s in cached}
formula_errors=[(s,c,v) for s,cells_ in values.items() for c,v in cells_.items() if isinstance(v,str) and v in ('#REF!','#DIV/0!','#VALUE!','#NAME?','#N/A','#NUM!','#NULL!','#SPILL!','#CALC!')]
assert not formula_errors,formula_errors[:4]
products={p['id']:p for p in snap['products']}
for row in range(8,189):
    pid=values['Wall Sculptures'][f'AA{row}'];cost=products[pid]['costing']
    assert cost['labour_cost']==0 and cost['total_cost']==cost['manufacturing_cost'],pid
    for sheet,col,key in [('Wall Sculptures','AM','manufacturing_cost'),('Wall Sculptures','AL','labour_cost'),('Wall Sculptures','BA','total_cost'),
                           ('Manufacturing Costs','W','manufacturing_cost'),('Manufacturing Costs','V','labour_cost'),('Manufacturing Costs','X','total_cost'),
                           ('Upload Plan','R','manufacturing_cost'),('Upload Plan','AD','labour_cost'),('Upload Plan','AE','total_cost')]:
        actual=values[sheet][f'{col}{row}'];assert abs(actual-cost[key])<.005,(pid,sheet,col,actual,cost[key])
    assert abs(values['Wall Sculptures'][f'H{row}']-cost['pricing']['marked_up_price'])<.005,pid
assert values['Cost Rates']['D11']==0
NS='http://schemas.openxmlformats.org/spreadsheetml/2006/main';R='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
def native(file):
    result={}
    with zipfile.ZipFile(file) as z:
        for i,sheet in enumerate(changes['sheets'],1):
            t=E.fromstring(z.read(f'xl/worksheets/sheet{i}.xml'));rn=f'xl/worksheets/_rels/sheet{i}.xml.rels'
            rel={x.get('Id'):x.get('Target') for x in E.fromstring(z.read(rn))} if rn in z.namelist() else {}
            links={x.get('ref'):rel[x.get('{'+R+'}id')] if x.get('{'+R+'}id') else x.get('location') for x in t.findall('{'+NS+'}hyperlinks/{'+NS+'}hyperlink')}
            pane=t.find('{'+NS+'}sheetViews/{'+NS+'}sheetView/{'+NS+'}pane')
            result[sheet]={'links':links,'pane':pane.attrib if pane is not None else None}
    return result
old=native(OUT/'previous-catalogue.xlsx');new=native(OUT/'catalogue_wall_sculptures.xlsx')
for sheet in old:
    want={} if sheet=='Images' else dict(old[sheet]['links'])
    for item in changes['new_hyperlinks']:
        if item['sheet']!=sheet:continue
        if item['target']:want[item['cell']]=item['target']
        else:want.pop(item['cell'],None)
    assert new[sheet]['links']==want,('links',sheet)
    assert old[sheet]['pane']==new[sheet]['pane'],('pane',sheet)
result={'status':'PASS','verified_utc':datetime.now(timezone.utc).isoformat(),'app_snapshot_utc':snap['created_utc'],
        'event_cutoff':snap['event_cutoff'],'summary':snap['summary'],'sha256':hashlib.sha256((OUT/'catalogue_wall_sculptures.xlsx').read_bytes()).hexdigest(),
        'products_costs_and_prices_reconciled':181,'image_rows':len(changes['image_rows']),'unexpected_value_or_formula_changes':0,
        'formula_errors':0,'hyperlinks_verified':sum(len(s['links']) for s in new.values()),'freeze_panes_preserved':True,
        'labour_dependency_test':read('labour-dependency-check.json')['status'],
        'zero_labour_components':len(products),'labour_hourly_rate':0}
(OUT/'verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
