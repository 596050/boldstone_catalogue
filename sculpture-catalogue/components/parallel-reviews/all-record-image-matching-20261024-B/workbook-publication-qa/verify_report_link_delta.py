"""Verify the final report-link-only change against the independently checked book."""
from pathlib import Path
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import unquote, urlsplit
import argparse, hashlib, json, posixpath, zipfile
import xml.etree.ElementTree as ET

Q = Path(__file__).resolve().parent
C = Q.parents[2] / 'reconciliation/whole-gallery-navigation-master-2026-10-24'
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
a = argparse.ArgumentParser()
a.add_argument('--workbook-sha256', required=True)
a.add_argument('--plan-sha256', required=True)
args = a.parse_args()
candidate = C / 'master-workbook.pending'
plan_path = C / 'workbook-edit-plan.json'
assert sha(candidate) == args.workbook_sha256
assert sha(plan_path) == args.plan_sha256
previous = Q / 'final/immutable-input-snapshots/4d78ad-workbook.pending'
assert sha(previous) == '4d78ad49271f02efc1ae0331e79509169aa41b972533fbae650d0f1cdb3e6bf5'
snapshots = read(Q / 'final/immutable-input-snapshots.json')
for item in snapshots['files']:
    assert sha(item['snapshot_path']) == item['verified_sha256']
old_plan_path = next(Path(x['snapshot_path']) for x in snapshots['files'] if x['original_path'].endswith('/workbook-edit-plan.json'))
old_plan, plan = read(old_plan_path), read(plan_path)
assert old_plan['cell_changes'] == plan['cell_changes'] and len(plan['cell_changes']) == 44
assert len(plan['native_link_changes']) == 225
old_links = {(x['sheet'], x['cell']): x['target'] for x in old_plan['hyperlinks']}
new_links = {(x['sheet'], x['cell']): x['target'] for x in plan['hyperlinks']}
assert set(old_links) == set(new_links) and len(new_links) == 12206
expected = {k: {'before': old_links[k], 'target': v} for k, v in new_links.items() if old_links[k] != v}
assert len(expected) == 69
old_prefix = '/outputs/current-six-url-case-navigation-master-2026-10-24/'
new_prefix = '/outputs/whole-gallery-navigation-master-2026-10-24/'
for row in expected.values():
    assert row['before'].replace(old_prefix, new_prefix) == row['target']

z1, z2 = zipfile.ZipFile(previous), zipfile.ZipFile(candidate)
assert set(z1.namelist()) == set(z2.namelist())
changed_parts = [n for n in z1.namelist() if z1.read(n) != z2.read(n)]
assert changed_parts and all(n.startswith('xl/worksheets/_rels/') and n.endswith('.xml.rels') for n in changed_parts)
S = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
br = {x.attrib['Id']: x.attrib for x in ET.fromstring(z2.read('xl/_rels/workbook.xml.rels'))}
sheet_names = {}
for sh in ET.fromstring(z2.read('xl/workbook.xml')).find('{' + S + '}sheets'):
    target = br[sh.attrib['{' + R + '}id']]['Target']
    part = target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/' + target)
    sheet_names[part] = sh.attrib['name']
actual = {}
for part in changed_parts:
    r1 = {x.attrib['Id']: x.attrib for x in ET.fromstring(z1.read(part))}
    r2 = {x.attrib['Id']: x.attrib for x in ET.fromstring(z2.read(part))}
    assert set(r1) == set(r2)
    sheet_part = part.replace('/_rels/', '/').removesuffix('.rels')
    links = {x.attrib['{' + R + '}id']: x.attrib['ref'] for x in ET.fromstring(z2.read(sheet_part)).findall('{' + S + '}hyperlinks/{' + S + '}hyperlink') if '{' + R + '}id' in x.attrib}
    for rid, item in r1.items():
        if item == r2[rid]:
            continue
        assert item['Type'].endswith('/hyperlink') and rid in links
        assert {k: v for k, v in item.items() if k != 'Target'} == {k: v for k, v in r2[rid].items() if k != 'Target'}
        actual[(sheet_names[sheet_part], links[rid])] = {'before': item['Target'], 'target': r2[rid]['Target']}
assert actual == expected

class Anchors(HTMLParser):
    def __init__(self): super().__init__(); self.ids = set()
    def handle_starttag(self, tag, attrs):
        item = dict(attrs)
        if 'id' in item: self.ids.add(item['id'])

for row in actual.values():
    url = urlsplit(row['target']); assert not url.scheme
    p = Path(unquote(url.path)); assert p.is_file(), str(p)
    if url.fragment:
        html = Anchors(); html.feed(p.read_text())
        assert unquote(url.fragment) in html.ids, (p, url.fragment)
assert sha(candidate) == args.workbook_sha256 and sha(plan_path) == args.plan_sha256
out = Q / 'final-report-links'; out.mkdir(exist_ok=False)
for name, p in [('verified-workbook.pending', candidate), ('workbook-edit-plan.json', plan_path)]:
    (out / name).write_bytes(p.read_bytes())
receipt = {'status': 'PASS_FINAL_REPORT_LINK_ONLY_DELTA', 'checked_utc': datetime.now(timezone.utc).isoformat(), 'candidate_sha256': args.workbook_sha256, 'plan_sha256': args.plan_sha256, 'previous_independent_QA_seal_sha256': sha(Q / 'final/sealed-handoff.json'), 'previous_workbook_sha256': sha(previous), 'changed_package_parts': changed_parts, 'exact_local_report_link_changes': len(actual), 'all_other_package_bytes_identical_to_independently_checked_workbook': True, 'all_69_targets_and_anchors_exist': True, 'counts': {'sheets': 28, 'formulas': 3407, 'hyperlinks': 12206, 'total_value_changes': 44, 'total_hyperlink_changes': 225}, 'changes': [{'sheet': k[0], 'cell': k[1], **v} for k, v in actual.items()], 'workbook_or_canonical_or_native_or_platform_writes': 0}
(out / 'independent-readback.json').write_text(json.dumps(receipt, indent=2) + '\n')
files = [out / 'verified-workbook.pending', out / 'workbook-edit-plan.json', out / 'independent-readback.json', Path(__file__), Q / 'final/sealed-handoff.json', Q / 'final/immutable-input-snapshots.json'] + [Path(x['snapshot_path']) for x in snapshots['files']]
seal = {'status': 'PASS_INDEPENDENT_FINAL_WORKBOOK_QA_WITH_REPORT_ROUTING', 'candidate_sha256': args.workbook_sha256, 'counts': receipt['counts'], 'prior_saved_package_checks_passed': 110076, 'prior_artifact_tool_value_reads_passed': 44, 'final_delta_link_checks_passed': 69, 'all_cell_and_style_and_formula_package_parts_unchanged_from_prior_QA': True, 'native_Excel_runtime_evaluated': False, 'files': {str(p): sha(p) for p in files}}
sealed = out / 'sealed-handoff.json'; sealed.write_text(json.dumps(seal, indent=2) + '\n')
print(json.dumps({'status': seal['status'], 'seal': str(sealed), 'sha256': sha(sealed), 'candidate_sha256': args.workbook_sha256, 'total_hyperlink_changes': 225}, indent=2))
