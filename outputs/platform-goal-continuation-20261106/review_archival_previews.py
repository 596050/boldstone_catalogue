"""Read bounded native thumbnails for analysis; retain no full originals."""
from pathlib import Path
from urllib.request import urlopen
from urllib.parse import urlencode
from PIL import Image,ImageOps,ImageDraw,ImageFont
import json,sys,io,math,textwrap

ROOT=Path('/Users/tprice/Documents/boldstone');OUT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'catalogue-review'))
from delete_dropbox import connection
from dropbox.files import PathOrLink,ThumbnailSize,ThumbnailMode

rows=json.loads((OUT/'archival-review-targets.json').read_text())
references=[('id:cnqzTNngPVsAAAAAAA6VmA','CURRENT Acanthus Frond Left Pewter'),('id:cnqzTNngPVsAAAAAAA7JVw','CURRENT Lava Moonshell II White'),('id:cnqzTNngPVsAAAAAAA7JVg','CURRENT Lava Moonshell I White'),('id:cnqzTNngPVsAAAAAAAylYA','CURRENT Lava Moonshell Corner Curve White')]
stem='archival-visual-review'
if len(sys.argv)>1:
    config=json.loads((OUT/sys.argv[1]).read_text());rows=config['archives'];references=config['references'];stem=Path(sys.argv[1]).stem
app=json.loads((OUT/'app-source.json').read_text());images={}
for p in app['products']:
    for kind in ['listing','in_situ','associated']:
        for im in p['photos'].get(kind,{}).get('images',[]):images[im['id']]=im
previews=[];index=[]
with connection(ROOT) as(db,_):
    for r in rows:
        result,response=db.files_get_thumbnail_v2(PathOrLink.path(r['id']),size=ThumbnailSize.w640h480,mode=ThumbnailMode.bestfit)
        try:data=response.content
        finally:response.close()
        assert len(data)<2_000_000 and result.file_metadata.id==r['id'] and result.file_metadata.content_hash==r['content_hash']
        previews.append(Image.open(io.BytesIO(data)).convert('RGB'))
        index.append(dict(number=len(index)+1,**r))
for aid,label in references:
    im=images[aid];q=urlencode(dict(id=aid,v=im['original']['dropbox_content_hash'],size='thumb'))
    with urlopen('http://127.0.0.1:8767/api/image?'+q,timeout=60) as response:data=response.read(2_000_001)
    assert len(data)<2_000_000
    previews.append(Image.open(io.BytesIO(data)).convert('RGB'));index.append(dict(number=len(index)+1,id=aid,name=label,reference=True))
canvas=Image.new('RGB',(1260,450*math.ceil(len(index)/3)),'#f4f3ef');draw=ImageDraw.Draw(canvas)
font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',17)
for n,(im,r) in enumerate(zip(previews,index)):
    px=(n%3)*420;py=(n//3)*450;thumb=ImageOps.contain(im,(400,340))
    canvas.paste(thumb,(px+(420-thumb.width)//2,py))
    label=f'{n+1}. '+r['name']
    draw.multiline_text((px+8,py+346),'\n'.join(textwrap.wrap(label,41)),font=font,fill='black',spacing=4)
canvas.save(OUT/(stem+'.jpg'),quality=90)
(OUT/(stem+'-index.json')).write_text(json.dumps(index,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(dict(native_archive_thumbnails=len(rows),current_references=len(references),full_originals_retained=0)))
