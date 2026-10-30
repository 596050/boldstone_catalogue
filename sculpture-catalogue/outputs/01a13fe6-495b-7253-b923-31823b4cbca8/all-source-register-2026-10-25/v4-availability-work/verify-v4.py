"""Independent ZIP/XML readback of the narrowly edited workbook."""
from pathlib import Path
from xml.etree import ElementTree as E
from copy import deepcopy
from collections import Counter
import hashlib,json,posixpath,re,zipfile

W=Path(__file__).resolve().parent;ROOT=Path('/Users/tprice/Documents/boldstone')
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=read(ROOT/'sculpture-catalogue/components/reconciliation/six-native-deletions-and-app-review-2026-10-25/workbook-cutoff-packet.json')
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
baseline=load(p['baseline_workbook']);output=load(p['output_workbook'])
b=model(baseline);v=model(output)
assert list(v)==list(b) and len(v)==23
allowed={(c['sheet'],c['cell']):c for c in a['cell_changes']}
assert len(allowed)==5 and not a['hyperlink_changes']
diffs=[];sheet_results=[];formula_count=0;cell_count=0;link_count=0
for name,before in b.items():
 if name=='Native Availability':continue
 after=v[name];assert before['cells'].keys()==after['cells'].keys(),name
 for address,old in before['cells'].items():
  new=after['cells'][address];cell_count+=1;formula_count+=old['formula'] is not None
  if old!=new:
   c=allowed[(name,address)]
   assert old['type']==new['type']=='text' and old['formula']==new['formula']==None
   assert old['value']==c['before'] and new['value']==c['after']
   diffs.append({'sheet':name,'cell':address,'before':old['value'],'after':new['value']})
 assert before['links']==after['links'],name
 link_count+=len(before['links'])
 oldxml=deepcopy(before['xml']);newxml=deepcopy(after['xml'])
 for tree in [oldxml,newxml]:
  for c in tree.iter(N+'c'):
   if (name,c.get('r')) in allowed:
    for child in list(c):c.remove(child)
    c.attrib.pop('t',None)
 assert E.tostring(oldxml)==E.tostring(newxml),'Unrelated sheet structure changed: '+name
 sheet_results.append({'sheet':name,'nonempty_cells':len(before['cells']),'links':len(before['links']),'all_unlisted_values_formulas_styles_geometry_features_unchanged':True})
assert len(diffs)==5
assert baseline.keys()==output.keys()
old_tables=[x for x in baseline if re.fullmatch(r'xl/tables/table\d+\.xml',x)]
source_tables=[x for x in old_tables if not E.fromstring(baseline[x]).get('name').startswith('NativeAvailability')]
for file in source_tables:assert baseline[file]==output[file],file
assert len(source_tables)==22 and len(old_tables)==24
for name in ['xl/styles.xml','xl/sharedStrings.xml']:
 old=E.fromstring(baseline[name]);new=E.fromstring(output[name])
 if name.endswith('sharedStrings.xml'):
  assert [E.tostring(x) for x in old]==[E.tostring(x) for x in list(new)[:len(old)]]
 else:
  for block in old:
   counterpart=new.find(block.tag);assert counterpart is not None
   assert [E.tostring(x) for x in block]==[E.tostring(x) for x in list(counterpart)[:len(block)]]
for name in ['xl/workbook.xml','xl/_rels/workbook.xml.rels','[Content_Types].xml']:
 assert baseline[name]==output[name],name
tables=[E.fromstring(output[n]) for n in old_tables]
assert len({x.get('id') for x in tables})==24 and len({x.get('name') for x in tables})==24
assert next(x for x in tables if x.get('name')=='WallSculpturesTable').get('ref')=='A8:AH421'
assert next(x for x in tables if x.get('name')=='NativeAvailabilityDeletedFiles').get('ref')=='A12:AE18'
assert next(x for x in tables if x.get('name')=='NativeAvailabilitySurvivingFiles').get('ref')=='A22:I26'
assert len([k for k in v['Wall Sculptures']['cells'] if re.fullmatch(r'A\d+',k) and int(k[1:])>=9])==413
n=v['Native Availability']['cells'];value=lambda address:n.get(address,{}).get('value','')
for addr,expected in {'B6':'6360','B7':'6','B8':'6354','B30':'347'}.items():assert value(addr)==expected,(addr,value(addr))
assert n['B7']['formula'] and 'COUNTA(F13:F18)' in n['B7']['formula']
assert n['B8']['formula'] and 'B6-B7' in n['B8']['formula']
rows={value('F'+str(r)):r for r in range(13,19)}
assert set(rows)=={s['file_id'] for s in overlay['rows']} and len(rows)==6
for source in overlay['rows']:
 r=rows[source['file_id']]
 for col,key in [('A','name'),('G','revision_at_deletion'),('H','folder_id'),('I','historical_image_url'),('J','historical_path'),('K','bytes_at_deletion'),('P','operation_id'),('Q','batch_id'),('R','reason'),('W','content_hash_at_deletion'),('AD','status')]:
  assert value(f'{col}{r}')==str(source[key]),(source['file_id'],col)
 assert value(f'O{r}')=='347'
 for col,key in [('L','user_confirmation_utc'),('M','deletion_readback_utc')]:assert value(f'{col}{r}')=='UTC: '+source[key]
 assert value(f'N{r}')=='UTC: '+source['independent_native_readback']['checked_utc']
 assert value(f'AC{r}')=='No' and value(f'AB{r}')=='Yes'
 assert value(f'Y{r}')==', '.join(str(e['id']) for e in source['audit_events'])
 assert v['Native Availability']['links'][f'E{r}']['target']==source['folder_url']
 for pc,hc in [('S','T'),('U','V')]:
  receipt=value(f'{pc}{r}');assert sha(receipt)==value(f'{hc}{r}')==overlay['source_evidence'][receipt]
