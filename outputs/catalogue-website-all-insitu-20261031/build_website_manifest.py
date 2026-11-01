"""Prepare exact existing-product changes, preserving stock, shipping and primary galleries."""
from pathlib import Path
from datetime import datetime,timezone
import csv,hashlib,html,json,re
OUT=Path(__file__).resolve().parent
read=lambda p:json.loads(p.read_text())
s=read(OUT/'catalogue-snapshot.json');plan=read(OUT/'website-plan.json')
assets=read(OUT/'hosted-assets.json');stage=read(OUT/'staged-in-situ.json')
hosted={a['filename']:a['src'].split('?')[0] for a in assets if a.get('src','').startswith('https://images.squarespace-cdn.com/')}
with (OUT/'inventory-before.csv').open(encoding='utf-8-sig') as f:reader=csv.DictReader(f);headers=reader.fieldnames;native=list(reader)
byid={x['Product ID [Non Editable]']:x for x in native if x['Product ID [Non Editable]']}
products={p['id']:p for p in s['products']};rows=[];changes=[]
for p in plan['products']:
 if not p.get('product_id'):continue
 current=products[p['catalogue_id']];f={x['key']:x['value'] for x in current['fields']+current['listing_fields']}
 old=byid[p['product_id']];row=old.copy()
 assert old['SKU']==p['sku'] and old['Variant ID [Non Editable]']==p['variant_id']
 # Use current catalogue copy and authoritative current specification values.
 narrative=re.split(r'\nDimensions:',f['Description'],maxsplit=1)[0].strip()
 body=''.join('<p>'+html.escape(x.strip()).replace('\n','<br>')+'</p>' for x in re.split(r'\n\s*\n',narrative) if x.strip())
 details=[('Dimensions',f['Dimensions / depth']),('Weight',f['Weight']),('Use','Suitable for outdoor use and indoor display.'),('Fixings',f['Fixing']),('Availability',f['Availability']),('Production lead time',f['Lead time']),('Delivery','Delivery is quoted separately. Please contact us for UK and international delivery options.')]
 body+='<ul>'+''.join('<li><strong>'+html.escape(k)+':</strong> '+html.escape(v.replace('\u2014','-'))+'</li>' for k,v in details)+'</ul>'
 p['website_description_html']=body;p['website_description']=f['Description'];p['website_in_situ']=[]
 for a in p['in_situ']:
  url=a.get('website_url')
  if not url:
   x=stage[a['content_hash']];assert x['status']=='verified';url=hosted[x['filename']]
  p['website_in_situ'].append({'id':a['image_id'],'url':url,'original_name':a['name'],'dropbox_path':a['path'],'alt':a['alt']})
 if p['website_in_situ']:
  body+='<h3>In a setting</h3><p>Styling inspiration showing the sculpture in context. Room settings and group arrangements are illustrative; this listing is for the individual sculpture described above.</p>'
  body+='<div class="boldstone-in-situ-gallery" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px;">'
  for a in p['website_in_situ']:
   body+='<p style="margin:0;"><a href="'+html.escape(a['url']+'?format=2500w',quote=True)+'" target="_blank" rel="noopener"><img src="'+html.escape(a['url']+'?format=1500w',quote=True)+'" alt="'+html.escape(a['alt'],quote=True)+'" loading="lazy" decoding="async" style="max-width:100%;height:auto;" /></a></p>'
  body+='</div>'
 assert not re.search(r'\b(GFRC|Jesmonite|plaster|concrete|moulding paste|Royal Mail|Tracked 48)\b',p['retail_name']+' '+body,re.I)
 row['Title']=p['retail_name'];row['Description']=body;row['Price']=p['price'];p['published_description_html']=body
 for key in headers:
  if key not in ('Title','Description','Price'):assert row[key]==old[key],(p['catalogue_id'],key)
 p['website_in_situ_skipped']=[]
 rows.append(row);changes.append({'catalogue_id':p['catalogue_id'],'product_id':p['product_id'],'variant_id':p['variant_id'],'sku':p['sku'],'title':p['retail_name'],'old_price':old['Price'],'new_price':p['price'],'in_situ_images':len(p['website_in_situ']),'public':p['public']})
assert len(rows)==178 and sum(p['public'] for p in changes)==176
payload={'prepared_utc':datetime.now(timezone.utc).isoformat(),'headers':headers,'rows':rows,'before_rows':[byid[p['product_id']] for p in changes],'changes':changes,'snapshot_event_cutoff':s['event_cutoff'],'before_native_sha256':hashlib.sha256((OUT/'inventory-before.csv').read_bytes()).hexdigest()}
(OUT/'website-update-manifest.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2))
(OUT/'website-final-plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2))
report={'status':'PREPARED','public_listings':176,'existing_products':178,'in_situ_placements':sum(len(p['website_in_situ']) for p in plan['products']),'distinct_in_situ_photos':len(plan['assets']),'no_two_photo_cap':True,'without_in_situ':[p['retail_name'] for p in plan['products'] if p.get('public') and not p['website_in_situ']]}
(OUT/'website-photo-readiness.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
