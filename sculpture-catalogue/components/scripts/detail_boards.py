import json
from pathlib import Path
from PIL import Image,ImageOps,ImageDraw
root=Path(__file__).resolve().parents[1];d=json.loads((root/'evidence/evidence_index.json').read_text())
for name,refs in [('fingerprint',[154,155,156,157,158,160]),('barbados',[23]),('mixed',[50,297])]:
    wanted={d['groups'][n-1]['id'] for n in refs};rows=[a for a in d['assets'] if a['folder_id'] in wanted]
    for start in range(0,len(rows),24):
        chunk=rows[start:start+24];board=Image.new('RGB',(1680,((len(chunk)+5)//6)*228),'white');draw=ImageDraw.Draw(board)
        for i,r in enumerate(chunk):
            x=i%6*280;y=i//6*228
            with Image.open(r['thumb']) as src:
                pic=ImageOps.contain(src.convert('RGB'),(272,190));board.paste(pic,(x+(280-pic.width)//2,y))
            draw.text((x+3,y+193),r['group'][:36]+'\n'+r['name'].split('__')[-1]+' '+r['id'][-7:],fill='black')
        board.save(root/'reviews'/f'{name}-{start//24+1:02d}.jpg',quality=96)
    (root/'evidence'/f'{name}-board-index.json').write_text(json.dumps(rows,ensure_ascii=False))
