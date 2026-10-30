import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
root=Path(__file__).resolve().parent;a=json.load(open(root/'assignment.json'));gs={x['group_ref']:x for x in a['groups']}; extra=[]
for gr in ['G177','G235']:
 for r in a['assets']:
  if r['folder_id']==gs[gr]['id'] and Path(r['thumb']).is_file():extra.append({'label':gr+' '+r['id'][-10:],'file_id':r['id'],'folder_id':r['folder_id'],'preview_path':r['thumb']})
font=ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc',16)
for n in range(0,len(extra),16):
 sheet=Image.new('RGB',(1440,1200),'#ddd');d=ImageDraw.Draw(sheet)
 for j,r in enumerate(extra[n:n+16]):
  x=j%4*360;y=j//4*300;im=Image.open(r['preview_path']).convert('RGB');im.thumbnail((348,260));sheet.paste(im,(x+(360-im.width)//2,y+(260-im.height)//2));d.text((x+7,y+265),f"D{n+j+1:02d} {r['label']}",fill='black',font=font)
 sheet.save(root/'review_sheets'/f'detail-{n//16+1:02d}.jpg',quality=92)
(root/'detail_image_index.json').write_text(json.dumps(extra,indent=2));print(len(extra))
