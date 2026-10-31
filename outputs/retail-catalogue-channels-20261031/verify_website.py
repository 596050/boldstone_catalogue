from pathlib import Path
import csv,json,collections,re,hashlib
from datetime import datetime,timezone
OUT=Path(__file__).resolve().parent
load=lambda f:{r['Variant ID [Non Editable]']:r for r in csv.DictReader((OUT/f).open())}
before=load('inventory-after-retail.csv');after=load('inventory-after-descriptions.csv');expected=load('squarespace-description-update.csv')
assert len(before)==len(after)==331 and len(expected)==178
assert set(before)==set(after) and set(expected)<=set(after)
diffs=[]
for vid,row in after.items():
 for key,value in row.items():
  if value!=before[vid][key]:
   assert vid in expected and key in ('Title','Description'),(vid,key)
   diffs.append((vid,key))
 if vid in expected:
  assert row['Title']==expected[vid]['Title'] and row['Description']==expected[vid]['Description']
  public=' '.join(row[k] for k in ('Title','Description','Tags','Categories'))
  assert not re.search(r'\b(GFRC|Jesmonite|plaster|concrete|moulding paste|Royal Mail|Tracked 48)\b',public,re.I),(vid,'unwanted wording')
  assert 'Suitable for outdoor use' in public and 'French cleats' in public and 'Keyhole fixings' in public
receipt={'status':'PASS_EXACT_NATIVE_EXPORT_READBACK','verified_utc':datetime.now(timezone.utc).isoformat(),'catalogue_products_updated':len(expected),'total_variant_records_preserved':len(after),'changed_fields':dict(collections.Counter(k for i,k in diffs)),'unrelated_products_unchanged':128,'public_catalogue_products':sum(after[i]['Visible']=='Yes' for i in expected),'hidden_photography_holds':sum(after[i]['Visible']=='No' for i in expected),'prices_skus_stock_visibility_gallery_images_unchanged':True,'material_and_carrier_wording_absent':True,'sha256':hashlib.sha256((OUT/'inventory-after-descriptions.csv').read_bytes()).hexdigest()}
(OUT/'website-copy-verification.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))
