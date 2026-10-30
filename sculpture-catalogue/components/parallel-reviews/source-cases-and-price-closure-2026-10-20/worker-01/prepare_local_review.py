import json, hashlib, math
from pathlib import Path
from PIL import Image, ImageOps, ImageDraw

OUT=Path(__file__).parent
BASE=OUT.parent/'inputs'
REGISTER=json.load(open(BASE/'component_register.json'))
E=Path('/Users/tprice/Library/Application Support/BoldstoneImageConsistency/product-evidence-resolution-20261016T201618Z')
GROUPS={g['group_ref']:g for g in REGISTER['groups']}
LANES={
 'bone':['G351','G352','G026','G027','G353'],
 'cup':['G058','G059','G060','G061','G062','G063'],
 'dr':['G101','G102','G118'],
 'fish':['G167','G168','G169','G170','G171','G172','G173'],
}
def dhash(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  while b:=f.read(4*1024*1024): h.update(hashlib.sha256(b).digest())
 return h.hexdigest()

manifest={'remote_reads':0,'remote_writes':0,'shared_writes':0,'wall_circle_excluded':True,'cases':{}}
for lane,refs in LANES.items():
 folder_ids={GROUPS[x]['id']:x for x in refs}
 assets=[a for a in REGISTER['assets'] if a['folder_id'] in folder_ids]
 views=[]; by_key={}; fullcount=0; nativecount=0
 for a in assets:
  full=Path(a.get('full') or '/NONEXISTENT')
  thumb=Path(a.get('thumb') or '/NONEXISTENT')
  p=full if full.is_file() else thumb if thumb.is_file() else None
  if not p: continue
  isfull=full.is_file()
  fullcount+=int(isfull)
  actual=dhash(p) if isfull else None
  native=isfull and p.stat().st_size==a['bytes'] and actual==a['content_hash']
  nativecount+=int(native)
  # Every distinct cached full byte stream is reviewed; repeated IDs/hashes are indexed.
  key=hashlib.sha256(p.read_bytes()).hexdigest()
  if key in by_key:
   views[by_key[key]]['equivalent_asset_ids'].append(a['id']);continue
  row={'review_index':len(views)+1,'asset_id':a['id'],'equivalent_asset_ids':[a['id']],
   'folder_id':a['folder_id'],'group_ref':folder_ids[a['folder_id']],
   'source_name':a['name'],'path':str(p),'cache_kind':'FULL' if isfull else 'THUMBNAIL',
   'saved_native_bytes':a['bytes'],'local_bytes':p.stat().st_size,
   'saved_native_content_hash':a['content_hash'],'local_dropbox_content_hash':actual,
   'matches_saved_native_bytes_and_hash':native,'local_sha256':key}
  by_key[key]=len(views);views.append(row)
 for start in range(0,len(views),12):
  part=views[start:start+12]; sheetno=start//12+1
  sheet=Image.new('RGB',(1600,1440),'#d8d8d8');d=ImageDraw.Draw(sheet)
  for j,a in enumerate(part):
   x=(j%4)*400;y=(j//4)*480
   im=Image.open(a['path']);im=ImageOps.exif_transpose(im).convert('RGB')
   im.thumbnail((390,413))
   sheet.paste(im,(x+(400-im.width)//2,y+4+(414-im.height)//2))
   tag='NATIVE BYTES' if a['matches_saved_native_bytes_and_hash'] else a['cache_kind']+' DERIVATIVE'
   d.text((x+8,y+422),f"{lane.upper()} {a['review_index']:03d} {a['group_ref']} {tag}",fill='black')
   d.text((x+8,y+438),a['asset_id'],fill='black')
   d.text((x+8,y+454),a['source_name'][:48],fill='black')
   a['contact_sheet']=f'{lane}-{sheetno:02}.jpg';a['sheet_tile']=j+1
  sheet.save(OUT/f'{lane}-{sheetno:02}.jpg',quality=92)
 manifest['cases'][lane]={'group_refs':refs,'asset_count':len(assets),'cached_full_asset_count':fullcount,
  'saved_native_bytes_match_count':nativecount,'distinct_cached_image_count':len(views),
  'views':views,'review_state':'PREPARED_NOT_YET_REVIEWED'}

labels=json.load(open(E/'Manufacturing_Labelled_References.json'))
target_rows={27,51,54,55,56,67,68,69,70,71,72,73,91}
m=[dict(x,source_index=i) for i,x in enumerate(labels) if x.get('row') in target_rows]
for start in range(0,len(m),12):
 part=m[start:start+12]; sheet=Image.new('RGB',(1600,1440),'#e0e0e0');d=ImageDraw.Draw(sheet)
 for j,a in enumerate(part):
  x=j%4*400;y=j//4*480
  im=Image.open(a['picture']['path']).convert('RGB');im.thumbnail((390,408))
  sheet.paste(im,(x+(400-im.width)//2,y+4+(410-im.height)//2))
  d.text((x+8,y+422),f"SOURCE ROW {a['row']} {a['code'].strip()}",fill='black')
  d.text((x+8,y+439),a['name'],fill='black')
  d.text((x+8,y+455),f"picture {a['picture']['index']:03d}; labelled index {a['source_index']}",fill='black')
  a['contact_sheet']=f'maker-{start//12+1:02}.jpg';a['sheet_tile']=j+1
 sheet.save(OUT/f'maker-{start//12+1:02}.jpg',quality=94)
manifest['maker_references']=m
(OUT/'visual-review-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({k:{q:v[q] for q in ['asset_count','cached_full_asset_count','saved_native_bytes_match_count','distinct_cached_image_count']} for k,v in manifest['cases'].items()},indent=2))
