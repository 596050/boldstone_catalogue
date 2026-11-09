"""Bind ten new LinkedIn posts to current component records and original photographs."""
import hashlib
import json
import sys
from pathlib import Path
from urllib.parse import urlencode
from PIL import Image,ImageOps,ImageDraw

ROOT=Path('/Users/tprice/Documents/boldstone');OUT=Path(__file__).parent
sys.path[:0]=[str(ROOT/'catalogue-review'),str(ROOT/'catalogue-review/scripts')]
from channel_content import values,finish_retail_name
from delete_dropbox import connection

load=lambda p:json.loads(Path(p).read_text())
products={p['id']:p for p in load(OUT/'app-specifications.json')['products']}
coverage=load(OUT/'app-coverage.json')['products']
google={p['catalogue_id']:p for p in load(ROOT/'outputs/catalogue-channel-imports-20261107/google-source-reconciliation.json')['wall_sculpture_matches_detail']}
instagram=load(ROOT/'outputs/instagram-marketplace-next-channels-20261107-1324/instagram-five-posts.json')
extra=['BSI-59530C6155C2','BSI-624D16148726','BSI-5181D32AA24F','BSI-21DCD11AD8C6','BSI-3C849B547D50']
ids=[p['catalogue_id'] for p in instagram]+extra
assert len(ids)==len(set(ids))==10
(OUT/'media').mkdir(exist_ok=True)
records=[]
with connection(ROOT) as (db,_):
 for pid in ids:
  p=products[pid];f=values(p);c=coverage[pid]
  prior=next((q for q in instagram if q['catalogue_id']==pid),None)
  if prior:
   image_id=prior['image_id'];path=Path(prior['media_path'])
   assert image_id in set(c['listing']['image_ids']+c['in_situ']['image_ids']),pid
   assert hashlib.sha256(path.read_bytes()).hexdigest()==prior['sha256']
  else:
   image_id=p['photos']['primary_listing']['image_id']
   assert image_id and image_id in c['listing']['image_ids']
   path=None
  meta=db.files_get_metadata(image_id)
  assert meta.id==image_id and meta.size<25000000
  if prior:
   assert meta.content_hash==prior['content_hash'] and meta.rev==prior['revision']
  else:
   path=OUT/'media'/(pid+Path(meta.name).suffix.lower())
   expected=meta.content_hash
   if not path.exists():
    downloaded,response=db.files_download('rev:'+meta.rev)
    try:body=response.content
    finally:response.close()
    assert downloaded.id==meta.id
    content_hash=hashlib.sha256(b''.join(hashlib.sha256(body[i:i+4194304]).digest() for i in range(0,len(body),4194304))).hexdigest()
    assert content_hash==expected
    path.write_bytes(body)
  with Image.open(path) as im:width,height=im.size
  url=google[pid]['website_url']
  records.append(dict(catalogue_id=pid,sku=f['Seller SKU'],title=finish_retail_name(p),family=p['family'],fields=f,
     media_path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),image_id=image_id,
     dropbox_revision=meta.rev,dropbox_content_hash=meta.content_hash,width=width,height=height,
     website_url=url,tracked_url=url+'?'+urlencode(dict(utm_source='linkedin',utm_medium='social',utm_campaign='wall_sculptures_20261108',utm_content=f['Seller SKU'])),
     status='PREPARED_NOT_PUBLISHED'))
(OUT/'linkedin-ten-posts.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')
# A contact sheet is a review aid, never an upload or alteration of the originals.
sheet=Image.new('RGB',(1200,1050),'white');draw=ImageDraw.Draw(sheet)
for i,p in enumerate(records):
 with Image.open(p['media_path']) as im:
  tile=ImageOps.contain(im.convert('RGB'),(220,410))
  x=(i%5)*240+(240-tile.width)//2;y=(i//5)*525
  sheet.paste(tile,(x,y));draw.text(((i%5)*240+8,y+420),p['title'][:30],fill='black')
  draw.text(((i%5)*240+8,y+443),p['sku'][:30],fill='black')
sheet.save(OUT/'linkedin-ten-review.jpg',quality=88)
print(json.dumps(dict(records=len(records),reused_reviewed_media=5,downloaded_selected_originals=5,verified_current_dropbox_identities=10)))
