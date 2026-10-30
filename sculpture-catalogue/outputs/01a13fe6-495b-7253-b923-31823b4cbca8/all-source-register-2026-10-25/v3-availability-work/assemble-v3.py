"""Preserve native workbook features while inserting Artifact-authored edits.

Artifact Tool authors every new cell and style. This adapter retains baseline
worksheet/table payloads, transfers only the nine declared metadata cells and
new availability sheet, and supplies native hyperlinks absent from the API.
"""
from pathlib import Path
from copy import deepcopy
from xml.etree import ElementTree as E
import hashlib,json,posixpath,re,zipfile

W=Path(__file__).resolve().parent
ROOT=Path('/Users/tprice/Documents/boldstone')
PACKET=ROOT/'sculpture-catalogue/components/reconciliation/acanthus-native-availability-2026-10-25/workbook-cutoff-packet.json'
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=read(PACKET);a=read(W/'authoring-receipt.json')
S='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
R='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
P='http://schemas.openxmlformats.org/package/2006/relationships'
C='http://schemas.openxmlformats.org/package/2006/content-types'
N='{'+S+'}';RN='{'+R+'}'
E.register_namespace('',S);E.register_namespace('r',R)
assert sha(PACKET)==a['packet_sha256']
for key,h in [('source_workbook','source_workbook_sha256'),('overlay_path','overlay_sha256'),('register_path','register_sha256')]:assert sha(p[key])==p[h],key
out=Path(p['output_workbook'])
assert not out.exists(),'Refuse to overwrite sealed output; remove only an unsealed failed build explicitly.'
def load_zip(path):
 with zipfile.ZipFile(path) as z:return {n:z.read(n) for n in z.namelist()}
parts=load_zip(p['source_workbook']);original=dict(parts);stage=load_zip(W/'authored-stage.xlsx')
modified=set();added=set()
def save(name,root):
 E.register_namespace('',root.tag[1:].split('}',1)[0])
 parts[name]=E.tostring(root,encoding='utf-8',xml_declaration=True)
 E.register_namespace('',S)
 (modified if name in original else added).add(name)
def sheet_map(payload):
 rel={x.get('Id'):posixpath.normpath(posixpath.join('xl',x.get('Target'))).lstrip('/') for x in E.fromstring(payload['xl/_rels/workbook.xml.rels'])}
 return {x.get('name'):rel[x.get(RN+'id')] for x in E.fromstring(payload['xl/workbook.xml']).find(N+'sheets')}
base_sheets=sheet_map(parts);stage_sheets=sheet_map(stage)
assert len(base_sheets)==22 and list(stage_sheets)==list(base_sheets)+['Native Availability']

# Append only shared strings referenced by the transferred cells/sheet.
strings=E.fromstring(parts['xl/sharedStrings.xml'])
stage_strings=E.fromstring(stage['xl/sharedStrings.xml'])
string_prefix=[E.tostring(x) for x in strings]
string_map={};existing_strings={E.tostring(x):i for i,x in enumerate(strings)}
def remap_string(cell):
 if cell.get('t')!='s':return
 value=cell.find(N+'v');idx=int(value.text)
 if idx not in string_map:
  child=stage_strings[idx];key=E.tostring(child)
  if key not in existing_strings:
   existing_strings[key]=len(strings);strings.append(deepcopy(child))
  string_map[idx]=existing_strings[key]
 value.text=str(string_map[idx])
def cell_text(cell,payload):
 if cell.get('t')=='s':
  item=E.fromstring(payload['xl/sharedStrings.xml'])[int(cell.find(N+'v').text)]
  return ''.join(x.text or '' for x in item.iter(N+'t'))
 if cell.get('t')=='inlineStr':return ''.join(x.text or '' for x in cell.iter(N+'t'))
 return cell.findtext(N+'v','')

# Keep baseline style indices untouched; append donor definitions for the new sheet.
styles=E.fromstring(parts['xl/styles.xml']);extra=E.fromstring(stage['xl/styles.xml'])
style_order=['numFmts','fonts','fills','borders','cellStyleXfs','cellXfs','cellStyles','dxfs','tableStyles','colors','extLst']
def container(root,name):
 item=root.find(N+name)
 if item is None:
  item=E.Element(N+name,{'count':'0'});rank=style_order.index(name)
  ix=next((i for i,x in enumerate(root) if x.tag.rsplit('}',1)[-1] in style_order and style_order.index(x.tag.rsplit('}',1)[-1])>rank),len(root))
  root.insert(ix,item)
 return item
formats=container(styles,'numFmts');code_ids={x.get('formatCode'):int(x.get('numFmtId')) for x in formats};num_map={}
next_id=max([163]+list(code_ids.values()))+1
for item in list(extra.find(N+'numFmts')) if extra.find(N+'numFmts') is not None else []:
 old=int(item.get('numFmtId'));code=item.get('formatCode')
 if code not in code_ids:
  code_ids[code]=next_id;next_id+=1;copy=deepcopy(item);copy.set('numFmtId',str(code_ids[code]));formats.append(copy)
 num_map[old]=code_ids[code]
