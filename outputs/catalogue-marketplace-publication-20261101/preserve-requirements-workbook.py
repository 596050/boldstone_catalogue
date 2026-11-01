"""Keep original workbook features and transplant artifact-authored content only."""
import copy,hashlib,json,posixpath,sys,zipfile,xml.etree.ElementTree as E
from pathlib import Path
OUT=Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).resolve().parent/'requirements-workbook'
changes=json.loads((OUT/'patches.json').read_text())
U='http://schemas.openxmlformats.org/spreadsheetml/2006/main';R='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
PKG='http://schemas.openxmlformats.org/package/2006/relationships';CT='http://schemas.openxmlformats.org/package/2006/content-types'
NS={'s':U};q=lambda x:'{'+U+'}'+x
E.register_namespace('',U);E.register_namespace('r',R)
def shared(z):
 return [''.join(t.text or '' for t in s.iter(q('t'))) for s in E.fromstring(z.read('xl/sharedStrings.xml'))] if 'xl/sharedStrings.xml' in z.namelist() else []
def value(c,ss):
 if c is None:return None
 if c.get('t')=='inlineStr':return ''.join(t.text or '' for t in c.iter(q('t')))
 f=c.find('s:f',NS)
 if f is not None:return '='+f.text
 v=c.find('s:v',NS);v=v.text if v is not None else None
 return ss[int(v)] if c.get('t')=='s' else v
def literalize(c,ss):
 if c.get('t')=='s':
  text=value(c,ss)
  for child in list(c):c.remove(child)
  c.set('t','inlineStr');t=E.SubElement(E.SubElement(c,q('is')),q('t'));t.text=text;t.set('{http://www.w3.org/XML/1998/namespace}space','preserve')
