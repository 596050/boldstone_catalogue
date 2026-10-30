"""Plan targeted current-reference edits; original source cells stay immutable."""
import copy
import importlib.util
import json
import posixpath
import re
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse
from xml.etree import ElementTree as E

H = Path(__file__).resolve().parent
B = H.parents[2]
ROOT = B.parent
read = lambda p: json.loads(Path(p).read_text())
write = lambda p, v: Path(p).write_text(json.dumps(v, ensure_ascii=False, indent=2) + '\n')
s = importlib.util.spec_from_file_location('native', B / 'components/reconciliation/image-identity-coverage-2026-10-20/verify_edit.py')
n = importlib.util.module_from_spec(s)
s.loader.exec_module(n)
w = n.load(H / 'inputs/master_workbook.before')
oldplan = read(B / 'components/reconciliation/current-six-url-case-navigation-master-2026-10-24/workbook-edit-plan.json')
plan = copy.deepcopy(oldplan)
native = read(ROOT / 'reports/dropbox-wall-complete-role-review-20261024T214349Z/complete-current-native-object-map.json')
saved = read(H / 'inputs/asset_map.before')
oldnative = read(H / 'inputs/native_map.before')['current_objects']
replacement = read(B / 'components/parallel-reviews/held-identities-resumption-01a16dbc-20261024/deleted-reference-resolution/proposed-reference-replacements.json')
replacements = {r['before']['file_id']: r['proposed']['file_id'] for r in replacement['changes']}

def norm(url):
    u = urlparse(url or '')
    p = unquote(u.path)
    for pre in ['/home', '/preview']:
        if p.startswith(pre+'/'):
            p = p[len(pre):]
            break
    q = parse_qs(u.query)
    return p.rstrip('/') + ('/'+q['preview'][0] if q.get('preview') else '')

actual = {}
for sn, info in w['sheets'].items():
    rel = posixpath.join(posixpath.dirname(info['part']), '_rels', posixpath.basename(info['part'])+'.rels')
    rs = {r.get('Id'): r.get('Target') for r in E.fromstring(w['files'][rel])} if rel in w['files'] else {}
    for node in info['root'].iter(n.q('hyperlink')):
        target = '#'+node.get('location') if node.get('location') else rs[node.get('{'+n.R+'}id')]
        actual[(sn, node.get('ref'))] = target
assert len(actual) == len(plan['hyperlinks']) == 12206
assert all(actual[(h['sheet'], h['cell'])] == h['target'] and w['values'][h['sheet']][h['cell']] == h['label'] for h in plan['hyperlinks'])
file_map = {}
for fid, current in native.items():
    if current.get('object_type') != 'file' or fid not in saved:
        continue
    old = saved[fid]
    if old.get('image_url'):
        key = norm(old['image_url'])
        assert key not in file_map or file_map[key] == current['image_url']
        file_map[key] = current['image_url']
folder_map = {}
for fid, current in native.items():
    if current.get('object_type') != 'folder' or fid not in oldnative:
        continue
    old = oldnative[fid]
    oldurl = old.get('folder_url') or ('https://www.dropbox.com/home'+quote(old['display_path'],safe='/') if old.get('display_path') else None)
    if oldurl:
        folder_map[norm(oldurl)] = current['folder_url']
for c in replacement['changes']:
    file_map[norm(c['before']['image_url'])] = c['proposed']['image_url']
old_output = str(B/'outputs/current-six-url-case-navigation-master-2026-10-24')
new_output = str(B/'outputs'/H.name)

def protected(sheet, cell):
    col = cell.rstrip('0123456789')
    return sheet == 'Fingerprint History' or sheet == 'Source Specifications' and col in ['M', 'N'] or sheet == 'Moonphases and Dune' and col == 'I'

links = {(h['sheet'], h['cell']): h for h in plan['hyperlinks']}
for h in plan['hyperlinks']:
    if protected(h['sheet'], h['cell']):
        continue
    if h['target'].startswith(old_output+'/'):
        rerouted = new_output+h['target'][len(old_output):]
        if Path(rerouted.split('#')[0]).is_file():h['target']=rerouted
    if not h['target'].startswith('https://www.dropbox.com/'):continue
    key = norm(h['target'])
    # Keep equivalent /preview and /home URL syntax when no path changed.
    if key in file_map and norm(file_map[key]) != key:
        h['target'] = file_map[key]
    elif key in folder_map and norm(folder_map[key]) != key:
        h['target'] = folder_map[key]
pairings = {
    'Master Catalogue': [('Q', 'N', 'O', 'R')],
    'Specifications': [('L', 'J', 'K', 'M')],
    'Photo Coverage': [('M', 'D', 'E', 'N'), ('O', 'G', 'H', 'P'), ('Q', 'J', 'K', 'R')],
    'Missing Pictures': [('I', 'G', 'H', 'J')],
    'Identity Review': [('I', 'G', 'H', 'J'), ('N', 'L', 'M', 'P')],
    'Listing Reconciliation': [('O', 'M', 'N', 'P')],
    'Listing Issues': [('L', 'J', 'K', 'M')],
    'Listing Resolution': [('T', 'R', 'S', 'U')],
    'Selling Details': [('N', 'L', 'M', 'O')],
    'Platform Sources': [('W', 'U', 'V', 'X')],
    'Listing Offer Links': [('T', 'R', 'S', 'U')],
}
cell_changes = {}
def change(sheet, cell, value):
    before = w['values'][sheet].get(cell, '')
    if before != value:
        cell_changes[(sheet, cell)] = {'sheet': sheet, 'cell': cell, 'before': before, 'value': value}

