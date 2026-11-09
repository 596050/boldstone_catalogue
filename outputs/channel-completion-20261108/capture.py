"""Capture current non-secret app inputs and the exact master pointer."""
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

OUT=Path(__file__).parent
ROOT=OUT.parents[1]
for endpoint in ['specifications','coverage','jobs','health']:
    with urllib.request.urlopen('http://127.0.0.1:8767/api/'+endpoint,timeout=120) as r:data=json.load(r)
    (OUT/('app-'+endpoint+'.json')).write_text(json.dumps(data,indent=2)+'\n')
pointer=json.loads((ROOT/'sculpture-catalogue/current-master.json').read_text())
(OUT/'source-pointer-before.json').write_text(json.dumps(pointer,indent=2)+'\n')
with urllib.request.urlopen('http://127.0.0.1:8767/api/bootstrap',timeout=120) as r:bootstrap=json.load(r)
jobs=json.loads((OUT/'app-jobs.json').read_text())
summary=dict(captured_utc=datetime.now(timezone.utc).isoformat(),products=len(bootstrap['products']),
             data_directory=bootstrap['data_directory'],job_summary=jobs.get('summary'),
             master_path=pointer['current_app_review_workbook']['path'],master_revision=pointer['current_app_review_workbook']['dropbox']['rev'])
(OUT/'capture-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
