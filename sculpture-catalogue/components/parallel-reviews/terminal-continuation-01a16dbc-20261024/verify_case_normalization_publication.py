"""Independent offline readback of the bounded URL-capitalization publication."""
import argparse
import hashlib
import json
import posixpath
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[2]
LANE = HERE / 'case-normalization-handoff-20261024T165515Z'
read = lambda path: json.loads(Path(path).read_text())
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
digest = lambda value: hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
N = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
ID = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'

def workbook_cells(path):
    result = {}
    with ZipFile(path) as book:
        shared = [''.join(s.itertext()) for s in ET.fromstring(book.read('xl/sharedStrings.xml'))] if 'xl/sharedStrings.xml' in book.namelist() else []
        rels = {r.attrib['Id']: r.attrib['Target'] for r in ET.fromstring(book.read('xl/_rels/workbook.xml.rels'))}
        for sheet in ET.fromstring(book.read('xl/workbook.xml')).findall('s:sheets/s:sheet', N):
            name = sheet.attrib['name']
            target = rels[sheet.attrib[ID + 'id']]
            part = target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/' + target)
            tree = ET.fromstring(book.read(part))
            for c in tree.findall('s:sheetData/s:row/s:c', N):
                ref = c.attrib['r']
                v = c.find('s:v', N)
                value = ''
                if c.attrib.get('t') == 's' and v is not None:
                    value = shared[int(v.text)]
                elif c.attrib.get('t') == 'inlineStr':
                    value = ''.join(c.find('s:is', N).itertext())
                elif v is not None:
                    value = v.text or ''
                result[(name, ref, 'value')] = value
                f = c.find('s:f', N)
                if f is not None:
                    result[(name, ref, 'formula')] = f.text or ''
            relpart = posixpath.dirname(part) + '/_rels/' + posixpath.basename(part) + '.rels'
            links = {r.attrib['Id']: r.attrib.get('Target', '') for r in ET.fromstring(book.read(relpart))} if relpart in book.namelist() else {}
            for link in tree.findall('s:hyperlinks/s:hyperlink', N):
                result[(name, link.attrib['ref'], 'hyperlink_target')] = links.get(link.attrib.get(ID + 'id'), '')
    return result

PROTECTED_FIELDS = ['product_id', 'canonical_component_id', 'canonical_design_id', 'family', 'name',
    'record_type', 'sale_unit', 'specifications', 'master_fields', 'physical_specifications_verified',
    'six_working_fields_recorded', 'counted_as_individual_option', 'file_id', 'folder_id',
    'context_file_id', 'context_folder_id', 'context_status', 'context_description', 'photo_coverage',
    'selling_details', 'identity_basis', 'option_family_id', 'current_commercial_policy',
    'offered_fixing_choices', 'size_class', 'build_class']
HISTORICAL = ['original_review_specification_assertions', 'source_only_assertions_not_applied_to_options',
              'source_component_dispositions', 'aliases', 'source_sets']

def protected_options(register):
    return {r['product_id']: digest({k: r.get(k) for k in PROTECTED_FIELDS}) for r in register['options']}

parser = argparse.ArgumentParser()
parser.add_argument('--snapshot', action='store_true')
args = parser.parse_args()
packet = read(LANE / 'handoff.json')
pointer_path = BASE / 'current-master.json'
pointer = read(pointer_path)
register_path = BASE / pointer['register']
workbook_path = BASE / pointer['workbook']
assert sha(register_path) == pointer['register_sha256']
assert sha(workbook_path) == pointer['workbook_sha256']
register = read(register_path)
snapshot_path = LANE / 'publication-readback-baseline.json'
if args.snapshot:
    assert not snapshot_path.exists()
    assert pointer['register_sha256'] == packet['register_sha256']
    assert pointer['workbook_sha256'] == packet['workbook_sha256']
    inventory = read(LANE / 'projection-column-classification.json')['workbook_occurrences']
    cells = workbook_cells(workbook_path)
    baseline = {'status': 'FROZEN_OFFLINE_BEFORE_PUBLICATION', 'recorded_utc': datetime.now(timezone.utc).isoformat(),
        'pointer_sha256': sha(pointer_path), 'register_sha256': sha(register_path), 'workbook_sha256': sha(workbook_path),
        'options': protected_options(register), 'historical_objects': {k: digest(register.get(k)) for k in HISTORICAL},
        'working_design_groups': pointer['current_working_design_group_projection']['grouped_working_design_identity_count'],
        'active_options': pointer['current_option_count'], 'retained_options': len(register['options']),
        'cells': [{**r, 'before_full_text': cells[(r['sheet'], r['cell'], r['kind'])]} for r in inventory]}
    snapshot_path.write_text(json.dumps(baseline, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'status': baseline['status'], 'cells': len(baseline['cells']), 'options': len(baseline['options']), 'sha256': sha(snapshot_path)}))
    raise SystemExit(0)

