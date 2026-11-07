import hashlib, json, sys
from datetime import datetime, timezone
from pathlib import Path
from PIL import Image, ImageOps, ImageDraw

ROOT=Path('/Users/tprice/Documents/boldstone')
OUT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'catalogue-review'))
from delete_dropbox import connection

data=json.loads((OUT/'instagram-candidates.json').read_text())
records=[]
with connection(ROOT) as (db,_):
    for c in data:
        assert not c['prior_instagram_url'], 'Review prior publication before reuse'
        aid=c['photos']['primary_listing']['image_id']
        photo=next(i for i in c['photos']['listing']['images'] if i['id']==aid)
        assert photo['primary_eligible'] and not photo['withheld_reasons']
        meta=db.files_get_metadata(aid)
        assert meta.id==aid and meta.content_hash==photo['original']['dropbox_content_hash']
        suffix=Path(meta.name).suffix.lower()
        assert suffix in ('.jpg','.jpeg','.png') and meta.size<30_000_000
        target=OUT/'instagram-media'/(c['catalogue_id']+suffix)
        target.parent.mkdir(exist_ok=True)
        if target.exists():
            body=target.read_bytes()
        else:
            downloaded,response=db.files_download('rev:'+meta.rev)
            try: body=response.content
            finally: response.close()
            assert downloaded.id==aid
        digest=hashlib.sha256(b''.join(hashlib.sha256(body[i:i+4194304]).digest() for i in range(0,len(body),4194304))).hexdigest()
        assert len(body)==meta.size and digest==meta.content_hash
        target.write_bytes(body)
        with Image.open(target) as im:
            width,height=im.size
            im.verify()
        fields={f['key']:f['value'] for f in c['listing_fields']}
        records.append(dict(catalogue_id=c['catalogue_id'],title=c['retail_name'],
                            image_id=aid,image_name=meta.name,revision=meta.rev,content_hash=digest,
                            media_path=str(target.resolve()),sha256=hashlib.sha256(body).hexdigest(),
                            width=width,height=height,aspect_ratio=width/height,
                            sku=fields.get('Seller SKU'),source_description=fields['Description'],
                            status='PREPARED_NOT_PUBLISHED'))
        print(json.dumps(dict(title=c['retail_name'],width=width,height=height,bytes=len(body))),flush=True)
(OUT/'instagram-five-posts.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')
board=Image.new('RGB',(1500,420),'white')
draw=ImageDraw.Draw(board)
for i,r in enumerate(records):
    with Image.open(r['media_path']) as im:
        thumb=ImageOps.contain(im.convert('RGB'),(285,350))
        board.paste(thumb,(i*300+(300-thumb.width)//2,(350-thumb.height)//2))
    draw.text((i*300+8,360),r['title'][:35],fill='black')
    draw.text((i*300+8,382),str(r['width'])+' x '+str(r['height']),fill='black')
board.save(OUT/'instagram-review-contact-sheet.jpg')