def sheet_paths(z):
 rels={r.get('Id'):posixpath.normpath('xl/'+r.get('Target').lstrip('/').removeprefix('xl/')) for r in E.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
 return {s.get('name'):rels[s.get('{'+R+'}id')] for s in E.fromstring(z.read('xl/workbook.xml')).find('s:sheets',NS)}
with zipfile.ZipFile(OUT/'previous-catalogue.xlsx') as original,zipfile.ZipFile(OUT/'authored.xlsx') as authored:
 old={n:original.read(n) for n in original.namelist()};parts=dict(old);ss=shared(authored);oldss=shared(original)
 op=sheet_paths(original);ap=sheet_paths(authored);checked=0;links=0
 for sheet,name in op.items():
  patches={p['cell']:p for p in changes['patches'] if p['sheet']==sheet}
  a=E.fromstring(old[name]);b=copy.deepcopy(a)
  if patches:
   source=E.fromstring(authored.read(ap[sheet]));src={c.get('r'):c for c in source.findall('s:sheetData/s:row/s:c',NS)}
   for row in b.findall('s:sheetData/s:row',NS):
    if sheet=='Wall Sculptures' and any(c.get('r') in patches for c in row):
     row.set('ht',str(max(float(row.get('ht','15')),90)))
     row.set('customHeight','1')
    for idx,c in enumerate(list(row)):
     addr=c.get('r')
     if addr not in patches:continue
     new=copy.deepcopy(src[addr]);assert value(new,ss)==str(patches[addr]['value'])
     if c.get('s') is not None:new.set('s',c.get('s'))
     else:new.attrib.pop('s',None)
     literalize(new,ss);row.remove(c);row.insert(idx,new);checked+=1
   parts[name]=E.tostring(b,encoding='utf-8',xml_declaration=True)
  ac={c.get('r'):c for c in a.findall('s:sheetData/s:row/s:c',NS)};bc={c.get('r'):c for c in b.findall('s:sheetData/s:row/s:c',NS)}
  assert ac.keys()==bc.keys()
  for addr,c in ac.items():
   if addr in patches:assert value(bc[addr],oldss)==str(patches[addr]['value'])
   else:assert E.tostring(c)==E.tostring(bc[addr]),(sheet,addr)
  for tag in ['hyperlinks','sheetViews','autoFilter','mergeCells','tableParts','cols','conditionalFormatting','dataValidations']:
   assert [E.tostring(e) for e in a.findall('s:'+tag,NS)]==[E.tostring(e) for e in b.findall('s:'+tag,NS)],(sheet,tag)
  links+=len(a.findall('s:hyperlinks/s:hyperlink',NS))
 assert checked==len(changes['patches'])
 wb=E.fromstring(parts['xl/workbook.xml']);sheets=wb.find('s:sheets',NS)
 rels=E.fromstring(parts['xl/_rels/workbook.xml.rels']);ct=E.fromstring(parts['[Content_Types].xml'])
 original_styles=E.fromstring(old[op['Wall Sculptures']]);lookup={c.get('r'):c for c in original_styles.findall('s:sheetData/s:row/s:c',NS)}
 headerstyle=lookup['A7'].get('s');textstyle=lookup['C8'].get('s');numberstyle=lookup['A8'].get('s')
 for n,data in enumerate(changes['new_sheets'],len(op)+1):
  assert data['name'] not in op
  sheet=E.fromstring(authored.read(ap[data['name']]))
  assert sheet.find('s:drawing',NS) is None and sheet.find('s:tableParts',NS) is None
  for c in sheet.findall('s:sheetData/s:row/s:c',NS):
   literalize(c,ss);row=int(''.join(x for x in c.get('r') if x.isdigit()))
   column=''.join(x for x in c.get('r') if x.isalpha())
   header=data['headers'][sum((ord(ch)-64)*26**i for i,ch in enumerate(reversed(column)))-1] if row>=4 else ''
   numericstyle='19' if 'GBP' in header else '21' if data['name']=='US Delivery Estimates' else numberstyle
   c.set('s',headerstyle if row in (1,4) else numericstyle if c.get('t','n')=='n' else textstyle)
   assert c.get('t')!='e','Formula error in new sheet'
  path=f'xl/worksheets/sheet{n}.xml';assert path not in parts
  parts[path]=E.tostring(sheet,encoding='utf-8',xml_declaration=True)
  rid=f'rIdChannelRequirements{n}';assert not any(r.get('Id')==rid for r in rels)
  E.SubElement(sheets,q('sheet'),{'name':data['name'],'sheetId':str(n),'{'+R+'}id':rid})
  E.SubElement(rels,'{'+PKG+'}Relationship',{'Id':rid,'Type':R+'/worksheet','Target':f'worksheets/sheet{n}.xml'})
  E.SubElement(ct,'{'+CT+'}Override',{'PartName':'/'+path,'ContentType':'application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml'})
 for name,root,namespace in ([('xl/workbook.xml',wb,U),('xl/_rels/workbook.xml.rels',rels,PKG),('[Content_Types].xml',ct,CT)] if changes['new_sheets'] else []):
  E.register_namespace('',namespace)
  parts[name]=E.tostring(root,encoding='utf-8',xml_declaration=True)
 # Preserve every existing native part except the exact reviewed worksheets
 # and package indexes necessary for the two new sheets.
 allowed={op[p['sheet']] for p in changes['patches']}|{'xl/workbook.xml','xl/_rels/workbook.xml.rels','[Content_Types].xml'}
 assert all(parts[n]==b for n,b in old.items() if n not in allowed)
 target=OUT/'catalogue_wall_sculptures.xlsx'
 with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
  for n,b in parts.items():z.writestr(n,b)
 with zipfile.ZipFile(target) as z:
  assert z.testzip() is None
  assert len(sheet_paths(z))==10
 receipt={'status':'PASS','products':181,'cells_updated':checked,'new_sheets':len(changes['new_sheets']),'hyperlinks_preserved':links,
          'original_styles_and_unrelated_cells_preserved':True,'sha256':hashlib.sha256(target.read_bytes()).hexdigest()}
 (OUT/'verification.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))
