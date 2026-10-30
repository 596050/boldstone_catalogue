import datetime,hashlib,json,math
from pathlib import Path
from PIL import Image,ImageOps,ImageDraw,ImageFont
root=Path('/Users/tprice/Documents/boldstone/reports/dropbox-leaf-form-individual-review-2026-10-23')
b=json.loads((root/'current-baseline.json').read_text())
entries=[r for i in range(3) for r in json.loads((root/f'download-receipts-batch-{i}.json').read_text())['entries']]
byid={r['id']:r for r in entries}
assert set(byid)=={r['file_id'] for r in b['selected_files']}
assert all(Path(r['local_path']).stat().st_size==r['size'] and hashlib.sha256(Path(r['local_path']).read_bytes()).hexdigest()==r['sha256'] for r in entries)
font=ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc',20)
small=ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc',17)
refs=[('LF1 / maker row36 / White050','leaf-form__leaf-form-white__050.jpg'),('LF2 / maker row37 / White001','leaf-form__leaf-form-white__001.png')]
W=2000;tw=500;th=430;rh=360
boards=[];image_records=[]
def paste_fit(canvas,p,box):
    with Image.open(p) as raw:
        raw.load();o=raw.getexif().get(274,1);im=ImageOps.exif_transpose(raw).convert('RGB')
        fit=ImageOps.contain(im,(box[2]-box[0],box[3]-box[1]))
        canvas.paste(fit,(box[0]+(box[2]-box[0]-fit.width)//2,box[1]+(box[3]-box[1]-fit.height)//2))
        return {'raw_dimensions':list(raw.size),'exif_orientation':o,'display_dimensions':list(im.size)}
def make(title,records,name):
    h=rh+math.ceil(len(records)/4)*th+45
    c=Image.new('RGB',(W,h),'white');d=ImageDraw.Draw(c);d.text((12,7),title,font=font,fill='black')
    for n,(label,fn) in enumerate(refs):
        x=n*1000;paste_fit(c,root/'originals'/fn,(x+10,40,x+470,325));d.text((x+490,130),label,font=font,fill='black')
    for i,r in enumerate(records):
        x=(i%4)*tw;y=rh+(i//4)*th
        props=paste_fit(c,r['local_path'],(x+8,y+8,x+tw-8,y+th-75))
        num=r['name'].split('__')[-1];d.text((x+8,y+th-68),num,font=font,fill='black');d.text((x+8,y+th-41),r['id'],font=small,fill='black')
        image_records.append({'file_id':r['id'],'name':r['name'],'board':name,'tile':i+1,**props})
    out=root/name;c.save(out,quality=94);boards.append({'path':str(out),'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'files':[r['id'] for r in records]})
white=sorted([r for r in entries if '__leaf-form-white__' in r['name']],key=lambda r:r['name'])
context=sorted([r for r in entries if '__leaf-form-white-in-situ__' in r['name']],key=lambda r:r['name'])
assert len(white)==60 and len(context)==3
for i in range(0,len(white),12): make('Leaf Form full-frame original review; reference strip LF1 / LF2',white[i:i+12],f'white-originals-{i//12+1:02}.jpg')
make('Leaf Form individual context originals; reference strip LF1 / LF2',context,'individual-context-originals.jpg')
for n,(label,fn) in enumerate(refs):
    c=Image.new('RGB',(1100,1100),'white');d=ImageDraw.Draw(c);d.text((10,8),label,font=font,fill='black');paste_fit(c,root/'originals'/fn,(0,50,1100,1100));c.save(root/f'numbered-reference-{n+1}.jpg',quality=95)
out={'recorded_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'files':63,'bytes':sum(r['size'] for r in entries),'hash_verification':'All 63 downloaded originals match current Dropbox size/content hash and local SHA256 readback.','display_method':'Full-frame contain-fit; EXIF orientation only; no crops or edits to originals.','boards':boards,'images':image_records,'native_mutations':0}
with (root/'review-board-index.json').open('x') as f:json.dump(out,f,indent=2);f.write('\n')
print(json.dumps({'files':63,'bytes':out['bytes'],'boards':len(boards),'all_hashes_verified':True,'exif_orientations':sorted(set(r['exif_orientation'] for r in image_records))}))

