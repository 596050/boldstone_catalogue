from PIL import Image,ImageDraw,ImageFont
import json,math,textwrap
from pathlib import Path
H=Path(__file__).resolve().parent;r=lambda p:json.loads(Path(p).read_text());a=r(H/'inputs/audit.before');assets=r(H/'inputs/report_assets.before');scope=r(H/'scope.json');(H/'inspection').mkdir(exist_ok=True);font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',16)
rows=[]
for x in a['missing_pictures']:
 if x['status']=='Open'and x['role']!='Individual'and x['option_id']not in scope['target_option_ids']:
  src=assets.get(x['reference']['file_id'],{}).get('thumb');rows.append({'label':str(len(rows)+1)+'. '+x['name']+' / '+x['role'],'source':src,'option_id':x['option_id'],'role':x['role'],'reference':x['reference']})
def draw(rows,prefix,perpage,columns):
 for page in range(math.ceil(len(rows)/perpage)):
  part=rows[page*perpage:(page+1)*perpage];width=500;im=Image.new('RGB',(width*columns,math.ceil(len(part)/columns)*315),'white');d=ImageDraw.Draw(im)
  for i,x in enumerate(part):
   xx=(i%columns)*width;yy=(i//columns)*315;src=x['source']
   if src and Path(src).exists():
    p=Image.open(src).convert('RGB');p.thumbnail((width-15,250));im.paste(p,(xx+(width-15-p.width)//2,yy))
   d.multiline_text((xx+5,yy+252),'\n'.join(textwrap.wrap(x['label'],54)),fill='black',font=font)
  im.save(H/'inspection'/(prefix+'-'+str(page+1)+'.jpg'))
draw(rows,'context-gap-references',18,3);(H/'context-inspection-rows.json').write_text(json.dumps(rows,indent=2)+'\n');print('CONTEXT_INSPECTION',len(rows),'rows',math.ceil(len(rows)/18),'pages')
ac=next(v for k,v in r(H/'current-family-listings.json').items()if k.endswith('/Acanthus'));rows=[{'label':x['name'],'source':assets[x['file_id']]['thumb'],'file_id':x['file_id']}for x in ac['entries']if x['object_type']=='file'and assets.get(x['file_id'],{}).get('thumb')];draw(rows,'acanthus-family',20,4);print('ACANTHUS_INSPECTION',len(rows),'cached views')
