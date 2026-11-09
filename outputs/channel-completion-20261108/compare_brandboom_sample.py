"""Compare public rendered photo assets; never mutate or guess platform media IDs."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib, io, json, urllib.request
from PIL import Image, ImageOps, ImageDraw

OUT=Path(__file__).parent
load=lambda name:json.loads((OUT/name).read_text())
native=load('brandboom-sample-image-inventory.json')
plan=load('brandboom-restore-plan.json')
product=next(p for p in plan['records'] if p['sku']==native['sku'])
urls=load('current-public-images-verified.json')
items=[dict(kind='expected',key=i,url=urls[i]['url']) for i in product['image_ids']]
items += [dict(kind='native',key=i['data-media-id'],url=i['data-main-src']) for i in native['images']]

def fetch(item):
    req=urllib.request.Request(item['url'],headers={'User-Agent':'BoldstoneCatalogueImageAudit/1.0'})
    with urllib.request.urlopen(req,timeout=60) as r:
        assert r.headers.get_content_type().startswith('image/')
        body=r.read(40_000_001);assert len(body)<=40_000_000
    im=ImageOps.exif_transpose(Image.open(io.BytesIO(body)));im.load()
    white=Image.new('RGB',im.size,'white')
    if im.mode=='RGBA':white.paste(im,mask=im.getchannel('A'))
    else:white.paste(im.convert('RGB'))
    small=white.resize((48,48),Image.Resampling.LANCZOS)
    thumb=white.copy();thumb.thumbnail((160,160))
    return {**item,'sha256':hashlib.sha256(body).hexdigest(),'dimensions':list(im.size),'pixels':list(small.getdata()),'thumb':thumb}

with ThreadPoolExecutor(max_workers=3) as pool:rows=list(pool.map(fetch,items))
expected=[x for x in rows if x['kind']=='expected'];actual=[x for x in rows if x['kind']=='native']
def distance(a,b):return sum(abs(x-y) for p,q in zip(a['pixels'],b['pixels']) for x,y in zip(p,q))/(48*48*3)
results=[]
canvas=Image.new('RGB',(800,200*len(actual)),'white');draw=ImageDraw.Draw(canvas)
for index,a in enumerate(actual):
    scores=sorted((distance(a,b),b['key'],b) for b in expected)
    best=scores[0];second=scores[1]
    results.append(dict(native_media_id=a['key'],native_url=a['url'],native_sha256=a['sha256'],best_source_id=best[1],mean_absolute_pixel_difference=round(best[0],4),second_source_id=second[1],second_difference=round(second[0],4),gap=round(second[0]-best[0],4)))
    y=index*200
    canvas.paste(a['thumb'],(10,y+30));canvas.paste(best[2]['thumb'],(210,y+30));canvas.paste(second[2]['thumb'],(410,y+30))
    draw.text((10,y+8),f"Native {a['key']}",fill='black');draw.text((210,y+8),f"Closest selected: {best[0]:.3f}",fill='black');draw.text((410,y+8),f"Runner-up: {second[0]:.3f}",fill='black')
    draw.text((580,y+45),best[1][-16:],fill='black')
canvas.save(OUT/'brandboom-sample-photo-comparison.jpg',quality=88)
duplicates={i:[r['native_media_id'] for r in results if r['best_source_id']==i] for i in product['image_ids']}
result=dict(checked_at=datetime.now(timezone.utc).isoformat(),sku=native['sku'],expected_count=len(expected),native_count=len(actual),comparisons=results,
    best_match_duplicate_candidates={k:v for k,v in duplicates.items() if len(v)>1},
    selected_photos_without_a_best_match=[k for k,v in duplicates.items() if not v],
    qualification='Rendered pixels are comparative evidence, not original-byte identity. No media or association removed; visual review required for ambiguous matches.')
(OUT/'brandboom-sample-photo-comparison.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='comparisons'}))
print([(r['native_media_id'],r['mean_absolute_pixel_difference'],r['gap']) for r in results])
