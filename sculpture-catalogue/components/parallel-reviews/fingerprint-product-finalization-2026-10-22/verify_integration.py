"""Independent bounded checks of the master writer's Fingerprint integration."""
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone
import argparse
import hashlib
import json
import re
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path('/Users/tprice/Documents/boldstone/sculpture-catalogue')
JOB = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument('--register', required=True, type=Path)
parser.add_argument('--audit', required=True, type=Path)
parser.add_argument('--workbook', type=Path)
parser.add_argument('--output', type=Path, default=JOB / 'integration-verification.json')
args = parser.parse_args()
packet = json.loads((JOB / 'product-update-packet.json').read_text())
base = json.loads((ROOT / packet['preparation_baseline']['register']).read_text())
current = json.loads(args.register.read_text())
audit = json.loads(args.audit.read_text())
results = []

def check(label, condition, detail=None):
    results.append({'check': label, 'pass': bool(condition), **({'detail': detail} if detail is not None else {})})

old = set(packet['legacy_disposition']['product_ids'])
old_components = set(packet['legacy_disposition']['component_ids'])
expected = {x['product_id']: x for x in packet['options']}
actual = {x['product_id']: x for x in current['options']}
old_actual = {x['product_id']: x for x in base['options']}
components = {x['component_id']: x for x in current['components']}
new_component_ids = {x['component_id'] for x in packet['components']}
check('Unique current option IDs', len(actual) == len(current['options']))
check('Unique current component IDs', len(components) == len(current['components']))
check('Exactly six current Fingerprint options', {k for k, v in actual.items() if v['family'] == 'Fingerprint'} == set(expected))
check('Exactly three current Fingerprint components', {k for k, v in components.items() if v['family'] == 'Fingerprint'} == new_component_ids)
check('Superseded option IDs excluded from active register', not (old & set(actual)))
check('Superseded component IDs excluded from active register', not (old_components & set(components)))
check('Expected active option count', len(actual) == len(old_actual) - 4 + 6)
check('Expected active component count', len(components) == len(base['components']) - 2 + 3)
check('Original source assertions preserved exactly', current['original_review_specification_assertions'] == base['original_review_specification_assertions'])
history = current.get('historical_fingerprint_product_records', {})
check('All old option records preserved exactly in history', history.get('options') == [x for x in base['options'] if x['product_id'] in old])
check('All old component records preserved exactly in history', history.get('components') == [x for x in base['components'] if x['component_id'] in old_components])
base_audit = json.loads(Path(base['latest_image_coverage_audit']['path']).read_text())
check('All old photo coverage preserved exactly in history', history.get('coverage') == [x for x in base_audit['coverage'] if x['option_id'] in old])
check('All old photo actions preserved exactly in history', history.get('picture_actions') == [x for x in base_audit['missing_pictures'] if x['option_id'] in old])
source_inventory = current['latest_fingerprint_numbered_reconciliation']['numbered_folder_finish_inventory']
check('Current numbered source inventory linked to six active IDs', {x.get('canonical_option_id') for x in source_inventory} == set(expected))
check('Source inventory does not add duplicate current counts', all(x.get('canonical_count_effect') == 0 for x in source_inventory))
for pid, original in old_actual.items():
    if pid not in old:
        check('Unrelated option unchanged ' + pid, actual.get(pid) == original)
for component in base['components']:
    if component['component_id'] not in old_components:
        check('Unrelated component unchanged ' + component['component_id'], components.get(component['component_id']) == component)

for pid, proposed in expected.items():
    item = actual.get(pid, {})
    check(pid + ' identity', all(item.get(k) == proposed[k] for k in ('name', 'canonical_key', 'canonical_component_id')))
    check(pid + ' individual original photo', item.get('file_id') == proposed['original_individual_photo']['file_id'])
    check(pid + ' actual photo containing folder', item.get('folder_id') == proposed['original_image_folder']['file_id'])
    check(pid + ' original photo URL', item.get('image_url') == proposed['original_individual_photo']['url'])
    check(pid + ' actual photo containing folder URL', item.get('folder_url') == proposed['original_image_folder']['url'])
    binding = item.get('component_folder_binding', {})
    check(pid + ' separate product folder ID', binding.get('component_folder_id') == proposed['component_folder']['file_id'])
    check(pid + ' separate product folder URL', binding.get('component_folder_url') == proposed['component_folder']['url'])
    check(pid + ' no physical verification', item.get('physical_specifications_verified') is False)
    check(pid + ' six fields recorded', item.get('six_working_fields_recorded') is True and len(item.get('specifications', {})) == 6)
    check(pid + ' offered fixing choices', item.get('offered_fixing_choices') == ['Keyhole fixing', 'French cleat'])
    for label, field in proposed['specifications'].items():
        got = item.get('specifications', {}).get(label, {})
        check(pid + ' specification ' + label, got.get('display') == field['display'])
        master = item.get('master_fields', {}).get(label, {})
        check(pid + ' master field ' + label, master.get('display') == field['display'])
        check(pid + ' qualification basis ' + label, master.get('basis') == field['basis'])
    for role in ('individual', 'in_situ', 'series'):
        check(pid + ' product coverage ' + role, item.get('photo_coverage', {}).get(role) == 'Available')

