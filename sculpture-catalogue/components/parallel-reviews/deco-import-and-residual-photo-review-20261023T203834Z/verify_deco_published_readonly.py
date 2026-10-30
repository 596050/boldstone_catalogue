from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
from urllib.parse import quote, urlparse, unquote, parse_qs
import json, hashlib

b = Path('/Users/tprice/Documents/boldstone/sculpture-catalogue')
j = b / 'components/parallel-reviews/deco-import-and-residual-photo-review-20261023T203834Z'
ws = json.loads((j / 'verification-workspace.json').read_text())
v = Path(ws['private_verification_workspace'])
# Reuse the previously independently checked standard-library XLSX reader only.
reader = b / 'components/parallel-reviews/remaining-photo-sources-and-bordered-import-20261023T200049Z/verify_final_workbook_readonly.py'
prefix = reader.read_text().split('ptrbytes=')[0]
helper = {}
exec(prefix, helper)
loadbook = helper['loadbook']
sha = lambda data: hashlib.sha256(data).hexdigest()
before_pointer = json.loads((j / 'baseline-pointer.json').read_text())
ptr_bytes = (b / 'current-master.json').read_bytes()
ptr = json.loads(ptr_bytes)
assert ptr['workbook_sha256'] != before_pointer['workbook_sha256'], 'Deco update is not published yet'
assert ptr['register'] == 'components/reconciliation/deco004-photo-and-physical-review-2026-10-23/canonical-master-register.json'
data = (b / ptr['workbook']).read_bytes()
assert sha(data) == ptr['workbook_sha256']
snapshot = v / 'published-deco004-catalogue.xlsx'
if snapshot.exists():
    assert snapshot.read_bytes() == data, 'Existing immutable verification snapshot belongs to different bytes'
else:
    snapshot.write_bytes(data)
before = loadbook(Path(ws['baseline_workbook']).read_bytes())
after = loadbook(data)
checks = []

def ck(label, passed, **details):
    checks.append({'label': label, 'pass': bool(passed), **details})
    assert passed, (label, details)

ck('Published workbook hash bound to immutable snapshot', sha(snapshot.read_bytes()) == ptr['workbook_sha256'])
ck('All28 established sheets and order preserved', list(before['sheets']) == list(after['sheets']) and len(after['sheets']) == 28)
ck('All3390 established formula texts and cell locations preserved', before['formulas'] == after['formulas'] and len(after['formulas']) == 3390)
for name in ['Specifications', 'Selling Details']:
    old = before['sheets'][name]
    new = after['sheets'][name]
    old_data = {k: x for k, x in old['cells'].items() if int(''.join(c for c in k if c.isdigit())) >= 10}
    new_data = {k: x for k, x in new['cells'].items() if int(''.join(c for c in k if c.isdigit())) >= 10}
    ck(name + ' all data values/styles/formulas preserved', old_data == new_data, checked_data_cells=len(old_data))
    if name == 'Specifications':
        review_link = b / 'outputs/deco004-photo-and-physical-review-2026-10-23/physical-evidence-review.html'
        ck(name + ' all original hyperlinks preserved with one source-review navigation addition', all(new['links'].get(k) == value for k, value in old['links'].items()) and set(new['links']) == set(old['links']) | {'A3'}, checked_links=len(old['links']))
        ck('Specifications A3 adds only the existing local physical-evidence review page', new['links']['A3'] == str(review_link) and review_link.is_file())
    else:
        ck(name + ' all original hyperlinks preserved', old['links'] == new['links'], checked_links=len(old['links']))

old_reg = json.loads((b / before_pointer['register']).read_text())
reg_bytes = (b / ptr['register']).read_bytes()
ck('Published register hash matches pointer', sha(reg_bytes) == ptr['register_sha256'])
reg = json.loads(reg_bytes)
old_opts = {x['product_id']: x for x in old_reg['options']}
opts = {x['product_id']: x for x in reg['options']}
ck('188 retained options and187 active IDs preserved', old_opts.keys() == opts.keys() and len(opts) == 188 and old_reg['active_option_ids'] == reg['active_option_ids'])
for field in ['name', 'specifications', 'master_fields', 'selling_details', 'file_id', 'folder_id', 'physical_specifications_verified', 'platform_publication_performed']:
    ck('All188 option ' + field + ' preserved', all(x.get(field) == opts[k].get(field) for k, x in old_opts.items()))

