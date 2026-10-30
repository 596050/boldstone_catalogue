"""Finish the independent review of the frozen six-case navigation release."""
from copy import deepcopy
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
import ast
import csv
import json
import posixpath
import re
import xml.etree.ElementTree as ET
import zipfile
from inspect_candidate import ROOT, LANE, CANDIDATE as C, sha, load, objsha, diffs, dropbox_target, allowed_case_url


def save(name, value):
    with (LANE / name).open('x') as f:
        json.dump(value, f, ensure_ascii=False, indent=2); f.write('\n')


def check(name, passed, details=None):
    checks.append({'name': name, 'passed': bool(passed), 'details': details})


expected = load(LANE / 'expectations.json')
pre = load(LANE / 'preliminary-comparison.json')
freeze = load(C / 'candidate-freeze.json')
frozen = dict(freeze['frozen_artifacts'])
frozen[str(C / 'candidate-freeze.json')] = sha(C / 'candidate-freeze.json')
assert frozen == pre['frozen_artifacts']
assert all(sha(p) == h for p, h in frozen.items())
manifest = load(C / 'input-manifest.json')
old = load(expected['baseline_register']['path'])
new = load(C / 'canonical-master-register.json')
summary = load(C / 'import-summary.json')
checks = []
for name, passed in pre['preliminary_checks'].items():
    check(name, passed)
check('baseline_handoff_and_all_input_snapshots_match_guards',
      sha(expected['handoff']['path']) == expected['handoff']['sha256'] and
      all(sha(x['snapshot']) == x['sha256'] for x in manifest.values()) and
      sha(manifest['master_workbook']['snapshot']) == expected['baseline_workbook']['sha256'])

reg_changes = pre['register_differences']
link_roots = {'options', 'components', 'source_review_reconciliation', 'original_specification_current_references'}
links = [x for x in reg_changes if x['path'].split('/')[1] in link_roots]
expected_counts = {'options': 12, 'components': 8, 'source_review_reconciliation': 18, 'original_specification_current_references': 108}
check('146_current_projection_changes_are_authorized_case_only_links',
      all(sum(x['path'].split('/')[1] == k for x in links) == v for k, v in expected_counts.items()) and
      all(x['path'].rsplit('/', 1)[1] in {'image_url', 'folder_url'} and allowed_case_url(x['before'], x['after'], expected) for x in links))
metadata = [x for x in reg_changes if x not in links]
allowed_metadata_paths = {
    '/latest_active_photo_source_review/path', '/latest_current_url_case_normalization',
    '/latest_image_coverage_audit/audit', '/latest_image_coverage_audit/native_binding_verification',
    '/latest_image_coverage_audit/path', '/latest_image_coverage_audit/recorded_utc',
    '/latest_image_coverage_audit/status', '/latest_image_coverage_audit/verification',
    '/latest_image_coverage_audit/visual_verification',
}
check('remaining_register_changes_are_only_nine_release_metadata_fields', {x['path'] for x in metadata} == allowed_metadata_paths and new['latest_current_url_case_normalization'] == summary)
check('188_active_189_retained_112_components_110_groups_and_holds_preserved',
      len(new['active_option_ids']) == 188 and len(new['options']) == 189 and len(new['components']) == 112 and
      new['current_working_design_group_projection']['grouped_working_design_identity_count'] == 110 and
      all(summary[k] == v for k, v in {'corrected_options': 6, 'corrected_option_url_fields': 12, 'held_context': 22, 'held_series': 1, 'deferred_identity': 1, 'active_photo_requests': 0}.items()) and
      all(summary[k] == 0 for k in ['native_file_ids_changed', 'native_folder_ids_changed', 'native_moves', 'source_snapshots_changed', 'new_image_selections', 'photo_role_bindings_changed', 'new_physical_verifications', 'new_platform_matches', 'native_or_platform_writes_by_importer']))

old_audit = load(manifest['audit']['snapshot']); new_audit = load(C / 'image-coverage-current.json')
audit_changes = list(diffs(old_audit, new_audit))
check('image_audit_changes_only_40_current_link_strings_no_roles_or_counts',
      len(audit_changes) == 40 and all(x['path'].split('/')[1] in {'coverage', 'missing_pictures'} and allowed_case_url(x['before'], x['after'], expected) for x in audit_changes))
file_ids = {r['expected_file_id'] for r in expected['rows']}
folder_ids = {r['expected_folder_id'] for r in expected['rows']}
all_ids = file_ids | folder_ids
target_paths = {dropbox_target(u)[1] for row in expected['rows'] for u in row['proposed'].values()}


def case_path(before, after):
    if not isinstance(before, str) or not isinstance(after, str) or before == after:
        return False
    if before.startswith('https://'):
        return allowed_case_url(before, after, expected)
    if before.startswith('ns:') and after.startswith('ns:'):
        bns, bp = before.split('//', 1); ans, ap = after.split('//', 1)
        return bns == ans and bp.casefold() == ap.casefold() and '/' + ap.lstrip('/') in target_paths
    return before.casefold() == after.casefold() and after in target_paths


