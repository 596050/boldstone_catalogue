"""Attach native hyperlink relationships, then verify the saved workbook bytes.

artifact-tool authors all cells, styles, tables and formulas. The native-link
fallback avoids its unsupported HYPERLINK calculation while preserving links.
"""
import argparse
import collections
import hashlib
import json
import posixpath
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse
from xml.etree import ElementTree as E

HERE = Path(__file__).resolve().parent
S = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
P = 'http://schemas.openxmlformats.org/package/2006/relationships'
q = lambda ns, tag: '{' + ns + '}' + tag
read = lambda p: json.loads(p.read_text())
digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()

def col(n):
    s = ''
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--book', required=True)
    parser.add_argument('--attach', action='store_true')
    args = parser.parse_args()
    book = Path(args.book)
    expected = read(HERE / 'expected-workbook.json')
    g = read(HERE / 'canonical-master-register.json')
    with zipfile.ZipFile(book) as z:
        files = {i.filename: (i, z.read(i.filename)) for i in z.infolist()}
    workbook = E.fromstring(files['xl/workbook.xml'][1])
    wb_rels = {x.get('Id'): x.get('Target') for x in E.fromstring(files['xl/_rels/workbook.xml.rels'][1])}
    sheets = {}
    for sheet in workbook.find(q(S, 'sheets')):
        target = wb_rels[sheet.get(q(R, 'id'))]
        sheets[sheet.get('name')] = target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/' + target)
    by_sheet = collections.defaultdict(list)
    for x in expected['hyperlinks']:
        by_sheet[x['sheet']].append(x)
    if args.attach:
        assert len({(x['sheet'], x['cell']) for x in expected['hyperlinks']}) == len(expected['hyperlinks'])
        replacement = {}
        late = {'printOptions', 'pageMargins', 'pageSetup', 'headerFooter', 'rowBreaks', 'colBreaks', 'customProperties', 'cellWatches', 'ignoredErrors', 'smartTags', 'drawing', 'legacyDrawing', 'legacyDrawingHF', 'picture', 'oleObjects', 'controls', 'webPublishItems', 'tableParts', 'extLst'}
        for name, entries in by_sheet.items():
            loc = sheets[name]
            tree = E.fromstring(files[loc][1])
            assert tree.find(q(S, 'hyperlinks')) is None
            node = E.Element(q(S, 'hyperlinks'))
            index = next((i for i, x in enumerate(tree) if x.tag.split('}')[-1] in late), len(tree))
            tree.insert(index, node)
            relpath = posixpath.join(posixpath.dirname(loc), '_rels', posixpath.basename(loc) + '.rels')
            rels = E.fromstring(files[relpath][1]) if relpath in files else E.Element(q(P, 'Relationships'))
            used = {x.get('Id') for x in rels}
            for i, entry in enumerate(entries, 1):
                h = E.SubElement(node, q(S, 'hyperlink'), ref=entry['cell'], display=entry['label'])
                if entry['target'].startswith('#'):
                    h.set('location', entry['target'][1:])
                else:
                    assert entry['target'].startswith('https://')
                    rid = 'rIdMasterLink' + str(i)
                    assert rid not in used
                    h.set(q(R, 'id'), rid)
                    E.SubElement(rels, q(P, 'Relationship'), Id=rid, Type=R + '/hyperlink', Target=entry['target'], TargetMode='External')
            replacement[loc] = E.tostring(tree, encoding='utf-8', xml_declaration=True)
            replacement[relpath] = E.tostring(rels, encoding='utf-8', xml_declaration=True)
        temp = book.with_suffix('.links.tmp')
        with zipfile.ZipFile(temp, 'w', compression=zipfile.ZIP_DEFLATED) as z:
            for name, (info, content) in files.items():
                z.writestr(info, replacement.pop(name, content))
            for name, content in replacement.items():
                z.writestr(name, content)
        temp.replace(book)

    checks, issues, cell_values, formula_cells, all_links = 0, [], {}, {}, []
    def check(condition, message):
        nonlocal checks
        checks += 1
        if not condition:
            issues.append(message)
    with zipfile.ZipFile(book) as z:
        strings = [''.join(x.itertext()) for x in E.fromstring(z.read('xl/sharedStrings.xml'))] if 'xl/sharedStrings.xml' in z.namelist() else []
        check(list(sheets) == list(expected['sheets']), 'Sheet names and order')
        for name, loc in sheets.items():
            tree = E.fromstring(z.read(loc))
            values, formulas = {}, {}
            for cell in tree.iter(q(S, 'c')):
                addr, typ = cell.get('r'), cell.get('t')
                check(typ != 'e', f'{name}!{addr}: error cell')
                v, f = cell.find(q(S, 'v')), cell.find(q(S, 'f'))
                raw = v.text if v is not None and v.text is not None else ''
                if typ == 's': value = strings[int(raw)]
                elif typ == 'inlineStr': value = ''.join(cell.find(q(S, 'is')).itertext())
                elif typ == 'b': value = raw == '1'
                elif typ in ['str', 'e']: value = raw
                elif raw: value = float(raw)
                else: value = ''
                values[addr] = value
                if f is not None: formulas[addr] = '=' + (f.text or '')
            cell_values[name], formula_cells[name] = values, formulas
            view = expected['sheets'][name]
            for j, value in enumerate(view['headers'], 1):
                check(values.get(col(j) + '9', '') == value, f'{name}: header {j}')
            for i, row in enumerate(view['rows'], view['first']):
                for j, value in enumerate(row, 1):
                    addr = col(j) + str(i)
                    check(values.get(addr, '') == value, f'{name}!{addr}: value')
            relpath = posixpath.join(posixpath.dirname(loc), '_rels', posixpath.basename(loc) + '.rels')
            relations = {x.get('Id'): x for x in E.fromstring(z.read(relpath))} if relpath in z.namelist() else {}
            actual = {}
            for h in tree.findall('.//' + q(S, 'hyperlink')):
                if h.get('location'):
                    target = '#' + h.get('location')
                else:
                    relation = relations[h.get(q(R, 'id'))]
                    check(relation.get('TargetMode') == 'External', f'{name}: external link mode')
                    target = relation.get('Target')
                actual[h.get('ref')] = target
                all_links.append({'sheet': name, 'cell': h.get('ref'), 'target': target})
            check(len(actual) == len(by_sheet[name]), name + ': native link count')
            for entry in by_sheet[name]:
                check(actual.get(entry['cell']) == entry['target'], f'{name}!{entry["cell"]}: native destination')
                check(values.get(entry['cell']) == entry['label'], f'{name}!{entry["cell"]}: link label')
            check(len(tree.findall('.//' + q(S, 'tablePart'))) == 1, name + ': filterable table')
            pane = tree.find('.//' + q(S, 'pane'))
            check(pane is not None, name + ': frozen identifiers and headers')
        for f in expected['formulas']:
            check(formula_cells[f['sheet']].get(f['cell']) == f['formula'], f'{f["sheet"]}!{f["cell"]}: formula')
            check(cell_values[f['sheet']].get(f['cell']) == f['expected'], f'{f["sheet"]}!{f["cell"]}: cached result')
        check(sum(len(v) for v in formula_cells.values()) == len(expected['formulas']), 'Only planned formulas')

    # Check identities and specifications against the canonical input, not only
    # the builder's prepared cell matrix.
    for i, option in enumerate(g['options'], 10):
        values = cell_values['Master Catalogue']
        check(values['A' + str(i)] == option['product_id'], 'Master option ID')
        check(values['B' + str(i)] == option['name'], 'Master approved/source name')
        for j, field in enumerate(['Dimensions / depth', 'Weight', 'Material / finish', 'Fixing', 'Individual price', 'Availability'], 5):
            check(values[col(j) + str(i)] == option['master_fields'][field]['display'], 'Master field scope: ' + option['product_id'] + ' ' + field)
        check(values['Q' + str(i)] == (option.get('file_id') or 'Unbound'), 'Primary stable file ID')
        check(values['R' + str(i)] == (option.get('folder_id') or 'Unbound'), 'Primary stable folder ID')
        check(values['K' + str(i)] == 6, 'Six working fields recorded')
    check(cell_values['Master Catalogue']['B4'] == 184, '184 options headline')
    check(cell_values['Master Catalogue']['D4'] == 111, '111 component identities headline')
    check(cell_values['Master Catalogue']['F4'] == 184, '184 options with six working fields')
    check(cell_values['Master Catalogue']['H4'] == 183, '183 current Dropbox references')
    check(len(g['original_review_specification_assertions']) == 1668, 'Original specification record count')
    for i, raw in enumerate(g['original_review_specification_assertions'], 10):
        for j, source_index in [(1,0),(2,1),(3,2),(4,3),(5,4),(6,5),(10,9),(11,10),(12,11),(13,7),(14,8),(15,12)]:
            check(cell_values['Source Specifications'].get(col(j) + str(i), '') == raw[source_index], 'Original source assertion retained')
        check(cell_values['Source Specifications'].get('G' + str(i), '') + cell_values['Source Specifications'].get('P' + str(i), '') == raw[6], 'Original source basis retained across continuation columns')
    fields = ['Dimensions / depth','Weight','Material / finish','Fixing','Individual price','Availability']
    for i, option in enumerate(g['options']):
        for j, field in enumerate(fields):
            row = str(10 + i * 6 + j)
            check(cell_values['Specifications'].get('F' + row, '') + cell_values['Specifications'].get('O' + row, '') == option['master_fields'][field]['basis'], 'Full current basis retained across continuation columns')
    before = read(Path(g['master_input_manifest']['count_register']['snapshot']))
    check([(x['product_id'],x['name']) for x in g['options']] == [(x['product_id'],x['name']) for x in before['options']], 'No option identity/count change')
    check(g['original_review_specification_assertions'] == before['original_review_specification_assertions'], 'Original assertion arrays untouched')
    check(len(g['wall_circle_display_recoveries']) == 36, '36 Wall Circle source proposals restored')
    check(all(not x['physical_specifications_verified'] for x in g['options']), 'Working completion not physical verification')
    check(g['summary']['physical_stock_quantity'] is None, 'No physical stock quantity invented')
    check(len(g['master_platform_association_overlays']['O001']['related_option_ids']) == 7, 'Seven Wall Circle visual records associated only at parent-family scope')
    check(len(g['master_platform_association_overlays']['O034']['related_option_ids']) == 2, 'Two Bone Spiral panels associated only with source set')
    check(all(not x['exact_individual_match_upgraded'] for x in g['master_platform_association_overlays'].values()), 'No exact variant/SKU match upgrade from source associations')
    prefixes = ['/BOLDSTONE MASTER/Products/01 Wall Sculptures/Fan Folds', '/BOLDSTONE MASTER/Products/01 Wall Sculptures/Shellmoon', '/BOLDSTONE MASTER/Products/01 Wall Sculptures/Mooncrater', '/BOLDSTONE MASTER/Products/01 Wall Sculptures/Moon Crater Phase/Moon Crater Phase 4']
    ammonite = read(Path(g['master_input_manifest']['ammonite_current_paths']['snapshot']))
    prefixes += [x['old_prefix'] for x in ammonite['prefix_maps']]
    stale = []
    for entry in all_links:
        parsed = urlparse(entry['target'])
        if not parsed.netloc.endswith('dropbox.com'): continue
        path = unquote(parsed.path)
        for root in ['/home','/preview']:
            if path.startswith(root + '/'):
                path = path[len(root):];break
        if any(path == p or path.startswith(p + '/') for p in prefixes): stale.append(entry)
    check(not stale, 'No superseded current Dropbox link prefixes')
    result = {'status': 'PASS' if not issues else 'FAIL', 'checked_utc': datetime.now(timezone.utc).isoformat(),
              'workbook': str(book), 'workbook_sha256': digest(book), 'master_register_sha256': digest(HERE / 'canonical-master-register.json'),
              'checks': checks, 'issues': issues, 'native_hyperlinks': len(all_links), 'count_formulas': len(expected['formulas']),
              'stale_current_links': stale, 'sheet_data_rows': {k:len(v['rows']) for k,v in expected['sheets'].items()},
              'summary': g['summary'], 'spreadsheet_authoring': '@oai/artifact-tool',
              'native_link_fallback': 'Native OOXML hyperlinks only; unsupported HYPERLINK calculation avoided'}
    (HERE / 'saved-file-verification.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k:result[k] for k in ['status','checks','workbook_sha256','native_hyperlinks','count_formulas']} | {'issue_count':len(issues),'first_issues':issues[:8]}))
    assert not issues

if __name__ == '__main__': main()
