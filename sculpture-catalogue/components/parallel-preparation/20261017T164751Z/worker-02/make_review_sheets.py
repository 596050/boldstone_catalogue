from pathlib import Path
import json, math
from PIL import Image, ImageOps, ImageDraw, ImageFont
root=Path(__file__).resolve().parent
assignment=json.load(open(root/'assignment.json'))
assets={a['id']:a for a in assignment['assets']}
selected=[]
for g in assignment['groups']:
    if g.get('selected'):
        fid=g['selected'][0]
        a=assets.get(fid)
        if a:
            p=next((a.get(k) for k in ['thumb','full'] if a.get(k) and Path(a[k]).is_file()),None)
            selected.append({'index':len(selected)+1,'group_ref':g['group_ref'],'group_name':g['name'],'role':g['role'],'component_ids':g['component_ids'],'file_id':fid,'folder_id':a['folder_id'],'preview_path':p,'source_asset':a})
(root/'review_sheets').mkdir(exist_ok=True)
font=ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc',16)
small=ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc',14)
for n in range(0,len(selected),16):
    batch=selected[n:n+16]; sheet=Image.new('RGB',(1440,1320),'#dddddd'); d=ImageDraw.Draw(sheet)
    for j,r in enumerate(batch):
        x=(j%4)*360; y=(j//4)*330
        if r['preview_path']:
            im=Image.open(r['preview_path']).convert('RGB'); im.thumbnail((348,250)); sheet.paste(im,(x+(360-im.width)//2,y+4+(250-im.height)//2))
        text=f"{r['index']:02d} {r['group_ref']} {r['file_id'][-10:]}"
        d.text((x+7,y+257),text,fill='black',font=font)
        name=r['group_name']
        d.text((x+7,y+279),name[:43],fill='black',font=small)
        if len(name)>43:d.text((x+7,y+296),name[43:86],fill='black',font=small)
        d.text((x+7,y+313),r['role'],fill='black',font=small)
    output=root/'review_sheets'/f'groups-{n//16+1:02d}.jpg';sheet.save(output,quality=92)
(root/'image_index.json').write_text(json.dumps(selected,indent=2))
print('images',len(selected),'sheets',math.ceil(len(selected)/16),'missing previews',sum(not r['preview_path'] for r in selected))
