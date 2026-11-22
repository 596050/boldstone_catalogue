"""Recover carousel covers from the post's public Instagram embed HTML."""
import json,sys,urllib.request
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse
from PIL import Image
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'social-publisher'))
from source_chrome import SourceChrome
from common import atomic_json,digest,read_json,utc
from settings import Settings

class EmbedImages(HTMLParser):
 def __init__(self):super().__init__();self.images=[]
 def handle_starttag(self,tag,attrs):
  attrs=dict(attrs)
  if tag=='img' and 'EmbeddedMediaImage' in attrs.get('class','').split():self.images.append(attrs)

groups=read_json(OUT/'history-audit.json')['groups']
decisions={r['source_key']:r['decision'] for r in read_json(OUT/'history-review-decisions-2026.json')['decisions']}
verified=set()
for file in ['older-photo-source-receipts.json','older-instagram-photo-source-receipts.json','instagram-native-history-photo-receipts.json','instagram-embed-cover-receipts.json']:
 if (OUT/file).exists():verified.update(r['source_key'] for r in read_json(OUT/file) if r.get('status')=='SOURCE_PHOTO_VERIFIED')
selected=[g for g in groups if g['source_key'] not in verified and decisions.get(g['source_key'])=='INCLUDE_SCULPTURE' and
          any(s['platform']=='instagram' and s['post_type'] in ['IG image','IG carousel'] for s in g['sources'])]
c=SourceChrome(Settings(),OUT/'instagram-source-reader-state');name='verification'
receipt_file=OUT/'instagram-embed-cover-receipts.json';receipts=read_json(receipt_file) if receipt_file.exists() else []
evidence_dir=OUT/'embed-source-evidence';evidence_dir.mkdir(exist_ok=True)
for group in selected:
 source=next(s for s in group['sources'] if s['platform']=='instagram');code=urlparse(source['url']).path.rstrip('/').split('/')[-1]
 c.navigate(name,'https://www.instagram.com/p/'+code+'/embed/captioned/',recovery=True)
 snap=c.call(name,{'op':'snapshot','fullDocument':True,'includeHTML':True})
 assert any(urlparse(l['href']).path=='/boldstonesculpture/' and l['text']=='boldstonesculpture' for l in snap['links'])
 assert any(urlparse(l['href']).path=='/p/'+code+'/' for l in snap['links'])
 assert ' '.join(group['caption'].split()) in ' '.join(snap['text'].split()),'Exact original caption not present'
 parser=EmbedImages();parser.feed(snap['html']);assert len(parser.images)==1
 photo=parser.images[0];assert (urlparse(photo['src']).hostname or '').endswith('.cdninstagram.com')
 request=urllib.request.Request(photo['src'],headers={'User-Agent':'Mozilla/5.0','Referer':snap['url']})
 with urllib.request.urlopen(request,timeout=30) as response:raw=response.read(30_000_001)
 assert len(raw)<=30_000_000 and raw[:2]==b'\xff\xd8'
 path=OUT/'history-media'/('instagram-embed-'+code+'.jpg');path.write_bytes(raw);w,h=Image.open(path).size
 assert w>=400 and h>=300 and len(raw)<=5_000_000,(code,w,h,len(raw))
 evidence=evidence_dir/(code+'.json');atomic_json(evidence,{'utc':utc(),'source':source,'snapshot':snap,'selected_native_embed_image':photo,'cover_photo_only':True})
 receipt={'utc':utc(),'status':'SOURCE_PHOTO_VERIFIED','source_key':group['source_key'],'sources':group['sources'],'caption':group['caption'],
          'media_path':str(path.resolve()),'sha256':digest(raw),'bytes':len(raw),'width':w,'height':h,
          'evidence_path':str(evidence.resolve()),'evidence_sha256':digest(evidence.read_bytes()),'source_cover_photo_preserved':True,
          'method':'public Instagram embed DOM cover, exact native caption, author and source permalink; JPEG decoded locally'}
 receipts.append(receipt);atomic_json(receipt_file,receipts);print(json.dumps({'shortcode':code,'source_key':group['source_key'],'dimensions':[w,h],'bytes':len(raw)}),flush=True)
