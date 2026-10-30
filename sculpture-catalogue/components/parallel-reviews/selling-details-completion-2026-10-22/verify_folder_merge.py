import hashlib
import json
import posixpath
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

BASE = Path(__file__).resolve().parents[3]
JOB = BASE / 'components/reconciliation/moonphases-dune-ripple-master-refresh-2026-10-22'
OUT = Path(__file__).resolve().parent
N = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
R = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
checks = 0

def check(ok, label):
    global checks
    checks += 1
    if not ok:
        raise AssertionError(label)

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def read(p):
    return json.loads(p.read_text())

regpath = JOB / 'canonical-master-register.json'
before = read(JOB / 'inputs/master_register.before')
after = read(regpath)
check(sha(regpath) == '9b92c621f3725571517b2009b4776db36f6b3cb3f881850662d59e977d2768a2', 'prepared register identity')
b = {o['product_id']: o for o in before['options']}
a = {o['product_id']: o for o in after['options']}
check(set(b) == set(a) and len(a) == 186, '186 stable option IDs')
check(len(after['components']) == 112, '112 components')
check(before['summary'] == after['summary'], 'all counts unchanged')
check(before['original_review_specification_assertions'] == after['original_review_specification_assertions'], 'original assertions retained')
for pid in a:
    for field in b[pid]['specifications']:
        check(b[pid]['specifications'][field]['display'] == a[pid]['specifications'][field]['display'], f'{pid} {field} specification')
        check(b[pid]['master_fields'][field]['display'] == a[pid]['master_fields'][field]['display'], f'{pid} {field} current display')
        check(b[pid]['master_fields'][field]['physical_verification'] == a[pid]['master_fields'][field]['physical_verification'], f'{pid} {field} physical flag')
    check(b[pid]['physical_specifications_verified'] == a[pid]['physical_specifications_verified'], f'{pid} physical status')
    if b[pid]['name'] != a[pid]['name']:
        check(a[pid]['family'] == 'Dune Ripple', 'only Dune current names changed')
for key in ['source_sets', 'source_offer_edges']:
    check(len(before[key]) == len(after[key]), key + ' count')
    for old, new in zip(before[key], after[key]):
        for k in set(old) | set(new):
            if old.get(k) != new.get(k):
                check(k == 'current_primary_reference', key + ' only current reference changes')
                for stable in ['file_id', 'folder_id']:
                    check(old[k].get(stable) == new[k].get(stable), key + ' stable native ID')
refresh = after['latest_moonphases_dune_ripple_refresh']
check(refresh['folder_renames'] == 35 and refresh['current_option_display_names_changed'] == 13, 'folder and Dune changes')
for overlay in refresh['overlays']:
    check(sha(Path(overlay['path'])) == overlay['sha256'], 'sealed current overlay')
fp = after['latest_fingerprint_working_specification_confirmation']
check(fp['field_groups'] == 36 and fp['physical_verification_added'] is False and fp['display_changes'] == 0, 'Fingerprint explicit working approval')
check(sha(Path(fp['path'])) == fp['sha256'], 'owner Fingerprint ledger identity')
audit = read(JOB / 'image-coverage-current.json')
check(audit['counts']['individual_statuses'] == {'Available': 164, 'Detail only': 5, 'Unbound identity': 1, 'Group only': 16}, 'individual coverage preserved')
check(audit['counts']['in_situ_statuses']['No verified image'] == 61, '61 in situ gaps')
check(audit['counts']['series_statuses']['No verified image'] == 18, '18 series gaps')
check(after['current_individual_photo_capture_policy']['cropped_photos_created'] == 0, 'no crops')

book = JOB / 'master-workbook.pending'
plan = read(JOB / 'workbook-edit-plan.json')
expected = read(JOB / 'expected-edit.json')
with ZipFile(book) as z:
    shared = []
    if 'xl/sharedStrings.xml' in z.namelist():
        shared = [''.join(e.itertext()) for e in ET.fromstring(z.read('xl/sharedStrings.xml'))]
    wb = ET.fromstring(z.read('xl/workbook.xml'))
    rels = {e.get('Id'): e.get('Target') for e in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
    sheets = {}
    links = {}
    formula_count = 0
    for se in wb.find('s:sheets', N):
        target = rels[se.get(R + 'id')]
        path = target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/' + target)
        xml = ET.fromstring(z.read(path))
        values = {}
        for c in xml.findall('.//s:sheetData/s:row/s:c', N):
            typ = c.get('t')
            v = c.find('s:v', N)
            text = v.text if v is not None and v.text is not None else ''
            if typ == 's': text = shared[int(text)]
            elif typ == 'inlineStr': text = ''.join(c.find('s:is', N).itertext())
            check(typ != 'e', se.get('name') + ' no Excel error ' + c.get('r'))
            f = c.find('s:f', N)
            if f is not None: formula_count += 1
            values[c.get('r')] = {'value': text, 'formula': f.text if f is not None else None}
        sheets[se.get('name')] = values
        relpath = posixpath.join(posixpath.dirname(path), '_rels', posixpath.basename(path) + '.rels')
        sr = {e.get('Id'):e.get('Target') for e in ET.fromstring(z.read(relpath))} if relpath in z.namelist() else {}
        for h in xml.findall('s:hyperlinks/s:hyperlink', N):
            target = sr.get(h.get(R+'id')) or ('#' + h.get('location', ''))
            links[(se.get('name'), h.get('ref'))] = target
    check(len(sheets) == 27 and formula_count == 2794, 'native sheet/formula totals')
    for change in plan['cell_changes']:
        actual = sheets[change['sheet']].get(change['cell'], {}).get('value', '')
        check(str(change['value']) == actual, f"changed cell {change['sheet']} {change['cell']}")
    for h in expected['hyperlinks']:
        check(links.get((h['sheet'], h['cell'])) == h['target'], f"native hyperlink {h['sheet']} {h['cell']}")
    check(len(links) == 11495, '11495 native hyperlinks')
    for f in expected['formulas']:
        c = sheets[f['sheet']][f['cell']]
        check('=' + c['formula'] == f['formula'] and float(c['value']) == f['expected'], 'new reference counters')

receipt = {'status': 'PASS', 'scope': 'Independent saved JSON and native XLSX readback; no remote writes or physical certification', 'checks': checks, 'register': str(regpath), 'register_sha256': sha(regpath), 'prepared_workbook': str(book), 'prepared_workbook_sha256': sha(book), 'option_ids_preserved': 186, 'component_count': 112, 'specification_displays_unchanged': 1116, 'current_master_displays_unchanged': 1116, 'folder_renames': 35, 'Dune_option_names_updated': 13, 'Fingerprint_explicit_working_approvals': 36, 'individual_photo_needs': 21, 'deferred_identity': 1, 'in_situ_gaps': 61, 'series_gaps': 18, 'native_links_checked': len(links), 'native_formulas': formula_count}
(OUT / 'prepared-folder-merge-verification.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps(receipt, indent=2))
