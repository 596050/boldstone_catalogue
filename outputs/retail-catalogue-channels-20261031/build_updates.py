"""Prepare an exact-ID Squarespace title update; keep prices and other records."""
from pathlib import Path
import csv, json
OUT=Path(__file__).resolve().parent
PREV=OUT.parent/'01a13fe6-495b-7253-b923-31823b4cbca8/squarespace-replacement-20261030'
plan=json.loads((OUT/'retail-plan.json').read_text())
native=json.loads((PREV/'new-native-mappings.json').read_text())
if isinstance(native,dict):
    native=native.get('products',native.get('mappings'))
mapping={p['catalogue_id']:p for p in native}
source=PREV/'removal-20261031/inventory-after-publication.csv'
with source.open(newline='',encoding='utf-8-sig') as stream:
    reader=csv.DictReader(stream); headers=reader.fieldnames; original=list(reader)
byid={r['Product ID [Non Editable]']:r for r in original if r['Product ID [Non Editable]']}
rows=[]
for p in plan['products']:
    if p['listing_decision']!='include': continue
    m=mapping[p['catalogue_id']]; before=byid[m['product_id']]
    assert before['Title']==p['catalogue_name']
    assert before['SKU']==m['sku']
    row=before.copy(); row['Title']=p['retail_name']
    # Keep the original designation searchable in the existing factual description.
    desc=before['Description']
    if p['catalogue_name'] in desc:
        desc=desc.replace(p['catalogue_name'],p['retail_name'],1)
    row['Description']=desc
    p.update(product_id=m['product_id'],variant_id=m['variant_id'],sku=m['sku'],price=m['price'],
             public=before['Visible']=='Yes',website_url='https://boldstonesculpture.com/buy/p/'+m['slug'],
             existing_images=m['images'])
    rows.append(row)
assert len(rows)==178 and len({r['Product ID [Non Editable]'] for r in rows})==178
with (OUT/'squarespace-retail-title-update.csv').open('w',newline='') as stream:
    writer=csv.DictWriter(stream,fieldnames=headers); writer.writeheader();writer.writerows(rows)
(OUT/'website-plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2))
print(json.dumps({'existing_products_to_update':len(rows),'new_products_to_create':0,
                  'published':sum(p.get('public',False) for p in plan['products'])}))
