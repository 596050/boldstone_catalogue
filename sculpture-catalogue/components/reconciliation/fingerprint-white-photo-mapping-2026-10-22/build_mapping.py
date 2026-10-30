from pathlib import Path
from urllib.parse import quote, unquote
from html import escape
from collections import Counter
from datetime import datetime, timezone
import csv, hashlib, json, re, shutil, zipfile

ROOT = Path('/Users/tprice/Documents/boldstone')
JOB = Path(__file__).resolve().parent
OUT = ROOT / 'sculpture-catalogue/outputs/fingerprint-white-photo-mapping-2026-10-22'
OUT.mkdir(parents=True, exist_ok=True)
comparison = json.loads((JOB / 'panel-comparison.json').read_text())
readback = json.loads((JOB / 'placement-readback.json').read_text())
native = readback['listing']
meta = {x['id']: x for x in json.loads((JOB / 'reference-metadata.json').read_text())}
verified = json.loads((JOB / 'source-original-verification.json').read_text())['sources']
by_id = {x['file_id']: x for x in native['entries']}
folders = {x['name']: x for x in native['entries'] if x['object_type'] == 'folder'}
family = readback['family_folder']
assert native['has_more'] is False

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def display(p): return p.split('ns:202238505/', 1)[1] if p.startswith('ns:') else p
def folder_url(p): return 'https://www.dropbox.com/home' + quote(display(p), safe='/')
def image_url(p):
    folder, name = display(p).rsplit('/', 1)
    return folder_url(folder) + '?preview=' + quote(name, safe='')
def link(url, label): return '<a href="' + escape(url, quote=True) + '">' + escape(label) + '</a>'

refs = {}
descriptions = {1: 'Broad sweeping ridges, without an internal curl centre.', 2: 'Curl at the right edge in the numbered source view.', 3: 'Curl at the left edge in the numbered source view.'}
for num, source in enumerate(verified, 1):
    entry = by_id[source['id']]
    context = folders[f'Fingerprint Concentric {num} White In Situ']
    component = folders[f'Fingerprint Concentric {num} White']
    assert entry['file']['size'] == source['size']
    local = OUT / 'reference-originals' / Path(source['local_path']).name
    local.parent.mkdir(exist_ok=True)
    shutil.copy2(source['local_path'], local)
    assert sha(local) == source['sha256']
    refs[num] = {'number': num, 'name': f'Fingerprint Concentric {num}', 'finish': 'White', 'description': descriptions[num], 'folder_id': component['file_id'], 'folder_path': component['path'], 'folder_url': folder_url(component['path']), 'context_folder_id': context['file_id'], 'context_folder_path': context['path'], 'context_folder_url': folder_url(context['path']), 'reference_file_id': source['id'], 'reference_file_revision': meta[source['id']]['rev'], 'reference_image_url': image_url(entry['path']), 'reference_local_path': str(local.relative_to(OUT)), 'reference_sha256': source['sha256']}

photos = []
for photo in comparison['images']:
    p = Path(photo['local_path'])
    assert sha(p) == photo['source_sha256']
    assert all(x.get('numeric_top_agrees_with_visual', True) for x in photo['panels'])
    members = sorted({x['component_number'] for x in photo['panels']})
    detail = photo['image_number'] <= 4
    name = ' and '.join(f'Fingerprint Concentric {n}' for n in members) + ' White' + ('' if detail else ' In Situ')
    existing = folders.get(name)
    proposed = family['path_display'] + '/' + name
    copy = OUT / 'matched-photos' / name / p.name
    copy.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(p, copy)
    assert sha(copy) == photo['source_sha256']
    panels = []
    for panel in photo['panels']:
        n = panel['component_number']
        ref = refs[n]
        panels.append({'left_to_right_position': panel['left_to_right_position'], 'component_number': n, 'component_name': ref['name'], 'rotation_clockwise_degrees_from_numbered_reference': panel['rotation_clockwise_degrees'], 'whole_outline_visible': panel['whole_outline_visible'], 'component_folder_id': ref['folder_id'], 'component_context_folder_id': ref['context_folder_id'], 'reference_file_id': ref['reference_file_id'], 'reference_file_revision': ref['reference_file_revision'], 'reference_image_url': ref['reference_image_url'], 'reference_folder_url': ref['context_folder_url'], 'matching_basis': 'Full face compared against native numbered White original' if panel['whole_outline_visible'] else 'Truncated ridge pattern and overlapping wider photographs; whole face is not shown'})
    photos.append({'image_number': photo['image_number'], 'source_filename': p.name, 'source_local_path': str(p), 'source_sha256': photo['source_sha256'], 'source_bytes': p.stat().st_size, 'source_dropbox_file_id': 'Unbound', 'finish': 'White', 'image_role': photo['image_role'], 'match_status': 'VISUALLY_MATCHED_CURRENT_FOLDER_REFERENCES', 'left_to_right_component_numbers': [x['component_number'] for x in panels], 'visible_panels': panels, 'whole_arrangement_visible': not detail, 'isolated_individual_image_qualified': False, 'destination_folder_name': name, 'destination_folder_id': existing['file_id'] if existing else 'Unbound', 'destination_existing_path': existing['path'] if existing else None, 'destination_existing_url': folder_url(existing['path']) if existing else None, 'destination_proposed_flat_path': proposed, 'destination_parent_folder_id': family['id'], 'destination_parent_folder_url': folder_url(family['path_display']), 'destination_status': 'Existing matching folder; owner flattening pending' if existing else 'New flat folder required', 'sorted_copy_relative_path': str(copy.relative_to(OUT)), 'coverage_scope': 'Detail or partial arrangement; full-scene and isolated-photo gaps are not closed' if detail else 'Whole arrangement on brick wall; room/lifestyle and isolated-photo coverage are not inferred'})

