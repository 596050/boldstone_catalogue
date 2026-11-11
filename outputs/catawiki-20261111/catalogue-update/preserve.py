"""Transplant only Artifact-authored Catawiki cells, preserving existing XLSX parts."""
from pathlib import Path
import copy,hashlib,json,math,posixpath,re,sys,xml.etree.ElementTree as E,zipfile

ROOT=Path('/Users/tprice/Documents/boldstone');OUT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'catalogue-review/scripts'))
from import_saatchi_snapshot import Xlsx,Q,NS,U,R,column,column_index
plan=json.loads((OUT/'plan.json').read_text());old=Xlsx(OUT/'previous-catalogue.xlsx');auth=Xlsx(OUT/'authored.xlsx')
assert list(old.paths)==list(auth.paths)
same=lambda a,b: math.isclose(a,b,rel_tol=1e-10,abs_tol=1e-6) if isinstance(a,(int,float)) and isinstance(b,(int,float)) and not isinstance(a,bool) and not isinstance(b,bool) else str(a or '')==str(b or '')
E.register_namespace('',U);E.register_namespace('r',R)
parts=dict(old.parts);styles=E.fromstring(parts['xl/styles.xml'])
formats=styles.find('s:numFmts',NS)
if formats is None:formats=E.Element(Q('numFmts'),{'count':'0'});styles.insert(0,formats)
xfs=styles.find('s:cellXfs',NS)
def add_style(code,base='H8'):
 fmt=next((f.get('numFmtId') for f in formats if f.get('formatCode')==code),None)
 if fmt is None:
  fmt=str(max([163]+[int(n.get('numFmtId')) for n in formats])+1)
  E.SubElement(formats,Q('numFmt'),{'numFmtId':fmt,'formatCode':code})
 xf=copy.deepcopy(xfs[int(old.cells['Wall Sculptures'][base].get('s','0'))]);xf.set('numFmtId',fmt);xf.set('applyNumberFormat','1')
 alignment=xf.find('s:alignment',NS)
 if alignment is None:alignment=E.SubElement(xf,Q('alignment'))
 alignment.set('wrapText','1');alignment.set('vertical','center');xf.set('applyAlignment','1')
 xfs.append(xf)
 return str(len(xfs)-1)
sty={k:add_style(v,'C8' if k=='text' else 'H8') for k,v in {'gbp':'"£"#,##0.00','eur':'"€"#,##0.00','percentage':'0.0%','ratio':'0.000000','integer':'0','decimal':'0.00','text':'@','utc':'yyyy-mm-dd hh:mm:ss "UTC"'}.items()}
formats.set('count',str(len(formats)));xfs.set('count',str(len(xfs)))
parts['xl/styles.xml']=E.tostring(styles,encoding='utf-8',xml_declaration=True)
sheet='Wall Sculptures';p=old.paths[sheet];tree=E.fromstring(old.parts[p]);before=copy.deepcopy(tree)
rows={int(row.get('r')):row for row in tree.find('s:sheetData',NS)}
patches={x['cell']:x for x in plan['patches']};assert len(patches)==len(plan['patches'])
for address,patch in patches.items():
 assert old.value(sheet,address) is None and old.formula(sheet,address) is None
 assert same(auth.value(sheet,address),patch['value']),(address,auth.value(sheet,address),patch['value'])
 assert (auth.formula(sheet,address) or '')==(patch.get('formula','').lstrip('='))
 src=auth.cells[sheet].get(address)
 c=copy.deepcopy(src) if src is not None else E.Element(Q('c'),{'r':address})
 if isinstance(patch['value'],str):
  for child in list(c):
   if child.tag!=Q('f'):c.remove(child)
  if patch.get('formula'):
   c.set('t','str');E.SubElement(c,Q('v')).text=patch['value']
  else:
   c.set('t','inlineStr');t=E.SubElement(E.SubElement(c,Q('is')),Q('t'));t.text=patch['value'];t.set('{http://www.w3.org/XML/1998/namespace}space','preserve')
 elif patch['value'] is None:
  c.set('t','inlineStr');E.SubElement(E.SubElement(c,Q('is')),Q('t'))
 c.set('s',old.cells[sheet]['A7'].get('s','0') if patch['style']=='header' else sty[patch['style']])
 row=rows[int(re.search(r'\d+',address)[0])];assert not any(c0.get('r')==address for c0 in row)
 row.append(c);row[:]=sorted(row,key=lambda c0:column_index(c0.get('r')))
