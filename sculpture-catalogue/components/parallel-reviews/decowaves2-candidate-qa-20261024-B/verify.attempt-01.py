import ast
import copy
import csv
import hashlib
import json
import posixpath
import zipfile
from collections import Counter
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse, parse_qs
from xml.etree import ElementTree as ET

BASE = Path('/Users/tprice/Documents/boldstone/sculpture-catalogue')
C = BASE / 'components/reconciliation/decowaves2-owner-design-group-master-2026-10-24'
OUT = BASE / 'outputs/decowaves2-owner-design-group-master-2026-10-24'
OWN = Path(__file__).parent
RECOVERY = BASE / 'components/parallel-reviews/decowaves2-owner-answer-recovery-20261024'
PAIR = {'BSI-FE830AE502C3', 'BSI-837E9B0B3B36'}
COMP = {'BC-DECO-2', 'BC-FDW-2'}
TERRA = 'BSI-27967D2BD7B4'
REG = '8826312ebe27d675e7477925d849be3a3bc14d71cfdaa2f6b310c594b2a64ccf'
BOOK = 'ee78acab9c7f07cfab9cb5292c27e3eec70762127d1e9bd495310aed16e06316'
PLAN = 'f919e685b438b99a2d41236b77379e72e575215ea3cfd434d6181fd9fb0db2e4'

