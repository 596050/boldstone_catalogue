"""Fetch only the 18 selected originals missing from the website image mapping."""
from pathlib import Path
from datetime import datetime, timezone
import concurrent.futures, hashlib, io, json, urllib.request
from PIL import Image

OUT=Path(__file__).parent
load=lambda name:json.loads((OUT/name).read_text())
comparison=load('website-selected-photo-comparison.json')
metadata=load('current-selected-photo-metadata.json')
plan=load('brandboom-restore-plan.json')
urls={}
for record,row in zip(plan['records'],plan['rows']):
    links=row[17].split(',')
    assert len(links)==len(record['image_ids'])
    for iid,url in zip(record['image_ids'],links):
        if iid in urls:assert urls[iid]==url
        urls[iid]=url
ids=sorted({iid for record in comparison['products'] for iid in record['unmapped_current_photos']})
assert len(ids)==18
folder=OUT/'website-new-media';folder.mkdir(exist_ok=True)
def get(iid):
    source=metadata[iid];expected=source['original']['dropbox_content_hash']
    hint='.png' if source['name'].lower().endswith('.png') else '.jpg'
    cached=folder/('boldstone-'+expected[:16]+hint)
    body=cached.read_bytes() if cached.exists() else urllib.request.urlopen(urls[iid],timeout=60).read()
    assert len(body)==source['original']['bytes']
    actual=hashlib.sha256(b''.join(hashlib.sha256(body[n:n+4194304]).digest() for n in range(0,len(body),4194304))).hexdigest()
    assert actual==expected,(iid,actual,expected)
    with Image.open(io.BytesIO(body)) as image:
        width,height=image.size
        image_format=image.format
        # MPO is a JPEG container; retain its original bytes, never re-encode.
        extension={'JPEG':'.jpg','MPO':'.jpg','PNG':'.png'}[image_format]
        image.verify()
    path=folder/('boldstone-'+actual[:16]+extension)
    if path.exists():assert path.read_bytes()==body
    else:path.write_bytes(body)
    return dict(id=iid,name=source['name'],path=str(path),width=width,height=height,format=image_format,bytes=len(body),sha256=hashlib.sha256(body).hexdigest(),dropbox_content_hash=expected,revision=source['provenance']['revision'])
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:photos=list(pool.map(get,ids))
by_id={p['id']:p for p in photos}
products=[]
for record in comparison['count_differences']:
    assert len(record['unmapped_current_photos'])==1
    products.append({**record,'new_photo':by_id[record['unmapped_current_photos'][0]],'operation':'Append one currently selected photograph; preserve existing images, primary, product ID and SKU'})
(OUT/'website-photo-append-plan.json').write_text(json.dumps(dict(prepared_utc=datetime.now(timezone.utc).isoformat(),photos=photos,products=products),indent=2)+'\n')
print(json.dumps(dict(verified_originals=len(photos),placements=len(products),bytes=sum(p['bytes'] for p in photos))))
