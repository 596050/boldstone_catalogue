"""Read-only validation of the owner-approved MSW2 water-build addition."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json

H = Path(__file__).resolve().parent
B = H.parents[2]
parser = argparse.ArgumentParser()
parser.add_argument('--register', type=Path)
args = parser.parse_args()
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
p = read(H / 'working-product-proposal.json')
pointer = read(B / 'current-master.json')
register_path = args.register or B / pointer['register']
g = read(register_path)
matches = [x for x in g['options'] if x.get('canonical_key') == p['proposed_canonical_key']]
if not matches:
    print(json.dumps({'status': 'PENDING_MAIN_WRITER_NEW_PRODUCT', 'register': str(register_path)}))
    raise SystemExit(3)
register_sha = sha(register_path)
coverage_path = register_path.parent / 'image-coverage-current.json'
coverage_sha = sha(coverage_path)
old = read(p['source_register']['path'])
baseline = {x['product_id']: x for x in old['options']}
options = {x['product_id']: x for x in g['options']}
checks = []

def check(name, condition):
    checks.append({'check': name, 'pass': bool(condition)})
    if not condition:
        raise AssertionError(name)

check('Owner decision receipt exact', sha(p['owner_decision']['path']) == p['owner_decision']['sha256'])
check('Source baseline exact', sha(p['source_register']['path']) == p['source_register']['sha256'])
check('Exactly one new water-build option', len(matches) == 1)
o = matches[0]
oid = o['product_id']
check('New ID distinct from existing options', oid not in baseline)
check('Exact owner product name', o['name'] == p['name'])
check('Existing design and component retained', o['canonical_design_id'] == o['canonical_component_id'] == 'BC-MSW-MOON')
for field, expected in p['working_fields'].items():
    check('Working display ' + field, o['master_fields'][field]['display'] == expected['display'])
check('No physical specifications certified', o.get('physical_specifications_verified') is False)
selling = o['selling_details']
check('GBP750 stays estimated', selling['currency'] == 'GBP' and selling['estimated_price'] == 750 and selling['price_status'] == 'estimate')
check('Made to order and1–2weeks policy', selling['availability'] == 'made_to_order' and selling['lead_time_min_weeks'] == 1 and selling['lead_time_max_weeks'] == 2)
check('No physical stock claimed', selling.get('physical_stock_quantity') is None)
protected = ['name', 'canonical_key', 'canonical_component_id', 'canonical_design_id', 'file_id', 'folder_id', 'image_url', 'folder_url', 'context_file_id', 'context_folder_id', 'context_image_url', 'context_folder_url', 'specifications', 'master_fields', 'selling_details', 'photo_coverage']
for prior_id in ['BSI-6FE9343F889E', 'BSI-6E9202BEAD51', 'BSI-B9E2B67965E2', 'BSI-D886F539DD3E']:
    check(prior_id + ' identity/photo/specification/commerce fields unchanged', all(options[prior_id].get(k) == baseline[prior_id].get(k) for k in protected))
c = next(x for x in read(coverage_path)['coverage'] if x['option_id'] == oid)
for role, expected in p['role_recommendations'].items():
    check(role + ' qualified coverage status', c[role]['status'] == expected['status'])
    ref = c[role]['reference']
    check(role + ' exact same source and actual parent', ref['file_id'] == 'id:cnqzTNngPVsAAAAAAAubvA' and ref['folder_id'] == 'id:cnqzTNngPVsAAAAAAAyinQ')
check('One active option added only', set(g['active_option_ids']) == set(old['active_option_ids']) | {oid} and len(g['active_option_ids']) == 188)
check('One retained option added only', set(options) == set(baseline) | {oid} and len(options) == 189)
check('112 component records retained', len(g['components']) == len(old['components']) == 112)
check('Original review specification assertions unchanged', g['original_review_specification_assertions'] == old['original_review_specification_assertions'])
if not args.register:
    check('Published register checksum matches pointer', register_sha == pointer['register_sha256'])
    check('Published workbook checksum matches pointer', sha(B / pointer['workbook']) == pointer['workbook_sha256'])
    check('Publication verified by main writer', read(B / pointer['publication_receipt'])['status'] == 'PASS_PUBLISHED_AND_READ_BACK')
    check('Current pointer stable', read(B / 'current-master.json') == pointer)
check('Register and coverage bytes stable during readback', sha(register_path) == register_sha and sha(coverage_path) == coverage_sha)
published = not bool(args.register)
r = {'recorded_utc': datetime.now(timezone.utc).isoformat(), 'status': 'PASS_PUBLISHED_MSW2_WATER_PRODUCT' if published else 'PASS_CANDIDATE_MSW2_WATER_PRODUCT', 'checks_passed': len(checks), 'checks': checks, 'product_id': oid, 'name': o['name'], 'register': str(register_path), 'register_sha256': register_sha, 'coverage_sha256': coverage_sha, 'workbook_sha256': pointer['workbook_sha256'] if published else None, 'publication_verified': published, 'workbook_cell_level_checks_owned_by_main_writer': True, 'canonical_writes': 0, 'native_calls': 0}
receipt = H / (('published' if published else 'candidate') + '-readback-' + register_sha[:8] + '.json')
with receipt.open('x') as f:
    f.write(json.dumps(r, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'status': r['status'], 'checks_passed': len(checks), 'product_id': oid, 'receipt': str(receipt), 'receipt_sha256': sha(receipt)}))
