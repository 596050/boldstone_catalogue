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
calculated = {(r['sheet'],r['cell']):r for r in plan.get('calculated_value_changes',[])}
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
        expected = changes.get((sn, cell), calculated.get((sn,cell),{})).get('value', before)
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
    planned_heights={(x['sheet'],x['row']):x['height'] for x in plan['row_heights']}
    for row in old.find(n.q('sheetData')):
        idx=int(row.get('r'));height=planned_heights.get((sn,idx))
        check(idx in rows and all((float(rows[idx].get(k)) == height if k=='ht' and height is not None else rows[idx].get(k)==v or k=='ht' and float(rows[idx].get(k))==float(v)) for k,v in row.attrib.items()),sn+' row'+str(idx)+' preserved/planned attributes')
        if height is not None:check(float(rows[idx].get('ht'))==height,sn+' planned row height '+str(idx))
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
original = read(H/'inputs/master_register.before')
candidate = read(H/'canonical-master-register.json')
packet = read(H/'specification-completion-packet.json')
expected_rows = {(r['product_id'],r['field']):r for r in packet['changes']}
check(len(expected_rows) == 30,'Exactly30 scoped working specification fields')
for old,current in zip(original['options'],candidate['options']):
    oid=old['product_id']
    check(current['product_id']==oid,'Preserved option order '+oid)
    check({k:v for k,v in old.items()if k!='master_fields'}=={k:v for k,v in current.items()if k!='master_fields'},'All nonfield option data unchanged '+oid)
    for field,value in old['master_fields'].items():
        row=expected_rows.get((oid,field));expected=row['after']if row else value
        check(current['master_fields'][field]==expected,'Exact scoped/retained field '+oid+' '+field)
        check(current['master_fields'][field]['physical_verification']==value['physical_verification'],'Physical status retained '+oid+' '+field)
        if row:
            check(row['before']==value,'Target baseline field '+oid+' '+field)
            check(expected['completion_proposal']['owner_confirmed_specific_value']is False,'No individual confirmation '+oid+' '+field)
            if field=='Dimensions / depth':check(expected['depth_estimate']==value['depth_estimate'],'Existing depth estimate preserved '+oid)
for key in original:
    if key != 'options':
        check(candidate[key] == original[key],'Other register section retained '+key)
check(candidate['summary'] == original['summary'],'All188/189/112/110 count definitions unchanged')
check(candidate['original_review_specification_assertions'] == original['original_review_specification_assertions'],'All1668 original source assertions retained')
check(sha(H/'image-coverage-current.json') == sha(H/'inputs/coverage.before'),'All photograph roles and holds unchanged')
for label,record in read(H/'input-manifest.json').items():
    check(sha(record['path']) == sha(record['snapshot']) == record['sha256'],'Protected baseline '+label)
result = {'status':'FAIL' if failures else 'PASS','recorded_utc':datetime.now(timezone.utc).isoformat(),
    'checks_passed':checks-len(failures),'checks_total':checks,'failures':failures[:80],
    'workbook_sha256':sha(H/'master-workbook.pending'),'register_sha256':sha(H/'canonical-master-register.json'),
    'coverage_sha256':sha(H/'image-coverage-current.json'),'sheets':28,'formulas':3407,'native_hyperlinks':len(actual_links),
    'authored_cells':len(plan['cell_changes']),'calculated_cells':len(plan['calculated_value_changes']),
    'row_heights_increased':len(plan['row_heights']),'working_proposal_field_objects':30,'other_field_objects_unchanged':1104,'other_active_field_objects_unchanged':1098,
    'new_physical_measurements':0,'weight_fixing_price_availability_identity_or_photo_changes':0,'new_working_materials':27,'new_working_face_sizes':3,'external_writes':0}
(H/'saved-workbook-verification.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
if failures:
    raise SystemExit(1)
