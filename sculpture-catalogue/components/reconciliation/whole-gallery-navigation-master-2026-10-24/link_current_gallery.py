"""Link the separately sealed current reader without rewriting frozen source proof."""
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

H = Path(__file__).resolve().parent
B = H.parents[2]
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
rel = lambda p: str(Path(p).relative_to(B))
def write(p,value):
    p = Path(p)
    tmp = p.with_name(p.name+'.current-gallery-tmp')
    tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    os.replace(tmp,p)

assert not (H/'current-gallery-link-publication-receipt.json').exists()
pointer_path = B/'current-master.json'
assert sha(pointer_path) == '5638de40cee85948c4c1df49828b2efd475789d8026db998ca3c758b92a5f7b4'
original = read(pointer_path)
release = read(H/'publication-receipt.json')
q = B/'components/parallel-reviews/all-record-image-matching-qa-01a16dbc-20261024/postpublication/sealed-publication-readback.json'
assert sha(q) == '8502762e43ec406a3ae39798fda3c83d42065ae9766c9280aae71f8b1c7430ad'
run = B/'components/parallel-reviews/all-record-image-matching-20261024-B/published-projections/20261024T233018571196Z'
seal_path = run/'sealed-handoff.json'
assert sha(seal_path) == '1b138c884ab5ad1b77c1c221d0b6202dd6e573170fcbf5476c22d778ab807b93'
seal = read(seal_path)
assert seal['published_pointer_sha256'] == sha(pointer_path)
assert seal['published_register_sha256'] == original['register_sha256']
assert seal['all188_product_objects_equal_published_register']
assert seal['held_identities_and_22_installation_and_one_series_deferrals_retained']
for path,digest in seal['files'].items():
    member = Path(path) if Path(path).is_absolute() else run/path
    assert sha(member) == digest, path
for key in ['register','workbook']:
    assert sha(B/original[key]) == original[key+'_sha256']
for path,digest in release['controls_sha256'].items():
    assert sha(path) == digest, path

out = B/'outputs/whole-gallery-navigation-master-2026-10-24'
source_index = out/'index.html'
current_index = out/'current-gallery-navigation.html'
text = source_index.read_text()
frozen_run = Path(original['current_complete_gallery_mapping']['source_gallery_handoff']['path']).parent
old_reader_prefix = os.path.relpath(frozen_run,out)
new_reader_prefix = os.path.relpath(run,out)
assert old_reader_prefix in text
text = text.replace(old_reader_prefix,new_reader_prefix)
text = text.replace('</h1>','</h1><p>The current gallery reader includes the two repaired Wall Circle references. Its source photographs, qualifications and earlier selected-file history are preserved.</p>',1)
assert old_reader_prefix not in text
current_index.write_text(text)
projection = {'status':'CURRENT_PUBLISHED_READER_PROJECTED_AND_INDEPENDENTLY_VERIFIED',
    'path':rel(seal_path),'sha256':sha(seal_path),'register_sha256':original['register_sha256'],
    'workbook_sha256':original['workbook_sha256'],'readers':copy.deepcopy(seal['readers']),
    'independent_reader_checks_passed':seal['independent_reader_checks_passed'],
    'current_master_navigation':rel(current_index),'current_master_navigation_sha256':sha(current_index),
    'source_review_and_role_proof_files_unchanged':True,'source_identity_and_specification_claims_unchanged':True}
p = copy.deepcopy(original)
p['recorded_utc'] = datetime.now(timezone.utc).isoformat()
p['current_published_gallery_projection'] = projection
p['current_image_review_links'].update(all_links=rel(current_index),
    all_individual_option_galleries=str(run/'product-images.html'),complete_platform_galleries=str(run/'source-galleries.html'),
    complete_family_galleries=str(run/'family-images.html'),current_gallery_projection_seal=rel(seal_path),
    current_gallery_projection_seal_sha256=sha(seal_path))
