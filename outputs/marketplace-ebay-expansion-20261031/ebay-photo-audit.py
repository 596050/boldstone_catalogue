from pathlib import Path
import json,io
from urllib.request import urlopen
from concurrent.futures import ThreadPoolExecutor
from PIL import Image,ImageOps,ImageDraw
p=Path(__file__).resolve().parent
rows=json.loads((p/'existing-wall-listings.json').read_text())
def get(r):
 with urlopen(r['photos'][0],timeout=45) as q: im=Image.open(io.BytesIO(q.read())).convert('RGB')
 return r,ImageOps.contain(im,(280,220))
out=Image.new('RGB',(1200,1400),'white');draw=ImageDraw.Draw(out)
with ThreadPoolExecutor(max_workers=4) as ex:
 for i,(r,im) in enumerate(ex.map(get,rows)):
  x=(i%4)*300;y=(i//4)*280;out.paste(im,(x+(300-im.width)//2,y));draw.text((x+5,y+222),str(i+1)+'. '+r['Item ID'],fill='black');draw.text((x+5,y+242),r['Title'][:38],fill='black')
out.save(p/'ebay-existing-contact-sheet.jpg')
print(p/'ebay-existing-contact-sheet.jpg')
