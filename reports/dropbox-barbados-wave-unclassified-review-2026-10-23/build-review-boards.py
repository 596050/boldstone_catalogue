import datetime,hashlib,json,math
from pathlib import Path
from PIL import Image,ImageOps,ImageDraw,ImageFont
root=Path('/Users/tprice/Documents/boldstone/reports/dropbox-barbados-wave-unclassified-review-2026-10-23')
b=json.loads((root/'current-baseline.json').read_text())
receipts=[e for i in range(2) for e in json.loads((root/f'download-receipts-batch-{i}.json').read_text())['entries']]
byid={r['id']:r for r in receipts};assert len(byid)==27
assert set(byid)=={e['file_id'] for e in b['selected_files']}
assert all(Path(r['local_path']).stat().st_size==r['size'] and hashlib.sha256(Path(r['local_path']).read_bytes()).hexdigest()==r['sha256'] for r in receipts)
ref=byid[b['approved_wave_reference_file_id']]
font=ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc',20);small=ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc',17)
boards=[];image_records=[];W=2000;tw=500;th=440;rh=370
def fit(c,p,box):
    with Image.open(p) as raw:
        raw.load();o=raw.getexif().get(274,1);im=ImageOps.exif_transpose(raw).convert('RGB');t=ImageOps.contain(im,(box[2]-box[0],box[3]-box[1]));c.paste(t,(box[0]+(box[2]-box[0]-t.width)//2,box[1]+(box[3]-box[1]-t.height)//2));return {'raw_dimensions':list(raw.size),'exif_orientation':o,'display_dimensions':list(im.size)}
def make(title,rows,name):
    c=Image.new('RGB',(W,rh+math.ceil(len(rows)/4)*th+25),'white');d=ImageDraw.Draw(c);d.text((12,6),title,font=font,fill='black');fit(c,ref['local_path'],(10,40,650,340));d.text((690,120),'Existing approved Barbados Wave reference / BC-BAR-WAVE',font=font,fill='black');d.text((690,165),'Full-frame review; source and physical provenance qualifications retained.',font=small,fill='black')
    for i,r in enumerate(rows):
        x=(i%4)*tw;y=rh+(i//4)*th;props=fit(c,r['local_path'],(x+7,y+7,x+tw-7,y+th-75));d.text((x+8,y+th-68),r['name'].split('__')[-1],font=font,fill='black');d.text((x+8,y+th-41),r['id'],font=small,fill='black');image_records.append({'file_id':r['id'],'name':r['name'],'board':name,'tile':i+1,**props})
    out=root/name;c.save(out,quality=94);boards.append({'path':str(out),'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'file_ids':[r['id'] for r in rows]})
for ident,title,stem in [('id:cnqzTNngPVsAAAAAAA51Jw','Barbados Moons and Waves Unclassified','unclassified-originals'),('id:cnqzTNngPVsAAAAAAAyh-w','Barbados Wave White','white-originals'),('id:cnqzTNngPVsAAAAAAAyjRg','Barbados Wave White In Situ','in-situ-originals')]:
    folder=next(e['path'] for e in b['complete_listing']['entries'] if e['file_id']==ident);rows=sorted([r for r in receipts if r['path'].rsplit('/',1)[0]==folder],key=lambda r:r['name'])
    for i in range(0,len(rows),12):make(title+' / full-frame originals',rows[i:i+12],f'{stem}-{i//12+1:02}.jpg')
out={'recorded_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'originals':27,'bytes':sum(r['size'] for r in receipts),'all_originals_size_content_hash_sha256_verified':True,'display_method':'Full frame contain-fit, EXIF orientation only; no crops or edits to originals.','boards':boards,'images':image_records,'native_mutations':0}
with (root/'review-board-index.json').open('x') as f:json.dump(out,f,indent=2);f.write('\n')
print(json.dumps({'originals':27,'bytes':out['bytes'],'boards':len(boards),'all_hashes_verified':True}))

