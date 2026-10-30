#!/usr/bin/env python3
"""Create local inspection boards and immutable source hashes; no source-image edit."""
from pathlib import Path
from datetime import datetime, timezone
from PIL import Image, ImageOps, ImageDraw
import hashlib,json,textwrap

B=Path(__file__).resolve().parents[1];O=Path(__file__).resolve().parent
MASTER=B/'inputs/master-register.json'
BASE=Path('/Users/tprice/Documents/boldstone/sculpture-catalogue')
NATIVE=BASE/'components/parallel-reviews/wall-circle-2026-10-17/family-keep/native-pattern-image-bindings.json'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dbhash(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  while True:
   b=f.read(4*1024*1024)
   if not b:break
   h.update(hashlib.sha256(b).digest())
 return h.hexdigest()
g=json.loads(MASTER.read_text());assert sha(MASTER)=='7760b44a4d52ff3b78c893d5b86ef174814b48c29f7e41814c8a01a42af5326d'
modelbind=g['input_manifest']['source_model'];modelpath=Path(modelbind['snapshot']);assert sha(modelpath)==modelbind['sha256']
model=json.loads(modelpath.read_text());assets={x['id']:x for x in model['assets']}
ops=sorted([o for o in g['options'] if o['canonical_key'].startswith('BC-WALL-CIRCLE|')],key=lambda o:o['canonical_key'])
visual=[]
for o in ops:
 a=assets[o['file_id']];p=Path(a['full']);assert p.is_file(),p
 with Image.open(p) as im: sz=list(im.size)
 assert p.stat().st_size==a['bytes'];assert dbhash(p)==a['content_hash']
 visual.append({'review_id':o['canonical_key'].split('|')[1],'product_id':o['product_id'],'name':o['name'],'file_id':o['file_id'],'folder_id':o['folder_id'],'master_index':g['options'].index(o),'local_path':str(p),'sha256':sha(p),'dropbox_content_hash':a['content_hash'],'bytes':p.stat().st_size,'dimensions_px':sz,'working_fields':o['master_fields'],'source_model_asset_ref':{'path':str(modelpath),'sha256':modelbind['sha256'],'json_pointer':'/assets/'+str(model['assets'].index(a))}})
bindings=json.loads(NATIVE.read_text());patterns=[]
for i,b in enumerate(bindings):
 p=Path(b['local_image']);assert p.is_file();assert sha(p)==b['image_sha256'];assert dbhash(p)==b['image_dropbox_content_hash']
 with Image.open(p) as im:sz=list(im.size)
 patterns.append({'pattern_index':i,'short_name':b['pattern'].split('  ')[0],'pattern':b['pattern'],'native_image_id':b['image']['id'],'native_image_url':b['image']['assetUrl'],'local_path':str(p),'sha256':sha(p),'dropbox_content_hash':dbhash(p),'bytes':p.stat().st_size,'dimensions_px':sz,'native_variant_ids':b['variant_ids'],'source_binding_ref':{'path':str(NATIVE),'sha256':sha(NATIVE),'json_pointer':'/'+str(i)}})
O.mkdir(exist_ok=True,parents=True);boards=[]
def tile(im,p,xy,wh,label):
 src=Image.open(p).convert('RGB');small=ImageOps.contain(src,(wh[0]-16,wh[1]-60));x,y=xy;im.paste(small,(x+(wh[0]-small.width)//2,y+48+(wh[1]-60-small.height)//2));d=ImageDraw.Draw(im)
 for j,line in enumerate(textwrap.wrap(label,width=max(20,wh[0]//7))[:3]):d.text((x+8,y+4+j*14),line,fill='black')
im=Image.new('RGB',(1680,1160),'#eeeeee')
for i,v in enumerate(visual):tile(im,v['local_path'],((i%4)*420,(i//4)*580),(420,580),v['review_id']+' '+v['name'])
p=O/'seven-visual-records.png';im.save(p);boards.append({'path':str(p),'sha256':sha(p),'purpose':'Seven complete source-image frames; resized for inspection only.'})
for start in [0,6,12]:
 im=Image.new('RGB',(1440,1160),'#eeeeee')
 for j,v in enumerate(patterns[start:start+6]):tile(im,v['local_path'],((j%3)*480,(j//3)*580),(480,580),str(v['pattern_index']+1).zfill(2)+' '+v['short_name'])
 p=O/f'native-patterns-{start//6+1:02d}.png';im.save(p);boards.append({'path':str(p),'sha256':sha(p),'purpose':'Six complete native pattern-image frames; no crop or pattern alteration.'})
manifest={'schema':'boldstone.wall-seven-vs-eighteen-local-inputs.v1','prepared_utc':datetime.now(timezone.utc).isoformat(),'master_binding':{'path':str(MASTER),'sha256':sha(MASTER)},'source_model_binding':{'path':str(modelpath),'sha256':sha(modelpath)},'native_pattern_bindings':{'path':str(NATIVE),'sha256':sha(NATIVE)},'visual_records':visual,'native_patterns':patterns,'inspection_boards':boards,'counts':{'visual_records':len(visual),'native_patterns':len(patterns),'pairwise_comparisons_required':len(visual)*len(patterns),'existing_native_variants':len(g['wall_circle_native_options'])},'source_originals_modified':False,'remote_reads':0,'remote_writes':0,'shared_writes':0}
(O/'LOCAL_INPUTS.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'counts':manifest['counts'],'boards':boards},indent=2))
