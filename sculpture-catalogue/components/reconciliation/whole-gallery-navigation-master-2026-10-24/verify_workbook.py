"""Restore unsupported native links, then verify every saved workbook cell."""
import copy
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import posixpath
import sys
from pathlib import Path
from xml.etree import ElementTree as E

H = Path(__file__).resolve().parent
B = H.parents[2]
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
s = importlib.util.spec_from_file_location('native', B / 'components/reconciliation/image-identity-coverage-2026-10-20/verify_edit.py')
n = importlib.util.module_from_spec(s)
s.loader.exec_module(n)
n.HERE = H
if '--attach' in sys.argv:
    assert not (H / 'native-attachment.json').exists(), 'Already attached to this export'
    before = sha(H / 'master-workbook.pending')
    restored = n.attach()
    (H / 'native-attachment.json').write_text(json.dumps({'before_sha256': before, 'after_sha256': sha(H / 'master-workbook.pending'),
        'original_differential_formats_restored': restored, 'cell_value_or_formula_authoring_performed': False}, indent=2)+'\n')
a = n.load(H / 'master-workbook.pending')
b = n.load(H / 'inputs/master_workbook.before')
plan = read(H / 'workbook-edit-plan.json')
changes = {(r['sheet'], r['cell']): r for r in plan['cell_changes']}
failures = []
checks = 0
def check(value, name):
    global checks
    checks += 1
    if not value:
        failures.append(name)

def native_tables(book, info):
    rel = posixpath.join(posixpath.dirname(info['part']), '_rels', posixpath.basename(info['part'])+'.rels')
    rels = {r.get('Id'): r.get('Target') for r in E.fromstring(book['files'][rel])}
    result = []
    for node in info['root'].iter(n.q('tablePart')):
        target = rels[node.get('{'+n.R+'}id')]
        part = target.lstrip('/') if target.startswith('/') else posixpath.normpath(posixpath.dirname(info['part'])+'/'+target)
        result.append(E.tostring(E.fromstring(book['files'][part])))
    return result

check(list(a['sheets']) == list(b['sheets']) and len(a['sheets']) == 28, 'All28 original tabs retained in order')
for sn, info in b['sheets'].items():
    check(a['formulas'][sn] == b['formulas'][sn], sn+' all original formulas unchanged')
    for cell, before in b['values'][sn].items():
        expected = changes.get((sn, cell), {}).get('value', before)
        check(a['values'][sn].get(cell, '') == expected, sn+'!'+cell+' original value or exact planned edit')
        check(a['styles'][sn].get(cell, '0') == b['styles'][sn][cell], sn+'!'+cell+' original cell style')
    for cell, value in a['values'][sn].items():
        if cell not in b['values'][sn]:
            check(value == '' or (sn, cell) in changes, sn+'!'+cell+' no unplanned nonblank cell')
    old = info['root']
    current = a['sheets'][sn]['root']
    for tag in ['sheetViews', 'sheetFormatPr', 'cols', 'mergeCells', 'dataValidations', 'pageMargins', 'pageSetup', 'sheetProtection', 'conditionalFormatting']:
        check([E.tostring(x) for x in old.findall(n.q(tag))] == [E.tostring(x) for x in current.findall(n.q(tag))], sn+' original '+tag)
    check(native_tables(a, a['sheets'][sn]) == native_tables(b, info), sn+' original tables and filters')
    rows = {int(r.get('r')): r for r in current.find(n.q('sheetData'))}
    for row in old.find(n.q('sheetData')):
        idx = int(row.get('r'))
        check(idx in rows and all(rows[idx].get(k) == v or k == 'ht' and float(rows[idx].get(k)) == float(v) for k, v in row.attrib.items()), sn+' row'+str(idx)+' original height/attributes')
for group in ['fonts', 'fills', 'borders', 'cellStyleXfs', 'cellXfs', 'numFmts', 'dxfs']:
    old = b['style_root'].find(n.q(group))
    current = a['style_root'].find(n.q(group))
    check(old is None or current is not None and len(current) >= len(old) and all(E.tostring(x) == E.tostring(y) for x, y in zip(old, current)), 'Original style definitions '+group)
actual_links = {}
for sn, info in a['sheets'].items():
    rel = posixpath.join(posixpath.dirname(info['part']), '_rels', posixpath.basename(info['part'])+'.rels')
    rels = {r.get('Id'): r.get('Target') for r in E.fromstring(a['files'][rel])}
    for node in info['root'].iter(n.q('hyperlink')):
        actual_links[(sn, node.get('ref'))] = '#'+node.get('location') if node.get('location') else rels[node.get('{'+n.R+'}id')]
expected_links = {(r['sheet'], r['cell']): r for r in plan['hyperlinks']}
check(set(actual_links) == set(expected_links), 'All12206 native hyperlink cell positions preserved')
for key, value in expected_links.items():
    check(actual_links.get(key) == value['target'], 'Planned native hyperlink target '+str(key))
    check(a['values'][key[0]].get(key[1], '') == value['label'], 'Planned native hyperlink label '+str(key))
for row in plan['summary_expected']:
    check(a['values'][row['sheet']][row['cell']] == row['value'], 'Preserved summary '+row['sheet']+'!'+row['cell'])
check(sum(map(len, a['formulas'].values())) == sum(map(len, b['formulas'].values())) == plan['expected_formula_count'], 'All original formula text/count retained')
original = read(H / 'inputs/master_register.before')
candidate = read(H / 'canonical-master-register.json')
for before, current in zip(original['options'], candidate['options']):
    check(before['product_id'] == current['product_id'], 'Original option position '+before['product_id'])
    for key in ['name', 'canonical_component_id', 'master_fields', 'specifications', 'selling_details', 'photo_coverage']:
        check(before[key] == current[key], 'Preserved '+key+' '+before['product_id'])
check(candidate['summary'] == original['summary'], 'All188 active/189 retained/112 components/110 groups unchanged')
check(candidate['original_review_specification_assertions'] == original['original_review_specification_assertions'], 'All1668 original source assertions unchanged')
audit = read(H / 'image-coverage-current.json')
check(audit['counts'] == read(H / 'inputs/coverage.before')['counts'], 'Every image-coverage count and owner deferral unchanged')
for label, record in read(H / 'input-manifest.json').items():
    check(sha(record['path']) == sha(record['snapshot']) == record['sha256'], 'Protected live/frozen baseline '+label)
result = {'status': 'FAIL' if failures else 'PASS', 'recorded_utc': datetime.now(timezone.utc).isoformat(),
    'checks_passed': checks-len(failures), 'checks_total': checks, 'failures': failures[:100],
    'workbook_sha256': sha(H / 'master-workbook.pending'), 'register_sha256': sha(H / 'canonical-master-register.json'),
    'audit_sha256': sha(H / 'image-coverage-current.json'), 'sheets': len(a['sheets']),
    'formulas': sum(map(len, a['formulas'].values())), 'native_hyperlinks': len(actual_links),
    'planned_value_changes': len(changes), 'planned_link_target_changes': len(plan['native_link_changes']),
    'actual_physical_or_commercial_field_changes': 0, 'canonical_or_platform_writes': 0}
(H / 'saved-workbook-verification.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(result, indent=2))
if failures:
    raise SystemExit(1)
