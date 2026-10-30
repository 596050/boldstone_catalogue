"""Read-only B5 validation of the combined candidate against the sealed plan."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

H = Path(__file__).resolve().parent
B = H.parents[3]
C = B / 'components/reconciliation/catalogue-current-note-finalization-2026-10-23'
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
plan_path = H / 'patch-plan.json'
plan = read(plan_path)
register_path = C / 'canonical-master-register.json'
coverage_path = C / 'image-coverage-current.json'
register_sha, coverage_sha = sha(register_path), sha(coverage_path)
checks = []

def check(name, condition):
    checks.append({'check': name, 'pass': bool(condition)})
    if not condition:
        raise AssertionError(name)

check('Exact sealed B plan', sha(plan_path) == '6b2311764716872cf3d0d2dce4be888cc781e18603a229db0baf13822dd5b0e8')
check('Exact navigation baseline register', sha(plan['source_register']['path']) == plan['source_register']['sha256'])
check('Exact navigation baseline coverage', sha(plan['source_coverage']['path']) == plan['source_coverage']['sha256'])
old, current = read(plan['source_register']['path']), read(register_path)
old_coverage = {x['option_id']: x for x in read(plan['source_coverage']['path'])['coverage']}
coverage = {x['option_id']: x for x in read(coverage_path)['coverage']}
baseline = {x['product_id']: x for x in old['options']}
options = {x['product_id']: x for x in current['options']}
check('Exactly five assigned B targets', len(plan['items']) == 5 and len({x['option_id'] for x in plan['items']}) == 5)
for item in plan['items']:
    oid = item['option_id']
    before, after = baseline[oid], options[oid]
    changed, history = item['replace_current_fields'], item['append_history']
    check(oid + ' exact current corrections', all(after[k] == v for k, v in changed.items()))
    check(oid + ' exact dated history including all six prior fields', history['entry'] in after.get(history['field'], []))
    check(oid + ' all other option fields unchanged', {k: v for k, v in before.items() if k not in changed} == {k: v for k, v in after.items() if k not in changed and k != history['field']})
    check(oid + ' complete coverage record unchanged', coverage[oid] == old_coverage[oid])
    check(oid + ' Available in-situ reference unchanged', coverage[oid]['in_situ'] == item['guards']['coverage_in_situ'] and coverage[oid]['in_situ']['status'] == 'Available')
    check(oid + ' complete option photo roles unchanged', after['photo_coverage'] == before['photo_coverage'])
check('Azure qualified status unchanged', options['BSI-3C849B547D50']['context_status'] == baseline['BSI-3C849B547D50']['context_status'])
check('Exactly four pending current summaries become Available', sum(baseline[x['option_id']]['context_status'] == 'Review pending' and options[x['option_id']]['context_status'] == 'Available' for x in plan['items']) == 4)
check('188 retained identities and order preserved', len(current['options']) == 188 and [x['product_id'] for x in current['options']] == [x['product_id'] for x in old['options']])
check('187 active identities preserved', current['active_option_ids'] == old['active_option_ids'] and len(current['active_option_ids']) == 187)
check('Candidate register unchanged during reader check', sha(register_path) == register_sha)
check('Candidate coverage unchanged during reader check', sha(coverage_path) == coverage_sha)
receipt = {'recorded_utc': datetime.now(timezone.utc).isoformat(), 'status': 'PASS_CANDIDATE_B5_ONLY_NOT_PUBLICATION', 'checks_passed': len(checks), 'checks': checks, 'register': str(register_path), 'register_sha256': register_sha, 'coverage': str(coverage_path), 'coverage_sha256': coverage_sha, 'plan_sha256': sha(plan_path), 'five_current_descriptions_match': True, 'four_current_status_corrections_match': True, 'azure_status_retained': True, 'full_prior_six_fields_retained_in_dated_history': True, 'all_other_B_option_fields_exact': True, 'all_five_full_B_coverage_records_exact': True, 'shared_candidate_writes': 0, 'native_calls': 0, 'new_photo_reviews': 0, 'publication_verified': False, 'workbook_checked': False, 'scope': 'B five-option current-description/status patch only. A two-note additions and disjoint Dune Partial Series policy are outside this reader scope. Final pointer/workbook hash readback follows main publication.'}
receipt_path = H / ('candidate-readback-' + register_sha[:8] + '.json')
with receipt_path.open('x') as f:
    f.write(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'status': receipt['status'], 'checks_passed': len(checks), 'receipt': str(receipt_path), 'receipt_sha256': sha(receipt_path), 'register_sha256': register_sha, 'coverage_sha256': coverage_sha}))
