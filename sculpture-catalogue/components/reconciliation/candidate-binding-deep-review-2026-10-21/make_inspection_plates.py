"""Labelled diagnostic comparisons; untouched source files retained separately."""
import hashlib,json,textwrap
from pathlib import Path
from PIL import Image,ImageOps,ImageDraw,ImageFont
H=Path(__file__).resolve().parent;read=lambda p:json.loads(Path(p).read_text());assets=read(H/'current-assets.json');checks={x['sequence']:x for x in read(H/'candidate-checks.json')}
font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',20);manifest=[]
def source(fid):
 a=assets[fid];return next(a[k]for k in ['full','thumb']if a.get(k)and Path(a[k]).is_file())
def make(name,views,cols=2,tilew=800,tileh=620):
 rows=(len(views)+cols-1)//cols;canvas=Image.new('RGB',(cols*tilew,rows*tileh),'#eef2ed');draw=ImageDraw.Draw(canvas);actual=[]
 for n,x in enumerate(views):
  x=dict(x);fid=x['file_id'];src=source(fid);left=n%cols*tilew;top=n//cols*tileh
  with Image.open(src)as im:
   im=ImageOps.exif_transpose(im).convert('RGB');size=im.size;box=x.get('crop')
   if box:im=im.crop(tuple(round(v*(size[0]if j%2==0 else size[1]))for j,v in enumerate(box)))
   if x.get('rotate'):im=im.rotate(x['rotate'],expand=True)
   factor=min((tilew-20)/im.width,(tileh-95)/im.height,3 if box else 1)
   im=im.resize((max(1,round(im.width*factor)),max(1,round(im.height*factor))),Image.Resampling.LANCZOS);canvas.paste(im,(left+(tilew-im.width)//2,top+(tileh-95-im.height)//2))
  for row,line in enumerate(textwrap.wrap(x['label'],74)[:4]):draw.text((left+10,top+tileh-87+row*21),line,font=font,fill='#243a2b')
  actual.append({**x,'source_path':src,'source_size':size,'source_sha256':hashlib.sha256(Path(src).read_bytes()).hexdigest()})
 p=H/'plates'/(name+'.jpg');canvas.save(p,quality=95);manifest.append({'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'views':actual})
def primary(n,crop=None,rotate=None):return{'file_id':checks[n]['primary_reference']['file_id'],'label':str(n)+' PRIMARY '+checks[n]['name'],'crop':crop,'rotate':rotate}
make('fold-primary-geometry',[primary(n)for n in [56,57,58,59]])
make('palm-primary-geometry',[primary(n)for n in [43,44,45,54]])
make('flower-match',[primary(29),{'file_id':checks[29]['candidate_reference']['file_id'],'label':'29 ROOM: complete Flower relief; source-qualified depiction','crop':[.182,.228,.302,.357]}])
make('fold-series-members',[{'file_id':checks[130]['candidate_reference']['file_id'],'label':'SERIES position '+str(n+1)+' from LEFT, source landscape pose','crop':box}for n,box in enumerate([[.047,.34,.250,.570],[.252,.336,.460,.567],[.468,.332,.679,.567],[.682,.335,.884,.564]])])
make('fold-series-rotated-clockwise',[{'file_id':checks[130]['candidate_reference']['file_id'],'label':'SERIES position '+str(n+1)+' from LEFT; diagnostic rotation 90 degrees clockwise','rotate':-90,'crop':box}for n,box in enumerate([[.047,.34,.250,.570],[.252,.336,.460,.567],[.468,.332,.679,.567],[.682,.335,.884,.564]])])
make('palm-garden-members',[{'file_id':checks[43]['candidate_reference']['file_id'],'label':'GARDEN position '+str(n+1)+' from LEFT','crop':box}for n,box in enumerate([[.350,.277,.429,.387],[.432,.277,.510,.387],[.514,.277,.593,.387],[.596,.277,.674,.387]])])
make('fold-garden-members',[{'file_id':checks[56]['candidate_reference']['file_id'],'label':'GARDEN position '+str(n+1)+' from LEFT','crop':box}for n,box in enumerate([[.105,.14,.325,.53],[.412,.20,.580,.545],[.647,.24,.775,.53],[.801,.27,.899,.531]])])
foldgarden=[]
for n,box,rot in [(56,[.105,.14,.325,.53],0),(57,[.412,.20,.580,.545],0),(58,[.647,.24,.775,.53],180),(59,[.801,.27,.899,.531],180)]:
 foldgarden.extend([primary(n,rotate=rot),{'file_id':checks[56]['candidate_reference']['file_id'],'label':str(n)+' GARDEN position '+str(n-55)+'; diagnostic primary rotation '+str(rot)+' degrees','crop':box}])
make('fold-garden-binding-comparison',foldgarden)
make('egyptian-gold-pair',[primary(54),{'file_id':checks[54]['candidate_reference']['file_id'],'label':'54 / 128 room Gold pair: left and right full panels','crop':[.645,.165,.790,.305]}])
extra=read(H/'opportunistic-brancusi1-task.json')
make('brancusi-gold-pair',[primary(41),{'file_id':checks[41]['candidate_reference']['file_id'],'label':'41 Gold folded panels room scene, enlarged source pixels','crop':[.745,.350,.920,.562]},{'file_id':extra['primary_reference']['file_id'],'label':'39 PRIMARY Brancusi 1 Gold Leaf'}])
make('brancusi-white-versions',[primary(38),{'file_id':checks[38]['candidate_reference']['file_id'],'label':'38 White garden solo, full source'},primary(40),{'file_id':checks[40]['candidate_reference']['file_id'],'label':'40 White garden group, full source'}])
make('shellmoon-configurations',[primary(103),{'file_id':checks[103]['candidate_reference']['file_id'],'label':'103 garden context, full source'},primary(104),{'file_id':checks[104]['candidate_reference']['file_id'],'label':'104 garden context, full source'}])
make('spice-comparison',[primary(106),primary(107),{'file_id':checks[106]['candidate_reference']['file_id'],'label':'106 / 107 / 156 / 157 display context; full source'}])
make('brancusi-white-group-details',[primary(38),primary(40),{'file_id':checks[40]['candidate_reference']['file_id'],'label':'White garden LEFT pair, complete fold outlines','crop':[.16,.235,.37,.40]},{'file_id':checks[40]['candidate_reference']['file_id'],'label':'White garden RIGHT pair, complete fold outlines','crop':[.68,.235,.90,.40]}])
make('riyadh-site-members',[primary(98,rotate=-90),{'file_id':checks[98]['candidate_reference']['file_id'],'label':'Riyadh site: far-left complete WAVE panel','crop':[.14,.34,.21,.55]},primary(99,rotate=-90),{'file_id':checks[99]['candidate_reference']['file_id'],'label':'Riyadh site: SPIRAL panel second from left','crop':[.209,.34,.257,.55]},primary(100),{'file_id':checks[100]['candidate_reference']['file_id'],'label':'Riyadh site: PLAIN MOON panel fourth from left','crop':[.300,.34,.350,.55]}])
make('half-moon-marbling',[primary(74),{'file_id':checks[74]['candidate_reference']['file_id'],'label':'74 candidate full room view'}])
make('acanthus-colour-studies',[primary(154),primary(155),{'file_id':checks[154]['candidate_reference']['file_id'],'label':'154 / 155 full five-member colour-study source'}])
make('shellmoon-outlet-details',[{'file_id':checks[103]['candidate_reference']['file_id'],'label':'Battersea: portrait relief above pebble basin','crop':[.34,.285,.51,.63]},{'file_id':checks[104]['candidate_reference']['file_id'],'label':'Islington: landscape relief on pink wall, wider garden photo','crop':[.04,.25,.35,.49]}])
make('spice-member-details',[primary(106),{'file_id':checks[106]['candidate_reference']['file_id'],'label':'Spice LEFT wall panel, partly obscured','crop':[.30,.345,.62,.82]},primary(107),{'file_id':checks[107]['candidate_reference']['file_id'],'label':'Spice RIGHT wall panel','crop':[.62,.345,.91,.82]}])
make('shellwave-water-two-tiers',[primary(139)])
make('frozen-fish-build-size',[primary(66),{'file_id':checks[66]['candidate_reference']['file_id'],'label':'66 garden scene: same fin design; no scale witness'}])
make('half-moon-rotated-panel',[primary(74,crop=[.585,.122,.722,.786],rotate=-90),{'file_id':checks[74]['candidate_reference']['file_id'],'label':'74 horizontal room panel, compare dark wedge and black round inclusions','crop':[.018,.279,.979,.488]}],cols=1,tilew=1500,tileh=450)
make('riyadh-alternative-orientation',[primary(99,rotate=90),{'file_id':checks[99]['candidate_reference']['file_id'],'label':'Riyadh second from left SPIRAL, complete relief','crop':[.202,.315,.263,.555]},primary(100,rotate=180),{'file_id':checks[100]['candidate_reference']['file_id'],'label':'Riyadh fourth from left PLAIN MOON','crop':[.297,.315,.352,.555]}])
(H/'inspection-plate-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'plates':len(manifest)}))
