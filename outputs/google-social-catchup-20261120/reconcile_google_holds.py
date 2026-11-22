"""Read-only reconciliation of existing Google records; never calls prepare or submit."""
import json,sys
from pathlib import Path
OUT=Path(__file__).parent;ROOT=OUT.parents[1];sys.path.insert(0,str(ROOT/'social-publisher'))
from common import atomic_json,canonical,digest,read_json,utc
from settings import Settings
from google_fast import GoogleFastChrome
from workflow import Workflow
from engine import Engine
from journal import Store
from google_public import GooglePublicReadback
state=ROOT/'social-publisher/state';registry=OUT/'platform-publication-holds.json';holds=read_json(registry)['holds'];results=[]
with Store(state) as store:
 for hold in holds:
  job=store.get(hold['job_id'])
  if job['state']=='PUBLISHED':continue
  assert store.has_intent(job['id']) and digest(Path(hold['proof_path']).read_bytes())==hold['proof_sha256']
  video=job['payload'].get('media_type')=='video/mp4';settings=Settings(OUT/'video-config/profiles.json') if video else Settings();directory=OUT/'google-video-state' if video else state
  chrome=GoogleFastChrome(settings,directory)
  if video:
   main=GoogleFastChrome(Settings(),state);b=main.bindings['verification'];main.bound('verification',mutation=True);assert b['url']==settings.profile('boldstone_google_business_profile')['inventory_url']
   chrome.bindings['verification']={**b,'profile_hash':chrome.profile_hash('verification')};chrome.save_bindings()
  error_code=None
  workflow=Workflow(settings,chrome,directory)
  adapter=GooglePublicReadback(workflow,OUT/'google-public-readback-context.json',hold['native_post_id']) if (OUT/'google-public-readback-context.json').exists() else workflow
  try:Engine(store,adapter,settings.policy).reconcile(job['id'],native_url=hold.get('native_url'))
  except Exception as error:
   error_code=getattr(error,'code',type(error).__name__);print(canonical({'utc':utc(),'job_id':job['id'],'readback_error':str(error),'readback_error_code':error_code}),flush=True)
  # Inspection never changes an editor field. Restore only this inspection
  # page, so the next serial account configuration sees its own native URL.
  b=chrome.bindings['verification'];base=settings.profile('boldstone_google_business_profile')['inventory_url']
  if b['url']!=base:chrome.navigate('verification',base,recovery=True)
  current=store.get(job['id']);results.append({'job_id':job['id'],'state':current['state'],'receipt':current['receipt'],'error':current['last_error'],'readback_error_code':error_code});print(canonical(results[-1]),flush=True)
 store.export();store.backup()
atomic_json(OUT/'platform-hold-readback-results.json',{'utc':utc(),'results':results,'no_publication_actions':True})
