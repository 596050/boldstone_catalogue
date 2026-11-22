"""Publish only a frozen reviewed history batch, with read-only reconciliation."""
import sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'social-publisher'))
from common import atomic_json,canonical,read_json,utc,digest
from settings import Settings
from google_fast import GoogleFastChrome
from workflow import Workflow
from engine import Engine
from journal import Store
from hold_google_unpublished import hold_unpublished

folder=OUT/sys.argv[1];limit=int(sys.argv[2]) if len(sys.argv)>2 else 1000
settings=Settings();directory=ROOT/'social-publisher/state';chrome=GoogleFastChrome(settings,directory)
manifest=folder/('delivery-manifest.json' if (folder/'delivery-manifest.json').exists() else 'manifest.json')
batch=read_json(manifest)['batch_id'];jobs=settings.jobs(manifest)
with Store(directory) as store:
 store.enqueue(jobs)
 if chrome.bindings['boldstone_google_business_profile']['profile_hash']!=settings.fingerprint('boldstone_google_business_profile'):
  chrome.adopt_profile('boldstone_google_business_profile')
 count=0
 for item in jobs:
  job=store.get(item['id'])
  if job['state']=='PUBLISHED':continue
  holds=read_json(OUT/'platform-publication-holds.json')['holds'] if (OUT/'platform-publication-holds.json').exists() else []
  hold=next((h for h in holds if h['job_id']==job['id']),None)
  if hold:
   assert store.has_intent(job['id']) and digest(Path(hold['proof_path']).read_bytes())==hold['proof_sha256']
   print(canonical({'utc':utc(),'job_id':job['id'],'state':'PLATFORM_PUBLICATION_HELD','reason':hold['reason']}),flush=True);continue
  if not store.has_intent(job['id']):Engine(store,Workflow(settings,chrome,directory),settings.policy).run(job['id'])
  for retry in range(settings.policy.get('max_reconcile_attempts',8)):
   current=store.get(job['id'])
   epoch=Workflow(settings,chrome,directory).reconciliation_epoch(current)
   if current['state']=='PUBLISHED' or not store.has_intent(job['id']) or current['verify_attempts']>=epoch+settings.policy.get('max_reconcile_attempts',8):break
   while time.time()<current['next_attempt']:time.sleep(max(0,min(3,current['next_attempt']-time.time())))
   try:
    Engine(store,Workflow(settings,chrome,directory),settings.policy).reconcile(job['id'])
   except Exception as error:
    print(canonical({'utc':utc(),'job_id':job['id'],'status':'READBACK_PENDING','error':str(error)}),flush=True)
    if not getattr(error,'retryable',False):break
   # A saved, explicitly unpublished native record must not stall unrelated
   # posts or trigger a replacement submission. Inspect its full saved media
   # and action before releasing only its exact retained create form.
   current=store.get(job['id']);record=directory/'evidence'/(job['id']+'-google-record.json')
   if current['state']!='PUBLISHED' and current['verify_attempts']>=3 and record.exists():
    native=read_json(record)
    if native.get('status',{}).get('text','').strip() in {'Pending','Rejected','Not approved','Processing'}:
     hold_unpublished(store,settings,chrome,job['id']);break
  current=store.get(job['id']);atomic_json(folder/(job['id']+'-run.json'),current)
  print(canonical({'utc':utc(),'job_id':job['id'],'title':job['payload']['title'],'state':current['state'],'error':current['last_error'],'url':(current['receipt'] or {}).get('native_url')}),flush=True)
  selected=[j for j in store.jobs() if j['payload'].get('batch_id')==batch]
  atomic_json(folder/'publication-state.json',{'utc':utc(),'jobs':selected})
  if current['state']!='PUBLISHED':
   holds=read_json(OUT/'platform-publication-holds.json')['holds'] if (OUT/'platform-publication-holds.json').exists() else []
   if not any(h['job_id']==current['id'] for h in holds):break
  count+=1
  if count>=limit:break
 store.export();store.backup()