for proposed in packet['components']:
    item = components.get(proposed['component_id'], {})
    check(proposed['component_id'] + ' exactly two finishes', set(item.get('option_ids', [])) == set(proposed['option_ids']) and item.get('option_count') == 2)

coverage = {x['option_id']: x for x in audit['coverage']}
check('Coverage scope equals current register', set(coverage) == set(actual) and len(coverage) == len(audit['coverage']))
for pid, proposed in expected.items():
    row = coverage.get(pid, {})
    for role in ('individual', 'in_situ', 'series'):
        check(pid + ' audit coverage ' + role, row.get(role, {}).get('status') == 'Available')
    check(pid + ' audit original identity', row.get('individual', {}).get('reference', {}).get('file_id') == proposed['original_individual_photo']['file_id'])

gaps = [x for x in audit['coverage'] if x['individual']['status'] != 'Available']
open_required = [x for x in audit['missing_pictures'] if x.get('status') == 'Open' and x.get('action_type') != 'Optional image']
check('No active old-option image actions', all(x['option_id'] not in old for x in open_required))
check('No new Fingerprint image gaps', not (set(expected) & {x['option_id'] for x in gaps}))
check('No new Fingerprint required photo actions', not (set(expected) & {x['option_id'] for x in open_required}))
check('Image status summary recalculated', dict(Counter(x['individual']['status'] for x in audit['coverage'])) == audit['counts']['individual_statuses'])
check('Required photo action total recalculated', len(open_required) == audit['counts']['required_picture_actions'])
check('Current option count in image audit', audit['counts']['individual_options'] == len(actual))
check('Current option count in summary', current['summary']['individual_named_working_options'] == len(actual))
check('Current component count in summary', current['summary']['identified_component_identities'] == len(components))
check('Current field groups in summary', current['summary']['current_field_groups'] == len(actual) * 6)

