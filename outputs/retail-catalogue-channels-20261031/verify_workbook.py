"""Verify workbook values/formulas and native links without rewriting the artifact."""
from pathlib import Path
from datetime import date,datetime,timezone
import json,hashlib,zipfile,xml.etree.ElementTree as E
import openpyxl
OUT=Path(__file__).resolve().parent
read=lambda f:json.loads((OUT/f).read_text())
changes=read('workbook-changes.json');snap=read('current-catalogue-snapshot.json');plan=read('website-final-plan.json')
normal=lambda v:v.isoformat() if isinstance(v,(date,datetime)) else (None if v=='' else v)
a=openpyxl.load_workbook(OUT/'previous-catalogue.xlsx',read_only=True,data_only=False)
b=openpyxl.load_workbook(OUT/'catalogue_wall_sculptures.xlsx',read_only=True,data_only=False)
assert b.sheetnames==a.sheetnames+['Website Copy']
before={s.title:{c.coordinate:normal(c.value) for row in s.iter_rows() for c in row if c.value is not None} for s in a}
after={s.title:{c.coordinate:normal(c.value) for row in s.iter_rows() for c in row if c.value is not None} for s in b}
expected={k:dict(v) for k,v in before.items()}
expected['Website Copy']={'A2':'Wall sculptures - customer-facing website copy','A4':changes['website_copy_stamp'],'A5':'Retail names and descriptions; internal material and costing records are on the other sheets.'}
for i,row in enumerate([['Retail / website name','Customer-facing description','Website listing','Website context images','Catalogue ID']]+changes['website_copy_rows'],7):
 for j,value in enumerate(row,1):
  if normal(value) is not None:expected['Website Copy'][f'{openpyxl.utils.get_column_letter(j)}{i}']=normal(value)
for x in changes['patches']:
 assert expected[x['sheet']].get(x['cell'])==normal(x['before']),(x['sheet'],x['cell'],'template conflict')
 if normal(x['value']) is None:expected[x['sheet']].pop(x['cell'],None)
 else:expected[x['sheet']][x['cell']]=normal(x['value'])
for i,row in enumerate(changes['source_append'],changes['source_append_start']):
 for j,v in enumerate(row,1):
  if normal(v) is not None:expected['Specification Sources'][f'{openpyxl.utils.get_column_letter(j)}{i}']=normal(v)
errors=[]
for sheet in expected:
 for cell in expected[sheet].keys()|after[sheet].keys():
  if expected[sheet].get(cell)!=after[sheet].get(cell):errors.append({'sheet':sheet,'cell':cell,'expected':expected[sheet].get(cell),'actual':after[sheet].get(cell)})
# Excel timestamps round to milliseconds and do not store timezone offsets; these columns are UTC.
def same_excel_utc(x):
 if x['sheet']!='Specification Sources' or not x['cell'].startswith('N'):return False
 try:
  e=datetime.fromisoformat(x['expected']).replace(tzinfo=None)
  a=datetime.fromisoformat(x['actual']).replace(tzinfo=None)
  return abs((e-a).total_seconds())<=0.001
 except (ValueError,TypeError):return False
date_roundings=sum(same_excel_utc(x) for x in errors)
errors=[x for x in errors if not same_excel_utc(x)]
(OUT/'workbook-cell-differences.json').write_text(json.dumps(errors,indent=2,ensure_ascii=False))
assert not errors,(len(errors),errors[:4])
NS='http://schemas.openxmlformats.org/spreadsheetml/2006/main';R='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
def native(path,names):
 result={}
 with zipfile.ZipFile(path) as z:
  for i,name in enumerate(names,1):
   tree=E.fromstring(z.read(f'xl/worksheets/sheet{i}.xml'))
   rn=f'xl/worksheets/_rels/sheet{i}.xml.rels'
   rels={r.attrib['Id']:r.attrib['Target'] for r in E.fromstring(z.read(rn))} if rn in z.namelist() else {}
   links={e.attrib['ref']:rels[e.attrib['{'+R+'}id']] for e in tree.findall('{'+NS+'}hyperlinks/{'+NS+'}hyperlink') if '{'+R+'}id' in e.attrib}
   pane=tree.find('{'+NS+'}sheetViews/{'+NS+'}sheetView/{'+NS+'}pane')
   result[name]={'links':links,'pane':pane.attrib if pane is not None else None}
 return result
na=native(OUT/'previous-catalogue.xlsx',a.sheetnames);nb=native(OUT/'catalogue_wall_sculptures.xlsx',b.sheetnames)
for name,v in na.items():
 assert v['pane']==nb[name]['pane'],name
 for cell,target in v['links'].items():assert nb[name]['links'].get(cell)==target,(name,cell)
for x in changes['new_hyperlinks']:assert nb[x['sheet']]['links'][x['cell']]==x['target']
products={p['id']:p for p in snap['products']};wp={p['catalogue_id']:p for p in plan['products']}
for r in range(8,189):
 pid=after['Wall Sculptures'][f'AA{r}'];p=products[pid];f={x['key']:x['value'] for x in p['fields']+p['listing_fields']}
 assert after['Wall Sculptures'][f'AD{r}']==f['Description']==wp[pid]['website_description']
 assert after['Wall Sculptures'][f'AV{r}']==f['Retail name'] and after['Wall Sculptures'][f'G{r}']==f['Fixing']
 assert after['Wall Sculptures'][f'C{r}']==p['name']
# Formula text is covered by the complete cell comparison; inspect cached results independently.
cached=openpyxl.load_workbook(OUT/'catalogue_wall_sculptures.xlsx',read_only=True,data_only=True)
formula_errors=[]
for sheet in cached:
 for row in sheet.iter_rows():
  for c in row:
   if c.data_type=='e':formula_errors.append((sheet.title,c.coordinate,c.value))
assert not formula_errors,formula_errors[:4]
price_rows=list(cached['Wall Sculptures'].iter_rows(min_row=8,max_row=188,values_only=True))
for row in price_rows:
 pid=row[26];price=products[pid]['costing']['selling_price_gbp'] if 'selling_price_gbp' in products[pid]['costing'] else None
 if price is not None:assert abs(float(row[7])-float(price))<.005,(pid,row[7],price)
receipt={'status':'PASS','verified_utc':datetime.now(timezone.utc).isoformat(),'app_snapshot_utc':snap['created_utc'],'event_cutoff':snap['event_cutoff'],'summary':snap['summary'],'sha256':hashlib.sha256((OUT/'catalogue_wall_sculptures.xlsx').read_bytes()).hexdigest(),'original_nonempty_cells_checked':sum(len(x) for x in before.values()),'expected_cell_updates':len(changes['patches']),'retail_names':181,'customer_descriptions':181,'new_source_rows':len(changes['source_append']),'original_hyperlinks_preserved':sum(len(v['links']) for v in na.values()),'new_hyperlinks':len(changes['new_hyperlinks']),'formula_error_count':len(formula_errors),'original_cell_changes_outside_manifest':0,'freeze_panes_preserved':True}
for name in ['workbook-verification.json','preservation-verification.json']:(OUT/name).write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt,indent=2))
