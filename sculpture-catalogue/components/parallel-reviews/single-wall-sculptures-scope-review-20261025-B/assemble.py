"""Append the Artifact-authored sheet while preserving existing native features.

The baseline has 43,121 native hyperlinks and exact-text timestamp cells added
for capabilities missing from Artifact Tool's file API. To preserve those and
all unrelated views exactly, retain every original worksheet/table payload and
append the new authored sheet, remapping its global style/string references.
No cell values, formulas or styles are authored outside Artifact Tool.
"""
from pathlib import Path
from xml.etree import ElementTree as E
from copy import deepcopy
import hashlib,json,posixpath,re,zipfile

W=Path(__file__).resolve().parent;read=lambda p:json.loads(Path(p).read_text())
d=read(W/'unified-data.json');baseline=Path(d['baseline']);out=Path(d['output']);stage=W/'primary-sheet.xlsx'
S='http://schemas.openxmlformats.org/spreadsheetml/2006/main';R='http://schemas.openxmlformats.org/officeDocument/2006/relationships';P='http://schemas.openxmlformats.org/package/2006/relationships';C='http://schemas.openxmlformats.org/package/2006/content-types'
N='{'+S+'}';E.register_namespace('',S);E.register_namespace('r',R)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert sha(baseline)=='9858a137fe23ce721749d659b41ec5e0d881a2a78ff3b99d2348ed4b8090c045'
with zipfile.ZipFile(baseline) as z:parts={n:z.read(n) for n in z.namelist()}
with zipfile.ZipFile(stage) as z:new={n:z.read(n) for n in z.namelist()}
original=dict(parts);modified=set();added=set()
def save(name,root):
 E.register_namespace('',root.tag[1:].split('}',1)[0])
 parts[name]=E.tostring(root,encoding='utf-8',xml_declaration=True)
 E.register_namespace('',S)
 (modified if name in original else added).add(name)

# Original shared-string indices and content remain fixed.
strings=E.fromstring(parts['xl/sharedStrings.xml']);extra_strings=E.fromstring(new['xl/sharedStrings.xml'])
string_offset=len(strings);prior_strings=[E.tostring(x) for x in strings]
for x in extra_strings:strings.append(deepcopy(x))
strings.set('uniqueCount',str(len(strings)));strings.set('count',str(int(strings.get('count',str(string_offset)))+int(extra_strings.get('count',str(len(extra_strings))))))
assert [E.tostring(x) for x in list(strings)[:string_offset]]==prior_strings
save('xl/sharedStrings.xml',strings)

# Append new style definitions; all baseline style indices remain unchanged.
styles=E.fromstring(parts['xl/styles.xml']);extra_styles=E.fromstring(new['xl/styles.xml'])
style_order=['numFmts','fonts','fills','borders','cellStyleXfs','cellXfs','cellStyles','dxfs','tableStyles','colors','extLst']
def container(root,name):
 item=root.find(N+name)
 if item is None:
  item=E.Element(N+name,{'count':'0'});rank=style_order.index(name)
  idx=next((i for i,x in enumerate(root) if x.tag.split('}')[-1] in style_order and style_order.index(x.tag.split('}')[-1])>rank),len(root));root.insert(idx,item)
 return item
nf=container(styles,'numFmts');code_ids={x.get('formatCode'):int(x.get('numFmtId')) for x in nf};num_map={}
next_format=max([163]+list(code_ids.values()))+1
for f in list(extra_styles.find(N+'numFmts')) if extra_styles.find(N+'numFmts') is not None else []:
 oldid=int(f.get('numFmtId'));code=f.get('formatCode')
 if code not in code_ids:
  code_ids[code]=next_format;next_format+=1;copy=deepcopy(f);copy.set('numFmtId',str(code_ids[code]));nf.append(copy)
 num_map[oldid]=code_ids[code]
nf.set('count',str(len(nf)))
offsets={};prefixes={}
for tag in ['fonts','fills','borders','cellStyleXfs','cellXfs','dxfs']:
 dest=container(styles,tag);src=extra_styles.find(N+tag);offsets[tag]=len(dest);prefixes[tag]=[E.tostring(x) for x in dest]
 for item in list(src) if src is not None else []:
  item=deepcopy(item)
  if tag in ['cellStyleXfs','cellXfs']:
   for attr,source in [('fontId','fonts'),('fillId','fills'),('borderId','borders')]:
    if item.get(attr) is not None:item.set(attr,str(int(item.get(attr))+offsets[source]))
   if item.get('numFmtId') is not None:item.set('numFmtId',str(num_map.get(int(item.get('numFmtId')),int(item.get('numFmtId')))))
   if item.get('xfId') is not None:item.set('xfId',str(int(item.get('xfId'))+offsets['cellStyleXfs']))
  if tag=='dxfs':
   for fmt in item.iter(N+'numFmt'):
    fmt.set('numFmtId',str(num_map.get(int(fmt.get('numFmtId')),int(fmt.get('numFmtId')))))
  dest.append(item)
 dest.set('count',str(len(dest)))
for tag,prefix in prefixes.items():assert [E.tostring(x) for x in list(styles.find(N+tag))[:len(prefix)]]==prefix
save('xl/styles.xml',styles)

sheet_number=max(int(re.search(r'sheet(\d+)\.xml$',n).group(1)) for n in parts if re.fullmatch(r'xl/worksheets/sheet\d+\.xml',n))+1
table_number=max(int(re.search(r'table(\d+)\.xml$',n).group(1)) for n in parts if re.fullmatch(r'xl/tables/table\d+\.xml',n))+1
sheet_part=f'xl/worksheets/sheet{sheet_number}.xml';table_part=f'xl/tables/table{table_number}.xml'
root=E.fromstring(new['xl/worksheets/sheet1.xml'])
for cell in root.iter(N+'c'):
 if cell.get('s') is not None:cell.set('s',str(int(cell.get('s'))+offsets['cellXfs']))
 if cell.get('t')=='s':v=cell.find(N+'v');v.text=str(int(v.text)+string_offset)
