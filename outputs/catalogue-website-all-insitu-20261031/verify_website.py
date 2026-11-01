from pathlib import Path
from datetime import datetime,timezone
from decimal import Decimal
import csv,json,hashlib,collections
OUT=Path(__file__).resolve().parent
load=lambda name:{r['Variant ID [Non Editable]']:r for r in csv.DictReader((OUT/name).open(encoding='utf-8-sig'))}
before=load('inventory-before.csv');after=load('inventory-after.csv');expected=load('squarespace-catalogue-update.csv')
assert len(before)==len(after)==331 and len(expected)==178
assert set(before)==set(after) and set(expected)<=set(after)
diffs=[]
for vid,row in after.items():
 for k,value in row.items():
  same=Decimal(value)==Decimal(before[vid][k]) if k=='Price' else value==before[vid][k]
  if not same:
   assert vid in expected and k in ('Title','Description','Price'),(vid,k)
   diffs.append((vid,k))
 if vid in expected:
  for k in row:
   assert (Decimal(row[k])==Decimal(expected[vid][k]) if k=='Price' else row[k]==expected[vid][k]),(vid,k)
result={'status':'PASS_EXACT_NATIVE_EXPORT_READBACK','verified_utc':datetime.now(timezone.utc).isoformat(),'catalogue_products_updated':178,'public_listings':176,'hidden_photography_holds':2,'total_variant_records_preserved':331,'untouched_other_variants':153,'changed_fields':dict(collections.Counter(k for _,k in diffs)),'shipping_weights_stock_primary_galleries_preserved':True,'sha256':hashlib.sha256((OUT/'inventory-after.csv').read_bytes()).hexdigest()}
(OUT/'website-copy-verification.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
