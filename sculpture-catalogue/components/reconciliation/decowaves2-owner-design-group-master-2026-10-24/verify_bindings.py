"""Independently compare the candidate's exact meaning to its frozen sources."""
import copy
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

H = Path(__file__).resolve().parent
B = H.parents[2]
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
m = read(H / 'input-manifest.json')
old = read(m['master_register']['snapshot'])
g = read(H / 'canonical-master-register.json')
edge = read(H / 'owner-design-edge.json')
projection = read(H / 'working-design-group-projection.json')
pair = {'BSI-FE830AE502C3', 'BSI-837E9B0B3B36'}
issues, checks = [], 0
def check(ok, message):
    global checks
    checks += 1
    if not ok:
        issues.append(message)

check(set(edge['owner_confirmed_option_ids']) == pair, 'Number2 applies to exactly the presented pair')
check(edge['owner_answer_verbatim'] == 'wYes' and edge['normalized_answer'] == 'Yes', 'Original answer and explicit interpretation retained')
check(g['current_owner_design_equivalence_edges'][:-1] == old['current_owner_design_equivalence_edges'], 'Number1 original edge unchanged')
check(g['current_owner_design_equivalence_edges'][-1] == edge and len(g['current_owner_design_equivalence_edges']) == 2, 'One new edge after duplicate-answer deduplication')
restored = copy.deepcopy(g)
for edit in read(H / 'authorized-current-field-changes.json'):
    obj = restored
    for key in edit['path'][:-1]:
        obj = obj[key]
    key = edit['path'][-1]
    check(obj[key] == edit['current'], 'Declared current change ' + str(edit['path']))
    if edit['before_exists']:
        obj[key] = edit['before']
    else:
        del obj[key]
check(restored == old, 'Every register difference declared and reversible to exact baseline')
for option, prior in zip(g['options'], old['options']):
    restored_option = copy.deepcopy(option)
    if option['product_id'] in pair:
        restored_option.pop('current_owner_design_equivalence')
    check(restored_option == prior, 'Entire existing option retained ' + option['product_id'])
    for key in ['master_fields', 'specifications', 'selling_details', 'file_id', 'folder_id', 'canonical_component_id', 'canonical_design_id', 'photo_coverage']:
        check(option.get(key) == prior.get(key), 'Field, identity or photograph scope retained ' + option['product_id'] + ' ' + key)
for component, prior in zip(g['components'], old['components']):
    restored_component = copy.deepcopy(component)
    if component['component_id'] in edge['component_ids']:
        restored_component.pop('current_owner_design_group')
        restored_component['scope_note'] = prior['scope_note']
    check(restored_component == prior, 'Retained component record ' + component['component_id'])
for key in ['source_sets', 'source_offer_edges', 'aliases', 'original_review_specification_assertions', 'wall_circle_native_options', 'listing_resolution_native_action_drafts', 'current_authenticated_squarespace_inventory_observation', 'current_global_context_owner_hold', 'current_frozen_fish_size_policy', 'wall_sculpture_customisation_policy', 'current_primary_navigation_health']:
    check(g[key] == old[key], 'Source or policy unchanged ' + key)
check(len(g['options']) == 189 and len(g['active_option_ids']) == 188 and len(g['components']) == 112, '188 active options,189 retained rows and112 component records')
check(len(projection['groups']) == 110 and projection['grouped_working_design_identity_count'] == 110, '110 working design groups')
flat = [cid for group in projection['groups'] for cid in group['retained_component_ids']]
check(len(flat) == len(set(flat)) == 112 and set(flat) == {c['component_id'] for c in g['components']}, 'All112 component IDs appear exactly once')
multiple = [group for group in projection['groups'] if len(group['retained_component_ids']) > 1]
check({frozenset(x['retained_component_ids']) for x in multiple} == {frozenset(['BC-DECO-1', 'BC-FDW-1']), frozenset(['BC-DECO-2', 'BC-FDW-2'])}, 'Only the two separately confirmed equivalences are grouped')
newgroup = next(x for x in multiple if x['working_design_group_id'] == 'BC-DECO-2')
check(set(newgroup['owner_directly_confirmed_option_ids']) == pair, 'Terracotta has no new direct photograph acceptance')
check(projection['whole_library_unique_design_count'] is None and not edge['terracotta_owner_photo_approval'], 'No physical or whole-library total inferred')
for key in ['audit', 'native_map', 'report_assets', 'report_reviews', 'photo_source', 'review_state', 'pending', 'physical_audit', 'originals']:
    check(sha(H / Path(m[key]['path']).name) == m[key]['sha256'], 'Exact existing source coverage retained ' + key)
