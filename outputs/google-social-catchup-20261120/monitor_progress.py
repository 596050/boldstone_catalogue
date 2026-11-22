"""Refresh only the local receipt review, then stop when the catch-up completes."""
import json,os,subprocess,time
from pathlib import Path
OUT=Path(__file__).parent
(OUT/'progress-monitor.pid').write_text(str(os.getpid())+'\n')
while True:
 subprocess.run(['/usr/bin/python3',str(OUT/'update_report.py')],check=True)
 report=json.loads((OUT/'publication-receipts.json').read_text())
 if report['publication_complete']:break
 time.sleep(25)
