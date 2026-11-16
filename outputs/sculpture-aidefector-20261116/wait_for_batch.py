import json
import subprocess
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
manifest = json.loads((BASE / 'manifest.json').read_text())
number = int(sys.argv[1])
batch = next(b for b in manifest['batches'] if b['number'] == number)
groups = [g for g in manifest['groups'] if g['label'] in batch['groups']]
outputs = [Path(g['output_folder']) / (f['sha256'] + '.png') for g in groups for f in g['files']]
deadline = time.monotonic() + 180


def complete(path):
    try:
        with path.open('rb') as stream:
            stream.seek(-12, 2)
            return stream.read() == b'\x00\x00\x00\x00IEND\xaeB`\x82'
    except (OSError, ValueError):
        return False


print(json.dumps({'batch': number, 'waiting_for_images': len(outputs)}), flush=True)
while not all(complete(p) for p in outputs):
    if time.monotonic() > deadline:
        print(json.dumps({'batch': number, 'complete_images': sum(complete(p) for p in outputs), 'status': 'still_processing'}), flush=True)
        sys.exit(2)
    time.sleep(0.25)

subprocess.run([sys.executable, str(BASE / 'verify_processing.py')], check=True)
subprocess.run([sys.executable, str(BASE / 'build_index.py')], check=True)
