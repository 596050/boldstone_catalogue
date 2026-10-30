"""Triage unresolved source photographs against all current native-bound caches.

Border removal and rotations exist only in analysis memory. No source or
catalogue photograph is edited, and no score creates an identity assertion.
"""
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageOps, ImageStat

H=Path(__file__).resolve().parent
ROOT=H.parents[3]
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
write=lambda p,v:Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
run=Path(read(H/'current-work.json')['run'])
out=run/'source-evidence/unresolved-comparisons';out.mkdir(exist_ok=True)
decisions=read(H/'source-visual-decisions.json')
sources=read(ROOT/'reports/dropbox-wall-complete-role-review-20261024T214349Z/current-6360-visual-source-evidence.json')
images={x['file_id']:x for x in read(run/'images.json')}
def openrgb(p):
    with Image.open(p) as im:return ImageOps.exif_transpose(im).convert('RGB')
def trim(im):
    diff=ImageChops.difference(im,Image.new('RGB',im.size,'white')).convert('L')
    box=diff.point(lambda v:255 if v>20 else 0).getbbox()
    return im.crop(box) if box else im
def rms(a,b):
    values=ImageStat.Stat(ImageChops.difference(a,b)).rms
    return math.sqrt(sum(v*v for v in values)/len(values))
cache={}
for r in sources:
    assert sha(r['source_image_path'])==r['actual_visual_source_sha256']
    im=trim(openrgb(r['source_image_path'])).resize((32,32),Image.Resampling.BILINEAR)
    cache[r['file_id']]={'rgb':im,'gray':ImageOps.autocontrast(im.convert('L')),'source':r}
rows=[]
for key,d in decisions.items():
    if d['matched_candidate_file_id']:continue
    source=trim(openrgb(d['source_path'])).resize((32,32),Image.Resampling.BILINEAR)
    rotations=[source.rotate(a) for a in (0,90,180,270)]
    grays=[ImageOps.autocontrast(x.convert('L')) for x in rotations]
    candidates=[]
    for fid,c in cache.items():
        rgb=min((rms(im,c['rgb']),a) for im,a in zip(rotations,(0,90,180,270)))
        gray=min((rms(im,c['gray']),a) for im,a in zip(grays,(0,90,180,270)))
        candidates.append({'file_id':fid,'rgb_score':rgb[0],'source_rotation_rgb':rgb[1],
                           'gray_score':gray[0],'source_rotation_gray':gray[1]})
    union={c['file_id']:c for c in sorted(candidates,key=lambda c:c['rgb_score'])[:4]}
    for c in sorted(candidates,key=lambda c:c['gray_score'])[:3]:union.setdefault(c['file_id'],c)
    ranked=sorted(union.values(),key=lambda c:min(c['rgb_score'],c['gray_score']))[:7]
    for c in ranked:
        fid=c['file_id'];r=cache[fid]['source'];i=images[fid]
        c.update({k:i.get(k) for k in ('name','family','image_url','folder_url','folder_id')})
        c['cached_path']=r['source_image_path'];c['cached_sha256']=r['actual_visual_source_sha256']
    row={'key':key,'source_path':d['source_path'],'source_sha256':d['source_sha256'],
         'gallery_entry_id':d['gallery_entry_id'],'candidates':ranked,'ranking_is_identity_proof':False}
    rows.append(row)
    print(key,[(c['file_id'][-6:],round(c['rgb_score'],2),round(c['gray_score'],2)) for c in ranked[:3]],flush=True)
write(out/'ranked-unresolved.json',rows)
font=ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc',17)
manifest=[]
for row in rows:
    board=Image.new('RGB',(1600,1100),'white');draw=ImageDraw.Draw(board)
    cells=[('SOURCE '+row['key'],row['source_path'])]+[(f"{n+1} {c['file_id'][-6:]} RGB {c['rgb_score']:.1f} L {c['gray_score']:.1f}",c['cached_path']) for n,c in enumerate(row['candidates'])]
    for n,(label,path) in enumerate(cells):
        x=(n%4)*400;y=(n//4)*550
        draw.text((x+7,y+5),label,fill='black',font=font)
        im=openrgb(path);im.thumbnail((390,450),Image.Resampling.LANCZOS)
        board.paste(im,(x+(400-im.width)//2,y+40+(450-im.height)//2))
        if n:
            c=row['candidates'][n-1]
            text=c['family']+' / '+c['name']
            lines=[text[j:j+45] for j in range(0,min(len(text),135),45)]
            draw.text((x+7,y+493),'\n'.join(lines),fill='black',font=font)
    p=out/(row['key'].replace(':','-')+'.jpg');board.save(p,quality=90)
    manifest.append({**row,'board':str(p),'board_sha256':sha(p)})
write(out/'manifest.json',manifest)
print(json.dumps({'review_boards':len(manifest),'current_files_screened':len(cache),'automatic_matches':0}))
