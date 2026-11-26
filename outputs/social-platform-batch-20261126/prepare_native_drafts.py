"""Prepare ten composers in isolated state; never opens or writes the outbox."""
from pathlib import Path
import json,sys,sqlite3
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1]
sys.path.insert(0,str(ROOT/'social-publisher'))
from common import atomic_json,read_json,utc,Hold
from settings import Settings
from preparation import PreparationOnlyChrome
from workflow import Workflow
from upload_bridge import UploadClient

settings=Settings(OUT/'draft-config/profiles.json')
jobs=settings.jobs(OUT/'combined-draft-manifest.json',require_authorized=False);assert len(jobs)==10
plan=read_json(OUT/'draft-tab-ids.json');planned={(r['profile_id'],r['post_key']):r for r in plan['bindings']}
root=OUT/'native-drafts';root.mkdir(exist_ok=True)
probe=PreparationOnlyChrome(settings,root/'reader-state');inventory=probe.inventory()
def address(tid):
 matches=[(w,t) for w in inventory['windows'] for t in w['tabs'] if t['tab_id']==tid]
 assert len(matches)==1
 return matches[0]
reader,_=address(plan['verification_tab_id']);results=[]
with sqlite3.connect((ROOT/'social-publisher/state/outbox.sqlite3').as_uri()+'?mode=ro',uri=True) as db:
 for job in jobs:
  assert db.execute('select id from jobs where channel_key=? and post_key=?',(job['channel_key'],job['post_key'])).fetchone() is None

for job in jobs:
 name=job['payload']['profile_id'];allocated=planned[(name,job['post_key'])];window,tab=address(allocated['tab_id']);directory=root/job['id'];chrome=PreparationOnlyChrome(settings,directory)
 previous=read_json(directory/'preparation-result.json') if (directory/'preparation-result.json').exists() else None
 if previous and previous.get('state','').startswith('PREPARED_'):
  results.append(previous);chrome.close();continue
 result={'id':job['id'],'post_key':job['post_key'],'title':job['payload']['title'],'profile_id':name,
         'platforms':['facebook','instagram'] if name=='boldstone_facebook' else ['threads'],
         'window_id':window['window_id'],'tab_id':tab['tab_id'],'publish_clicks':0,'publish_intents_written_by_this_worker':0,'outbox_jobs_added_by_this_worker':0}
 try:
  if name not in chrome.bindings:
   assert tab['url']=='about:blank'
   chrome.bind(name,window['window_id'],tab['tab_id'])
  elif chrome.bindings[name]['profile_hash']!=chrome.profile_hash(name):
   # Inspect and retain our exact existing owner; only the preparation recipe
   # changed to make Facebook-only advertising controls conditional.
   before=chrome.call(name,{'op':'snapshot','fullDocument':True})
   atomic_json(directory/'before-recipe-adoption.json',before)
   assert chrome.bindings[name]['tab_id']==allocated['tab_id']
   chrome.adopt_profile(name)
  if 'verification' not in chrome.bindings:
   chrome.bind('verification',reader['window_id'],plan['verification_tab_id'])
  if name=='boldstone_facebook':chrome.upload_client=UploadClient(ROOT/'social-publisher/state')
  ready=Workflow(settings,chrome,directory).prepare(job)
  snap=chrome.call(name,{'op':'snapshot','fullDocument':True,'includeHTML':True});atomic_json(directory/'prepared-native.json',snap)
  upload=chrome.call(name,{'op':'upload_status','job':job['id'],'mediaSha256':job['payload']['media_sha256']})
  assert upload.get('committed') and upload.get('sha256')==job['payload']['media_sha256']
  result.update(state='PREPARED_NOT_PUBLISHED',ready=ready,upload=upload,caption=job['payload']['caption'],media_sha256=job['payload']['media_sha256'],native_snapshot_path=str((directory/'prepared-native.json').resolve()))
 except Exception as error:
  result.update(state='HELD',code=getattr(error,'code',type(error).__name__),detail=str(error))
  try:atomic_json(directory/'held-native.json',chrome.call(name,{'op':'snapshot','fullDocument':True,'includeHTML':True}))
  except Exception as inspection_error:result['inspection_error']=str(inspection_error)
 finally:chrome.close()
 atomic_json(directory/'preparation-result.json',result);results.append(result)
 atomic_json(OUT/'native-draft-results.json',{'utc':utc(),'mode':'prepare_only','drafts':results,'prepared_composers':sum(r['state']=='PREPARED_NOT_PUBLISHED' for r in results),'publish_clicks':0,'publish_intents_written_by_this_worker':0,'outbox_jobs_added_by_this_worker':0})
 print(json.dumps({k:result[k] for k in ['title','platforms','state','code','detail'] if k in result},ensure_ascii=False),flush=True)
atomic_json(OUT/'native-draft-results.json',{'utc':utc(),'mode':'prepare_only','drafts':results,'prepared_composers':sum(r['state'].startswith('PREPARED_') for r in results),'publish_clicks':0,'publish_intents_written_by_this_worker':0,'outbox_jobs_added_by_this_worker':0})
