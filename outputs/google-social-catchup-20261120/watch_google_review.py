"""Bounded read-only follow-up for Google's review and video processing.

No manifest enqueue, prepare, submit, replacement post or existing-post edit.
The normal publisher lock and background-tab guards remain mandatory.
"""
import datetime,json,subprocess,sys,time
from pathlib import Path
OUT=Path(__file__).parent;ROOT=OUT.parents[1];sys.path.insert(0,str(ROOT/'social-publisher'))
from common import atomic_json,utc
deadline=time.time()+24*60*60
status=OUT/'google-review-watch-status.json'
for attempt in range(49):
 started=utc()
 with (OUT/'google-review-watch.log').open('a') as out,(OUT/'google-review-watch-error.txt').open('a') as err:
  result=subprocess.run(['/usr/bin/python3',str(OUT/'reconcile_google_holds.py')],cwd=str(ROOT),stdout=out,stderr=err)
 for script in ['reconcile_facebook_history.py','audit_full_catchup.py','update_history_report.py']:
  with (OUT/'google-review-watch.log').open('a') as out,(OUT/'google-review-watch-error.txt').open('a') as err:
   subprocess.run(['/usr/bin/python3',str(OUT/script)],cwd=str(ROOT),stdout=out,stderr=err)
 records=json.loads((OUT/'platform-hold-readback-results.json').read_text()) if (OUT/'platform-hold-readback-results.json').exists() else {}
 pending=[r for r in records.get('results',[]) if r['state']!='PUBLISHED']
 complete=bool(records) and result.returncode==0 and not pending
 expired=time.time()>=deadline or attempt==48
 atomic_json(status,{'utc':utc(),'state':'COMPLETE' if complete else 'REVIEW_WINDOW_ENDED' if expired else 'WAITING_FOR_GOOGLE_REVIEW','read_only':True,'attempt':attempt+1,'last_started_utc':started,'last_returncode':result.returncode,'pending_job_ids':[r['job_id'] for r in pending],'deadline_utc':datetime.datetime.fromtimestamp(deadline,datetime.timezone.utc).isoformat(),'interval_seconds':1800,'next_check_utc':None if complete or expired else datetime.datetime.fromtimestamp(min(time.time()+1800,deadline),datetime.timezone.utc).isoformat(),'no_publication_actions':True})
 if complete or expired:break
 # A closed or externally navigated owned tab must be inspected before any
 # future read. Never rebind, reopen a browser, or adopt a user's destination.
 fatal={'CHROME_NOT_RUNNING','TAB_CLOSED','RESERVED_TAB_NOT_BOUND','TAB_NAVIGATED_EXTERNALLY','NORMAL_PROFILE_REQUIRED','CONFIG_CHANGED','TAB_OWNERSHIP_LOST'}
 if any(r.get('readback_error_code') in fatal for r in pending):
  data=json.loads(status.read_text());data.update(state='USER_BROWSER_STATE_NEEDS_INSPECTION',next_check_utc=None);atomic_json(status,data);break
 # Use one fixed wake time, without keeping a browser or database lock open.
 wake=min(time.time()+1800,deadline)
 while time.time()<wake:time.sleep(max(0,min(30,wake-time.time())))
