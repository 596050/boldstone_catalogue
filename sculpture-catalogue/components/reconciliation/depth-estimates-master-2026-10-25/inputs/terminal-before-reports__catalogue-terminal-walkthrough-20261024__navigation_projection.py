"""Explicitly bind frozen review packets to a checked current navigation release."""
import hashlib
import json
from pathlib import Path

H = Path(__file__).resolve().parent
B = H.parents[1]/'sculpture-catalogue'
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()

def current_projection(pointer):
    projection = read(H/'current-navigation-projection.json')
    for key in ['register','workbook']:
        assert pointer[key+'_sha256'] == projection['current_bindings'][key+'_sha256'], 'Rebind reader after the next master data edit'
        assert sha(B/pointer[key]) == pointer[key+'_sha256']
    for key in ['current_asset_reference_map','current_native_reference_map']:
        assert pointer[key]['sha256'] == projection['current_bindings'][key]['sha256']
        assert sha(B/pointer[key]['path']) == pointer[key]['sha256']
    assert projection.get('working_physical_and_commercial_numeric_values_and_states_preserved',projection.get('all189_working_field_objects_and_source_assertions_unchanged',False))
    assert projection.get('all_source_assertions_unchanged',True)
    return projection

def frozen_binding(pointer, kind, digest):
    return digest in current_projection(pointer)['accepted_frozen_bindings'].get(kind, [])

def native_reference(pointer, fid):
    projection = current_projection(pointer)
    return projection['shopify_gallery_current_native_references'][fid]
