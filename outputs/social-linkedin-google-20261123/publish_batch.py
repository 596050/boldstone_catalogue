"""Run only the nine explicitly authorized deliveries; never a queued backlog."""
from pathlib import Path
import sys,json
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1]
sys.path.insert(0,str(ROOT/'social-publisher'))
from settings import Settings
from google_fast import GoogleFastChrome
from workflow import Workflow
from engine import Engine
from journal import Store
from common import atomic_json,utc
settings=Settings();requested=settings.jobs(OUT/'manifest.json');ids=[j['id'] for j in requested]
assert len(ids)==9 and len(set(ids))==9
assert {j['payload']['profile_id'] for j in requested}=={'sally_linkedin','boldstone_google_business_profile'}
results=[]
with Store(ROOT/'social-publisher/state') as store:
 store.enqueue(requested)
 for expected in requested:
  job=store.get(expected['id']);assert job['content_hash']==expected['content_hash']
  chrome=GoogleFastChrome(settings,ROOT/'social-publisher/state')
  try:Engine(store,Workflow(settings,chrome,ROOT/'social-publisher/state'),settings.policy).run(job_id=job['id'])
  finally:chrome.close()
  job=store.get(expected['id']);r={'id':job['id'],'post_key':job['post_key'],'title':job['payload']['title'],'profile_id':job['payload']['profile_id'],'state':job['state'],'last_error':job['last_error'],'receipt':job['receipt']}
  results.append(r);atomic_json(OUT/'publication-progress.json',{'utc':utc(),'requested_deliveries':9,'results':results})
  print(json.dumps({k:r[k] for k in ['title','profile_id','state','last_error']},ensure_ascii=False),flush=True)
 store.export();store.backup()
 atomic_json(OUT/'publication-results.json',{'utc':utc(),'requested_deliveries':9,'results':results,'complete':all(r['state']=='PUBLISHED' for r in results)})
