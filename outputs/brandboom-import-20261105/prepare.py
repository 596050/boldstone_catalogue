"""Freeze public Brandboom product data from the current catalogue."""
import hashlib,json,re,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path('/Users/tprice/Documents/boldstone');OUT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'catalogue-review'));sys.path.insert(0,str(ROOT/'catalogue-review/scripts'))
from channel_content import values,complete_description,marketplace_title,appearance,has_surface_effect
from import_saatchi_snapshot import Xlsx,column
from delete_dropbox import connection
read=lambda p:json.loads(p.read_text())
app=read(OUT/'app-source.json');products={p['id']:p for p in app['products']}
scope=read(ROOT/'outputs/saatchi-publication-20261104/176-publication-packet.json')['records']
pointer=read(OUT/'source-pointer-before.json')['current_app_review_workbook']
assert hashlib.sha256(Path(pointer['path']).read_bytes()).hexdigest()==pointer['sha256']
book=Xlsx(pointer['path']);headers={book.value('Wall Sculptures',a):re.sub(r'\d','',a) for a in book.cells['Wall Sculptures'] if re.fullmatch(r'[A-Z]+7',a)}
rows={book.value('Wall Sculptures',f'AA{r}'):r for r in range(8,189)}
public=read(ROOT/'outputs/faire-gumtree-20261104/current-public-images.json')
all_images={im['id']:im for b in scope for k in ['listing','in_situ'] for im in products[b['catalogue_id']]['photos'][k]['images']}
urls={};need=[]
for iid,im in all_images.items():
 expected=im.get('original',{}).get('dropbox_content_hash');p=public.get(iid)
 if p and p.get('dropbox_content_hash')==expected:urls[iid]=p['url']
 else:need.append((iid,expected))
temporary=[]
with connection(ROOT) as (db,_):
 for iid,expected in need:
  link=db.files_get_temporary_link(iid)
  assert link.metadata.id==iid and link.metadata.content_hash==expected
  urls[iid]=link.link
  temporary.append(dict(id=iid,hash=expected,created_utc=datetime.now(timezone.utc).isoformat(),scope='Transient source for native import only; verify Brandboom saved a permanent image asset'))
template=Xlsx(OUT/'native-template.xlsx');native_headers=[template.value('product import',column(i)+'1').strip() for i in range(1,18)]
native_headers+=['Image URL']
records=[];grid=[]
for binding in scope:
 p=products[binding['catalogue_id']];f=values(p);sku=f['Seller SKU'];assert sku==binding['sku'] and p['listing_decision']=='include'
 n=rows[p['id']];wholesale=book.value('Wall Sculptures',headers['wholesale_wholesale_price_gbp']+str(n));net=book.value('Wall Sculptures',headers['wholesale_net_after_fees_gbp']+str(n))
 retail=p['costing']['pricing']['marked_up_price'];assert net+.011>=retail and wholesale>0
 primary=p['photos']['primary_listing']['image_id'];listing=p['photos']['listing']['images'];situ=p['photos']['in_situ']['images']
 assert primary in {im['id'] for im in listing}
 ids=list(dict.fromkeys([primary]+[im['id'] for im in listing+situ]));images=[urls[iid] for iid in ids]
 assert len(images)==len(set(images)) and all(u.startswith('https://') and ',' not in u for u in images)
 description=complete_description(p,sku,dispatch_days=10)
 assert 'gypsum-based material' in description and 'Sally Price' in description and 'Quantity supplied: 1 ' in description
 assert not re.search(r'\bGFRC\b|\bRoyal Mail\b|\bLimited Edition\b',description,re.I)
 if has_surface_effect(p):assert 'surface-effect pattern will vary' in description
 title=marketplace_title(p,limit=120)
 # Each physical component/finish retains one unique Style ID and one option.
 # Omit unaligned indicative MSRP, unverified tariff/origin and exact stock counts.
 row=[sku,sku,'STANDARD','One sculpture',title,description,appearance(p),wholesale,None,'Home Decor','Wall Sculpture',None,None,None,None,1,None,','.join(images)]
 assert len(row)==len(native_headers)
 grid.append(row)
 records.append(dict(catalogue_id=p['id'],sku=sku,style_id=sku,title=title,wholesale_gbp=wholesale,catalogue_retail_gbp=retail,minimum_net_under_saved_wholesale_model_gbp=net,image_ids=ids,image_count=len(ids),source_hash=app['revision']))
assert len(grid)==len({r[0] for r in grid})==176
packet=dict(prepared_utc=datetime.now(timezone.utc).isoformat(),showroom_id='111089',showroom_url='https://manage.brandboom.com/products/s/111089',app_revision=app['revision'],target_records=176,headers=native_headers,rows=grid,records=records,temporary_image_sources=temporary,stock_basis='No exact stock quantity inferred; made-to-order copy retains ten working days. Inventory Count omitted.',pricing_basis='Current catalogue protected general-wholesaler unit prices; retailer margin/promotion/fee reserves are planning assumptions, not a claim about Brandboom fees. Retail MSRP omitted because indicative protected retail references are not aligned with the current website.',extra_app_included_records_held=['BSI-D886F539DD3E','BSI-65520F070145'],internal_costs_exported=False)
(OUT/'upload-plan.json').write_text(json.dumps(packet,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(dict(status='PREPARED',records=176,distinct_images=len(all_images),temporary_source_links=len(temporary),wholesale_min=min(r[7] for r in grid),wholesale_max=max(r[7] for r in grid))))
