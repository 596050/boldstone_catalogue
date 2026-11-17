"""Try the visible LinkedIn media drop area in a separate background draft."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'social-publisher'))
from settings import Settings
from chrome import Chrome
from workflow import Workflow
from common import digest,atomic_json,utc
s=Settings();c=Chrome(s,OUT/'linkedin-drop-state');w=Workflow(s,c,OUT/'linkedin-drop-state')
name='sally_linkedin';p=json.loads((OUT/'posts.json').read_text())[1];profile=s.profile(name)
job_id=digest([profile['channel_key'],p['catalogue_id']])[:32]
context={**profile,**p,'id':job_id,'job':job_id,'profile_id':name,'media_sha256':p['sha256'],'mediaSha256':p['sha256'],'media_type':'image/png','caption':p['captions']['linkedin']}
c.begin(name,job_id,profile['compose_url'])
recipe=s.workflow(profile)
for i,step in enumerate(w.enabled_steps(recipe['prepare'],context)):
 if step.get('unless') and c.call(name,{'op':'exists','locator':step['unless']})['exists']:continue
 if step['op']=='wait':w.wait(name,step['locator'])
 elif step['op']=='click':c.call(name,{'op':'click','locator':step['locator']})
 elif step['op']=='upload':
  guards=[g for g in w.guards(recipe,context) if g.get('purpose') in {'account','audience'}]
  c.call(name,{'op':'assert','checks':guards})
  zone=[{'selector':'dialog[open] div:has(>h2)','contains':'Select files to begin'}]
  c.call(name,{'op':'assert','checks':[{'locator':zone}]})
  result=c.upload(name,context,zone,method='drop')
  atomic_json(OUT/'linkedin-inner-drop-result.json',{'utc':utc(),'job_id':job_id,'publish_actions':0,'result':result})
  break
 else:raise RuntimeError(step['op'])
 c.checkpoint(name,i+1)
 print(str(i)+' '+step['op']+' complete',flush=True)
atomic_json(OUT/'linkedin-inner-drop-snapshot.json',c.call(name,{'op':'snapshot','fullDocument':True}))
print('Native preview inspection required; no publication intent written.')
