"""Release the borrowed video tab only after every frozen clip was submitted.

Later read-only video checks borrow the idle Google writer instead. Original
Meta publishing bindings and all post intents stay unchanged.
"""
import sys
from pathlib import Path
OUT=Path(__file__).parent;ROOT=OUT.parents[1];sys.path.insert(0,str(ROOT/'social-publisher'))
from common import atomic_json,read_json,utc
from settings import Settings
from google_fast import GoogleFastChrome
from journal import Store

state=ROOT/'social-publisher/state';video_settings=Settings(OUT/'video-config/profiles.json')
with Store(state) as store:
 main=GoogleFastChrome(Settings(),state);video=GoogleFastChrome(video_settings,OUT/'google-video-state');name='boldstone_google_business_profile'
 jobs=video_settings.jobs(OUT/'history-video-part1/manifest.json')
 assert all(store.has_intent(j['id']) for j in jobs),'Unsubmitted video clips still need their original writer'
 original=read_json(OUT/'meta-reader-state/original-binding.json');old=dict(video.bindings[name]);replacement=dict(main.bindings[name])
 if old['tab_id']==replacement['tab_id']:
  assert (OUT/'facebook-source-tab-restored.json').exists(),'Inspect a partial source-tab handoff'
  print('Facebook source tab was already restored');raise SystemExit(0)
 assert old['tab_id']==original['tab_id'] and old['owner']==original['owner']
 base=video_settings.profile(name)['inventory_url']
 for browser in [main,video]:
  binding,_=browser.bound(name,mutation=True)
  assert binding['url']==base and not binding.get('dirty')
  browser.call(name,{'op':'assert','checks':[{'locator':[{'selector':'h1','text':'Your posts'}]}]})
 atomic_json(OUT/'video-reader-handoff-before-source-restore.json',{'utc':utc(),'original_video_writer':old,'idle_google_writer':replacement,'all_frozen_video_intents_present':True,'no_publication_actions':True})
 video.bindings[name]={**replacement,'profile_hash':video.profile_hash(name)};video.save_bindings()
 restorer=GoogleFastChrome(Settings(),OUT/'meta-reader-state');restorer.bindings['verification']={**old,'profile_hash':restorer.profile_hash('verification')};restorer.save_bindings()
 restorer.navigate('verification',original['url'],recovery=True)
 assert restorer.call('verification',{'op':'probe'})['url']==original['url']
 atomic_json(OUT/'facebook-source-tab-restored.json',{'utc':utc(),'tab_id':original['tab_id'],'url':original['url'],'future_video_readback_tab_id':replacement['tab_id'],'no_publication_actions':True})
 print('Original Facebook Meta tab restored in the background; Google review checks retain their reserved tabs')
