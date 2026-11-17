"""Prepare one owned photo draft without creating any publication intent."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'social-publisher'))
from settings import Settings
from chrome import Chrome
from workflow import Workflow
from common import atomic_json,digest
settings=Settings();chrome=Chrome(settings,ROOT/'social-publisher/state');workflow=Workflow(settings,chrome,ROOT/'social-publisher/state')
name=sys.argv[1];p=json.loads((OUT/'posts.json').read_text())[0];profile=settings.profile(name)
job_id=digest([profile['channel_key'],p['catalogue_id']])[:32]
context={**profile,**p,'id':job_id,'job':job_id,'profile_id':name,'media_sha256':p['sha256'],'mediaSha256':p['sha256'],'media_type':'image/png','caption':p['captions'][profile['platform']]}
chrome.adopt_profile(name)
binding=chrome.begin(name,job_id,profile['compose_url'])
recipe=settings.workflow(profile)
try:
 for i,step in enumerate(workflow.enabled_steps(recipe['prepare'],context)):
  if step.get('when') or (step['op']=='click' and any(x.get('name')=='Tag products' for x in step['locator'])):break
  if step.get('if_exists') and not chrome.call(name,{'op':'exists','locator':step['locator']})['exists']:continue
  if step.get('unless') and chrome.call(name,{'op':'exists','locator':step['unless']})['exists']:continue
  op=step['op']
  if op=='wait':workflow.wait(name,step['locator'])
  elif op=='set_checked':workflow.set_checked(name,step['locator'],step['value'],confirmation=step.get('confirmation'))
  elif op=='upload':
   guards=[g for g in workflow.guards(recipe,context) if g.get('purpose') in {'account','destination','audience','story','boost','schedule'}]
   chrome.upload(name,context,step['locator'],method=step['method'],preview=step['preview'],guards=guards)
  elif op=='photo_alt':workflow.photo_alt(name,step)
  elif op in {'click','set_text','assert'}:chrome.call(name,{k:v for k,v in step.items() if k not in {'unless','if_exists','dirty'}})
  else:raise RuntimeError(op)
  chrome.checkpoint(name,i+1)
  print(str(i)+' '+op+' complete',flush=True)
  if op=='photo_alt' or (op=='upload' and profile['platform']=='linkedin'):break
finally:
 atomic_json(OUT/(name+'-photo-calibration.json'),chrome.call(name,{'op':'snapshot'}))
 workflow.close()
print(json.dumps({'draft_job':job_id,'publish_actions':0}))