workbook_counts = None
if args.workbook:
    ns = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    rel_ns = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
    with zipfile.ZipFile(args.workbook) as z:
        strings = []
        if 'xl/sharedStrings.xml' in z.namelist():
            strings = [''.join(t.text or '' for t in x.iter('{' + ns['s'] + '}t')) for x in ET.fromstring(z.read('xl/sharedStrings.xml'))]
        rels = {x.attrib['Id']: x.attrib['Target'] for x in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
        def read_sheet(name):
            sheet = next(x for x in ET.fromstring(z.read('xl/workbook.xml')).find('s:sheets', ns) if x.get('name') == name)
            path = rels[sheet.get(rel_ns + 'id')]
            path = path.lstrip('/') if path.startswith('/') else 'xl/' + path
            doc = ET.fromstring(z.read(path))
            cells = {}
            for row in doc.findall('s:sheetData/s:row', ns):
                for cell in row:
                    value, inline = cell.find('s:v', ns), cell.find('s:is', ns)
                    cells[cell.get('r')] = (strings[int(value.text)] if cell.get('t') == 's' and value is not None else
                        ''.join(t.text or '' for t in inline.iter('{' + ns['s'] + '}t')) if inline is not None else
                        value.text if value is not None else '')
            return cells, doc
        master_cells, master_xml = read_sheet('Master Catalogue')
        spec_cells, spec_xml = read_sheet('Specifications')
        missing_cells, missing_xml = read_sheet('Missing Pictures')
        _, photo_xml = read_sheet('Photo Coverage')
        def cell_position(cell):
            m = re.fullmatch(r'\$?([A-Z]+)\$?(\d+)', cell)
            column = 0
            for char in m[1]:
                column = column * 26 + ord(char) - 64
            return column, int(m[2])
        def has_cf(doc, target, predicate):
            col, row = cell_position(target)
            for cf in doc.findall('s:conditionalFormatting', ns):
                for area in cf.get('sqref', '').split():
                    first, _, last = area.partition(':')
                    c1, r1 = cell_position(first)
                    c2, r2 = cell_position(last or first)
                    if c1 <= col <= c2 and r1 <= row <= r2 and any(predicate(rule) for rule in cf):
                        return True
            return False
        for row in (9 + len(actual) - 1, 9 + len(actual)):
            check('Appended master row warning format ' + str(row), has_cf(master_xml, 'K' + str(row), lambda rule: rule.get('type') == 'cellIs' and rule.get('operator') == 'notEqual' and rule.findtext('s:formula', namespaces=ns) == '6'))
            for col in 'CFI':
                for phrase in ('Verify', 'No verified'):
                    check('Appended photo row warning format ' + col + str(row) + ' ' + phrase, has_cf(photo_xml, col + str(row), lambda rule, phrase=phrase: rule.get('type') == 'containsText' and rule.get('text') == phrase))
        master_rows = {master_cells.get('A' + str(i)): i for i in range(10, 10000) if master_cells.get('A' + str(i))}
        check('Workbook master option IDs match register', set(master_rows) == set(actual))
        check('Workbook option summary count', master_cells.get('B4') == str(len(actual)))
        check('Workbook component summary count', master_cells.get('D4') == str(len(components)))
        check('Workbook completed field summary count', master_cells.get('F4') == str(len(actual)))
        check('Workbook Dropbox reference summary count', master_cells.get('H4') == str(sum(bool(x.get('image_url')) for x in actual.values())))
        check('Workbook find/capture count', missing_cells.get('B4') == str(sum(x.get('action_type') == 'Find / capture' for x in open_required)))
        check('Workbook verify-existing count', missing_cells.get('D4') == str(sum(x.get('action_type') == 'Verify existing image' for x in open_required)))
        spec_rows = {}
        for i in range(10, 20000):
            pid, label = spec_cells.get('A' + str(i)), spec_cells.get('C' + str(i))
            if pid:
                spec_rows.setdefault(pid, []).append((label, i))
        check('Workbook specification current IDs match register', set(spec_rows) == set(actual))
        check('Workbook exactly six fields per option', all(len(v) == 6 for v in spec_rows.values()))
        for pid, proposed in expected.items():
            row = master_rows.get(pid)
            check(pid + ' workbook master name', master_cells.get('B' + str(row)) == proposed['name'])
            check(pid + ' workbook complete working fields', master_cells.get('K' + str(row)) == '6')
            fields_in_sheet = {label: i for label, i in spec_rows.get(pid, [])}
            for col, (label, field) in zip('EFGHIJ', proposed['specifications'].items()):
                check(pid + ' workbook displayed ' + label, master_cells.get(col + str(row)) == field['display'])
                formula = master_xml.find(f"s:sheetData/s:row/s:c[@r='{col}{row}']/s:f", ns)
                check(pid + ' formula covers current specification range ' + label, formula is not None and ('$' + str(9 + len(actual) * 6)) in (formula.text or ''))
                i = fields_in_sheet.get(label)
                check(pid + ' workbook owned ' + label, spec_cells.get('D' + str(i)) == field['display'])
                check(pid + ' workbook field basis ' + label, spec_cells.get('F' + str(i)) == field['basis'])
        bad_old = []
        for i in range(10, 20000):
            if missing_cells.get('B' + str(i)) in old and missing_cells.get('N' + str(i)) == 'Open':
                bad_old.append(i)
        check('Workbook no open superseded capture rows', not bad_old, bad_old)
        error_cells = []
        for path in z.namelist():
            if path.startswith('xl/worksheets/sheet') and path.endswith('.xml'):
                doc = ET.fromstring(z.read(path))
                error_cells += [path + ':' + c.get('r', '') for c in doc.findall("s:sheetData/s:row/s:c[@t='e']", ns)]
        check('Saved workbook has no spreadsheet error cells', not error_cells, error_cells)
        workbook_counts = {'master_records': len(master_rows), 'specification_rows': sum(len(v) for v in spec_rows.values())}

receipt = {'status': 'PASS' if all(x['pass'] for x in results) else 'FAIL',
           'recorded_utc': datetime.now(timezone.utc).isoformat(),
           'register': str(args.register), 'register_sha256': hashlib.sha256(args.register.read_bytes()).hexdigest(),
           'audit': str(args.audit), 'audit_sha256': hashlib.sha256(args.audit.read_bytes()).hexdigest(),
           'checks': len(results), 'failures': [x for x in results if not x['pass']],
           'current_component_identities': len(components), 'current_options': len(actual),
           'current_working_field_groups': len(actual) * 6,
           'individual_image_gaps': len(gaps), 'required_picture_actions': len(open_required),
           'workbook': str(args.workbook) if args.workbook else None,
           'workbook_sha256': hashlib.sha256(args.workbook.read_bytes()).hexdigest() if args.workbook else None,
           'workbook_counts': workbook_counts}
args.output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(receipt, ensure_ascii=False, indent=2))
if receipt['status'] != 'PASS':
    raise SystemExit(1)
