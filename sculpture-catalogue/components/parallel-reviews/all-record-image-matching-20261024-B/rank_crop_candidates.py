"""Bounded crop-aware comparison within existing family scope; triage only."""
import hashlib,json,math
from pathlib import Path
from PIL import Image,ImageChops,ImageDraw,ImageFont,ImageOps,ImageStat
H=Path(__file__).resolve().parent
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
write=lambda p,v:Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
run=Path(read(H/'current-work.json')['run']);out=run/'source-evidence/crop-comparisons';out.mkdir(exist_ok=True)
ranked=read(run/'source-evidence/ranked-source-candidates.json')
decisions=read(H/'source-visual-decisions.json')
sources=read(H.parents[3]/'reports/dropbox-wall-complete-role-review-20261024T214349Z/current-6360-visual-source-evidence.json')
images={x['file_id']:x for x in read(run/'images.json')}
def rgb(p):
    with Image.open(p) as im:return ImageOps.exif_transpose(im).convert('RGB')
def metric(a,b):
    x=ImageStat.Stat(ImageChops.difference(a,b)).rms;return math.sqrt(sum(v*v for v in x)/len(x))
cache={}
for x in sources:
    if x['family'] in ['Dune Ripple','Moon Crater Phase','Moonwave','Ammonite','Brancusi','Fold Unfold']:
        im=rgb(x['source_image_path']);im.thumbnail((160,160));cache[x['file_id']]={**x,'analysis':im}
manifest=[]
for d in decisions.values():
    key=f"{d['offer_ref']}:{d['gallery_order']:02d}"
    if d['matched_candidate_file_id'] or d['offer_ref'] not in ['O006','O007','O009','O016','O018','O029','O045','O051','O052']:continue
    rr=next(x for x in ranked if x['gallery_entry_id']==d['gallery_entry_id'])
    src=rgb(d['source_path']);target=src.resize((24,24),Image.Resampling.BILINEAR);ar=src.width/src.height
    candidates=[]
    for fid,c in cache.items():
        if c['family'] not in rr['candidate_family_scope']:continue
        im=c['analysis'];best=(float('inf'),None,None)
        for angle in [0,90,180,270]:
            rot=im.rotate(angle,expand=True);w,h=rot.size
            maxw=min(w,h*ar);maxh=maxw/ar
            for frac in [1,.85,.7,.55,.4]:
                cw,ch=maxw*frac,maxh*frac
                for u in [0,.25,.5,.75,1]:
                    for v in [0,.25,.5,.75,1]:
                        x=(w-cw)*u;y=(h-ch)*v;box=tuple(round(z) for z in [x,y,x+cw,y+ch])
                        small=rot.crop(box).resize((24,24),Image.Resampling.BILINEAR)
                        score=metric(target,small)
                        if score<best[0]:best=(score,angle,box)
        candidates.append({'file_id':fid,'rgb_score':best[0],'candidate_analysis_rotation':best[1],
            'analysis_crop_box':best[2],'analysis_dimensions':im.size,'cached_path':c['source_image_path'],
            'cached_sha256':c['actual_visual_source_sha256'],**{k:images[fid].get(k) for k in ['name','family','folder_id','image_url','folder_url']}})
    candidates=sorted(candidates,key=lambda x:x['rgb_score'])[:5]
    row={'key':key,'gallery_entry_id':d['gallery_entry_id'],'source_path':d['source_path'],'source_sha256':d['source_sha256'],'candidate_family_scope':rr['candidate_family_scope'],'candidates':candidates,'ranking_is_identity_proof':False}
    manifest.append(row);print(key,[(c['file_id'][-6:],round(c['rgb_score'],1)) for c in candidates[:3]],flush=True)
write(out/'rankings.json',manifest)
font=ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc',17)
for r in manifest:
    board=Image.new('RGB',(1500,1150),'white');dr=ImageDraw.Draw(board)
    cells=[('SOURCE '+r['key'],r['source_path'])]+[(f"{n+1} {c['file_id'][-6:]} crop-score {c['rgb_score']:.1f}",c['cached_path']) for n,c in enumerate(r['candidates'])]
    for n,(label,path) in enumerate(cells):
        x=(n%3)*500;y=(n//3)*575;dr.text((x+5,y+5),label,fill='black',font=font)
        im=rgb(path);im.thumbnail((490,480),Image.Resampling.LANCZOS);board.paste(im,(x+(500-im.width)//2,y+35+(480-im.height)//2))
        if n:
            text=r['candidates'][n-1]['family']+' / '+r['candidates'][n-1]['name'];dr.text((x+5,y+520),'\n'.join(text[j:j+58] for j in range(0,min(174,len(text)),58)),fill='black',font=font)
    p=out/(r['key'].replace(':','-')+'.jpg');board.save(p,quality=90);r['board']=str(p);r['board_sha256']=sha(p)
write(out/'manifest.json',manifest)
print(json.dumps({'boards':len(manifest),'automatic_matches':0}))
