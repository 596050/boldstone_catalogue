"""Read back only submitted jobs in this batch; never creates a publish intent."""
from pathlib import Path
import sys,json
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1];sys.path.insert(0,str(ROOT/'social-publisher'))
from common import atomic_json,read_json,utc
from settings import Settings
from google_fast import GoogleFastChrome
from journal import Store
from engine import Engine
from workflow import Workflow
settings=Settings();state=ROOT/'social-publisher/state';jobs=settings.jobs(OUT/'publish-manifest.json')
holds={h['job_id']:h for h in read_json(OUT/'platform-publication-holds.json')['holds']}
with Store(state) as store:
 before=[e for e in store.ledger if e['kind']=='PUBLISH_INTENT'];c=GoogleFastChrome(settings,state)
 try:
  for expected in jobs:
   job=store.get(expected['id'])
   if job['state']=='OUTCOME_UNKNOWN':
    assert store.has_intent(job['id']);assert job['id'] in holds
    try:Engine(store,Workflow(settings,c,state),settings.policy).reconcile(job['id'],native_url=holds[job['id']]['native_url'])
    except Exception as error:print(json.dumps({'id':job['id'],'code':getattr(error,'code',type(error).__name__),'detail':str(error)}),flush=True)
  results=[]
  for expected in jobs:
   j=store.get(expected['id']);r={k:j[k] for k in ['id','post_key','state','last_error','receipt']};r.update(title=j['payload']['title'],profile_id=j['payload']['profile_id'])
   if j['state']!='PUBLISHED' and j['id'] in holds:r['native_pending_record']=holds[j['id']]
   results.append(r)
  assert before==[e for e in store.ledger if e['kind']=='PUBLISH_INTENT']
  store.export();store.backup();atomic_json(OUT/'publication-results.json',{'utc':utc(),'results':results,'complete':all(r['state']=='PUBLISHED' for r in results),'publish_intents_added_by_reconciliation':0})
  print(json.dumps([{'title':r['title'],'profile':r['profile_id'],'state':r['state']} for r in results]),flush=True)
 finally:c.close()
