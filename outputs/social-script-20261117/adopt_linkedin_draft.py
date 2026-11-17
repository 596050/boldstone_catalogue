"""Move the verified LinkedIn recovery draft into the main guarded outbox."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'social-publisher'))
from common import Hold,atomic_json,canonical,utc
from settings import Settings
from chrome import Chrome
from workflow import Workflow,render
from journal import Store

directory=ROOT/'social-publisher/state';job_id='eca95a34d419e1585a06440de42f85b5';name='sally_linkedin'
with Store(directory) as store:
 meta=[j for j in store.jobs() if j['payload'].get('batch_id')=='component-sculptures-20261117' and j['payload']['platform'] in {'facebook','instagram'}]
 if len(meta)!=10 or any(j['state']!='PUBLISHED' for j in meta):raise Hold('META_BATCH_NOT_FINISHED')
 job=store.get(job_id)
 if store.has_intent(job_id):raise Hold('INTENT_CANNOT_BE_RESET')
 s=Settings();c=Chrome(s,directory);w=Workflow(s,c,directory)
 recovered=json.loads((OUT/'linkedin-drop-state/bindings.json').read_text())[name]
 if recovered['job_id']!=job_id:raise Hold('WRONG_RECOVERED_DRAFT')
 atomic_json(OUT/'retained-first-linkedin-draft-binding.json',c.bindings[name])
 c.bindings[name]=recovered
 c.bound(name,mutation=True)
 c.call(name,{'op':'claim'})
 payload=job['payload'];profile=s.profile(name)
 if profile['channel_key']!=payload['channel_key']:raise Hold('ACCOUNT_CHANGED')
 context={**profile,**payload,'id':job_id}
 recipe=s.workflow(profile)
 ready=c.call(name,{'op':'ready','job':job_id,'mediaSha256':payload['media_sha256'],'checks':w.guards(recipe,context),'submit':render(recipe['submit'],context)})
 c.adopt_profile(name)
 payload.setdefault('previous_profile_hashes',[]).append(payload['profile_hash'])
 payload['profile_hash']=s.fingerprint(name);payload['profile_snapshot']=profile;payload['workflow_snapshot']=recipe
 with store.db:store.db.execute('UPDATE jobs SET payload=? WHERE id=?',(canonical(payload),job_id))
 store.change(job_id,'QUEUED');store.export();store.backup()
 atomic_json(OUT/'linkedin-draft-handoff.json',{'utc':utc(),'job_id':job_id,'status':'READY_IN_MAIN_OUTBOX','publish_actions':0,'ready':ready})
 print(json.dumps({'job_id':job_id,'status':'READY_IN_MAIN_OUTBOX','publish_actions':0}))
