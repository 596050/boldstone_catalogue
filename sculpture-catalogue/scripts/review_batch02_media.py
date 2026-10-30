import json
from pathlib import Path
from PIL import Image,ImageOps,ImageDraw

project=Path(__file__).resolve().parents[1];ev=project/'evidence'
inventory=json.loads((ev/'wall_inventory_2026-10-16.json').read_text())
cache=json.loads((ev/'image_review_cache_index.json').read_text())
records=[]
for r in sorted(inventory['entries'],key=lambda r:r['path'].casefold()):
    if r['object_type']=='file' and '/Acanthus/' in r['path']:
        c=cache[r['file_id']];assert c['hash_verified']
        records.append(dict(file_id=r['file_id'],group=r['path'].split('/')[-2],name=r['name'],path=r['path'],local_path=c['local_path'],sha256=c['sha256'],content_hash=c['content_hash'],hash_verified=True))
(ev/'batch02_media.json').write_text(json.dumps(records,ensure_ascii=False))
for start in range(0,len(records),16):
    chunk=records[start:start+16];board=Image.new('RGB',(1440,((len(chunk)+3)//4)*310),'white');draw=ImageDraw.Draw(board)
    for i,r in enumerate(chunk):
        x=i%4*360;y=i//4*310
        with Image.open(r['local_path']) as src:
            im=ImageOps.contain(ImageOps.exif_transpose(src).convert('RGB'),(350,225));board.paste(im,(x+(360-im.width)//2,y))
        draw.multiline_text((x+4,y+229),f'{start+i+1}. {r["group"]}\n{r["name"][-48:]}\n{r["file_id"]}',fill='black',spacing=3)
    board.save(project/'reviews'/f'batch02-contact-{start//16+1}.jpg',quality=94)

selection=json.loads((ev/'batch02_and_match_selection.json').read_text())['candidates']
for start in range(0,len(selection),8):
    chunk=selection[start:start+8];board=Image.new('RGB',(1100,len(chunk)*245),'white');draw=ImageDraw.Draw(board)
    for i,r in enumerate(chunk):
        c=cache[r['candidate']['id']];assert c['hash_verified']
        for j,p in enumerate([r['image_path'],c['local_path']]):
            with Image.open(p) as src:
                im=ImageOps.contain(ImageOps.exif_transpose(src).convert('RGB'),(530,182));board.paste(im,(j*550+(550-im.width)//2,i*245))
        draw.multiline_text((8,i*245+184),r['title']+'\nSS image '+str(r['image_order']),fill='black',spacing=3)
        draw.multiline_text((558,i*245+184),r['candidate']['path'].split('/')[-2]+'\nCURRENT CONTENT-HASH VERIFIED\n'+r['candidate']['id'],fill='black',spacing=3)
    board.save(project/'reviews'/f'verified-established-{start//8+1}.jpg',quality=94)
print(json.dumps(dict(batch02_files=len(records),current_offer_comparisons=len(selection))))
