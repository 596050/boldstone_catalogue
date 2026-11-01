"""Reconcile saved native galleries and prepare final copy and workbook mappings."""
from pathlib import Path
from datetime import datetime,timezone
from html.parser import HTMLParser
import csv,json,html,re,hashlib
OUT=Path(__file__).resolve().parent
read=lambda name:json.loads((OUT/name).read_text())
plan=read('website-final-plan.json'); full=read('all-image-execution-plan.json'); snap=read('catalogue-snapshot-latest.json');receipts=read('gallery-update-receipts.json')
products={p['catalogue_id']:p for p in full['products']}; source={p['id']:p for p in snap['products']}
assert len(receipts)==len({r['catalogue_id'] for r in receipts})==176
assert all(r['status']=='SAVED_UI' for r in receipts)
byreceipt={r['catalogue_id']:r for r in receipts}
with (OUT/'inventory-gallery-final.csv').open(encoding='utf-8-sig') as f:
 reader=csv.DictReader(f);headers=reader.fieldnames;native=list(reader)
with (OUT/'inventory-carousel-copy-after.csv').open(encoding='utf-8-sig') as f:before=list(csv.DictReader(f))
key='Variant ID [Non Editable]';old_by_variant={r[key]:r for r in before}; native_by_id={r['Product ID [Non Editable]']:r for r in native}
class Text(HTMLParser):
 def __init__(self):super().__init__();self.text=[];self.images=[]
 def handle_data(self,s):self.text.append(s)
 def handle_starttag(self,t,attrs):
  a=dict(attrs)
  if t=='img':self.images.append((a.get('src'),a.get('alt')))
def meaning(s):
 p=Text();p.feed(s);return ' '.join(''.join(p.text).split()),p.images
def image_identity(url):
 # Squarespace promotes editor upload URLs from /content/ to /content/v1/.
 return url.split('?')[0].replace('https://images.squarespace-cdn.com/content/v1/','https://images.squarespace-cdn.com/content/')
changes=[];rows=[];checks=[]
assert set(old_by_variant)=={r[key] for r in native}
for r in native:
 old=old_by_variant[r[key]];pid=r['Product ID [Non Editable]'];wanted=next((p for p in full['products'] if p['product_id']==pid and p['public']),None)
 allowed={'Hosted Image URLs','Description'} if wanted else set()
 assert all(r[k]==old[k] for k in headers if k not in allowed),(r['Title'],'unrelated native field changed')
 if wanted:
  rec=byreceipt[wanted['catalogue_id']];actual=r['Hosted Image URLs'].split()
  assert {image_identity(u) for u in actual}=={image_identity(a['src']) for a in rec['images']},(r['Title'],'gallery readback')
  published={image_identity(u):u for u in actual}
  for a in rec['images']:a['published_src']=published[image_identity(a['src'])]
  rec['published_primary_url']=published[image_identity(rec['primary_url'])]
  assert meaning(r['Description'])==meaning(next(x['Description'] for x in read('carousel-description-manifest.json')['rows'] if x['Product ID [Non Editable]']==pid)),(r['Title'],'description meaning changed')
  # First pilot receipt predates the explicit identity fields. Recover from the exact plan.
  for a in rec['images']:
   if 'content_hash' not in a:
    e=next((x for x in wanted['existing'] if x['native_url']==a['src']),None)
    filename=a['src'].split('?')[0].rsplit('/',1)[-1]
    if not e:e=next(x for x in wanted['additions'] if x['filename']==filename)
    match=next(x for x in wanted['gallery'] if x['content_hash']==e['content_hash'])
    a.update({k:match[k] for k in ['image_id','content_hash','role']})
  assert {a['content_hash'] for a in rec['images']}=={a['content_hash'] for a in wanted['gallery']}
  primary=next(a for a in rec['images'] if a['image_id']==wanted['primary_id'])
  assert primary['src']==rec['primary_url']
  assert image_identity(actual[0])==image_identity(rec['primary_url']),(r['Title'],'primary not first')
  assert [image_identity(u) for u in actual]==[image_identity(a['src']) for a in rec['images']],(r['Title'],'gallery order')
  checks.append({'catalogue_id':wanted['catalogue_id'],'images':len(actual),'primary_url':rec['published_primary_url'],'status':'PASS'})
