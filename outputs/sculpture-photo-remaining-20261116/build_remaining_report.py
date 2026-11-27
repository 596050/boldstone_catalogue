import html
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[1]
checklist = ROOT / 'outputs/wall-sculpture-photo-folders-20261113'
inventory = json.loads((checklist / 'inventory-in-situ.json').read_text())
audit = json.loads((checklist / 'folder-audit.json').read_text())
processing = json.loads((ROOT / 'outputs/sculpture-aidefector-20261116/manifest.json').read_text())
mapping = json.loads((ROOT / 'outputs/sculpture-aidefector-20261116/dropbox-tabs.json').read_text())
candidate_mapping = json.loads((ROOT / 'outputs/sculpture-aidefector-20261116/candidate-folder-matches.json').read_text())
assert inventory['has_more'] is False
assert inventory['checked_at'] == audit['summary']['checked_at']
entries = inventory['entries']
by_id = {e['file_id']: e for e in entries}
by_path = {e['path'].casefold(): e for e in entries}
assert len(by_id) == len(entries)
children = defaultdict(list)
for entry in entries:
    children[entry['path'].rsplit('/', 1)[0].casefold()].append(entry)

EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.tif', '.tiff', '.heic', '.heif', '.avif', '.bmp', '.gif', '.dng', '.cr2', '.nef', '.arw'}


def is_image(entry):
    return entry['object_type'] == 'file' and Path(entry['name']).suffix.casefold() in EXTENSIONS


def folder_images(entry):
    prefix = entry['path'].casefold() + '/'
    return [e for e in entries if e['path'].casefold().startswith(prefix) and is_image(e)]


def folder_url(entry, fallback=None):
    if entry.get('path_display'):
        return 'https://www.dropbox.com/home' + quote(entry['path_display'], safe='/')
    if fallback:
        return fallback
    raise ValueError('No verified display path or earlier link')


verified_labels = set()
local_complete_labels = set()
local_output_files_present = 0
for group in processing['groups']:
    folder = Path(group['output_folder'])
    outputs = group['verified_outputs']
    assert group['status'] == 'processed_verified'
    assert group['verified_at'] and len(group['files']) == len(outputs)
    present = [f for f in outputs if Path(f['path']).is_file()]
    assert all(Path(f['path']).stat().st_size == f['size'] for f in present)
    local_output_files_present += len(present)
    if folder.is_dir() and len(present) == len(outputs):
        local_complete_labels.add(group['label'])
    verified_labels.add(group['label'])
processing_receipt = json.loads((ROOT / 'outputs/sculpture-aidefector-20261116/verification.json').read_text())
assert processing_receipt['verified_groups'] == len(verified_labels)
assert processing_receipt['verified_images'] == sum(len(g['verified_outputs']) for g in processing['groups'])
processed_ids = {m['file_id']: m for m in mapping if m['label'] in verified_labels}
assert len(processed_ids) == len(mapping)
pending_by_name = defaultdict(list)
for label, candidates in candidate_mapping.items():
    if label in verified_labels:
        for candidate in candidates:
            pending_by_name[candidate['name']].append(label)

rows = []
for old in audit['components']:
    component = by_id[old['component_id']]
    assert component['object_type'] in {'folder', 'mount'}
    row = {
        'name': component['name'], 'family': old['family'],
        'id': component['file_id'], 'path': component.get('path_display') or old['component_path'],
        'url': folder_url(component, old['component_url']), 'folders': {}, 'related_folders': [],
        'processing_status': 'processed' if component['file_id'] in processed_ids else ('identity_unconfirmed' if component['name'] in pending_by_name else 'not_in_processed_batch'),
        'possible_processed_sets': pending_by_name.get(component['name'], []),
    }
    for role, old_folder in old['folders'].items():
        if old_folder.get('folder_missing'):
            row['folders'][role] = {
                'id': None, 'name': role, 'path': None, 'url': row['url'],
                'image_count': 0, 'direct_item_count': 0, 'folder_missing': True,
            }
            continue
        folder = by_id.get(old_folder['id'])
        assert folder is not None, (row['name'], role)
        row['folders'][role] = {
            'id': folder['file_id'], 'name': folder['name'],
            'path': folder.get('path_display') or old_folder['path'],
            'url': folder_url(folder, old_folder['url']),
            'image_count': len(folder_images(folder)),
            'direct_item_count': len(children[folder['path'].casefold()]),
        }
    row['missing_roles'] = [role for role, folder in row['folders'].items() if not folder['image_count']]
    parent_children = children[component['path'].rsplit('/', 1)[0].casefold()]
    possible_related = [e for e in children[component['path'].casefold()] if e['object_type'] in {'folder', 'mount'} and e['file_id'] not in {f['id'] for f in row['folders'].values()}]
    possible_related += [e for e in parent_children if e['object_type'] in {'folder', 'mount'} and e['name'].casefold() == (component['name'] + ' Details').casefold()]
    for folder in possible_related:
        if not re.search(r'\b(?:details?|high resolution)\b', folder['name'], re.I):
            continue
        images = folder_images(folder)
        if not images:
            continue
        previous = next((r for r in old['related_folders'] if r['name'] == folder['name']), None)
        assert previous, folder['name']
        row['related_folders'].append({'id': folder['file_id'], 'name': folder['name'], 'url': folder_url(folder, previous['url']), 'image_count': len(images)})
    rows.append(row)

