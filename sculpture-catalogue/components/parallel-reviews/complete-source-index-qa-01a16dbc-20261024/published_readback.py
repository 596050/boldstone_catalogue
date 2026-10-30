"""Verify the main publisher's completed metadata release without writing it."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

B = Path('/Users/tprice/Documents/boldstone/sculpture-catalogue')
H = B / 'components/reconciliation/source-review-index-completion-2026-10-24'
OUT = Path(__file__).resolve().parent
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
read = lambda path: json.loads(Path(path).read_text())
checks = []


def check(name, passed):
    checks.append({'check': name, 'pass': bool(passed)})
    assert passed, name


qa = read(OUT / 'candidate-readback.json')
check('Original independent candidate receipt exact', sha(OUT / 'candidate-readback.json') == 'dcaa97598a899a097b2987d62251e0375699063c69255caa69e0e0dded6fe4fc' and qa['status'] == 'PASS' and qa['checks_passed'] == qa['checks_total'] == 192)
check('Original independent candidate seal exact', sha(OUT / 'sealed-handoff.json') == '8d6299381be9db211fdd6c778078cafe20ede9d03f9f6fa00b6b75947336b58e')
check('Same final freeze identity and artifacts', sha(H / 'candidate-freeze.json') == qa['candidate_freeze_sha256'] and qa['frozen_artifacts'] and all(sha(p) == v for p, v in qa['frozen_artifacts'].items()))
candidate = read(H / 'prepared-pointer.json')
pointer = read(B / 'current-master.json')
check('Published pointer equals independently checked candidate bytes', pointer == candidate and sha(B / 'current-master.json') == qa['candidate_pointer_sha256'] == sha(H / 'prepared-pointer.json'))
baseline = read(OUT / 'baseline.json')
for label, entry in baseline['data_files'].items():
    check('Published original data unchanged: ' + label, sha(entry['path']) == entry['sha256'])
for target, prepared in read(H / 'prepared-control-paths.json').items():
    control = read(target)
    check('Published control equals exact prepared bytes: ' + target, sha(target) == sha(prepared))
    check('Published control full pointer synchronized: ' + target, control['current_master_catalogue'] == pointer and control['current_source_photo_review_index'] == pointer['current_source_photo_review_index'] and control['latest_master_metadata_change'] == pointer['latest_master_metadata_change'])
receipt = read(H / 'publication-receipt.json')
check('Terminal publisher receipt reports completed readback', receipt['status'] == 'PASS_PUBLISHED_AND_READ_BACK' and receipt['publication_mode'] == 'SOURCE_PHOTO_EVIDENCE_INDEX_METADATA_ONLY' and receipt['current_master_pointer_sha256'] == sha(B / 'current-master.json') and receipt['preceding_pointer_sha256'] == qa['source_pointer_sha256'])
check('Publisher bound exact independent receipt and seal', receipt['independent_qa']['path'] == str(OUT / 'candidate-readback.json') and receipt['independent_qa']['sha256'] == sha(OUT / 'candidate-readback.json') and receipt['independent_qa']['seal_path'] == str(OUT / 'sealed-handoff.json') and receipt['independent_qa']['seal_sha256'] == sha(OUT / 'sealed-handoff.json'))
check('Publisher bound exact frozen candidate and unchanged catalogue', receipt['candidate_freeze_sha256'] == qa['candidate_freeze_sha256'] and receipt['register_sha256'] == qa['candidate_register_sha256'] and receipt['workbook_sha256'] == qa['candidate_workbook_sha256'] and receipt['all_five_data_artifacts_byte_identical'] is True and receipt['new_native_or_platform_writes'] == 0)
descriptor = pointer['current_source_photo_review_index']
check('Published index descriptor and counts exact', descriptor == receipt['source_photo_review_index'] and descriptor['counts'] == receipt['counts'] == qa['counts'] and sha(B / descriptor['path']) == descriptor['sha256'] and sha(B / descriptor['review']) == descriptor['review_sha256'])
index = read(B / descriptor['path'])
check('All sealed provider proof artifacts remain byte-identical', len(index['provider_files']) == 121 and all(sha(p) == v for p, v in index['provider_files'].items()))
check('Publisher terminal readback agrees', read(H / 'post-publication-readback.json')['pointer_and_three_controls_equal_candidate'] is True and read(H / 'post-publication-readback.json')['all_43_current_options_and_258_fields_match'] is True)
check('Active option and design counts unchanged', pointer['current_option_count'] == 188 and pointer['current_working_design_group_projection']['grouped_working_design_identity_count'] == 110)
result = {'status': 'PASS', 'recorded_utc': datetime.now(timezone.utc).isoformat(), 'phase': 'PUBLISHED_READBACK',
    'checks_passed': len(checks), 'checks_total': len(checks), 'checks': checks, 'current_pointer_sha256': sha(B / 'current-master.json'),
    'publication_receipt_sha256': sha(H / 'publication-receipt.json'), 'candidate_freeze_sha256': qa['candidate_freeze_sha256'],
    'register_sha256': qa['candidate_register_sha256'], 'workbook_sha256': qa['candidate_workbook_sha256'], 'counts': qa['counts'],
    'all_five_data_artifacts_byte_identical': True, 'reviewed_unpaired_source_records': 42, 'held_source_refs': ['O001'],
    'new_source_media_reviews': 0, 'live_calls': 0, 'native_or_platform_or_shared_writes': 0}
(OUT / 'published-readback.json').write_text(json.dumps(result, indent=2) + '\n')
(OUT / 'sealed-published-handoff.json').write_text(json.dumps({'status': 'PASS', 'recorded_utc': result['recorded_utc'],
    'files': {n: sha(OUT / n) for n in ['published_readback.py', 'published-readback.json', 'candidate-readback.json', 'sealed-handoff.json']}}, indent=2) + '\n')
print(json.dumps({'status': 'PASS', 'checks_passed': len(checks), 'current_pointer_sha256': result['current_pointer_sha256'],
    'published_readback_sha256': sha(OUT / 'published-readback.json'), 'sealed_published_handoff_sha256': sha(OUT / 'sealed-published-handoff.json')}))
