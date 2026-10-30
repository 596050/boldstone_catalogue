"""Serialize missing native-hyperlink support and verify the saved XLSX bytes.

All cells, formulas, formatting and tables are authored with artifact-tool.
Native hyperlinks are used because its HYPERLINK calculation returns an error.
"""
import argparse
import collections
import hashlib
import json
import posixpath
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as E

HERE = Path(__file__).resolve().parent
S = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
P = 'http://schemas.openxmlformats.org/package/2006/relationships'
q = lambda ns, tag: '{' + ns + '}' + tag
digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()

def col(n):
    s = ''
    while n:
        n, rem = divmod(n - 1, 26)
        s = chr(65 + rem) + s
    return s

def main():
    args = argparse.ArgumentParser()
    args.add_argument('--book', required=True)
    args.add_argument('--attach', action='store_true')
    opts = args.parse_args()
    book = Path(opts.book)
    plan = json.loads((HERE / 'expected-workbook.json').read_text())
    graph = json.loads((HERE / 'canonical-count-register.json').read_text())
    with zipfile.ZipFile(book) as z:
        files = {i.filename: (i, z.read(i.filename)) for i in z.infolist()}
    workbook = E.fromstring(files['xl/workbook.xml'][1])
    rels = {x.get('Id'): x.get('Target') for x in E.fromstring(files['xl/_rels/workbook.xml.rels'][1])}
    paths = {}
    for s in workbook.find(q(S, 'sheets')):
        target = rels[s.get(q(R, 'id'))]
        paths[s.get('name')] = target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/' + target)
    by_sheet = collections.defaultdict(list)
    for x in plan['hyperlinks']:
        by_sheet[x['sheet']].append(x)
    if opts.attach:
        assert len({(x['sheet'], x['cell']) for x in plan['hyperlinks']}) == len(plan['hyperlinks'])
        replacements = {}
        late = {'printOptions', 'pageMargins', 'pageSetup', 'headerFooter', 'rowBreaks', 'colBreaks', 'customProperties', 'cellWatches', 'ignoredErrors', 'smartTags', 'drawing', 'legacyDrawing', 'legacyDrawingHF', 'picture', 'oleObjects', 'controls', 'webPublishItems', 'tableParts', 'extLst'}
        for name, entries in by_sheet.items():
            loc = paths[name]
            tree = E.fromstring(files[loc][1])
            assert tree.find(q(S, 'hyperlinks')) is None
            links = E.Element(q(S, 'hyperlinks'))
            index = next((i for i, x in enumerate(tree) if x.tag.split('}')[-1] in late), len(tree))
            tree.insert(index, links)
            relpath = posixpath.join(posixpath.dirname(loc), '_rels', posixpath.basename(loc) + '.rels')
            reltree = E.fromstring(files[relpath][1]) if relpath in files else E.Element(q(P, 'Relationships'))
            used = {x.get('Id') for x in reltree}
            for i, x in enumerate(entries, 1):
                assert x['target'].startswith('https://')
                rid = 'rIdCatalogueLink' + str(i)
                assert rid not in used
                E.SubElement(links, q(S, 'hyperlink'), ref=x['cell'], display=x['label'], attrib={q(R, 'id'): rid})
                E.SubElement(reltree, q(P, 'Relationship'), Id=rid, Type=R + '/hyperlink', Target=x['target'], TargetMode='External')
            replacements[loc] = E.tostring(tree, encoding='utf-8', xml_declaration=True)
            replacements[relpath] = E.tostring(reltree, encoding='utf-8', xml_declaration=True)
        temp = book.with_suffix('.links.tmp')
        with zipfile.ZipFile(temp, 'w', compression=zipfile.ZIP_DEFLATED) as z:
            for name, (info, raw) in files.items():
                z.writestr(info, replacements.pop(name, raw))
            for name, raw in replacements.items():
                z.writestr(name, raw)
        temp.replace(book)

    checks, issues, values, formulas = 0, [], {}, {}
    def check(ok, message):
        nonlocal checks
        checks += 1
        if not ok:
            issues.append(message)
    with zipfile.ZipFile(book) as z:
        strings = []
        if 'xl/sharedStrings.xml' in z.namelist():
            strings = [''.join(x.itertext()) for x in E.fromstring(z.read('xl/sharedStrings.xml'))]
        check(list(paths) == list(plan['sheets']), 'Worksheet order and names')
        for name, loc in paths.items():
            tree = E.fromstring(z.read(loc))
            cells, f_cells = {}, {}
            for cell in tree.iter(q(S, 'c')):
                typ, addr = cell.get('t'), cell.get('r')
                check(typ != 'e', f'{name}!{addr}: error cell')
                v, f = cell.find(q(S, 'v')), cell.find(q(S, 'f'))
                raw = v.text if v is not None and v.text is not None else ''
                if typ == 's':
                    val = strings[int(raw)]
                elif typ == 'inlineStr':
                    inline = cell.find(q(S, 'is'))
                    val = ''.join(inline.itertext()) if inline is not None else ''
                elif typ == 'b':
                    val = raw == '1'
                elif typ in ['str', 'e']:
                    val = raw
                elif raw:
                    val = float(raw)
                else:
                    val = ''
                cells[addr] = val
                if f is not None:
                    f_cells[addr] = '=' + (f.text or '')
            values[name], formulas[name] = cells, f_cells
            expected = plan['sheets'][name]
            for j, title in enumerate(expected['headers'], 1):
                check(cells.get(col(j) + '9', '') == title, f'{name}: header {j}')
            for i, row in enumerate(expected['rows'], expected['first']):
                for j, want in enumerate(row, 1):
                    addr = col(j) + str(i)
                    check(cells.get(addr, '') == want, f'{name}!{addr}: expected value {str(want)[:90]}')
            relpath = posixpath.join(posixpath.dirname(loc), '_rels', posixpath.basename(loc) + '.rels')
            relationships = {x.get('Id'): x for x in E.fromstring(z.read(relpath))} if relpath in z.namelist() else {}
            actual = {}
            for h in tree.findall('.//' + q(S, 'hyperlink')):
                rel = relationships[h.get(q(R, 'id'))]
                check(rel.get('TargetMode') == 'External', f'{name} native link external mode')
                actual[h.get('ref')] = rel.get('Target')
            check(len(actual) == len(by_sheet[name]), f'{name}: hyperlink count')
            for h in by_sheet[name]:
                check(actual.get(h['cell']) == h['target'], f'{name}!{h["cell"]}: native link destination')
                check(cells.get(h['cell']) == h['label'], f'{name}!{h["cell"]}: link label')
            check(len(tree.findall('.//' + q(S, 'tablePart'))) == 1, f'{name}: filterable table')
        check(sum(len(x) for x in formulas.values()) == len(plan['formulas']), 'Only planned count formulas present')
        for f in plan['formulas']:
            check(formulas[f['sheet']].get(f['cell']) == f['formula'], f'{f["sheet"]}!{f["cell"]}: formula')
            check(values[f['sheet']].get(f['cell']) == f['expected'], f'{f["sheet"]}!{f["cell"]}: cached result')

    check(len(graph['components']) == values['Components']['B4'], 'Saved component total reconciles')
    check(sum(c['option_count'] for c in graph['components']) == values['Components']['D4'], 'Component option total reconciles')
    check(len(graph['options']) == values['Components']['F4'], 'Sale-option total reconciles')
    check(len(graph['original_review_specification_assertions']) == 1668, '1668 original assertions retained')
    check(len(graph['source_review_reconciliation']) == 278, '278 review rows classified')
    check(len(graph['source_component_dispositions']) == 125, '125 model component rows classified')
    check(all(x['offered_fixing_choices'] == ['Keyhole fixing', 'French cleat'] for x in graph['options']), 'Global offered fixing choice retained')
    check(len(graph['scoped_working_correction_option_ids']) == 4, 'Four scoped correction records applied')
    check(len(graph['case_closure_dispositions']) == 15, 'Fifteen source-case dispositions retained')
    check(len({x['component_id'] for x in graph['components']}) == len(graph['components']), 'Unique canonical component IDs')
    check(len({x['name'] for x in graph['components']}) == len(graph['components']), 'Unambiguous component display names')
    check(len([x for x in graph['options'] if not x['file_id']]) == 1, 'Only Long option has explicitly unbound file identity')
    check(graph['summary']['physical_stock_quantity'] is None, 'No stock total invented')
    check(graph['summary']['catalogue_wide_unique_design_total_including_unresolved_sources'] is None, 'Unresolved whole-library unique-design total remains explicit')
    result = {'status': 'PASS' if not issues else 'FAIL', 'checked_utc': datetime.now(timezone.utc).isoformat(),
              'workbook': str(book), 'workbook_sha256': digest(book),
              'register_sha256': digest(HERE / 'canonical-count-register.json'), 'checks': checks, 'issues': issues,
              'native_hyperlinks': len(plan['hyperlinks']), 'count_formulas': len(plan['formulas']),
              'sheet_data_rows': {k: len(v['rows']) for k, v in plan['sheets'].items()},
              'count_summary': graph['summary'], 'cell_authoring': '@oai/artifact-tool',
              'native_link_fallback': 'OOXML relationships only; artifact HYPERLINK function is not implemented'}
    (HERE / 'saved-file-verification.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ['status', 'checks', 'issues', 'workbook_sha256', 'native_hyperlinks', 'count_formulas']}))
    assert not issues

if __name__ == '__main__':
    main()
