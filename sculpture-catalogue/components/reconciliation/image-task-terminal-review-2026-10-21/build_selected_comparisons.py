import hashlib,json,textwrap
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont,ImageOps
H=Path(__file__).resolve().parent;read=lambda p:json.loads(Path(p).read_text())
items={x['sequence']:x for x in read(H/'terminal-review-items.json')};assets=read(H/'current-assets.json')
candidates={x['label']:x for p in read(H/'candidate-plate-manifest.json')for x in p['views']if p['category']=='new-context'}
choices=[(37,None),(38,'NC032'),(46,'NC216'),(53,'NC369'),(75,'NC538'),(98,'NC671'),(111,'NC707'),(112,'NC731'),(123,'NC155')]
font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',17);result=[]
for start in range(0,len(choices),3):
 canvas=Image.new('RGB',(1600,1550),'#eef2ed');d=ImageDraw.Draw(canvas);vs=[]
 for row,(seq,label)in enumerate(choices[start:start+3]):
  x=items[seq];fid=candidates[label]['file_id']if label else x['prior_action']['reference']['file_id']
  for col,(image_id,caption)in enumerate([(x['primary_reference']['file_id'],'PRIMARY '+x['name']),(fid,(label or'RECLASSIFY CURRENT')+' '+x['requested_role'])]):
   a=assets[image_id];src=next(a[k]for k in ['full','thumb']if a.get(k)and Path(a[k]).is_file());left=col*800;top=row*510
   with Image.open(src)as im:
    im=ImageOps.exif_transpose(im).convert('RGB');im.thumbnail((780,425));canvas.paste(im,(left+(800-im.width)//2,top+(425-im.height)//2))
   for n,line in enumerate(textwrap.wrap(str(seq)+' '+caption,82)[:3]):d.text((left+10,top+430+n*20),line,font=font,fill='#203425')
   vs.append({'sequence':seq,'file_id':image_id,'label':label,'local_path':src,'caption':caption})
 p=H/'plates'/('selected-context-pairs-'+str(start//3+1).zfill(2)+'.jpg');canvas.save(p,quality=95);result.append({'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'views':vs})
(H/'selected-context-comparison-manifest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print('Prepared nine original-source comparisons in three diagnostic plates')
