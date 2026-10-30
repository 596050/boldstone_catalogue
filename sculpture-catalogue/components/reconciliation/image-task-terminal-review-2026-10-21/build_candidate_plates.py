"""Additional bounded context search plates, excluding prior review queues."""
import hashlib,json,textwrap
from pathlib import Path
from PIL import Image,ImageOps,ImageDraw,ImageFont
HERE=Path(__file__).resolve().parent;read=lambda p:json.loads(Path(p).read_text());font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',13);head=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',22)
result=[]
for category,filename,cols,rows in [('new-context','context-candidates-not-in-prior-queues.json',4,8),('fountain-finish','fountain-finish-candidates.json',4,4)]:
 assets=sorted(read(HERE/filename),key=lambda x:(x['family'],x['path']));views=[]
 for i,x in enumerate(assets,1):views.append({'label':('NC'if category=='new-context'else'FP')+str(i).zfill(3),'file_id':x['file_id'],'family':x['family'],'name':x['name'],'path':x['path'],'local_path':x.get('full')or x.get('thumb')or''})
 for start in range(0,len(views),cols*rows):
  tilew=400;tileh=285;canvas=Image.new('RGB',(tilew*cols,tileh*rows+50),'#eef2ed');draw=ImageDraw.Draw(canvas);draw.text((12,10),category+' | '+str(start//(cols*rows)+1),font=head,fill='#263c2c')
  chunk=views[start:start+cols*rows]
  for j,x in enumerate(chunk):
   left=(j%cols)*tilew+7;top=(j//cols)*tileh+50;src=x['local_path']
   if src and Path(src).exists():
    with Image.open(src)as im:
     im=ImageOps.exif_transpose(im).convert('RGB');im.thumbnail((386,215));canvas.paste(im,(left+(386-im.width)//2,top+(215-im.height)//2))
   caption=x['label']+' '+x['family']+' / '+x['name']
   for line,text in enumerate(textwrap.wrap(caption,52)[:4]):draw.text((left,top+216+line*15),text,font=font,fill='#203425')
  p=HERE/'plates'/(category+'-'+str(start//(cols*rows)+1).zfill(2)+'.jpg');canvas.save(p,quality=92);result.append({'category':category,'path':str(p),'views':chunk,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
(HERE/'candidate-plate-manifest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'plates':len(result),'context_candidates':sum(len(x['views'])for x in result if x['category']=='new-context'),'fountain_finish_candidates':sum(len(x['views'])for x in result if x['category']=='fountain-finish')}))
