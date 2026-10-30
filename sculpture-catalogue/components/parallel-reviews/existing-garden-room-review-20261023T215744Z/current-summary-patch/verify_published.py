"""Check B's five corrections after the main writer publishes its combined release."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

H = Path(__file__).resolve().parent
B = H.parents[3]
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
plan = read(H / 'patch-plan.json')
pointer_path = B / 'current-master.json'
pointer = read(pointer_path)
if pointer['register_sha256'] == plan['source_register']['sha256']:
    print(json.dumps({'status': 'PENDING_MAIN_WRITER_PUBLICATION', 'register': pointer['register']}))
    raise SystemExit(3)

register_path = B / pointer['register']
register = read(register_path)
old = read(plan['source_register']['path'])
coverage_path = register_path.parent / 'image-coverage-current.json'
coverage = {x['option_id']: x for x in read(coverage_path)['coverage']}
baseline = {x['product_id']: x for x in old['options']}
options = {x['product_id']: x for x in register['options']}
checks = []

def check(name, condition):
    checks.append({'check': name, 'pass': bool(condition)})
    if not condition:
        raise AssertionError(name)

check('Published register matches pointer checksum', sha(register_path) == pointer['register_sha256'])
check('Published workbook matches pointer checksum', sha(B / pointer['workbook']) == pointer['workbook_sha256'])
publication = read(B / pointer['publication_receipt'])
check('Publication readback reports success', publication['status'] == 'PASS_PUBLISHED_AND_READ_BACK')
for item in plan['items']:
    oid = item['option_id']
    before, after = baseline[oid], options[oid]
    changed = item['replace_current_fields']
    history = item['append_history']
    check(oid + ' exact current corrections', all(after[k] == v for k, v in changed.items()))
    check(oid + ' original fields retained in dated history', history['entry'] in after.get(history['field'], []))
    check(oid + ' all other option fields unchanged', {k: v for k, v in before.items() if k not in changed} == {k: v for k, v in after.items() if k not in changed and k != history['field']})
    check(oid + ' existing Available role and exact reference unchanged', coverage[oid]['in_situ'] == item['guards']['coverage_in_situ'])
    check(oid + ' complete photo-role coverage unchanged', after['photo_coverage'] == before['photo_coverage'])
check('All retained identities preserved', [x['product_id'] for x in register['options']] == [x['product_id'] for x in old['options']])
check('All 187 active options preserved', register['active_option_ids'] == old['active_option_ids'] and len(register['active_option_ids']) == 187)
check('Pointer unchanged during readback', read(pointer_path) == pointer)
receipt = {'recorded_utc': datetime.now(timezone.utc).isoformat(), 'status': 'PASS_PUBLISHED_B_CURRENT_SUMMARY_CORRECTIONS', 'checks_passed': len(checks), 'checks': checks, 'register': str(register_path), 'register_sha256': pointer['register_sha256'], 'workbook': str(B / pointer['workbook']), 'workbook_sha256': pointer['workbook_sha256'], 'publication_receipt': pointer['publication_receipt'], 'plan_sha256': sha(H / 'patch-plan.json'), 'scope': 'Exact five B descriptions, four current summary statuses, dated history, unchanged B option fields and coverage. Published workbook bytes checked against its release checksum; workbook cell-level verification belongs to the main writer saved-file receipt.', 'canonical_writes': 0, 'native_writes': 0}
(H / 'published-readback.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'status': receipt['status'], 'checks_passed': len(checks), 'register': str(register_path), 'receipt_sha256': sha(H / 'published-readback.json')}))