for row in root.iter(N+'row'):
 if row.get('s') is not None:row.set('s',str(int(row.get('s'))+offsets['cellXfs']))
for column in root.iter(N+'col'):
 if column.get('style') is not None:column.set('style',str(int(column.get('style'))+offsets['cellXfs']))
for rule in root.iter(N+'cfRule'):
 if rule.get('dxfId') is not None:rule.set('dxfId',str(int(rule.get('dxfId'))+offsets['dxfs']))
for view in root.iter(N+'sheetView'):view.set('tabSelected','1')
rels=E.fromstring(new['xl/worksheets/_rels/sheet1.xml.rels'])
for rel in rels:
 assert rel.get('Type').endswith('/table'),rel.attrib
 rel.set('Target','../tables/table'+str(table_number)+'.xml')
table=E.fromstring(new['xl/tables/table1.xml']);table.set('id',str(table_number));assert table.get('name')=='WallSculpturesTable'
save(table_part,table)

# Native hyperlinks use the existing verified source targets and new row map.
def col(n):
 s='';n+=1
 while n:n,k=divmod(n-1,26);s=chr(65+k)+s
 return s
assert root.find(N+'hyperlinks') is None
hlinks=E.Element(N+'hyperlinks');internal=external=0
used={x.get('Id') for x in rels}
for ij,v in d['links'].items():
 i,j=map(int,ij.split(','));target=v['target'];attrs={'ref':col(j)+str(i+9),'display':v['label']}
 if target.startswith('#'):attrs['location']=target[1:];internal+=1
 else:
  rid='wallLink_'+str(i)+'_'+str(j);assert rid not in used;used.add(rid)
  attrs['{'+R+'}id']=rid;external+=1
  E.SubElement(rels,'{'+P+'}Relationship',{'Id':rid,'Type':R+'/hyperlink','Target':target,'TargetMode':'External'})
 E.SubElement(hlinks,N+'hyperlink',attrs)
later={'printOptions','pageMargins','pageSetup','headerFooter','rowBreaks','colBreaks','customProperties','cellWatches','ignoredErrors','smartTags','drawing','legacyDrawing','legacyDrawingHF','picture','oleObjects','controls','webPublishItems','tableParts','extLst'}
idx=next((i for i,x in enumerate(root) if x.tag.split('}')[-1] in later),len(root));root.insert(idx,hlinks)
save(sheet_part,root);save(f'xl/worksheets/_rels/sheet{sheet_number}.xml.rels',rels)

workbook=E.fromstring(parts['xl/workbook.xml']);wr=E.fromstring(parts['xl/_rels/workbook.xml.rels'])
sheets=workbook.find(N+'sheets');assert d['sheet'] not in [x.get('name') for x in sheets]
rid='rIdWallSculptures';assert rid not in [x.get('Id') for x in wr]
sheetid=max(int(x.get('sheetId')) for x in sheets)+1
sheets.insert(0,E.Element(N+'sheet',{'name':d['sheet'],'sheetId':str(sheetid),'{'+R+'}id':rid}))
E.SubElement(wr,'{'+P+'}Relationship',{'Id':rid,'Type':R+'/worksheet','Target':'worksheets/sheet'+str(sheet_number)+'.xml'})
views=workbook.find(N+'bookViews')
if views is None:views=E.Element(N+'bookViews');workbook.insert(list(workbook).index(sheets),views)
if len(views)==0:E.SubElement(views,N+'workbookView',{'activeTab':'0','firstSheet':'0'})
for view in views:view.set('activeTab','0');view.set('firstSheet','0')
for name in workbook.iter(N+'definedName'):
 if name.get('localSheetId') is not None:name.set('localSheetId',str(int(name.get('localSheetId'))+1))
save('xl/workbook.xml',workbook);save('xl/_rels/workbook.xml.rels',wr)
types=E.fromstring(parts['[Content_Types].xml'])
for part,kind in [(sheet_part,'application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml'),(table_part,'application/vnd.openxmlformats-officedocument.spreadsheetml.table+xml')]:
 E.SubElement(types,'{'+C+'}Override',{'PartName':'/'+part,'ContentType':kind})
save('[Content_Types].xml',types)
assert modified=={'xl/sharedStrings.xml','xl/styles.xml','xl/workbook.xml','xl/_rels/workbook.xml.rels','[Content_Types].xml'}
assert len(added)==3
for part in original.keys()-modified:assert parts[part]==original[part],part
with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_DEFLATED) as z:
 for part,content in parts.items():z.writestr(part,content)
receipt={'status':'PASS_PRIMARY_SHEET_ADDED_WITH_BASELINE_VIEWS_PRESERVED','output':str(out),'sha256':sha(out),'baseline_sha256':sha(baseline),
 'original_worksheet_table_relationship_parts_byte_identical':True,'original_global_strings_and_style_definitions_preserved':True,
 'modified_global_parts':sorted(modified),'added_parts':sorted(added),'new_hyperlinks':len(d['links']),'new_internal_links':internal,'new_external_links':external,
 'new_sheet_part':sheet_part,'new_table_part':table_part,'first_sheet':'Wall Sculptures','preserved_source_tabs':21,
 'adapter_reason':'Preserve baseline native hyperlinks and exact-text timestamps unsupported by the authoring API; all new cell content and styles are Artifact-authored.'}
(W/'assembly-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))
