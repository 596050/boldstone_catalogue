import pytest
from research_workflows.input_budget import preflight


def workflow():
    return {'jobs': [
        {'id': 'producer', 'capsule': 'code', 'runtime': 'python', 'resources': {'max_output_mb': 8},
         'inputs': {}, 'outputs': {'data': {}}},
        {'id': 'replay', 'capsule': 'code', 'runtime': 'python', 'resources': {}, 'outputs': {},
         'inputs': {'market': {'mode': 'bundle', 'object_sha256': 'source'},
                    'metadata': {'mode': 'bundle', 'object_sha256': 'source'},
                    'audit': {'mode': 'artifact_ref', 'job': 'producer', 'output': 'data'}}}]}


def test_duplicate_aliases_exceed_logical_cap_even_with_one_physical_source():
    w=workflow();sizes={'code': 1000, 'source': 600<<20}
    r=preflight(w,sizes,{'python': {'max_input_mb': 1024,'max_output_mb': 64}})['jobs'][1]
    assert r['status']=='DEFINITE_INPUT_BUDGET_REJECTION'
    assert r['known_logical_input_bytes']==(1200<<20)+1000
    assert r['known_unique_physical_object_bytes']==(600<<20)+1000
    assert preflight(w,sizes,{'python': {'max_input_mb': 2048,'max_output_mb': 64}})['jobs'][1]['status']=='UPPER_BOUND_WITHIN_CAP'


def test_large_producer_allowance_is_unknown_instead_of_definite_rejection():
    r=preflight(workflow(),{'code': 0,'source': 4<<20},
        {'python': {'max_input_mb': 10,'max_output_mb': 64}})['jobs'][1]
    assert r['status']=='UNRESOLVED_ARTIFACT_UPPER_BOUND'
    assert r['known_logical_input_bytes']==8<<20
    assert r['logical_input_upper_bound_bytes']==16<<20


def test_missing_or_invalid_sizes_and_undeclared_output_are_rejected():
    limits={'python': {'max_input_mb': 1024,'max_output_mb': 64}}
    with pytest.raises(KeyError):preflight(workflow(),{'code': 1},limits)
    for invalid in (True,-1,1.5):
        with pytest.raises(ValueError):preflight(workflow(),{'code': 1,'source': invalid},limits)
    w=workflow();w['jobs'][1]['inputs']['audit']['output']='absent'
    with pytest.raises(ValueError,match='declared'):preflight(w,{'code': 1,'source': 1},limits)


def test_runtime_input_cap_cannot_be_raised_by_a_job_override():
    w=workflow();w['jobs'][1]['resources']['max_input_mb']=2048
    with pytest.raises(ValueError,match='input cap'):
        preflight(w,{'code': 1,'source': 600<<20},{'python': {'max_input_mb': 1024,'max_output_mb': 64}})
    w=workflow();w['jobs'][0]['resources']['max_output_mb']=65
    with pytest.raises(ValueError,match='approved'):
        preflight(w,{'code': 1,'source': 1},{'python': {'max_input_mb': 1024,'max_output_mb': 64}})