def load(p):
    return json.loads(Path(p).read_text())

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def save(name, value):
    (OWN / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')

checks = []
def check(name, passed, details=None):
    checks.append({'name': name, 'passed': bool(passed), 'details': details})

manifest = load(C / 'input-manifest.json')
old = load(manifest['master_register']['snapshot'])
new = load(C / 'canonical-master-register.json')
edge = load(C / 'owner-design-edge.json')
projection = load(C / 'working-design-group-projection.json')
plan = load(C / 'workbook-edit-plan.json')
changes = load(C / 'authorized-current-field-changes.json')
oldops = {x['product_id']: x for x in old['options']}
newops = {x['product_id']: x for x in new['options']}
oldcomps = {x['component_id']: x for x in old['components']}
frozen_paths = [C / x for x in [
    'canonical-master-register.json', 'master-workbook.pending', 'workbook-edit-plan.json',
    'authorized-current-field-changes.json', 'input-manifest.json', 'owner-design-edge.json',
    'working-design-group-projection.json', 'transcript-evidence.json',
    'physical-source-audit.json', 'current-primary-navigation-health.json',
]] + [OUT / x for x in [
    'decowaves1-owner-design-equivalence.html', 'decowaves2-owner-design-equivalence.html',
    'Owner_Decowaves2_Design_Equivalence_2.csv', 'Current_Working_Design_Groups_110.csv',
    'physical-evidence-review.html',
]]
frozen = {str(p): sha(p) for p in frozen_paths}
check('frozen_register_workbook_plan_hashes',
      sha(C / 'canonical-master-register.json') == REG and
      sha(C / 'master-workbook.pending') == BOOK and sha(C / 'workbook-edit-plan.json') == PLAN)
check('published_baseline_and_all_input_snapshots_match',
      manifest['master_register']['sha256'] == '164211ed960d363e3e249142096997821ff80c63404a5ee8db6254959f9a42e5' and
      manifest['master_workbook']['sha256'] == 'd74b32a3a7a9073c0d3e62c0660dd03fbf22cb521273a0f0a323a58ea7e7fb54' and
      all(sha(v['snapshot']) == v['sha256'] for v in manifest.values() if isinstance(v, dict) and 'snapshot' in v))

seal = load(RECOVERY / 'sealed-handoff.json')
recovery = load(RECOVERY / 'transcript-evidence.json')
transcript = load(C / 'transcript-evidence.json')
check('independent_recovery_seal_and_all_artifacts_match',
      sha(RECOVERY / 'sealed-handoff.json') == '06d6dbd345c81f5e1bc0505020f614b71dc42aac28e685ac009554f8b009e161' and
      all(sha(f['path']) == f['sha256'] for f in seal['files']))
reads = []
with Path(transcript['source_path']).open('rb') as f:
    first = f.readline()
    meta = json.loads(first)
    check('session_meta_identity_and_exact_line_hash',
          meta['payload']['id'] == transcript['source_thread_id'] == recovery['session_id'] == '01a13fbf-1cbc-7511-8416-cf339051083e' and
          hashlib.sha256(first).hexdigest() == recovery['session_meta_sha256'])
    for r in transcript['records']:
        f.seek(r['byte_offset'])
        raw = f.read(r['byte_length'])
        reads.append({'kind': r['kind'], 'ordinal': json.loads(raw)['ordinal'],
                      'timestamp': r['timestamp'], 'raw_line_sha256': hashlib.sha256(raw).hexdigest(),
                      'matched': json.loads(raw) == r['source_record'] and hashlib.sha256(raw).hexdigest() == r['raw_line_sha256']})
    start = transcript['records'][0]['byte_offset']
    last = transcript['records'][-1]
    f.seek(start)
    window = [json.loads(x) for x in f.read(last['byte_offset'] + last['byte_length'] - start).splitlines()]
check('all_three_exact_transcript_records_match_both_recovery_packets',
      len(reads) == 3 and all(x['matched'] for x in reads) and
      [(r['byte_offset'], r['byte_length'], r['raw_line_sha256']) for r in transcript['records']] ==
      [(r['byte_offset'], r['byte_length'], r['raw_line_sha256']) for r in recovery['records']])
q, a1, a2 = transcript['records']
human = [d for d in window if d.get('payload', {}).get('type') == 'message' and d['payload'].get('role') == 'user']
check('exact_pair_question_followed_only_by_two_identical_owner_answers',
      q['source_record']['payload']['role'] == 'assistant' and
      all(oldops[oid][k] in q['text_verbatim'] for oid in PAIR for k in ['image_url', 'folder_url']) and
      'same sculpture design in different finishes?' in q['text_verbatim'] and
      a1['text_verbatim'] == a2['text_verbatim'] == edge['owner_answer_verbatim'] == 'wYes' and
      all(x['source_record']['payload']['role'] == 'user' for x in [a1, a2]) and
      [x['ordinal'] for x in human] == [41252, 41257] and
      q['timestamp'] == '2026-10-24T04:06:31.591Z' and
      a1['timestamp'] == edge['owner_answer_timestamp'] == '2026-10-24T11:44:50.773Z' and
      a2['timestamp'] == edge['duplicate_answer_timestamp'] == '2026-10-24T11:46:10.866Z')
ev = load(C / 'evidence-manifest.json')
check('candidate_evidence_binding_and_native_receipt_hashes_match',
      all(sha(p) == v['sha256'] for p, v in ev.items()) and
      sha(edge['source_evidence']['path']) == edge['source_evidence']['sha256'] == sha(C / 'transcript-evidence.json'))

expected = copy.deepcopy(old)
before_mismatches = []
for item in changes:
    parent = expected
    for part in item['path'][:-1]:
        parent = parent[part]
    key = item['path'][-1]
    if item['before_exists'] and parent[key] != item['before']:
        before_mismatches.append(item['path'])
    if not item['before_exists'] and key in parent:
        before_mismatches.append(item['path'])
    parent[key] = copy.deepcopy(item['current'])
check('entire_register_has_only_twelve_logged_changes',
      len(changes) == 12 and all(x['group'] == 'register' for x in changes) and not before_mismatches and expected == new,
      before_mismatches)
stripped = copy.deepcopy(newops)
for oid in PAIR:
    stripped[oid].pop('current_owner_design_equivalence', None)
check('all189_option_objects_and_order_preserved_except_two_pair_annotations',
      len(newops) == 189 and stripped == oldops and
      [x['product_id'] for x in new['options']] == [x['product_id'] for x in old['options']])
stripped_comps = {x['component_id']: copy.deepcopy(x) for x in new['components']}
for cid in COMP:
    stripped_comps[cid].pop('current_owner_design_group', None)
    stripped_comps[cid]['scope_note'] = oldcomps[cid]['scope_note']
check('all112_component_ids_memberships_and_fields_preserved',
      len(stripped_comps) == 112 and stripped_comps == oldcomps and
      [x['component_id'] for x in new['components']] == [x['component_id'] for x in old['components']])
check('one_number2_edge_added_once_prior_number1_edge_unchanged',
      new['current_owner_design_equivalence_edges'] == old['current_owner_design_equivalence_edges'] + [edge] and
      set(edge['owner_confirmed_option_ids']) == PAIR and set(edge['component_ids']) == set(edge['retained_component_ids']) == COMP and
      edge['normalized_answer'] == 'Yes' and edge['no_physical_mould_cast_or_specification_transfer'] and
      edge['terracotta_owner_photo_approval'] is False)
check('edge_contains_exact_current_pair_names_ids_and_links',
      len(edge['exact_pair_references']) == 2 and
      all(all(r[k] == oldops[r['product_id']][k] for k in ['name', 'canonical_design_id', 'canonical_component_id', 'file_id', 'folder_id', 'image_url', 'folder_url']) for r in edge['exact_pair_references']))
preserve = ['source_offer_edges', 'source_platform_offer_coverage', 'current_authenticated_squarespace_inventory_observation',
            'latest_authenticated_source_observation_import', 'listing_resolution_native_action_drafts', 'current_listing_resolution',
            'current_listing_resolution_details', 'current_primary_navigation_health']
check('platform_source_fields_history_and_navigation_health_preserved', all(old[k] == new[k] for k in preserve))
payloads = [('physical-source-audit.json', 'physical_audit'), ('photo-review-queue.json', 'report_reviews'),
            ('photo-source-review.json', 'photo_source'), ('guided-owner-review-state.json', 'review_state'),
            ('pending-followups.json', 'pending')]
check('physical_evidence_photo_roles_review_state_and_holds_byte_identical',
      all(sha(C / file) == sha(manifest[key]['snapshot']) for file, key in payloads))
check('primary_navigation_warning_payload_unchanged', sha(C / 'current-primary-navigation-health.json') ==
      sha(BASE / 'components/reconciliation/decowaves1-owner-design-group-master-2026-10-24/current-primary-navigation-health.json'))

expected_map = dict(old['current_working_design_group_projection']['component_id_to_working_group'])
expected_map['BC-FDW-2'] = 'BC-DECO-2'
check('projection_adds_only_number2_design_relationship', projection['component_id_to_working_group'] == expected_map and
      new['current_working_design_group_projection'] == projection and len(set(expected_map.values())) == 110)
groups = {x['working_design_group_id']: x for x in projection['groups']}
check('all112_component_records_appear_once_across110groups', len(groups) == 110 and
      Counter(cid for g in groups.values() for cid in g['retained_component_ids']) == Counter(oldcomps.keys()))
membership_failures = []
oldgroups = {x['working_design_group_id']: x for x in old['current_working_design_group_projection']['groups']}
for gid, g in groups.items():
    cids = {cid for cid, target in expected_map.items() if target == gid}
    opts = {oid for cid in cids for oid in oldcomps[cid]['option_ids']}
    if set(g['retained_component_ids']) != cids or set(g['active_option_ids']) != opts:
        membership_failures.append(gid)
    if gid != 'BC-DECO-2' and g != oldgroups[gid]:
        membership_failures.append(gid + ':unrelated_group_changed')
check('every_group_membership_and_all_other_group_objects_preserved', not membership_failures, membership_failures)
check('number2_direct_confirmation_excludes_existing_terracotta_membership',
      set(groups['BC-DECO-2']['owner_directly_confirmed_option_ids']) == PAIR and
      TERRA in groups['BC-DECO-2']['active_option_ids'] and TERRA not in groups['BC-DECO-2']['owner_directly_confirmed_option_ids'] and
      'without new photograph approval' in groups['BC-DECO-2']['grouping_basis'])
check('counts_separate188options112ids110groups_and_unknown_physical_totals',
      projection['active_individual_finish_option_count'] == 188 and projection['retained_option_record_count'] == 189 and
      projection['retained_component_identity_record_count'] == 112 and projection['grouped_working_design_identity_count'] == 110 and
      projection['direct_owner_relationships'] == 2 and projection['whole_library_unique_design_count'] is None and
      'not a whole-library' in projection['scope'])

def csvread(name):
    with (OUT / name).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))