counts = Counter(x['destination_folder_name'] for x in photos)
report = {'schema': 'boldstone-fingerprint-owner-photo-matches/v1', 'recorded_utc': datetime.now(timezone.utc).isoformat(), 'batch': 'White', 'status': 'MATCHED_AND_SORTED_LOCALLY', 'source_photos': 13, 'visible_panel_appearances': 33, 'whole_visible_panel_appearances': 27, 'current_numbered_components': 3, 'detail_or_partial_photos': 4, 'full_arrangement_photos': 9, 'arrangement_reference_groups': len(counts), 'placement_policy': 'Flat direct children of Fingerprint, repeating full member names; current native reference links retain verified observed paths until the owner moves them.', 'numbering_authority': 'Current owner-managed Concentric 1/2/3 White In Situ originals, by native file ID and revision.', 'native_listing_complete': True, 'native_objects_at_readback': len(native['entries']), 'dropbox_placement': 'Pending; original photographs are sorted in the local package.', 'legacy_canonical_crosswalk_inferred': False, 'new_physical_products_or_moulds_inferred': 0, 'new_listing_derivatives': 0, 'native_writes': 0, 'master_writes': 0, 'references': list(refs.values()), 'group_counts': dict(counts), 'photos': photos}
(JOB / 'photo-folder-matches.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
json_path = OUT / 'Fingerprint_13_White_Photo_Matches.json'
json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
csv_path = OUT / 'Fingerprint_13_White_Photo_Matches.csv'
fields = ['Image', 'Original filename', 'Panels left to right', 'Clockwise rotations from numbered reference', 'Image role', 'Folder name', 'Existing folder ID', 'Existing folder URL', 'Proposed flat path', 'Original SHA256']
with csv_path.open('w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f); w.writerow(fields)
    for p in photos: w.writerow([p['image_number'], p['source_filename'], ' / '.join(map(str, p['left_to_right_component_numbers'])), ' / '.join(str(x['rotation_clockwise_degrees_from_numbered_reference']) + ' degrees' for x in p['visible_panels']), p['image_role'], p['destination_folder_name'], p['destination_folder_id'], p['destination_existing_url'] or '', p['destination_proposed_flat_path'], p['source_sha256']])

prior_guide = ROOT / 'sculpture-catalogue/outputs/fingerprint-whatsapp-photo-mapping-2026-10-22/index.html'
style = re.search(r'<style>(.*?)</style>', prior_guide.read_text(), re.S).group(1)
parts = ['<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Fingerprint White — 13 photograph matches</title><style>' + style + '</style><main><h1>Fingerprint White — 13 photograph matches</h1><p>Three current numbered designs occur in this batch. Four photographs are details or partial arrangements; nine show a full two- or three-panel arrangement.</p><p class="pending">Unchanged originals are sorted by visible components and image role. Intended destinations are flat children of Fingerprint. Dropbox placement is pending. Close-ups do not qualify as complete isolated images.</p><p>' + link(folder_url(family['path_display']), 'Fingerprint folder') + ' · ' + link('Fingerprint_White_Matched_Photos.zip', 'Sorted White originals') + ' · ' + link(csv_path.name, 'Matching table') + ' · ' + link('../fingerprint-whatsapp-photo-mapping-2026-10-22/index.html', 'Earlier Cream batch') + '</p><h2>Current White references</h2><div class="refs">']
for n, r in refs.items():
    parts.append('<section class="card"><h3>' + escape(r['name']) + ' — White</h3><img src="' + quote(r['reference_local_path'], safe='/') + '" alt="White component ' + str(n) + ' original reference"><p>' + escape(r['description']) + '</p><p>' + link(r['reference_image_url'], 'Dropbox example image') + ' · ' + link(r['context_folder_url'], 'Containing In Situ folder') + ' · ' + link(r['folder_url'], 'White component folder') + '</p></section>')
parts.append('</div><h2>All matches</h2><table><thead><tr><th>Image</th><th>Panels, left → right</th><th>View</th></tr></thead><tbody>')
for p in photos: parts.append('<tr><td>' + link('#photo-' + str(p['image_number']), 'Image ' + str(p['image_number'])) + '</td><td>' + ' → '.join(map(str, p['left_to_right_component_numbers'])) + '</td><td>' + escape(p['image_role']) + '</td></tr>')
parts.append('</tbody></table><h2>Each photograph and its destination</h2><div class="photos">')
for p in photos:
    url = quote(p['sorted_copy_relative_path'], safe='/')
    existing = (' · ' + link(p['destination_existing_url'], 'Current matching folder')) if p['destination_existing_url'] else ''
    scope = 'Both panels are cropped; this is a detail reference.' if p['image_number'] <= 2 else 'One whole panel and part of its neighbour; this is a partial arrangement.' if p['image_number'] <= 4 else 'The complete arrangement is visible.'
    parts.append('<article class="card" id="photo-' + str(p['image_number']) + '"><h3>Image ' + str(p['image_number']) + '</h3><a href="' + url + '"><img src="' + url + '" alt="Supplied White photograph ' + str(p['image_number']) + '"></a><p><span class="badge">Left → right: ' + ' → '.join(map(str, p['left_to_right_component_numbers'])) + '</span></p><p>' + escape(scope) + '</p><p><strong>Folder</strong><br>' + escape(p['destination_folder_name']) + '<br><span class="muted">' + escape(p['destination_status']) + '; directly under ' + link(p['destination_parent_folder_url'], 'Fingerprint') + existing + '</span></p><p class="muted">Clockwise rotations from the numbered White reference views: ' + ' / '.join(str(x['rotation_clockwise_degrees_from_numbered_reference']) + '°' for x in p['visible_panels']) + '.</p><p>References: ' + ' · '.join(link(refs[n]['reference_image_url'], str(n) + ' image') + ' / ' + link(refs[n]['context_folder_url'], str(n) + ' folder') for n in sorted(p['left_to_right_component_numbers'])) + '</p><p class="muted">' + escape(p['source_filename']) + '</p></article>')
parts.append('</div><p class="muted">Original photographs, native IDs, revisions, hashes, view limitations and rotations are retained in ' + link(json_path.name, 'the detailed mapping') + '. No physical dimensions, stock, mould counts, platform links or legacy Left/Right identities have been inferred.</p></main></html>')
html_path = OUT / 'index.html'; html_path.write_text('\n'.join(parts))
zip_path = OUT / 'Fingerprint_White_Matched_Photos.zip'
with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    for p in photos: z.write(OUT / p['sorted_copy_relative_path'], arcname=str(Path(p['sorted_copy_relative_path']).relative_to('matched-photos')))
    z.write(csv_path, arcname=csv_path.name)
with zipfile.ZipFile(zip_path) as z:
    assert len([n for n in z.namelist() if n.endswith('.jpeg')]) == 13
    for p in photos: assert hashlib.sha256(z.read(str(Path(p['sorted_copy_relative_path']).relative_to('matched-photos')))).hexdigest() == p['source_sha256']
for url in re.findall(r'(?:href|src)="([^"]+)"', html_path.read_text()):
    if not url.startswith(('https://', '#')): assert (OUT / unquote(url)).exists(), url
assert sum(len(p['visible_panels']) for p in photos) == 33
assert sum(x['whole_outline_visible'] for p in photos for x in p['visible_panels']) == 27
assert all(str(Path(p['destination_proposed_flat_path']).parent) == family['path_display'] for p in photos)
verification = {'status': 'PASS', 'photos_mapped': 13, 'panel_appearances_mapped': 33, 'full_faces_compared_numerically': 27, 'full_face_numeric_and_visual_assignments_agree': True, 'truncated_faces_visually_matched': 6, 'detail_partial_photos': 4, 'full_arrangement_photos': 9, 'flat_destination_groups': len(counts), 'existing_matching_group_folders': sum(folders.get(n) is not None for n in counts), 'new_group_folders_required': sum(folders.get(n) is None for n in counts), 'original_copy_and_zip_hashes_preserved': True, 'reference_and_folder_native_ids_preserved': True, 'isolated_image_gaps_closed': 0, 'native_writes': 0, 'master_writes': 0, 'outputs': {p.name: {'sha256': sha(p), 'bytes': p.stat().st_size} for p in [json_path, csv_path, html_path, zip_path]}}
(JOB / 'verification.json').write_text(json.dumps(verification, indent=2) + '\n')
print(json.dumps({'status': verification['status'], 'groups': dict(counts), 'existing_matching_group_folders': verification['existing_matching_group_folders'], 'new_group_folders_required': verification['new_group_folders_required'], 'guide': str(html_path), 'zip': str(zip_path)}, ensure_ascii=False))