natural = lambda s: [int(t) if t.isdigit() else t.casefold() for t in re.split(r'(\d+)', s)]
rows.sort(key=lambda r: (natural(r['family']), natural(r['name'])))
remaining = [r for r in rows if r['processing_status'] == 'not_in_processed_batch' and r['missing_roles']]
uncertain_gaps = [r for r in rows if r['processing_status'] == 'identity_unconfirmed' and r['missing_roles']]
uncertain = [r for r in rows if r['processing_status'] == 'identity_unconfirmed']
counts = Counter(tuple(r['missing_roles']) for r in remaining)
summary = {
    'checked_at': inventory['checked_at'], 'component_count': len(rows),
    'processed_verified_sets': len(verified_labels),
    'processed_local_sets': len(local_complete_labels),
    'processed_local_output_files_present': local_output_files_present,
    'processed_matched_components': len(processed_ids),
    'unconfirmed_processed_sets': len(candidate_mapping),
    'confirmed_remaining_components': len(remaining),
    'both_folders_lack_images': counts[('High Resolution', 'In Detail')],
    'high_resolution_only_lacks_images': counts[('High Resolution',)],
    'detail_only_lacks_images': counts[('In Detail',)],
    'uncertain_components_with_gaps': len(uncertain_gaps),
    'uncertain_candidate_components': len(uncertain),
    'remaining_components_with_alternative_photo_folders': sum(bool(r['related_folders']) for r in remaining),
    'method': 'Current complete Dropbox inventory compared with the saved verified processing record, mapped by stable component IDs. Completed processing remains recorded after local outputs are removed. Local output availability is checked separately. Counts measure image-file presence in requested folders, including descendants; related named detail and high-resolution folders are linked separately. No visual quality or resolution review was performed. Processing absence is limited to the identified batch.',
}
assert len(rows) == len(audit['components'])
assert len(remaining) == sum(counts.values())
assert not {r['id'] for r in remaining} & set(processed_ids)
result = {'summary': summary, 'remaining': remaining, 'unconfirmed_candidates': uncertain, 'all_components': rows}
(BASE / 'remaining-components.json').write_text(json.dumps(result, indent=2) + '\n')

esc = html.escape


def photo_cell(folder):
    count = folder['image_count']
    text = f'{count} image' + ('s' if count != 1 else '') if count else 'No images'
    if folder.get('folder_missing'):
        text = 'Folder absent · open component'
    return f'<a class="{"present" if count else "missing"}" href="{esc(folder["url"], quote=True)}" target="_blank" rel="noopener noreferrer">{text}</a>'


def render_row(row):
    notes = []
    if row['processing_status'] == 'identity_unconfirmed':
        notes.append('May match a processed unnumbered set: ' + esc('; '.join(row['possible_processed_sets'])))
    for folder in row['related_folders']:
        notes.append(f'Existing alternative: <a href="{esc(folder["url"], quote=True)}" target="_blank" rel="noopener noreferrer">{esc(folder["name"])}</a> ({folder["image_count"]} images)')
    category = 'both' if len(row['missing_roles']) == 2 else ('detail' if row['missing_roles'] == ['In Detail'] else 'high')
    return f'<tr data-kind="{category}" data-text="{esc((row["family"] + " " + row["name"]).casefold(), quote=True)}"><td>{esc(row["family"])}</td><td><a href="{esc(row["url"], quote=True)}" target="_blank" rel="noopener noreferrer">{esc(row["name"])}</a></td><td>{photo_cell(row["folders"]["High Resolution"])}</td><td>{photo_cell(row["folders"]["In Detail"])}</td><td>{"<br>".join(notes) or "—"}</td></tr>'


