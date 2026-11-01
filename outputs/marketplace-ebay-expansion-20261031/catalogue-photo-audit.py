from pathlib import Path
import json,io
from urllib.request import urlopen
from concurrent.futures import ThreadPoolExecutor
from PIL import Image,ImageOps,ImageDraw
p=Path(__file__).resolve().parent
rows=json.loads((p.parent/'website-marketplace-refresh-20261031/website-final-plan.json').read_text())['products']
def get(r):
 if not r.get('primary_url'):return r,Image.new('RGB',(220,155),'lightgray')
 cache=p/(r['catalogue_id']+'.jpg')
 if cache.exists():im=Image.open(cache).convert('RGB')
 else:
  with urlopen(r['primary_url']+'?format=300w',timeout=45) as q:im=Image.open(io.BytesIO(q.read())).convert('RGB')
  im.save(cache)
 return r,ImageOps.contain(im,(220,155))
with ThreadPoolExecutor(max_workers=4) as ex:results=list(ex.map(get,rows))
for start in range(0,len(results),40):
 out=Image.new('RGB',(1200,1700),'white');draw=ImageDraw.Draw(out)
 for i,(r,im) in enumerate(results[start:start+40]):
  x=(i%5)*240;y=(i//5)*212;out.paste(im,(x+(240-im.width)//2,y));draw.text((x+5,y+157),str(start+i)+'. '+r['catalogue_id'],fill='black');draw.text((x+5,y+173),r['catalogue_name'][:35],fill='black');draw.text((x+5,y+186),r['catalogue_name'][35:70],fill='black')
 out.save(p/('catalogue-contact-'+str(start//40+1)+'.jpg'))
print('done',len(results))
