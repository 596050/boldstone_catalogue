"""Exercise the real Vision worker using small copies of existing local previews."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import hashlib
import json
import shutil
import sys

out = Path(__file__).resolve().parent
sys.path.insert(0, str(out.parent.parent))
from similarity import Similarity
from projection import Projection

samples = json.loads((out / 'local-worker-sources.json').read_text())
paths = [Path(row['path']) for row in samples]
assert len(paths) == 2
digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
before = [digest(path) for path in paths]
fixture = out / 'local-worker-fixture'
fixture.mkdir(exist_ok=True)
copies = [fixture / ('sample-' + str(i) + path.suffix) for i, path in enumerate(paths)]
for path, target in zip(paths, copies):
    shutil.copy2(path, target)
cat = SimpleNamespace(assets={name: {} for name in ('A', 'B', 'A-copy', 'missing', 'separate')},
    paths={'A': (copies[0], 'preview'), 'A-copy': (copies[0], 'preview'),
           'B': (copies[1], 'preview'), 'separate': (copies[1], 'preview')},
    preview_paths={}, edges={}, products={})
view = Projection(cat, [])
with patch('similarity.ThreadPoolExecutor') as pool:
    service = Similarity(fixture)
existing = Path.home() / 'Library/Application Support/BoldstoneReview/similarity-v1' / service.binary.name
if existing.is_file():
    service.binary = existing
job = service.start({'groups': [['A', 'B', 'A-copy', 'missing'], ['separate']]}, view)
request = pool.return_value.submit.call_args.args[2]
result = service.root / (job['job_id'] + '.result.json')
result.write_text('{"order":')
service._run(job['job_id'], request)
status = service.status(job['job_id'])
assert status['state'] == 'ready', status
assert status['order'] == ['A', 'A-copy', 'B', 'missing', 'separate'], status
assert status['analysed'] == 4 and status['missing_ids'] == ['missing'], status
with patch('similarity.subprocess.run') as worker:
    service._run(job['job_id'], request)
    worker.assert_not_called()
assert [digest(path) for path in paths] == before, 'An original source image changed'
receipt = {'result': status, 'damaged_result_rebuilt': True, 'valid_cache_reused': True,
           'source_bytes_unchanged': True, 'source_sha256': before,
           'dropbox_calls': 0, 'review_changes': 0}
(out / 'local-worker-verification.json').write_text(json.dumps(receipt, indent=2))
print(json.dumps(receipt))