old_audit = json.loads(Path(old_reg['latest_image_coverage_audit']['path']).read_text())
audit = json.loads(Path(reg['latest_image_coverage_audit']['path']).read_text())
c1 = {x['option_id']: x for x in old_audit['coverage']}
c2 = {x['option_id']: x for x in audit['coverage']}
fid = 'id:cnqzTNngPVsAAAAAAAyluQ'
old_parent = 'id:cnqzTNngPVsAAAAAAAyh5w'
new_parent = 'id:cnqzTNngPVsAAAAAAA6VrQ'
targets = {'BSI-E7CDC2CFAC9D', 'BSI-CAB0D722062D', 'BSI-EC5966EA0C7A'}
def role_binding(role):
    source = role.get('reference') or {}
    return {'status': role['status'], 'source': {key: source.get(key) for key in ['file_id', 'folder_id', 'path', 'image_url', 'folder_url', 'name']}}

for role in ['individual', 'series']:
    ck('All188 ' + role + ' status and exact source bindings unchanged', all(role_binding(c1[k][role]) == role_binding(c2[k][role]) for k in c1))
ck('All188 context role statuses unchanged', all(c1[k]['in_situ']['status'] == c2[k]['in_situ']['status'] for k in c1))
changed = {k for k in c1 if role_binding(c1[k]['in_situ']) != role_binding(c2[k]['in_situ'])}
scene_option = 'BSI-F61AE4921B6B'
ck('Exactly three004 references plus one held003 scene-path reference refreshed', changed == targets | {scene_option}, changed_option_ids=sorted(changed))
for oid in targets:
    old_ref = c1[oid]['in_situ']['reference']
    new_ref = c2[oid]['in_situ']['reference']
    ck(oid + ' same004 source in verified new actual parent', old_ref['file_id'] == new_ref['file_id'] == fid and old_ref['folder_id'] == old_parent and new_ref['folder_id'] == new_parent)
    ck(oid + ' current path and folder link show four-component In Situ parent', '/Two Leaves 1 and Spiral 1 and Palm 1 and Palm 2 White In Situ/' in new_ref['path'] and 'Two%20Leaves%201%20and%20Spiral%201%20and%20Palm%201%20and%20Palm%202%20White%20In%20Situ' in new_ref['folder_url'])
scene_metadata_path = b / 'components/reconciliation/deco004-photo-and-physical-review-2026-10-23/fresh-scene-followup-metadata.json'
scene_metadata = json.loads(scene_metadata_path.read_text())
scene_folder = next(x['result']['structuredContent']['folder'] for x in scene_metadata['records'] if x['id'] == old_parent)
old_scene = c1[scene_option]['in_situ']['reference']
new_scene = c2[scene_option]['in_situ']['reference']
ck('Existing Timeless Spiral003 context identity and actual parent preserved', old_scene['file_id'] == new_scene['file_id'] == 'id:cnqzTNngPVsAAAAAAAyh6g' and old_scene['folder_id'] == new_scene['folder_id'] == old_parent)
ck('Timeless003 path refresh matches latest verified same-ID folder rename', new_scene['path'].rsplit('/', 1)[0].endswith(scene_folder['path_display']) and new_scene['folder_url'].endswith(quote(scene_folder['path_display'], safe='/')))
ck('All photography counts preserved,40 required actions remain', audit['counts']['required_picture_actions'] == old_audit['counts']['required_picture_actions'] == 40 and audit['counts']['in_situ_statuses'] == {'Available': 165, 'No verified image': 22} and audit['counts']['series_statuses']['No verified image'] == 17)
queue_counts = ptr['current_missing_picture_lists']
ck('Two owner deferrals remain open and yield12 active context plus10 held cases', queue_counts['active_in_situ_source_requests'] == 12 and queue_counts['owner_held_in_situ_cases'] == 10 and queue_counts['in_situ_gaps'] == 22 and queue_counts['series_gaps'] == 17)