dim=tree.find('s:dimension',NS)
if dim is None:dim=E.Element(Q('dimension'));tree.insert(1 if tree.find('s:sheetPr',NS) is not None else 0,dim)
dim.set('ref','A1:'+column(plan['last_added_column'])+'188')
cols=tree.find('s:cols',NS);assert cols is not None
E.SubElement(cols,Q('col'),{'min':str(plan['first_added_column']),'max':str(plan['last_added_column']),'width':'32','customWidth':'1'})
for tag in ['sheetViews','sheetFormatPr','mergeCells','hyperlinks','tableParts','conditionalFormatting','dataValidations']:
 assert [E.tostring(x) for x in before.findall('s:'+tag,NS)]==[E.tostring(x) for x in tree.findall('s:'+tag,NS)]
for r in before.findall('s:sheetData/s:row',NS):assert r.attrib==rows[int(r.get('r'))].attrib
parts[p]=E.tostring(tree,encoding='utf-8',xml_declaration=True)
rel_path=posixpath.dirname(p)+'/_rels/'+posixpath.basename(p)+'.rels'
rels={x.get('Id'):x.get('Target') for x in E.fromstring(old.parts[rel_path])}
rid=tree.find('s:tableParts/s:tablePart',NS).get('{'+R+'}id')
target=rels[rid].lstrip('/');tp=target if target.startswith('xl/') else posixpath.normpath(posixpath.dirname(p)+'/'+target)
table=E.fromstring(old.parts[tp]);tc=table.find('s:tableColumns',NS)
assert len(tc)==plan['first_added_column']-1
for n,h in enumerate(plan['new_headers'],plan['first_added_column']):E.SubElement(tc,Q('tableColumn'),{'id':str(n),'name':h})
tc.set('count',str(len(tc)));table.set('ref','A7:'+column(plan['last_added_column'])+'188')
af=table.find('s:autoFilter',NS)
if af is not None:af.set('ref',table.get('ref'))
parts[tp]=E.tostring(table,encoding='utf-8',xml_declaration=True)
changed={p,tp,'xl/styles.xml'}
assert all(body==parts[n] for n,body in old.parts.items() if n not in changed)
target=OUT/'catalogue_wall_sculptures.xlsx'
with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
 for n,body in parts.items():z.writestr(n,body)
final=Xlsx(target);preserved=0;formulas=0
for sh,cells in old.cells.items():
 for a,c in cells.items():
  assert E.tostring(c)==E.tostring(final.cells[sh][a]),(sh,a)
  assert old.value(sh,a)==final.value(sh,a),(sh,a)
  assert old.formula(sh,a)==final.formula(sh,a),(sh,a)
  formulas+=bool(old.formula(sh,a));preserved+=1
for a,patch in patches.items():
 assert same(final.value(sheet,a),patch['value']),(a,final.value(sheet,a),patch['value'])
 assert (final.formula(sheet,a) or '')==patch.get('formula','').lstrip('=')
assert len({final.value(sheet,'AA'+str(r)) for r in range(8,189)})==181
for sh,cells in final.cells.items():assert not any(c.get('t')=='e' for c in cells.values()),sh
assert list(final.paths)==list(old.paths) and len(final.paths)==12
receipt={'status':'PASS','sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'new_columns':len(plan['new_headers']),
 'new_cells':len(patches),'all_existing_cells_preserved':preserved,'all_existing_formulas_preserved':formulas,
 'all_other_parts_byte_identical':True,'changed_parts':sorted(changed),'sheets':list(final.paths),
 'master_columns':plan['last_added_column'],'counts':plan['counts'],'uplift_gbp':100,'native_changes':False}
(OUT/'verification.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt,indent=2))
