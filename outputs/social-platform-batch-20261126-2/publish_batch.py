"""Publish only these ten authorised deliveries, preserving all prior intents."""
import json,sys,time
from pathlib import Path
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1]
sys.path[:0]=[str(ROOT/'social-publisher'),str(ROOT/'outputs/google-social-catchup-20261120')]
from common import atomic_json,read_json,digest,utc
from settings import Settings
from google_fast import GoogleFastChrome
from workflow import Workflow
from engine import Engine
from journal import Store
import hold_google_unpublished
hold_google_unpublished.OUT=OUT
settings=Settings();state=ROOT/'social-publisher/state';jobs=settings.jobs(OUT/'publish-manifest.json')
assert len(jobs)==10 and {j['payload']['profile_id'] for j in jobs}=={'sally_linkedin','boldstone_google_business_profile'}
checks=read_json(OUT/'meta-duplicate-checks.json');assert len(checks)==5 and all(x['result']=='NO_MATCH_IN_NATIVE_RANGE' for x in checks)
with Store(state) as store:
 chrome=GoogleFastChrome(settings,state)
 if not (OUT/'preflight-tabs-transferred.json').exists():
  source=read_json(OUT/'browser-state/bindings.json');transferred=[]
  for name,key in [('sally_linkedin','sally_linkedin'),('boldstone_google_business_profile','boldstone_google_business_profile'),('verification','boldstone_facebook')]:
   original=source[key];inventory=chrome.state_for(original);_,tab=chrome.find(inventory,original['window_id'],original['tab_id'])
   assert tab['url']==original['url'] and not chrome.target_foreground(inventory,original)
   chrome.bindings[name]={**original,'profile_hash':chrome.profile_hash(name),'job_id':None,'step':0,'dirty':False}
   chrome.save_bindings()
   # Retain the actual preflight owner. A different owner's document still
   # refuses this claim; no ownership marker is cleared or overwritten.
   chrome.call(name,{'op':'claim'})
   snap=chrome.call(name,{'op':'snapshot','fullDocument':True});assert not snap.get('editors')
   transferred.append({'profile_id':name,'source_profile_id':key,'binding':chrome.bindings[name]})
  atomic_json(OUT/'preflight-tabs-transferred.json',{'utc':utc(),'transfers':transferred})
  store.event('OWN_PREFLIGHT_TABS_TRANSFERRED',batch_id='component-sculptures-20261126-2',evidence_path=str(OUT/'preflight-tabs-transferred.json'))
 chrome.close();store.enqueue(jobs);results=[]
 for expected in jobs:
  job=store.get(expected['id']);assert job['content_hash']==expected['content_hash'];chrome=GoogleFastChrome(settings,state)
  if job['state']=='BLOCKED' and not store.has_intent(job['id']):store.change(job['id'],'QUEUED')
  try:
   Engine(store,Workflow(settings,chrome,state),settings.policy).run(job_id=job['id'])
   current=store.get(job['id'])
   if current['state']!='PUBLISHED' and current['payload']['platform']=='google_business_profile' and store.has_intent(job['id']):
    hold_google_unpublished.hold_unpublished(store,settings,chrome,job['id'])
  except Exception as error:
   print(json.dumps({'job_id':job['id'],'error':str(error),'code':getattr(error,'code',type(error).__name__)}),flush=True)
  finally:chrome.close()
  job=store.get(expected['id']);r={k:job[k] for k in ['id','post_key','state','last_error','receipt']};r.update(title=job['payload']['title'],profile_id=job['payload']['profile_id']);results.append(r)
  atomic_json(OUT/'publication-progress.json',{'utc':utc(),'results':results});print(json.dumps({k:r[k] for k in ['title','profile_id','state','last_error']},ensure_ascii=False),flush=True)
 store.export();store.backup();atomic_json(OUT/'publication-results.json',{'utc':utc(),'results':results,'complete':all(r['state']=='PUBLISHED' for r in results)})
