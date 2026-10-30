"""Contact sheets for inspecting unchanged source images; not listing-image derivatives."""
import json,hashlib,textwrap
from pathlib import Path
from PIL import Image,ImageOps,ImageDraw,ImageFont
H=Path(__file__).resolve().parent;read=lambda p:json.loads(Path(p).read_text());assets=read(H/'current-assets.json');queue=read(H/'photo-review-queue.json');out=H/'inspection';out.mkdir(exist_ok=True)
font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',15);head=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',24)
manifest=[]
def source(x):return next((x[k]for k in ['full','thumb']if x.get(k)and Path(x[k]).is_file()),None)
def make(cat,views,cols=3,rows=4,tw=500,th=410):
 for start in range(0,len(views),cols*rows):
  vs=views[start:start+cols*rows];canvas=Image.new('RGB',(cols*tw,rows*th+50),'#eff2ee');d=ImageDraw.Draw(canvas);d.text((12,10),cat+' / '+str(start//(cols*rows)+1),font=head,fill='#234530');saved=[]
  for j,v in enumerate(vs):
   x=assets[v['file_id']];src=source(x);left=j%cols*tw;top=j//cols*th+50
   if src:
    with Image.open(src)as im:
     im=ImageOps.exif_transpose(im).convert('RGB');size=im.size;im.thumbnail((tw-20,th-90));canvas.paste(im,(left+(tw-im.width)//2,top+(th-90-im.height)//2))
   else:size=None
   for line,s in enumerate(textwrap.wrap(v['label'],60)[:5]):d.text((left+10,top+th-83+line*16),s,font=font,fill='#213d29')
   saved.append({**v,'source_path':src,'source_sha256':hashlib.sha256(Path(src).read_bytes()).hexdigest()if src else None,'source_size':size})
  p=out/(cat+'-'+str(start//(cols*rows)+1).zfill(2)+'.jpg');canvas.save(p,quality=94);manifest.append({'category':cat,'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'views':saved})
ind=[x for x in queue if x['role']=='Individual']
make('individual-components',[{'file_id':x['source_reference']['file_id'],'label':str(x['sequence']).zfill(3)+' '+x['name']+' | '+x['status_before'],'task_id':x['task_id']}for x in ind])
make('context-subjects',[{'file_id':x['source_reference']['file_id'],'label':str(x['sequence']).zfill(3)+' '+x['name']+' | '+x['role'],'task_id':x['task_id']}for x in queue if x['role']!='Individual'])
if (H/'candidate-selection.json').exists():
 vs=read(H/'candidate-selection.json');make('additional-candidates',[{'file_id':x['file_id'],'label':x['label']+' '+x['family']+' / '+x['name']}for x in vs],cols=4,rows=5,tw=420,th=350)
(H/'inspection-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'plates':len(manifest),'views':sum(len(x['views'])for x in manifest)}))
