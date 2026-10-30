import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
root=Path(__file__).resolve().parent;a=json.load(open(root/'assignment.json'))
assets={r['id']:r for r in a['assets']}; groups={r['group_ref']:r for r in a['groups']}
extra=[]
for gr in ['G176','G172','G173','G209','G212','G214','G244','G198','G202','G225','G235','G259']:
 g=groups[gr]; cand=[r for r in a['assets'] if r['folder_id']==g['id']] if gr in ['G176','G172','G173','G244'] else [assets[f] for f in g['selected'][1:]]
 for r in cand[:20]:
  p=next((r.get(k) for k in ['thumb','full'] if r.get(k) and Path(r[k]).is_file()),None)
  if p:extra.append({'label':gr+' '+r['id'][-10:],'file_id':r['id'],'folder_id':r['folder_id'],'preview_path':p})
refs=json.load(open('/Users/tprice/Library/Application Support/BoldstoneImageConsistency/product-evidence-resolution-20261016T201618Z/Manufacturing_Labelled_References.json'))
rows=set(sum([c['maker_rows'] for c in a['components']],[]))
for r in refs:
 if r['row'] in rows:extra.append({'label':str(r['row'])+' '+r['code'],'preview_path':r['picture']['preview'],'source_ref':'manufacture-stevensons:row'+str(r['row'])})
font=ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc',16)
for n in range(0,len(extra),16):
 batch=extra[n:n+16];sheet=Image.new('RGB',(1440,1200),'#dddddd');d=ImageDraw.Draw(sheet)
 for j,r in enumerate(batch):
  x=(j%4)*360;y=(j//4)*300;im=Image.open(r['preview_path']).convert('RGB');im.thumbnail((348,260));sheet.paste(im,(x+(360-im.width)//2,y+(260-im.height)//2))
  d.text((x+7,y+265),f"E{n+j+1:02d} {r['label']}",fill='black',font=font)
 sheet.save(root/'review_sheets'/f'extra-{n//16+1:02d}.jpg',quality=92)
(root/'extra_image_index.json').write_text(json.dumps(extra,indent=2))
print('extras',len(extra))
print('G176 assets',[r['id'] for r in a['assets'] if r['folder_id']==groups['G176']['id']])