baseline = read(snapshot_path)
options = {r['product_id']: r for r in register['options']}
pending = []
for row in packet['rows']:
    for field in ('image_url', 'folder_url'):
        if options[row['option_id']][field] != row['proposed'][field]:
            pending.append({'option_id': row['option_id'], 'field': field})
if pending:
    print(json.dumps({'status': 'AWAITING_SOLE_PUBLISHER', 'URL_fields_not_yet_published': len(pending),
        'current_pointer_sha256': sha(pointer_path), 'current_register_sha256': sha(register_path)}))
    raise SystemExit(0)

assert protected_options(register) == baseline['options'], 'Protected option evidence changed'
assert {k: digest(register.get(k)) for k in HISTORICAL} == {k: baseline['historical_objects'][k] for k in HISTORICAL}, 'Historical objects changed'
# The separately approved Moonwave moves may refresh a source offer's current
# reference. Compare captured source objects and original BOMs independently.
assert sha(Path(packet['register'])) == packet['register_sha256']
before_register = read(Path(packet['register']))
allowed_option_urls = {row['option_id']: row['proposed'] for row in packet['rows']}
assert len(before_register['options']) == len(register['options']) == 189
for before, after in zip(before_register['options'], register['options']):
    expected = dict(before)
    if before['product_id'] in allowed_option_urls:
        expected.update(allowed_option_urls[before['product_id']])
    assert after == expected, ('Retained option changed outside the twelve approved URL fields', before['product_id'])
before_offers, after_offers = before_register['source_offer_edges'], register['source_offer_edges']
assert [e['offer_ref'] for e in before_offers] == [e['offer_ref'] for e in after_offers]
captured_members = 0
for before, after in zip(before_offers, after_offers):
    for key in ('source_offer', 'individual_count_increment'):
        assert before[key] == after[key], ('Captured source offer changed', before['offer_ref'], key)
    assert len(before['members']) == len(after['members'])
    for old_member, new_member in zip(before['members'], after['members']):
        assert all(new_member.get(key) == value for key, value in old_member.items()), ('Original BOM or member changed', before['offer_ref'])
        captured_members += 1
coverage_before = before_register['source_media_configuration_coverage'][163]
coverage_after = register['source_media_configuration_coverage'][163]
assert all(coverage_after.get(key) == value for key, value in coverage_before.items()), 'Captured Moonwave coverage fields changed'
moonwave_lane = BASE.parent / 'reports/dropbox-moonwave-ten-approved-moves-20261024T182423Z'
moonwave_seal = read(moonwave_lane / 'execution-seal.json')
assert moonwave_seal['status'] == 'COMPLETE_VERIFIED'
for sealed in moonwave_seal['receipts']:
    assert sha(Path(sealed['path'])) == sealed['sha256']
native_moonwave = {row['file_id']: row for row in read(moonwave_lane / 'all-current-moonwave-image-folder-links.json')}
own_source_id, own_coverage_id = 'id:cnqzTNngPVsAAAAAAArp1g', 'id:cnqzTNngPVsAAAAAAArp2Q'
source_edge = next(edge for edge in after_offers if edge.get('current_primary_reference', {}).get('file_id') == own_source_id)
assert source_edge['offer_ref'] == 'O016'
moonwave_bindings = [source_edge['current_primary_reference'], coverage_after['current_example_reference_navigation'][own_coverage_id]]
for reference, expected_id in zip(moonwave_bindings, [own_source_id, own_coverage_id]):
    assert reference['file_id'] == expected_id
    for field in ['folder_id', 'image_url', 'folder_url']:
        assert reference[field] == native_moonwave[expected_id][field], ('Moonwave own-file navigation differs', expected_id, field)