table_head = '<thead><tr><th>Family</th><th>Component sculpture</th><th>High Resolution</th><th>In Detail</th><th>Existing pictures / identity notes</th></tr></thead>'
checked = datetime.fromisoformat(inventory['checked_at'].replace('Z', '+00:00')).astimezone(ZoneInfo('Europe/London')).strftime('%-d %B %Y, %H:%M %Z')
page = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Remaining sculpture photo folders</title><style>
body{font:16px/1.5 system-ui,sans-serif;background:#f7f6f2;color:#202722;margin:0}main{max-width:1480px;margin:auto;padding:40px 24px}h1{font:500 38px/1.1 Georgia,serif;margin:0 0 18px}h2{font:500 26px Georgia,serif;margin-top:42px}p{max-width:1050px}a{color:#235e51;text-underline-offset:3px}small,.muted{color:#657069}.counts{display:flex;gap:16px;flex-wrap:wrap;margin:26px 0}.counts div{background:white;border:1px solid #dce1d9;border-radius:8px;padding:16px 24px;min-width:145px}.counts strong{display:block;font-size:32px;line-height:1.2}input,select{font:inherit;padding:9px 12px;border:1px solid #b6c3bb;border-radius:5px;background:white}input{min-width:270px}.controls{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin:20px 0}.tablewrap{overflow:auto;background:white;border:1px solid #dce1d9;border-radius:8px}table{border-collapse:collapse;width:100%;font-size:14px}th,td{padding:13px;text-align:left;border-bottom:1px solid #e3e7e1;vertical-align:top}th{background:#eaf0e9;font-weight:600}td:nth-child(2){min-width:230px}td:last-child{max-width:390px}.missing{color:#a14428;font-weight:600}.present{color:#26735d}.note{background:#fff8e6;border-left:3px solid #d5aa52;padding:12px 18px}.foot{font-size:13px;color:#657069;margin-top:32px}[hidden]{display:none!important}
</style><main><h1>Remaining sculpture photo folders</h1>'''
page += f'<p><strong>{summary["confirmed_remaining_components"]} components</strong> have no matching set in the saved processing record and lack images in one or both requested Dropbox photo folders.</p><p class="muted">Dropbox checked {esc(checked)} · {len(rows)} catalogue components · {len(verified_labels)} verified processed sets, of which {len(processed_ids)} have confirmed component matches. {len(local_complete_labels)} complete sets currently remain in the local <em>Processed Sculptures</em> folder.</p>'
page += f'<div class="counts"><div><strong>{len(remaining)}</strong>Remaining components</div><div><strong>{summary["both_folders_lack_images"]}</strong>Both folders lack images</div><div><strong>{summary["detail_only_lacks_images"]}</strong>In Detail only</div><div><strong>{summary["high_resolution_only_lacks_images"]}</strong>High Resolution only</div><div><strong>{len(uncertain_gaps)}</strong>Uncertain matches with gaps</div></div>'
page += f'<p class="note">{summary["remaining_components_with_alternative_photo_folders"]} listed components already have pictures in alternative named folders, linked in the notes. An empty requested folder may need existing images processed or filed. Image presence does not establish photo quality or sufficient resolution.</p>'
page += '<div class="controls"><label>Find a component <input id="search" type="search" placeholder="Name or family"></label><label>Show <select id="kind"><option value="all">All remaining components</option><option value="both">Both folders lack images</option><option value="detail">In Detail only</option><option value="high">High Resolution only</option></select></label><span id="visible" aria-live="polite"></span></div><div class="tablewrap"><table id="remaining">' + table_head + '<tbody>' + ''.join(map(render_row, remaining)) + '</tbody></table></div>'
candidate_status = (f'{len(uncertain_gaps)} candidate components still lack images in one or both requested folders.' if uncertain_gaps else 'All candidate components below currently have images in both requested folders, so none add to the remaining photo gaps.')
page += f'<h2>Unnumbered processed sets</h2><p>{len(candidate_mapping)} processed sets have unnumbered source names. Their original component matches remain unconfirmed. {candidate_status}</p><div class="tablewrap"><table>' + table_head + '<tbody>' + ''.join(map(render_row, uncertain)) + '</tbody></table></div>'
page += f'<p class="foot">The {len(processed_ids)} components with confirmed verified processing records are excluded even if their Dropbox folders are still empty. Removing local processed copies does not undo completed processing. This list identifies gaps for the {len(rows)} established component/finish folders and checks Dropbox contents separately from processing history. Photo counts include image files in descendant folders. Full audit data: <a href="remaining-components.json">JSON</a>.</p></main>'
page += '<script>const input=document.getElementById("search"),kind=document.getElementById("kind"),rows=[...document.querySelectorAll("#remaining tbody tr")];function filter(){const q=input.value.trim().toLowerCase();let n=0;for(const row of rows){const show=row.dataset.text.includes(q)&&(kind.value==="all"||row.dataset.kind===kind.value);row.hidden=!show;if(show)n++;}document.getElementById("visible").textContent=n+" components shown";}input.addEventListener("input",filter);kind.addEventListener("change",filter);filter();</script></html>'
(BASE / 'remaining-components.html').write_text(page)
print(json.dumps(summary, indent=2))
