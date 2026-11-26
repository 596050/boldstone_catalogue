"""Inspect and prefill the three requested design services in background tabs."""
import json,sys,time
from pathlib import Path
OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(OUT.parent/'design-platform-registrations-20261123'),str(OUT.parents[1]/'social-publisher')]
import registration_browser as registration
registration.OUT=OUT
from common import Hold,atomic_json,utc

class DesignChrome(registration.RegistrationChrome):
 def navigate(self,name,url,job_id=None,recovery=False):
  if name!='architonic' or not url.startswith('https://www.architonic.com/en/login?'):
   return super().navigate(name,url,job_id,recovery)
  self.settings.check_url(self.profile(name),url)
  b,before=self.bound(name,mutation=True)
  assert not b.get('dirty')
  self.call(name,{'op':'claim'});b['pending_url']=url;self.save_bindings()
  result=self.call(name,{'op':'navigate','url':url})
  deadline=time.monotonic()+20
  while time.monotonic()<deadline:
   state=self.state_for(b);_,tab=self.find(state,b['window_id'],b['tab_id'])
   if self.target_foreground(state,b):raise Hold('FOCUS_CHANGED_PAUSED')
   if not tab['loading'] and tab['url']==url:
    b.update(url=url,job_id=job_id,step=0,dirty=False);b.pop('pending_url',None);self.save_bindings();self.call(name,{'op':'claim'});return result
   time.sleep(.3)
  raise Hold('NAVIGATION_TIMEOUT')

def browser():return DesignChrome(registration.RegistrationSettings(),OUT/'browser-state')

def snapshot(c,name,suffix='current',scope=None):
 request={'op':'snapshot','fullDocument':True,'includeHTML':True}
 if scope:request['scope']=scope
 s=c.call(name,request);atomic_json(OUT/(name+'-'+suffix+'.json'),{'utc':utc(),'snapshot':s})
 print(json.dumps({'platform':name,'url':s['url'],'text':s['text'][:5000],
  'inputs':[i for i in s['inputs'] if 'type="password"' not in i['html']],
  'controls':s['controls'][:35],
  'links':[l for l in s.get('links',[]) if any(k in str(l).lower() for k in ['login','google','publish','catalog','brand','contact','register','signup','account'])][:25]},ensure_ascii=False),flush=True)
 return s

if __name__=='__main__':
 c=browser();name,op=sys.argv[1:3]
 try:
  if op=='navigate':c.navigate(name,sys.argv[3])
  elif op=='fill':
   for locator,value in json.loads(sys.argv[3]):c.call(name,{'op':'set_text','locator':locator,'value':value})
  elif op=='click':
   locator=json.loads(sys.argv[3]);assert locator.get('name','').lower() not in {'subscribe','submit','post','publish','send','i agree'}
   c.call(name,{'op':'click','locator':locator})
  elif op!='inspect':raise ValueError(op)
  snapshot(c,name,scope=json.loads(sys.argv[4]) if len(sys.argv)>4 else None)
 finally:c.close()
