"""Read native inventory searches and exact Commerce catalogue matches."""
import json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'social-publisher'))
from settings import Settings
from chrome import Chrome
from common import atomic_json, utc
c=Chrome(Settings(),ROOT/'social-publisher/state')
posts=json.loads((OUT/'posts.json').read_text())
matches=[];duplicates=[]
for p in posts:
 title=p['title']
 c.call('boldstone_facebook',{'op':'set_text','locator':[{'selector':'input[type=text]','name':'Search by ID or caption'}],'value':title})
 time.sleep(1.2)
 s=c.call('boldstone_facebook',{'op':'snapshot'})
 if title in s['text']: raise RuntimeError('Possible published duplicate: '+title)
 assert 'No activity during this date range' in s['text'],s['text'][-2000:]
 atomic_json(OUT/(p['catalogue_id']+'-native-duplicate-search.json'),s)
 duplicates.append({'catalogue_id':p['catalogue_id'],'query':title,'result':'NO_MATCH','scope':'Meta published inventory','utc':utc()})
 search=[{'selector':'input[type=text]','name':"Describe what you're looking for"}]
 c.call('verification',{'op':'set_text','locator':search,'value':''})
 c.call('verification',{'op':'set_text','locator':search,'value':title})
 choice=[{'selector':'div[id]','text':'Search by name, ID or brand for: "'+title+'"'}]
 c.call('verification',{'op':'click','locator':choice})
 deadline=time.monotonic()+15
 while True:
  if c.call('verification',{'op':'exists','locator':[{'selector':'input[type=checkbox]','name':'Select '+title}]})['exists']:break
  if time.monotonic()>deadline:raise RuntimeError('Missing Commerce product: '+title)
  time.sleep(.3)
 s=c.call('verification',{'op':'snapshot'})
 assert 'Products for Boldstone Sculpture (103781478537396)' in s['text']
 assert p['commerce_variant_id'] in s['text'] and ('£%.2f'%p['price_gbp']) in s['text'] and 'Eligible' in s['text']
 atomic_json(OUT/(p['catalogue_id']+'-commerce-search.json'),s)
 p['native_commerce_title']=title;p['native_commerce_price_text']='£%.2f'%p['price_gbp']
 matches.append({'catalogue_id':p['catalogue_id'],'name':title,'content_id':p['commerce_variant_id'],'price_text':p['native_commerce_price_text'],'catalogue_id_meta':'1638438493182970','status':'EXACT_MATCH','utc':utc()})
 print(title+': no published match; Commerce product verified',flush=True)
 atomic_json(OUT/'commerce-matches.json',matches)
 atomic_json(OUT/'native-duplicate-checks.json',duplicates)
atomic_json(OUT/'posts.json',posts)
