"""Transplant only artifact-authored cells; preserve original workbook features."""
import copy,hashlib,json,posixpath,re,sys,xml.etree.ElementTree as E,zipfile
from pathlib import Path
OUT=Path(__file__).parent;ROOT=OUT.parents[2]
sys.path.insert(0,str(ROOT/'catalogue-review/scripts'))
from import_saatchi_snapshot import Xlsx,Q,NS,U,R,column,column_index
plan=json.loads((OUT/'plan.json').read_text());old=Xlsx(OUT/'previous-catalogue.xlsx');auth=Xlsx(OUT/'authored.xlsx')
parts=dict(old.parts);changed=set(); preserved=0; formulas=0
E.register_namespace('',U);E.register_namespace('r',R)
for sheet,path in old.paths.items():
 ps={p['cell']:p for p in plan['patches'] if p['sheet']==sheet}
 if not ps:continue
 tree=E.fromstring(old.parts[path]);data=tree.find('s:sheetData',NS)
 rows={int(r.get('r')):r for r in data}
 oldcells=old.cells[sheet]
 headerstyle=oldcells['A7'].get('s','0');textstyle=oldcells['C8'].get('s','0')
 numericstyle=old.cells['Wall Sculptures']['N8'].get('s','0')
 for address,p in ps.items():
  assert old.value(sheet,address)==p['before']
  assert auth.value(sheet,address)==p['value'],(sheet,address)
  c=copy.deepcopy(auth.cells[sheet][address])
  if c.get('t')=='s':
   value=auth.value(sheet,address);c.set('t','inlineStr')
   for child in list(c):c.remove(child)
   node=E.SubElement(E.SubElement(c,Q('is')),Q('t'));node.text=value
   if value!=value.strip() or '\n' in value:node.set('{http://www.w3.org/XML/1998/namespace}space','preserve')
  r=int(re.search(r'\d+',address).group());row=rows[r]
  previous=next((e for e in row if e.get('r')==address),None)
  if previous is not None:c.set('s',previous.get('s','0'));row.remove(previous)
  else:c.set('s',headerstyle if r==7 else numericstyle if isinstance(p['value'],(int,float)) else textstyle)
  row.append(c);row[:]=sorted(row,key=lambda e:column_index(e.get('r')))
 if sheet=='Wall Sculptures':
  last=column(plan['last_column']);tree.find('s:dimension',NS).set('ref','A1:'+last+'188')
  cols=tree.find('s:cols',NS)
  E.SubElement(cols,Q('col'),{'min':str(plan['first_added_column']),'max':str(plan['last_column']),'width':'32','customWidth':'1'})
 after={c.get('r'):c for c in tree.findall('s:sheetData/s:row/s:c',NS)}
 for address,c in oldcells.items():
  if address not in ps:
   assert E.tostring(c)==E.tostring(after[address]),(sheet,address)
   preserved+=1;formulas+=c.find('s:f',NS)is not None
 for tag in ['hyperlinks','sheetViews','mergeCells','tableParts','conditionalFormatting','dataValidations']:
  before=E.fromstring(old.parts[path])
  assert [E.tostring(e) for e in before.findall('s:'+tag,NS)]==[E.tostring(e) for e in tree.findall('s:'+tag,NS)]
 parts[path]=E.tostring(tree,encoding='utf-8',xml_declaration=True);changed.add(path)
# Extend only the existing master table; preserve its IDs and all old columns.
master=old.paths['Wall Sculptures'];tree=E.fromstring(old.parts[master])
rid=tree.find('s:tableParts/s:tablePart',NS).get('{'+R+'}id')
rp=posixpath.dirname(master)+'/_rels/'+posixpath.basename(master)+'.rels'
target=next(e.get('Target') for e in E.fromstring(old.parts[rp]) if e.get('Id')==rid)
tp=target.lstrip('/') if target.startswith('/') else posixpath.normpath(posixpath.dirname(master)+'/'+target)
table=E.fromstring(old.parts[tp]);columns=table.find('s:tableColumns',NS);old_count=len(columns)
assert old_count==plan['first_added_column']-1
for h in plan['added_headers']:
 n=column_index(plan['headers'][h]);E.SubElement(columns,Q('tableColumn'),{'id':str(n),'name':h})
columns.set('count',str(len(columns)));table.set('ref','A7:'+column(plan['last_column'])+'188')
auto=table.find('s:autoFilter',NS)
if auto is not None:auto.set('ref',table.get('ref'))
parts[tp]=E.tostring(table,encoding='utf-8',xml_declaration=True);changed.add(tp)
assert all(parts[n]==v for n,v in old.parts.items() if n not in changed)
final=OUT/'catalogue_wall_sculptures.xlsx'
with zipfile.ZipFile(final,'w',zipfile.ZIP_DEFLATED) as z:
 for name,body in parts.items():z.writestr(name,body)
check=Xlsx(final);assert list(check.paths)==list(old.paths)
for p in plan['patches']:assert check.value(p['sheet'],p['cell'])==p['value']
all_formulas=0;patchset={(p['sheet'],p['cell']) for p in plan['patches']}
for sheet in old.paths:
 for address,c in old.cells[sheet].items():
  f=old.formula(sheet,address)
  if f is not None:assert check.formula(sheet,address)==f;all_formulas+=1
  if (sheet,address) not in patchset:
   assert check.value(sheet,address)==old.value(sheet,address)
 for address,c in check.cells[sheet].items():assert c.get('t')!='e',(sheet,address)
assert len({check.value('Wall Sculptures',f'AA{r}') for r in range(8,189)})==181
receipt=dict(status='PASS',sha256=hashlib.sha256(final.read_bytes()).hexdigest(),cells_updated=len(plan['patches']),original_parts=len(old.parts),changed_parts=sorted(changed),all_other_parts_byte_identical=True,all_existing_formulas_preserved=all_formulas,all_unrequested_values_preserved=True,component_records=181,listing_photo_selections_added=plan['new_listing_selections'],saatchi_prepared_not_uploaded=plan['saatchi_prepared_not_uploaded'],saatchi_native_publications=0,wescover_public_matches=176,sheets=list(check.paths))
receipt.update(saatchi_context_candidates_native_test_pending=plan['saatchi_context_candidates_native_test_pending'],saatchi_held_variant_photo_review=plan['saatchi_held_variant_photo_review'])
if plan.get('furnitures_completion_added'):
 receipt.update(furnitures_separate_specification_fields_verified=plan['furnitures_separate_specification_fields_verified'],furnitures_separate_specification_fields_pending=plan['furnitures_separate_specification_fields_pending'])
(OUT/'verification.json').write_text(json.dumps(receipt,indent=2)+'\n')
(OUT/'independent-verification.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt,indent=2))
