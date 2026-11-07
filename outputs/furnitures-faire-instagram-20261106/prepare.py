import json,re,sys,shutil,hashlib
from pathlib import Path
from decimal import Decimal,ROUND_CEILING
from datetime import datetime,timezone
ROOT=Path('/Users/tprice/Documents/boldstone');OUT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'catalogue-review'))
sys.path.insert(0,str(ROOT/'catalogue-review/scripts'))
from channel_content import values,marketplace_title,complete_description,appearance
from import_saatchi_snapshot import Xlsx
read=lambda p:json.loads(p.read_text())
save=lambda n,v:(OUT/n).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
norm=lambda s:re.sub('[^a-z0-9]','',s.lower())
now=datetime.now(timezone.utc).isoformat()
pointer=read(ROOT/'sculpture-catalogue/current-master.json')
save('source-pointer-before.json',pointer)
source=Path(pointer['current_app_review_workbook']['path'])
assert hashlib.sha256(source.read_bytes()).hexdigest()==pointer['current_app_review_workbook']['sha256']
shutil.copy2(source,OUT/'previous-catalogue.xlsx')
app=read(OUT/'app-specifications.json');by_pid={p['id']:p for p in app['products']}
approved=read(ROOT/'outputs/brandboom-import-20261105/upload-plan.json')
assert len(approved['records'])==176
old=read(ROOT/'outputs/platform-rollout-20261104/faire-update.json')
old_by_name={norm(r[1]):dict(zip(old['headers'],r)) for r in old['rows']}
sku_pid={r['sku']:r['catalogue_id'] for r in approved['records']}
faire=[]
for line in (OUT/'evidence/faire-preview-all-176.txt').read_text().splitlines():
 m=re.search(r'£([\d,.]+) RRP £([\d,.]+) (.*?)(?:, Value:.*)?$',line)
 if not m:continue
 wholesale,retail=map(lambda s:Decimal(s.replace(',','')),m.group(1,2))
 prior=old_by_name[norm(m[3])];sku=prior['SKU'];pid=sku_pid[sku]
 f=values(by_pid[pid]);assert f['Seller SKU']==sku
 url=re.search(r'faire.com/product/[a-z0-9_]+',line)
 faire.append(dict(catalogue_id=pid,sku=sku,name=m[3],wholesale_gbp=float(wholesale),retail_gbp=float(retail),
   retail_to_wholesale=float(retail/wholesale),margin_valid=wholesale*Decimal('1.25')<=retail<=wholesale*10,
   url='https://'+url[0] if url else '',checked_utc=now,
   status='SHOP_INACTIVE_REVIEWING_CATALOGUE_EDITOR_LOCKED',source='Native Faire shop preview; 176 of 176 products displayed'))
assert len(faire)==176 and len({x['catalogue_id'] for x in faire})==176 and all(x['margin_valid'] for x in faire)
save('faire-observed-prices.json',dict(checked_utc=now,records=faire,
 requirement='Retail must be 1.25 to 10 times wholesale; wholesale price must match other wholesale channels. Faire Brand Onboarding email, 6 November 2026.',
 shop_url='https://www.faire.com/brand/b_dddpsekzv4',edit_status='Native bulk editor redirects to locked review homepage',
 email_reported_action='Sender reports wholesale and retail raised by 30%; readback verifies current values only, not publication approval.'))
site=read(ROOT/'outputs/moonshell-lava-channel-refresh-20261031/website-final-plan.json')
site_by_pid={p['catalogue_id']:p for p in site['products']}
headers=['Type','SKU','Name','Published','Visibility in catalog','Description','In stock?','Stock','Backorders allowed?','Regular price','Categories','Images','Attribute 1 name','Attribute 1 value(s)','Attribute 1 visible','Attribute 1 global','Attribute 2 name','Attribute 2 value(s)','Attribute 2 visible','Attribute 2 global','Attribute 3 name','Attribute 3 value(s)','Attribute 3 visible','Attribute 3 global']
records=[];rows=[]
for binding in approved['records']:
 pid=binding['catalogue_id'];p=by_pid[pid];f=values(p);sku=f['Seller SKU'];assert sku==binding['sku']
 wp=site_by_pid[pid]
 gallery=wp['website_gallery']
 assert isinstance(gallery,list)
 current={x['id'] for role in ['listing','in_situ'] for x in p['photos'][role]['images']}
 photos=[x for x in gallery if x['id'] in current]
 primary=p['photos']['primary_listing'].get('image_id')
 photos.sort(key=lambda x:x['id']!=primary)
 assert photos and photos[0]['id']==primary,(pid,'Current primary not in verified website gallery')
 situ=[x for x in photos if x.get('role')=='in_situ']
 listing=[x for x in photos if x.get('role')!='in_situ']
 chosen=(listing[:max(1,6-min(2,len(situ)))]+situ[:2])[:6]
 urls=[x['url'] for x in chosen]
 assert len(set(urls))==len(urls) and all(x.startswith('https://images.squarespace-cdn.com/') for x in urls)
 retail=Decimal(str(p['costing']['pricing']['marked_up_price']))
 asking=(retail/Decimal('.90')).quantize(Decimal('.01'),rounding=ROUND_CEILING)
 assert asking*Decimal('.90')>=retail
 desc=complete_description(p,sku,10)
 desc=re.sub(r'(?m)^Delivery:.*$', 'Delivery: The delivery charge for your order is shown at checkout. Carrier transit time is additional to dispatch time.',desc)
 r=dict(catalogue_id=pid,sku=sku,title=marketplace_title(p),description=desc,
   catalogue_retail_gbp=float(retail),price_gbp=float(asking),commission_rate=.10,
   price_basis='Catalogue retail divided by 0.90, rounded upward to a penny; preserves catalogue net after advertised 10% commission, before packing and delivery.',
   category='Living Room',material='Gypsum-based material',dimensions=f['Dimensions / depth'],colour=appearance(p),
   stock=1,stock_basis='One available sale unit per SKU, under owner confirmation all 176 are physically available in the UK; no larger quantity inferred.',
   image_ids=[x['id'] for x in chosen],image_urls=urls,source_revision=app['revision'])
 records.append(r)
 rows.append(['simple',sku,r['title'],1,'visible',desc,1,1,0,float(asking),'Living Room',', '.join(urls),
   'Material',r['material'],1,0,'Dimensions',r['dimensions'],1,0,'Colour',r['colour'],1,0])
save('furnitures-upload-plan.json',dict(checked_utc=now,app_revision=app['revision'],headers=headers,rows=rows,records=records,
 dashboard_before=0,expected_products=176,images_policy='Current selected photographs only, current primary first, up to two selected in-situ photographs, maximum six.',
 platform_caveats=['Native dashboard says Stripe payouts arrive in the next release; orders are recorded meanwhile.',
  'No per-product delivery rates or shop delivery settings exposed; header advertises free UK delivery over GBP500. Checkout must be checked.']))
print(json.dumps(dict(faire_records=len(faire),margin_valid=sum(x['margin_valid'] for x in faire),furnitures_records=len(records),images=sum(len(x['image_urls']) for x in records))))