pairs = csvread('Owner_Decowaves2_Design_Equivalence_2.csv')
check('pair_csv_preserves_exact_two_records_links_ids_and_original_answer', len(pairs) == 2 and
      {r['option_id'] for r in pairs} == PAIR and all(
          all(r[k] == newops[r['option_id']][k] for k in ['name', 'image_url', 'folder_url', 'file_id', 'folder_id']) and
          r['owner_answer_utc'] == a1['timestamp'] and r['owner_answer_verbatim'] == 'wYes' and
          r['specifications_transferred'] == 'False' and r['component_id_retained'] == newops[r['option_id']]['canonical_component_id']
          for r in pairs))
rows = csvread('Current_Working_Design_Groups_110.csv')
check('110group_csv_matches_exact_membership_and_confirmation_scope', len(rows) == 110 and
      {r['working_design_group_id'] for r in rows} == set(groups) and all(
          ([] if not r[k] else r[k].split(' | ')) == groups[r['working_design_group_id']][k]
          for r in rows for k in ['retained_component_ids', 'active_option_ids', 'owner_directly_confirmed_option_ids']))

class HTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links, self.text = [], []
    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.links.append(dict(attrs).get('href'))
    def handle_data(self, data):
        self.text.append(data)

h = HTML()
h.feed((OUT / 'decowaves2-owner-design-equivalence.html').read_text())
text = ' '.join(h.text)
h1 = HTML()
h1.feed((OUT / 'decowaves1-owner-design-equivalence.html').read_text())
text1 = ' '.join(h1.text)
check('number2_html_has_exact_pair_links_and_all12_qualified_field_displays',
      all(newops[oid][k] in h.links for oid in PAIR for k in ['image_url', 'folder_url']) and
      all(v['display'] in text for oid in PAIR for v in newops[oid]['master_fields'].values()))
