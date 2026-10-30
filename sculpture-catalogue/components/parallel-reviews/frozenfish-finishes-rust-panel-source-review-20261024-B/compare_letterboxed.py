"""Compare retained FFS2 images after removing white margins in memory only."""
from pathlib import Path
from PIL import Image,ImageOps,ImageChops,ImageStat
import json,math
H=Path(__file__).resolve().parent;B=H.parents[2]
read=lambda p:json.loads(Path(p).read_text())
p=read(B/'current-master.json');a=read(B/p['current_asset_reference_map']['path'])
idx={x['ref']:x for x in read(B/'components/evidence/offer_review_index.json')}
def trimmed(path):
    with Image.open(path) as im:im=ImageOps.exif_transpose(im).convert('RGB')
    diff=ImageChops.difference(im,Image.new('RGB',im.size,'white')).convert('L')
    columns=list(diff.resize((im.width,1),Image.Resampling.BOX).getdata())
    rows=list(diff.resize((1,im.height),Image.Resampling.BOX).getdata())
    xs=[i for i,v in enumerate(columns) if v>12];ys=[i for i,v in enumerate(rows) if v>12]
    bbox=(min(xs),min(ys),max(xs)+1,max(ys)+1) if xs and ys else (0,0,*im.size)
    return im.crop(bbox).resize((96,96),Image.Resampling.LANCZOS),list(bbox),list(im.size)
def rmse(a,b):return math.sqrt(sum(x*x for x in ImageStat.Stat(ImageChops.difference(a,b)).rms)/3)
cache={fid:(x,trimmed(x['thumb'])) for fid,x in a.items() if '/Frozen Fish/' in x.get('path','') and Path(x.get('thumb','/missing')).is_file()}
rows=[]
for ref in ['O049','O063']:
    for s in idx[ref]['images']:
        source=s['path'] if Path(s['path']).is_file() else s['thumb'];im,bbox,size=trimmed(source)
        scores=sorted([{'file_id':fid,'path':x['path'],'cached_path':x['thumb'],'comparison_bbox':bb,'dimensions':sz,'rmse':rmse(im,v)} for fid,(x,(v,bb,sz)) in cache.items()],key=lambda x:x['rmse'])
        row={'ref':ref,'source_order':s['order'],'source_cached_path':source,'source_comparison_bbox':bbox,'source_dimensions':size,'candidates_ranked':len(cache),'ranking':scores[:3]}
        rows.append(row);print(json.dumps({'ref':ref,'source_order':s['order'],'source_bbox':bbox,'top':scores[:2]}))
(H/'white-margin-comparison.json').write_text(json.dumps({'method':'Threshold12 on mean column and row white-background luminance difference; content bounding box then96px RGB RMSE. Analysis in memory only; no source or image file modified. Scores rank candidates, not physical configuration.','rows':rows},indent=2)+'\n')
