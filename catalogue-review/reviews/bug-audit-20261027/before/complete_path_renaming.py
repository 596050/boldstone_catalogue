#!/usr/bin/env python3
"""Finish the authorized filename pass and release the app's native job queue.

No deletion/upload/folder-move calls. Existing uncertain requests are handled
only by the per-batch executor's durable IDs and independently checked receipts.
"""
import argparse
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

from renumber_current_paths import PROJECT, now, save, sha, prepare
from finish_current_path_batches import inventory


def update_reservation(runtime, root, reason, active=True):
    save(runtime/'native-writer-reservation.json', {'active':active,'label':'Dropbox filename renaming',
         'reason':reason,'root':str(root),'updated_at':now()})


def command(script,root,lease,extra=()):
    subprocess.run([str(PROJECT/'application/.venv/bin/python'),str(PROJECT/'image-processing'/script),'--root',str(root),*extra],
                   check=True,pass_fds=(lease,))


def finish(root, runtime):
    root=root.resolve();runtime=runtime.resolve()
    sys.path.insert(0,str(PROJECT/'catalogue-review'))
    from delete_dropbox import connection
    lease_path=runtime/'native-jobs/writer.lock';lease_path.parent.mkdir(parents=True,exist_ok=True)
    with (root/'completion-driver.lock').open('a') as guard:
        fcntl.flock(guard,fcntl.LOCK_EX|fcntl.LOCK_NB)
        update_reservation(runtime,root,'Finishing the path-derived filenames. Image moves and deletions are queued behind this pass.')
        with lease_path.open('a') as lease:
            fcntl.flock(lease,fcntl.LOCK_EX)
            try:
                manifest=json.loads((root/'manifest.json').read_text())
                command('finish_current_path_batches.py',root,lease.fileno(),['--apply','--batch-size','1000'])
                if not (root/'batch-pass-complete.json').exists():
                    raise RuntimeError('The filename pass is held before its next batch; no new job was started.')
                # User deletions during the earlier pass change per-folder
                # membership. Fresh plans compact only the retained files.
                for attempt in range(1,4):
                    follow=root/f'followup-{attempt:02d}'
                    if not (follow/'manifest.json').exists():
                        follow.mkdir(exist_ok=True)
                        with connection(PROJECT) as (client,_):snapshot=inventory(client,manifest)
                        save(follow/'native-before.json',snapshot['wall'],immutable=True)
                        save(follow/'workshop-before.json',snapshot['workshop'],immutable=True)
                        prepare(follow,run_id='20261026-'+follow.name)
                    planned=json.loads((follow/'manifest.json').read_text())
                    if not planned['counts']['renames']:
                        break
                    update_reservation(runtime,root,f"Closing gaps after recent deletions: follow-up {attempt}, {planned['counts']['renames']} filenames.")
                    command('finish_current_path_batches.py',follow,lease.fileno(),['--apply','--batch-size','1000'])
                    if not (follow/'batch-pass-complete.json').exists():raise RuntimeError('A follow-up batch needs review.')
                else:
                    raise RuntimeError('The folders continued changing during three fresh passes. Review before continuing.')
                update_reservation(runtime,root,'Independently checking all retained file IDs, bytes, names, sequence numbers and existing links.')
                command('verify_current_path_renames.py',root,lease.fileno())
                overlay=root/'current-filename-paths.json'
                value=json.loads(overlay.read_text())
                verification=json.loads(Path(value['verification']).read_text())
                if verification['status']!='PASS':raise RuntimeError('Final filename verification did not pass.')
                save(runtime/'filename-readback.json',{'path':str(overlay),'sha256':sha(overlay)})
                # The server must install a fresh image inventory before queued
                # jobs plan source paths, otherwise they could use old names.
                token=(runtime/'server-token').read_text().strip()
                request=urllib.request.Request('http://127.0.0.1:8767/api/dropbox-sync',data=b'{}',
                    headers={'Content-Type':'application/json','X-Review-Token':token,'Origin':'http://127.0.0.1:8767'})
                json.load(urllib.request.urlopen(request,timeout=30))
                deadline=time.monotonic()+420
                while time.monotonic()<deadline:
                    state=json.load(urllib.request.urlopen('http://127.0.0.1:8767/api/dropbox-sync',timeout=30))
                    if state.get('last_checked','') and state['last_checked']>=value['at'] and state['state']=='ready':break
                    time.sleep(2)
                else:raise RuntimeError('Final native verification passed; the app still needs its current image refresh.')
                save(root/'completion.json',{'at':now(),'state':'completed','verification':value['verification'],
                     'current_filename_paths':str(overlay),'current_filename_paths_sha256':sha(overlay)},immutable=True)
                update_reservation(runtime,root,'Filename renaming and independent verification are complete.',active=False)
                print('All filename work verified. App native jobs released.',flush=True)
            except BaseException as error:
                update_reservation(runtime,root,'The filename pass needs checking before new native jobs can run. See the retained completion-error receipt.')
                save(root/'completion-error.json',{'at':now(),'state':'needs_review','message':str(error),'type':type(error).__name__})
                raise


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True)
    p.add_argument('--runtime',type=Path,default=Path.home()/'Library/Application Support/BoldstoneReview')
    p.add_argument('--apply',action='store_true');a=p.parse_args()
    if not a.apply:raise SystemExit('--apply required')
    finish(a.root,a.runtime)
