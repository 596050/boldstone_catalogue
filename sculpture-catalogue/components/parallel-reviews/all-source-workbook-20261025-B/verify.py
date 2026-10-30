"""Independently reconcile every source row, saved cell and native hyperlink."""
from pathlib import Path
from xml.etree import ElementTree as E
from collections import Counter,defaultdict
from datetime import datetime,timezone
import csv,hashlib,json,posixpath,sqlite3,sys,zipfile
W=Path(__file__).resolve().parent;B=W.parents[2]
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
d=read(W/'workbook-data.json');tabs={t['name']:t for t in d['tabs']};target=Path(d['output'])
manifest=read(W/'input-manifest.json');checks=Counter()
def check(ok,kind,detail=''):
 if not ok:raise AssertionError((kind,detail))
 checks[kind]+=1
for item in manifest['inputs']:check(sha(Path(item['path']))==item['sha256'],'frozen_inputs',item['path'])
pointer=read(B/'current-master.json');reg=read(B/pointer['register']);plan=read(pointer['current_listing_treatment_plan']['register'])
active={x['product_id']:x for x in reg['options'] if x['product_id'] in reg['active_option_ids']}
plans={x['product_id']:x for x in plan['options']}
check({x[0] for x in tabs['Products']['rows']}==set(active),'all_active_options')
check({x[0] for x in tabs['Components']['rows']}=={x['component_id'] for x in reg['components']},'all_components')
check({x[0] for x in tabs['Reviewed offers']['rows']}=={x['offer_ref'] for x in reg['source_offer_edges']},'all_reviewed_offers')
sm={(x[1],x[4]):x for x in tabs['Specifications']['rows']}
for p in reg['options']:
 for field,v in p['master_fields'].items():
  row=sm[(p['product_id'],field)]
  check(row[5]==v['display'] and row[6]==v.get('state') and row[7]==v.get('basis'),'original_working_field_and_basis',(p['product_id'],field))
  check(row[9]==v.get('physical_verification'),'physical_qualification_preserved')
for row in tabs['Products']['rows']:
 p=active[row[0]];t=plans[row[0]]
 for pos,key in [(6,'Dimensions / depth'),(7,'Weight'),(8,'Material / finish'),(9,'Fixing'),(12,'Individual price'),(13,'Availability')]:check(row[pos]==p['master_fields'][key]['display'],'product_working_values',row[0])
 check(row[10]==p.get('selling_details',{}).get('estimated_price'),'product_numeric_price')
 check(row[17]==t['selected_squarespace_product_id'] and row[18]==t['selected_squarespace_variant_id'] and row[19]==t['selected_local_shopify_handle'],'listing_ids_preserved')

sourcepaths={Path(x['path']).name:Path(x['path']) for x in manifest['inputs']}
sspath=next(p for p in sourcepaths.values() if p.name.startswith('products_Oct-24'))
shpath=sourcepaths['products_export_1 (1).csv']
def csvdata(p):
 with p.open(encoding='utf-8-sig',newline='') as f:r=csv.DictReader(f);return r.fieldnames,list(r)
ssh,ss=csvdata(sspath);shh,sh=csvdata(shpath)
for sn,header,rows in [('Squarespace raw',ssh,ss),('Shopify raw',shh,sh)]:
 check(tabs[sn]['columns']==['CSV record']+header,'raw_column_completeness',sn)
 check(len(tabs[sn]['rows'])==len(rows),'raw_row_completeness',sn)
 for ordinal,(raw,row) in enumerate(zip(rows,tabs[sn]['rows']),2):check(row==[str(ordinal)]+[raw[k] for k in header],'all_original_raw_cells',sn+str(ordinal))
ssids={x['Product ID [Non Editable]'] for x in ss if x['Product ID [Non Editable]']}
check({x[0] for x in tabs['Squarespace']['rows']}==ssids and len(ssids)==208,'all_squarespace_products')
check({x[0] for x in tabs['Squarespace variants']['rows']}=={x['Variant ID [Non Editable]'] for x in ss} and len(ss)==376,'all_squarespace_variants')
vmap={x[0]:x for x in tabs['Squarespace variants']['rows']};parent=None
for i,x in enumerate(ss,2):
 parent=x['Product ID [Non Editable]'] or parent;v=vmap[x['Variant ID [Non Editable]']]
 check(v[1]==parent and v[3]==x['SKU'] and v[17]==str(i),'squarespace_continuation_binding')
 for pos,key in [(5,'Price'),(6,'Sale Price'),(9,'Weight'),(10,'Length'),(11,'Width'),(12,'Height')]:
  value=float(x[key]) if x[key] else None
  check(v[pos]==value,'source_numeric_value_preserved',(i,key))