check('current_reports_supersede_pending_number2_without_rewriting_number1_answer',
      all(s in text for s in ['110 working design groups', '188 current sale options', 'one Yes', 'wYes', 'No measurements']) and
      all(s in text1 for s in ['110 working', 'Number2 was separately confirmed', '03:55:40 UTC', 'whole-library unique-design total remains unknown']) and
      'Number2 remains unanswered' not in text1 and 'Number2 unconfirmed' not in text1 and
      'Current_Working_Design_Groups_110.csv' in h.links and 'Owner_Decowaves2_Design_Equivalence_2.csv' in h.links)
physical = HTML()
physical.feed((OUT / 'physical-evidence-review.html').read_text())
pt = ' '.join(physical.text)
check('physical_checklist_retains188options752groups_and_no_new_measurement_claim',
      '188' in pt and '752' in pt and 'comparator' in pt.lower())

# Reuse only the independently authored ZIP/XML reader, not the prior checks.
helper = BASE / 'components/parallel-reviews/decowaves1-candidate-qa-20261024T040807Z/verify_decowaves1.py'
tree = ast.parse(helper.read_text())
function = next(x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name == 'read_xlsx')
N = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main', 'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
exec(compile(ast.Module(body=[function], type_ignores=[]), str(helper), 'exec'))
w0, heights0 = read_xlsx(manifest['master_workbook']['snapshot'])
w1, heights1 = read_xlsx(C / 'master-workbook.pending')
check('28_workbook_sheet_names_and_order_preserved', list(w0) == list(w1) and len(w1) == 28)
expected_w = copy.deepcopy(w0)
allowed_cells = {('Master Catalogue', c) for c in ['A3', 'V50', 'V52', 'V53', 'V54']} | \
                {('Components', c) for c in ['A3', 'E35', 'E36', 'E37', 'E38']} | \
                {('Photo Coverage', c) for c in ['L50', 'L52', 'L53', 'L54']}
value_errors = []
for item in plan['cell_changes']:
    cell = expected_w[item['sheet']][item['cell']]
    if cell['value'] != str(item['before']) or cell['formula'] is not None:
        value_errors.append((item['sheet'], item['cell']))
    cell['value'] = str(item['value'])
check('fourteen_value_edits_are_only_pair_annotations_and_current_count_labels',
      len(plan['cell_changes']) == 14 and {(i['sheet'], i['cell']) for i in plan['cell_changes']} == allowed_cells and not value_errors,
      value_errors)
