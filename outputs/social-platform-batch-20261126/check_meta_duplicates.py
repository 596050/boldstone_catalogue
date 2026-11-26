"""Inspect the current native Published inventory before preparing this batch."""
import json,sys,time
from pathlib import Path
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1]
sys.path[:0]=[str(ROOT/'social-publisher'),str(ROOT/'outputs/design-platform-registrations-20261123')]
import registration_browser as registration
registration.OUT=OUT
from common import atomic_json,utc
c=registration.browser();name='boldstone_facebook';rows=json.loads((OUT/'posts.json').read_text())['posts'];results=[]
locator=[{'selector':'input[type=text]','name':'Search by ID or caption'}]
for row in rows:
 c.call(name,{'op':'set_text','locator':locator,'value':''})
 deadline=time.monotonic()+25
 while True:
  snap=c.call(name,{'op':'snapshot','fullDocument':True})
  if any(x['name'].startswith('Select item with ID ') for x in snap['controls']):break
  if time.monotonic()>deadline:raise RuntimeError('Unfiltered inventory did not settle')
  time.sleep(.4)
 c.call(name,{'op':'set_text','locator':locator,'value':row['title']})
 deadline=time.monotonic()+25
 while True:
  snap=c.call(name,{'op':'snapshot','fullDocument':True})
  if row['title'] in snap['text']:
   result='FOUND';break
  if 'No activity during this date range' in snap['text']:
   result='NO_MATCH_IN_NATIVE_RANGE';break
  if time.monotonic()>deadline:raise RuntimeError('Search did not settle: '+row['title'])
  time.sleep(.4)
 atomic_json(OUT/(row['catalogue_id']+'-meta-duplicate-search.json'),snap)
 record={'catalogue_id':row['catalogue_id'],'title':row['title'],'result':result,'utc':utc(),'scope':'Native Meta Published inventory and its displayed date range'};results.append(record)
 atomic_json(OUT/'meta-duplicate-checks.json',results);print(json.dumps(record,ensure_ascii=False),flush=True)
 if result=='FOUND':raise RuntimeError('Existing post found; inspect before selecting this sculpture')
c.call(name,{'op':'set_text','locator':locator,'value':''})
