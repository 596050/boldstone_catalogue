"""Freeze approved original-sculpture legacy photographs for Google."""
import json,re,sqlite3,subprocess,sys,urllib.request
from pathlib import Path
from urllib.parse import urlencode
from PIL import Image
OUT=Path(__file__).parent;ROOT=OUT.parents[1]
sys.path.insert(0,str(ROOT/'social-publisher'))
from common import atomic_json,digest,utc
from settings import Settings
folder=OUT/sys.argv[1];folder.mkdir(exist_ok=True)
assert not (folder/'manifest.json').exists(),'Resume the frozen manifest instead'
rows=json.loads((OUT/'history-review-decisions-legacy.json').read_text())['decisions']
extra=json.loads((OUT/'legacy-embed-cover-receipts.json').read_text()) if (OUT/'legacy-embed-cover-receipts.json').exists() else []
sources={r['shortcode']:r for r in extra if r.get('status')=='SOURCE_PHOTO_VERIFIED'}
existing=set()
for file in OUT.glob('history-*/manifest.json'):existing.update(p['post_key'] for p in json.loads(file.read_text())['posts'])
replacement={
 'CrTwxmYLwiv':'An earlier studio preview of sculptural forms from Boldstone.',
 'CrTxUyFr6JC':'A studio study of vertical sculptural forms from the Boldstone archive.',
 'CUat9E2IoSg':'Sand Ripple Smooth and Textured Sand Ripple, shown at the 2021 Chelsea Flower Show. These sculptures explore water and sand ripples through contrasting smooth and textured surfaces, displayed against a rust-coloured wall.',
 'CTzFZ_qocVx':'Light and shadow on a Boldstone wall sculpture, photographed during preparations for the September 2021 Chelsea Flower Show.',
 'CTiOXt6ohLC':'Moon Fishwave, from the Boldstone sculpture display at the September 2021 Chelsea Flower Show. The work draws on patterns in nature, light and shadow.',
 'CUm5rMsIL5w':'Detail of Growing Leaves, shown on a contrasting orange-red wall at the 2021 Chelsea Flower Show. The original caption records dimensions of 100 × 30 cm.',
}
posts=[];prepared=[]
for row in rows:
 if row['decision']!='INCLUDE_SCULPTURE' or row['sources'][0]['post_type']=='IG reel':continue
 code=row['shortcode'];key='INSTAGRAM-ARCHIVE-'+code
 if key in existing:continue
 r=row.get('photo') or sources.get(code)
 if not r or r.get('status')!='SOURCE_PHOTO_VERIFIED':continue
 media=Path(r['media_path']);assert digest(media.read_bytes())==r['sha256']
 assert digest(Path(r['evidence_path']).read_bytes())==r['evidence_sha256']
 delivery=media;w,h=Image.open(media).size
 if media.stat().st_size>5_000_000 or media.suffix.lower() not in {'.jpg','.jpeg','.png'}:
  delivery=OUT/'google-delivery-media'/(key+'.png')
  for maximum in [1600,1400,1200,1000]:
   with Image.open(media) as im:im.thumbnail((maximum,maximum));im.save(delivery,format='PNG')
   if delivery.stat().st_size<=5_000_000:break
  w,h=Image.open(delivery).size
 if w<400 or h<300:
  origin=delivery;delivery=OUT/'google-delivery-media'/(key+'-minimum.png')
  option='--resampleWidth' if 400/w>=300/h else '--resampleHeight';size='400' if option=='--resampleWidth' else '300'
  subprocess.run(['/usr/bin/sips','-s','format','png',option,size,str(origin),'--out',str(delivery)],capture_output=True,check=True)
 w,h=Image.open(delivery).size;assert w>=400 and h>=300 and delivery.stat().st_size<=5_000_000
 text=re.sub(r'#\w+','',row['caption']);text=re.sub(r'https?://\S+|\b(?:www\.)?boldstone(?:sculpture)?\.(?:co\.uk|com)\b|\S+@\S+','',text,flags=re.I)
 paragraphs=[]
 for para in text.split('\n\n'):
  para=para.strip().replace('\u200b','')
  if not para or re.search(r'(?i)\b(?:swipe|link in bio|drop a|DM|inquir|enquir|follow to|come and|find out more|see more|contact us|made to order|ready to transform|who else|which spot)\b',para):continue
  paragraphs.append(para)
 text=replacement.get(code,'\n\n'.join(paragraphs)).strip()
 if not text:text='A wall sculpture from the Boldstone archive, exploring surface, form, light and shadow.'
 # Frame historical photographs as archive material, without dated availability claims.
 year=row['sources'][0]['publish_time'][:4]
 caption=text+'\n\nFrom the Boldstone sculpture archive ('+year+'). Use Learn more to explore sculptures and commissions on our website.'
 assert 0<len(caption)<=1500,(code,len(caption))
 title=(text.split('\n')[0] or 'Boldstone archive sculpture')[:180]
 url='https://boldstonesculpture.com/?'+urlencode({'utm_source':'google_business_profile','utm_medium':'social','utm_campaign':'sculpture_archive_catchup_20261120','utm_content':code})
 sha=digest(delivery.read_bytes())
 posts.append({'post_key':key,'title':title,'alt_text':title,'media_path':str(delivery.resolve()),'sha256':sha,'targets':{'boldstone_google_business_profile':{'caption':caption,'purchase_url':url,'button_label':'Learn more'}}})
 prepared.append({**r,'source_key':row['source_key'],'sources':row['sources'],'caption':row['caption'],'shortcode':code,'google_post_key':key,'delivery_media_path':str(delivery.resolve()),'delivery_sha256':sha,'google_caption':caption,'google_url':url,'google_button':'Learn more','review_decision':{k:v for k,v in row.items() if k not in {'photo','native_record'}},'title':title})
assert posts
request=urllib.request.Request('https://boldstonesculpture.com/',headers={'User-Agent':'Mozilla/5.0'})
with urllib.request.urlopen(request,timeout=30) as response:
 assert response.status==200
 atomic_json(folder/'website-check.json',{'utc':utc(),'url':response.url,'status':response.status})
manifest={'schema_version':1,'batch_id':'google-social-catchup-20261120-'+folder.name,'publish_authorized':True,'posts':posts}
atomic_json(folder/'prepared-posts.json',prepared);atomic_json(folder/'manifest.json',manifest)
jobs=Settings().jobs(folder/'manifest.json');print(json.dumps({'posts':len(posts),'jobs':len(jobs),'batch_id':manifest['batch_id']}))