old_assets = load(manifest['report_assets']['snapshot']); new_assets = load(C / 'current-assets.json')
asset_changes = list(diffs(old_assets, new_assets))
check('asset_projection_changes_only_case_of_six_files_and_their_parents', len(asset_changes) == 26 and
      all(x['path'].split('/')[1] in file_ids and x['path'].rsplit('/', 1)[1] in {'display_path', 'path', 'folder_path', 'image_url', 'folder_url'} and case_path(x['before'], x['after']) for x in asset_changes))
old_map = load(manifest['native_map']['snapshot']); new_map = load(C / 'current-native-reference-map.json')
map_changes = list(diffs(old_map['current_objects'], new_map['current_objects']))
check('native_reference_map_preserves_same_ids_parent_ids_names_sizes', len(map_changes) == 12 and all(x['path'].split('/')[1] in all_ids and x['path'].rsplit('/', 1)[1] in {'display_path', 'path'} and case_path(x['before'], x['after']) for x in map_changes))
check('all_six_file_paths_and_immediate_parents_match_proposed_links', all(
    new_map['current_objects'][r['expected_file_id']]['display_path'] == dropbox_target(r['proposed']['image_url'])[1] and
    new_map['current_objects'][r['expected_file_id']]['parent_id'] == r['expected_folder_id'] and
    new_map['current_objects'][r['expected_folder_id']]['display_path'] == dropbox_target(r['proposed']['folder_url'])[1]
    for r in expected['rows']))
old_history = old_map['verified_path_change_history']; new_history = new_map['verified_path_change_history']
check('old_path_history_retained_with_one_no_move_observation_append', new_history[:-1] == old_history and len(new_history) == len(old_history) + 1 and new_history[-1]['native_moves'] == 0)
check('physical_audit_originals_design_groups_and_Wall_Circle_health_bytes_unchanged', all(
    sha(C / name) == manifest[key]['sha256'] for key, name in [
        ('physical_audit', 'physical-source-audit.json'), ('originals', 'original-verification.json'),
        ('working_groups', 'working-design-group-projection.json'), ('primary_health', 'current-primary-navigation-health.json')]))

helper = ROOT / 'components/parallel-reviews/decowaves1-candidate-qa-20261024T040807Z/verify_decowaves1.py'
function = next(n for n in ast.parse(helper.read_text()).body if isinstance(n, ast.FunctionDef) and n.name == 'read_xlsx')
N = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main', 'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
exec(compile(ast.Module(body=[function], type_ignores=[]), str(helper), 'exec'))
before_book, before_heights = read_xlsx(manifest['master_workbook']['snapshot'])
after_book, after_heights = read_xlsx(C / 'master-workbook.pending')
value_changes = [x for x in pre['workbook_cell_differences'] if x['path'].endswith('/value')]
expected_header = '188 active options;112 retained component IDs;110 working design groups. Six current image and folder links aligned to Dropbox capitalization, retaining stable IDs, qualified specifications and owner holds.'
check('only_workbook_value_change_is_the_current_release_header', len(value_changes) == 1 and value_changes[0]['path'] == '/Master Catalogue/A3/value' and value_changes[0]['after'] == expected_header)
link_changes = [x for x in pre['workbook_cell_differences'] if x['path'].endswith('/hyperlink')]
external_changes = [x for x in link_changes if x['before'].startswith('http') or x['after'].startswith('http')]
local_changes = [x for x in link_changes if x not in external_changes]
proj = load(C / 'projection-index.json'); old_out = proj['old_output']; new_out = proj['new_output']
local_fail = []
for x in local_changes:
    exact_rebase = x['before'].startswith(old_out + '/') and x['after'] == new_out + x['before'][len(old_out):]
    review = x['path'] == '/Master Catalogue/A3/hyperlink' and x['after'] == new_out + '/six-current-link-corrections.html'
    if not (exact_rebase or review) or not Path(x['after'].split('#', 1)[0]).is_file():
        local_fail.append(x)
check('275_external_links_only_six_files_or_parents_plus_existing_report_rebases', len(external_changes) == 275 and all(allowed_case_url(x['before'], x['after'], expected) for x in external_changes) and not local_fail, {'external': len(external_changes), 'local': len(local_changes), 'local_failures': local_fail})
check('no_other_workbook_cell_properties_or_row_heights_changed', len(pre['workbook_cell_differences']) == len(value_changes) + len(link_changes) and before_heights == after_heights)
protected_failures = []
for sheet, cells in before_book.items():
    for cell, value in cells.items():
        col = re.sub('[0-9]', '', cell)
        protected = sheet == 'Fingerprint History' or (sheet == 'Source Specifications' and col in {'M', 'N'}) or (sheet == 'Moonphases and Dune' and col == 'I')
        if protected and after_book[sheet].get(cell) != value:
            protected_failures.append(sheet + '!' + cell)
