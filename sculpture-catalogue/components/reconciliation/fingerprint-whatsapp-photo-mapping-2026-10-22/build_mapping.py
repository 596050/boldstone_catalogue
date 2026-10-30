from pathlib import Path
from urllib.parse import quote, unquote
from collections import Counter
from datetime import datetime, timezone
from html import escape
import csv
import hashlib
import json
import re
import shutil
import zipfile

ROOT = Path('/Users/tprice/Documents/boldstone')
JOB = Path(__file__).resolve().parent
OUT = ROOT / 'sculpture-catalogue/outputs/fingerprint-whatsapp-photo-mapping-2026-10-22'
OUT.mkdir(parents=True, exist_ok=True)

numeric = json.loads((JOB / 'numeric-panel-comparison.json').read_text())
native = json.loads((JOB / 'flat-policy-native-readback.json').read_text())['listing']
placement = json.loads((JOB / 'current-placement-policy.json').read_text())
metadata = json.loads((JOB / 'current-reference-metadata.json').read_text())
originals = json.loads((JOB / 'source-original-verification.json').read_text())
assert native['has_more'] is False
folder_by_name = {r['name']: r for r in native['entries'] if r['object_type'] == 'folder'}
parent = {'file_id': placement['placement_parent_id'], 'path': placement['placement_parent_ns_path']}
parent_display = parent['path'].split('ns:202238505/', 1)[1]

def db_folder(path):
    return 'https://www.dropbox.com/home' + quote(path, safe='/')

def db_image(path):
    folder, name = path.rsplit('/', 1)
    return db_folder(folder) + '?preview=' + quote(name, safe='')

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

# Independently reviewed against all 13 supplied photographs and the three
# current native original photographs. Degrees describe clockwise rotation
# from each numbered source photograph, not a new component or size option.
visual = {
    1: [(1, 0), (2, 0), (3, 0)],
    2: [(2, 90), (1, 180)],
    3: [(2, 90), (1, 270)],
    4: [(2, 0), (1, 0)],
    5: [(2, 270), (1, 0)],
    6: [(2, 180), (1, 0)],
    7: [(2, 90), (1, 0), (3, 90)],
    8: [(2, 270), (1, 0), (3, 270)],
    9: [(2, 180), (1, 0), (3, 180)],
    10: [(1, 0), (3, 0)],
    11: [(2, 90), (1, 0)],
    12: [(2, 270), (1, 0), (3, 180)],
    13: [(2, 180), (1, 0), (3, 0)],
}
descriptions = {
    1: 'Broad sweeping ridges; the small centre of the curl lies outside the panel.',
    2: 'Curl meets the right edge in the current numbered source photograph.',
    3: 'Curl meets the left edge in the current numbered source photograph.',
}
components = {}
for num in (1, 2, 3):
    cream = folder_by_name[f'Fingerprint Concentric {num} Cream']
    context = folder_by_name[f'Fingerprint Concentric {num} Cream In Situ']
    ref = next(r for r in metadata['reference_files'] if f'Concentric {num} Cream In Situ/' in r['path_display'])
    verified = next(r for r in originals['sources'] if r['id'] == ref['id'])
    components[num] = {
        'number': num,
        'name': f'Fingerprint Concentric {num}',
        'finish_label': 'Cream',
        'visual_identifier': descriptions[num],
        'cream_folder_id': cream['file_id'],
        'cream_folder_path': cream['path'],
        'cream_folder_url': db_folder(cream['path'].split('ns:202238505/', 1)[1]),
        'context_folder_id': context['file_id'],
        'context_folder_path': context['path'],
        'context_folder_url': db_folder(context['path'].split('ns:202238505/', 1)[1]),
        'reference_file_id': ref['id'],
        'reference_file_revision': ref['rev'],
        'reference_file_path': ref['path_display'],
        'reference_image_url': db_image(ref['path_display']),
        'reference_local_path': verified['local_path'],
        'reference_sha256': verified['sha256'],
        'legacy_canonical_binding': 'Unbound - current folder numbering is not automatically a legacy LEFT/RIGHT crosswalk',
    }

