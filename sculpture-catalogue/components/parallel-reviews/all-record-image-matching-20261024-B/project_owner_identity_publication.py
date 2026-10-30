"""Project the four published owner decisions into a new, isolated reader.

The native inventory, source-photo proof, existing source links and historical
readers remain unchanged. Only the Main publisher can update the master pointer.
"""
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
import argparse
import hashlib
import html
import json
import shutil
import sqlite3
import subprocess
import sys

H = Path(__file__).resolve().parent
B = H.parents[2]
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
write = lambda p, v: Path(p).write_text(json.dumps(v, ensure_ascii=False, indent=2) + '\n')
e = lambda v: html.escape(str(v or ''), quote=True)
link = lambda u, label: '<a href="' + e(u) + '">' + e(label) + '</a>' if u else e(label)
parser = argparse.ArgumentParser()
parser.add_argument('--published-pointer-sha256', required=True)
args = parser.parse_args()
pointer_path = B / 'current-master.json'
assert sha(pointer_path) == args.published_pointer_sha256
pointer = read(pointer_path)
regpath = B / pointer['register']
assert sha(regpath) == pointer['register_sha256']
assert sha(B / pointer['workbook']) == pointer['workbook_sha256']
register = read(regpath)
active = set(register['active_option_ids'])
products = {p['product_id']: p for p in register['options'] if p['product_id'] in active}
assert len(products) == 188
source = H / 'published-projections/20261024T233018571196Z'
source_seal = source / 'sealed-handoff.json'
assert sha(source_seal) == '1b138c884ab5ad1b77c1c221d0b6202dd6e573170fcbf5476c22d778ab807b93'
original = sqlite3.connect('file:' + str(source / 'complete-image-platform-register.sqlite') + '?mode=ro', uri=True)
old = {pid: json.loads(blob) for pid, blob in original.execute('SELECT product_id,record_json FROM products')}
assert set(products) == set(old)
ffid, targetid = 'BSI-04D6E8690F30', 'BSI-FE10273D3655'
names = {'BSI-CCB6CA396E9C': 'Pale Blue Marbled', 'BSI-22DA74B2107E': 'Azure Blue and White Marbled', 'BSI-1B20DCA291BB': 'Brass with World Colours'}
expected = {
    'LEGACY-FFL1-FFS2-RELIEF': ('Same design', ffid),
    'WC-03-PATTERN': ('Pale Blue Marbled is the pattern name', 'BSI-CCB6CA396E9C'),
    'WC-06-PATTERN': ('azure blue and white marbled', 'BSI-22DA74B2107E'),
    'WC-07-PATTERN': ('Do brass with world colours', 'BSI-1B20DCA291BB'),
}
answers = []
for decision, (text, pid) in expected.items():
    resolution = products[pid]['current_owner_identity_resolution' if pid == ffid else 'current_owner_pattern_resolution']
    assert resolution['decision_id'] == decision and resolution['owner_answer_verbatim'] == text
    assert sha(resolution['seal']) == resolution['seal_sha256']
    assert sha(resolution['answer_path']) == resolution['answer_sha256']
    packet = read(resolution['answer_path'])
    assert packet['owner_answer_verbatim'] == text and packet['decision_id'] == decision
    for item in read(resolution['seal'])['files']:
        assert sha(item['path']) == item['sha256']
    answers.append({'decision_id': decision, 'product_id': pid, 'resolution': resolution})
for pid, name in names.items():
    assert products[pid]['owner_confirmed_pattern_name'] == name
    assert products[pid]['name'] == 'Wall Circle — ' + name
    assert products[pid]['master_fields'] == old[pid]['master_fields']
    assert products[pid]['current_owner_pattern_resolution']['native_pattern_or_variant_id_assigned'] is None
ff = products[ffid]
assert ff['current_owner_identity_resolution']['same_design_as_option_id'] == targetid
assert ff['canonical_component_id'] == products[targetid]['canonical_component_id'] == 'BC-FFS-2'
assert not ff.get('file_id') and ff.get('file_id') == old[ffid].get('file_id')
allowed_ids = set(names) | {ffid, targetid}
changes = []
for pid, product in products.items():
    keys = {k for k in set(product) | set(old[pid]) if product.get(k) != old[pid].get(k)}
    if keys:
        assert pid in allowed_ids, (pid, keys)
        changes.append({'product_id': pid, 'changed_fields': sorted(keys)})
    for key in ['file_id', 'folder_id', 'image_url', 'folder_url', 'context_file_id', 'context_folder_id']:
        assert product.get(key) == old[pid].get(key), (pid, key)

