"""Prepare an offline, guarded handoff. Never modify shared catalogue inputs."""
import copy
import hashlib
import html
import json
import posixpath
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit
from xml.etree import ElementTree as ET
from zipfile import ZipFile

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[2]
PROJECT = BASE.parent
PROPOSAL = HERE / 'case-normalization-proposal-20261024T154232Z.json'
read = lambda path: json.loads(Path(path).read_text())
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
esc = lambda value: html.escape(str(value), quote=True)
stamp = datetime.now(timezone.utc)
OUT = HERE / ('case-normalization-handoff-' + stamp.strftime('%Y%m%dT%H%M%SZ'))

pointer_path = BASE / 'current-master.json'
pointer_sha = sha(pointer_path)
pointer = read(pointer_path)
register_path = BASE / pointer['register']
workbook_path = BASE / pointer['workbook']
register = read(register_path)
assert sha(register_path) == pointer['register_sha256']
assert sha(workbook_path) == pointer['workbook_sha256']
proposal = read(PROPOSAL)
assert proposal['source_register_sha256'] == pointer['register_sha256']
assert proposal['new_selections_or_native_writes'] == 0
seal_path = Path(proposal['audit_seal'])
assert sha(seal_path) == proposal['audit_seal_sha256']
seal = read(seal_path)
for file in seal['files']:
    assert sha(file['path']) == file['sha256'], file['path']
findings_path = seal_path.parent / 'findings.json'
findings = read(findings_path)
audit_rows = {row['option_id']: row for row in findings['rows']}
options = {row['product_id']: (i, row) for i, row in enumerate(register['options'])}
assert len(proposal['rows']) == len({r['option_id'] for r in proposal['rows']}) == 6
candidate = copy.deepcopy(register)
patch = []
rows = []
before_to_identity = {}
for proposed in proposal['rows']:
    option_id = proposed['option_id']
    index, option = options[option_id]
    audit = audit_rows[option_id]
    file = audit['native_file_metadata']
    folder = audit['native_folder_metadata']
    assert option['file_id'] == proposed['expected_file_id'] == file['id']
    assert option['folder_id'] == proposed['expected_folder_id'] == folder['id']
    assert audit['case_only_url_difference'] is True
    assert posixpath.dirname(file['path_display']) == folder['path_display']
    for key in ('image_url', 'folder_url'):
        before, after = proposed['before'][key], proposed['proposed'][key]
        assert option[key] == before
        old, new = urlsplit(before), urlsplit(after)
        assert old.scheme == new.scheme == 'https'
        assert old.netloc == new.netloc == 'www.dropbox.com'
        assert (old.query, old.fragment) == (new.query, new.fragment)
        assert unquote(old.path).casefold() == unquote(new.path).casefold()
        assert unquote(old.path) != unquote(new.path)
        if key == 'folder_url':
            assert unquote(new.path) == '/home' + folder['path_display']
        elif new.path.startswith('/home/'):
            assert unquote(new.path) == '/home' + folder['path_display']
            assert parse_qs(new.query) == {'preview': [file['name']]}
        else:
            assert unquote(new.path) == '/preview' + file['path_display']
            assert not new.query
        patch.append({'op': 'replace', 'path': f'/options/{index}/{key}',
                      'option_id': option_id, 'expected_before': before, 'value': after,
                      'expected_file_id': file['id'], 'expected_folder_id': folder['id']})
        before_to_identity[before] = {'option_id': option_id, 'field': key}
        candidate['options'][index][key] = after
    rows.append({**proposed, 'current_option': option, 'file_metadata': file,
                 'folder_metadata': folder, 'metadata_observations': audit['evidence']})

def differences(before, after, path=''):
    if type(before) is not type(after):
        return [path]
    if isinstance(before, dict):
        assert before.keys() == after.keys()
        return [p for key in before for p in differences(before[key], after[key], path + '/' + key)]
    if isinstance(before, list):
        assert len(before) == len(after)
        return [p for i, (a, b) in enumerate(zip(before, after)) for p in differences(a, b, path + '/' + str(i))]
    return [] if before == after else [path]

changed_paths = differences(register, candidate)
assert sorted(changed_paths) == sorted(row['path'] for row in patch)
assert len(changed_paths) == 12

def occurrences(value, path=''):
    if isinstance(value, dict):
        return [r for key, child in value.items() for r in occurrences(child, path + '/' + str(key))]
    if isinstance(value, list):
        return [r for i, child in enumerate(value) for r in occurrences(child, path + '/' + str(i))]
    if not isinstance(value, str):
        return []
    return [{'path': path, **identity, 'exact_value': value == before}
            for before, identity in before_to_identity.items() if before in value]