replacement_source_paths = {norm(c['before']['image_url']) for c in replacement['changes']}
for h in plan['hyperlinks']:
    if protected(h['sheet'], h['cell']):
        continue
    before_target = actual[(h['sheet'], h['cell'])]
    if norm(before_target) in replacement_source_paths and any(word in h['label'].lower() for word in ['deleted', 'historical']):
        h['label'] = 'Image (current equivalent)'
        change(h['sheet'], h['cell'], h['label'])

for sn, blocks in pairings.items():
    values = w['values'][sn]
    for filecol, imagecol, foldercol, parentcol in blocks:
        for cell, fid in values.items():
            if not re.fullmatch(filecol+r'\d+', cell) or not isinstance(fid, str):
                continue
            selected = replacements.get(fid, fid)
            if selected not in native or native[selected].get('object_type') != 'file':
                continue
            row = cell[len(filecol):]
            reference = native[selected]
            if selected != fid:
                change(sn, cell, selected)
            change(sn, parentcol+row, reference['folder_id'])
            for column, field in [(imagecol, 'image_url'), (foldercol, 'folder_url')]:
                link = links.get((sn, column+row))
                if link and norm(link['target']) != norm(reference[field]):
                    link['target'] = reference[field]
# Source IDs in Source Mapping and Source Specifications remain original IDs.
# Their H/I current-navigation links can follow the referenced original file.
for sn in ['Source Mapping', 'Source Specifications']:
    for cell, fid in w['values'][sn].items():
        if re.fullmatch(r'J\d+', cell) and isinstance(fid, str) and fid in native:
            reference = native[fid]
            if reference.get('object_type') != 'file':
                continue
            for column, field in [('H', 'image_url'), ('I', 'folder_url')]:
                link = links.get((sn, column+cell[1:]))
                if link and norm(link['target']) != norm(reference[field]):
                    link['target'] = reference[field]
for sn, cells in [('Master Catalogue', ['V188', 'V190']), ('Photo Coverage', ['L188', 'L190'])]:
    for cell in cells:
        before = w['values'][sn][cell]
        assert 'No replacement or restore; owner hold retained.' in before
        change(sn, cell, before.replace('No replacement or restore; owner hold retained.', 'Current equivalent image reference verified and selected; original deletion history and owner hold retained. No Dropbox restoration.'))
header = '188 active options; full image-role review covers 6,360 current wall images. Local platform galleries and qualified matches linked; physical specifications and held identities remain qualified.'
change('Master Catalogue', 'A3', header)
links[('Master Catalogue', 'A3')].update(label=header, target=str(B / 'outputs' / H.name / 'index.html'))
changes = list(cell_changes.values())
plan.update(cell_changes=changes, value_blocks=[{'sheet': c['sheet'], 'range': c['cell'], 'values': [[c['value']]]} for c in changes],
    formula_changes=[], formula_blocks=[], row_heights=[], table_appends=[], new_sheets=[],
    baseline_ranges=[['Master Catalogue', 'A2:Y5', 'baseline-master-header'], ['Master Catalogue', 'N188:R190', 'baseline-wall-reference'], ['Photo Coverage', 'L188:N190', 'baseline-wall-coverage']],
    preview_ranges=[['Master Catalogue', 'A2:Y5', '01-master-header'], ['Master Catalogue', 'N188:R190', '02-wall-reference'], ['Photo Coverage', 'L188:N190', '03-wall-coverage']],
    supplemental_preview_ranges=[['Master Catalogue', 'T'+next(c[1:] for c,v in w['values']['Master Catalogue'].items() if re.fullmatch(r'A\d+',c) and v=='BSI-C02D6DF365D3')+':U'+next(c[1:] for c,v in w['values']['Master Catalogue'].items() if re.fullmatch(r'A\d+',c) and v=='BSI-C02D6DF365D3'), '04-context-navigation']],
    native_link_changes=[{'sheet': h['sheet'], 'cell': h['cell'], 'before': actual[(h['sheet'], h['cell'])], 'current': h['target']} for h in plan['hyperlinks'] if h['target'] != actual[(h['sheet'], h['cell'])]],
    actual_parent_cells=[c['sheet']+'!'+c['cell'] for c in changes if c['cell'].rstrip('0123456789') in ['M', 'N', 'P', 'R', 'U', 'X'] and c['value'].startswith('id:')])
assert all(not protected(h['sheet'], h['cell']) for h in plan['native_link_changes'])
write(H / 'workbook-edit-plan.json', plan)
write(H / 'expected-edit.json', {'sheets': {}, 'hyperlinks': plan['hyperlinks'], 'formulas': []})
print(json.dumps({'status': 'PLAN_READY', 'targeted_cell_value_changes': len(changes), 'native_hyperlink_target_changes': len(plan['native_link_changes']), 'formulas_or_tabs_changed': 0}, indent=2))
