"""Pin current app selections to existing native store IDs, without a two-photo cap."""
from pathlib import Path
import csv, json, hashlib, collections
OUT=Path(__file__).resolve().parent
OLD=OUT.parent/'retail-catalogue-channels-20261031'
read=lambda p:json.loads(p.read_text())
s=read(OUT/'catalogue-snapshot.json')
previous=read(OLD/'website-final-plan.json')
native=list(csv.DictReader((OUT/'inventory-before.csv').open(encoding='utf-8-sig')))
byid={r['Product ID [Non Editable]']:r for r in native if r['Product ID [Non Editable]']}
old_assets={r['filename']:r['src'].split('?')[0] for r in read(OLD/'native-insitu-assets.json')}
old_stage=read(OLD/'staged-in-situ.json')
byhash={r['content_hash']:dict(r,url=old_assets[r['filename']]) for r in old_stage.values() if r.get('filename') in old_assets}
products={p['id']:p for p in s['products']}; assets={};plans=[]
assert s['cost_settings']['labour_hourly']==0
assert len(native)==331 and len(products)==181
for prior in previous['products']:
 p=products[prior['catalogue_id']]; row=dict(prior)
 row.update(catalogue_name=p['name'],retail_name=p['retail_name'],listing_decision=p['listing_decision'],in_situ=[],website_in_situ=[])
 assert p['costing']['labour_cost']==0
 assert p['costing']['manufacturing_cost']==p['costing']['total_cost']
 row['price']=f"{p['costing']['pricing']['marked_up_price']:.2f}"
 if prior.get('product_id'):
  n=byid[prior['product_id']]
  assert n['SKU']==prior['sku'] and n['Variant ID [Non Editable]']==prior['variant_id']
  assert (n['Visible']=='Yes')==prior.get('public')
  assert p['listing_decision']=='include'
  row['before_price']=n['Price']
 if row.get('public'):
  rows=[r for r in s['images'] if r['product_id']==p['id'] and r['scope']=='Associated' and 'in_situ' in r['image']['effective_types'] and not r['image']['excluded'] and not r['image']['withheld_reasons']]
  rows.sort(key=lambda r:(r['choice'].get('order',0),r['image']['name'],r['image']['id']))
  seen=set()
  for r in rows:
   im=r['image']; h=im['original']['dropbox_content_hash']; assert im['source']=='Dropbox' and h
   if h in seen:continue
   seen.add(h)
   asset={'image_id':im['id'],'name':im['name'],'url':im['url'],'content_hash':h,'bytes':im['original']['bytes'],'path':im['provenance']['path'],'alt':r['choice'].get('alt') or p['retail_name']+' - in situ'}
   if h in byhash:asset['website_url']=byhash[h]['url']
   assets.setdefault(h,asset);row['in_situ'].append(asset)
 plans.append(row)
payload={'created_utc':s['created_utc'],'event_cutoff':s['event_cutoff'],'source_snapshot_sha256':hashlib.sha256((OUT/'catalogue-snapshot.json').read_bytes()).hexdigest(),'image_policy':'Every current associated, non-excluded, unrestricted in-situ photograph. Exact-byte repeats appear once per product. Existing product galleries and primary photos retained.','products':plans,'assets':list(assets.values())}
(OUT/'website-plan.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2))
print(json.dumps({'mapped_products':sum(bool(p.get('product_id')) for p in plans),'public':sum(p.get('public',False) for p in plans),'in_situ_placements':sum(len(p['in_situ']) for p in plans),'distinct_photos':len(assets),'already_hosted':sum('website_url' in a for a in assets.values()),'new_photos':sum('website_url' not in a for a in assets.values()),'price_changes':sum(bool(p.get('product_id')) and p['price']!=p['before_price'] for p in plans)}))
