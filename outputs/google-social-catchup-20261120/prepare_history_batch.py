"""Freeze reviewed older sculpture posts with native-source photographs."""
import json,re,sqlite3,subprocess,sys,urllib.request
from PIL import Image
from pathlib import Path
from urllib.parse import urlencode
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'social-publisher'))
from common import atomic_json,digest,read_json,utc
from settings import Settings

part=sys.argv[1];limit=int(sys.argv[2]);folder=OUT/part;folder.mkdir(exist_ok=True)
if (folder/'manifest.json').exists():raise SystemExit('Frozen manifest exists; resume it rather than rebuilding.')
decisions={r['source_key']:r for r in read_json(OUT/'history-review-decisions-2026.json')['decisions']}
receipts=[]
for file in ['older-photo-source-receipts.json','older-instagram-photo-source-receipts.json','instagram-native-history-photo-receipts.json','instagram-embed-cover-receipts.json']:
 if (OUT/file).exists():receipts.extend(read_json(OUT/file))
db=sqlite3.connect('file:'+str(ROOT/'social-publisher/state/outbox.sqlite3')+'?mode=ro',uri=True)
existing={r[0] for r in db.execute('SELECT post_key FROM jobs')};db.close()
posts=[];prepared=[];seen=set()
for r in receipts:
 key=r['source_key'];post_key='META-HISTORY-'+key[:32]
 if r.get('status')!='SOURCE_PHOTO_VERIFIED' or decisions.get(key,{}).get('decision')!='INCLUDE_SCULPTURE' or key in seen or post_key in existing:continue
 if not any(s['post_type'] in {'Photos','IG image','IG carousel','Links'} for s in r['sources']):continue
 seen.add(key)
 media=Path(r['media_path']);assert digest(media.read_bytes())==r['sha256'] and media.stat().st_size<=30_000_000
 delivery=media;sha=r['sha256'];w,h=Image.open(media).size
 if media.suffix.lower() not in {'.png','.jpg','.jpeg'} or media.stat().st_size>5_000_000:
  copies=OUT/'google-delivery-media';copies.mkdir(exist_ok=True);delivery=copies/(post_key+'.png')
  for maximum in [1600,1400,1200,1000]:
   with Image.open(media) as pic:
    pic.thumbnail((maximum,maximum));pic.save(delivery,format='PNG')
   if delivery.stat().st_size<=5_000_000:break
  assert delivery.stat().st_size<=5_000_000
  sha=digest(delivery.read_bytes());w,h=Image.open(delivery).size
 if w<400 or h<300:
  resize_source=delivery
  copies=OUT/'google-delivery-media';copies.mkdir(exist_ok=True);delivery=copies/(post_key+'-minimum.png')
  if not delivery.exists():
   option='--resampleWidth' if 400/w>=300/h else '--resampleHeight';size='400' if option=='--resampleWidth' else '300'
   subprocess.run(['/usr/bin/sips','-s','format','png',option,size,str(resize_source),'--out',str(delivery)],check=True,capture_output=True)
  dw,dh=Image.open(delivery).size;assert dw>=400 and dh>=300 and abs(dw/dh-w/h)<.01
  sha=digest(delivery.read_bytes());assert delivery.stat().st_size<=5_000_000
 assert digest(Path(r['evidence_path']).read_bytes())==r['evidence_sha256']
 text=re.sub(r'https?://\S+','',r['caption']);text=re.sub(r'#\w+','',text)
 parts=[]
 for paragraph in text.split('\n\n'):
  paragraph=paragraph.strip()
  if not paragraph or re.fullmatch(r'(?i)(?:discover|explore|find out|see|learn|read)\s+more\s*(?:at|on)?\s*[.!]?',paragraph):continue
  if re.fullmatch(r'(?i)(?:www\.)?boldstonesculpture\.com[.!]?',paragraph):continue
  if re.search(r'(?i)\b(?:swipe|link in (?:our |the )?bio|product tag)\b',paragraph):continue
  parts.append(paragraph)
 caption='\n\n'.join(parts)+'\n\nFrom the Boldstone sculpture archive. Use Learn more to explore sculptures and commissions on our website.'
 assert 0<len(caption)<=1500,(r['caption'][:80],len(caption))
 title=r['caption'].split('\n')[0][:180]
 url='https://boldstonesculpture.com/?'+urlencode({'utm_source':'google_business_profile','utm_medium':'social','utm_campaign':'sculpture_archive_catchup_20261120','utm_content':key[:16]})
 post={'post_key':post_key,'title':title,'alt_text':title,'media_path':str(delivery.resolve()),'sha256':sha,
       'targets':{'boldstone_google_business_profile':{'caption':caption,'purchase_url':url,'button_label':'Learn more'}}}
 posts.append(post);prepared.append({**r,'delivery_media_path':str(delivery.resolve()),'delivery_sha256':sha,'google_post_key':post_key,'google_caption':caption,'google_url':url,'google_button':'Learn more','review_decision':decisions[key]})
 if len(posts)>=limit:break
assert posts,'No new reviewed source photographs'
request=urllib.request.Request('https://boldstonesculpture.com/',headers={'User-Agent':'Mozilla/5.0'})
with urllib.request.urlopen(request,timeout=30) as response:
 assert response.status==200 and 'boldstonesculpture.com' in response.url
 atomic_json(folder/'website-check.json',{'utc':utc(),'url':response.url,'status':response.status})
manifest={'schema_version':1,'batch_id':'google-social-catchup-20261120-'+part,'publish_authorized':True,'posts':posts}
atomic_json(folder/'prepared-posts.json',prepared);atomic_json(folder/'manifest.json',manifest)
jobs=Settings().jobs(folder/'manifest.json')
print(json.dumps({'batch_id':manifest['batch_id'],'posts':len(posts),'jobs':len(jobs),'max_caption':max(len(p['google_caption']) for p in prepared)}))
