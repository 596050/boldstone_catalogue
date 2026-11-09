"""Freeze five additional product posts per channel; no publication."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import sys
from urllib.parse import urlencode
from PIL import Image
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).parent
sys.path[:0]=[str(ROOT/'catalogue-review'),str(ROOT/'catalogue-review/scripts')]
from channel_content import values,finish_retail_name,has_surface_effect
from delete_dropbox import connection
load=lambda name:json.loads((OUT/name).read_text())
spec={p['id']:p for p in load('app-specifications.json')['products']};coverage=load('app-coverage.json')['products'];master=load('master-platform-values.json');metadata=load('current-selected-photo-metadata.json')
ids=['BSI-489226D6FF87','BSI-3625008B0B78','BSI-987E02C8748D','BSI-96174B219ECA','BSI-1A7497B69626']
media=OUT/'social-media';media.mkdir(exist_ok=True)
records=[]
with connection(ROOT) as (db,_):
    for pid in ids:
        p=spec[pid];v=values(p);m=master[pid];assert not(m.get('instagram_post_url') or m.get('linkedin_post_url'))
        iid=coverage[pid]['primary_listing']['image_id'];assert iid in coverage[pid]['listing']['image_ids']
        expected=metadata[iid]['original']['dropbox_content_hash'];native=db.files_get_metadata(iid)
        assert native.id==iid and native.content_hash==expected and native.size<25_000_000
        dest=media/(pid+Path(native.name).suffix.lower())
        if not dest.exists():
            readback,response=db.files_download('rev:'+native.rev)
            try:body=response.content
            finally:response.close()
            assert readback.id==iid and readback.rev==native.rev
            content=hashlib.sha256(b''.join(hashlib.sha256(body[i:i+4194304]).digest() for i in range(0,len(body),4194304))).hexdigest()
            assert content==expected;dest.write_bytes(body)
        with Image.open(dest) as image:width,height=image.size
        records.append(dict(catalogue_id=pid,sku=v['Seller SKU'],title=finish_retail_name(p),family=p['family'],
            price_gbp=p['costing']['pricing']['marked_up_price'],design_copy=v['Description'],dimensions=v['Dimensions / depth'],
            media_path=str(dest),sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),image_id=iid,dropbox_revision=native.rev,dropbox_content_hash=expected,width=width,height=height,
            website_url=m['pinterest_link'],commerce_variant_id=m['pinterest_id'],surface_effect=has_surface_effect(p),
            tracked_urls={channel:m['pinterest_link']+'?'+urlencode(dict(utm_source=channel,utm_medium='social',utm_campaign='wall_sculptures_20261108_evening',utm_content=v['Seller SKU'])) for channel in ['instagram','linkedin','facebook']},
            status='PREPARED_NOT_PUBLISHED'))
(OUT/'social-five-products.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'products':len(records),'media':[{'title':p['title'],'dimensions':[p['width'],p['height']],'bytes':Path(p['media_path']).stat().st_size} for p in records]}))
