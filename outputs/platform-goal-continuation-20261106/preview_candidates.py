"""Make a local contact sheet for visual review, from existing small previews."""
from pathlib import Path
from urllib.request import urlopen
from urllib.parse import urlencode
from concurrent.futures import ThreadPoolExecutor
from PIL import Image,ImageOps,ImageDraw,ImageFont
import json,io,textwrap,sys,math

OUT=Path(__file__).parent
rows=json.loads((OUT/'saatchi-candidate-associations.json').read_text())
ids=['id:cnqzTNngPVsAAAAAAAuexA','id:cnqzTNngPVsAAAAAAAuSKA','id:cnqzTNngPVsAAAAAAAs4wg','id:cnqzTNngPVsAAAAAAAuVqA','id:cnqzTNngPVsAAAAAAAubnQ','id:cnqzTNngPVsAAAAAAAuUWw','id:cnqzTNngPVsAAAAAAAuQAw','id:cnqzTNngPVsAAAAAAAuQDg','id:cnqzTNngPVsAAAAAAAyjMA']
images={r['image']['id']:r['image'] for r in rows}
labels={}
stem='original-review-contact-sheet'
if len(sys.argv)>1:
    config=json.loads((OUT/sys.argv[1]).read_text());ids=[r['id'] for r in config]
    labels={r['id']:r['label'] for r in config};stem=Path(sys.argv[1]).stem
def load(aid):
    p=images[aid];q=urlencode(dict(id=aid,v=p['original']['dropbox_content_hash'],size='thumb'))
    with urlopen('http://127.0.0.1:8767/api/image?'+q,timeout=60) as r:data=r.read()
    return Image.open(io.BytesIO(data)).convert('RGB')
canvas=Image.new('RGB',(1260,450*math.ceil(len(ids)/3)),'#f4f3ef');draw=ImageDraw.Draw(canvas)
font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',17)
with ThreadPoolExecutor(max_workers=2) as pool:
    for n,(aid,im) in enumerate(zip(ids,pool.map(load,ids))):
        x=(n%3)*420;y=(n//3)*450
        thumb=ImageOps.contain(im,(400,340));canvas.paste(thumb,(x+(420-thumb.width)//2,y))
        label=str(n+1)+'. '+labels.get(aid,images[aid]['name'])
        draw.multiline_text((x+8,y+346),'\n'.join(textwrap.wrap(label,41)),font=font,fill='black',spacing=4)
canvas.save(OUT/(stem+'.jpg'),quality=90)
(OUT/(stem+'-index.json')).write_text(json.dumps([dict(number=n+1,**images[aid]) for n,aid in enumerate(ids)],ensure_ascii=False,indent=2)+'\n')
print('Saved '+str(len(ids))+'-image visual review sheet')