check('historical_workbook_source_columns_and_Fingerprint_history_unchanged', not protected_failures, protected_failures)

class Parser(HTMLParser):
    def __init__(self):
        super().__init__(); self.links = []
    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.links.extend(v for k, v in attrs if k == 'href')

page = Path(new_out) / 'six-current-link-corrections.html'
parsed = Parser(); parsed.feed(page.read_text())
check('six_item_report_contains_all_twelve_proposed_image_and_folder_urls', all(v in parsed.links for row in expected['rows'] for v in row['proposed'].values()))
with (Path(new_out) / 'Current_Individual_Options_188.csv').open(newline='') as f:
    current_options_csv = list(csv.DictReader(f))
check('current_option_csv_has_188_rows_and_all_six_corrected_image_folder_urls', len(current_options_csv) == 188 and all(any(row['option_id'] in values and all(url in values for url in row['proposed'].values()) for values in (set(x.values()) for x in current_options_csv)) for row in expected['rows']))

source_review_path = ROOT / 'components/parallel-reviews/unpaired43-next-evidence-20261024-B/next-evidence-review.json'
source_review = load(source_review_path)
new_options = {o['product_id']: o for o in new['options']}
source_ops = {o['product_id']: o for row in source_review['rows'] for o in row['related_current_options']}
source_guards = all(all(o[k] == new_options[oid][k] for k in ['name', 'image_url', 'folder_url', 'file_id', 'folder_id', 'master_fields', 'current_listing_resolution']) for oid, o in source_ops.items())
source_unaffected = not set(source_ops) & {r['option_id'] for r in expected['rows']}
check('B43_all_48_option_links_288_full_fields_and_source_observations_unchanged', len(source_ops) == 48 and source_guards and source_unaffected and objsha(new['current_authenticated_squarespace_inventory_observation']) == source_review['unchanged_source_observation_object_sha256'])
check('candidate_and_before_pointer_bytes_stable_through_final_readback', all(sha(p) == h for p, h in frozen.items()) and sha(ROOT / 'current-master.json') == expected['baseline_pointer_sha256'])

now = datetime.now(timezone.utc).isoformat()
result = {'schema': 'boldstone.independent.six-current-url-case-navigation-qa.v1', 'status': 'PASS' if all(x['passed'] for x in checks) else 'FAIL',
          'recorded_utc': now, 'checks_passed': sum(x['passed'] for x in checks), 'checks_total': len(checks), 'checks': checks,
          'candidate_register_sha256': sha(C / 'canonical-master-register.json'), 'candidate_workbook_sha256': sha(C / 'master-workbook.pending'),
          'candidate_audit_sha256': sha(C / 'image-coverage-current.json'), 'frozen_artifacts': frozen,
          'scope': 'Six exact existing file and parent URL capitalization corrections plus current projections. Same IDs, complete source/history/specification objects, roles and holds preserved. No new live reads, physical checks, source matches or canonical writes by B.',
          'shared_writes': 0, 'native_calls': 0}
save('candidate-readback.json', result)
if result['status'] == 'PASS':
    attestation = {'status': 'B43_SOURCE_REVIEW_GUARDS_PASS_ON_FROZEN_SIX_CASE_CANDIDATE', 'recorded_utc': now,
                   'review': {'path': str(source_review_path), 'sha256': sha(source_review_path)}, 'candidate_register_sha256': result['candidate_register_sha256'],
                   'candidate_workbook_sha256': result['candidate_workbook_sha256'], 'options_checked': 48, 'complete_working_fields_checked': 288,
                   'affected_review_options': 0, 'new_or_changed_matches': 0, 'review_rewritten': False,
                   'publication_required_before_current_binding': True}
    save('source-review-baseline-attestation.json', attestation)
files = ['expectations.json', 'inspect_candidate.py', 'verify_complete.py', 'preliminary-comparison.json', 'candidate-readback.json']
if result['status'] == 'PASS':
    files.append('source-review-baseline-attestation.json')
seal = {'status': result['status'], 'recorded_utc': now, 'candidate_register_sha256': result['candidate_register_sha256'], 'candidate_workbook_sha256': result['candidate_workbook_sha256'],
        'files': [{'path': str(LANE / n), 'sha256': sha(LANE / n)} for n in files], 'shared_writes': 0, 'native_calls': 0}
save('sealed-handoff.json', seal)
print(json.dumps({'status': result['status'], 'passed': result['checks_passed'], 'total': result['checks_total'], 'failed': [x for x in checks if not x['passed']], 'qa_sha256': sha(LANE / 'candidate-readback.json'), 'seal_sha256': sha(LANE / 'sealed-handoff.json')}, ensure_ascii=False, indent=2))
