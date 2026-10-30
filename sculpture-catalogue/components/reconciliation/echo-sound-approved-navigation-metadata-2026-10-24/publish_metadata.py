"""Commit the reviewed Echo metadata pointer and three controls with exact guards."""
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

H = Path(__file__).resolve().parent
B = H.parents[2]
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(path, value):
    path = Path(path)
    tmp = path.with_name(path.name + '.echo-navigation-tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    os.replace(tmp, path)

assert not (H / 'publication-receipt.json').exists()
m = read(H / 'input-manifest.json')
p = read(H / 'prepared-pointer.json')
old = read(m['pointer']['snapshot'])
freeze = read(H / 'candidate-freeze.json')
for path, expected in freeze['frozen_artifacts'].items():
    assert sha(path) == expected, path
for key, x in m.items():
    assert sha(x['path']) == sha(x['snapshot']) == x['sha256'], key
assert p['register_sha256'] == old['register_sha256'] == freeze['candidate_register_sha256']
assert p['workbook_sha256'] == old['workbook_sha256'] == freeze['candidate_workbook_sha256']
assert sha(B / p['register']) == p['register_sha256'] and sha(B / p['workbook']) == p['workbook_sha256']
assert p['latest_image_coverage_audit'] == old['latest_image_coverage_audit']
qa = read(H / 'independent-qa-reference.json')
assert sha(qa['path']) == qa['sha256'] and sha(qa['seal_path']) == qa['seal_sha256']
q = read(qa['path'])
assert q['status'] == 'PASS' and q['checks_passed'] == q['checks_total']
assert q['candidate_register_sha256'] == p['register_sha256'] and q['candidate_workbook_sha256'] == p['workbook_sha256']
assert q['candidate_freeze_sha256'] == sha(H / 'candidate-freeze.json')
assert q['frozen_artifacts']
for path, expected in q['frozen_artifacts'].items():
    assert sha(path) == expected, path
updates = read(H / 'prepared-control-paths.json')
for key, path in updates.items():
    assert read(path)['current_master_catalogue'] == p
if '--prepare' in sys.argv:
    print('ALL_METADATA_PUBLICATION_GUARDS_PASS_PREPARED_ONLY')
    raise SystemExit(0)
for key, x in m.items():
    assert sha(x['path']) == x['sha256'], key
for key, path in updates.items():
    write(m[key]['path'], read(path))
write(B / 'current-master.json', p)
assert read(B / 'current-master.json') == p
for key in updates:
    assert read(m[key]['path'])['current_master_catalogue'] == p
assert sha(B / p['register']) == old['register_sha256'] and sha(B / p['workbook']) == old['workbook_sha256']
assert sha(m['audit']['path']) == m['audit']['sha256']
receipt = {**read(H / 'import-summary.json'), 'status': 'PASS_PUBLISHED_AND_READ_BACK', 'publication_mode': 'METADATA_ONLY_NO_WORKBOOK_OR_REGISTER_EDITS',
    'recorded_utc': p['recorded_utc'], 'committed_utc': datetime.now(timezone.utc).isoformat(),
    'preceding_publication_receipt': old['publication_receipt'], 'preceding_pointer_sha256': m['pointer']['sha256'],
    'current_master_pointer_sha256': sha(B / 'current-master.json'),
    'register': str(B / p['register']), 'register_sha256': p['register_sha256'],
    'workbook': str(B / p['workbook']), 'workbook_sha256': p['workbook_sha256'],
    'audit_sha256': m['audit']['sha256'],
    'controls_sha256': {m[key]['path']: sha(m[key]['path']) for key in updates},
    'independent_qa': qa, 'candidate_freeze_sha256': sha(H / 'candidate-freeze.json'),
    'new_native_map': p['current_native_reference_map'], 'new_asset_map': p['current_asset_reference_map']}
write(H / 'publication-receipt.json', receipt)
write(H / 'WORK_STATE.json', {'status': 'PUBLISHED_VERIFIED_METADATA_ONLY', 'publication_receipt': str(H / 'publication-receipt.json')})
print(json.dumps(receipt, indent=2))
