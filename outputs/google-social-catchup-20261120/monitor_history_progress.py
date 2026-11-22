import subprocess,time
from pathlib import Path
OUT=Path(__file__).parent
while True:
 subprocess.run(['/usr/bin/python3',str(OUT/'update_history_report.py')],check=True)
 time.sleep(30)