assert pointer['current_option_count'] == baseline['active_options'] == 188
assert len(register['options']) == baseline['retained_options'] == 189
assert pointer['current_working_design_group_projection']['grouped_working_design_identity_count'] == baseline['working_design_groups'] == 110
cells = workbook_cells(workbook_path)
failed, protected, current, other_source = [], 0, 0, 0
mapping = {row['expected_before']: row['value'] for row in packet['guarded_replacements']}
current_cells, other_source_cells = set(), set()
for row in baseline['cells']:
    expected = row['before_full_text']
    historical = row['header'].startswith('Historical ')
    if historical:
        protected += 1
    elif expected in mapping:
        current += 1
        current_cells.add((row['sheet'], row['cell'], row['kind']))
        expected = mapping[expected]
    else:
        # An image URL for another source photograph can contain a corrected
        # folder URL as a prefix. It is outside the six exact-ID URL guards.
        other_source += 1
        other_source_cells.add((row['sheet'], row['cell'], row['kind']))
    actual = cells.get((row['sheet'], row['cell'], row['kind']))
    if actual != expected:
        failed.append({k: row[k] for k in ['sheet', 'cell', 'kind', 'header', 'option_id']})
assert not failed, json.dumps({'workbook_mismatches': failed[:30], 'total': len(failed)})
assert protected == 12 and current + other_source == 353
controls = ['components/checkpoint.json', 'checkpoint.json', 'components/reviews/specification_review_progress.json']
assert all(read(BASE / f)['current_master_catalogue'] == pointer for f in controls)
receipt = read(BASE / pointer['publication_receipt'])
assert receipt['status'].startswith('PASS')
assert read(pointer_path) == pointer, 'Pointer changed during readback'
assert sha(workbook_path) == pointer['workbook_sha256']
result = {'status': 'PASS_INDEPENDENT_CASE_NORMALIZATION_PUBLICATION_READBACK',
    'recorded_utc': datetime.now(timezone.utc).isoformat(), 'pointer_sha256': sha(pointer_path),
    'register_sha256': sha(register_path), 'workbook_sha256': sha(workbook_path),
    'baseline_sha256': sha(snapshot_path), 'six_option_URL_fields': 12,
    'verifier_sha256': sha(Path(__file__)), 'exact_retained_option_objects_compared': 189,
    'current_workbook_occurrences_verified': current, 'historical_workbook_occurrences_preserved': protected,
    'current_workbook_distinct_hyperlink_cells_verified': len(current_cells),
    'other_source_prefix_only_occurrences_preserved': other_source,
    'other_source_prefix_only_distinct_cells_preserved': len(other_source_cells),
    'scope_refinement': 'Only exact approved full URLs are replacement targets. Seven references to the distinct Leaf Curve001 source photograph matched only a folder prefix and are correctly preserved, not replaced by selected080.',
    'protected_retained_option_objects': len(baseline['options']), 'unchanged_historical_object_groups': len(HISTORICAL),
    'captured_source_offers_preserved': len(before_offers), 'original_BOM_members_preserved': captured_members,
    'Moonwave_captured_coverage_163_fields_preserved': len(coverage_before),
    'Moonwave_source_offer_O016_own_file_and_parent_verified': True,
    'Moonwave_coverage_163_own_file_and_parent_verified': True,
    'Moonwave_execution_seal_sha256': sha(moonwave_lane / 'execution-seal.json'),
    'separately_approved_Moonwave_current_reference_changes': 'Allowed outside the six URL fields; captured source offers and original BOMs compared independently',
    'current_controls': 3, 'active_options': 188, 'retained_options': 189, 'working_design_groups': 110,
    'new_live_reads': 0, 'shared_or_native_writes_by_verifier': 0}
output = LANE / ('publication-readback-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '.json')
assert not output.exists()
output.write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({**result, 'output': str(output)}, indent=2))
