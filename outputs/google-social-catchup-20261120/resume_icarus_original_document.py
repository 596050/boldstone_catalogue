"""Complete only Icarus's first Post after proving the original unclicked document."""
import sys
from pathlib import Path
OUT=Path(__file__).parent;ROOT=OUT.parents[1];sys.path[:0]=[str(ROOT/'social-publisher'),str(OUT)]
from common import canonical,read_json,utc
from settings import Settings
from google_fast import GoogleFastChrome
from workflow import Workflow
from google_business import GoogleBusinessProfile
from journal import Store
from hold_google_unpublished import hold_unpublished
state=ROOT/'social-publisher/state';directory=OUT/'google-video-state';settings=Settings(OUT/'video-config/profiles.json');chrome=GoogleFastChrome(settings,directory);job_id='ec19a30e5499ce8c73827b22e55d197d'
with Store(state) as store:
 main=GoogleFastChrome(Settings(),state);main.bound('verification',mutation=True);b=main.bindings['verification'];assert b['url']==settings.profile('boldstone_google_business_profile')['inventory_url']
 chrome.bindings['verification']={**b,'profile_hash':chrome.profile_hash('verification')};chrome.save_bindings()
 try:
  try:GoogleBusinessProfile(Workflow(settings,chrome,directory)).resume_unattempted(store,store.get(job_id))
  except Exception as error:print(canonical({'utc':utc(),'state':store.get(job_id)['state'],'error':str(error)}),flush=True)
  record=directory/'evidence'/(job_id+'-google-record.json')
  if store.get(job_id)['state']!='PUBLISHED' and record.exists():
   hold_unpublished(store,settings,chrome,job_id)
 finally:
  b=chrome.bindings['verification'];base=settings.profile('boldstone_google_business_profile')['inventory_url']
  if b['url']!=base:chrome.navigate('verification',base,recovery=True)
  store.export();store.backup()
 print(canonical({'utc':utc(),'job_id':job_id,'state':store.get(job_id)['state']}),flush=True)
