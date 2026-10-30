"""Independent scoped-coverage, value, grouping and saved-package checks."""
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
from xml.etree import ElementTree as E
import csv,hashlib,json,posixpath,sqlite3,zipfile
W=Path(__file__).resolve().parent;OLD=W.with_name('all-source-workbook-20261025-B');B=W.parents[2]
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
d=read(W/'unified-data.json');base=read(OLD/'workbook-data.json');tabs={t['name']:t for t in base['tabs']};manifest=read(W/'input-manifest.json');checks=Counter()
def check(ok,kind,detail=''):
 if not ok:raise AssertionError((kind,detail))
 checks[kind]+=1
for x in manifest['inputs']:check(sha(x['path'])==x['sha256'],'frozen_input',x['path'])
pointer=read(B/'current-master.json');g=(B/pointer['current_published_gallery_projection']['path']).parent
reg=read(B/pointer['register']);active=set(reg['active_option_ids'])
ssscope={'6a43e6a4b629f94bfa50bfd2'};shscope=set();source_hv={};expected_images=set();edge_files=set()
with sqlite3.connect('file:'+str(g/'complete-image-platform-register.sqlite')+'?mode=ro',uri=True) as c:
 for blob, in c.execute('SELECT record_json FROM local_squarespace_records'):ssscope.add(json.loads(blob)['squarespace_native_tuple']['native_product_id'])
 for blob, in c.execute('SELECT record_json FROM local_shopify_products'):
  obj=json.loads(blob)
  if obj['product']['in_preserved_wall_subset']:shscope.add(obj['handle'])
 for blob, in c.execute('SELECT record_json FROM local_shopify_variants'):
  obj=json.loads(blob)
  if obj['handle'] in shscope:source_hv[obj['variant_key']]=obj
 for fid,blob in c.execute('SELECT file_id,record_json FROM images'):
  if json.loads(blob)['inventory_status']=='CURRENT_NATIVE_FILE_AND_ACTUAL_PARENT_VERIFIED':expected_images.add(fid)
 edge_files={x[0] for x in c.execute('SELECT DISTINCT file_id FROM associations')}
old_inputs=read(OLD/'input-manifest.json')['inputs'];byname={Path(x['path']).name:x for x in old_inputs}
native_source=byname['complete-current-native-object-map.json'];check(sha(native_source['path'])==native_source['sha256'],'native_source_hash')
native=read(native_source['path']);nf={k for k,v in native.items() if v['object_type']=='file'};nd={k for k,v in native.items() if v['object_type']=='folder'}
check(nf==expected_images and len(nf)==6360,'current_file_universe')
check(len(nd)==442,'current_folder_universe');unassigned=nf-edge_files;check(len(unassigned)==625,'unassigned_image_universe')
sspath=next(x for x in old_inputs if Path(x['path']).name.startswith('products_Oct-24'))
check(sha(sspath['path'])==sspath['sha256'],'squarespace_export_hash')
with open(sspath['path'],encoding='utf-8-sig',newline='') as f:ssraw=list(csv.DictReader(f))
source_sv={};parent=None
for row in ssraw:
 parent=row['Product ID [Non Editable]'] or parent
 if parent in ssscope:source_sv[row['Variant ID [Non Editable]']]={'parent':parent,'raw':row}
check(len(source_sv)==224 and len(source_hv)==38,'all_wall_and_scope_review_variants')
expected={'catalogue_ids':active,'ss_product_ids':ssscope,'ss_variant_ids':set(source_sv),'sh_handles':shscope,'sh_variant_keys':set(source_hv),'current_file_ids':nf,'unassigned_file_ids':unassigned,'folder_ids':nd}
for key,ids in expected.items():
 got={x for r in d['records'] for x in r[key]};check(got==ids,'complete_scoped_id_coverage',key)
for key in ['catalogue_ids','ss_variant_ids','sh_variant_keys']:
 tally=Counter(x for r in d['records'] for x in r[key]);check(all(v==1 for v in tally.values()),'one_row_per_option_or_source_variant',key)
