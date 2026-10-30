"""Independent final review: six URL corrections and ten approved Moonwave moves."""
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
from inspect_candidate import ROOT, LANE, CANDIDATE as C, sha, load, objsha, diffs, dropbox_target, allowed_case_url, allowed_moved_image_url, allowed_moved_folder_pair


def save(name, value):
    with (LANE / name).open('x') as f:
        json.dump(value, f, ensure_ascii=False, indent=2); f.write('\n')


def check(name, passed, details=None):
    checks.append({'name': name, 'passed': bool(passed), 'details': details})


expected = load(LANE / 'expectations.json')
extension = load(LANE / 'moonwave-scope-extension.json')
moves = extension['moves']; moved_by_id = {x['file_id']: x for x in moves}
native_readback = load(LANE / 'moonwave-native-readback.json')
native_packet = Path(native_readback['native_seal']['path']).parent
native_overlay = load(native_readback['overlay']['path'])
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
    '/latest_image_coverage_audit/visual_verification', '/latest_moonwave_approved_native_navigation',
    '/source_offer_edges/15/current_primary_reference/folder_id',
    '/source_offer_edges/15/current_primary_reference/folder_url',
    '/source_offer_edges/15/current_primary_reference/image_url',
    '/source_media_configuration_coverage/163/current_example_reference_navigation',
}
check('remaining_register_changes_are_declared_metadata_and_two_own_file_navigation_records', {x['path'] for x in metadata} == allowed_metadata_paths and new['latest_current_url_case_normalization'] == summary)
check('Moonwave_native_owner_authority_receipts_and_ten_original_hashes_pass', native_readback['status'] == 'PASS' and native_readback['checks_passed'] == native_readback['checks_total'] == 13 and sha(native_readback['native_seal']['path']) == native_readback['native_seal']['sha256'] and sha(native_readback['overlay']['path']) == native_readback['overlay']['sha256'])
coverage_copy = deepcopy(new['source_media_configuration_coverage'])
current_example = coverage_copy[163].pop('current_example_reference_navigation')
rp2 = moved_by_id['id:cnqzTNngPVsAAAAAAArp2Q']; example = current_example.get(rp2['file_id'], {})
check('coverage163_adds_only_rp2Q_current_navigation_preserving_four_ids_and_BOM_scope',
      coverage_copy == old['source_media_configuration_coverage'] and len(current_example) == 1 and
      example.get('file_id') == rp2['file_id'] and example.get('folder_id') == rp2['new_parent_id'] and
      example.get('path') == 'ns:202238505/' + rp2['new_path'] and
      dropbox_target(example.get('image_url', ''))[1] == rp2['new_path'] and
      dropbox_target(example.get('folder_url', ''))[1] == rp2['new_path'].rsplit('/', 1)[0] and
      example.get('source_overlay_sha256') == native_readback['overlay']['sha256'])
check('188_active_189_retained_112_components_110_groups_and_holds_preserved',
      len(new['active_option_ids']) == 188 and len(new['options']) == 189 and len(new['components']) == 112 and
      new['current_working_design_group_projection']['grouped_working_design_identity_count'] == 110 and
      all(summary[k] == v for k, v in {'corrected_options': 6, 'corrected_option_url_fields': 12, 'held_context': 22, 'held_series': 1, 'deferred_identity': 1, 'active_photo_requests': 0}.items()) and
      all(summary[k] == 0 for k in ['native_file_ids_changed', 'native_folder_ids_changed', 'native_moves', 'source_snapshots_changed', 'new_image_selections', 'photo_role_bindings_changed', 'new_physical_verifications', 'new_platform_matches', 'native_or_platform_writes_by_importer']))
check('import_summary_distinguishes_ten_completed_native_moves_from_no_importer_writes', all(summary[k] == v for k, v in {'approved_moonwave_file_paths_refreshed': 10, 'approved_moonwave_actual_parent_changes': 10, 'moonwave_White_files': 84, 'moonwave_InSitu_files': 15, 'moonwave_originals_preserved': 99, 'moonwave_original_bytes_preserved': 784220860}.items()))

old_audit = load(manifest['audit']['snapshot']); new_audit = load(C / 'image-coverage-current.json')
audit_changes = list(diffs(old_audit, new_audit))
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
case_asset_changes = [x for x in asset_changes if x['path'].split('/')[1] in file_ids]
move_asset_changes = [x for x in asset_changes if x['path'].split('/')[1] in moved_by_id]
check('image_audit_changes_only_40_case_normalized_paths_and_urls_no_roles_or_counts',
      len(audit_changes) == 40 and all(x['path'].split('/')[1] in {'coverage', 'missing_pictures'} and case_path(x['before'], x['after']) for x in audit_changes))
