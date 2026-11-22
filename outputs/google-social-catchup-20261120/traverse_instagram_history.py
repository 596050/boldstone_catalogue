"""Read owned posts using Instagram's native Next control, without taking focus."""
import hashlib,io,json,re,sys,time,unicodedata,urllib.request
from PIL import Image
from pathlib import Path
from urllib.parse import urlparse
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'social-publisher'))
from source_chrome import SourceChrome
from chrome import Chrome
from settings import Settings
from common import Hold,atomic_json,digest,read_json,utc

def core(caption):
 text=re.sub(r'https?://\S+','',caption);text=re.sub(r'#\w+','',text)
 text=re.sub(r'(?im)[^\n.!?]*\b(?:product tag|tagged product|link in (?:our |the )?bio)\b[^\n.!?]*(?:[.!?]|$)','',text)
 text='\n\n'.join(p for p in text.split('\n\n') if not re.match(r'(?i)^\s*(?:Shop this sculpture|View this sculpture and order|For homes, gardens and design projects\. View|For homes, gardens and design projects\. View the individual sculpture|See the sculpture, current price)',p))
 return ' '.join(unicodedata.normalize('NFKC',text).casefold().split()).strip()

c=SourceChrome(Settings(),OUT/'instagram-reader-state');name='verification'
export={r['Permalink'].rstrip('/').split('/')[-1]:r for r in read_json(OUT/'meta-instagram-2026-rows.json')}
groups=read_json(OUT/'history-audit.json')['groups'];source_by_code={s['url'].rstrip('/').split('/')[-1]:(g,s) for g in groups for s in g['sources'] if s['platform']=='instagram'}
included={r['source_key'] for r in read_json(OUT/'history-review-decisions-2026.json')['decisions'] if r['decision']=='INCLUDE_SCULPTURE'}
records_path=OUT/'instagram-native-history-posts.json';records=read_json(records_path) if records_path.exists() else []
by_code={r['shortcode']:r for r in records}
receipts_path=OUT/'instagram-native-history-photo-receipts.json';receipts=read_json(receipts_path) if receipts_path.exists() else []
evidence_dir=OUT/'all-history-native-source';evidence_dir.mkdir(exist_ok=True)
for index in range(665):
 deadline=time.monotonic()+15
 while True:
  try:s=c.call(name,{'op':'source_modal'});break
  except Hold as error:
   if error.code not in {'SOURCE_AUTHOR_OR_CAPTION_MISSING','SOURCE_POST_AMBIGUOUS'} or time.monotonic()>deadline:raise
   time.sleep(.4)
 code=urlparse(s['url']).path.rstrip('/').split('/')[-1];key=digest(core(s['caption']).encode()) if core(s['caption']) else 'instagram:'+code
 if code in export and core(s['caption'])!=core(export[code]['Description']):raise Hold('SOURCE_CAPTION_DIFFERS_FROM_NATIVE_EXPORT',code)
 evidence=evidence_dir/(code+'-'+digest(s)[:12]+'.json')
 if not evidence.exists():atomic_json(evidence,{'utc':utc(),'source':s,'read_only':True})
 record={'utc':utc(),'shortcode':code,'source_key':key,'source':s,'evidence_path':str(evidence.resolve()),'evidence_sha256':digest(evidence.read_bytes()),'in_2026_export':code in export}
 by_code[code]=record;atomic_json(records_path,list(by_code.values()))
 known_photos=set()
 for file in ['older-photo-source-receipts.json','older-instagram-photo-source-receipts.json','instagram-native-history-photo-receipts.json']:
  f=OUT/file
  if f.exists():known_photos.update(r['source_key'] for r in read_json(f) if r.get('status')=='SOURCE_PHOTO_VERIFIED')
 wanted=(code not in export or key in included) and key not in known_photos
 if wanted and s['photos']:
  try:
   photo=s['photos'][0];host=urlparse(photo['src']).hostname or ''
   if not host.endswith(('.cdninstagram.com','.fbcdn.net')):raise Hold('SOURCE_PHOTO_HOST_REFUSED')
   request=urllib.request.Request(photo['src'],headers={'User-Agent':'Mozilla/5.0','Referer':s['url']})
   with urllib.request.urlopen(request,timeout=25) as response:raw=response.read(30_000_001)
   if len(raw)>30_000_000:raise Hold('SOURCE_PHOTO_TOO_LARGE_FOR_REVIEW')
   decoded=Image.open(io.BytesIO(raw));decoded.verify();extension={'JPEG':'.jpg','PNG':'.png','WEBP':'.webp'}.get(decoded.format)
   if not extension:raise Hold('SOURCE_PHOTO_FORMAT_REFUSED')
   image=OUT/'history-media'/('instagram-native-'+code+'-'+digest(raw)[:12]+extension)
   if not image.exists():image.write_bytes(raw)
   g,source=source_by_code.get(code,(None,{'platform':'instagram','post_id':'instagram:'+code,'url':s['url'],'post_type':'IG reel' if s['videos'] else 'IG image','publish_time':s['times'][-1]['datetime'] if s['times'] else None}))
   receipt={'utc':utc(),'status':'SOURCE_PHOTO_VERIFIED','source_key':key,'sources':g['sources'] if g else [source],'caption':s['caption'],
            'media_path':str(image.resolve()),'sha256':digest(raw),'bytes':len(raw),'width':decoded.width,'height':decoded.height,
            'evidence_path':str(evidence.resolve()),'evidence_sha256':digest(evidence.read_bytes()),'source_cover_photo_preserved':True,'native_modal_author_verified':True,'source_video_count':len(s['videos'])}
  except Exception as error:
   receipt={'utc':utc(),'status':'SOURCE_PHOTO_REVIEW_REQUIRED','source_key':key,'shortcode':code,'error':str(error),'evidence_path':str(evidence.resolve())}
  receipts=[r for r in receipts if r['source_key']!=key]+[receipt];atomic_json(receipts_path,receipts)
 union=set(export)|set(by_code)
 atomic_json(OUT/'instagram-history-coverage-progress.json',{'utc':utc(),'expected_profile_posts':653,'covered_unique_posts':len(union),'native_posts_read':len(by_code),'photos_recovered':len(receipts),'next_available':s['next_available'],'status':'NATIVE_HISTORY_IN_PROGRESS'})
 print(json.dumps({'index':index,'shortcode':code,'title':s['caption'].split('\n')[0][:100],'in_2026_export':code in export,'photos':len(s['photos']),'videos':len(s['videos']),'covered_unique_posts':len(union)}),flush=True)
 if not s['next_available']:break
 old=s['url'];Chrome.call(c,name,{'op':'click','locator':[{'selector':'div._abm0:has(svg[aria-label=Next])'}]})
 binding=c.bindings[name];deadline=time.monotonic()+15
 while True:
  state=c.state_for(binding);_,tab=c.find(state,binding['window_id'],binding['tab_id'])
  if c.target_foreground(state,binding):raise Hold('FOREGROUND_TAB_PAUSED')
  if tab['url']!=old and re.fullmatch(r'https://www\.instagram\.com/(?:boldstonesculpture/)?p/[^/?]+/(?:\?img_index=\d+)?',tab['url']):
   Settings.check_url(c.profile(name),tab['url']);binding['url']=tab['url'];c.save_bindings();c.call(name,{'op':'claim'});break
  if time.monotonic()>deadline:raise Hold('SOURCE_NEXT_NAVIGATION_NOT_OBSERVED')
  time.sleep(.3)
