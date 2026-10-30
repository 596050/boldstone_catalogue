"""Independent comparison: six URL corrections plus ten approved Moonwave moves."""
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone
import ast
import hashlib
import json
import posixpath
import xml.etree.ElementTree as ET
import zipfile
from urllib.parse import urlsplit, unquote, parse_qs, quote
from copy import deepcopy

ROOT = Path('/Users/tprice/Documents/boldstone/sculpture-catalogue')
LANE = Path(__file__).resolve().parent
CANDIDATE = ROOT / 'components/reconciliation/current-six-url-case-navigation-master-2026-10-24'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def load(p):
    return json.loads(Path(p).read_text())


def objsha(x):
    return hashlib.sha256(json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def dropbox_target(url):
    z = urlsplit(url)
    if (z.scheme, z.netloc) != ('https', 'www.dropbox.com'):
        return None
    path = unquote(z.path)
    route = next((prefix for prefix in ['/home', '/preview'] if path.startswith(prefix + '/')), None)
    if route is None:
        return None
    path = path[len(route):]
    preview = parse_qs(z.query).get('preview', [])
    if len(preview) > 1:
        return None
    if preview:
        path += '/' + preview[0]
    return (route, path, z.query, z.fragment)


def allowed_case_url(before, after, expected):
    if not isinstance(before, str) or not isinstance(after, str):
        return False
    b, a = dropbox_target(before), dropbox_target(after)
    targets = {dropbox_target(url)[1] for row in expected['rows'] for url in row['proposed'].values()}
    return bool(b and a and b[0] == a[0] and b[2:] == a[2:] and b[1].casefold() == a[1].casefold() and a[1] in targets and before != after)


def allowed_moved_image_url(before, after, moves):
    b, a = dropbox_target(before), dropbox_target(after)
    return bool(b and a and any(b[1] == m['old_path'] and a[1] == m['new_path'] for m in moves))


def allowed_moved_folder_pair(before, after, moves):
    b, a = dropbox_target(before), dropbox_target(after)
    return bool(b and a and b[0] == a[0] == '/home' and b[2:] == a[2:] == ('', '') and any(b[1] == m['old_path'].rsplit('/', 1)[0] and a[1] == m['new_path'].rsplit('/', 1)[0] for m in moves))


def diffs(a, b, path=''):
    if type(a) is not type(b):
        yield {'path': path, 'before': a, 'after': b}
    elif isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            p = path + '/' + str(k).replace('~', '~0').replace('/', '~1')
            if k not in a:
                yield {'path': p, 'operation': 'add', 'after': b[k]}
            elif k not in b:
                yield {'path': p, 'operation': 'remove', 'before': a[k]}
            else:
                yield from diffs(a[k], b[k], p)
    elif isinstance(a, list):
        if len(a) != len(b):
            yield {'path': path, 'operation': 'list-length', 'before': len(a), 'after': len(b)}
        else:
            for i, (x, y) in enumerate(zip(a, b)):
                yield from diffs(x, y, path + '/' + str(i))
    elif a != b:
        yield {'path': path, 'before': a, 'after': b}


if __name__ == '__main__':
    expected = load(LANE / 'expectations.json')
    moves = load(LANE / 'moonwave-scope-extension.json')['moves']
    by_id = {x['file_id']: x for x in moves}
    freeze = load(CANDIDATE / 'candidate-freeze.json')
    assert isinstance(freeze['frozen_artifacts'], dict)
    initial = dict(freeze['frozen_artifacts'])
    initial[str(CANDIDATE / 'candidate-freeze.json')] = sha(CANDIDATE / 'candidate-freeze.json')
    assert all(sha(p) == h for p, h in initial.items()), 'Candidate freeze guard mismatch'
    old_reg = load(expected['baseline_register']['path'])
    new_reg = load(CANDIDATE / 'canonical-master-register.json')
    assert sha(expected['baseline_register']['path']) == expected['baseline_register']['sha256']
    assert sha(expected['baseline_workbook']['path']) == expected['baseline_workbook']['sha256']
    reg_diffs = list(diffs(old_reg, new_reg))

    # Reuse only the independent XML reader function, never its old task runner.
    helper = ROOT / 'components/parallel-reviews/decowaves1-candidate-qa-20261024T040807Z/verify_decowaves1.py'
    function = next(n for n in ast.parse(helper.read_text()).body if isinstance(n, ast.FunctionDef) and n.name == 'read_xlsx')
    N = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main', 'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(helper), 'exec'))
    old_book, old_heights = read_xlsx(expected['baseline_workbook']['path'])
    new_book, new_heights = read_xlsx(CANDIDATE / 'master-workbook.pending')
    cell_diffs = list(diffs(old_book, new_book))
    height_diffs = list(diffs(old_heights, new_heights))
    old_formula = {(s, c): v['formula'] for s, cells in old_book.items() for c, v in cells.items() if v.get('formula') is not None}
    new_formula = {(s, c): v['formula'] for s, cells in new_book.items() for c, v in cells.items() if v.get('formula') is not None}
    old_links = {(s, c): v['hyperlink'] for s, cells in old_book.items() for c, v in cells.items() if v.get('hyperlink')}
    new_links = {(s, c): v['hyperlink'] for s, cells in new_book.items() for c, v in cells.items() if v.get('hyperlink')}
    replacements = {before: row['proposed'][field] for row in expected['rows'] for field, before in row['before'].items()}
    expected_options = json.loads(json.dumps(old_reg['options']))
    for o in expected_options:
        row = next((r for r in expected['rows'] if r['option_id'] == o['product_id']), None)
        if row:
            assert o['file_id'] == row['expected_file_id'] and o['folder_id'] == row['expected_folder_id']
            o.update(row['proposed'])
    expected_edges = deepcopy(old_reg['source_offer_edges'])
    source_edge = expected_edges[15]
    assert source_edge['offer_ref'] == 'O016' and source_edge['current_primary_reference']['file_id'] == 'id:cnqzTNngPVsAAAAAAArp1g'
    m = by_id['id:cnqzTNngPVsAAAAAAArp1g']
    folder = m['new_path'].rsplit('/', 1)[0]
    source_edge['current_primary_reference'].update(folder_id=m['new_parent_id'], folder_url='https://www.dropbox.com/home'+quote(folder, safe='/'), image_url='https://www.dropbox.com/home'+quote(folder, safe='/')+'?preview='+quote(m['new_path'].rsplit('/', 1)[1]))
    checks = {
        'all_189_options_change_only_the_twelve_proposed_current_urls': expected_options == new_reg['options'],
        'all_189_full_working_field_objects_unchanged': all(objsha(o['master_fields']) == expected['all_option_field_hashes'][o['product_id']] for o in new_reg['options']),
        'eight_full_source_identity_hold_objects_unchanged': all(objsha(new_reg[k]) == v for k, v in expected['source_and_identity_hashes'].items() if k != 'source_offer_edges'),
        'all_retained_source_edges_only_O016_own_file_current_navigation_changes': expected_edges == new_reg['source_offer_edges'],
        '28_sheet_names_and_order_unchanged': list(old_book) == list(new_book) and len(new_book) == 28,
        'all_3407_formulas_unchanged': old_formula == new_formula and len(new_formula) == 3407,
        '12206_link_slots_unchanged': set(old_links) == set(new_links) and len(new_links) == 12206,
        'external_links_only_six_case_files_or_approved_Moonwave_targets': all(allowed_case_url(old_links[k], new_links[k], expected) or allowed_moved_image_url(old_links[k], new_links[k], moves) or allowed_moved_folder_pair(old_links[k], new_links[k], moves) for k in old_links if old_links[k] != new_links[k] and (old_links[k].startswith('http') or new_links[k].startswith('http'))),
        'frozen_artifacts_unchanged_during_inspection': all(sha(p) == h for p, h in initial.items()),
    }
    report = {'status': 'PRELIMINARY_COMPARISON_REQUIRES_SCOPE_REVIEW', 'recorded_utc': datetime.now(timezone.utc).isoformat(),
              'candidate': str(CANDIDATE), 'candidate_register_sha256': sha(CANDIDATE / 'canonical-master-register.json'),
              'candidate_workbook_sha256': sha(CANDIDATE / 'master-workbook.pending'), 'frozen_artifacts': initial,
              'independent_reader': {'path': str(helper), 'sha256': sha(helper), 'function': 'read_xlsx'},
              'preliminary_checks': checks, 'register_differences': reg_diffs, 'workbook_cell_differences': cell_diffs,
              'workbook_height_differences': height_diffs, 'native_calls': 0, 'shared_writes': 0}
    with (LANE / 'preliminary-comparison.json').open('x') as f:
        json.dump(report, f, ensure_ascii=False, indent=2); f.write('\n')
    print(json.dumps({'status': report['status'], 'checks': checks, 'register_change_groups': dict(Counter(x['path'].split('/')[1] for x in reg_diffs)),
                      'workbook_change_groups': dict(Counter(x['path'].split('/')[1] for x in cell_diffs)),
                      'height_changes': len(height_diffs), 'external_link_changes': sum(old_links[k] != new_links[k] and old_links[k].startswith('http') for k in old_links)}, indent=2))
