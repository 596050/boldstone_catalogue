"""Run only this authorized batch, preserving every platform's durable intent."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'social-publisher'))
from common import Hold,atomic_json,canonical,utc
from settings import Settings
from chrome import Chrome
from workflow import Workflow
from engine import Engine
from journal import Store

platforms=set(sys.argv[1:] or ['facebook','instagram','linkedin'])
directory=ROOT/'social-publisher/state'
settings=Settings();chrome=Chrome(settings,directory)
with Store(directory) as store:
 jobs=[j for j in store.jobs() if j['payload'].get('batch_id')=='component-sculptures-20261117' and j['payload']['platform'] in platforms]
 for original in jobs:
  job=store.get(original['id']);name=job['payload']['profile_id']
  if job['state'] in {'PUBLISHED','HISTORICAL_VERIFIED'}:continue
  if store.has_intent(job['id']):
   print(canonical({'job_id':job['id'],'status':'NEEDS_RECONCILIATION','state':job['state']}),flush=True);break
  if job['payload']['profile_hash']!=settings.fingerprint(name):
   chrome.adopt_profile(name)
   p=job['payload'];p.setdefault('previous_profile_hashes',[]).append(p['profile_hash'])
   p.update(profile_hash=settings.fingerprint(name),profile_snapshot=settings.profile(name),workflow_snapshot=settings.workflow(settings.profile(name)))
   with store.db:store.db.execute('UPDATE jobs SET payload=? WHERE id=?',(canonical(p),job['id']))
   store.change(job['id'],'QUEUED')
  elif job['state']=='BLOCKED':
   print(canonical({'job_id':job['id'],'status':'BLOCKED','error':job['last_error']}),flush=True);break
  report=Engine(store,Workflow(settings,chrome,directory),settings.policy).run(job['id'])
  result=store.get(job['id'])
  atomic_json(OUT/(job['id']+'-run.json'),result)
  print(canonical({'utc':utc(),'job_id':job['id'],'platform':job['payload']['platform'],'title':job['payload']['title'],'state':result['state'],'error':result['last_error'],'url':(result['receipt']or{}).get('native_url')}),flush=True)
  selected=[j for j in store.jobs() if j['payload'].get('batch_id')=='component-sculptures-20261117']
  atomic_json(OUT/'publication-state.json',{'utc':utc(),'jobs':selected})
  if result['state']!='PUBLISHED':break
 store.export();store.backup()
