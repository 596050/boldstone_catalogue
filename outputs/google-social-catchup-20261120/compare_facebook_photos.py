"""Find very close pixel matches to photographs already planned for Google."""
import collections,json,math,sqlite3,sys
from pathlib import Path
from PIL import Image,ImageChops,ImageOps,ImageStat
OUT=Path(__file__).parent;ROOT=OUT.parents[1];sys.path.insert(0,str(ROOT/'social-publisher'))
from common import atomic_json,utc
def thumbnail(path):
 with Image.open(path) as source:
  source=ImageOps.exif_transpose(source);ratio=source.width/source.height
  if source.mode=='RGBA':
   base=Image.new('RGBA',source.size,'white');base.alpha_composite(source);source=base.convert('RGB')
  else:source=source.convert('RGB')
  return ratio,source.resize((64,64),Image.Resampling.LANCZOS)
targets={}
db=sqlite3.connect('file:'+str(ROOT/'social-publisher/state/outbox.sqlite3')+'?mode=ro',uri=True)
for raw in db.execute("SELECT payload FROM jobs WHERE channel_key='google_business_profile:15009857378722117958'"):
 p=json.loads(raw[0]);path=Path(p['media_path'])
 if p.get('media_type','').startswith('image/') and path.exists():targets.setdefault(str(path),{'google_post_keys':[]})['google_post_keys'].append(p['post_key'])
db.close()
for file in OUT.glob('history-*/prepared-posts.json'):
 if (file.parent/'delivery-prepared-posts.json').exists():file=file.parent/'delivery-prepared-posts.json'
 for row in json.loads(file.read_text()):
  if row.get('media_kind')=='video':continue
  path=row.get('delivery_media_path',row['media_path']);targets.setdefault(path,{'google_post_keys':[]})['google_post_keys'].append(row['google_post_key'])
for path,row in targets.items():row['ratio'],row['thumbnail']=thumbnail(path)
rows=json.loads((OUT/'facebook-unmatched-photo-receipts.json').read_text());results=[]
for row in rows:
 ratio,pic=thumbnail(row['media_path']);matches=[]
 for path,target in targets.items():
  if abs(ratio-target['ratio'])>.005:continue
  rms=ImageStat.Stat(ImageChops.difference(pic,target['thumbnail'])).rms;score=math.sqrt(sum(v*v for v in rms)/3)
  if score<=5:matches.append({'google_post_keys':sorted(set(target['google_post_keys'])),'media_path':path,'rgb_rms_64':score})
 results.append({'photo_id':row['photo_id'],'media_path':row['media_path'],'date':row['sources'][0]['publish_time'],'caption':row['caption'],'matches':sorted(matches,key=lambda r:r['rgb_rms_64'])[:5]})
atomic_json(OUT/'facebook-google-photo-comparison.json',{'utc':utc(),'method':'same aspect ratio within 0.005 and normalized 64-pixel RGB RMS at most 5; candidates require visual confirmation','photos_compared':len(rows),'candidate_matches':sum(bool(r['matches']) for r in results),'photos':results})
print(json.dumps({'photos_compared':len(rows),'candidate_matches':sum(bool(r['matches']) for r in results),'without_close_pixel_match':sum(not r['matches'] for r in results)}))
