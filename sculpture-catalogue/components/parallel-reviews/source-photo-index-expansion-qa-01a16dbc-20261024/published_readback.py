"""Read the committed index release and verify its exact frozen metadata bytes."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

B = Path('/Users/tprice/Documents/boldstone/sculpture-catalogue')
H = B / 'components/reconciliation/source-component-review-and-flower-links-2026-10-24'
OUT = Path(__file__).resolve().parent
F = '2a53952e0065430e57fd0e9854eac9211a784822774ae8588b7e99d2929c8ef5'
Q = '33aed3fb056ccaddffb8ad7986ac70aba02ae5d6e00cdb019f04360ba81d17e4'
S = 'e3476517c2fc930e391019b69c7fb5e1dea9be9f4b2d65af3989d5f427debd32'
FID = 'id:cnqzTNngPVsAAAAAAAyh5Q'
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
read = lambda p: json.loads(Path(p).read_text())
checks = []


def check(name, passed):
    checks.append({'check': name, 'pass': bool(passed)})


receipt = read(H / 'publication-receipt.json')
baseline = read(OUT / 'pre-expansion-baseline.json')
before = read(OUT / 'pointer.before.json')
freeze = read(H / 'candidate-freeze.json')
qa = read(OUT / 'candidate-readback.json')
seal = read(OUT / 'sealed-candidate-handoff.json')
pointer = read(B / 'current-master.json')
check('Final frozen candidate unchanged', sha(H / 'candidate-freeze.json') == F and len(freeze['frozen_artifacts']) == 14
      and all(sha(path) == expected for path, expected in freeze['frozen_artifacts'].items()))
check('Independent113-check QA and seal unchanged', sha(OUT / 'candidate-readback.json') == Q and sha(OUT / 'sealed-candidate-handoff.json') == S
      and qa['status'] == 'PASS' and qa['checks_passed'] == qa['checks_total'] == 113)
check('Independent QA files seal exact', all(sha(OUT / path) == expected for path, expected in seal['files'].items()))
check('Published pointer exactly equals reviewed candidate bytes', sha(B / 'current-master.json') == sha(H / 'prepared-pointer.json') == qa['candidate_pointer_sha256'])
allowed = {'recorded_utc', 'publication_receipt', 'current_source_photo_review_index', 'latest_master_metadata_change',
           'current_asset_reference_map', 'current_native_reference_map', 'latest_acanthus_flower_case_navigation'}
check('Only seven pointer metadata fields changed', {k for k in set(before) | set(pointer) if before.get(k) != pointer.get(k)} == allowed)
for name, item in baseline['data_files'].items():
    check('Original published data file retained: ' + name, sha(item['path']) == item['sha256'])
for key, expected in [('current_asset_reference_map', qa['candidate_asset_map_sha256']), ('current_native_reference_map', qa['candidate_native_map_sha256'])]:
    check('Published navigation descriptor and map exact: ' + key, sha(B / pointer[key]['path']) == pointer[key]['sha256'] == expected and receipt[key] == pointer[key])
controls = read(H / 'prepared-control-paths.json')
check('Exactly three existing controls committed', set(controls) == set(baseline['controls']) == set(receipt['controls_sha256']))
for destination, prepared in controls.items():
    value = read(destination)
    check('Published control equals candidate and complete pointer: ' + destination,
          sha(destination) == sha(prepared) == receipt['controls_sha256'][destination]
          and value['current_master_catalogue'] == pointer
          and all(value[k] == pointer[k] for k in allowed - {'recorded_utc', 'publication_receipt'}))
check('Receipt confirms exact pointer and predecessor', receipt['status'] == 'PASS_PUBLISHED_AND_READ_BACK'
      and receipt['publication_mode'] == 'SOURCE_COMPONENT_INDEX_AND_ONE_CASE_NAVIGATION_METADATA_ONLY'
      and receipt['current_master_pointer_sha256'] == sha(B / 'current-master.json')
      and receipt['preceding_pointer_sha256'] == baseline['pointer_sha256']
      and receipt['preceding_publication_receipt'] == before['publication_receipt'])
check('Receipt confirms exact register/workbook/counts', receipt['register_sha256'] == pointer['register_sha256'] == qa['candidate_register_sha256']
      and receipt['workbook_sha256'] == pointer['workbook_sha256'] == qa['candidate_workbook_sha256']
      and receipt['counts'] == qa['counts'] == pointer['current_source_photo_review_index']['counts'])
check('One-ID case refresh retained without physical move or native write', receipt['changed_asset_records'] == receipt['changed_native_objects'] == [FID]
      and receipt['actual_parent_changes'] == receipt['new_native_or_platform_writes'] == 0
      and receipt['old_published_data_artifacts_byte_identical'] is True
      and receipt['register_workbook_and_audit_byte_identical'] is True)
check('Receipt binds exact independent QA, seal and freeze', Path(receipt['independent_qa']['path']) == OUT / 'candidate-readback.json'
      and receipt['independent_qa']['sha256'] == Q and Path(receipt['independent_qa']['seal_path']) == OUT / 'sealed-candidate-handoff.json'
      and receipt['independent_qa']['seal_sha256'] == S and receipt['candidate_freeze_sha256'] == F)
descriptor = pointer['current_source_photo_review_index']
check('Published index and HTML checksum links exact', sha(B / descriptor['path']) == descriptor['sha256']
      and sha(B / descriptor['review']) == descriptor['review_sha256'] and receipt['source_photo_review_index'] == descriptor)
result = {'status': 'PASS' if all(x['pass'] for x in checks) else 'FAIL', 'recorded_utc': datetime.now(timezone.utc).isoformat(),
          'checks_passed': sum(x['pass'] for x in checks), 'checks_total': len(checks), 'checks': checks,
          'current_pointer_sha256': sha(B / 'current-master.json'), 'candidate_freeze_sha256': F,
          'candidate_qa_sha256': Q, 'counts': qa['counts'], 'current_asset_map_sha256': pointer['current_asset_reference_map']['sha256'],
          'current_native_map_sha256': pointer['current_native_reference_map']['sha256'],
          'publication_receipt_sha256': sha(H / 'publication-receipt.json'),
          'register_sha256': pointer['register_sha256'], 'workbook_sha256': pointer['workbook_sha256'],
          'new_source_media_reviews': 0, 'live_calls': 0, 'native_or_platform_or_shared_writes': 0}
(OUT / 'published-readback.json').write_text(json.dumps(result, indent=2) + '\n')
(OUT / 'sealed-published-handoff.json').write_text(json.dumps({'status': result['status'], 'recorded_utc': result['recorded_utc'],
    'files': {n: sha(OUT / n) for n in ['published_readback.py', 'published-readback.json', 'sealed-candidate-handoff.json']}}, indent=2) + '\n')
print(json.dumps({k: result[k] for k in ['status', 'checks_passed', 'checks_total', 'current_pointer_sha256', 'counts']}, indent=2))
print('Published readback seal SHA256:', sha(OUT / 'sealed-published-handoff.json'))
for failed in [x for x in checks if not x['pass']]:
    print('FAIL', failed)
raise SystemExit(0 if result['status'] == 'PASS' else 1)