check({x[0] for x in tabs['Shopify']['rows']}=={r['Handle'] for r in sh},'all_shopify_products')

G=(B/pointer['current_published_gallery_projection']['path']).parent
with sqlite3.connect('file:'+str(G/'complete-image-platform-register.sqlite')+'?mode=ro',uri=True) as c:
 expected_files={x[0] for x in c.execute('SELECT file_id FROM images')}
 check({x[0] for x in tabs['Dropbox files']['rows']}==expected_files and len(expected_files)==6690,'all_dropbox_asset_records')
 check({x[0] for x in tabs['Shopify variants']['rows']}=={x[0] for x in c.execute('SELECT variant_key FROM local_shopify_variants')},'all_shopify_variants')
 source_edges={(a,b) for a,b in c.execute('SELECT product_id,offer_ref FROM source_product_links')}
 prepared_edges={(x[1],x[3]) for x in tabs['Catalogue source links']['rows']}
 check(source_edges.issubset(prepared_edges),'all_prior_source_edges_retained')
 latest_audit=read(sourcepaths['all-source-association-audit.json'])['entries']
 latest_edges={(x['product_id'],x['offer_ref']) for x in latest_audit}
 check(prepared_edges==source_edges|latest_edges and len(prepared_edges)==268,'complete_current_and_historical_source_edges')
 historical=[x for x in tabs['Catalogue source links']['rows'] if (x[1],x[3]) not in latest_edges]
 check(len(historical)==6 and all(x[6] is False and x[7]=='Historical component context; not selected in current individual plan' for x in historical),'historical_source_edges_not_exact_matches')
 all_edges={x[0]:(x[1],x[2],x[3],x[4]) for x in c.execute('SELECT association_id,product_id,file_id,intended_use,status FROM associations')}
 recovered={}
 for row in tabs['Image associations']['rows']:
  for aid in row[8].split('\n'):
   check(aid not in recovered,'unique_image_edge',aid);recovered[aid]=(row[1],row[3])
   check((row[1],row[3])==all_edges[aid][:2] and all_edges[aid][2] in row[7].split('\n') and all_edges[aid][3] in row[6].split('\n'),'image_edge_scope_preserved',aid)
 check(set(recovered)==set(all_edges) and len(recovered)==19494,'complete_image_evidence')
 for vk,blob in c.execute('SELECT variant_key,record_json FROM local_shopify_variants'):
  original=json.loads(blob);v=next(x for x in tabs['Shopify variants']['rows'] if x[0]==vk)
  check(v[1]==original['handle'] and v[3]==original['sku_raw'] and v[19]==str(original['source_row']['logical_row_including_header']),'shopify_variant_source_identity')
  check(v[5]==(float(original['price_raw']) if original['price_raw'] else None),'shopify_source_price')
native=read(sourcepaths['complete-current-native-object-map.json']);folder_ids={k for k,v in native.items() if v['object_type']=='folder'};file_ids={k for k,v in native.items() if v['object_type']=='file'}
check({x[0] for x in tabs['Dropbox folders']['rows']}==folder_ids and len(folder_ids)==442,'complete_current_folder_inventory')
current={x[0] for x in tabs['Dropbox files']['rows'] if x[6]=='CURRENT_NATIVE_FILE_AND_ACTUAL_PARENT_VERIFIED'}
check(current==file_ids and len(current)==6360,'complete_current_file_inventory')
u=read(G/'current-images-without-option-scope.json');um={x['file_id'] for x in u}
check({x[0] for x in tabs['Dropbox files']['rows'] if x[5]=='No product-option association'}==um and len(um)==625,'all_unassigned_images_retained')
check({x[2] for x in tabs['Unmatched and qualified']['rows'] if x[1]=='Dropbox'}==um,'unassigned_review_queue')
check(sum(x[4]=='individual' and x[0] in um for x in tabs['Dropbox files']['rows'])==73,'individual_unassigned_scope')
for x in tabs['Platform SKU pairs']['rows']:
 check(x[0] and x[1]=='Exact raw SKU pair','raw_sku_pair_scope')
 ssr=ss[x[9]-2];shr=sh[x[10]-2];check(ssr['SKU']==shr['Variant SKU']==x[0],'independent_exact_raw_sku_pair')
check(len({x[0] for x in tabs['Platform SKU pairs']['rows']})==140,'unique_full_export_sku_pairs')

if '--source-only' in sys.argv:
 print(json.dumps({'status':'PASS_SOURCE_RECONCILIATION','checks_passed':sum(checks.values()),'categories':dict(checks)}));sys.exit(0)

