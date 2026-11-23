"""Re-read the existing Brancusi public post, without pagination or submission."""
from pathlib import Path
import json,sys,sqlite3,shutil
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1]
sys.path.insert(0,str(ROOT/'social-publisher'))
from common import atomic_json,read_json,digest,utc
from settings import Settings
from google_fast import GoogleFastChrome
from workflow import Workflow
from journal import Store
from google_public import GooglePublicReadback

main=ROOT/'social-publisher/state';jid='579120726d0e904918fbdd95e5b92b8c'
with sqlite3.connect((main/'outbox.sqlite3').as_uri()+'?mode=ro',uri=True) as db:
    db.row_factory=sqlite3.Row;job=Store.decode(db.execute('SELECT * FROM jobs WHERE id=?',(jid,)).fetchone())
p=job['payload'];current=Settings();old=Settings(OUT/'existing-google-config/profiles.json')
assert old.fingerprint(p['profile_id'])==p['profile_hash'] and job['state']=='PUBLISHED'
cal_path=ROOT/'outputs/google-social-catchup-20261120/google-public-readback-context.json'
cal=read_json(cal_path);receipt=job['receipt'];prior_path=Path(receipt['evidence_path']);prior=read_json(prior_path)
assert digest(prior_path.read_bytes())==receipt['evidence_sha256']
assert p['profile_snapshot']['location_id']==cal['location_id']==current.profile(p['profile_id'])['location_id']
assert p['profile_snapshot']['account_name']==current.profile(p['profile_id'])['account_name']==prior['account_name']
assert prior['native_record']['post_id']==receipt['google_post_id']=='7043713459646511209'
assert prior['native_record']['location_id']==cal['location_id'] and prior['profile_hash']==p['profile_hash']
assert current.fingerprint(p['profile_id']) in cal['profile_hashes']
cal['profile_hashes']=list(dict.fromkeys(cal['profile_hashes']+[p['profile_hash']]))
cal['references'].append({'path':str(prior_path),'sha256':digest(prior_path.read_bytes())})
cal['frozen_profile_identity_extension']={'utc':utc(),'same_location_and_account_name':True,'original_published_post_id':receipt['google_post_id'],
    'source_calibration_path':str(cal_path),'source_calibration_sha256':digest(cal_path.read_bytes()),'frozen_profile_hash':p['profile_hash']}
local_cal=OUT/'existing-google-public-calibration.json';atomic_json(local_cal,cal)
main_chrome=GoogleFastChrome(current,main)
main_chrome.navigate('verification',p['profile_snapshot']['inventory_url'],recovery=True)
bindings=read_json(main/'bindings.json');state=OUT/'existing-google-state'
atomic_json(state/'bindings.json',{name:{**bindings[name],**({'profile_hash':digest({'role':'verification','allowed_hosts':['www.google.com']})} if name=='verification' else {})} for name in [p['profile_id'],'verification']})
shutil.copyfile(main/'evidence'/(jid+'-google-photo.json'),state/'evidence'/(jid+'-google-photo.json'))
chrome=GoogleFastChrome(old,state)
try:
    fresh=GooglePublicReadback(Workflow(old,chrome,state),local_cal,receipt['google_post_id']).verify(job,native_url=receipt['native_url'])
    atomic_json(OUT/'existing-google-verified.json',{'status':'EXISTING_POST_REVERIFIED','job_id':jid,'post_key':p['post_key'],'title':p['title'],'receipt':fresh})
    print(json.dumps({'status':'EXISTING_POST_REVERIFIED','post_id':fresh['google_post_id'],'native_status':fresh['google_status'],'url':fresh['native_url']}),flush=True)
finally:
    latest=read_json(main/'bindings.json');reader=chrome.bindings['verification'];original=latest['verification']
    assert reader['owner']==original['owner'] and reader['tab_id']==original['tab_id']
    latest['verification']={**reader,'profile_hash':original['profile_hash']}
    atomic_json(main/'bindings.json',latest);chrome.close()
