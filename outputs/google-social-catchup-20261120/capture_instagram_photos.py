"""Retain the visible cover of original owned Instagram sculpture posts."""
import json,sys,time,urllib.request
from pathlib import Path
from urllib.parse import urlparse

ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'social-publisher'))
from source_chrome import SourceChrome as Chrome
from settings import Settings
from common import Hold,atomic_json,digest,read_json,utc

c=Chrome(Settings(),OUT/'instagram-source-reader-state');name='verification'
groups=read_json(OUT/'history-audit.json')['groups']
decisions={r['source_key']:r['decision'] for r in read_json(OUT/'history-review-decisions-2026.json')['decisions']}
selected=[g for g in groups if decisions[g['source_key']] in {'INCLUDE_SCULPTURE','IMAGE_REVIEW_REQUIRED'} and
          not any(s['platform']=='facebook' for s in g['sources']) and
          any(s['platform']=='instagram' and s['post_type'] in ['IG image','IG carousel'] for s in g['sources'])]
receipts_path=OUT/'older-instagram-photo-source-receipts.json'
receipts=read_json(receipts_path) if receipts_path.exists() else []
done={r['source_key'] for r in receipts if r.get('status')=='SOURCE_PHOTO_VERIFIED'}
for group in selected:
 if group['source_key'] in done:continue
 source=next(s for s in group['sources'] if s['platform']=='instagram')
 try:
  assert urlparse(source['url']).hostname=='www.instagram.com'
  c.navigate(name,source['url'],recovery=True)
  deadline=time.monotonic()+25
  while True:
   snap=c.call(name,{'op':'snapshot','scope':[{'selector':'main'}],'includeHTML':True})
   if ' '.join(group['caption'].split())[:100] in ' '.join(snap['text'].split()):break
   if time.monotonic()>deadline:raise Hold('SOURCE_CAPTION_NOT_VISIBLE')
   time.sleep(.3)
  assert any(l['text']=='boldstonesculpture' and urlparse(l['href']).path=='/boldstonesculpture/' for l in snap['links']),'Owned author not verified'
  photos=[i for i in snap['images'] if min(i['width'],i['height'])>=250 and (urlparse(i['src']).hostname or '').endswith('.cdninstagram.com')]
  if not photos:raise Hold('SOURCE_PHOTO_NOT_VISIBLE')
  photo=photos[0]
  # The original post precedes Instagram's separately linked recommendation grid.
  if 'More posts from' in snap['text']:
   assert snap['html'].find(photo['src'].split('?')[0]) < snap['html'].find('More posts from'),'Related photo refused'
  request=urllib.request.Request(photo['src'],headers={'User-Agent':'Mozilla/5.0','Referer':source['url']})
  with urllib.request.urlopen(request,timeout=25) as response:raw=response.read(5_000_001)
  assert len(raw)<=5_000_000 and raw[:2]==b'\xff\xd8','Unsupported source image'
  path=OUT/'history-media'/('instagram-'+source['post_id']+'.jpg');path.write_bytes(raw)
  evidence=OUT/'older-source-evidence'/('instagram-'+source['post_id']+'.json')
  atomic_json(evidence,{'utc':utc(),'source':source,'snapshot':snap,'selected_photo':photo,'cover_photo_only':True})
  result={'utc':utc(),'status':'SOURCE_PHOTO_VERIFIED','source_key':group['source_key'],'sources':group['sources'],
          'caption':group['caption'],'media_path':str(path.resolve()),'sha256':digest(raw),'bytes':len(raw),
          'width':photo['width'],'height':photo['height'],'evidence_path':str(evidence.resolve()),'evidence_sha256':digest(evidence.read_bytes()),
          'source_cover_photo_preserved':True,'source_post_type':source['post_type']}
 except Exception as error:
  result={'utc':utc(),'status':'SOURCE_REVIEW_REQUIRED','source_key':group['source_key'],'sources':group['sources'],'error':str(error)}
 receipts=[r for r in receipts if r['source_key']!=group['source_key']]+[result];atomic_json(receipts_path,receipts)
 print(json.dumps({'source_post_id':source['post_id'],'status':result['status'],'error':result.get('error'),'source_photos_verified':sum(r['status']=='SOURCE_PHOTO_VERIFIED' for r in receipts)}),flush=True)
 if result.get('error') and any(code in result['error'] for code in ['FOREGROUND','OWNERSHIP','CHROME_NOT_RUNNING','TAB_NAVIGATED_EXTERNALLY','ACCOUNT_ACTION_REQUIRED','NORMAL_PROFILE_REQUIRED','APPLE_EVENT_PERMISSION']):break
