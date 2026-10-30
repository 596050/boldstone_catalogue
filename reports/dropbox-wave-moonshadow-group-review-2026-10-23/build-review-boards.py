import datetime,hashlib,json,math
from pathlib import Path
from PIL import Image,ImageOps,ImageDraw,ImageFont
root=Path('/Users/tprice/Documents/boldstone/reports/dropbox-wave-moonshadow-group-review-2026-10-23')
b=json.loads((root/'current-baseline.json').read_text())
receipts=[e for i in range(2) for e in json.loads((root/f'download-receipts-batch-{i}.json').read_text())['entries']]
byid={e['id']:e for e in receipts};assert len(byid)==44
assert set(byid)=={e['file_id'] for e in b['selected_files']}
assert all(Path(e['local_path']).stat().st_size==e['size'] and hashlib.sha256(Path(e['local_path']).read_bytes()).hexdigest()==e['sha256'] for e in receipts)
font=ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc',20);small=ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc',17)
refs=[('1 = Wave','id:cnqzTNngPVsAAAAAAAud2w'),('2 = Moonshadow','id:cnqzTNngPVsAAAAAAAudwg')]
W=2000;tw=500;th=440;rh=350;boards=[];images=[]
def fit(c,p,box):
    with Image.open(p) as raw:
        raw.load();orientation=raw.getexif().get(274,1);im=ImageOps.exif_transpose(raw).convert('RGB')
        t=ImageOps.contain(im,(box[2]-box[0],box[3]-box[1]));c.paste(t,(box[0]+(box[2]-box[0]-t.width)//2,box[1]+(box[3]-box[1]-t.height)//2))
        return {'raw_dimensions':list(raw.size),'exif_orientation':orientation,'display_dimensions':list(im.size)}
def make(title,rows,name):
    c=Image.new('RGB',(W,rh+math.ceil(len(rows)/4)*th+20),'white');d=ImageDraw.Draw(c);d.text((12,6),title,font=font,fill='black')
    for j,(label,ident) in enumerate(refs):
        x=j*1000;fit(c,byid[ident]['local_path'],(x+10,38,x+470,325));d.text((x+490,130),label,font=font,fill='black')
    for i,r in enumerate(rows):
        x=(i%4)*tw;y=rh+(i//4)*th;props=fit(c,r['local_path'],(x+7,y+7,x+tw-7,y+th-75))
        d.text((x+8,y+th-68),r['name'].split('__')[-1],font=font,fill='black');d.text((x+8,y+th-41),r['id'],font=small,fill='black')
        images.append({'file_id':r['id'],'name':r['name'],'board':name,'tile':i+1,**props})
    out=root/name;c.save(out,quality=94);boards.append({'path':str(out),'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'file_ids':[r['id'] for r in rows]})
for ident,label,stem in [('id:cnqzTNngPVsAAAAAAAyjHA','Wave Between Moonshadow White','white-groups'),('id:cnqzTNngPVsAAAAAAAyjHQ','Wave Between Moonshadow White Scene Views','scene-groups'),('id:cnqzTNngPVsAAAAAAAyjHg','Existing numbered group In Situ','in-situ-groups')]:
    folder=next(e['path'] for e in b['complete_listing']['entries'] if e['file_id']==ident)
    rows=sorted([r for r in receipts if r['path'].rsplit('/',1)[0]==folder],key=lambda e:e['name'])
    for i in range(0,len(rows),12):make(label+'; full-frame originals',rows[i:i+12],f'{stem}-{i//12+1:02}.jpg')
out={'recorded_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'downloaded_originals':44,'group_images':42,'numbered_references':2,'bytes':sum(e['size'] for e in receipts),'hash_verification':'All44 current originals size/content-hash matched and local SHA256 verified.','display_method':'Full-frame contain-fit, EXIF orientation only; no crops or edits to originals.','boards':boards,'images':images,'native_mutations':0}
with (root/'review-board-index.json').open('x') as f:json.dump(out,f,indent=2);f.write('\n')
print(json.dumps({'downloaded_originals':44,'group_images':42,'boards':len(boards),'bytes':out['bytes'],'all_hashes_verified':True}))