register_occurrences = occurrences(register)
ns = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
rel_ns = {'r': 'http://schemas.openxmlformats.org/package/2006/relationships'}
id_ns = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
workbook_occurrences = []
with ZipFile(workbook_path) as book:
    strings = []
    if 'xl/sharedStrings.xml' in book.namelist():
        strings = [''.join(si.itertext()) for si in ET.fromstring(book.read('xl/sharedStrings.xml'))]
    relations = {r.attrib['Id']: r.attrib['Target'] for r in ET.fromstring(book.read('xl/_rels/workbook.xml.rels'))}
    for sheet in ET.fromstring(book.read('xl/workbook.xml')).findall('s:sheets/s:sheet', ns):
        target = relations[sheet.attrib[id_ns + 'id']]
        part = target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/' + target)
        tree = ET.fromstring(book.read(part))
        headers = {}
        for cell in tree.findall('.//s:sheetData/s:row/s:c', ns):
            ref = cell.attrib['r']
            raw = cell.find('s:v', ns)
            text = ''
            if cell.attrib.get('t') == 's' and raw is not None:
                text = strings[int(raw.text)]
            elif cell.attrib.get('t') == 'inlineStr':
                text = ''.join(cell.find('s:is', ns).itertext())
            elif raw is not None:
                text = raw.text or ''
            formula = cell.find('s:f', ns)
            values = [('value', text)]
            if formula is not None:
                values.append(('formula', formula.text or ''))
            col = ''.join(c for c in ref if c.isalpha())
            if ''.join(c for c in ref if c.isdigit()) == '1':
                headers[col] = text
            for kind, value in values:
                for before, identity in before_to_identity.items():
                    if before in value:
                        workbook_occurrences.append({'sheet': sheet.attrib['name'], 'cell': ref,
                            'header': headers.get(col, ''), 'kind': kind, **identity, 'exact_value': value == before})
        relpart = posixpath.dirname(part) + '/_rels/' + posixpath.basename(part) + '.rels'
        hyperlinks = {}
        if relpart in book.namelist():
            hyperlinks = {r.attrib['Id']: r.attrib.get('Target', '') for r in ET.fromstring(book.read(relpart))}
        for link in tree.findall('s:hyperlinks/s:hyperlink', ns):
            target = hyperlinks.get(link.attrib.get(id_ns + 'id'), '')
            for before, identity in before_to_identity.items():
                if before in target:
                    ref = link.attrib['ref']
                    col = ''.join(c for c in ref if c.isalpha())
                    workbook_occurrences.append({'sheet': sheet.attrib['name'], 'cell': ref,
                        'header': headers.get(col, ''), 'kind': 'hyperlink_target', **identity,
                        'exact_value': target == before})

report_roots = {BASE / value for value in pointer.get('current_image_review_links', {}).values()
                if isinstance(value, str) and value.endswith('.html')}
report_roots.add(BASE / pointer['current_local_draft_completion']['review'])
for value in pointer['current_individual_sculpture_list'].values():
    if isinstance(value, str) and value.endswith(('.html', '.csv', '.json')):
        report_roots.add(BASE / value)
report_roots.update((PROJECT / 'reports/catalogue-terminal-walkthrough-20261024').glob('*'))
report_roots.update(HERE / name for name in ['index.html', 'walkthrough-state.json', 'acanthus-options.html', 'acanthus-options.json'])
# Include every text projection in the current output directory; earlier releases stay historical.
output_dir = (BASE / pointer['current_image_review_links']['all_links']).parent
report_roots.update(output_dir.rglob('*'))
report_inventory = []
for path in sorted(report_roots):
    if not path.is_file() or path.suffix.lower() not in ('.html', '.csv', '.json', '.txt', '.md'):
        continue
    content = path.read_text()
    hits = [{**identity, 'literal_occurrences': content.count(before)}
            for before, identity in before_to_identity.items() if before in content]
    if hits:
        report_inventory.append({'path': str(path), 'sha256': sha(path), 'hits': hits})

controls = ['components/checkpoint.json', 'checkpoint.json', 'components/reviews/specification_review_progress.json']
assert all(read(BASE / path)['current_master_catalogue'] == pointer for path in controls)
assert sha(pointer_path) == pointer_sha, 'Shared pointer changed; retry with fresh guards'
assert sha(register_path) == pointer['register_sha256']
assert sha(workbook_path) == pointer['workbook_sha256']
OUT.mkdir(exist_ok=False)
packet = {'schema': 'boldstone.case-only-navigation-handoff.v1',
    'status': 'GUARDED_READY_FOR_SOLE_PUBLISHER_NOT_APPLIED', 'recorded_utc': stamp.isoformat(),
    'publisher_thread': '01a144ab-1a7c-7223-a403-73a4d53d70ff',
    'pointer_sha256': pointer_sha, 'register': str(register_path), 'register_sha256': sha(register_path),
    'workbook': str(workbook_path), 'workbook_sha256': sha(workbook_path),
    'source_proposal': str(PROPOSAL), 'source_proposal_sha256': sha(PROPOSAL),
    'audit_seal': str(seal_path), 'audit_seal_sha256': sha(seal_path),
    'rows': rows, 'guarded_replacements': patch, 'in_memory_changed_paths': changed_paths,
    'counts': {'options': 6, 'top_level_url_fields': 12, 'retained_option_rows': len(register['options']),
               'active_option_count': pointer['current_option_count']},
    'historical_inputs_changed': False, 'shared_catalogue_writes': 0, 'new_live_reads': 0,
    'native_or_platform_writes': 0, 'new_selections_or_physical_verifications': 0,
    'scope': 'Twelve top-level URLs only in guarded option projection. Same IDs, immediate parents, URL routes and query filenames. Metadata observations retain their actual original clocks. No HTTP accessibility, visual identity or physical specification claim.',
    'publication_followup': 'Publisher must refresh current workbook/report projections while retaining historical source columns, earlier releases, original metadata receipts and URL histories. Occurrences inventory is evidence, not a global substitution list.'}
