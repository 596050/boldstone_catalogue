"""Build narrowly scoped supplemental fields for existing public catalogue IDs."""
from pathlib import Path
from html.parser import HTMLParser
import json,csv
OUT=Path(__file__).resolve().parent
plan=json.loads((OUT/'website-final-plan.json').read_text())
verified=json.loads((OUT/'gallery-native-verification.json').read_text())
assert verified['status']=='PASS_NATIVE_GALLERIES_AND_PRESERVED_FIELDS' and verified['products']==176
with (OUT/'inventory-gallery-final.csv').open(encoding='utf-8-sig') as f:native={r['Variant ID [Non Editable]']:r for r in csv.DictReader(f)}
with (OUT/'meta-feed-current.xml').open(encoding='utf-8-sig') as f:meta={r['id']:r for r in csv.DictReader(f)}
class Text(HTMLParser):
 def __init__(self):super().__init__();self.parts=[]
 def handle_data(self,s):self.parts.append(s)
 def handle_endtag(self,t):
  if t in ('p','li','ul','h2'):self.parts.append('\n')
meta_rows=[];google_rows=[];caps=[]
for p in plan['products']:
 if not p.get('public'):continue
 vid=p['variant_id'];r=native[vid];assert r['Visible']=='Yes' and meta[vid]['link'].split('?')[0]==p['website_url']
 assert float(r['Weight'])>0,(vid,'Missing packed shipping weight')
 assert r['On Sale']=='No',(vid,'Sale price requires separate handling')
 urls=[a['url'] for a in p['website_gallery']];assert urls[0]==p['primary_url'] and len(urls)==len(set(urls))
 meta_rows.append({'id':vid,'additional_image_link':','.join(urls[1:]),'custom_label_0':'Wall Sculptures','custom_label_1':p['family']})
 text=Text();text.feed(p['published_description_html']);description='\n'.join(x.strip() for x in ''.join(text.parts).splitlines() if x.strip())
 google_rows.append({'id':vid,'title':p['retail_name'],'description':description,'price':r['Price']+' GBP','image_link':urls[0],'additional_image_link':','.join(urls[1:11]),'shipping_weight':r['Weight']+' lb','custom_label_0':'Wall Sculptures','custom_label_1':p['family']})
 if len(urls)>11:caps.append({'catalogue_id':p['catalogue_id'],'name':p['retail_name'],'website_photos':len(urls),'google_photos':11})
assert len(meta_rows)==len(google_rows)==176
payload={'snapshot_event_cutoff':plan.get('event_cutoff'),'meta':{'headers':list(meta_rows[0]),'rows':meta_rows},'google':{'headers':list(google_rows[0]),'rows':google_rows},'google_image_limit_products':caps,'scope':'Existing public wall sculptures only; no new products or changes to unrelated products'}
(OUT/'channel-supplement-manifest.json').write_text(json.dumps(payload,indent=2,ensure_ascii=False))
print({'meta_rows':len(meta_rows),'google_rows':len(google_rows),'google_image_cap_applied':len(caps)})