oldprefix = str(BASE / 'outputs/decowaves1-owner-design-group-master-2026-10-24') + '/'
newprefix = str(OUT) + '/'
planned_links = {(x['sheet'], x['cell']): x['target'] for x in plan['hyperlinks']}
link_changes, link_errors = [], []
for sheet, cells in w0.items():
    for addr, cell in cells.items():
        before = cell.get('hyperlink')
        after = w1[sheet].get(addr, {}).get('hyperlink')
        if before == after:
            continue
        rebase = isinstance(before, str) and before.startswith(oldprefix) and after == newprefix + before[len(oldprefix):]
        new_review = (sheet, addr) == ('Master Catalogue', 'A3') and before == oldprefix + 'decowaves1-owner-design-equivalence.html' and after == newprefix + 'decowaves2-owner-design-equivalence.html'
        valid = (rebase or new_review) and planned_links.get((sheet, addr)) == after and Path(after.split('#', 1)[0]).is_file()
        link_changes.append({'sheet': sheet, 'cell': addr, 'before': before, 'after': after, 'valid': valid})
        if valid:
            expected_w[sheet][addr]['hyperlink'] = after
        else:
            link_errors.append(link_changes[-1])
check('every_changed_hyperlink_is_declared_local_release_or_number2_review',
      not link_errors and bool(link_changes), {'changed': len(link_changes), 'errors': link_errors})
check('entire_workbook_values_formulas_and_links_equal_exact_allowed_projection',
      expected_w == w1, {'unexpected_sheets': [s for s in w1 if expected_w[s] != w1[s]]})
expected_heights = copy.deepcopy(heights0)
for r in plan['row_heights']:
    expected_heights[r['sheet']][r['row']] = float(r['height'])
check('four_declared_row_height_changes_only', len(plan['row_heights']) == 4 and expected_heights == heights1)
formulas0 = {(s, a): c['formula'] for s, cells in w0.items() for a, c in cells.items() if c['formula'] is not None}
formulas1 = {(s, a): c['formula'] for s, cells in w1.items() for a, c in cells.items() if c['formula'] is not None}
links0 = {(s, a): c['hyperlink'] for s, cells in w0.items() for a, c in cells.items() if c.get('hyperlink')}
links1 = {(s, a): c['hyperlink'] for s, cells in w1.items() for a, c in cells.items() if c.get('hyperlink')}
external0 = {k: v for k, v in links0.items() if v.startswith(('https://', 'http://'))}
external1 = {k: v for k, v in links1.items() if v.startswith(('https://', 'http://'))}
check('all3407formulas12206links_and_external_native_urls_preserved',
      formulas0 == formulas1 and len(formulas1) == 3407 and len(links0) == len(links1) == 12206 and external0 == external1)
check('no_new_sheets_or_native_link_edit_plan', not plan['new_sheets'] and not plan['native_link_changes'])
check('physical_workbook_checklist_stays188_752',
      w1['Specifications']['A3'] == w0['Specifications']['A3'] and '188' in w1['Specifications']['A3']['value'] and '752' in w1['Specifications']['A3']['value'])
check('all_frozen_candidate_bytes_stable_through_readback', all(sha(p) == value for p, value in frozen.items()))

result = {
    'schema': 'boldstone.independent-decowaves2-candidate-qa.v1',
    'status': 'PASS' if all(x['passed'] for x in checks) else 'FAIL',
    'recorded_utc': datetime.now(timezone.utc).isoformat(),
    'candidate_register_sha256': REG, 'candidate_workbook_sha256': BOOK,
    'checks_passed': sum(x['passed'] for x in checks), 'checks_total': len(checks), 'checks': checks,
    'transcript_readback': reads, 'frozen_artifacts': frozen,
    'xlsx_reader_source': {'path': str(helper), 'sha256': sha(helper), 'extracted_function_only': 'read_xlsx'},
    'scope': 'Independent exact transcript, JSON object preservation, design projection, CSV/HTML and XLSX semantic comparison. No shared/native writes or new physical verification.',
}
save('local-report-link-changes.json', link_changes)
save('candidate-readback.json', result)
handoff = {
    'status': result['status'], 'recorded_utc': result['recorded_utc'],
    'candidate_register_sha256': REG, 'candidate_workbook_sha256': BOOK,
    'files': [{'path': str(OWN / n), 'sha256': sha(OWN / n)} for n in ['verify.py', 'candidate-readback.json', 'local-report-link-changes.json']],
    'shared_or_native_writes': 0,
}
save('sealed-handoff.json', handoff)
print(json.dumps({'status': result['status'], 'checks_passed': result['checks_passed'], 'checks_total': result['checks_total'],
                  'failed': [x for x in checks if not x['passed']], 'qa_path': str(OWN / 'candidate-readback.json'),
                  'qa_sha256': sha(OWN / 'candidate-readback.json'), 'seal_sha256': sha(OWN / 'sealed-handoff.json')}))
