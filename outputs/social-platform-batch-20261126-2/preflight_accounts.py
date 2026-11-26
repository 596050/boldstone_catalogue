"""Reserve and inspect only newly created background tabs for this batch."""
import json,sys
from pathlib import Path
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1];sys.path.insert(0,str(ROOT/'social-publisher'))
from settings import Settings
from chrome import Chrome
from common import atomic_json,utc
settings=Settings();c=Chrome(settings,OUT/'browser-state')
targets={
 'sally_linkedin':(962006597,'https://www.linkedin.com/in/sally-price-1193858a/'),
 'boldstone_google_business_profile':(962006600,settings.profile('boldstone_google_business_profile')['inventory_url']),
 'boldstone_facebook':(962006603,settings.profile('boldstone_facebook')['inventory_url']),
 'boldstone_threads':(962006606,settings.profile('boldstone_threads')['inventory_url'])}
inventory=c.inventory();atomic_json(OUT/'focus-baseline.json',{'utc':utc(),'focus':c.focus_stamp(inventory)})
for name,(tid,url) in targets.items():
 matches=[(w,t) for w in inventory['windows'] for t in w['tabs'] if t['tab_id']==tid];assert len(matches)==1
 w,t=matches[0];assert t['url']=='about:blank';c.bind(name,w['window_id'],tid);c.navigate(name,url)
 snap=c.call(name,{'op':'snapshot','fullDocument':True,'includeHTML':True});atomic_json(OUT/(name+'-preflight.json'),{'utc':utc(),'snapshot':snap})
 print(json.dumps({'platform':name,'tab_id':tid,'title':snap['title'],'url':snap['url'],'text':snap['text'][:1200]},ensure_ascii=False),flush=True)
c.close()
