import json,math,hashlib
from pathlib import Path
from datetime import datetime,timezone
from PIL import Image,ImageOps,ImageDraw,ImageFont
b=Path(__file__).resolve().parent
base=json.loads((b/'current-baseline.json').read_text())
receipts=json.loads((b/'download-receipts.json').read_text())
byid={x['file_id']:x for x in receipts['entries']}
assert len(byid)==27 and sum(x['size'] for x in byid.values())==41524314
for r in byid.values():
 data=Path(r['local_path']).read_bytes()
 assert len(data)==r['size'] and hashlib.sha256(data).hexdigest()==r['sha256']
fonts=['/System/Library/Fonts/Supplemental/Arial.ttf','/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf']
fp=next((x for x in fonts if Path(x).exists()),None)
font=ImageFont.truetype(fp,18) if fp else ImageFont.load_default()
head=ImageFont.truetype(fp,24) if fp else ImageFont.load_default()
primary={o['file_id']:o['visual_review_id'] for o in base['catalogue_source']['options']}
context={o['context_file_id']:o['visual_review_id'] for o in base['catalogue_source']['options'] if o.get('context_file_id')}
groups=[('marbled-1-2-originals.jpg',[0,1],3),('marbled-3-4-originals.jpg',[2,4],4),('scene-study-originals.jpg',[3,5],5),('yellow-grey-originals.jpg',[6],2)]
boards=[];images=[]
for name,indices,cols in groups:
 items=[]
 for i in indices:
  folder=base['target_folders'][i]
  items.extend((folder,f) for f in sorted(folder['files'],key=lambda x:x['name']))
 w,h,top=500,410,75
 canvas=Image.new('RGB',(cols*w+20,math.ceil(len(items)/cols)*h+top+15),'white');draw=ImageDraw.Draw(canvas)
 draw.text((10,8),name.replace('-',' '),font=head,fill='black')
 draw.text((10,40),'Full-frame originals; EXIF orientation only. Source roles retained.',font=font,fill='black')
 for n,(folder,f) in enumerate(items):
  x=10+(n%cols)*w;y=top+(n//cols)*h;r=byid[f['file_id']]
  with Image.open(r['local_path']) as raw:
   size=raw.size;im=ImageOps.exif_transpose(raw).convert('RGB');im.thumbnail((w-14,h-80));canvas.paste(im,(x+(w-14-im.width)//2,y+(h-80-im.height)//2))
  draw.text((x,y+h-72),folder['old_name'],font=font,fill='black')
  tag=f['name'].rsplit('__',1)[-1]+' / '+f['file_id'][-8:]
  if f['file_id'] in primary:tag+=' / Primary '+primary[f['file_id']]
  if f['file_id'] in context:tag+=' / Context '+context[f['file_id']]
  draw.text((x,y+h-45),tag,font=font,fill='black')
  images.append({'file_id':f['file_id'],'name':f['name'],'folder_id':folder['folder_id'],'board':name,'tile':n+1,'original_dimensions':size})
 path=b/name;canvas.save(path,quality=94)
 boards.append({'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'images':len(items)})
index={'recorded_utc':datetime.now(timezone.utc).isoformat(),'boards':boards,'images':images,'originals':27,'bytes':41524314,'all_original_size_and_dropbox_content_hash_verified':True,'local_sha256_reverified':True,'display_method':'Full-frame contain-fit with EXIF orientation only; originals unmodified.','native_mutations':0}
(b/'review-board-index.json').write_text(json.dumps(index,indent=2)+'\n')
print(json.dumps({'boards':boards,'originals':27,'bytes':41524314}))
