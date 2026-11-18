"""Inspect and calibrate the public UI in an owned background tab."""
import json
import sys
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'social-publisher'))
from chrome import Chrome
from settings import Settings
from common import atomic_json

chrome = Chrome(Settings(), os.environ.get('BOLDSTONE_CAL_STATE', ROOT / 'social-publisher/state'))
name, operation = sys.argv[1:3]
args = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
if operation == 'navigate':
    result = chrome.navigate(name, args['url'])
else:
    result = chrome.call(name, {'op': operation, **args})
if operation == 'snapshot':
    atomic_json(Path(__file__).parent / (name + '-snapshot.json'), result)
    print(json.dumps({'url': result['url'], 'text': result['text'][:8000], 'controls': [{k:c[k] for k in ['tag','role','name','disabled','expanded']} for c in result['controls'] if c['name'] not in {'0', '‑‑', 'Edit', 'Hide', 'Show', 'Delete'}]}, ensure_ascii=False))
else:
    print(json.dumps(result, ensure_ascii=False))