photos = []
for item in numeric['images']:
    number = item['image_number']
    reviewed = visual[number]
    computed = [(p['ranking'][0]['component'], p['ranking'][0]['rotation_clockwise_deg']) for p in item['panels']]
    assert computed == reviewed, (number, computed, reviewed)
    source = Path(item['local_path'])
    assert sha(source) == item['source_sha256']
    members = sorted({n for n, _ in reviewed})
    group_name = ' and '.join(f'Fingerprint Concentric {n}' for n in members) + ' Cream In Situ'
    display = parent_display + '/' + group_name
    existing = next((f for f in native['entries'] if f['path'] == 'ns:202238505/' + display), None)
    copy = OUT / 'matched-photos' / group_name / source.name
    copy.parent.mkdir(parents=True, exist_ok=True)
    if not copy.exists():
        shutil.copy2(source, copy)
    assert sha(copy) == item['source_sha256']
    panels = []
    for pos, (member, rotation) in enumerate(reviewed, 1):
        ref = components[member]
        panels.append({
            'left_to_right_position': pos,
            'component_number': member,
            'component_name': ref['name'],
            'rotation_clockwise_degrees_from_current_reference': rotation,
            'component_cream_folder_id': ref['cream_folder_id'],
            'component_context_folder_id': ref['context_folder_id'],
            'reference_file_id': ref['reference_file_id'],
            'reference_file_revision': ref['reference_file_revision'],
            'reference_image_url': ref['reference_image_url'],
            'reference_folder_url': ref['context_folder_url'],
        })
    photos.append({
        'image_number': number,
        'source_filename': source.name,
        'source_local_path': str(source),
        'source_sha256': item['source_sha256'],
        'source_bytes': source.stat().st_size,
        'source_dropbox_file_id': 'Unbound',
        'source_dropbox_scope': 'No native ID bound for this local attachment; none of the ' + str(sum(f['object_type'] == 'file' for f in native['entries'])) + ' current Fingerprint file byte counts equals this attachment byte count.',
        'finish_label': 'Cream',
        'match_status': 'VISUALLY_MATCHED_CURRENT_NUMBERED_FOLDER_REFERENCES',
        'left_to_right_component_numbers': [n for n, _ in reviewed],
        'visible_panels': panels,
        'destination_folder_name': group_name,
        'destination_proposed_path': display,
        'destination_folder_id': existing['file_id'] if existing else 'Unbound',
        'destination_exists_in_current_inventory': existing is not None,
        'destination_parent_folder_id': parent['file_id'],
        'destination_parent_folder_url': db_folder(parent_display),
        'sorted_copy_relative_path': str(copy.relative_to(OUT)),
        'coverage_scope': 'Whole arrangement on brick wall; links to all visible component records. No isolated image or room/lifestyle coverage certification inferred.',
    })
    assert all(source.stat().st_size != f.get('file', {}).get('size') for f in native['entries'] if f['object_type'] == 'file')

