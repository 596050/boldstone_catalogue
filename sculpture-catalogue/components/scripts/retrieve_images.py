import json
from pathlib import Path
import numpy as np
from PIL import Image,ImageOps,ImageDraw
root=Path(__file__).resolve().parents[1];ev=root/'evidence';d=json.loads((ev/'evidence_index.json').read_text());offers=json.loads((ev/'offer_review_index.json').read_text())
def feat(p):
    with Image.open(p) as im:
        im=ImageOps.exif_transpose(im).convert('RGB');ratio=im.width/im.height
        g=np.asarray(im.resize((32,32)).convert('L'),dtype=np.float32)/255;g=(g-g.mean())/(g.std()+.1)
        c=np.asarray(im.resize((8,8)),dtype=np.float32).ravel()/255
    return np.concatenate([g.ravel()*.8,c*.4,np.array([np.log(ratio)],np.float32)*7])
assets=[a for a in d['assets'] if a['thumb']];X=np.stack([feat(a['thumb']) for a in assets]);results=[]
for offer in offers:
    im=next((i for i in offer['images'] if 'path'in i),None)
    if not im:continue
    scores=((X-feat(im['path']))**2).sum(axis=1);ix=np.argsort(scores)[:4]
    results.append(dict(ref=offer['ref'],pid=offer['pid'],title=offer['title'],source_image=im,candidates=[dict(asset_id=assets[i]['id'],group=assets[i]['group'],folder_id=assets[i]['folder_id'],path=assets[i]['path'],thumb=assets[i]['thumb'],score=float(scores[i])) for i in ix]))
(ev/'image_retrieval_candidates.json').write_text(json.dumps(results,ensure_ascii=False))
for start in range(0,len(results),12):
    rows=results[start:start+12];board=Image.new('RGB',(1440,len(rows)*156),'white');draw=ImageDraw.Draw(board)
    for i,r in enumerate(rows):
        y=i*156
        for j,p in enumerate([r['source_image']['thumb']]+[a['thumb'] for a in r['candidates']]):
            with Image.open(p) as im:
                pic=ImageOps.contain(im.convert('RGB'),(220,122));board.paste(pic,(j*280+(220-pic.width)//2,y))
        draw.text((0,y+125),r['ref']+' '+r['title'][:41],fill='black')
        for j,a in enumerate(r['candidates']):draw.text(((j+1)*280,y+125),a['group'][:35]+'\n'+str(round(a['score'],2))+' '+a['asset_id'][-7:],fill='black')
    board.save(root/'reviews'/f'candidate-pairs-{start//12+1:02d}.jpg',quality=94)
print(json.dumps(dict(offers=len(results),assets=len(assets))))
