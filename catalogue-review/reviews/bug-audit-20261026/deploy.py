from pathlib import Path
from contextlib import closing
import sqlite3,hashlib,json,urllib.request,subprocess,os,signal,time,datetime
TASK=Path(__file__).resolve().parent;APP=TASK.parents[1];RUNTIME=Path('/Users/tprice/Library/Application Support/BoldstoneReview');URL='http://127.0.0.1:8767'
def get(path):
    with urllib.request.urlopen(URL+path,timeout=20) as response:return json.load(response)
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
health=get('/api/health');sync=get('/api/dropbox-sync')
assert health['version']=='2.7.0',health
if sync['state']=='checking':raise SystemExit('Dropbox refresh is running; deployment deferred.')
files=[]
for path in (TASK/'work').rglob('*'):
    if not path.is_file() or '__pycache__' in path.parts or path.suffix=='.pyc':continue
    rel=path.relative_to(TASK/'work');old=TASK/'before'/rel
    if not old.exists() or digest(path)!=digest(old):
        live=APP/rel
        assert (not live.exists()) if not old.exists() else digest(live)==digest(old), 'Concurrent edit: '+str(rel)
        files.append(rel)
with closing(sqlite3.connect((RUNTIME/'reviews.sqlite3').as_uri()+'?mode=ro',uri=True)) as db:
    for table in ['deletion_jobs','deletion_batches']:
        assert db.execute('select count(*) from '+table+" where state='executing'").fetchone()[0]==0,'Deletion is executing; deployment deferred.'
    before_rows=db.execute('SELECT * FROM reviews ORDER BY kind,product_id,item_id').fetchall()
    before_events=db.execute('select count(*) from events').fetchone()[0]
    with closing(sqlite3.connect(TASK/'before-deployment.sqlite3')) as backup:db.backup(backup)
token_digest=digest(RUNTIME/'server-token');pid=int((RUNTIME/'server.pid').read_text())
cmd=subprocess.check_output(['ps','-p',str(pid),'-o','command='],text=True)
assert str(APP/'server.py') in cmd
os.kill(pid,signal.SIGTERM)
for _ in range(50):
    try:os.kill(pid,0)
    except ProcessLookupError:break
    time.sleep(.1)
else:raise RuntimeError('Old app server did not stop')
for rel in files:
    destination=APP/rel;destination.parent.mkdir(exist_ok=True,parents=True)
    tmp=destination.with_name(destination.name+'.audit-tmp');tmp.write_bytes((TASK/'work'/rel).read_bytes());tmp.replace(destination)
with (RUNTIME/'server.log').open('a') as log:
    process=subprocess.Popen(['/opt/homebrew/bin/python3',str(APP/'server.py')],cwd=APP,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
(RUNTIME/'server.pid').write_text(str(process.pid))
for _ in range(80):
    try:
        health=get('/api/health')
        if health['version']=='2.7.1':break
    except Exception:pass
    if process.poll() is not None:raise RuntimeError('Updated server failed to start')
    time.sleep(.25)
else:raise RuntimeError('Updated server did not respond')
with closing(sqlite3.connect((RUNTIME/'reviews.sqlite3').as_uri()+'?mode=ro',uri=True)) as db:
    after_rows=db.execute('SELECT * FROM reviews ORDER BY kind,product_id,item_id').fetchall()
    assert before_rows==after_rows,'Reviews changed during deployment; inspect concurrent user activity, never restore over it.'
    assert db.execute('select count(*) from events').fetchone()[0]==before_events
assert digest(RUNTIME/'server-token')==token_digest
receipt={'deployed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'health':health,'pid':process.pid,'review_rows_preserved':len(before_rows),'events_preserved':before_events,'session_token_preserved':True,'code_sha256':{str(rel):digest(APP/rel) for rel in files},'agent_native_mutations':0}
(TASK/'deployment.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt,indent=2))