route_asset_ids = {'id:cnqzTNngPVsAAAAAAAsR7A', 'id:cnqzTNngPVsAAAAAAAsStA'}
route_changes = [x for x in case_asset_changes if x['path'] in {'/' + oid + '/image_url' for oid in route_asset_ids}]
case_changes = [x for x in case_asset_changes if x not in route_changes]
row_by_file_id = {row['expected_file_id']: row for row in expected['rows']}
check('six_asset_projections_change_24_case_paths_and_two_equivalent_same_file_URL_forms',
      len(case_asset_changes) == 26 and len(case_changes) == 24 and len(route_changes) == 2 and
      all(x['path'].rsplit('/', 1)[1] in {'display_path', 'path', 'folder_path', 'image_url', 'folder_url'} and case_path(x['before'], x['after']) for x in case_changes) and
      all(dropbox_target(x['before'])[0] == '/home' and dropbox_target(x['after'])[0] == '/preview' and
          dropbox_target(x['before'])[1] == dropbox_target(x['after'])[1] and
          x['after'] == row_by_file_id[x['path'].split('/')[1]]['proposed']['image_url'] for x in route_changes))
overlay_objects = {x['file_id']: x for x in native_overlay['objects']}
move_asset_failures = []
for x in move_asset_changes:
    oid = x['path'].split('/')[1]; field = x['path'].rsplit('/', 1)[1]; move = moved_by_id[oid]
    old_parent = move['old_path'].rsplit('/', 1)[0]; new_parent = move['new_path'].rsplit('/', 1)[0]
    b, a = x.get('before'), x.get('after')
    permitted = (
        field == 'display_path' and (b, a) == (move['old_path'], move['new_path']) or
        field == 'path' and (b, a) == ('ns:202238505/' + move['old_path'], 'ns:202238505/' + move['new_path']) or
        field == 'folder_id' and (b, a) == (move['old_parent_id'], move['new_parent_id']) or
        field == 'folder_path' and (b, a) in [(old_parent, new_parent), ('ns:202238505/' + old_parent, 'ns:202238505/' + new_parent)] or
        field == 'image_url' and allowed_moved_image_url(b, a, [move]) or
        field == 'folder_url' and dropbox_target(b)[1] == old_parent and dropbox_target(a)[1] == new_parent or
        field == 'modified_time' and a == overlay_objects[oid]['current_server_modified']
    )
    if not permitted: move_asset_failures.append(x)
check('ten_moved_asset_records_only_change_verified_paths_parents_and_server_clock', len(move_asset_changes) == 70 and len(asset_changes) == 96 and not move_asset_failures, move_asset_failures)
old_map = load(manifest['native_map']['snapshot']); new_map = load(C / 'current-native-reference-map.json')
map_changes = list(diffs(old_map['current_objects'], new_map['current_objects']))
case_map_changes = [x for x in map_changes if x['path'].split('/')[1] in all_ids]
new_map_changes = [x for x in map_changes if x['path'].split('/')[1] in moved_by_id]
check('case_reference_map_preserves_same_ids_parent_ids_names_sizes', len(case_map_changes) == 12 and all(x['path'].rsplit('/', 1)[1] in {'display_path', 'path'} and case_path(x['before'], x['after']) for x in case_map_changes))
new_map_valid = []
for x in new_map_changes:
    oid = x['path'].split('/')[1]; move = moved_by_id[oid]; obj = x.get('after', {})
    new_map_valid.append(x.get('operation') == 'add' and obj.get('file_id') == oid and obj.get('object_type') == 'file' and obj.get('name') == move['new_path'].rsplit('/', 1)[1] and obj.get('path') == 'ns:202238505/' + move['new_path'] and obj.get('display_path') == move['new_path'] and obj.get('parent_id') == move['new_parent_id'] and obj.get('size') == move['size'])
check('ten_previously_unrepresented_map_files_added_from_verified_exact_ids', len(new_map_changes) == 10 and len(map_changes) == 22 and all(new_map_valid))
expected_path_index = deepcopy(old_map['old_path_to_id'])
for move in moves: expected_path_index[move['new_path'].casefold()] = move['file_id']
check('path_index_preserves_prior_aliases_and_adds_only_ten_current_paths', expected_path_index == new_map['old_path_to_id'])
check('all_six_file_paths_and_immediate_parents_match_proposed_links', all(
    new_map['current_objects'][r['expected_file_id']]['display_path'] == dropbox_target(r['proposed']['image_url'])[1] and
    new_map['current_objects'][r['expected_file_id']]['parent_id'] == r['expected_folder_id'] and
    new_map['current_objects'][r['expected_folder_id']]['display_path'] == dropbox_target(r['proposed']['folder_url'])[1]
    for r in expected['rows']))