formats.set('count',str(len(formats)))
offsets={};prefixes={}
for tag in ['fonts','fills','borders','cellStyleXfs','cellXfs','dxfs']:
 dest=container(styles,tag);source=extra.find(N+tag);offsets[tag]=len(dest);prefixes[tag]=[E.tostring(x) for x in dest]
 for item in list(source) if source is not None else []:
  item=deepcopy(item)
  if tag in ['cellStyleXfs','cellXfs']:
   for attr,table in [('fontId','fonts'),('fillId','fills'),('borderId','borders')]:
    if item.get(attr) is not None:item.set(attr,str(int(item.get(attr))+offsets[table]))
   if item.get('numFmtId') is not None:item.set('numFmtId',str(num_map.get(int(item.get('numFmtId')),int(item.get('numFmtId')))))
   if item.get('xfId') is not None:item.set('xfId',str(int(item.get('xfId'))+offsets['cellStyleXfs']))
  elif tag=='dxfs':
   for fmt in item.iter(N+'numFmt'):fmt.set('numFmtId',str(num_map.get(int(fmt.get('numFmtId')),int(fmt.get('numFmtId')))))
  dest.append(item)
 dest.set('count',str(len(dest)))
for tag,prefix in prefixes.items():assert [E.tostring(x) for x in list(styles.find(N+tag))[:len(prefix)]]==prefix
save('xl/styles.xml',styles)

# Transfer only specified text edits, keeping original cell style and geometry.
for name in dict.fromkeys(x['sheet'] for x in a['cell_changes']):
 file=base_sheets[name];sheet=E.fromstring(parts[file]);donor=E.fromstring(stage[stage_sheets[name]])
 cells={x.get('r'):x for x in sheet.iter(N+'c')};donors={x.get('r'):x for x in donor.iter(N+'c')}
 for change in [x for x in a['cell_changes'] if x['sheet']==name]:
  old=cells[change['cell']];new=deepcopy(donors[change['cell']])
  assert cell_text(old,original)==change['before']
  assert cell_text(new,stage)==change['after']
  assert old.find(N+'f') is None and new.find(N+'f') is None
  remap_string(new)
  if old.get('s') is not None:new.set('s',old.get('s'))
  elif new.get('s') is not None:new.attrib.pop('s')
  parent=next(r for r in sheet.iter(N+'row') if old in list(r));index=list(parent).index(old);parent.remove(old);parent.insert(index,new)
 save(file,sheet)

# Change precisely two current actions; all old source-history links remain untouched.
for change in a['hyperlink_changes']:
 file=base_sheets[change['sheet']];sheet=E.fromstring(parts[file]);relfile=posixpath.join(posixpath.dirname(file),'_rels',posixpath.basename(file)+'.rels')
 relationships=E.fromstring(parts[relfile]);links=[x for x in sheet.iter(N+'hyperlink') if x.get('ref')==change['cell']];assert len(links)==1
 link=links[0];matches=[x for x in relationships if x.get('Id')==link.get(RN+'id')];assert len(matches)==1
 assert matches[0].get('Target')==change['before'];matches[0].set('Target',change['after']);link.set('display',change['display'])
 save(file,sheet);save(relfile,relationships)

sheet_number=max(int(re.fullmatch(r'xl/worksheets/sheet(\d+)\.xml',n).group(1)) for n in parts if re.fullmatch(r'xl/worksheets/sheet\d+\.xml',n))+1
next_table=max(int(re.fullmatch(r'xl/tables/table(\d+)\.xml',n).group(1)) for n in parts if re.fullmatch(r'xl/tables/table\d+\.xml',n))+1
new_sheet_part=f'xl/worksheets/sheet{sheet_number}.xml'
new_rel_part=f'xl/worksheets/_rels/sheet{sheet_number}.xml.rels'
donor_sheet_part=stage_sheets['Native Availability'];sheet=E.fromstring(stage[donor_sheet_part])
for cell in sheet.iter(N+'c'):
 remap_string(cell)
 if cell.get('s') is not None:cell.set('s',str(int(cell.get('s'))+offsets['cellXfs']))
for row in sheet.iter(N+'row'):
 if row.get('s') is not None:row.set('s',str(int(row.get('s'))+offsets['cellXfs']))
for column in sheet.iter(N+'col'):
 if column.get('style') is not None:column.set('style',str(int(column.get('style'))+offsets['cellXfs']))
for rule in sheet.iter(N+'cfRule'):
 if rule.get('dxfId') is not None:rule.set('dxfId',str(int(rule.get('dxfId'))+offsets['dxfs']))
