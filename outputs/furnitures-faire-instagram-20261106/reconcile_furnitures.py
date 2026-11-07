"""Read visible product cards from Chrome's saved HTML, without script data."""
from html.parser import HTMLParser
from urllib.parse import urlsplit,parse_qs
from decimal import Decimal
from datetime import datetime,timezone
from pathlib import Path
import json,re,hashlib
OUT=Path(__file__).parent
class Cards(HTMLParser):
 def __init__(self):super().__init__();self.rows=[];self.row=None
 def handle_starttag(self,tag,attrs):
  d=dict(attrs)
  if tag=='li':self.row=dict(text='',anchors=[],images=[])
  if self.row is not None:
   if tag=='a':self.row['anchors'].append(d)
   if tag=='img':self.row['images'].append(d)
 def handle_data(self,data):
  if self.row is not None:self.row['text']+=data+' '
 def handle_endtag(self,tag):
  if tag=='li' and self.row is not None:self.rows.append(self.row);self.row=None
read=lambda n:json.loads((OUT/n).read_text())
plan=read('furnitures-upload-plan.json');by={r['sku']:r for r in plan['records']}
bindings=read('furnitures-native-bindings.json');by_edit={r['edit_url']:r for r in bindings}
html=OUT/'evidence/furnitures-products-native.html';parser=Cards();parser.feed(html.read_text())
observed=[]
for card in parser.rows:
 edits=[a for a in card['anchors'] if a.get('aria-label','').startswith('Edit Boldstone')]
 if not edits:continue
 assert len(edits)==1
 a=edits[0];binding=by_edit['https://furnitures.co.uk'+a['href']];r=by[binding['sku']]
 assert a['aria-label']=='Edit '+r['title']
 assert ' active Living Room ' in card['text'] and re.search(r'\b1\s+in stock\b',card['text'])
 price=Decimal(re.search(r'£([\d,.]+)',card['text'])[1].replace(',',''));assert price==Decimal(str(r['price_gbp']))
 assert len(card['images'])==1
 image=parse_qs(urlsplit(card['images'][0]['src']).query)['url'][0]
 assert image==r['image_urls'][0]
 observed.append(dict(catalogue_id=r['catalogue_id'],sku=r['sku'],native_id=binding['native_id'],
  public_url=binding['public_url'],status='active',price_gbp=float(price),stock=1,primary_url=image))
assert len(observed)==176 and len({r['sku'] for r in observed})==176
photos=read('furnitures-photo-source-audit.json');assert photos==dict(compared=680,missing_hash=0,mismatch=[])
receipt=dict(status='PASS_176_NATIVE_ACTIVE_IDENTITIES_PRICES_STOCK_PRIMARY',checked_utc=datetime.now(timezone.utc).isoformat(),
 count=176,scope='Saved visible native product cards: exact identities, active status, category, asking price, one-stock indicator and primary image URL. Does not claim checkout/payout readiness or separate specification-field completeness.',
 source_html_sha256=hashlib.sha256(html.read_bytes()).hexdigest(),photo_hashes_compared=680,records=observed)
(OUT/'furnitures-native-reconciliation.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(dict(status=receipt['status'],count=176,photo_hashes_compared=680)))
