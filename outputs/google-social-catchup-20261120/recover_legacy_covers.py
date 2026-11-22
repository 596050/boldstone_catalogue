"""Recover missing legacy covers from public, rendered Instagram embeds."""
import json,sys,urllib.request
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse
from PIL import Image
OUT=Path(__file__).parent;ROOT=OUT.parents[1]
sys.path[:0]=[str(ROOT/'social-publisher'),str(OUT)]
from source_chrome import SourceChrome
from common import atomic_json,digest,utc
from settings import Settings
class Images(HTMLParser):
 def __init__(self):super().__init__();self.photos=[]
 def handle_starttag(self,t,a):
  a=dict(a)
  if t=='img' and 'EmbeddedMediaImage' in a.get('class','').split():self.photos.append(a)
file=OUT/'legacy-embed-cover-receipts.json';receipts=json.loads(file.read_text()) if file.exists() else []
done={r['source_key'] for r in receipts if r.get('status')=='SOURCE_PHOTO_VERIFIED'}
rows=json.loads((OUT/'history-review-decisions-legacy.json').read_text())['decisions']
c=SourceChrome(Settings(),OUT/'instagram-source-reader-state');name='verification'
for row in rows:
 if row['source_key'] in done or row['photo'] or row['decision'] not in {'INCLUDE_SCULPTURE','IMAGE_REVIEW_REQUIRED'}:continue
 code=row['shortcode']
 try:
  c.navigate(name,'https://www.instagram.com/p/'+code+'/embed/captioned/',recovery=True)
  snap=c.call(name,{'op':'snapshot','fullDocument':True,'includeHTML':True})
  assert any(urlparse(l['href']).path=='/boldstonesculpture/' and l['text']=='boldstonesculpture' for l in snap['links'])
  assert any(urlparse(l['href']).path=='/p/'+code+'/' for l in snap['links'])
  assert ' '.join(row['caption'].split()) in ' '.join(snap['text'].split()),'Original caption missing'
  parser=Images();parser.feed(snap['html']);assert len(parser.photos)==1
  photo=parser.photos[0];assert (urlparse(photo['src']).hostname or '').endswith('.cdninstagram.com')
  request=urllib.request.Request(photo['src'],headers={'User-Agent':'Mozilla/5.0','Referer':snap['url']})
  with urllib.request.urlopen(request,timeout=30) as response:raw=response.read(30_000_001)
  assert len(raw)<=30_000_000
  path=OUT/'history-media'/('instagram-legacy-embed-'+code+'.jpg');path.write_bytes(raw)
  with Image.open(path) as im:im.verify()
  w,h=Image.open(path).size
  evidence=OUT/'embed-source-evidence'/('legacy-'+code+'-'+digest(snap)[:12]+'.json')
  atomic_json(evidence,{'utc':utc(),'source':row['sources'][0],'snapshot':snap,'selected_native_embed_image':photo,'cover_photo_only':True})
  result={'utc':utc(),'status':'SOURCE_PHOTO_VERIFIED','source_key':row['source_key'],'shortcode':code,'sources':row['sources'],'caption':row['caption'],
    'media_path':str(path.resolve()),'sha256':digest(raw),'bytes':len(raw),'width':w,'height':h,'evidence_path':str(evidence.resolve()),'evidence_sha256':digest(evidence.read_bytes()),'source_cover_photo_preserved':True}
 except Exception as error:result={'source_key':row['source_key'],'shortcode':code,'status':'SOURCE_REVIEW_REQUIRED','error':str(error)}
 receipts=[r for r in receipts if r['source_key']!=row['source_key']]+[result];atomic_json(file,receipts)
 print(json.dumps({k:v for k,v in result.items() if k in {'shortcode','status','error','width','height'}}),flush=True)
