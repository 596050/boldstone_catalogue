"""Render labelled analytical contact sheets; never alter catalogue photographs."""
import hashlib
import json
import textwrap
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps
H=Path(__file__).resolve().parent
run=Path(json.loads((H/'current-work.json').read_text())['run'])
data=json.loads((run/'source-evidence/ranked-source-candidates.json').read_text())
rows=[x for x in data if x['offer_ref']!='O001']
out=run/'source-evidence/comparison-boards';out.mkdir(exist_ok=True)
font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',16)
small=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',13)
manifest=[]
for start in range(0,len(rows),12):
    group=rows[start:start+12]; board=Image.new('RGB',(1350,1440),'white');draw=ImageDraw.Draw(board)
    entries=[]
    for slot,row in enumerate(group):
        x=(slot%3)*450;y=(slot//3)*360
        candidate=row['ranked_candidates'][0]
        label=f"{row['offer_ref']} / {row['gallery_order']:02d}   SOURCE | CURRENT CANDIDATE"
        draw.text((x+5,y+5),label,fill='black',font=font)
        for offset,path in [(0,row['selected_rendition']['path']),(225,candidate['cached_path'])]:
            with Image.open(path) as source:
                source=ImageOps.exif_transpose(source).convert('RGB')
                source.thumbnail((218,270),Image.Resampling.LANCZOS)
                board.paste(source,(x+offset+(225-source.width)//2,y+35+(270-source.height)//2))
        caption=f"{candidate['file_id'][-6:]}  score {candidate['whole_frame_RGB_RMSE_32px']:.2f}  {candidate['name']}"
        draw.multiline_text((x+5,y+309),'\n'.join(textwrap.wrap(caption,59)[:3]),fill='black',font=small,spacing=1)
        draw.line([(x,y+359),(x+449,y+359)],fill='#aaaaaa')
        entries.append({'slot_1based':slot+1,'offer_ref':row['offer_ref'],'gallery_order':row['gallery_order'],
            'gallery_entry_id':row['gallery_entry_id'],'source_path':row['selected_rendition']['path'],
            'source_sha256':row['selected_rendition']['sha256'],'candidate_file_id':candidate['file_id'],
            'candidate_path':candidate['cached_path'],'candidate_sha256':candidate['cached_sha256']})
    path=out/f'comparison-{start//12+1:03d}.jpg';board.save(path,quality=94,subsampling=0)
    manifest.append({'board':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'entries':entries})
(out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'boards':len(manifest),'entries':len(rows),'out':str(out)}))