old_history = old_map['verified_path_change_history']; new_history = new_map['verified_path_change_history']
check('old_path_history_retained_with_case_observation_and_verified_Moonwave_append', new_history[:-2] == old_history and len(new_history) == len(old_history) + 2 and new_history[-2]['native_moves'] == 0 and new_history[-1]['sha256'] == native_readback['overlay']['sha256'])
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
expected_header = '188 active options;112 retained component IDs;110 working design groups. Six current URL corrections and ten approved Moonwave photo moves imported; stable identities, specifications and owner holds retained.'
rp1 = moved_by_id['id:cnqzTNngPVsAAAAAAArp1g']
value_by_path = {x['path']: x for x in value_changes}
parent_value_paths = {'/Platform Sources/X25/value', '/Listing Offer Links/U25/value'}
check('only_workbook_values_changed_are_release_header_and_O016_current_parent_ids',
      len(value_changes) == 3 and set(value_by_path) == parent_value_paths | {'/Master Catalogue/A3/value'} and
      value_by_path['/Master Catalogue/A3/value']['after'] == expected_header and
      all((value_by_path[p]['before'], value_by_path[p]['after']) == (rp1['old_parent_id'], rp1['new_parent_id']) for p in parent_value_paths))
check('O016_source_file_identity_and_current_parent_column_meanings_preserved',
      before_book['Listing Offer Links']['A25'] == after_book['Listing Offer Links']['A25'] and
      after_book['Listing Offer Links']['A25']['value'] == 'O016' and
      all(before_book[sheet][cell] == after_book[sheet][cell] and after_book[sheet][cell]['value'] == rp1['file_id']
          for sheet, cell in [('Platform Sources', 'W25'), ('Listing Offer Links', 'T25')]) and
      all(before_book[sheet][cell] == after_book[sheet][cell] and after_book[sheet][cell]['value'] == 'Dropbox folder ID'
          for sheet, cell in [('Platform Sources', 'X9'), ('Listing Offer Links', 'U9')]))
link_changes = [x for x in pre['workbook_cell_differences'] if x['path'].endswith('/hyperlink')]
external_changes = [x for x in link_changes if x['before'].startswith('http') or x['after'].startswith('http')]
local_changes = [x for x in link_changes if x not in external_changes]
proj = load(C / 'projection-index.json'); old_out = proj['old_output']; new_out = proj['new_output']
local_fail = []
for x in local_changes:
    exact_rebase = x['before'].startswith(old_out + '/') and x['after'] == new_out + x['before'][len(old_out):]
    review = x['path'] == '/Master Catalogue/A3/hyperlink' and x['after'] == new_out + '/moonwave-approved-folder-changes.html'
    if not (exact_rebase or review) or not Path(x['after'].split('#', 1)[0]).is_file():
        local_fail.append(x)
case_links = [x for x in external_changes if allowed_case_url(x['before'], x['after'], expected)]
moon_links = [x for x in external_changes if x not in case_links]
moon_image_paths = {'/Platform Sources/U25/hyperlink', '/Listing Offer Links/R25/hyperlink'}
moon_folder_paths = {'/Platform Sources/V25/hyperlink', '/Listing Offer Links/S25/hyperlink'}
check('275_case_links_and_exact_four_O016_own_file_and_parent_links_plus_report_rebases',
      len(external_changes) == 279 and len(case_links) == 275 and
      {x['path'] for x in moon_links} == moon_image_paths | moon_folder_paths and
      all(allowed_moved_image_url(x['before'], x['after'], [rp1]) if x['path'] in moon_image_paths
          else allowed_moved_folder_pair(x['before'], x['after'], [rp1]) for x in moon_links) and
      not local_fail,
      {'case_links': len(case_links), 'Moonwave_links': moon_links, 'local': len(local_changes), 'local_failures': local_fail})
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
native_links = load(native_packet / 'all-current-moonwave-image-folder-links.json')
moonwave_report = Path(new_out) / 'all-current-moonwave-images.html'
moonwave_parsed = Parser(); moonwave_parsed.feed(moonwave_report.read_text())
rendered_targets = {t[1] for url in moonwave_parsed.links if (t := dropbox_target(url))}
check('current_Moonwave_report_contains_all_99_file_targets_and_actual_folders', len(native_links) == 99 and all(dropbox_target(x['image_url'])[1] in rendered_targets and dropbox_target(x['folder_url'])[1] in rendered_targets for x in native_links))
with (Path(new_out) / 'Current_Individual_Options_188.csv').open(newline='') as f:
    current_options_csv = list(csv.DictReader(f))
check('current_option_csv_has_188_rows_and_all_six_corrected_image_folder_urls', len(current_options_csv) == 188 and all(any(row['option_id'] in values and all(url in values for url in row['proposed'].values()) for values in (set(x.values()) for x in current_options_csv)) for row in expected['rows']))
report_verification = load(C / 'report-verification.json')
report_artifacts = {x['path']: x['sha256'] for section in ['pages', 'csv_files'] for x in report_verification[section]}
check('all_linked_HTML_and_CSV_bytes_match_frozen_report_manifest',
      str(Path(new_out) / 'moonwave-approved-folder-changes.html') in report_artifacts and
      all(sha(p) == h for p, h in report_artifacts.items()))

