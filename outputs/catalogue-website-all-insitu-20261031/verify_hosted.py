from pathlib import Path
from datetime import datetime,timezone
from concurrent.futures import ThreadPoolExecutor,as_completed
from urllib.request import urlopen,Request
import json,time
OUT=Path(__file__).resolve().parent;plan=json.loads((OUT/'website-final-plan.json').read_text())
urls=sorted({a['url'] for p in plan['products'] for a in p['website_in_situ']})
def check(url):
 for attempt in range(3):
  try:
   with urlopen(Request(url+'?format=1500w',method='HEAD'),timeout=30) as r:
    content_type=r.headers.get('Content-Type','');assert r.status==200 and content_type.startswith('image/')
    return {'url':url,'status':'PASS','content_type':content_type,'content_length':r.headers.get('Content-Length')}
  except Exception as e:
   if attempt<2:time.sleep(2);continue
   return {'url':url,'status':'FAIL','error':type(e).__name__}
results=[]
with ThreadPoolExecutor(max_workers=6) as pool:
 for n,f in enumerate(as_completed(pool.submit(check,u) for u in urls),1):
  results.append(f.result())
  if n%100==0:print(json.dumps({'image_urls_checked':n,'failed':sum(r['status']!='PASS' for r in results)}),flush=True)
result={'status':'PASS_ALL_HOSTED_IMAGES' if all(r['status']=='PASS' for r in results) else 'FAIL','verified_utc':datetime.now(timezone.utc).isoformat(),'urls':len(urls),'results':results}
(OUT/'hosted-image-verification.json').write_text(json.dumps(result,indent=2));print(json.dumps({k:v for k,v in result.items() if k!='results'}))
