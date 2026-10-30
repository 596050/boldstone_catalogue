"""Read the saved shared records independently of the import implementation."""
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
before = read(HERE / 'before-import.json')
receipt = read(HERE / 'import-receipt.json')
files = {name: read(ROOT / name) for name in before['files']}
u = files['components/reviews/user_classifications.json']
p = files['components/reviews/specification_review_progress.json']
cp = files['components/reviews/walkthrough_checkpoint.json']
c = files['components/checkpoint.json']
b = before['files']
checks = {}
checks['root_component_mirror'] = files['checkpoint.json']['current_component_review'] == c
checks['current_question_preserved'] = all(cp[k] == v for k, v in b['components/reviews/walkthrough_checkpoint.json'].items()
    if k.startswith('current_') or k in ['proposed_name', 'question_scope', 'answer_state', 'next_review_after_keep'])
checks['previous_ledger_prefixes'] = all(u[k][:len(v)] == v for k, v in b['components/reviews/user_classifications.json'].items() if isinstance(v, list))
checks['previous_progress_reviews'] = all(p['reviews'][k] == v for k, v in b['components/reviews/specification_review_progress.json']['reviews'].items())
checks['previous_offer_photo_bindings'] = p['offer_photo_bindings'] == b['components/reviews/specification_review_progress.json']['offer_photo_bindings']
checks['protected_files_unchanged'] = all(sha(Path(path)) == digest for path, digest in before['protected_sha256'].items())
checks['imported_names_exactly_once'] = all(sum(x.get('source_decision_id') == e['source_decision_id'] for x in u['size_finish_variant_decisions']) == 1 for e in receipt['imported'])
checks['source_identity_ids_exactly_once'] = all(sum(x.get('source_decision_id') == e['source_decision_id'] for values in u.values() if isinstance(values, list) for x in values if isinstance(x, dict)) == 1 for e in read(HERE / 'source-manifest.json')['named_entries'])
partial = wholly_pending = accepted = 0
for e in receipt['imported']:
    cid, vid = e['component_id'], e['size_finish_variant_id']
    v = p['reviews'][cid]['size_finish_variants'][vid]
    assert v['identity_confirmed'] and v['canonical_name'] == e['name']
    assert not v['specifications_approved'] and not v['physical_specs_verified']
    assert v['primary_image_id'] is None and v['individual_photo_missing'] and v['reference_image_id']
    assert v['owner_face_dimensions_cm'] == {'height': 240, 'width': 80, 'depth': None}
    assert v['actual_weight_kg'] is None and v['accepted_conditional_weight_proposal_kg'] == 105
    assert not v['average_material_thickness_is_measured_depth'] and v['weight_model_assumptions']['average_material_thickness_mm'] == 30
    assert not v['actual_material_verified'] and not v['current_production_stock_and_lead_time_verified']
    assert v['individual_sale_unit_owner_approved'] == vid.endswith('SANDSTONE')
    assert len(v['specification_proposals']) == 6
    for prop in v['specification_proposals']:
        if prop.get('owner_approved'):
            assert prop['field'] == 'weight' and prop['actual_mass_established'] is False
            accepted += 1
        elif prop.get('owner_confirmed_subfields'):
            partial += 1
        else:
            wholly_pending += 1
    for ledger, pathkey in [('dimension_decisions','face_dimension_approval'), ('size_finish_variant_specification_decisions','conditional_weight_approval'), ('fixing_detail_decisions','fixing_type_approval')]:
        entries = [x for x in u[ledger] if x.get('component_id') == cid and x.get('size_finish_variant_id') == vid]
        assert len(entries) == 1
        assert entries[0]['approval_record'] == e[pathkey]
    d = read(ROOT / e['face_dimension_approval'])
    assert d['scope_kind'] == 'INDIVIDUAL_FACE_SIZE' and d['confirmed_dimensions_cm']['depth'] is None
    w = read(ROOT / e['conditional_weight_approval'])
    assert w['accepted_conditional_weight_kg'] == 105 and not w['actual_mass_established'] and len(w['approved_proposal_ids']) == 1
    assert not w['proposals_approved'] and not w['specifications_approved']
    f = read(ROOT / e['fixing_type_approval'])
    assert f['confirmed_fixing_type'] == 'French cleat fixings' and not f['complete_fixing_group_approved']
    assert all(f[k] is None for k in ['fixing_count','fixing_material','fixing_dimensions','fixing_positions','anchors','tested_load_rating'])
checks['six_precise_field_scopes'] = (accepted, partial, wholly_pending) == (6,15,15)
checks['identity_counts'] = u['identity_confirmation_counts'] == receipt['counts']['identity'] and u['identity_confirmation_counts']['explicit_size_finish_variant_names'] == 84
checks['specification_counts'] = u['specification_approval_counts'] == receipt['counts']['specifications'] and u['specification_approval_counts']['proposal_groups'] == 69
checks['dimension_counts'] = u['dimension_confirmation_counts'] == receipt['counts']['dimensions'] and u['dimension_confirmation_counts']['individual_dimension_decisions'] == 20
checks['no_new_complete_variant_approval'] = u['specification_approval_counts']['size_finish_variant_approvals'] == b['components/reviews/user_classifications.json']['specification_approval_counts']['size_finish_variant_approvals']
checks['queue_consumed'] = any(e.get('import_receipt') == receipt['receipt'] and e.get('approval_imported') for e in cp['parallel_import_queue'])
checks['all_checks'] = all(checks.values())
assert checks['all_checks'], checks
result = {'status':'PASS', 'checked_utc':datetime.now(timezone.utc).isoformat(), 'checks':checks,
    'import_receipt_sha256':sha(HERE / 'import-receipt.json'), 'accepted_conditional_groups':accepted,
    'partial_groups':partial, 'wholly_pending_groups':wholly_pending, 'physical_specs_verified':False}
(HERE / 'independent-shared-readback.json').write_text(json.dumps(result,indent=2)+'\n')
hashes = {k:sha(ROOT / k) for k in files}
repeat = subprocess.run(['python3',str(HERE / 'import_verified_reviews.py')],capture_output=True,text=True,check=True)
assert json.loads(repeat.stdout)['status'] == 'ALREADY_IMPORTED_IDEMPOTENT_NO_WRITE'
assert hashes == {k:sha(ROOT / k) for k in files}
(HERE / 'idempotency-readback.json').write_text(json.dumps({'status':'PASS','repeat':json.loads(repeat.stdout),'shared_files_unchanged':True},indent=2)+'\n')
print(json.dumps({'status':'PASS','checks':len(checks),'conditional_groups':accepted,'partial_groups':partial,'wholly_pending':wholly_pending,'idempotent_no_write':True,'receipt_sha256':result['import_receipt_sha256']}))