out = H / 'published-projections' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
out.mkdir(parents=True, exist_ok=False)
db = sqlite3.connect(out / 'complete-image-platform-register.sqlite')
original.backup(db)
original.close()
images = {fid: json.loads(blob) for fid, blob in db.execute('SELECT file_id,record_json FROM images')}
for pid, product in products.items():
    db.execute('UPDATE products SET name=?,family=?,record_json=? WHERE product_id=?', (product['name'], product.get('family'), json.dumps(product, ensure_ascii=False), pid))
reference = ff['owner_confirmed_design_reference']
fid = reference['file_id']
assert fid == products[targetid]['file_id']
im = images[fid]
for key in ['folder_id', 'image_url', 'folder_url']:
    assert reference[key] == im[key]
assert im['inventory_status'] == 'CURRENT_NATIVE_FILE_AND_ACTUAL_PARENT_VERIFIED'
aid = hashlib.sha256(('owner-shared-design|' + ffid + '|' + fid).encode()).hexdigest()[:24]
association = {'association_id': aid, 'product_id': ffid, 'file_id': fid, 'intended_use': 'owner_confirmed_shared_design_reference', 'association_status': 'OWNER_CONFIRMED_SHARED_DESIGN_REFERENCE_ONLY', 'image_url': im['image_url'], 'folder_url': im['folder_url'], 'folder_id': im['folder_id'], 'current_image_in_map': True, 'current_native_status': im['inventory_status'], 'visual_role': im['visual_role'], 'visual_role_status': im['visual_review_status'], 'evidence': [{'path': str(regpath), 'sha256': pointer['register_sha256'], 'product_id': ffid, 'details': {'current_owner_identity_resolution': ff['current_owner_identity_resolution'], 'owner_confirmed_design_reference': reference, 'selected_primary_changed': False, 'exact_legacy_specimen_or_sale_variant_assigned': False}}]}
db.execute('INSERT INTO associations VALUES(?,?,?,?,?,?)', (aid, ffid, fid, association['intended_use'], association['association_status'], json.dumps(association, ensure_ascii=False)))
per_product = defaultdict(dict)
for blob, in db.execute('SELECT record_json FROM associations'):
    row = json.loads(blob)
    image = images.get(row['file_id'], {})
    grouped = per_product[row['product_id']].setdefault(row['file_id'], {'file_id': row['file_id'], 'name': image.get('name'), 'visual_role': image.get('visual_role'), 'visual_review_status': image.get('visual_review_status'), 'image_url': image.get('image_url'), 'folder_url': image.get('folder_url'), 'native_status': image.get('inventory_status', 'NOT_IN_CURRENT_MAP'), 'association_statuses': [], 'evidence': []})
    if row['association_status'] not in grouped['association_statuses']:
        grouped['association_statuses'].append(row['association_status'])
    grouped['evidence'].append({'association_id': row['association_id'], 'intended_use': row['intended_use'], 'source_evidence': row['evidence']})
write(out / 'per-product-image-lists.json', {pid: list(rows.values()) for pid, rows in per_product.items()})
unchanged = ['source-gallery-review.json', 'source-photo-correspondences.json', 'local-shopify-gallery-review.json', 'local-shopify-gallery-import-readback.json', 'current-file-visual-roles.json']
for name in unchanged:
    shutil.copyfile(source / name, out / name)
    assert sha(source / name) == sha(out / name)
summary = read(source / 'summary.json')
summary.update({'status': 'PUBLISHED_OWNER_IDENTITY_DECISIONS_PROJECTED_FULL_REVIEW_RETAINED', 'recorded_utc': datetime.now(timezone.utc).isoformat(), 'baseline_pointer_sha256': args.published_pointer_sha256, 'held_identity_answers_complete': True, 'owner_identity_answers': 4, 'owner_identity_questions_remaining': 0, 'shared_design_reference_added': 1, 'new_exact_platform_variant_assignments': 0, 'next_work': ['Retain explicit source-photo uncertainty and owner-deferred photography.', 'Exact legacy/specimen and native selling-variant associations remain qualified; no owner naming question remains.']})
write(out / 'summary.json', summary)
db.execute('INSERT OR REPLACE INTO metadata VALUES(?,?)', ('integration_summary', json.dumps(summary, ensure_ascii=False)))
db.commit()
assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
assert db.execute('SELECT count(*) FROM source_product_links').fetchone()[0] == 260
db.close()
write(out / 'published-pointer-snapshot.json', pointer)
manifest = read(source / 'input-manifest.json')
manifest.update({str(regpath): pointer['register_sha256'], str(source_seal): sha(source_seal), str(out / 'published-pointer-snapshot.json'): sha(out / 'published-pointer-snapshot.json')})
for row in answers:
    manifest[row['resolution']['seal']] = row['resolution']['seal_sha256']