photo = after['sheets']['Photo Coverage']['cells']
rowmap = {x['value']: cell[1:] for cell, x in photo.items() if cell.startswith('A') and x['value'].startswith('BSI-')}
plan = {'workbookPath': str(snapshot), 'expectedSha256': sha(data), 'reportPath': str(v / 'artifact-readback.json'), 'cells': []}

def add(sheet, cell, expected, label):
    plan['cells'].append({'sheet': sheet, 'cell': cell, 'expected': expected, 'label': label})

for sh, cell, expected, label in [('Master Catalogue', 'B4', 187, 'active options'), ('Master Catalogue', 'D4', 112, 'component identities'), ('Master Catalogue', 'F4', 187, 'six working fields'), ('Photo Coverage', 'B4', 177, 'individual full views'), ('Photo Coverage', 'D4', 165, 'qualified contexts'), ('Photo Coverage', 'F4', 116, 'series references'), ('Missing Pictures', 'B4', 39, 'find or capture'), ('Missing Pictures', 'D4', 1, 'legacy identity'), ('Missing Pictures', 'F4', 54, 'optional images'), ('Selling Details', 'B4', 187, 'selling records')]:
    add(sh, cell, expected, label)
for oid in targets:
    row = rowmap[oid]
    add('Photo Coverage', 'F' + row, 'Available', oid + ' context status unchanged')
    add('Photo Coverage', 'O' + row, fid, oid + ' exact004 file ID')
    add('Photo Coverage', 'P' + row, new_parent, oid + ' new actual parent')
    add('Photo Coverage', 'M' + row, old_opts[oid]['file_id'], oid + ' individual primary unchanged')
    for sheet, col in [('Photo Coverage', 'G'), ('Master Catalogue', 'T')]:
        target = after['sheets'][sheet]['links'][col + row]
        source = c2[oid]['in_situ']['reference']
        url = urlparse(target)
        display_path = source['path'].split('ns:202238505/', 1)[1]
        target_path = unquote(url.path)
        preview_path_matches = target_path == '/preview' + display_path
        home_query_matches = target_path == '/home' + display_path.rsplit('/', 1)[0] and parse_qs(url.query).get('preview') == [source['name']]
        ck(oid + ' ' + sheet + '004 link resolves to exact canonical source in new parent', target == source['image_url'] and url.scheme == 'https' and url.hostname == 'www.dropbox.com' and (preview_path_matches or home_query_matches))
row = rowmap[scene_option]
for col, expected, label in [('F', 'Available', 'existing context remains available'), ('O', 'id:cnqzTNngPVsAAAAAAAyh6g', 'same003 source ID'), ('P', old_parent, 'same held-scene parent ID'), ('M', old_opts[scene_option]['file_id'], 'individual primary preserved')]:
    add('Photo Coverage', col + row, expected, 'Timeless Spiral ' + label)
row = rowmap['BSI-3635E3DC3434']
for col, expected, label in [('C', 'Available', 'accepted individual'), ('F', 'No verified image', 'context source pending'), ('I', 'No verified image', 'series source pending'), ('M', 'id:cnqzTNngPVsAAAAAAA6VmA', 'accepted primary ID')]:
    add('Photo Coverage', col + row, expected, 'Pewter ' + label)
(v / 'artifact-read-plan.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2) + '\n')
report = {'schema': 'boldstone.deco004-independent-final-readback.v1', 'recorded_utc': datetime.now(timezone.utc).isoformat(), 'status': 'PASS_XML_CANONICAL_PRESERVATION_ARTIFACT_READBACK_PENDING', 'pointer_sha256': sha(ptr_bytes), 'workbook': str(b / ptr['workbook']), 'workbook_sha256': sha(data), 'register': str(b / ptr['register']), 'register_sha256': sha(reg_bytes), 'checks': checks, 'check_count': len(checks), 'sheets': len(after['sheets']), 'formulas': len(after['formulas']), 'native_hyperlinks': after['hyperlinks'], 'public_artifact_read_plan': str(v / 'artifact-read-plan.json'), 'workbook_modified_or_exported': False, 'canonical_or_native_writes': 0}
(j / 'independent-final-xml-canonical-readback.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'status': report['status'], 'checks': len(checks), 'artifact_cells': len(plan['cells']), 'private_workspace': str(v), 'workbook_sha256': sha(data)}))
