"""Reconcile the native readback and prepare uniquely prefixed catalogue cells."""
import hashlib,json,re,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path('/Users/tprice/Documents/boldstone');OUT=Path(__file__).parent
sys.path.insert(0,'/tmp/boldstone-brandboom-xls-reader')
sys.path.insert(0,str(ROOT/'catalogue-review/scripts'))
import xlrd
from python_calamine import CalamineWorkbook
from import_saatchi_snapshot import Xlsx,column,column_index
read=lambda p:json.loads(p.read_text())
save=lambda n,v:(OUT/n).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
now=datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00','Z')
native_path=OUT/'brandboom-native-export.xls'
sheet=xlrd.open_workbook(native_path,ignore_workbook_corruption=True).sheet_by_index(0)
rows=[sheet.row_values(i) for i in range(sheet.nrows)]
independent=CalamineWorkbook.from_path(str(native_path)).get_sheet_by_index(0).to_python()
assert rows==independent,'Native readers disagree'
headers=rows[0];native={}
for row in rows[1:]:
 d=dict(zip(headers,row));sku=d['SKU Number'];assert sku
 if sku in native:assert native[sku]==d,'Conflicting repeated SKU'
 native[sku]=d
source=read(OUT.parent/'brandboom-import-20261105/upload-plan.json')
expected={r[0]:dict(zip(source['headers'],r)) for r in source['rows']}
assert set(native)==set(expected) and len(native)==176
checked=['SKU Number','Style ID','Option Code','Option Name','Size','Name','Description','Type','Category','Minimum Quantity','Wholesale (GBP)']
for sku,d in native.items():
 for h in checked:
  if h in ['Minimum Quantity','Wholesale (GBP)']:assert float(d[h])==float(expected[sku][h]),(sku,h)
  else:assert d[h]==expected[sku][h],(sku,h)
 assert d['Vendor']=='Boldstone' and d['Season']=='Year-round'
 assert float(d['Retail (GBP)'])==0,'Retail choice changed; re-review'
 assert not d['Inactive']
receipt=dict(status='PASS_176_NATIVE_CORE_VENDOR_SEASON_OPTION_LABELS',checked_utc=now,
 unique_skus=len(native),raw_export_rows=len(rows)-1,all_readers_agree=True,
 fields_checked=checked+['Vendor','Season','Retail (GBP)','Inactive'],mismatches=[],
 export_sha256=hashlib.sha256(native_path.read_bytes()).hexdigest(),
 taxonomy_verification='176 selected and saved through native Mass Edit; saved taxonomy independently observed on first 50 product rows. Native export does not expose taxonomy.',
 image_verification='Original import retained; 17 galleries / 124 placements checked in prior import pass. New field-only uploads contained no image fields.',
 native_records=native)
save('native-reconciliation.json',receipt)
master=Xlsx(OUT/'previous-catalogue.xlsx');sheet_name='Wall Sculptures'
existing={master.value(sheet_name,a):re.sub(r'\d','',a) for a in master.cells[sheet_name] if re.fullmatch('[A-Z]+7',a)}
assert not any(h.startswith('brandboom_') for h in existing)
first=max(column_index(c) for c in existing.values())+1
native_names={
 'UPC':'upc','SKU Number':'sku','Style ID':'style_id','Option Code':'option_code','Size':'size',
 'Name':'name','Description':'description','Option Name':'option_name','Type':'type','Category':'category',
 'Season':'season','Delivery Date':'delivery_date','Minimum Quantity':'minimum_quantity',
 'Inventory Count':'inventory_count','Available Count':'available_count',
 'Future Inventory Count':'future_inventory_count','Future Available Count':'future_available_count',
 'External Product ID':'external_product_id','External Sku ID':'external_sku_id','Barcode':'barcode',
 'Vendor':'vendor','Wholesale (GBP)':'wholesale_gbp','Retail (GBP)':'native_retail_gbp','Inactive':'inactive'}
extra=['catalogue_scope','showroom_id','showroom_url','retail_proposed_gbp','retail_status','prepack',
 'taxonomy_path','taxonomy_verification','source_revision','source_image_ids','source_image_count',
 'image_verification','presentation_id','presentation_edit_url','presentation_title','presentation_section',
 'presentation_status','presentation_order_type','presentation_show_prices','presentation_prepack_display',
 'marketplace_lifestyle_category','marketplace_lifestyle_status','marketplace_return_policy_proposed',
 'marketplace_fee_displayed','publication_status','checked_utc']