check(len(d['rows'])==413 and len({r[15] for r in d['rows']})==413,'unique_unified_rows')
prior=read(W.with_name('single-wall-sculptures-sheet-20261025-B')/'unified-data.json')
check(d['rows'][:412]==prior['rows'] and d['records'][:412]==prior['records'],'all_prior_rows_preserved_exactly')
check(all(d['links'][k]==v for k,v in prior['links'].items()),'all_prior_primary_links_preserved')
extra=d['records'][412]
check(extra['kind']=='Wall scope review' and extra['ss_product_ids']==['6a43e6a4b629f94bfa50bfd2'] and not extra['catalogue_ids'] and not extra['sh_handles'] and not extra['current_file_ids'],'sole_review_source_no_identity_inferred')
check(d['rows'][412][2]=='Wall scope unconfirmed; no catalogue identity/mounting assumed','explicit_scope_qualification')
original_products={r[0]:r for r in tabs['Products']['rows']};sources_sv={r[0]:r for r in tabs['Squarespace variants']['rows']}
photo_groups=[r for r in d['records'] if r['kind'] in ['Unassigned photograph group','Context photograph group']]
check(len(photo_groups)==49 and {f for r in photo_groups for f in r['current_file_ids']}==unassigned,'all_unassigned_groups_retained')
check(sum(len(r['current_file_ids']) for r in photo_groups)==625,'unassigned_files_once_in_folder_groups')
for record,row in zip(d['records'],d['rows']):
 check(record['key']==row[15],'stable_primary_key')
 for field,pos in [('ss_product_ids',17),('ss_variant_ids',18),('sh_handles',20),('sh_variant_keys',21),('folder_ids',26),('current_file_ids',27),('supplementary_file_ids',31)]:check(set(str(row[pos]).splitlines())==set(record[field]),'visible_ids_equal_coverage_record',(record['key'],field))
 check(row[24]==len(record['current_file_ids']) and row[25]==len(set(record['current_file_ids'])&unassigned),'visible_photo_counts',record['key'])
 if record['kind']=='Individual option':
  p=original_products[row[16]]
  for a,b in [(0,1),(2,2),(3,3),(4,22),(5,6),(6,7),(7,8),(8,9),(9,12),(10,13)]:check(row[a]==p[b],'all_existing_working_details_preserved',row[16])
  check(record['ss_product_ids']==([p[17]] if p[17] else []) and record['ss_variant_ids']==([p[18]] if p[18] else []) and record['sh_handles']==([p[19]] if p[19] else []),'selected_source_bindings_unchanged',row[16])
 else:check(not record['catalogue_ids'] and row[16]=='','no_new_sculpture_identity',record['key'])
 if record['kind'] in ['Unassigned photograph group','Context photograph group']:
  folder=record['key'].split('DBF:',1)[1]
  check(all(native[f]['parent_id']==folder for f in record['current_file_ids']),'native_parent_grouping',folder)
 if record['kind']!='Individual option' and record['ss_variant_ids']:
  vid=record['ss_variant_ids'][0];s=source_sv[vid];raw=s['raw'];v=sources_sv[vid]
  check(record['ss_product_ids']==[s['parent']] and row[19]==raw['SKU'],'original_ss_variant_binding')
  check(row[4]==(v[4] or 'Default source variant'),'source_variant_options_intact')
  check('On sale: '+raw['On Sale'] in row[9],'sale_state_not_lost')
  expected_raw='SS raw weight / L / W / H: '+' / '.join('(blank)' if x is None else str(x) for x in [v[9],v[10],v[11],v[12]])+'; raw units not encoded.'
  check(row[29].startswith(expected_raw),'repeated_numeric_dimensions_preserved',vid)
  if row[5].startswith('Raw export L / W / H:'):
   check(row[5]=='Raw export L / W / H: '+' / '.join('(blank)' if x is None else str(x) for x in [v[10],v[11],v[12]])+'; units not encoded.','raw_dimensions_visible',vid)
  for hk in record['sh_variant_keys']:
   check(raw['SKU'] and raw['SKU']==source_hv[hk]['sku_raw'],'exact_raw_SKU_group_only',hk)
scope=read(W/'scope-membership.json')
check(len(scope)==344,'full_export_scope_accounting')
check({r['id'] for r in scope if r['platform']=='Squarespace' and r['included']}==ssscope,'squarespace_inclusion_scope')
check({r['id'] for r in scope if r['platform']=='Shopify' and r['included']}==shscope,'shopify_inclusion_scope')

N='{http://schemas.openxmlformats.org/spreadsheetml/2006/main}';R='{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
def col(n):
 text='';n+=1
 while n:n,j=divmod(n-1,26);text=chr(65+j)+text
 return text
with zipfile.ZipFile(d['baseline']) as z:old={n:z.read(n) for n in z.namelist()}
with zipfile.ZipFile(d['output']) as z:
 check(z.testzip() is None,'saved_zip_integrity');new={n:z.read(n) for n in z.namelist()}
allowed={'xl/sharedStrings.xml','xl/styles.xml','xl/workbook.xml','xl/_rels/workbook.xml.rels','[Content_Types].xml'}
for part in old.keys()-allowed:check(new[part]==old[part],'original_package_part_byte_preserved',part)
for path,tags in [('xl/sharedStrings.xml',None),('xl/styles.xml',['fonts','fills','borders','cellStyleXfs','cellXfs','cellStyles','dxfs','numFmts'])]:
 a=E.fromstring(old[path]);b=E.fromstring(new[path])
 if tags is None:check([E.tostring(x) for x in list(b)[:len(a)]]==[E.tostring(x) for x in a],'original_shared_strings_preserved')
 else:
  for tag in tags:
   aa=a.find(N+tag);bb=b.find(N+tag)
   if aa is not None:check([E.tostring(x) for x in list(bb)[:len(aa)]]==[E.tostring(x) for x in aa],'original_style_prefix_preserved',tag)