for view in sheet.iter(N+'sheetView'):view.set('tabSelected','0')
donor_rel_part=posixpath.join(posixpath.dirname(donor_sheet_part),'_rels',posixpath.basename(donor_sheet_part)+'.rels')
relationships=E.fromstring(stage[donor_rel_part]);new_tables=[]
for rel in relationships:
 assert rel.get('Type').endswith('/table'),rel.attrib
 donor_table_part=posixpath.normpath(posixpath.join(posixpath.dirname(donor_sheet_part),rel.get('Target'))).lstrip('/')
 table=E.fromstring(stage[donor_table_part]);table.set('id',str(next_table))
 new_part=f'xl/tables/table{next_table}.xml';save(new_part,table);new_tables.append(new_part)
 rel.set('Target',f'../tables/table{next_table}.xml');next_table+=1
assert sheet.find(N+'hyperlinks') is None
hlinks=E.Element(N+'hyperlinks')
for i,link in enumerate(a['native_links']):
 rid='nativeAvailabilityLink'+str(i+1)
 target=Path(link['target']).as_uri() if link['target'].startswith('/') else link['target']
 E.SubElement(hlinks,N+'hyperlink',{'ref':link['cell'],'display':link['display'],RN+'id':rid})
 E.SubElement(relationships,'{'+P+'}Relationship',{'Id':rid,'Type':R+'/hyperlink','Target':target,'TargetMode':'External'})
later={'printOptions','pageMargins','pageSetup','headerFooter','rowBreaks','colBreaks','customProperties','cellWatches','ignoredErrors','smartTags','drawing','legacyDrawing','legacyDrawingHF','picture','oleObjects','controls','webPublishItems','tableParts','extLst'}
index=next((i for i,x in enumerate(sheet) if x.tag.rsplit('}',1)[-1] in later),len(sheet));sheet.insert(index,hlinks)
save(new_sheet_part,sheet);save(new_rel_part,relationships)

# Append the twenty-third sheet without changing original order, IDs or settings.
workbook=E.fromstring(parts['xl/workbook.xml']);wr=E.fromstring(parts['xl/_rels/workbook.xml.rels'])
sheets=workbook.find(N+'sheets');rid='rIdNativeAvailabilityV3';assert rid not in [x.get('Id') for x in wr]
sheet_id=max(int(x.get('sheetId')) for x in sheets)+1
E.SubElement(sheets,N+'sheet',{'name':'Native Availability','sheetId':str(sheet_id),RN+'id':rid})
E.SubElement(wr,'{'+P+'}Relationship',{'Id':rid,'Type':R+'/worksheet','Target':f'worksheets/sheet{sheet_number}.xml'})
save('xl/workbook.xml',workbook);save('xl/_rels/workbook.xml.rels',wr)
types=E.fromstring(parts['[Content_Types].xml'])
for file,kind in [(new_sheet_part,'worksheet')]+[(t,'table') for t in new_tables]:
 E.SubElement(types,'{'+C+'}Override',{'PartName':'/'+file,'ContentType':f'application/vnd.openxmlformats-officedocument.spreadsheetml.{kind}+xml'})
save('[Content_Types].xml',types)
assert [E.tostring(x) for x in list(strings)[:len(string_prefix)]]==string_prefix
strings.set('uniqueCount',str(len(strings)))
ref_count=0
for name in parts:
 if re.fullmatch(r'xl/worksheets/sheet\d+\.xml',name):ref_count+=sum(x.get('t')=='s' for x in E.fromstring(parts[name]).iter(N+'c'))
strings.set('count',str(ref_count));save('xl/sharedStrings.xml',strings)

for file in original.keys()-modified:assert parts[file]==original[file],file
expected_modified={'xl/styles.xml','xl/sharedStrings.xml','xl/workbook.xml','xl/_rels/workbook.xml.rels','[Content_Types].xml'}
expected_modified.update(base_sheets[x['sheet']] for x in a['cell_changes'])
expected_modified.update(posixpath.join(posixpath.dirname(base_sheets[x['sheet']]),'_rels',posixpath.basename(base_sheets[x['sheet']])+'.rels') for x in a['hyperlink_changes'])
assert modified==expected_modified,(modified,expected_modified)
assert len(added)==4
with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_DEFLATED) as z:
 for name,content in parts.items():z.writestr(name,content)
receipt={'status':'PASS_NATIVE_FEATURES_PRESERVED','output':str(out),'sha256':sha(out),'source_sha256':p['source_workbook_sha256'],'original_sheets':22,'sheets':23,'new_sheet_part':new_sheet_part,'new_table_parts':new_tables,'modified_parts':sorted(modified),'added_parts':sorted(added),'untouched_parts_byte_identical':len(original.keys()-modified),'old_cell_styles_unchanged':True,'old_style_and_string_definitions_preserved':True,'metadata_cell_changes':len(a['cell_changes']),'hyperlink_changes':len(a['hyperlink_changes']),'new_hyperlinks':len(a['native_links']),'adapter_reason':'Artifact Tool authors cells/styles; native OOXML adapter preserves baseline hyperlinks, source timestamp strings and unrelated native features.'}
(W/'assembly-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))
