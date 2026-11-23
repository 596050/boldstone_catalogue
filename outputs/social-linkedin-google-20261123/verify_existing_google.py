"""Fresh readback of the already published Brancusi Google post; never submits."""
from pathlib import Path
import sys,json,sqlite3,shutil
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1]
sys.path.insert(0,str(ROOT/'social-publisher'))
from common import atomic_json,read_json
from settings import Settings
from google_fast import GoogleFastChrome
from workflow import Workflow
from journal import Store
jid='579120726d0e904918fbdd95e5b92b8c';main=ROOT/'social-publisher/state'
with sqlite3.connect((main/'outbox.sqlite3').as_uri()+'?mode=ro',uri=True) as db:
 db.row_factory=sqlite3.Row;job=Store.decode(db.execute('SELECT * FROM jobs WHERE id=?',(jid,)).fetchone())
p=job['payload'];config=OUT/'existing-google-config';config.mkdir(exist_ok=True);(config/'workflows').mkdir(exist_ok=True)
original=Settings();frozen={'schema_version':1,'policy':original.policy,'profiles':{p['profile_id']:p['profile_snapshot']}}
atomic_json(config/'profiles.json',frozen);atomic_json(config/p['profile_snapshot']['workflow'],p['workflow_snapshot']);settings=Settings(config/'profiles.json');assert settings.fingerprint(p['profile_id'])==p['profile_hash']
state=OUT/'existing-google-state';state.mkdir(exist_ok=True);(state/'evidence').mkdir(exist_ok=True)
bindings=read_json(main/'bindings.json');atomic_json(state/'bindings.json',{name:bindings[name] for name in [p['profile_id'],'verification']})
shutil.copyfile(main/'evidence'/(jid+'-google-photo.json'),state/'evidence'/(jid+'-google-photo.json'))
c=GoogleFastChrome(settings,state);w=Workflow(settings,c,state)
try:
 receipt=w.verify(job,native_url=job['receipt']['native_url']);atomic_json(OUT/'existing-google-verified.json',{'status':'EXISTING_POST_REVERIFIED','job_id':jid,'post_key':p['post_key'],'title':p['title'],'receipt':receipt});print(json.dumps({'status':'EXISTING_POST_REVERIFIED','post_id':receipt['google_post_id'],'native_status':receipt['google_status'],'url':receipt['native_url']}),flush=True)
finally:
 latest=read_json(main/'bindings.json')
 for name in [p['profile_id'],'verification']:
  if name in c.bindings:latest[name]=c.bindings[name]
 atomic_json(main/'bindings.json',latest)
