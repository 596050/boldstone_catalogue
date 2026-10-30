"""Publish a precise source-association scope note; catalogue data stays fixed."""
import copy
from datetime import datetime, timezone
import hashlib
import html
import json
import os
from pathlib import Path
import shutil
from urllib.parse import parse_qs, unquote, urlparse

H = Path(__file__).resolve().parent
B = H.parents[2]
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
rel = lambda p: str(Path(p).relative_to(B))
def dropbox_path(url):
    if not url:
        return ''
    parsed = urlparse(url)
    path = unquote(parsed.path)
    for prefix in ['/home','/preview']:
        if path.startswith(prefix+'/'):
            path = path[len(prefix):]
            break
    preview = parse_qs(parsed.query).get('preview')
    return path.rstrip('/')+('/'+preview[0] if preview else '')
def write(path,value):
    path = Path(path)
    temp = path.with_name(path.name+'.scope-note-tmp')
    temp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    os.replace(temp,path)

assert not (H/'source-association-scope-publication-receipt.json').exists()
pointer_path = B/'current-master.json'
assert sha(pointer_path) == 'ef9363d00d6a31088a8b8fec6bffb87321a904b195ce529feb7ece30da4ffae0'
old = read(pointer_path)
register = read(B/old['register'])
options = {o['product_id']:o for o in register['options']}
prior = read(H/'current-gallery-link-publication-receipt.json')
source = B/'components/parallel-reviews/all-record-image-matching-20261024-B/association-gap-followup-20261025'
seal_path = source/'sealed-handoff.json'
assert sha(seal_path) == '45ab33056fa3f9879dcfd02eb4ab3127b9efd527c4049c7400ee4a74b57cd806'
seal = read(seal_path)
assert seal['canonical_register_sha256'] == old['register_sha256']
for path,digest in seal['files'].items():
    assert sha(source/path) == digest,path
rows = read(source/'all-65-case-dispositions.json')
parents = read(source/'existing-parent-family-links.json')
assert len(rows) == 65 and len({o['product_id'] for o in rows}) == 65 and len(parents) == 7
for row in rows:
    o = options[row['product_id']]
    assert row['name'] == o['name'] and row['canonical_component_id'] == o['canonical_component_id']
    assert dropbox_path(row['current_selected_image_url']) == dropbox_path(o['image_url'])
    assert dropbox_path(row['current_selected_folder_url']) == dropbox_path(o['folder_url'])
    assert not row['new_exact_variant_assignment']
for row in parents:
    assert row['offer_ref'] in options[row['product_id']]['related_platform_offer_refs']
    assert row['offer_ref'] in register['master_platform_association_overlays']
assert seal['scope']['component_edge_gaps'] == 65 and seal['scope']['remaining_without_existing_component_or_parent_family_association'] == 58
assert seal['scope']['new_exact_variant_assignments'] == 0
for key in ['register','workbook']:
    assert sha(B/old[key]) == old[key+'_sha256']

out = B/'outputs/whole-gallery-navigation-master-2026-10-24'
old_index = B/old['current_image_review_links']['all_links']
index = out/'current-catalogue.html'
text = old_index.read_text()
notice = '<aside><h2>Platform association scope</h2><p>'+html.escape(seal['scope']['suggested_current_wording'])+'</p><p><a href="'+html.escape(os.path.relpath(source/'index.html',out),quote=True)+'">Review all65 cases with sculpture images, containing folders and source links</a></p></aside>'
text = text.replace('</h1>','</h1>'+notice,1)
text = text.replace('65 active options without an existing platform-source association','65 active options without an existing component-to-source association')
index.write_text(text)
p = copy.deepcopy(old)
p['recorded_utc'] = datetime.now(timezone.utc).isoformat()
p['current_source_association_scope'] = {'status':seal['status'],'path':rel(seal_path),'sha256':sha(seal_path),
    'review':rel(source/'index.html'),'component_edge_gaps':65,'existing_parent_family_associations_within_65':7,
    'remaining_without_existing_component_or_parent_family_association':58,'photo_reuse_links':2,
    'new_exact_variant_assignments':0,'interpretation':seal['scope']['suggested_current_wording'],
    'dispositions':copy.deepcopy(seal['scope']['disposition_counts'])}
p['current_image_review_links'].update(all_links=rel(index),source_association_scope_review=rel(source/'index.html'))
p['next_catalogue_actions'][2] = 'Review29 Squarespace and3 Shopify exact-photo uncertainties and4 uncertain native roles.65 options lack component/source edges;7 already have parent Wall Circle family links;58 lack either in the checked local evidence.625 current files remain at family scope without an exact option edge.'
p['publication_receipt'] = rel(H/'source-association-scope-publication-receipt.json')
p['latest_master_metadata_change'] = {'status':'SOURCE_ASSOCIATION_SCOPE_WORDING_CLARIFIED_ONLY',
    'preceding_receipt':rel(H/'current-gallery-link-publication-receipt.json'),'register_workbook_maps_and_working_fields_unchanged':True}
allowed = {'recorded_utc','current_source_association_scope','current_image_review_links','next_catalogue_actions','publication_receipt','latest_master_metadata_change'}
assert all(p[k] == old[k] for k in old if k not in allowed)
updates = {}
snapshots = {}
for path,digest in prior['controls_sha256'].items():
    dest = Path(path)
    assert sha(dest) == digest
    value = read(dest)
    assert value['current_master_catalogue'] == old
    value.update(updated_utc=p['recorded_utc'],current_master_catalogue=copy.deepcopy(p))
    for key in ['current_source_association_scope','current_image_review_links','next_catalogue_actions','latest_master_metadata_change']:
        value[key] = copy.deepcopy(p[key])
    updates[dest] = value
for dest in [pointer_path,*updates]:
    snapshot = H/'inputs'/('before-source-scope-'+str(dest.relative_to(B)).replace('/','__'))
    assert not snapshot.exists()
    shutil.copy2(dest,snapshot)
    snapshots[dest] = snapshot
try:
    for dest,value in updates.items():
        write(dest,value)
    write(pointer_path,p)
    assert read(pointer_path) == p
    for dest,value in updates.items():
        assert read(dest) == value and value['current_master_catalogue'] == p
    for key in ['register','workbook']:
        assert sha(B/p[key]) == p[key+'_sha256']
    for key in ['current_asset_reference_map','current_native_reference_map']:
        assert sha(B/p[key]['path']) == p[key]['sha256']
    receipt = {'status':'PASS_SOURCE_ASSOCIATION_SCOPE_CLARIFIED_AND_READ_BACK','recorded_utc':p['recorded_utc'],
        'current_master_pointer_sha256':sha(pointer_path),'preceding_pointer_sha256':sha(snapshots[pointer_path]),
        'register_sha256':p['register_sha256'],'workbook_sha256':p['workbook_sha256'],
        'controls_sha256':{str(x):sha(x) for x in updates},'appendix_seal_sha256':sha(seal_path),
        'current_entry':rel(index),'current_entry_sha256':sha(index),'preceding_entry_unchanged_sha256':sha(old_index),
        'component_source_gaps':65,'existing_parent_family_links':7,'without_either_in_checked_scope':58,
        'canonical_option_or_physical_commercial_field_changes':0,'new_exact_variant_matches':0,'native_or_platform_writes':0,
        'only_pointer_metadata_keys_changed':sorted(allowed)}
    write(H/'source-association-scope-publication-receipt.json',receipt)
    print(json.dumps(receipt,indent=2))
except BaseException:
    for dest,snapshot in snapshots.items():
        shutil.copy2(snapshot,dest)
    raise