workbook=E.fromstring(new['xl/workbook.xml']);sheets=list(workbook.find(N+'sheets'));old_sheets=list(E.fromstring(old['xl/workbook.xml']).find(N+'sheets'))
check([x.get('name') for x in sheets]==['Wall Sculptures']+[x.get('name') for x in old_sheets],'primary_sheet_first_all_source_tabs_retained')
check([x.attrib for x in sheets[1:]]==[x.attrib for x in old_sheets],'original_sheet_ids_unchanged')
check(workbook.find(N+'bookViews')[0].get('activeTab')=='0','primary_sheet_opens_first')
rels={x.get('Id'):x.get('Target') for x in E.fromstring(new['xl/_rels/workbook.xml.rels'])}
parts_by_name={s.get('name'):posixpath.normpath('xl/'+rels[s.get(R+'id')]) if not rels[s.get(R+'id')].startswith('/') else rels[s.get(R+'id')].lstrip('/') for s in sheets}
strings=[''.join(x.itertext()) for x in E.fromstring(new['xl/sharedStrings.xml'])]
root=E.fromstring(new[parts_by_name['Wall Sculptures']]);values={};formulas={}
for cell in root.iter(N+'c'):
 addr=cell.get('r');v=cell.findtext(N+'v','');typ=cell.get('t');check(typ!='e','no_primary_error_cell',addr)
 if typ=='s':v=strings[int(v)]
 elif typ=='inlineStr':v=''.join(cell.find(N+'is').itertext())
 elif typ=='b':v=v=='1'
 elif v and typ not in ('str','d'):v=float(v)
 values[addr]=v
 if cell.find(N+'f') is not None:formulas[addr]=cell.findtext(N+'f')
for j,x in enumerate(d['columns']):check(values[col(j)+'8']==x,'saved_primary_headers')
for i,row in enumerate(d['rows'],9):
 for j,x in enumerate(row):check(values.get(col(j)+str(i),'')==('' if x is None else x),'every_saved_primary_cell',col(j)+str(i))
check(formulas=={k:v.lstrip('=') for k,v in d['formulas'].items()},'primary_formula_text')
for k,v in d['expected_formula_values'].items():check(values[k]==v,'cached_primary_summary',k)
check(len(list(root.iter(N+'pane')))==1,'primary_frozen_headers_and_identifiers')
check(len(list(root.iter(N+'tablePart')))==1,'primary_filter_table')
part=parts_by_name['Wall Sculptures'];rp=posixpath.dirname(part)+'/_rels/'+posixpath.basename(part)+'.rels';sr={x.get('Id'):x.get('Target') for x in E.fromstring(new[rp])}
links={x.get('ref'):'#'+x.get('location') if x.get('location') else sr[x.get(R+'id')] for x in root.iter(N+'hyperlink')}
expected_links={col(int(ij.split(',')[1]))+str(int(ij.split(',')[0])+9):v['target'] for ij,v in d['links'].items()}
check(links==expected_links and len(links)==1496,'all_new_hyperlinks_exact')
targets={}
for target in links.values():
 if target.startswith('#'):
  sn,addr=target[1:].split('!');sn=sn.strip("'").replace("''","'")
  if sn not in targets:targets[sn]={c.get('r') for c in E.fromstring(new[parts_by_name[sn]]).iter(N+'c')}
  check(addr in targets[sn],'new_internal_target_exists',target)
total=sum(len(list(E.fromstring(new[p]).iter(N+'hyperlink'))) for p in parts_by_name.values());check(total==44617,'all_original_and_new_hyperlinks_retained')
styles=E.fromstring(new['xl/styles.xml']);nc=len(styles.find(N+'cellXfs'));ndxf=len(styles.find(N+'dxfs'))
for cell in root.iter(N+'c'):
 if cell.get('s') is not None:check(int(cell.get('s'))<nc,'valid_style_index',cell.get('r'))
for rule in root.iter(N+'cfRule'):
 if rule.get('dxfId') is not None:check(int(rule.get('dxfId'))<ndxf,'valid_conditional_style_index')
for x in manifest['inputs']:check(sha(x['path'])==x['sha256'],'inputs_unchanged_after_validation',x['path'])
receipt={'status':'PASS_UNIFIED_WALL_SHEET_COVERAGE_AND_PRESERVATION','checked_utc':datetime.now(timezone.utc).isoformat(),'output':d['output'],'sha256':sha(d['output']),'bytes':Path(d['output']).stat().st_size,'sheets':22,'primary_sheet':'Wall Sculptures','primary_rows':413,'reviewed_options':188,'other_source_rows':174,'photograph_groups':49,'folder_only_rows':2,'coverage':{k:len(v) for k,v in expected.items()},'original_source_tabs_preserved':21,'original_and_new_hyperlinks':total,'checks_passed':sum(checks.values()),'checks':dict(checks),'all_scoped_source_variants_once':True,'new_identity_approvals':0,'canonical_or_platform_writes':0}
(W/'validation.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))
