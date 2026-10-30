"""Independent ZIP/XML readback of the narrowly edited workbook."""
from pathlib import Path
from xml.etree import ElementTree as E
from copy import deepcopy
from collections import Counter
import hashlib,json,posixpath,re,zipfile

W=Path(__file__).resolve().parent;ROOT=Path('/Users/tprice/Documents/boldstone')
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=read(ROOT/'sculpture-catalogue/components/reconciliation/acanthus-native-availability-2026-10-25/workbook-cutoff-packet.json')
a=read(W/'authoring-receipt.json');overlay=read(p['overlay_path'])
S='http://schemas.openxmlformats.org/spreadsheetml/2006/main';R='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
N='{'+S+'}';RN='{'+R+'}'
def load(path):
 with zipfile.ZipFile(path) as z:
  assert z.testzip() is None
  return {n:z.read(n) for n in z.namelist()}
def target(base,path):return posixpath.normpath(posixpath.join(posixpath.dirname(base),path)).lstrip('/')
def model(parts):
 wb=E.fromstring(parts['xl/workbook.xml']);rels={r.get('Id'):target('xl/workbook.xml',r.get('Target')) for r in E.fromstring(parts['xl/_rels/workbook.xml.rels'])}
 strings=[''.join(t.text or '' for t in s.iter(N+'t')) for s in E.fromstring(parts['xl/sharedStrings.xml'])]
 sheets={}
 for s in wb.find(N+'sheets'):
  file=rels[s.get(RN+'id')];xml=E.fromstring(parts[file]);cells={};fullcells={}
  for c in xml.iter(N+'c'):
   value=c.findtext(N+'v','');typ=c.get('t','n')
   if typ=='s':value=strings[int(value)] if value else ''
   elif typ=='inlineStr':value=''.join(t.text or '' for t in c.iter(N+'t'))
   formula=c.find(N+'f')
   item={'type':'text' if typ in ('s','str','inlineStr') else typ,'value':value,'formula':E.tostring(formula,encoding='unicode') if formula is not None else None}
   fullcells[c.get('r')]=item
   if value or formula is not None:cells[c.get('r')]=item
  relfile=posixpath.join(posixpath.dirname(file),'_rels',posixpath.basename(file)+'.rels')
  localrels={r.get('Id'):r.attrib for r in E.fromstring(parts[relfile])} if relfile in parts else {}
  links={}
  for h in xml.iter(N+'hyperlink'):
   rel=localrels.get(h.get(RN+'id'),{})
   assert h.get('ref') not in links
   links[h.get('ref')]={'target':rel.get('Target',h.get('location','')),'mode':rel.get('TargetMode','Internal'),'display':h.get('display',''),'tooltip':h.get('tooltip','')}
  sheets[s.get('name')]={'part':file,'xml':xml,'cells':cells,'fullcells':fullcells,'links':links}
 return sheets
baseline=load(p['source_workbook']);output=load(p['output_workbook'])
b=model(baseline);v=model(output)
assert list(v)==list(b)+['Native Availability']
assert len(b)==22 and len(v)==23
allowed={(c['sheet'],c['cell']):c for c in a['cell_changes']}
allowed_links={(c['sheet'],c['cell']):c for c in a['hyperlink_changes']}
assert len(allowed)==9 and len(allowed_links)==2
diffs=[];linkdiffs=[];sheet_results=[];formula_count=0;cell_count=0;link_count=0
for name,before in b.items():
 after=v[name];assert before['cells'].keys()==after['cells'].keys(),name
 for address,old in before['cells'].items():
  new=after['cells'][address];cell_count+=1;formula_count+=old['formula'] is not None
  if old!=new:
   c=allowed[(name,address)]
   assert old['type']==new['type']=='text' and old['formula']==new['formula']==None
   assert old['value']==c['before'] and new['value']==c['after']
   diffs.append({'sheet':name,'cell':address,'before':old['value'],'after':new['value']})
 assert before['links'].keys()==after['links'].keys(),name
 for address,old in before['links'].items():
  new=after['links'][address];link_count+=1
  if old!=new:
   c=allowed_links[(name,address)]
   assert old['target']==c['before'] and new['target']==c['after']
   assert old['mode']==new['mode'] and old['tooltip']==new['tooltip'] and new['display']==c['display']
   linkdiffs.append({'sheet':name,'cell':address,'before':old,'after':new})
 # Compare entire native worksheet trees after masking the nine authored cells
 # and two hyperlink labels. This covers every unchanged style, pane and feature.
 oldxml=deepcopy(before['xml']);newxml=deepcopy(after['xml'])
 for tree in [oldxml,newxml]:
  for c in tree.iter(N+'c'):
   if (name,c.get('r')) in allowed:
    for child in list(c):c.remove(child)
    c.attrib.pop('t',None)
  for link in tree.iter(N+'hyperlink'):
   if (name,link.get('ref')) in allowed_links:link.set('display','MASKED')
 assert E.tostring(oldxml)==E.tostring(newxml),'Unrelated sheet structure changed: '+name
 sheet_results.append({'sheet':name,'nonempty_cells':len(before['cells']),'links':len(before['links']),'all_unlisted_values_formulas_styles_geometry_features_unchanged':True})
assert len(diffs)==9 and len(linkdiffs)==2

# Original tables and all unaffected XML parts remain byte-identical.
old_tables=[x for x in baseline if re.fullmatch(r'xl/tables/table\d+\.xml',x)]
for file in old_tables:assert baseline[file]==output[file],file
assert len(old_tables)==22
for name in ['xl/styles.xml','xl/sharedStrings.xml']:
 old=E.fromstring(baseline[name]);new=E.fromstring(output[name])
 if name.endswith('sharedStrings.xml'):
  assert [E.tostring(x) for x in old]==[E.tostring(x) for x in list(new)[:len(old)]]
 else:
  for block in old:
   counterpart=new.find(block.tag);assert counterpart is not None
   assert [E.tostring(x) for x in block]==[E.tostring(x) for x in list(counterpart)[:len(block)]]
