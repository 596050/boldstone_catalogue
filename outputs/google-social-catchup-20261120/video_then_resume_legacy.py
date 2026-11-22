"""Use the shared writer lock serially, then resume the exact retained photo job."""
import subprocess
from pathlib import Path
OUT=Path(__file__).parent;ROOT=OUT.parents[1]
with (OUT/'history-video-part1/publish.log').open('a') as out,(OUT/'history-video-part1/publish-error.txt').open('a') as err:
 result=subprocess.run(['/usr/bin/python3',str(OUT/'publish_video_batch.py')],cwd=str(ROOT),stdout=out,stderr=err)
print('Video stage exited '+str(result.returncode)+'; photo job retains its original intent and checkpoint',flush=True)
with (OUT/'history-legacy-part1/publish.log').open('a') as out,(OUT/'history-legacy-part1/publish-error.txt').open('a') as err:
 result=subprocess.run(['/usr/bin/python3',str(OUT/'publish_history_batch.py'),'history-legacy-part1'],cwd=str(ROOT),stdout=out,stderr=err)
print('Legacy photo stage exited '+str(result.returncode),flush=True)