source_review_path = ROOT / 'components/parallel-reviews/unpaired43-next-evidence-20261024-B/next-evidence-review.json'
source_review = load(source_review_path)
new_options = {o['product_id']: o for o in new['options']}
source_ops = {o['product_id']: o for row in source_review['rows'] for o in row['related_current_options']}
source_guards = all(all(o[k] == new_options[oid][k] for k in ['name', 'image_url', 'folder_url', 'file_id', 'folder_id', 'master_fields', 'current_listing_resolution']) for oid, o in source_ops.items())
source_unaffected = not set(source_ops) & {r['option_id'] for r in expected['rows']}
check('B43_all_48_option_links_288_full_fields_and_source_observations_unchanged', len(source_ops) == 48 and source_guards and source_unaffected and objsha(new['current_authenticated_squarespace_inventory_observation']) == source_review['unchanged_source_observation_object_sha256'])
check('candidate_reports_and_before_pointer_bytes_stable_through_final_readback', all(sha(p) == h for p, h in frozen.items()) and all(sha(p) == h for p, h in report_artifacts.items()) and sha(ROOT / 'current-master.json') == expected['baseline_pointer_sha256'])

now = datetime.now(timezone.utc).isoformat()
result = {'schema': 'boldstone.independent.six-case-and-ten-Moonwave-navigation-qa.v1', 'status': 'PASS' if all(x['passed'] for x in checks) else 'FAIL',
          'recorded_utc': now, 'checks_passed': sum(x['passed'] for x in checks), 'checks_total': len(checks), 'checks': checks,
          'candidate_register_sha256': sha(C / 'canonical-master-register.json'), 'candidate_workbook_sha256': sha(C / 'master-workbook.pending'),
          'candidate_audit_sha256': sha(C / 'image-coverage-current.json'), 'frozen_artifacts': frozen, 'report_artifacts': report_artifacts,
          'native_readback': {'path': str(LANE / 'moonwave-native-readback.json'), 'sha256': sha(LANE / 'moonwave-native-readback.json')},
          'scope': 'Six existing file/parent URL capitalization corrections plus ten separately owner-approved, native-completed Moonwave moves. Same option identities, complete raw source/history/specification objects, roles and holds preserved. B independently read saved native receipts and ten moved local binaries, without live API calls or canonical writes.',
          'shared_writes': 0, 'native_calls': 0}
save('candidate-readback.json', result)
if result['status'] == 'PASS':
    attestation = {'status': 'B43_SOURCE_REVIEW_GUARDS_PASS_ON_FROZEN_COMBINED_NAVIGATION_CANDIDATE', 'recorded_utc': now,
                   'review': {'path': str(source_review_path), 'sha256': sha(source_review_path)}, 'candidate_register_sha256': result['candidate_register_sha256'],
                   'candidate_workbook_sha256': result['candidate_workbook_sha256'], 'options_checked': 48, 'complete_working_fields_checked': 288,
                   'affected_review_options': 0, 'new_or_changed_matches': 0, 'review_rewritten': False,
                   'publication_required_before_current_binding': True}
    save('source-review-baseline-attestation.json', attestation)
files = ['expectations.json', 'inspect_candidate.py', 'verify_complete.py', 'verify_six_only_not_run.py', 'preliminary-comparison.json', 'candidate-readback.json', 'verify_moonwave_native.py', 'moonwave-native-readback.json', 'moonwave-scope-extension.json', 'moonwave-scope-extension.initial.json']
files += ['checker-corrections.json', 'failed-attempt-1/verify_complete.py', 'failed-attempt-1/candidate-readback.json', 'failed-attempt-1/sealed-handoff.json']
if result['status'] == 'PASS':
    files.append('source-review-baseline-attestation.json')
seal = {'status': result['status'], 'recorded_utc': now, 'candidate_register_sha256': result['candidate_register_sha256'], 'candidate_workbook_sha256': result['candidate_workbook_sha256'],
        'files': [{'path': str(LANE / n), 'sha256': sha(LANE / n)} for n in files], 'shared_writes': 0, 'native_calls': 0}
save('sealed-handoff.json', seal)
print(json.dumps({'status': result['status'], 'passed': result['checks_passed'], 'total': result['checks_total'], 'failed': [x for x in checks if not x['passed']], 'qa_sha256': sha(LANE / 'candidate-readback.json'), 'seal_sha256': sha(LANE / 'sealed-handoff.json')}, ensure_ascii=False, indent=2))