write(out / 'input-manifest.json', manifest)
write(out / 'owner-identity-projection.json', {'answers': answers, 'shared_design_association': association, 'all_four_identity_questions_resolved': True, 'exact_native_variant_assignments_added': 0, 'selected_primary_references_changed': 0, 'existing_source_product_edges_preserved': 260})
seed = Path(read(H / 'current-work.json')['run'])
with sqlite3.connect('file:' + str(seed / 'image-register.sqlite') + '?mode=ro', uri=True) as seed_db:
    seed_products = {pid: json.loads(blob) for pid, blob in seed_db.execute('SELECT product_id,record_json FROM products')}
all_changes = [{'product_id': pid, 'changed_fields': sorted(k for k in set(p) | set(seed_products[pid]) if p.get(k) != seed_products[pid].get(k))} for pid, p in products.items() if p != seed_products[pid]]
write(out / 'publication-rebase.json', {'status': 'PUBLISHED_OWNER_IDENTITY_DECISIONS_PROJECTED_ONLY', 'published_pointer_sha256': args.published_pointer_sha256, 'published_register_path': str(regpath), 'published_register_sha256': pointer['register_sha256'], 'previous_published_reader': str(source), 'previous_published_reader_sha256': sha(source_seal), 'frozen_review_handoff': str(source_seal), 'frozen_review_handoff_sha256': sha(source_seal), 'allowed_option_changes': all_changes, 'this_increment_option_changes': changes, 'unchanged_source_proof_files': {name: sha(out / name) for name in unchanged}, 'selected_reference_replacements': read(source / 'publication-rebase.json')['selected_reference_replacements'], 'this_increment_selected_reference_changes': 0, 'new_shared_design_reference': association, 'new_exact_variant_assignments': 0, 'native_or_canonical_or_platform_writes_by_this_projection': 0})
remaining = read(source / 'remaining-work.json')
remaining['recorded_utc'] = datetime.now(timezone.utc).isoformat()
remaining['held_identities'] = {'status': 'ALL_FOUR_OWNER_DECISIONS_RESOLVED_AND_PUBLISHED', 'owner_questions_remaining': [], 'answers': answers, 'exact_platform_configuration_limits_retained': True}
remaining['canonical_release'] = {'owner_thread': '01a144ab-1a7c-7223-a403-73a4d53d70ff', 'status': 'MAIN_PUBLICATION_APPLIED_AND_PROJECTED', 'published_register_path': str(regpath), 'published_register_sha256': pointer['register_sha256']}
for row in remaining['options_without_existing_source_component_association']:
    row['name'] = products[row['product_id']]['name']
    if row['product_id'] == ffid:
        row['owner_identity_resolution'] = 'SAME_RELIEF_DESIGN_AS_FFS2_CONFIRMED; exact legacy selling-variant assignment remains unverified'
write(out / 'remaining-work.json', remaining)
write(H / 'current-integration.json', {'run': str(out), 'summary': str(out / 'summary.json'), 'reader': str(out / 'index.html'), 'database': str(out / 'complete-image-platform-register.sqlite')})
subprocess.run([sys.executable, str(H / 'build_product_image_reader.py')], check=True, stdout=subprocess.DEVNULL)

# Preserve the historical 65-case cohort, distinguishing its new design answer
# from an unsupported exact selling-variant association.
gap = out / 'source-association-review'
gap.mkdir()
entries = read(H / 'association-gap-followup-20261025/all-65-case-dispositions.json')
for row in entries:
    product = products[row['product_id']]
    row['name'] = product['name']
    row['product_reader'] = str(out / 'products' / (row['product_id'] + '.html'))
    row['canonical_component_id'] = product.get('canonical_component_id')
    if row['product_id'] in names:
        row['owner_confirmed_pattern_name'] = names[row['product_id']]
        row['explanation'] = 'The owner confirmed the pattern name ' + names[row['product_id']] + '. The existing Wall Circle parent-family source link remains; no exact native selling-variant alias is inferred.'
    if row['product_id'] == ffid:
        row['disposition'] = 'OWNER_CONFIRMED_SHARED_DESIGN_EXACT_LEGACY_VARIANT_UNASSIGNED'
        row['explanation'] = 'The owner confirmed FFL1 and FFS2 share the same relief design. The FFS2 image and source galleries are available as qualified design context. No exact legacy primary photograph or selling-variant/SKU is assigned.'
        row['qualified_design_reference'] = reference
        row['qualified_design_source_refs'] = ['O049', 'O063', 'SH-DRAFT']
    for photo in row['selected_reference_source_photo_links']:
        photo['name'] = product['name']
        photo['source_gallery'] = photo['source_gallery'].replace(str(source), str(out))
