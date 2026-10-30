"""Link the sealed depth-update image reader; no catalogue or workbook data edits."""
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil

H = Path(__file__).resolve().parent
B = H.parents[2]
OUT = B/'outputs'/H.name
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
rel = lambda p: str(Path(p).relative_to(B))
def write(path,value):
    path = Path(path)
    temp = path.with_name(path.name+'.current-reader-tmp')
    temp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    os.replace(temp,path)

assert not (H/'current-reader-publication-receipt.json').exists()
pointer_path = B/'current-master.json'
assert sha(pointer_path) == read(H/'publication-receipt.json')['current_master_pointer_sha256']
old = read(pointer_path)
release = read(H/'publication-receipt.json')
gallery_ref = read(H/'gallery-reference.json')
run = Path(gallery_ref['run'])
seal_path = run/'sealed-handoff.json'
assert sha(seal_path) == gallery_ref['sha256']
seal = read(seal_path)
assert seal['target_register_sha256'] == old['register_sha256'] and seal['target_workbook_sha256'] == old['workbook_sha256']
for path,digest in seal['files'].items():
    member = Path(path) if Path(path).is_absolute() else run/path
    assert sha(member) == digest,path
old_run = Path(old['current_published_gallery_projection']['readers']['product-images.html']).parent
for name in ['source-gallery-review.json','source-photo-correspondences.json','local-shopify-gallery-review.json',
             'local-shopify-gallery-import-readback.json','current-file-visual-roles.json']:
    assert sha(run/name) == sha(old_run/name),'Frozen source proof '+name
for key in ['register','workbook']:
    assert sha(B/old[key]) == old[key+'_sha256']
for path,digest in release['controls_sha256'].items():
    assert sha(path) == digest and read(path)['current_master_catalogue'] == old
readers = {name:str(run/name) for name in ['index.html','product-images.html','source-galleries.html','family-images.html']}
assert all(Path(path).is_file() for path in readers.values())
association = run/'source-association-review/summary.json'
association_review = run/'source-association-review/index.html'
assert association.is_file() and association_review.is_file()
source_index = OUT/'index.html'
navigation = OUT/'current-gallery-navigation.html'
text = source_index.read_text()
old_prefix = os.path.relpath(old_run,OUT)
assert old_prefix in text
text = text.replace(old_prefix,os.path.relpath(run,OUT)).replace('Earlier complete image-gallery snapshot','Current complete image-gallery reader')
text = text.replace('</h1>','</h1><p><a href="'+os.path.relpath(association_review,OUT)+'">Current source-association review: owner names and the shared Frozen Fish design link</a></p>',1)
navigation.write_text(text)
p = copy.deepcopy(old)
p['recorded_utc'] = datetime.now(timezone.utc).isoformat()
p['current_published_gallery_projection'] = {'status':'CURRENT30_WORKING_SPECIFICATION_PROPOSALS_AND_SOURCE_PROOF_RETAINED',
    'path':rel(seal_path),'sha256':sha(seal_path),'register_sha256':old['register_sha256'],'workbook_sha256':old['workbook_sha256'],
    'readers':readers,'counts':seal.get('counts',{}),'current_master_navigation':rel(navigation),
    'current_master_navigation_sha256':sha(navigation),'source_photo_proof_unchanged':True,
    'qualified_FFL1_design_reference_not_a_new_primary_or_exact_variant':True,'owner_questions_remaining_in_resumed_batch':0,'new_working_depth_estimates':0,'working_material_proposals':27,'working_face_size_estimates':3,'new_physical_measurements':0}
p['current_image_review_links'].update(all_links=rel(navigation),all_individual_option_galleries=readers['product-images.html'],
    complete_platform_galleries=readers['source-galleries.html'],complete_family_galleries=readers['family-images.html'],
    source_association_scope_review=rel(association_review),current_gallery_projection_seal=rel(seal_path),
    current_gallery_projection_seal_sha256=sha(seal_path))
p['current_source_association_scope'].update(path=rel(association),sha256=sha(association),review=rel(association_review),
    source_reader_seal=rel(seal_path),source_reader_seal_sha256=sha(seal_path),
    component_edge_gaps=65,existing_parent_family_associations_within_65=7,
    remaining_without_existing_component_or_parent_family_association=58,
    qualified_owner_shared_design_navigation_cases=1,remaining_without_direct_parent_or_design_navigation=57,
    owner_identity_questions_remaining_in_resumed_batch=0,new_exact_variant_assignments=0,
    interpretation='65 cases retain no explicit component/source edge. Seven have existing parent-family links;58 lack those explicit edges. One of those58 now has a qualified owner-confirmed design navigation to FFS2, leaving57 without any of these navigation scopes. No exact legacy variant is assigned.')
p['publication_receipt'] = rel(H/'current-reader-publication-receipt.json')
p['latest_master_metadata_change'] = {'status':'CURRENT_WORKING_PROPOSALS_IMAGE_READER_LINKS_ONLY','data_publication_receipt':rel(H/'publication-receipt.json'),
    'register_workbook_maps_and_owner_fields_unchanged':True}
allowed = {'recorded_utc','current_published_gallery_projection','current_image_review_links','current_source_association_scope','publication_receipt','latest_master_metadata_change'}
assert all(p[k] == old[k] for k in old if k not in allowed)
updates = {}
for path in release['controls_sha256']:
    value = read(path)
    value.update(updated_utc=p['recorded_utc'],current_master_catalogue=copy.deepcopy(p))
    for key in ['current_published_gallery_projection','current_image_review_links','current_source_association_scope','latest_master_metadata_change']:
        value[key] = copy.deepcopy(p[key])
    updates[Path(path)] = value
snapshots = {}
for path in [pointer_path,*updates]:
    snapshot = H/'inputs'/('before-current-reader-'+str(path.relative_to(B)).replace('/','__'))
    assert not snapshot.exists()
    shutil.copy2(path,snapshot)
    snapshots[path] = snapshot
try:
    assert sha(pointer_path) == release['current_master_pointer_sha256']
    for path,value in updates.items():
        write(path,value)
    write(pointer_path,p)
    assert read(pointer_path) == p
    for path,value in updates.items():
        assert read(path) == value and value['current_master_catalogue'] == p
    for key in ['register','workbook']:
        assert sha(B/p[key]) == p[key+'_sha256']
    receipt = {'status':'PASS_CURRENT_WORKING_PROPOSALS_READER_LINKS_PUBLISHED_AND_READ_BACK','recorded_utc':p['recorded_utc'],
        'current_master_pointer_sha256':sha(pointer_path),'preceding_pointer_sha256':sha(snapshots[pointer_path]),
        'register_sha256':p['register_sha256'],'workbook_sha256':p['workbook_sha256'],
        'controls_sha256':{str(x):sha(x) for x in updates},'current_reader_seal_sha256':sha(seal_path),
        'current_navigation':rel(navigation),'current_navigation_sha256':sha(navigation),
        'source_proof_JSON_files_unchanged':5,'new_identity_or_field_or_native_changes':0,
        'owner_questions_remaining_in_resumed_batch':0,'context_holds':22,'series_holds':1,
        'metadata_pointer_keys_changed':sorted(allowed)}
    write(H/'current-reader-publication-receipt.json',receipt)
    print(json.dumps(receipt,indent=2))
except BaseException:
    for path,snapshot in snapshots.items():
        shutil.copy2(snapshot,path)
    raise
