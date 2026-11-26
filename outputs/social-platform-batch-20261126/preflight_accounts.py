"""Inspect only task-created background tabs; no publication or account submission."""
import json,sys
from pathlib import Path
from urllib.parse import urlsplit
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1]
sys.path[:0]=[str(ROOT/'social-publisher'),str(ROOT/'outputs/design-platform-registrations-20261123')]
import registration_browser as registration
registration.OUT=OUT
from common import atomic_json,utc,Hold
from settings import Settings

settings=Settings()
targets={
 'archiproducts':(962005871,'https://www.archiproducts.com/',['www.archiproducts.com','business.archiproducts.com','account.archipassport.com']),
 'architonic':(962005874,'https://www.architonic.com/en/about-us',['www.architonic.com','business.architonic.com']),
 'archilovers':(962005877,'https://www.archilovers.com/',['www.archilovers.com','account.archipassport.com']),
 'sally_linkedin':(962005880,'https://www.linkedin.com/in/sally-price-1193858a/',None),
 'boldstone_google_business_profile':(962005883,settings.profile('boldstone_google_business_profile')['inventory_url'],None),
 'boldstone_facebook':(962005886,settings.profile('boldstone_facebook')['inventory_url'],None),
 'boldstone_threads':(962005889,settings.profile('boldstone_threads')['inventory_url'],None),
}
profiles={}
for name,(_,url,hosts) in targets.items():
 profiles[name]={'allowed_hosts':hosts,'start_url':url} if hosts else {**settings.profile(name),'start_url':url}
path=OUT/'registration-config.json';data={'email':'info@boldstone.co.uk','final_action_by_user':True,'profiles':profiles}
if path.exists():assert json.loads(path.read_text())==data
else:atomic_json(path,data)
c=registration.browser();inventory=c.inventory();atomic_json(OUT/'focus-baseline.json',{'utc':utc(),'focus':c.focus_stamp(inventory)})
results=[]
for name,(tid,url,hosts) in targets.items():
 try:
  if name not in c.bindings:
   matches=[(w,t) for w in inventory['windows'] for t in w['tabs'] if t['tab_id']==tid];assert len(matches)==1
   w,t=matches[0];assert t['url']=='about:blank';c.bind(name,w['window_id'],tid)
   try:c.navigate(name,url)
   except Hold as error:
    if error.code!='NAVIGATION_TIMEOUT':raise
    b=c.bindings[name];state=c.state_for(b);_,actual=c.find(state,b['window_id'],b['tab_id']);u=urlsplit(actual['url'])
    if actual['loading'] or u.hostname not in c.profile(name)['allowed_hosts']:raise
    b.update(url=actual['url']);b.pop('pending_url',None);c.save_bindings()
  snap=c.call(name,{'op':'snapshot','fullDocument':True,'includeHTML':True});atomic_json(OUT/(name+'-preflight.json'),{'utc':utc(),'snapshot':snap})
  result={'platform':name,'tab_id':tid,'url':snap['url'],'title':snap['title'],'state':'INSPECTED'}
  print(json.dumps({**result,'text':snap['text'][:4500],'inputs':[i for i in snap['inputs'] if 'type="password"' not in i['html']][:8],'controls':snap['controls'][:18]},ensure_ascii=False),flush=True)
 except Exception as error:
  result={'platform':name,'tab_id':tid,'state':'HELD','code':getattr(error,'code',type(error).__name__),'detail':str(error)};print(json.dumps(result),flush=True)
 results.append(result);atomic_json(OUT/'account-preflight-results.json',{'utc':utc(),'results':results})