group_counts = Counter(p['destination_folder_name'] for p in photos)
report = {
    'schema': 'boldstone-fingerprint-owner-photo-matches/v1',
    'recorded_utc': datetime.now(timezone.utc).isoformat(),
    'status': 'MATCHED_AND_SORTED_LOCALLY',
    'native_snapshot_used': 'flat-policy-native-readback.json',
    'native_snapshot_complete': True,
    'native_snapshot_objects': len(native['entries']),
    'source_photos': len(photos),
    'panel_appearances_matched': sum(len(p['visible_panels']) for p in photos),
    'current_numbered_components_used': 3,
    'arrangement_combinations': len(group_counts),
    'placement_policy': placement,
    'numbering_authority': 'Current native owner-managed Fingerprint Concentric 1/2/3 Cream In Situ folders and their original JPEGs.',
    'historical_42_position_guide_used_as_identity_authority': False,
    'match_scope': 'Photo-to-current-folder visual matching; not measured specifications, inventory, mould count, platform matching, or legacy canonical identity reconciliation.',
    'dropbox_placement': 'Pending; three required arrangement folder names are prepared in the sorted local package.',
    'source_originals_preserved': True,
    'new_listing_derivatives': 0,
    'native_writes': 0,
    'master_writes': 0,
    'components': list(components.values()),
    'group_counts': dict(group_counts),
    'photos': photos,
}
(JOB / 'photo-folder-matches.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
(OUT / 'Fingerprint_13_Photo_Matches.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
csv_path = OUT / 'Fingerprint_13_Photo_Matches.csv'
with csv_path.open('w', newline='', encoding='utf-8-sig') as f:
    fields = ['Image', 'Original filename', 'Panels from left to right', 'Clockwise rotations from numbered references', 'Finish', 'Arrangement destination', 'Destination folder ID', 'Destination status', 'Existing parent folder', 'Component reference folder IDs', 'Original SHA256']
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    for p in photos:
        w.writerow(dict(zip(fields, [p['image_number'], p['source_filename'], ' / '.join(map(str, p['left_to_right_component_numbers'])), ' / '.join(str(x['rotation_clockwise_degrees_from_current_reference']) + ' degrees' for x in p['visible_panels']), 'Cream', p['destination_folder_name'], p['destination_folder_id'], 'Existing' if p['destination_exists_in_current_inventory'] else 'New folder required', p['destination_parent_folder_url'], ' / '.join(x['component_context_folder_id'] for x in p['visible_panels']), p['source_sha256']])))

def link(url, text):
    return f'<a href="{escape(url, quote=True)}">{escape(text)}</a>'

parts = ['<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Fingerprint — 13 photograph matches</title><style>body{font:16px/1.5 system-ui,sans-serif;background:#f5f2ec;color:#242823;margin:0}main{max-width:1160px;margin:auto;padding:32px 20px}h1{line-height:1.15}h2{margin-top:2em}a{color:#145c64}table{border-collapse:collapse;width:100%;background:white}th,td{text-align:left;padding:10px;border-bottom:1px solid #ddd;vertical-align:top}.refs,.photos{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:20px}.card{background:white;border:1px solid #dedbd2;border-radius:10px;padding:16px;overflow-wrap:anywhere}.card img{width:100%;height:auto;display:block;border-radius:5px}.muted{color:#656960;font-size:14px}.badge{display:inline-block;background:#e4eee8;padding:3px 8px;border-radius:5px}.pending{background:#fff1d9;padding:12px;border-left:4px solid #b6752a}code{overflow-wrap:anywhere;white-space:normal}</style><main><h1>Fingerprint — 13 photograph matches</h1><p>All 13 supplied cream photographs are matched to the current Concentric 1, 2 and 3 folder references: 32 visible panel appearances across three arrangement combinations.</p><p class="pending">The unchanged originals are sorted into three proposed arrangement folders, each directly under Fingerprint. Full sculpture names are repeated for each group. Dropbox placement is pending; current reference links retain their observed paths until the owner removes the extra Concentric level. These photographs retain the whole arrangements, and the current master catalogue has not been changed.</p><p>' + link(db_folder(parent_display), 'Open Fingerprint family folder') + ' · ' + link('Fingerprint_Matched_Photos.zip', 'Download sorted original photographs') + ' · ' + link(csv_path.name, 'Download matching table') + '</p><h2>Current component references</h2><div class="refs">']
for num, c in components.items():
    local = OUT / 'reference-originals' / Path(c['reference_local_path']).name
    local.parent.mkdir(exist_ok=True)
    if not local.exists():
        shutil.copy2(c['reference_local_path'], local)
    assert sha(local) == c['reference_sha256']
    parts.append('<section class="card"><h3>' + escape(c['name']) + ' — Cream</h3><img src="' + quote(str(local.relative_to(OUT)), safe='/') + '" alt="Current original reference for component ' + str(num) + '"><p>' + escape(c['visual_identifier']) + '</p><p>' + link(c['reference_image_url'], 'Dropbox example image') + ' · ' + link(c['context_folder_url'], 'Containing In Situ folder') + ' · ' + link(c['cream_folder_url'], 'Cream component folder') + '</p></section>')
parts.append('</div><h2>All 13 matches</h2><p>Numbers below follow the current folder identities. Left-to-right order changes between photographs; rotating a panel does not create an additional sculpture.</p><table><thead><tr><th>Image</th><th>Panels, left → right</th><th>Arrangement group</th></tr></thead><tbody>')
for p in photos:
    parts.append('<tr><td>' + link('#photo-' + str(p['image_number']), 'Image ' + str(p['image_number'])) + '</td><td>' + ' → '.join(map(str, p['left_to_right_component_numbers'])) + '</td><td>' + ' + '.join(map(str, sorted(p['left_to_right_component_numbers']))) + ' — Cream In Situ</td></tr>')
parts.append('</tbody></table><h2>Photographs and precise destinations</h2><div class="photos">')
for p in photos:
    image_link = quote(p['sorted_copy_relative_path'], safe='/')
    parts.append('<article class="card" id="photo-' + str(p['image_number']) + '"><h3>Image ' + str(p['image_number']) + '</h3><a href="' + image_link + '"><img src="' + image_link + '" alt="Owner photograph ' + str(p['image_number']) + '"></a><p><span class="badge">Left → right: ' + ' → '.join(map(str, p['left_to_right_component_numbers'])) + '</span></p><p><strong>Destination folder</strong><br>' + escape(p['destination_folder_name']) + '<br><span class="muted">New folder required under ' + link(p['destination_parent_folder_url'], 'Fingerprint') + '</span></p><p class="muted">Clockwise rotations from the numbered references: ' + ' / '.join(str(x['rotation_clockwise_degrees_from_current_reference']) + '°' for x in p['visible_panels']) + '.</p><p>Component references: ' + ' · '.join(link(components[n]['reference_image_url'], str(n) + ' image') + ' / ' + link(components[n]['context_folder_url'], str(n) + ' folder') for n in sorted(p['left_to_right_component_numbers'])) + '</p><p class="muted">' + escape(p['source_filename']) + '</p></article>')
parts.append('</div><h2>Folder groups in the package</h2><table><thead><tr><th>Proposed folder</th><th>Images</th><th>Current Dropbox binding</th></tr></thead><tbody>')
for name in group_counts:
    nums = [str(p['image_number']) for p in photos if p['destination_folder_name'] == name]
    parts.append('<tr><td>' + escape(name) + '</td><td>' + ', '.join(nums) + '</td><td>Unbound — folder absent in complete current readback</td></tr>')
parts.append('</tbody></table><p class="muted">Stable native component folder and reference-file IDs, revisions and source hashes are retained in ' + link('Fingerprint_13_Photo_Matches.json', 'the machine-readable mapping') + '. Historical Left/Right catalogue identities and the earlier 42 positional folder guide are not remapped by this photo review. No dimensions, physical stock, mould totals, platform matches or photo-coverage completion are inferred.</p></main></html>')
html_path = OUT / 'index.html'
html_path.write_text('\n'.join(parts))
zip_path = OUT / 'Fingerprint_Matched_Photos.zip'
with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    for p in photos:
        src = OUT / p['sorted_copy_relative_path']
        z.write(src, arcname=str(Path(p['sorted_copy_relative_path']).relative_to('matched-photos')))
    z.write(csv_path, arcname=csv_path.name)

# Check the meaningful delivery properties: all 13 original byte streams occur
# once in the package, the visible-number assignments agree, and local links
# and target reference IDs are complete. This does not certify native upload.
with zipfile.ZipFile(zip_path) as z:
    for p in photos:
        name = str(Path(p['sorted_copy_relative_path']).relative_to('matched-photos'))
        assert hashlib.sha256(z.read(name)).hexdigest() == p['source_sha256']
    assert len([n for n in z.namelist() if n.endswith('.jpeg')]) == 13
for url in re.findall(r'(?:href|src)="([^"]+)"', html_path.read_text()):
    if url.startswith(('https://', '#')):
        continue
    assert (OUT / unquote(url)).exists(), url
verification = {
    'status': 'PASS',
    'source_photos_mapped': 13,
    'visible_panel_appearances_mapped': 32,
    'current_numbered_reference_components': 3,
    'arrangement_groups': len(group_counts),
    'new_arrangement_folders_required': 3,
    'all_sorted_copies_and_zip_members_match_original_sha256': True,
    'original_photographs_reconstructed_or_edited': False,
    'native_stable_folder_and_reference_file_ids_preserved': True,
    'native_uploads_or_moves': 0,
    'master_writes': 0,
    'outputs': {p.name: {'sha256': sha(p), 'bytes': p.stat().st_size} for p in [html_path, csv_path, OUT / 'Fingerprint_13_Photo_Matches.json', zip_path]},
}
(JOB / 'verification.json').write_text(json.dumps(verification, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'status': verification['status'], 'source_photos': 13, 'panel_appearances': 32, 'groups': dict(group_counts), 'html': str(html_path), 'zip': str(zip_path), 'zip_bytes': zip_path.stat().st_size}, ensure_ascii=False))
