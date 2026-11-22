"""Continue remaining reviewed photos after the separately running legacy batch."""
import fcntl,json,sqlite3,subprocess,time
from pathlib import Path
OUT=Path(__file__).parent;ROOT=OUT.parents[1]
def complete(part):
 f=OUT/part/'manifest.json';d=json.loads(f.read_text());wanted={r['post_key'] for r in d['posts']};c=sqlite3.connect('file:'+str(ROOT/'social-publisher/state/outbox.sqlite3')+'?mode=ro',uri=True)
 rows={k:(i,s) for i,k,s in c.execute('SELECT id,post_key,state FROM jobs WHERE json_extract(payload,\'$.batch_id\')=?',(d['batch_id'],)) if k in wanted};c.close();holds={r['job_id'] for r in json.loads((OUT/'platform-publication-holds.json').read_text())['holds']}
 return len(rows)==len(wanted) and all(s=='PUBLISHED' or i in holds for i,s in rows.values())
while not complete('history-legacy-part1'):time.sleep(10)
for part in ['history-video-part1','history-legacy-part2','history-legacy-part3','history-reel-still','history-facebook-extra1']:
 while True:
  with (ROOT/'social-publisher/state/runner.lock').open('a') as lock:
   try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
   except BlockingIOError:time.sleep(3);continue
   fcntl.flock(lock,fcntl.LOCK_UN)
  break
 print('Starting '+part,flush=True)
 command=['/usr/bin/python3',str(OUT/'publish_video_batch.py')] if part=='history-video-part1' else ['/usr/bin/python3',str(OUT/'publish_history_batch.py'),part]
 with (OUT/part/'publish.log').open('a') as out,(OUT/part/'publish-error.txt').open('a') as err:result=subprocess.run(command,cwd=str(ROOT),stdout=out,stderr=err)
 if part=='history-video-part1' and (result.returncode or not complete(part)):
  print('Video stage needs native inspection; continue the independent reviewed photos',flush=True);continue
 if result.returncode or not complete(part):raise SystemExit('Native readback or preparation needs inspection in '+part)
 print('Processed '+part,flush=True)
for script in ['reconcile_facebook_history.py','audit_full_catchup.py','update_history_report.py']:
 subprocess.run(['/usr/bin/python3',str(OUT/script)],cwd=str(ROOT),check=True)
print('Reviewed delivery queues processed; starting read-only Google review checks',flush=True)
with (OUT/'google-review-watch-launch.log').open('a') as out,(OUT/'google-review-watch-launch-error.txt').open('a') as err:
 subprocess.Popen(['/usr/bin/python3','-u',str(OUT/'watch_google_review.py')],cwd=str(ROOT),stdout=out,stderr=err,start_new_session=True)