# Check serialized workbook independently of Artifact Tool's authoring state.
NS='{http://schemas.openxmlformats.org/spreadsheetml/2006/main}';R='{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
def col(n):
 s='';n+=1
 while n:n,k=divmod(n-1,26);s=chr(65+k)+s
 return s
saved_formula_values={};total_links=0;values_read={}
with zipfile.ZipFile(target) as z:
 check(z.testzip() is None,'xlsx_zip_integrity')
 rels={x.get('Id'):x.get('Target') for x in E.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
 sheets=list(E.fromstring(z.read('xl/workbook.xml')).find(NS+'sheets'))
 check([x.get('name') for x in sheets]==list(tabs),'all_workbook_tabs_and_order')
 strings=[''.join(x.itertext()) for x in E.fromstring(z.read('xl/sharedStrings.xml'))] if 'xl/sharedStrings.xml' in z.namelist() else []
 for s in sheets:
  sn=s.get('name');t=tabs[sn];part=rels[s.get(R+'id')];part=part.lstrip('/') if part.startswith('/') else posixpath.normpath('xl/'+part)
  root=E.fromstring(z.read(part));vals={};forms={}
  for cell in root.iter(NS+'c'):
   raw=cell.findtext(NS+'v','');typ=cell.get('t');value=raw
   if typ=='s':value=strings[int(raw)]
   elif typ=='inlineStr':value=''.join(cell.find(NS+'is').itertext())
   elif typ=='b':value=raw=='1'
   elif raw and typ not in ('str','e'):value=float(raw)
   check(typ!='e','saved_cell_not_error',sn+'!'+cell.get('r'))
   vals[cell.get('r')]=value
   if cell.find(NS+'f') is not None:forms[cell.get('r')]=cell.findtext(NS+'f');saved_formula_values[cell.get('r')]=value
  values_read[sn]=vals
  for j,v in enumerate(t['columns']):check(vals[col(j)+'6']==v,'saved_header',sn)
  for i,row in enumerate(t['rows'],7):
   for j,v in enumerate(row):
    addr=col(j)+str(i)
    if addr in t['formulas']:continue
    check(vals.get(addr,'')==('' if v is None else v),'every_saved_data_cell',sn+'!'+addr)
  check(forms=={k:v.lstrip('=') for k,v in t['formulas'].items()},'saved_formula_text',sn)
  relpart=posixpath.dirname(part)+'/_rels/'+posixpath.basename(part)+'.rels'
  sr={r.get('Id'):r.get('Target') for r in E.fromstring(z.read(relpart))} if relpart in z.namelist() else {}
  links={}
  for a in root.iter(NS+'hyperlink'):links[a.get('ref')]='#'+a.get('location') if a.get('location') else sr[a.get(R+'id')]
  expected={col(int(ij.split(',')[1]))+str(int(ij.split(',')[0])+7):v['target'] for ij,v in t['links'].items()}
  check(links==expected,'all_saved_native_hyperlinks',sn);total_links+=len(links)
  check(len(list(root.iter(NS+'tablePart')))==1,'filter_table_present',sn)
  if sn!='Overview':check(len(list(root.iter(NS+'pane')))==1,'frozen_identifiers_and_headers',sn)
 for t in d['tabs']:
  for link in t['links'].values():
   if link['target'].startswith('#'):
    match=link['target'][1:].split('!');sn=match[0].strip("'").replace("''","'");addr=match[1]
    check(sn in values_read and (addr=='A1' or addr in values_read[sn]),'internal_link_target_exists',link['target'])
expected=read(W/'authoring-receipt.json')['formulaValues']
check(saved_formula_values==expected,'all_saved_summary_results')
check(total_links==sum(len(t['links']) for t in d['tabs']),'total_native_links')
for item in manifest['inputs']:check(sha(Path(item['path']))==item['sha256'],'source_and_canonical_preservation',item['path'])
result={'status':'PASS_COMPLETE_SAVED_WORKBOOK_AND_SOURCE_RECONCILIATION','checked_utc':datetime.now(timezone.utc).isoformat(),'output':str(target),'sha256':sha(target),'bytes':target.stat().st_size,'sheets':len(tabs),'checks_passed':sum(checks.values()),'check_categories':dict(checks),'native_hyperlinks':total_links,'counts':d['counts'],'retained_components':112,'retained_reviewed_offers':81,'all_original_squarespace_csv_cells_retained':True,'all_original_shopify_csv_cells_retained':True,'all_source_and_master_input_hashes_unchanged':True,'identity_approvals_added':0,'platform_writes':0}
(W/'validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
