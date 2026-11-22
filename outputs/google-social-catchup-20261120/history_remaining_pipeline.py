"""Serially deliver frozen reviewed batches after the currently active batch."""
import fcntl,json,sqlite3,subprocess,time
from pathlib import Path
OUT=Path(__file__).parent;ROOT=OUT.parents[1]
def complete(part):
 folder=OUT/part;manifest=folder/('delivery-manifest.json' if (folder/'delivery-manifest.json').exists() else 'manifest.json')
 data=json.loads(manifest.read_text());wanted={p['post_key'] for p in data['posts']}
 db=sqlite3.connect('file:'+str(ROOT/'social-publisher/state/outbox.sqlite3')+'?mode=ro',uri=True)
 rows={k:(i,s) for i,k,s in db.execute("SELECT id,post_key,state FROM jobs WHERE json_extract(payload,'$.batch_id')=?",(data['batch_id'],)) if k in wanted};db.close()
 holds={h['job_id'] for h in json.loads((OUT/'platform-publication-holds.json').read_text())['holds']} if (OUT/'platform-publication-holds.json').exists() else set()
 return len(rows)==len(wanted) and all(s=='PUBLISHED' or i in holds for i,s in rows.values())
while not complete('history-2026-part2'):time.sleep(10)
for part in ['history-2026-part3','history-2026-part4','history-video-part1','history-legacy-part1','history-legacy-part2','history-legacy-part3','history-reel-still']:
 while True:
  with (ROOT/'social-publisher/state/runner.lock').open('a') as lock:
   try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
   except BlockingIOError:time.sleep(3);continue
   fcntl.flock(lock,fcntl.LOCK_UN)
  break
 print('Starting '+part,flush=True)
 with (OUT/part/'publish.log').open('a') as output,(OUT/part/'publish-error.txt').open('a') as error:
  command=['/usr/bin/python3',str(OUT/'publish_video_batch.py')] if part=='history-video-part1' else ['/usr/bin/python3',str(OUT/'publish_history_batch.py'),part]
  result=subprocess.run(command,cwd=str(ROOT),stdout=output,stderr=error)
 if result.returncode or not complete(part):
  if part=='history-video-part1':print('Video readback pending; continue the independent photo queue',flush=True);continue
  raise SystemExit('Readback or preparation needs review in '+part)
 print('Processed '+part+'; platform holds remain separately recorded',flush=True)