tables=[E.fromstring(data) for name,data in output.items() if re.fullmatch(r'xl/tables/table\d+\.xml',name)]
assert len(tables)==24 and len({x.get('id') for x in tables})==24 and len({x.get('name') for x in tables})==24
wall_table=next(x for x in tables if x.get('name')=='WallSculpturesTable');assert wall_table.get('ref')=='A8:AH421'
assert len([k for k in v['Wall Sculptures']['cells'] if re.fullmatch(r'A\d+',k) and int(k[1:])>=9])==413

# Verify new evidence directly against the sealed overlay, independently of
# the author's calculated headline and new worksheet cell positions.
n=v['Native Availability']['cells']
value=lambda address:n.get(address,{}).get('value','')
for addr,expected in {'B6':'6360','B7':'5','B8':'6355','B30':'345'}.items():assert value(addr)==expected,(addr,value(addr))
assert n['B7']['formula'] and n['B8']['formula']
rows={value('F'+str(r)):r for r in range(13,18)}
assert set(rows)==set(p['deleted_file_ids'])
for source in overlay['rows']:
 r=rows[source['file_id']]
 assert value(f'G{r}')==source['revision_at_deletion']
 assert value(f'H{r}')==source['folder_id']
 assert value(f'I{r}')==source['historical_image_url']
 assert value(f'J{r}')==source['historical_path']
 assert value(f'K{r}')==str(source['bytes_at_deletion'])
 assert value(f'O{r}')=='345'
 assert value(f'L{r}')=='UTC: '+source['user_confirmation_utc']
 assert value(f'M{r}')=='UTC: '+source['deletion_readback_utc']
 assert value(f'N{r}')=='UTC: '+source['independent_native_readback']['checked_utc']
 assert value(f'AD{r}')==source['status']
 assert value(f'AC{r}')=='No'
 assert v['Native Availability']['links'][f'E{r}']['target']==source['folder_url']
 for pc,hc in [('S','T'),('U','V')]:
  receipt=value(f'{pc}{r}');assert sha(receipt)==value(f'{hc}{r}')==overlay['source_evidence'][receipt]
survivors={value('F'+str(r)):r for r in range(23,26)}
assert set(survivors)=={x['metadata']['id'] for x in overlay['remaining_verified_files']}
assert value('D'+str(survivors[overlay['surviving_master_example']['file_id']]))=='Existing master primary retained'
assert v['Wall Sculptures']['links']['L12']['target']==b['Wall Sculptures']['links']['L12']['target']==overlay['surviving_master_example']['image_url']
assert v['Products']['links']['AB9']['target']==b['Products']['links']['AB9']['target']==overlay['surviving_master_example']['image_url']
flower_row=rows['id:cnqzTNngPVsAAAAAAAt4Uw'];assert value('AE'+str(flower_row))==b['Wall Sculptures']['links']['L11']['target']

# Check native relationship/package integrity, including all table targets.
for name,data in output.items():
 if not name.endswith('.rels'):continue
 base=posixpath.join(posixpath.dirname(posixpath.dirname(name)),posixpath.basename(name)[:-5]) if name!='_rels/.rels' else ''
 ids=[]
 for rel in E.fromstring(data):
  ids.append(rel.get('Id'))
  if rel.get('TargetMode')!='External':assert target(base,rel.get('Target')) in output,(name,rel.attrib)
 assert len(ids)==len(set(ids)),name
for key,h in [('source_workbook','source_workbook_sha256'),('overlay_path','overlay_sha256'),('register_path','register_sha256')]:assert sha(p[key])==p[h]
for key,h in [('gallery_database','gallery_database_sha256')]:assert sha(overlay[key])==overlay[h]
assert sha(overlay['review_snapshot']['path'])==overlay['review_snapshot']['sha256']
errors=[(name,addr,c) for name,sheet in v.items() for addr,c in sheet['cells'].items() if c['type']=='e']
assert not errors,errors[:10]
receipt={'status':'PASS_ALL_22_BASELINE_SHEETS_PRESERVED_EXCEPT_DECLARED_AVAILABILITY_METADATA','workbook':p['output_workbook'],'sha256':sha(p['output_workbook']),'baseline_sha256':p['source_workbook_sha256'],'sheets':23,'baseline_sheets':22,'primary_rows':413,'nonempty_baseline_cells_compared':cell_count,'existing_formulas_preserved':formula_count,'existing_hyperlinks_compared':link_count,'exact_metadata_deltas':diffs,'exact_hyperlink_deltas':linkdiffs,'new_native_sheet_deleted_files':5,'new_native_sheet_surviving_files':3,'new_native_links':len(v['Native Availability']['links']),'baseline_count':6360,'baseline_adjusted_count':6355,'whole_library_rescan':False,'review_event_cutoff':345,'original_tables_preserved':22,'table_count':24,'formula_errors':0,'all_source_hashes_unchanged':True,'sheet_checks':sheet_results,'no_canonical_app_review_native_or_platform_writes':True}
(W/'validation.json').write_text(json.dumps(receipt,indent=2)+'\n')
(W/'exact-baseline-delta.json').write_text(json.dumps({'baseline_sha256':p['source_workbook_sha256'],'output_sha256':receipt['sha256'],'cells':diffs,'hyperlinks':linkdiffs},indent=2)+'\n')
print(json.dumps({k:v for k,v in receipt.items() if k not in ['exact_metadata_deltas','exact_hyperlink_deltas','sheet_checks']},indent=2))
