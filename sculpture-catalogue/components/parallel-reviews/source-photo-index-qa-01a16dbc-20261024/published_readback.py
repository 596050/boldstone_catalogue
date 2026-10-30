"""Bounded local readback of the published metadata index; no shared writes."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
B = Path('/Users/tprice/Documents/boldstone/sculpture-catalogue')
H = B / 'components/reconciliation/source-photo-evidence-index-2026-10-24'
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
read = lambda path: json.loads(Path(path).read_text())
EXPECTED_FREEZE = 'c26ea3c415d7d176de2c61db171f486382586025a828bb27ea339d63481fbbef'
EXPECTED_QA = '679957a0dc47c25717d037236e6e1951a1f54eb12121d3d94d1ba10cd4186ac6'
EXPECTED_QA_SEAL = '3a1e941d60352adfceeb425ec8d5f5e09dc786bfcf18c37be92e4cca65453d5d'
checks = []


def check(label, passed):
    checks.append({'check': label, 'pass': bool(passed)})


receipt = read(H / 'publication-receipt.json')
freeze = read(H / 'candidate-freeze.json')
baseline = read(OUT / 'pre-index-baseline.json')
before = read(OUT / 'pointer.before.json')
qa = read(OUT / 'candidate-readback.json')
seal = read(OUT / 'sealed-candidate-handoff.json')
candidate_path = H / 'prepared-pointer.json'
pointer_path = B / 'current-master.json'
pointer = read(pointer_path)
check('Final frozen candidate unchanged', sha(H / 'candidate-freeze.json') == EXPECTED_FREEZE and all(sha(path) == expected for path, expected in freeze['frozen_artifacts'].items()))
check('Independent candidate QA unchanged', sha(OUT / 'candidate-readback.json') == EXPECTED_QA and sha(OUT / 'sealed-candidate-handoff.json') == EXPECTED_QA_SEAL and qa['status'] == 'PASS' and qa['checks_passed'] == qa['checks_total'] == 110)
check('Independent candidate files seal verifies', all(sha(OUT / path) == expected for path, expected in seal['files'].items()))
check('Published pointer byte-identical to reviewed candidate', sha(pointer_path) == sha(candidate_path) == qa['candidate_pointer_sha256'])
check('Only four pointer metadata fields changed', sorted(k for k in set(before) | set(pointer) if before.get(k) != pointer.get(k)) == ['current_source_photo_review_index', 'latest_master_metadata_change', 'publication_receipt', 'recorded_utc'])
for key, item in baseline['data_files'].items():
    check('Protected data unchanged: ' + key, sha(item['path']) == item['sha256'])
controls = read(H / 'prepared-control-paths.json')
check('Exactly three control destinations', set(controls) == {x['path'] for x in baseline['controls'].values()})
for destination, prepared in controls.items():
    value = read(destination)
    check('Published control byte-identical and synchronized: ' + destination,
          sha(destination) == sha(prepared) == receipt['controls_sha256'][destination]
          and value['current_master_catalogue'] == pointer
          and value['current_source_photo_review_index'] == pointer['current_source_photo_review_index'])
check('Publication receipt confirms exact current pointer and predecessor',
      receipt['status'] == 'PASS_PUBLISHED_AND_READ_BACK'
      and receipt['publication_mode'] == 'SOURCE_PHOTO_EVIDENCE_INDEX_METADATA_ONLY'
      and receipt['current_master_pointer_sha256'] == sha(pointer_path)
      and receipt['preceding_pointer_sha256'] == baseline['pointer_sha256']
      and receipt['preceding_publication_receipt'] == before['publication_receipt'])
check('Publication receipt retains exact data/count/index descriptors',
      receipt['register_sha256'] == pointer['register_sha256'] == qa['candidate_register_sha256']
      and receipt['workbook_sha256'] == pointer['workbook_sha256'] == qa['candidate_workbook_sha256']
      and receipt['counts'] == qa['counts'] == pointer['current_source_photo_review_index']['counts']
      and receipt['source_photo_review_index'] == pointer['current_source_photo_review_index']
      and receipt['all_five_data_artifacts_byte_identical'] is True
      and receipt['new_native_or_platform_writes'] == 0)
check('Publication receipt binds independent QA and seal',
      Path(receipt['independent_qa']['path']) == OUT / 'candidate-readback.json'
      and receipt['independent_qa']['sha256'] == EXPECTED_QA
      and Path(receipt['independent_qa']['seal_path']) == OUT / 'sealed-candidate-handoff.json'
      and receipt['independent_qa']['seal_sha256'] == EXPECTED_QA_SEAL
      and receipt['candidate_freeze_sha256'] == EXPECTED_FREEZE)
result = {'status': 'PASS' if all(x['pass'] for x in checks) else 'FAIL',
          'recorded_utc': datetime.now(timezone.utc).isoformat(), 'phase': 'PUBLISHED_METADATA_READBACK',
          'checks_passed': sum(x['pass'] for x in checks), 'checks_total': len(checks), 'checks': checks,
          'current_pointer_sha256': sha(pointer_path), 'candidate_freeze_sha256': EXPECTED_FREEZE,
          'candidate_qa_sha256': EXPECTED_QA, 'counts': qa['counts'],
          'publication_receipt_sha256': sha(H / 'publication-receipt.json'),
          'register_sha256': pointer['register_sha256'], 'workbook_sha256': pointer['workbook_sha256'],
          'new_source_reviews_or_original_binary_reads': 0, 'live_calls': 0,
          'native_or_platform_or_shared_writes': 0}
(OUT / 'published-readback.json').write_text(json.dumps(result, indent=2) + '\n')
(OUT / 'sealed-published-handoff.json').write_text(json.dumps({'status': result['status'], 'recorded_utc': result['recorded_utc'],
    'files': {n: sha(OUT / n) for n in ['published_readback.py', 'published-readback.json', 'sealed-candidate-handoff.json']}}, indent=2) + '\n')
print(json.dumps({k: result[k] for k in ['status', 'checks_passed', 'checks_total', 'current_pointer_sha256', 'counts']}, indent=2))
print('Published QA receipt:', OUT / 'published-readback.json')
print('Published QA seal SHA256:', sha(OUT / 'sealed-published-handoff.json'))
for failed in [x for x in checks if not x['pass']]:
    print('FAIL', failed)
raise SystemExit(0 if result['status'] == 'PASS' else 1)
