"""Exercise the app renderer on sealed prior metadata, without an active database."""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from boldstone.reporting import save_review_report
from boldstone.util import new_id

HERE = Path(__file__).resolve().parent
LANE = HERE / 'case-normalization-handoff-20261024T165515Z'
packet = json.loads((LANE / 'handoff.json').read_text())
seal = json.loads((LANE / 'sealed-handoff.json').read_text())
for source in seal['files']:
    assert hashlib.sha256(Path(source['path']).read_bytes()).hexdigest() == source['sha256']
output = Path('/Users/tprice/Library/Application Support/BoldstoneLocal/reports')
state = SimpleNamespace(config=SimpleNamespace(directory=lambda kind: output if kind == 'reports' else None))
rows = []
for item in packet['rows']:
    metadata = dict(item['file_metadata'])
    assert metadata.get('tag') == 'file'
    metadata['.tag'] = metadata['tag']
    rows.append({'asset_id': item['expected_file_id'], 'outcome': 'PRIOR_METADATA_REFERENCE_ONLY',
        'option_id': item['option_id'], 'name': item['name'], 'metadata': metadata,
        'original_metadata_observations': item['metadata_observations'],
        'source_class': 'SEALED_PRIOR_METADATA_NORMALIZED_TAG_NO_NEW_LIVE_READ'})
result = {'batch_id': 'RECORDED-NAVIGATION-DEMO', 'attempt_id': new_id('local-render'),
    'objective_outcome': 'LOCAL_HTML_RENDERING_ONLY_NOT_A_NEW_FIXED_BATCH_ATTEMPT',
    'source_handoff': str(LANE / 'sealed-handoff.json'), 'results': rows,
    'new_live_reads': 0, 'native_mutations': 0, 'database_writes': 0}
paths = save_review_report(state, result)
assert json.loads(Path(paths['json']).read_text()) == result
manifest = {'status': 'LOCAL_RENDERING_DEMO_FROM_PRIOR_REAL_METADATA', 'files': [
    {'kind': kind, 'path': path, 'sha256': hashlib.sha256(Path(path).read_bytes()).hexdigest()}
    for kind, path in paths.items()], 'new_live_reads': 0, 'database_writes': 0, 'native_writes': 0}
(HERE / 'application-link-demo.json').write_text(json.dumps(manifest, indent=2) + '\n')
print(json.dumps(manifest, indent=2))
