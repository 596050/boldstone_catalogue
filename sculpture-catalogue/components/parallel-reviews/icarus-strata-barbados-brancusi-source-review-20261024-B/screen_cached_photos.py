"""Rank retained photographs for visual review; do not alter image files."""
import hashlib
import json
import math
from pathlib import Path
from PIL import Image, ImageChops, ImageOps, ImageStat

H = Path(__file__).resolve().parent
B = H.parents[2]
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
p = read(B / 'current-master.json')
a = read(B / p['current_asset_reference_map']['path'])
index = {x['ref']: x for x in read(B / 'components/evidence/offer_review_index.json')}
families = {'O061': 'Abstract Cave Paintings', 'O062': 'Strata', 'O078': 'Barbados Wave', 'O080': 'Brancusi Totem'}

def pixels(path):
    with Image.open(path) as im:
        return ImageOps.exif_transpose(im).convert('RGB').resize((96,96), Image.Resampling.LANCZOS)

def rmse(x, y):
    return math.sqrt(sum(v*v for v in ImageStat.Stat(ImageChops.difference(x,y)).rms)/3)

rows = []
for ref, family in families.items():
    candidates = [(fid, asset) for fid,asset in a.items() if '/'+family+'/' in asset.get('path','') and Path(asset.get('thumb','/missing')).is_file()]
    cache = {fid:pixels(asset['thumb']) for fid,asset in candidates}
    for s in index[ref]['images']:
        x = pixels(s['thumb'])
        scores = sorted((rmse(x,cache[fid]),fid,asset) for fid,asset in candidates)
        row = {'ref':ref,'source_order':s['order'],'source_url':s['url'],'source_cached_path':s['thumb'],
               'source_cached_sha256':sha(s['thumb']),'historical_original_present':Path(s['path']).is_file(),
               'candidates_ranked':len(candidates),'visually_reviewed':False,
               'ranking':[{'rmse_96px':score,'file_id':fid,'path':asset['path'],'cached_path':asset['thumb']} for score,fid,asset in scores[:3]]}
        rows.append(row)
        print(json.dumps({'ref':ref,'source_order':s['order'],'ranked':len(candidates),'top':row['ranking'][:2]}))
(H/'cached-photo-ranking.json').write_text(json.dumps({'method':'EXIF-normalized whole-frame RGB 96px RMSE; ranking is not visual confirmation or physical evidence','rows':rows},indent=2)+'\n')
