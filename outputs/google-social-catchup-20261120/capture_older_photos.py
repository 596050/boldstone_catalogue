"""Read only owned Facebook sculpture posts and retain their visible cover photo."""
import json,re,sys,time,urllib.request
from pathlib import Path
from urllib.parse import urlparse
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'social-publisher'))
from source_chrome import SourceChrome as Chrome
from settings import Settings
from common import Hold,atomic_json,digest,read_json,utc

directory=OUT/'meta-reader-state';c=Chrome(Settings(),directory);name='boldstone_facebook'
groups=read_json(OUT/'history-audit.json')['groups']
decisions={r['source_key']:r['decision'] for r in read_json(OUT/'history-review-decisions-2026.json')['decisions']}
selected=[g for g in groups if decisions[g['source_key']] in {'INCLUDE_SCULPTURE','IMAGE_REVIEW_REQUIRED'} and
          any(s['platform']=='facebook' and s['post_type'] in {'Photos','Links'} for s in g['sources'])]
(OUT/'older-source-evidence').mkdir(exist_ok=True);(OUT/'history-media').mkdir(exist_ok=True)
receipts_path=OUT/'older-photo-source-receipts.json'
receipts=read_json(receipts_path) if receipts_path.exists() else []
done={r['source_key'] for r in receipts if r.get('status')=='SOURCE_PHOTO_VERIFIED'}
limit=int(sys.argv[1]) if len(sys.argv)>1 else len(selected)
for group in selected[:limit]:
 if group['source_key'] in done:continue
 source=next(s for s in group['sources'] if s['platform']=='facebook' and s['post_type'] in {'Photos','Links'})
 prefix=' '.join(group['caption'].split())[:100]
 try:
  parsed=urlparse(source['url']);assert parsed.scheme=='https' and parsed.hostname in ['www.facebook.com','facebook.com']
  c.navigate(name,source['url'],recovery=True)
  scope=[{'selector':'[role=dialog][aria-modal=true]','contains':prefix}]
  deadline=time.monotonic()+25
  while not c.call(name,{'op':'exists','locator':scope})['exists']:
   if time.monotonic()>deadline:raise Hold('SOURCE_POST_NOT_VISIBLE')
   time.sleep(.3)
  snap=c.call(name,{'op':'snapshot','scope':scope,'includeHTML':True})
  assert any(link['text']=='Boldstone Sculpture' and urlparse(link['href']).path.rstrip('/')=='/BoldstoneSculpture' for link in snap['links']),'Owned author not verified'
  photos=[i for i in snap['images'] if min(i['width'],i['height'])>=250 and (urlparse(i['src']).hostname or '').endswith('.fbcdn.net')]
  feed=[i for i in photos if 'data-imgperflogname="feedImage"' in i.get('html','')]
  if feed:photos=feed
  if not photos:raise Hold('SOURCE_PHOTO_NOT_VISIBLE')
  photo=photos[0]
  request=urllib.request.Request(photo['src'],headers={'User-Agent':'Mozilla/5.0','Referer':source['url']})
  with urllib.request.urlopen(request,timeout=25) as response:raw=response.read(5_000_001);mime=response.headers.get('Content-Type')
  assert len(raw)<=5_000_000 and raw[:2]==b'\xff\xd8',('Unsupported source image',mime,len(raw))
  path=OUT/'history-media'/('facebook-'+source['post_id']+'.jpg');path.write_bytes(raw)
  evidence=OUT/'older-source-evidence'/(source['post_id']+'.json');atomic_json(evidence,{'utc':utc(),'source':source,'snapshot':snap,'selected_photo':photo,'cover_photo_only':True})
  result={'utc':utc(),'status':'SOURCE_PHOTO_VERIFIED','source_key':group['source_key'],'sources':group['sources'],
          'caption':group['caption'],'media_path':str(path.resolve()),'sha256':digest(raw),'bytes':len(raw),
          'width':photo['width'],'height':photo['height'],'evidence_path':str(evidence.resolve()),'evidence_sha256':digest(evidence.read_bytes()),
          'visible_source_photo_count':len(photos),'source_cover_photo_preserved':True}
 except Exception as error:
  result={'utc':utc(),'status':'SOURCE_REVIEW_REQUIRED','source_key':group['source_key'],'sources':group['sources'],'error':str(error)}
 receipts=[r for r in receipts if r['source_key']!=group['source_key']]+[result];atomic_json(receipts_path,receipts)
 print(json.dumps({'source_post_id':source['post_id'],'status':result['status'],'error':result.get('error'),'source_photos_verified':sum(r['status']=='SOURCE_PHOTO_VERIFIED' for r in receipts)}),flush=True)
 if result.get('error') and any(code in result['error'] for code in ['FOREGROUND','OWNERSHIP','CHROME_NOT_RUNNING','TAB_NAVIGATED_EXTERNALLY','ACCOUNT_ACTION_REQUIRED','NORMAL_PROFILE_REQUIRED','APPLE_EVENT_PERMISSION']):break