write(gap / 'all-65-case-dispositions.json', entries)
gap_summary = {'status': 'ALL_65_HISTORICAL_CASES_REFRESHED_AFTER_OWNER_DECISIONS', 'explicit_component_source_edge_gaps': 65, 'existing_parent_family_associations': 7, 'without_explicit_component_or_parent_family_association': 58, 'additional_owner_confirmed_shared_design_navigation': 1, 'other_cases_without_component_family_or_owner_shared_design_association': 57, 'owner_identity_questions_remaining': 0, 'disposition_counts': dict(Counter(x['disposition'] for x in entries)), 'new_exact_variant_assignments': 0, 'frozen_source_edges_unchanged': 260}
write(gap / 'summary.json', gap_summary)
page = '<!doctype html><meta charset="utf-8"><title>Source association review</title><style>body{font:16px system-ui;max-width:1200px;margin:35px auto;padding:0 20px;line-height:1.5}td,th{padding:12px;border-bottom:1px solid #ddd;vertical-align:top;text-align:left}a{color:#1c6354}</style><h1>Source association review</h1><p>' + link('../index.html', 'Current catalogue image index') + '</p><p>The historical 65 options still lack explicit component-to-source selling-record associations. Seven have existing parent-family links. Frozen Fish FFL1 now also has an owner-confirmed shared-design relationship to FFS2, with qualified image and source-gallery navigation. The other 57 have no supported component, parent-family or owner-confirmed shared-design association in these local records. These counts are not missing-photograph counts.</p><p>All four owner identity questions are resolved. Existing exact platform configuration limits and photograph qualifications remain.</p><table><tr><th>Catalogue option</th><th>Current reference</th><th>Source association</th></tr>'
for row in sorted(entries, key=lambda x: x['name'].casefold()):
    picture = link(row['current_selected_image_url'], 'Selected image') if row['current_selected_image_url'] else 'No exact selected image'
    if row.get('qualified_design_reference'):
        picture = link(reference['image_url'], 'Shared-design image') + ' · ' + link(reference['folder_url'], 'Containing folder') + ' — qualified design context'
    elif row['current_selected_folder_url']:
        picture += ' · ' + link(row['current_selected_folder_url'], 'Containing folder')
    page += '<tr id="' + e(row['product_id']) + '"><td>' + link(row['product_reader'], row['name']) + '</td><td>' + picture + '</td><td>' + e(row['explanation']) + '</td></tr>'
(gap / 'index.html').write_text(page + '</table>')
(out / 'index.html').write_text('<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Catalogue image register</title><style>body{font:17px system-ui;max-width:950px;margin:45px auto;padding:0 20px;line-height:1.6}a{color:#1c6354}</style><h1>Catalogue image register</h1><p>All four owner decisions are included: FFL1 and FFS2 share the same relief design; the three confirmed Wall Circle pattern names are Pale Blue Marbled, Azure Blue and White Marbled, and Brass with World Colours.</p><ul><li>' + link('product-images.html', '188 product image lists') + '</li><li>' + link('source-galleries.html', '81 complete source galleries, including local Shopify records') + '</li><li>' + link('family-images.html', '60 family libraries containing all 6,360 reviewed current images') + '</li><li>' + link('source-association-review/index.html', 'Updated source association review') + '</li></ul><p>Each image retains its role, Dropbox image and containing-folder links, and qualifications. Group photographs remain context. Frozen Fish uses an explicitly qualified shared-design reference; an exact legacy specimen photograph and selling-variant assignment are not inferred.</p><p>Exact Dropbox photograph correspondences remain uncertain for 29 Squarespace and three Shopify gallery images, and four native image roles remain uncertain. The 22 installation gaps and one series gap remain deferred. No owner identity question remains.</p><p>' + link('remaining-work.json', 'Remaining evidence limits and deferrals') + ' · ' + link('owner-identity-projection.json', 'Recorded owner decisions') + '</p>')
assert sha(pointer_path) == args.published_pointer_sha256
assert sha(regpath) == pointer['register_sha256']
print(json.dumps({'projection': str(out), 'register_sha256': pointer['register_sha256'], 'owner_answers': 4, 'source_edges_retained': 260, 'new_exact_variant_assignments': 0, 'new_shared_design_reference': 1}))
