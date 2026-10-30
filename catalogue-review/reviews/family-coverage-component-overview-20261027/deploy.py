"""Deploy only while the native writer is idle; retain exact review state."""
from pathlib import Path
import fcntl, hashlib, json, os, signal, sqlite3, subprocess, time, urllib.request

here=Path(__file__).resolve().parent
app=here.parents[1]
runtime=Path.home()/'Library/Application Support/BoldstoneReview'
tables=['reviews','events','operations','deletion_jobs','deletion_batches','background_jobs','deletion_reviews']
def get(path):
    with urllib.request.urlopen('http://127.0.0.1:8767'+path,timeout=10) as response:return json.load(response)
def snapshot():
    with sqlite3.connect('file:'+str(runtime/'reviews.sqlite3')+'?mode=ro',uri=True) as db:
        return {table:{'count':len(rows),'sha256':hashlib.sha256(json.dumps(rows,ensure_ascii=False).encode()).hexdigest()}
                for table in tables for rows in [db.execute('SELECT * FROM '+table+' ORDER BY rowid').fetchall()]}
with (runtime/'native-jobs/writer.lock').open('a') as lease:
    fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
    jobs=get('/api/jobs')
    assert jobs['active_count']==0 and not jobs['reservation'], 'Native work is active; no restart performed'
    assert get('/api/health')['version']=='2.11.1'
    pid=int((runtime/'server.pid').read_text())
    command=subprocess.check_output(['ps','-p',str(pid),'-o','command='],text=True).strip()
    assert str(app/'server.py') in command, command
    token_hash=hashlib.sha256((runtime/'server-token').read_bytes()).hexdigest()
    os.kill(pid,signal.SIGTERM)
    for _ in range(50):
        if subprocess.run(['kill','-0',str(pid)],capture_output=True).returncode:break
        time.sleep(.1)
    else:raise RuntimeError('Server did not stop; no forced kill performed')
    with sqlite3.connect(runtime/'reviews.sqlite3') as source,sqlite3.connect(here/'pre-deployment.sqlite3') as target:source.backup(target)
    before=snapshot()
    (here/'pre-deployment-state.json').write_text(json.dumps(before,indent=2))
    log=(runtime/'server.log').open('ab')
    process=subprocess.Popen(['/opt/homebrew/bin/python3',str(app/'server.py')],cwd=app,
                             stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
    (runtime/'server.pid').write_text(str(process.pid)+'\n')
    health=None
    for _ in range(80):
        try:
            health=get('/api/health')
            if health['version']=='2.12.0':break
        except Exception:pass
        if process.poll() is not None:raise RuntimeError('New server exited; inspect server log')
        time.sleep(.25)
    assert health and health['version']=='2.12.0'
    after=snapshot()
    receipt={'old_pid':pid,'new_pid':process.pid,'health':health,'before':before,'after':after,
             'all_rows_unchanged':before==after,'token_unchanged':token_hash==hashlib.sha256((runtime/'server-token').read_bytes()).hexdigest()}
    (here/'deployment.json').write_text(json.dumps(receipt,indent=2))
    assert receipt['all_rows_unchanged'] and receipt['token_unchanged']
    print(json.dumps({k:v for k,v in receipt.items() if k not in ('before','after')}))
