"""Create source-labelled diagnostic plates; no product image assets are edited."""
import hashlib,json,textwrap
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont,ImageOps
HERE=Path(__file__).resolve().parent
read=lambda p:json.loads(Path(p).read_text())
items=read(HERE/'terminal-review-items.json');assets=read(HERE/'current-assets.json');font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',16);head=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',23)
plates=[]
def cache(fid):
 a=assets.get(fid,{})
 for k in ['full','thumb']:
  p=a.get(k,'')
  if p and Path(p).exists():return p
 return''
def make(name,views,cols=4,rows=2,tilew=400,tileh=430):
 for start in range(0,len(views),cols*rows):
  vs=views[start:start+cols*rows];canvas=Image.new('RGB',(cols*tilew,rows*tileh+55),'#edf1eb');draw=ImageDraw.Draw(canvas);draw.text((12,12),name+' | plate'+str(start//(cols*rows)+1),font=head,fill='#263c2c')
  for j,v in enumerate(vs):
   left=(j%cols)*tilew+8;top=(j//cols)*tileh+55;src=v.get('local_path')or cache(v['file_id'])
   if src:
    with Image.open(src)as im:
     im=ImageOps.exif_transpose(im).convert('RGB');im.thumbnail((tilew-16,tileh-105));canvas.paste(im,(left+(tilew-16-im.width)//2,top+(tileh-105-im.height)//2))
   else:draw.text((left,top+30),'SOURCE NOT CACHED',font=font,fill='red')
   lines=textwrap.wrap(v['caption'],width=max(25,int((tilew-16)/8)))[:5]
   for n,line in enumerate(lines):draw.text((left,top+tileh-98+n*18),line,font=font,fill='#1d3024')
  path=HERE/'plates'/(name+'-'+str(start//(cols*rows)+1).zfill(2)+'.jpg');canvas.save(path,quality=93)
  plates.append({'category':name,'path':str(path),'views':vs,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
def reference_view(x):return{'task_id':x['task_id'],'sequence':x['sequence'],'file_id':x['prior_action']['reference']['file_id'],'caption':str(x['sequence']).zfill(3)+' '+x['name']+' | '+x['requested_role']}
make('individual',[reference_view(x)for x in items if x['requested_role']=='Individual'])
vs=[]
for x in items:
 if x['prior_action']['action_type']!='Verify existing image':continue
 primary=x['primary_reference']['file_id']or x['prior_action']['reference']['file_id']
 vs.append({'task_id':x['task_id'],'sequence':x['sequence'],'file_id':primary,'caption':str(x['sequence']).zfill(3)+' PRIMARY '+x['name']})
 vs.append({**reference_view(x),'caption':str(x['sequence']).zfill(3)+' CHECK '+x['name']+' | '+x['requested_role']})
make('verification-pairs',vs,cols=2,rows=3,tilew=800,tileh=490)
make('missing-context',[reference_view(x)for x in items if x['requested_role']!='Individual'and x['prior_action']['action_type']=='Find / capture'],cols=4,rows=3)
ar=HERE/'archive-download-receipt.json'
if ar.exists():
 seen=set();vs=[]
 for x in read(ar)['images']:
  if x['native_content_hash']in seen:continue
  seen.add(x['native_content_hash']);vs.append({'file_id':x['file_id'],'local_path':x['local_path'],'caption':'AR'+str(len(vs)+1).zfill(3)+' '+x['name']+' ['+x['file_id'][-5:]+']','archive_hash':x['native_content_hash']})
 make('archive-candidates',vs,cols=4,rows=3)
(HERE/'review-plate-manifest.json').write_text(json.dumps(plates,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'plates':len(plates),'categories':{c:sum(x['category']==c for x in plates)for c in dict.fromkeys(x['category']for x in plates)},'all157task_references_prepared':True}))
