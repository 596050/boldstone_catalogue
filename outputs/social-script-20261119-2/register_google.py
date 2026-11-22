"""Register the verified Google location while preserving its prepared draft."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'social-publisher'))
from common import atomic_json,digest,read_json,utc
from journal import Store
from settings import Settings
from chrome import Chrome,VERIFICATION

directory=ROOT/'social-publisher/state'
name='boldstone_google_business_profile'
profile_path=ROOT/'social-publisher/profiles.json'
receipt_path=OUT/'google-registration.json'
if receipt_path.exists():raise SystemExit('Already registered; inspect the existing receipt')
with Store(directory) as store:
 jobs=[j for j in store.jobs() if j['payload'].get('batch_id')=='component-sculptures-20261119-2']
 assert len(jobs)==15 and all(j['state']=='PUBLISHED' for j in jobs),'Finish and verify the original fifteen deliveries first'
 config=read_json(profile_path)
 assert name not in config['profiles']
 atomic_json(OUT/'profiles-before-google.json',config)
 atomic_json(OUT/'bindings-before-google.json',read_json(directory/'bindings.json'))
 config['profiles'][name]=read_json(OUT/'google-profile-proposed.json')
 atomic_json(profile_path,config)
 settings=Settings(profile_path)
 chrome=Chrome(settings,directory)
 prepared=read_json(OUT/'google-cal-state/bindings.json')['verification']
 first=read_json(OUT/'google-posts-prepared.json')[0]
 assert prepared['job_id']==digest([config['profiles'][name]['channel_key'],first['catalogue_id']])[:32]
 assert prepared['dirty'] is True and prepared['url']==config['profiles'][name]['compose_url']
 chrome.bindings[name]={**prepared,'profile_hash':settings.fingerprint(name)}
 binding,state=chrome.bound(name,mutation=True)
 chrome.call(name,{'op':'claim'})
 chrome.bindings[VERIFICATION]['profile_hash']=chrome.profile_hash(VERIFICATION)
 chrome.save_bindings()
 reserved=read_json(OUT/'reserved-tabs.json')
 reserved.append({'profile':name,'window':binding['window_id'],'tab':binding['tab_id']})
 atomic_json(OUT/'reserved-tabs.json',reserved)
 atomic_json(receipt_path,{'utc':utc(),'profile_id':name,'location_id':config['profiles'][name]['location_id'],
             'profile_hash':settings.fingerprint(name),'binding':binding,'existing_deliveries_preserved':15,
             'prepared_draft_owner_preserved':True,'prepared_job_id':binding['job_id'],'publish_clicks':0})
 print(json.dumps({'registered_profile':name,'prepared_job_id':binding['job_id'],'publish_clicks':0}))