inventory = {'status': 'READ_ONLY_LITERAL_URL_OCCURRENCE_INVENTORY',
    'register_occurrences': register_occurrences, 'workbook_occurrences': workbook_occurrences,
    'report_projection_occurrences': report_inventory,
    'report_scope': 'Current pointer-linked image reports, current output directory, current individual list, shared terminal reader and this session reader. Historical releases intentionally excluded.',
    'historical_protection': 'Every occurrence requires classification by publisher; source/historical columns and audit artifacts are not rewrite targets.'}
for name, data in [('handoff.json', packet), ('projection-occurrences.json', inventory)]:
    (OUT / name).write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')
cards = []
for i, row in enumerate(rows, 1):
    times = ', '.join(e['recorded_utc'] for e in row['metadata_observations'])
    delta = ''.join('<tr><th>' + esc(k) + '</th><td><code>' + esc(unquote(urlsplit(row['before'][k]).path)) +
        '</code></td><td><code>' + esc(unquote(urlsplit(row['proposed'][k]).path)) + '</code></td></tr>'
        for k in ('image_url', 'folder_url'))
    cards.append('<article id="' + esc(row['option_id']) + '"><h2>' + str(i) + '. ' + esc(row['name']) +
        '</h2><p><a href="' + esc(row['proposed']['image_url']) + '">Image at observed path</a> · <a href="' +
        esc(row['proposed']['folder_url']) + '">Containing folder</a></p><p>Selected file: <code>' +
        esc(row['expected_file_id']) + '</code><br>Containing folder: <code>' + esc(row['expected_folder_id']) +
        '</code></p><table><thead><tr><th>Field</th><th>Current saved path</th><th>Proposed capitalization</th></tr></thead><tbody>' +
        delta + '</tbody></table><p>Original metadata observations (UTC): ' + esc(times) + '</p></article>')
page = '<!doctype html><html><head><meta charset="utf-8"><title>Six catalogue URL capitalization corrections</title><style>body{font:16px system-ui;max-width:1120px;margin:36px auto;padding:0 22px;color:#20242a}article{border-top:1px solid #ccc;margin-top:30px;padding-top:12px}a{color:#14558c}table{border-collapse:collapse;width:100%;font-size:13px}td,th{border:1px solid #ccc;padding:8px;text-align:left;vertical-align:top}code{overflow-wrap:anywhere}p{line-height:1.5}</style></head><body><h1>Six URL capitalization corrections</h1><p>Prepared for the main session, the sole catalogue publisher. These twelve URL-field changes are not applied by this report. Same selected files, folders and original metadata observation clocks. No new live read or Dropbox write.</p><p><a href="handoff.json">Guarded handoff</a> · <a href="projection-occurrences.json">Current projection occurrence inventory</a></p>' + ''.join(cards) + '</body></html>'
(OUT / 'index.html').write_text(page)
result = {'schema': 'boldstone.case-only-navigation-handoff-seal.v1', 'status': 'PASS_GUARDED_TWELVE_URL_FIELDS_ONLY',
    'recorded_utc': datetime.now(timezone.utc).isoformat(), 'source_pointer_sha256': pointer_sha,
    'checks': {'all_six_current_ID_and_before_guards': True, 'same_native_immediate_parents': True,
        'capitalization_only_same_URL_route_and_query': True, 'only_twelve_candidate_fields_changed': True,
        'all_original_audit_seal_members_match': True, 'three_current_controls_equal_pointer': True,
        'source_register_workbook_and_pointer_unchanged': True},
    'files': [{'path': str(path), 'sha256': sha(path)} for path in [Path(__file__), OUT / 'handoff.json', OUT / 'projection-occurrences.json', OUT / 'index.html']]}
(OUT / 'sealed-handoff.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({'output': str(OUT), 'status': result['status'], 'seal_sha256': sha(OUT / 'sealed-handoff.json'),
    'url_fields': len(patch), 'register_literal_occurrences': len(register_occurrences),
    'workbook_occurrences_by_sheet': dict(Counter(r['sheet'] for r in workbook_occurrences)),
    'current_projection_files_with_hits': len(report_inventory)}, indent=2))