evidence = read(H / 'transcript-evidence.json')
with Path(evidence['source_path']).open('rb') as f:
    metadata = json.loads(f.readline())
    check(metadata['payload']['id'] == evidence['source_thread_id'], 'Authoritative transcript session identity')
    for row in evidence['records']:
        f.seek(row['byte_offset'])
        raw = f.read(row['byte_length'])
        check(hashlib.sha256(raw).hexdigest() == row['raw_line_sha256'] and json.loads(raw) == row['source_record'], 'Exact transcript bytes ' + row['kind'] + ' ' + row['timestamp'])
check(len(evidence['records']) == 3 and evidence['records'][1]['source_record']['payload']['role'] == 'user', 'Question plus two actual owner messages')
live = read(H / 'live-pair-metadata.json')
observations = {r['requested_id']: r['response']['structuredContent'] for r in live['observations']}
check(len(observations) == 4 and live['namespace_id'] == '202238505', 'Read-only metadata scope comprises four existing IDs')
for option in edge['exact_pair_references']:
    file = observations[option['file_id']]['file']
    folder = observations[option['folder_id']]['folder']
    check(file['id'] == option['file_id'] and folder['id'] == option['folder_id'], 'Live exact stable IDs ' + option['product_id'])
    check(Path(file['path_display']).parent.as_posix() == folder['path_display'], 'Live containing folder ' + option['product_id'])
    url = urlsplit(option['folder_url'])
    check(unquote(url.path.removeprefix('/home')) == folder['path_display'], 'Current folder link ' + option['product_id'])
    check(parse_qs(urlsplit(option['image_url']).query)['preview'][0] == file['name'], 'Current preview filename ' + option['product_id'])
out = Path(read(H / 'report-verification.json')['output_directory'])
with (out / 'Current_Working_Design_Groups_110.csv').open(encoding='utf-8-sig', newline='') as f:
    rows = list(csv.DictReader(f))
check(len(rows) == len({r['working_design_group_id'] for r in rows}) == 110, '110 exported working groups')
with (out / 'Current_Individual_Options_188.csv').open(encoding='utf-8-sig', newline='') as f:
    reader = csv.DictReader(f)
    headers, rows = reader.fieldnames, list(reader)
check(len(headers) == len(set(headers)) and len(rows) == 188, '188 option rows and no duplicated CSV columns')
all_confirmed = set().union(*(set(x['owner_confirmed_option_ids']) for x in g['current_owner_design_equivalence_edges']))
check({r['option_id'] for r in rows if r['owner_confirmed_design_equivalence_edge']} == all_confirmed, 'Exactly four directly confirmed finish references across two pairs')
physical = read(H / 'physical-source-audit.json')['summary']
check(physical['active_options_reviewed'] == 188 and physical['physical_field_groups_reviewed'] == 752 and physical['new_independent_physical_source_assertions'] == 0, 'Physical ledger and all estimate qualifications retained')
for key, source in m.items():
    check(sha(source['path']) == sha(source['snapshot']) == source['sha256'], 'Frozen current source ' + key)
for path, info in read(H / 'evidence-manifest.json').items():
    check(sha(path) == info['sha256'], 'Exact authority evidence ' + path)
result = {'status': 'FAIL' if issues else 'PASS', 'recorded_utc': datetime.now(timezone.utc).isoformat(), 'checks': checks, 'issues': issues,
          'workbook_sha256': sha(H / 'master-workbook.pending'), 'register_sha256': sha(H / 'canonical-master-register.json'),
          'audit_sha256': sha(H / 'image-coverage-current.json'), 'retained_component_id_records': 112, 'working_design_groups': 110,
          'active_options': 188, 'new_native_or_platform_writes': 0, 'new_physical_verifications': 0,
          'independence': 'Separate semantic reader and frozen-byte comparisons in this session; no second agent or reviewer claimed.'}
(H / 'native-binding-verification.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({k: result[k] for k in ['status', 'checks', 'issues', 'working_design_groups']}))
assert not issues
