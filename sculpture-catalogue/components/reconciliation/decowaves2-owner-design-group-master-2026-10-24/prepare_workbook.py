"""Plan the narrow workbook update against the frozen current catalogue."""
import importlib.util
import json
import posixpath
from pathlib import Path
from xml.etree import ElementTree as E

H = Path(__file__).resolve().parent
B = H.parents[2]
OUT = B / 'outputs' / H.name
read = lambda p: json.loads(Path(p).read_text())
s = importlib.util.spec_from_file_location('native_reader', B / 'components/reconciliation/image-identity-coverage-2026-10-20/verify_edit.py')
n = importlib.util.module_from_spec(s)
s.loader.exec_module(n)
w = n.load(H / 'inputs/master_workbook.before')
g = read(H / 'canonical-master-register.json')
projection = read(H / 'projection-index.json')
changes, links = {}, {}

def value(sheet, cell, current):
    assert cell not in w['formulas'][sheet]
    before = w['values'][sheet].get(cell, '')
    if before != current:
        changes[(sheet, cell)] = {'sheet': sheet, 'cell': cell, 'before': before, 'value': current}

def protected(sheet, cell):
    column = cell.rstrip('0123456789')
    return sheet == 'Fingerprint History' or sheet == 'Source Specifications' and column in ['M', 'N'] or sheet == 'Moonphases and Dune' and column == 'I'

for sheet, info in w['sheets'].items():
    relpart = posixpath.join(posixpath.dirname(info['part']), '_rels', posixpath.basename(info['part']) + '.rels')
    rels = {x.get('Id'): x.get('Target') for x in E.fromstring(w['files'][relpart])}
    for link in info['root'].findall('.//' + n.q('hyperlink')):
        cell = link.get('ref')
        target = '#' + link.get('location') if link.get('location') else rels[link.get('{' + n.R + '}id')]
        current = target if protected(sheet, cell) else target.replace(projection['old_output'], str(OUT))
        links[(sheet, cell)] = {'sheet': sheet, 'cell': cell, 'label': w['values'][sheet].get(cell, ''), 'target': current}
    for cell, text in w['values'][sheet].items():
        if isinstance(text, str) and 'Number2 unconfirmed' in text:
            value(sheet, cell, text.replace('Number2 unconfirmed', 'Number2 separately confirmed on24 Oct'))

header = '188 active options;112 retained component IDs;110 working design groups. Owner separately confirmed the number1 and number2 Verdigris/White design pairs. Each finish retains its own specifications and price.'
value('Master Catalogue', 'A3', header)
links[('Master Catalogue', 'A3')] = {'sheet': 'Master Catalogue', 'cell': 'A3', 'label': header, 'target': str(OUT / 'decowaves2-owner-design-equivalence.html')}
value('Components', 'A3', '112 retained component IDs project to110 working design groups after two separately owner-confirmed Decowaves/Frozen Decowaves relationships. Finish, size and build options retain their own specifications. Physical casts, moulds, stock and whole-library unique total remain unverified.')
pairrows = []
for oid in projection['pair_option_ids']:
    row = next(int(c[1:]) for c, v in w['values']['Master Catalogue'].items() if c.startswith('A') and v == oid)
    pairrows.append(row)
    note = 'Owner24 Oct: number2 Verdigris/White are the same relief design. Each finish retains its specifications, price and IDs.'
    for sheet, column in [('Master Catalogue', 'V'), ('Photo Coverage', 'L')]:
        value(sheet, column + str(row), w['values'][sheet].get(column + str(row), '') + '\n' + note)
componentrows = []
for cid in projection['pair_component_ids']:
    row = next(int(c[1:]) for c, v in w['values']['Components'].items() if c.startswith('A') and v == cid)
    componentrows.append(row)
    value('Components', 'E' + str(row), 'Retained ID in working design group BC-DECO-2. Owner confirmed the number2 Verdigris/White design pair. Separate finish specifications and IDs retained. No new Terracotta photograph approval.')
for key, edit in changes.items():
    if key in links:
        links[key]['label'] = edit['value']
expected = {('Master Catalogue', 'B4'): 188, ('Master Catalogue', 'D4'): 112, ('Master Catalogue', 'F4'): 188,
            ('Master Catalogue', 'H4'): 187, ('Photo Coverage', 'B4'): 177, ('Photo Coverage', 'D4'): 166,
            ('Photo Coverage', 'F4'): 117, ('Photo Coverage', 'B5'): 11, ('Missing Pictures', 'B4'): 23,
            ('Missing Pictures', 'D4'): 1, ('Missing Pictures', 'F4'): 70, ('Draft Listings', 'B4'): 101,
            ('Draft Listings', 'D4'): 3}
plan = {'cell_changes': list(changes.values()),
        'formula_changes': [{'sheet': sn, 'cell': c, 'before': w['formulas'][sn][c], 'formula': w['formulas'][sn][c], 'expected': v} for (sn, c), v in expected.items()],
        'value_blocks': [{'sheet': x['sheet'], 'range': x['cell'], 'values': [[x['value']]]} for x in changes.values()],
        'formula_blocks': [], 'hyperlinks': list(links.values()),
        'row_heights': [{'sheet': 'Master Catalogue', 'row': r, 'height': 65} for r in pairrows] + [{'sheet': 'Components', 'row': r, 'height': 65} for r in componentrows],
        'table_appends': [], 'new_sheets': {}, 'target_rows': [], 'expected_original_sheet_count': 28,
        'expected_formula_count': 3407, 'summary_expected': [{'sheet': sn, 'cell': c, 'value': v} for (sn, c), v in expected.items()],
        'native_link_changes': [],
        'baseline_ranges': [['Master Catalogue', 'A2:Y5', 'baseline-master-header'], ['Components', 'A3:K3', 'baseline-component-scope']] + [['Components', 'E' + str(r) + ':E' + str(r), 'baseline-component-' + str(r)] for r in componentrows],
        'preview_ranges': [['Master Catalogue', 'A2:Y5', 'current-master-header'], ['Components', 'A3:K3', 'current-component-scope']] + [['Components', 'E' + str(r) + ':E' + str(r), 'current-component-' + str(r)] for r in componentrows],
        'supplemental_preview_ranges': [['Photo Coverage', 'L' + str(r) + ':L' + str(r), 'current-photo-note-' + str(r)] for r in pairrows]}
for name, obj in [('workbook-edit-plan.json', plan), ('expected-edit.json', {'sheets': {}, 'hyperlinks': plan['hyperlinks'], 'formulas': []})]:
    (H / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'status': 'PLAN_READY', 'cell_changes': len(changes), 'pair_rows': pairrows, 'component_rows': componentrows, 'native_image_links_changed': 0}))
