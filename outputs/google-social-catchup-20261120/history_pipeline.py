"""Start the next frozen batch only after its predecessor is fully verified."""
import fcntl,json,sqlite3,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).parent
waiting=OUT/'history-2026-part1';following='history-2026-part2'
manifest=waiting/('delivery-manifest.json' if (waiting/'delivery-manifest.json').exists() else 'manifest.json')
data=json.loads(manifest.read_text());first=data['batch_id'];wanted={p['post_key'] for p in data['posts']}
while True:
 db=sqlite3.connect('file:'+str(ROOT/'social-publisher/state/outbox.sqlite3')+'?mode=ro',uri=True)
 rows={key:state for key,state in db.execute("SELECT post_key,state FROM jobs WHERE json_extract(payload,'$.batch_id')=?",(first,)) if key in wanted};db.close()
 if len(rows)==len(wanted) and all(state=='PUBLISHED' for state in rows.values()):
  with (ROOT/'social-publisher/state/runner.lock').open('a') as lock:
   try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
   except BlockingIOError:time.sleep(3);continue
   fcntl.flock(lock,fcntl.LOCK_UN)
  break
 time.sleep(5)
print('Predecessor fully verified. Starting '+following,flush=True)
with (OUT/following/'publish.log').open('a') as output,(OUT/following/'publish-error.txt').open('a') as error:
 result=subprocess.run(['/usr/bin/python3',str(OUT/'publish_history_batch.py'),following],cwd=str(ROOT),stdout=output,stderr=error)
print('Next batch exited '+str(result.returncode),flush=True)