added=['brandboom_'+native_names[h] for h in headers]+['brandboom_'+h for h in extra]
assert len(added)==len(set(added)) and not set(added)&set(existing)
allheaders=existing|{h:column(first+i) for i,h in enumerate(added)}
by_pid={r['catalogue_id']:r for r in source['records']}
master_rows={master.value(sheet_name,'AA'+str(n)):n for n in range(8,189)}
assert len(master_rows)==181 and set(by_pid)<=set(master_rows)
values={}
numeric={'brandboom_'+native_names[h] for h in ['Wholesale (GBP)','Retail (GBP)','Minimum Quantity','Inventory Count','Available Count','Future Inventory Count','Future Available Count']}
numeric|={'brandboom_retail_proposed_gbp','brandboom_source_image_count'}
for pid,n in master_rows.items():
 r=by_pid.get(pid)
 d={'brandboom_catalogue_scope':'Imported publication product' if r else 'Not imported: outside the approved 176-product publication scope',
    'brandboom_publication_status':'NOT_PUBLIC: presentation saved; Marketplace not submitted or approved' if r else 'NOT_IMPORTED',
    'brandboom_checked_utc':'Checked UTC: '+now}
 if r:
  for h in headers:
   v=native[r['sku']][h]
   if v=='':continue
   name='brandboom_'+native_names[h]
   if name in numeric:v=float(v);v=int(v) if v.is_integer() else v
   d[name]=v
  d.update(brandboom_showroom_id='111089',brandboom_showroom_url=source['showroom_url'],
   brandboom_retail_proposed_gbp=master.value(sheet_name,'RB'+str(n)),
   brandboom_retail_status='PENDING OWNER CHOICE: native Retail is unset/default 0, not a selling price. Protected suggested retail is a proposal; current website retail is below protected wholesale.',
   brandboom_prepack='No prepack; one individually described sculpture per SKU; MOQ 1',
   brandboom_taxonomy_path='Home Decor / Wall Decor / Wall Art',
   brandboom_taxonomy_verification=receipt['taxonomy_verification'],
   brandboom_source_revision=source['app_revision'],brandboom_source_image_ids='\n'.join(r['image_ids']),
   brandboom_source_image_count=r['image_count'],brandboom_image_verification=receipt['image_verification'],
   brandboom_presentation_id='681061',brandboom_presentation_edit_url='https://manage.brandboom.com/products/s/111089/p/681061',
   brandboom_presentation_title='Boldstone Wall Sculptures',brandboom_presentation_section='PRODUCTS',
   brandboom_presentation_status='176/176 saved in presentation. Native warning: Product Limit Reached (50/50). Owner-only preview; no public share link created.',
   brandboom_presentation_order_type='At-Once; 10-working-day dispatch stated in product description',
   brandboom_presentation_show_prices='Wholesale Price',brandboom_presentation_prepack_display='Off',
   brandboom_marketplace_lifestyle_category='Home',
   brandboom_marketplace_lifestyle_status='Application prepared, not submitted: Retail choice, plan visibility limit, final terms acceptance and payment setup remain to resolve.',
   brandboom_marketplace_return_policy_proposed="Seller's Discretion; staged only, not accepted",
   brandboom_marketplace_fee_displayed='Native application displays 10% per transaction; contractual/FX details require review before Join')
 values[pid]=d
patches=[]
for h in added:
 patches.append(dict(sheet=sheet_name,cell=allheaders[h]+'7',before=None,value=h))
 for pid,n in master_rows.items():
  if h not in values[pid]:continue
  cell=allheaders[h]+str(n);assert master.value(sheet_name,cell) in (None,'')
  patches.append(dict(sheet=sheet_name,cell=cell,before=master.value(sheet_name,cell),value=values[pid][h]))
plan=dict(scope='Add uniquely prefixed brandboom_ native fields, proposals and verified publication blockers to all 181 retained component rows. 176 native products reconciled by exact SKU. Existing specifications, prices, costs, photo choices and all other platform fields preserved.',
 first_added_column=first,last_column=first+len(added)-1,added_headers=added,headers=allheaders,
 numeric_headers=sorted(numeric),patches=patches,preview_range=column(first)+'7:'+column(first+2)+'10')
save('catalogue-plan.json',plan);save('plan.json',plan)
save('brandboom-records.json',values)
save('presentation-receipt.json',dict(status='SAVED_176_NOT_PUBLIC_PLAN_LIMIT',presentation_id='681061',
 edit_url='https://manage.brandboom.com/products/s/111089/p/681061',saved_products=176,
 owner_preview_only=True,native_plan_warning='Product Limit Reached (50/50)',
 marketplace_submitted=False,checked_utc=now))
save('option-label-correction-receipt.json',dict(status='COMPLETE_176_UPDATED_NONE_ADDED_NATIVE_EXPORT_VERIFIED',checked_utc=now,products_updated=176,skus_updated=176,products_added=0,option_labels_restored=176))
save('taxonomy-receipt.json',dict(status='NATIVE_APPLIED_176_SAVED_SAMPLE_50_REOPENED',checked_utc=now,products=176,taxonomy='Home Decor / Wall Decor / Wall Art',native_export_exposes_taxonomy=False))
print(json.dumps(dict(native_unique_skus=len(native),fields_added=len(added),patches=len(patches),preview=plan['preview_range'])))
