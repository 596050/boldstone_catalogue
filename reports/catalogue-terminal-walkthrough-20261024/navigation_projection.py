"""Explicitly bind frozen review packets to a checked current navigation release."""
import hashlib
import json
import re
from functools import lru_cache
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
    preserved = projection.get('working_physical_and_commercial_numeric_values_and_states_preserved',projection.get('all189_working_field_objects_and_source_assertions_unchanged',False))
    if not preserved:
        if projection.get('authorized_depth_and_bound_wording_changes'):
            ref = projection['non_numeric_wording_packet']
            assert sha(ref['path']) == ref['sha256']
            expected_wording = [{'option_id':r['product_id'],'field':r['field'],'before':r['before'],'after':r['after']} for r in read(ref['path'])['rows']]
            assert projection['non_numeric_wording_changes'] == expected_wording and len(expected_wording) == 1
            for change in expected_wording:
                old, new = change['before'], change['after']
                assert {k:v for k,v in old.items() if k not in ['display','basis']} == {k:v for k,v in new.items() if k not in ['display','basis']}
                for key in ['display','basis']:
                    assert re.findall(r'\d+(?:\.\d+)?',old[key]) == re.findall(r'\d+(?:\.\d+)?',new[key])
            if projection.get('authorized_scoped_specification_completion'):
                ref = projection['working_specification_completion_packet']
                assert sha(ref['path']) == ref['sha256']
                packet = read(ref['path'])
                expected_specs = [{'option_id':r['product_id'],'field':r['field'],'before':r['before'],'after':r['after']} for r in packet['changes']]
                assert projection['working_specification_changes'] == expected_specs and len(expected_specs) == 30
                assert sum(x['field']=='Material / finish' for x in expected_specs) == 27
                assert sum(x['field']=='Dimensions / depth' for x in expected_specs) == 3
                assert all(x['after']['physical_verification'] == x['before']['physical_verification'] == 0 for x in expected_specs)
                assert projection['other1104_field_objects_preserved_since_spec_completion_baseline']
            else:
                assert projection['other1119_field_objects_preserved_since_pre_depth_release']
        else:
            assert projection['authorized_depth_estimate_changes_only'] and projection['other1120_field_objects_preserved']
        assert projection['new_physical_measurements'] == 0
        ref = projection['depth_estimate_packet']
        assert sha(ref['path']) == ref['sha256']
        expected = [{'option_id':r['product_id'],'field':'Dimensions / depth','before':r['before'],'after':r['after']} for r in read(ref['path'])['rows']]
        assert projection['depth_estimate_changes'] == expected and len(expected) == 14
        assert all(x['after']['physical_verification'] == 0 for x in expected)
    assert projection.get('all_source_assertions_unchanged',True)
    return projection

def frozen_binding(pointer, kind, digest):
    return digest in current_projection(pointer)['accepted_frozen_bindings'].get(kind, [])

def native_reference(pointer, fid):
    projection = current_projection(pointer)
    return projection['shopify_gallery_current_native_references'][fid]

@lru_cache(maxsize=2)
def _options(register, digest):
    assert sha(B/register) == digest
    return {o['product_id']:o for o in read(B/register)['options']}

def current_option(pointer, option_id):
    current_projection(pointer)
    return _options(pointer['register'], pointer['register_sha256'])[option_id]

def current_fields(pointer, option_id, frozen_fields):
    """Accept only explicit, verified before/after changes from frozen evidence."""
    projection = current_projection(pointer)
    fields = current_option(pointer, option_id)['master_fields']
    assert set(fields) == set(frozen_fields), option_id
    changes = projection.get('owner_identity_wording_changes', []) + projection.get('depth_estimate_changes', []) + projection.get('non_numeric_wording_changes', []) + projection.get('working_specification_changes', [])
    for name, before in frozen_fields.items():
        value = before
        for change in changes:
            if change['option_id'] == option_id and change['field'] == name and value == change['before']:
                value = change['after']
        assert value == fields[name], (option_id, name, 'Unapproved field drift in frozen reader')
    return fields