for p in plan['products']:
 cid=p['catalogue_id'];s=source[cid];fields={v['key']:v['value'] for v in s['fields']+s['listing_fields']}
 if not p.get('product_id'):continue
 r=native_by_id[p['product_id']].copy();p['website_gallery']=[]
 if p['public']:
  rec=byreceipt[cid];situ_ids=set(s['photos']['in_situ_ids'])
  p['website_gallery']=[{'id':a['image_id'],'url':a['published_src'].split('?')[0],'alt':a['alt'],'content_hash':a['content_hash'],'role':a['role']} for a in rec['images']]
  p['website_in_situ']=[a for a in p['website_gallery'] if a['id'] in situ_ids]
  p['primary_url']=rec['published_primary_url'].split('?')[0];p['existing_images']=r['Hosted Image URLs'].split()
 narrative=re.split(r'\nDimensions:',fields['Description'],maxsplit=1)[0].strip()
 body=''.join('<p>'+html.escape(x.strip()).replace('\n','<br>')+'</p>' for x in re.split(r'\n\s*\n',narrative) if x.strip())
 details=[('Dimensions',fields['Dimensions / depth']),('Weight',fields['Weight']),('Use','Suitable for outdoor use and indoor display.'),('Fixings',fields['Fixing']),('Availability',fields['Availability']),('Production lead time',fields['Lead time']),('Delivery','Delivery is quoted separately. Please contact us for UK and international delivery options.')]
 body+='<ul>'+''.join('<li><strong>'+html.escape(k)+':</strong> '+html.escape(v.replace('\u2014','-'))+'</li>' for k,v in details)+'</ul>'
 if p['website_in_situ']:body+='<p>Room settings and group arrangements are illustrative; this listing is for the individual sculpture described above.</p>'
 assert not re.search(r'\b(GFRC|Jesmonite|plaster|concrete|moulding paste|Royal Mail|Tracked 48)\b',body,re.I)
 r['Description']=body;p['published_description_html']=body;p['website_description_html']=body;p['website_description']=fields['Description']
 rows.append(r);changes.append({'catalogue_id':cid,'product_id':p['product_id'],'gallery_photos':len(p['website_gallery']),'in_situ_photos':len(p['website_in_situ'])})
payload={'headers':headers,'rows':rows,'before_rows':[native_by_id[p['product_id']] for p in plan['products'] if p.get('product_id')],'changes':changes,'snapshot_event_cutoff':snap['event_cutoff'],'before_native_sha256':hashlib.sha256((OUT/'inventory-gallery-final.csv').read_bytes()).hexdigest()}
plan.update({'event_cutoff':snap['event_cutoff'],'source_snapshot_sha256':hashlib.sha256((OUT/'catalogue-snapshot-latest.json').read_bytes()).hexdigest(),'image_policy':'Current primary and selected listing photographs followed by every current associated, non-excluded, unrestricted in-situ photograph in the native product carousel. Exact-byte repeats appear once per product. Primary is first; hidden photography holds stay hidden.'})
(OUT/'gallery-final-copy-manifest.json').write_text(json.dumps(payload,indent=2,ensure_ascii=False))
(OUT/'website-final-plan.json').write_text(json.dumps(plan,indent=2,ensure_ascii=False))
(OUT/'gallery-native-verification.json').write_text(json.dumps({'status':'PASS_NATIVE_GALLERIES_AND_PRESERVED_FIELDS','at':datetime.now(timezone.utc).isoformat(),'products':len(checks),'placements':sum(r['images'] for r in checks),'checks':checks},indent=2))
(OUT/'gallery-update-receipts.json').write_text(json.dumps(receipts,indent=2))
(OUT/'catalogue-snapshot.json').write_bytes((OUT/'catalogue-snapshot-latest.json').read_bytes())
print({'verified':len(checks),'placements':sum(r['images'] for r in checks),'copy_rows':len(rows)})
