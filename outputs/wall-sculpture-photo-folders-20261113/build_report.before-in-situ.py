import html
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote


BASE = Path(__file__).resolve().parent
plan = json.loads((BASE / 'folder-plan.json').read_text())
before = json.loads((BASE / 'inventory-before.json').read_text())
after = json.loads((BASE / 'inventory-after.json').read_text())
assert after['has_more'] is False, 'The final Dropbox scan is incomplete'
entries = after['entries']
assert len({e['file_id'] for e in entries}) == len(entries)
by_path = {e['path'].casefold(): e for e in entries}
by_id = {e['file_id']: e for e in entries}
children = defaultdict(list)
for entry in entries:
    children[entry['path'].rsplit('/', 1)[0].casefold()].append(entry)

receipts = [json.loads(line) for line in (BASE / 'creation-receipts.jsonl').read_text().splitlines()]
successful = [r for r in receipts if r.get('status') in {'created', 'recovered_existing'}]
creations = {r['response']['folder']['file_id']: r for r in successful if r.get('status') == 'created'}
created_paths = {r['response']['folder']['path'].casefold() for r in creations.values()}
assert len(created_paths) == len(creations), 'Duplicate creation receipt'
assert len(created_paths) == len(plan['create']), 'Some planned folders lack creation receipts'
for folder_id, receipt in creations.items():
    actual = by_id[folder_id]
    assert actual['path'].casefold() == receipt['requested']['path'].casefold()
    assert actual['name'] == receipt['requested']['name']
    assert actual['object_type'] == 'folder'


def display_path(entry):
    receipt = creations.get(entry['file_id'])
    if receipt:
        f = receipt['response']['folder']
        if f.get('path_display'):
            return f['path_display']
    if entry.get('path_display'):
        return entry['path_display']
    return '/' + entry['path'].split('//', 1)[1]


def link(entry):
    return 'https://www.dropbox.com/home' + quote(display_path(entry), safe='/')


rows = []
targets = []
for component in plan['components']:
    current_component = by_id[component['file_id']]
    assert current_component['path'].casefold() == component['path'].casefold()
    row = {
        'name': current_component['name'],
        'family': component['family'],
        'component_id': current_component['file_id'],
        'component_path': display_path(current_component),
        'component_url': link(current_component),
        'folders': {},
        'related_folders': [],
    }
    for target in component['targets']:
        entry = by_path[target['path'].casefold()]
        assert entry['object_type'] in {'folder', 'mount'}
        assert entry['name'].casefold() == target['name'].casefold()
        contents = children[entry['path'].casefold()]
        record = {
            'role': target['role'],
            'name': entry['name'],
            'id': entry['file_id'],
            'path': display_path(entry),
            'url': link(entry),
            'empty': len(contents) == 0,
            'child_count': len(contents),
            'file_count': sum(c['object_type'] == 'file' for c in contents),
            'created': entry['file_id'] in creations,
        }
        row['folders'][target['role']] = record
        targets.append(record)
    required_ids = {f['id'] for f in row['folders'].values()}
    # Preserve and link pre-existing folders whose names differ from the requested names.
    for sibling in children[current_component['path'].casefold()]:
        if sibling['object_type'] not in {'folder', 'mount'} or sibling['file_id'] in required_ids:
            continue
        row['related_folders'].append({
            'name': sibling['name'], 'url': link(sibling),
            'child_count': len(children[sibling['path'].casefold()]),
        })
    # Detail photographs already held beside, rather than within, the component directory.
    parent_children = children[current_component['path'].rsplit('/', 1)[0].casefold()]
    for sibling in parent_children:
        if sibling['object_type'] in {'folder', 'mount'} and sibling['name'].casefold() == (current_component['name'] + ' Details').casefold():
            row['related_folders'].append({
                'name': sibling['name'], 'url': link(sibling),
                'child_count': len(children[sibling['path'].casefold()]),
            })
    rows.append(row)

empty_targets = [f for f in targets if f['empty']]
empty_rows = [r for r in rows if any(f['empty'] for f in r['folders'].values())]
before_ids = {e['file_id'] for e in before['entries']}
after_ids = set(by_id)
other_additions = [by_id[fid] for fid in (after_ids - before_ids) - set(creations)]
assert all(e['object_type'] == 'file' for e in other_additions), 'Additional folders require a scope recheck'
assert set(creations) <= after_ids - before_ids, 'A created folder was already present in the opening inventory'
assert before_ids <= after_ids, 'An original Dropbox item disappeared during the operation'
file_changes = []
for old in before['entries']:
    if old['object_type'] != 'file':
        continue
    new = by_id[old['file_id']]
    fields = ['name', 'path', 'modified_time', 'file']
    if any(old.get(k) != new.get(k) for k in fields):
        file_changes.append(old['file_id'])
assert not file_changes, 'Original file metadata changed during the operation'

summary = {
    'checked_at': after['checked_at'], 'component_finish_folders': len(rows),
    'families': len({r['family'].casefold() for r in rows}),
    'required_folders': len(targets), 'created': len(creations),
    'already_present': len(plan['existing']), 'empty_folders': len(empty_targets),
    'empty_high_resolution': sum(f['role'] == 'High Resolution' for f in empty_targets),
    'empty_in_detail': sum(f['role'] == 'In Detail' for f in empty_targets),
    'component_finish_folders_with_empty_folders': len(empty_rows),
    'populated_folders': sum(not f['empty'] for f in targets),
    'original_files_preserved': sum(e['object_type'] == 'file' for e in before['entries']),
    'original_file_metadata_changes': len(file_changes),
    'additional_files_observed': len(other_additions),
    'recursive_pages_after': after['pages'], 'final_listing_complete': True,
}
(BASE / 'folder-audit.json').write_text(json.dumps({'summary': summary, 'components': rows, 'additional_files_observed': other_additions}, indent=2) + '\n')
(BASE / 'empty-folder-links.json').write_text(json.dumps({'summary': summary, 'components': empty_rows}, indent=2) + '\n')

