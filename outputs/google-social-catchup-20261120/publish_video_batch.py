"""Deliver the frozen video batch using its separately reserved background tabs."""
import sys,time
from pathlib import Path
OUT=Path(__file__).parent;ROOT=OUT.parents[1];sys.path.insert(0,str(ROOT/'social-publisher'))
from common import atomic_json,canonical,utc,read_json,digest
sys.path.insert(0,str(OUT))
from hold_google_unpublished import hold_unpublished
from settings import Settings
from google_fast import GoogleFastChrome
from workflow import Workflow
from engine import Engine
from google_business import GoogleBusinessProfile
from google_public import GooglePublicReadback
from journal import Store
settings=Settings(OUT/'video-config/profiles.json');directory=OUT/'google-video-state';folder=OUT/'history-video-part1'
chrome=GoogleFastChrome(settings,directory);jobs=settings.jobs(folder/'manifest.json')
with Store(ROOT/'social-publisher/state') as store:
 # The Instagram source tab retains an inspected rejected-post edit. Borrow
 # the idle main inspection tab for this serial video stage instead.
 main=GoogleFastChrome(Settings(),ROOT/'social-publisher/state')
 source=main.bindings['verification'];main.bound('verification',mutation=True)
 if source['url']!=settings.profile('boldstone_google_business_profile')['inventory_url']:
  assert not source.get('dirty')
  main.navigate('verification',settings.profile('boldstone_google_business_profile')['inventory_url'],recovery=True)
  source=main.bindings['verification']
 assert source['url']=='https://www.google.com/local/business/15009857378722117958/promote/updates'
 chrome.bindings['verification']={**source,'profile_hash':chrome.profile_hash('verification')};chrome.save_bindings()
 try:
  store.enqueue(jobs)
  for item in jobs:
   job=store.get(item['id'])
   if job['state']=='PUBLISHED':continue
   holds=read_json(OUT/'platform-publication-holds.json')['holds'] if (OUT/'platform-publication-holds.json').exists() else []
   hold=next((h for h in holds if h['job_id']==job['id']),None)
   if hold:
    assert store.has_intent(job['id']) and digest(Path(hold['proof_path']).read_bytes())==hold['proof_sha256'];continue
   if not store.has_intent(job['id']):Engine(store,Workflow(settings,chrome,directory),settings.policy).run(job['id'])
   if store.get(job['id'])['state']=='OUTCOME_UNKNOWN':
    try:GoogleBusinessProfile(Workflow(settings,chrome,directory)).resume_unattempted(store,store.get(job['id']))
    except Exception as error:print(canonical({'utc':utc(),'job_id':job['id'],'unattempted_document_check':str(error)}),flush=True)
   for retry in range(3):
    current=store.get(job['id'])
    epoch=Workflow(settings,chrome,directory).reconciliation_epoch(current)
    if current['state']=='PUBLISHED' or not store.has_intent(job['id']) or current['verify_attempts']>=epoch+settings.policy.get('max_reconcile_attempts',8):break
    if current['next_attempt']-time.time()>30:break
    while time.time()<current['next_attempt']:time.sleep(max(0,min(2,current['next_attempt']-time.time())))
    try:Engine(store,Workflow(settings,chrome,directory),settings.policy).reconcile(job['id'])
    except Exception as error:print(canonical({'utc':utc(),'job_id':job['id'],'status':'READBACK_PENDING','error':str(error)}),flush=True)
   current=store.get(job['id']);record=directory/'evidence'/(job['id']+'-google-record.json')
   if current['state']!='PUBLISHED' and record.exists() and (OUT/'google-public-readback-context.json').exists():
    import re
    native=read_json(record);ids=set(re.findall(r'data-post-name="accounts/-/locations/(\d+)/localPosts/(\d+)"',native['snapshot']['html']))
    assert len(ids)==1 and next(iter(ids))[0]==current['payload']['profile_snapshot']['location_id']
    try:Engine(store,GooglePublicReadback(Workflow(settings,chrome,directory),OUT/'google-public-readback-context.json',next(iter(ids))[1]),settings.policy).reconcile(job['id'])
    except Exception as error:print(canonical({'utc':utc(),'job_id':job['id'],'public_readback_pending':str(error)}),flush=True)
    current=store.get(job['id'])
   if current['state']!='PUBLISHED' and record.exists():
    native_status=read_json(record).get('status',{}).get('text','').strip()
    if native_status in {'Pending','Rejected','Not approved','Processing'} or native_status.startswith('Published'):
     hold_unpublished(store,settings,chrome,job['id'])
   current=store.get(job['id']);atomic_json(folder/(job['id']+'-run.json'),current)
   print(canonical({'utc':utc(),'job_id':job['id'],'title':job['payload']['title'],'state':current['state'],'error':current['last_error'],'url':(current['receipt'] or {}).get('native_url')}),flush=True)
   atomic_json(folder/'publication-state.json',{'utc':utc(),'jobs':[store.get(j['id']) for j in jobs]})
   if current['state']!='PUBLISHED':
    holds=read_json(OUT/'platform-publication-holds.json')['holds'] if (OUT/'platform-publication-holds.json').exists() else []
    if not any(h['job_id']==current['id'] for h in holds):break
 finally:
  # This tab was used only for inspection; leave it at the exact native
  # inventory before the serial photo workflow resumes its own binding.
  reader=chrome.bindings['verification']
  if reader['url']!=settings.profile('boldstone_google_business_profile')['inventory_url']:
   chrome.navigate('verification',settings.profile('boldstone_google_business_profile')['inventory_url'],recovery=True)
  store.export();store.backup()