p['publication_receipt'] = rel(H/'current-gallery-link-publication-receipt.json')
p['latest_master_metadata_change'] = {'status':'CURRENT_GALLERY_READER_LINKS_UPDATED_ONLY',
    'preceding_data_publication_receipt':rel(H/'publication-receipt.json'),
    'preceding_pointer_sha256':sha(pointer_path),'zero_register_workbook_or_native_map_changes':True}
allowed = {'recorded_utc','current_published_gallery_projection','current_image_review_links','publication_receipt','latest_master_metadata_change'}
assert all(p[k] == original[k] for k in original if k not in allowed)
controls = {}
for path in release['controls_sha256']:
    dest = Path(path)
    value = read(dest)
    assert value['current_master_catalogue'] == original
    value.update(updated_utc=p['recorded_utc'],current_master_catalogue=copy.deepcopy(p),
        current_published_gallery_projection=copy.deepcopy(projection),
        current_image_review_links=copy.deepcopy(p['current_image_review_links']),
        latest_master_metadata_change=copy.deepcopy(p['latest_master_metadata_change']))
    controls[dest] = value
write(H/'prepared-current-gallery-pointer.json',p)
if '--apply' not in sys.argv:
    print(json.dumps({'status':'PREPARED_CURRENT_READER_LINKS_ONLY','current_reader':str(current_index),
        'register_unchanged':p['register_sha256'],'workbook_unchanged':p['workbook_sha256']},indent=2))
    raise SystemExit(0)
snapshots = {}
for path in [pointer_path,*controls]:
    dest = H/'inputs'/('before-current-gallery-metadata-'+('pointer.json' if path == pointer_path else str(path.relative_to(B)).replace('/','__')))
    assert not dest.exists()
    shutil.copy2(path,dest)
    snapshots[path] = dest
try:
    assert sha(pointer_path) == '5638de40cee85948c4c1df49828b2efd475789d8026db998ca3c758b92a5f7b4'
    for dest,value in controls.items():
        assert sha(dest) == release['controls_sha256'][str(dest)]
        write(dest,value)
    write(pointer_path,p)
    assert read(pointer_path) == p
    for dest,value in controls.items():
        assert read(dest) == value and value['current_master_catalogue'] == p
    for key in ['register','workbook']:
        assert sha(B/p[key]) == p[key+'_sha256']
    receipt = {'status':'PASS_METADATA_ONLY_CURRENT_READER_LINKS_PUBLISHED_AND_READ_BACK',
        'recorded_utc':p['recorded_utc'],'current_master_pointer_sha256':sha(pointer_path),
        'preceding_pointer_sha256':sha(snapshots[pointer_path]),'data_publication_receipt':rel(H/'publication-receipt.json'),
        'data_publication_receipt_sha256':sha(H/'publication-receipt.json'),
        'register_sha256':p['register_sha256'],'workbook_sha256':p['workbook_sha256'],
        'asset_map_sha256':p['current_asset_reference_map']['sha256'],'native_map_sha256':p['current_native_reference_map']['sha256'],
        'controls_sha256':{str(x):sha(x) for x in controls},'current_projection':projection,
        'changed_pointer_keys':sorted(allowed),'canonical_option_or_field_changes':0,'native_or_platform_writes':0,
        'frozen_original_index_sha256':sha(source_index),'current_index_sha256':sha(current_index)}
    write(H/'current-gallery-link-publication-receipt.json',receipt)
    write(out/'current-gallery-publication-state.json',{'status':'CURRENT_GALLERY_LINKS_PUBLISHED',
        'receipt':str(H/'current-gallery-link-publication-receipt.json'),'receipt_sha256':sha(H/'current-gallery-link-publication-receipt.json'),
        'current_master_pointer_sha256':sha(pointer_path)})
    print(json.dumps(receipt,indent=2))
except BaseException:
    for dest,snapshot in snapshots.items():
        shutil.copy2(snapshot,dest)
    raise
