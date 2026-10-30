"""Read back the committed metadata and every Echo file/containing-folder binding."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

H = Path(__file__).resolve().parent
B = H.parents[2]
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
m = read(H / 'input-manifest.json')
pub = read(H / 'publication-receipt.json')
p = read(B / 'current-master.json')
old = read(m['pointer']['snapshot'])
issues = []
checks = 0
def check(ok, message):
    global checks
    checks += 1
    if not ok:
        issues.append(message)

check(p == read(H / 'prepared-pointer.json'), 'Committed pointer equals reviewed candidate')
check(sha(B / 'current-master.json') == pub['current_master_pointer_sha256'], 'Exact pointer bytes')
for key in ['register', 'workbook']:
    check(sha(B / p[key]) == p[key + '_sha256'] == old[key + '_sha256'], 'Unchanged entire ' + key)
check(sha(m['audit']['path']) == m['audit']['sha256'] == pub['audit_sha256'], 'Unchanged entire photo audit')
for key in ['review_progress', 'component_checkpoint', 'root_checkpoint']:
    dest = m[key]['path']
    check(sha(dest) == pub['controls_sha256'][dest], 'Exact control bytes ' + key)
    check(read(dest)['current_master_catalogue'] == p, 'Control pointer synchronized ' + key)
check(p['summary'] == old['summary'] and p['current_option_count'] == 188 and p['retained_option_count'] == 189, 'Catalogue counts retained')
for key in ['platform_write_holds', 'current_frozen_fish_size_policy', 'wall_sculpture_customisation_policy',
            'current_global_context_owner_hold', 'current_individual_photo_capture_policy', 'latest_workbook_validation']:
    check(p[key] == old[key], 'Standing scope retained ' + key)
assets = read(B / p['current_asset_reference_map']['path'])
native = read(B / p['current_native_reference_map']['path'])
before_assets = read(m['assets']['snapshot'])
before_native = read(m['native_map']['snapshot'])
packet = p['latest_echo_sound_approved_native_navigation']
overlay = read(packet['overlay'])
check(sha(packet['overlay']) == packet['overlay_sha256'], 'Exact approved native overlay')
check(sha(packet['execution_seal']) == packet['execution_seal_sha256'], 'Exact native execution seal')
links = read(Path(packet['overlay']).with_name('all-current-echo-sound-image-folder-links.json'))
moved = {x['file_id'] for x in overlay['objects'] if x['old_path'] != x['current_path']}
check(len(moved) == 23 and len(links) == 180 and sum(x['size'] for x in links) == 1092139502, '23 moves and180 original file accounting')
check(set(assets) == set(before_assets), 'Asset ID population unchanged')
check(all(assets[i] == x for i, x in before_assets.items() if i not in moved), 'All unmoved asset objects unchanged')
check(all(native['current_objects'][i] == x for i, x in before_native['current_objects'].items()), 'All prior native objects unchanged')
for x in overlay['objects']:
    n = native['current_objects'][x['file_id']]
    check(n['parent_id'] == x['current_parent_id'] and n['display_path'] == x['current_path'] and n['name'] == x['current_name'], 'Current native object ' + x['file_id'])
for x in links:
    a = assets[x['file_id']]
    check(all(a[k] == x[k] for k in ['folder_id', 'image_url', 'folder_url']), 'Current image/folder link ' + x['file_id'])
for key in ['current_asset_reference_map', 'current_native_reference_map']:
    check(sha(B / p[key]['path']) == p[key]['sha256'], 'Published map hash ' + key)
q = pub['independent_qa']
check(sha(q['path']) == q['sha256'] and sha(q['seal_path']) == q['seal_sha256'], 'Exact independent QA receipt and seal')
check(read(q['path'])['status'] == 'PASS', 'Independent QA passed')
result = {'status': 'FAIL' if issues else 'PASS', 'recorded_utc': datetime.now(timezone.utc).isoformat(),
    'checks': checks, 'issues': issues, 'pointer_sha256': sha(B / 'current-master.json'),
    'register_sha256': p['register_sha256'], 'workbook_sha256': p['workbook_sha256'],
    'approved_Echo_moves_imported': 23, 'Echo_originals': 180, 'White': 93, 'InSitu': 25,
    'workbook_register_audit_byte_identical': True, 'new_physical_verifications_or_platform_pairs': 0}
(H / 'post-publication-readback.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result))
if issues:
    raise SystemExit(1)