survivors={value('F'+str(r)):r for r in range(23,27)}
assert set(survivors)=={x['metadata']['id'] for x in overlay['remaining_verified_files']}
for source in overlay['remaining_verified_files']:
 s=source['metadata'];r=survivors[s['id']]
 assert value(f'A{r}')==s['name'] and value(f'G{r}')==s['rev'] and value(f'H{r}')==str(s['size'])
for file_id in [overlay['surviving_master_example']['file_id'],'id:cnqzTNngPVsAAAAAAAt_oA']:
 assert value('D'+str(survivors[file_id]))=='Existing master primary retained'
assert '__010.jpg' in v['Wall Sculptures']['links']['L9']['target']
assert v['Products']['links']['AB100']['target']==v['Wall Sculptures']['links']['L9']['target']
assert v['Wall Sculptures']['links']['L11']['target']==b['Wall Sculptures']['links']['L11']['target']
assert v['Products']['links']['AB8']['target']==b['Products']['links']['AB8']['target']
assert len(v['Native Availability']['links'])==26
for l in a['native_links']:
 expected=Path(l['target']).as_uri() if l['target'].startswith('/') else l['target']
 assert v['Native Availability']['links'][l['cell']]['target']==expected
for name,data in output.items():
 if not name.endswith('.rels'):continue
 base=posixpath.join(posixpath.dirname(posixpath.dirname(name)),posixpath.basename(name)[:-5]) if name!='_rels/.rels' else ''
 ids=[]
 for rel in E.fromstring(data):
  ids.append(rel.get('Id'))
  if rel.get('TargetMode')!='External':assert target(base,rel.get('Target')) in output,(name,rel.attrib)
 assert len(ids)==len(set(ids)),name
for key,h in [('baseline_workbook','baseline_workbook_sha256'),('overlay_path','overlay_sha256')]:assert sha(p[key])==p[h]
assert sha(overlay['gallery_database'])==overlay['gallery_database_sha256']
assert sha(overlay['review_snapshot']['path'])==overlay['review_snapshot']['sha256']
errors=[(name,addr,c) for name,sheet in v.items() for addr,c in sheet['cells'].items() if c['type']=='e']
assert not errors,errors[:10]
changed_parts=[n for n in baseline if baseline[n]!=output[n]]
declared_parts=set(read(W/'assembly-receipt.json')['modified_parts'])
assert set(changed_parts)<=declared_parts
# Artifact's donor uses inline strings, so rewriting the unchanged shared-string
# pool may produce identical bytes. Every actual package delta is still declared.
assert declared_parts-set(changed_parts)<={'xl/sharedStrings.xml'}
receipt={'status':'PASS_ALL_22_SOURCE_SHEETS_PRESERVED_EXCEPT_FIVE_AVAILABILITY_TEXT_CELLS','workbook':p['output_workbook'],'sha256':sha(p['output_workbook']),'baseline_sha256':p['baseline_workbook_sha256'],'sheets':23,'source_sheets':22,'primary_rows':413,'nonempty_source_cells_compared':cell_count,'existing_source_formulas_preserved':formula_count,'existing_source_hyperlinks_compared':link_count,'exact_metadata_deltas':diffs,'exact_hyperlink_deltas':[],'availability_deleted_files':6,'availability_surviving_references':4,'availability_links':26,'baseline_count':6360,'baseline_adjusted_count':6354,'whole_library_rescan':False,'review_event_cutoff':347,'last_confirmed_native_event':342,'original_tables_preserved':22,'table_count':24,'formula_errors':0,'source_hashes_unchanged':True,'sheet_checks':sheet_results,'app_specification_overlay_imported':False,'no_canonical_app_native_or_platform_writes':True,'package_parts_changed':changed_parts}
(W/'validation.json').write_text(json.dumps(receipt,indent=2)+'\n')
(W/'exact-baseline-delta.json').write_text(json.dumps({'baseline_sha256':p['baseline_workbook_sha256'],'output_sha256':receipt['sha256'],'cells':diffs,'hyperlinks':[],'availability_sheet_rebuilt':True},indent=2)+'\n')
print(json.dumps({k:v for k,v in receipt.items() if k not in ['exact_metadata_deltas','sheet_checks','package_parts_changed']},indent=2))
