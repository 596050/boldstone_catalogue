"""Read-only B-scope review of four owner-approved photograph policies."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json

parser = argparse.ArgumentParser()
parser.add_argument('--published', action='store_true')
args = parser.parse_args()
lane = Path(__file__).resolve().parent
base = lane.parents[2]
frozen = base / 'components/reconciliation/eight-series-photo-policies-master-2026-10-24'
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
pointer_file = base / 'current-master.json'
pointer = read(pointer_file)
release = (base / pointer['register']).parent if args.published else frozen
register_file = release / 'canonical-master-register.json'
coverage_file = release / 'image-coverage-current.json'
state_file = release / 'guided-owner-review-state.json'
source_hashes = {str(p): sha(p) for p in [register_file, coverage_file, state_file]}
register = read(register_file)
baseline_file = frozen / 'inputs/master_register.before'
baseline = read(baseline_file)
before = {o['product_id']: o for o in baseline['options']}
after = {o['product_id']: o for o in register['options']}
baseline_coverage = read(base / 'components/reconciliation/riyadh-and-four-series-policies-master-2026-10-24/image-coverage-current.json')
old_coverage = {r['option_id']: r for r in baseline_coverage['coverage']}
new_coverage = {r['option_id']: r for r in read(coverage_file)['coverage']}
state = read(state_file)
checks = []


def check(label, condition):
    checks.append({'check': label, 'pass': bool(condition)})
    if not condition:
        raise AssertionError(label)


check('Frozen source is05b5 baseline', sha(baseline_file) == '05b5c2dc85d9952cbccfa6bd86dddbc7e404f822e948635936ef96e571239b0e')
manifest_file = lane / 'sealed-b-next-series-policy-batch04.json'
manifest = read(manifest_file)
check('Sealed four-owner manifest exact', sha(manifest_file) == '083525299d2715b1311c5762a1922910f79b1079b6d7e65f13ef086e597ad1ce')
receipts = {row['option_id']: Path(row['path']) for row in manifest['decisions']}
expected_hashes = {row['option_id']: row['sha256'] for row in manifest['decisions']}
check('Exactly four approved B options', set(receipts) == {'BSI-EBD43DF0704F', 'BSI-BFEE06AB14A0', 'BSI-1AF0A83FAA37', 'BSI-3635E3DC3434'})
for oid, receipt_path in receipts.items():
    old = before[oid]
    new = after[oid]
    owner = read(receipt_path)
    policy = new['current_series_optionality_policy']
    prefix = oid + ' '
    check(prefix + 'owner receipt hash exact', sha(receipt_path) == expected_hashes[oid])
    allowed = {'current_photo_task_review', 'current_series_optionality_policy', 'photo_coverage'}
    changed = {k for k in set(old) | set(new) if old.get(k) != new.get(k)}
    check(prefix + 'only photo policy and review fields changed', changed == allowed)
    check(prefix + 'identity sale physical source and family fields unchanged',
          {k: v for k, v in old.items() if k not in allowed} ==
          {k: v for k, v in new.items() if k not in allowed})
    check(prefix + 'all owner receipt meaning and wording retained',
          all(policy.get(k) == v for k, v in owner.items() if k != 'canonical_applied'))
    check(prefix + 'import applied flag and source identity exact',
          policy['canonical_applied'] is True and
          policy['source_receipt'] == str(receipt_path) and
          policy['source_sha256'] == expected_hashes[oid] and bool(policy['applied_utc']))
    check(prefix + 'companion-set absence not inferred',
          policy['fixed_companion_set_existence_confirmed'] is False and
          policy['status_label_qualification'] == owner['status_label_qualification'])
    check(prefix + 'Series category optional', new['photo_coverage']['series'] == 'Optional / no fixed set')
    check(prefix + 'other option coverage fields unchanged',
          {k: v for k, v in old['photo_coverage'].items() if k != 'series'} ==
          {k: v for k, v in new['photo_coverage'].items() if k != 'series'})
    check(prefix + 'individual and in-situ role records unchanged',
          all(old_coverage[oid][r] == new_coverage[oid][r] for r in ['individual', 'in_situ']))
    series = new_coverage[oid]['series']
    check(prefix + 'Series source remains unverified and exactly retained',
          series['status'] == 'Optional / no fixed set' and
          series['reference'] == old_coverage[oid]['series']['reference'] and
          series['physical_cast_or_size_certified'] is False)
    check(prefix + 'prior Series references exclusions and identity metadata retained',
          all(series.get(k) == v for k, v in old_coverage[oid]['series'].items()
              if k not in {'status', 'basis', 'terminal_review_state', 'owner_policy'}))
    check(prefix + 'basis preserves companion possibilities',
          'does not confirm that no companion set exists' in series['basis'])
    old_review = old['current_photo_task_review']
    new_review = new['current_photo_task_review']
    check(prefix + 'prior Series review retained in dated history',
          any(x.get('role') == 'series' and x.get('before') == old_review['roles']['series']
              for x in new_review['historical_policy_superseded_roles']))
    check(prefix + 'other current review roles unchanged',
          all(new_review['roles'].get(k) == v for k, v in old_review['roles'].items() if k != 'series'))
    check(prefix + 'absent from active Series question queue', oid not in state['queues']['series'])
    component_id = new['canonical_component_id']
    check(prefix + 'component and companion membership unchanged',
          next(x for x in register['components'] if x['component_id'] == component_id) ==
          next(x for x in baseline['components'] if x['component_id'] == component_id))

check('Active retained and component counts188189112',
      (len(register['active_option_ids']), len(register['options']), len(register['components'])) == (188, 189, 112))
check('Count definition remains correct', register['count_definition'] == baseline['count_definition'] and
      'All189' in register['count_definition'] and '188 remain current' in register['count_definition'])
check('Active option IDs unchanged', register['active_option_ids'] == baseline['active_option_ids'])
baseline_state = read(base / 'components/reconciliation/riyadh-and-four-series-policies-master-2026-10-24/guided-owner-review-state.json')
for field in ['held_in_situ_ids', 'held_series_ids', 'deferred_individual_ids']:
    check(field + 'unchanged', state[field] == baseline_state[field])
for oid in ['BSI-096BA2E00517', 'BSI-6E9202BEAD51', 'BSI-C3AA3700F7DA']:
    check(oid + 'earlier completed product and policy unchanged', after[oid] == before[oid])

if not args.published:
    check('No active Series prompt after eight decisions', state['queues']['series'] == [])
    check('One separate active individual-image request retained', len(state['queues']['individual']) == 1)
else:
    check('Published register hash matches pointer', sha(register_file) == pointer['register_sha256'])
    check('Published workbook hash matches pointer', sha(base / pointer['workbook']) == pointer['workbook_sha256'])
    check('Published numeric pointer counts correct',
          (pointer['current_option_count'], pointer['retained_option_count'], pointer['retired_option_count']) == (188, 189, 1))
    check('Main publication readback passed', read(base / pointer['publication_receipt'])['status'] == 'PASS_PUBLISHED_AND_READ_BACK')
    check('Current pointer stable', read(pointer_file) == pointer)
check('Readback source bytes stable', all(sha(Path(p)) == value for p, value in source_hashes.items()))
mode = 'published' if args.published else 'candidate'
receipt = {
    'recorded_utc': datetime.now(timezone.utc).isoformat(),
    'status': 'PASS_' + mode.upper() + '_B_FOUR_SERIES_POLICIES',
    'checks_passed': len(checks), 'checks': checks,
    'register': str(register_file), 'register_sha256': sha(register_file),
    'coverage_sha256': sha(coverage_file), 'baseline_sha256': sha(baseline_file),
    'workbook_sha256': pointer['workbook_sha256'] if args.published else None,
    'publication_verified': args.published,
    'workbook_cell_verification_owned_by_main_writer': True,
    'shared_canonical_writes': 0, 'native_or_platform_writes': 0,
}
output = lane / ('eight-policy-' + mode + '-readback-' + sha(register_file)[:8] + '.json')
with output.open('x') as stream:
    json.dump(receipt, stream, indent=2, ensure_ascii=False)
    stream.write('\n')
print(json.dumps({'status': receipt['status'], 'checks_passed': len(checks),
                  'receipt': str(output), 'sha256': sha(output),
                  'register_sha256': sha(register_file)}))