esc = html.escape


def cell(folder):
    status = 'Empty' if folder['empty'] else f"{folder['child_count']} item(s)"
    origin = 'Created today' if folder['created'] else 'Already existed'
    return (f'<td><a href="{esc(folder["url"], quote=True)}" target="_blank" rel="noopener noreferrer">'
            f'{esc(folder["name"])}</a><br><span class="{"empty" if folder["empty"] else "filled"}">'
            f'{status}</span> <small>{origin}</small></td>')


table_rows = []
for row in rows:
    has_empty = any(f['empty'] for f in row['folders'].values())
    notes = '<br>'.join(
        f'<a href="{esc(n["url"], quote=True)}" target="_blank" rel="noopener noreferrer">{esc(n["name"])}</a>'
        f' <small>({n["child_count"]} item(s))</small>' for n in row['related_folders']
    )
    search = esc((row['name'] + ' ' + row['family']).lower(), quote=True)
    table_rows.append(
        f'<tr data-search="{search}" data-empty="{str(has_empty).lower()}">'
        f'<td><a class="component" href="{esc(row["component_url"], quote=True)}" target="_blank" rel="noopener noreferrer">'
        f'{esc(row["name"])}</a><br><small>{esc(row["family"])}</small></td>'
        + cell(row['folders']['High Resolution']) + cell(row['folders']['In Detail'])
        + f'<td class="notes">{notes or "—"}</td></tr>'
    )

page = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Boldstone — Empty sculpture photo folders</title><style>
*{box-sizing:border-box}body{margin:28px;font:15px/1.5 system-ui,sans-serif;background:#f7f8f5;color:#25372c}
h1{font-size:28px;margin-bottom:8px}p{max-width:1050px}a{color:#1e6846;text-underline-offset:3px}
.summary{padding:14px 18px;background:#e8efe7;border-radius:8px;max-width:1100px}.controls{display:flex;gap:20px;align-items:center;flex-wrap:wrap;margin:22px 0}
input[type=search]{padding:11px;border:1px solid #b5c3b5;border-radius:5px;width:430px;max-width:90vw}
table{width:100%;border-collapse:collapse;background:#fff}th,td{padding:14px;text-align:left;border-bottom:1px solid #dce4d9;vertical-align:top}
th{background:#e8efe7;position:sticky;top:0}td{width:25%;overflow-wrap:anywhere}small{color:#657164}.component{font-weight:650}
.empty{display:inline-block;padding:2px 7px;border-radius:4px;background:#fff0d7;color:#89550e;margin-top:7px}.filled{display:inline-block;padding:2px 7px;background:#e8f4e8;border-radius:4px;margin-top:7px}
.notes{font-size:13px}.footnote{font-size:13px;color:#5d6b5b;margin-top:22px}tr[hidden]{display:none}
@media(max-width:850px){body{margin:16px}.tablewrap{overflow-x:auto}table{min-width:950px}}
</style><h1>Empty sculpture photo folders</h1>
'''
page += f'<p class="summary"><strong>{summary["empty_folders"]} empty folders</strong>: {summary["empty_high_resolution"]} High Resolution and {summary["empty_in_detail"]} In Detail, across {len(empty_rows)} component and finish folders.<br>{len(rows)} component and finish folders checked · {len(creations)} folders created · {len(plan["existing"])} required folders already existed.<br><small>Verified {esc(after["checked_at"])}.</small></p>'
page += '<p>Each folder name uses the full name of its existing component and finish folder. Open a linked empty folder to add photographs. The list shows folders with no files or subfolders at the time of the check.</p>'
page += '<p>Existing folders with different names are linked in the last column. This includes two “Batersea” High Resolution folders and existing sibling Details folders; photographs there remain in their original locations.</p>'
page += '<div class="controls"><input id="search" type="search" placeholder="Search component or family…" aria-label="Search component or family"><label><input id="showAll" type="checkbox"> Include components whose two folders are populated</label><span id="count"></span></div>'
page += '<div class="tablewrap"><table><thead><tr><th>Component and finish</th><th>[Name] High Resolution</th><th>[Name] In Detail</th><th>Existing related folders</th></tr></thead><tbody>' + ''.join(table_rows) + '</tbody></table></div>'
page += '<p class="footnote">All individual component and finish folders in the Wall Sculptures tree were checked, including existing Wall Circle pattern-source folders. Arrangement, In Situ, workshop, scene and catalogue document folders are outside the per-component folder list. The audit confirmed all original files remained at their original paths with unchanged recorded metadata.</p>'
page += '<p class="footnote">To undo these additions, request removal of the folders marked “Created today.” Their contents would be checked and deletion would require separate explicit confirmation. <a href="folder-audit.json">Full audit and exact folder paths</a> · <a href="empty-folder-links.json">Empty-folder list as JSON</a></p>'
page += '''<script>
const search=document.getElementById('search'),showAll=document.getElementById('showAll'),rows=[...document.querySelectorAll('tbody tr')];
function update(){let count=0;for(const row of rows){row.hidden=!(row.dataset.search.includes(search.value.toLowerCase())&&(showAll.checked||row.dataset.empty==='true'));if(!row.hidden)count++;}document.getElementById('count').textContent=count+' component and finish folders';}
search.addEventListener('input',update);showAll.addEventListener('change',update);update();
</script></html>'''
(BASE / 'empty-folder-list.html').write_text(page)
(BASE / 'verification.json').write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps(summary, indent=2))
