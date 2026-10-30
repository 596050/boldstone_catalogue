"""Record owner face size and replace guesses whose metre-long premise no longer applies."""
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REVIEWS = ROOT / 'components/reviews'
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
rel = lambda p: str(p.relative_to(ROOT))


def write(p, value):
    t = p.with_name(p.name + '.tmp')
    t.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    t.replace(p)


def main():
    output = HERE / 'user-face-dimensions-70x15.json'
    new_card_path = HERE / 'component-review.after-dimensions.json'
    assert not output.exists() and not new_card_path.exists(), 'Already recorded'
    paths = {'user': REVIEWS / 'user_classifications.json', 'progress': REVIEWS / 'specification_review_progress.json',
        'walkthrough': REVIEWS / 'walkthrough_checkpoint.json', 'component': ROOT / 'components/checkpoint.json', 'root': ROOT / 'checkpoint.json'}
    docs = {k: read(p) for k, p in paths.items()}
    before = copy.deepcopy(docs)
    digests = {k: sha(p) for k, p in paths.items()}
    u, progress, cp, component = (docs[k] for k in ['user', 'progress', 'walkthrough', 'component'])
    assert cp['current_component_id'] == 'BC-EMBED-SHELLS' and not cp['current_answer_recorded']
    assert not cp['current_dimension_answer_recorded'] and docs['root']['current_component_review'] == component
    source_card_path = ROOT / cp['current_review_record']
    source_card = read(source_card_path)
    assert source_card['primary_image_id'] == 'id:cnqzTNngPVsAAAAAAAyk1w'
    assert source_card['primary_folder_id'] == 'id:cnqzTNngPVsAAAAAAAykCQ'
    model_path = ROOT / 'components/evidence/component_register.json'
    retail_path = ROOT / 'components/evidence/price-source-review-2026-10-17/Retail PRICE List 2025.docx.txt'
    model = read(model_path)
    claims = [x for x in model['claims'] if x.get('component_id') == 'BC-FFS-1' and 'row70/' in x.get('source_ref', '')]
    assert any(x['value'] == '4-6kg each' for x in claims)
    assert '70cm x 15cm' in retail_path.read_text() and '262.5' in retail_path.read_text()
    protected = {str(p): sha(p) for p in [source_card_path, HERE / 'source-audit.json', model_path,
        ROOT / cp['register_workbook'], ROOT / cp['last_identity_relationship_approval']]}
    now = datetime.now(timezone.utc).isoformat()
    decision = {'schema_version': 1, 'decision_id': 'BC-EMBED-SHELLS:EMBED-SHELLS-WHITE:face:user-stated:70x15',
        'recorded_utc': now, 'component_id': 'BC-EMBED-SHELLS', 'size_finish_variant_id': 'EMBED-SHELLS-WHITE',
        'canonical_name': 'Embedded Shells — White', 'review_number': 45,
        'user_statement': 'Dimensions: 70 x 15 for embedded shells',
        'status': 'OWNER STATED FACE SIZE; UNITS AND PORTRAIT AXES INTERPRETED FROM REVIEW CONTEXT',
        'confirmed_dimensions_cm': {'height': 70, 'width': 15, 'depth': None},
        'approved_face_dimensions_cm': {'height': 70, 'width': 15},
        'unit_interpretation': 'Owner omitted units. Interpreted as centimetres from the current cm-based catalogue card; no conversion performed.',
        'axis_interpretation': '70cm height and15cm width for the tall portrait panel shown in the current review.',
        'scope': 'Individual pictured Embedded Shells white panel face only. No depth, weight, material, fixing, price, availability, name approval or measurement method supplied.',
        'prior_guess_cm': {'height': 100, 'width': 25}, 'prior_face_guess_superseded': True,
        'identity_approved': False, 'specifications_approved': False, 'physical_specs_verified': False,
        'not_confirmed': ['Depth/maximum projection', 'Actual dry weight', 'Material, inclusions, backing, reinforcement and sealant',
            'Rear fixing type/count/attachment/load', 'Individual price', 'Stock/reproducibility/lead time',
            'Name/identity approval', 'Squarespace/Shopify match', 'Physical measurement method'],
        'primary_file_id': source_card['primary_image_id'], 'primary_folder_id': source_card['primary_folder_id'],
        'image_link': source_card['primary_image_link'], 'folder_link': source_card['primary_folder_link'],
        'source_review': rel(source_card_path), 'source_review_sha256': sha(source_card_path),
        'workbook_status': 'Unchanged; owner face size and revised proposals saved in review overlay for later export.',
        'remote_files_changed': False, 'live_platform_records_changed': False}
    write(HERE / 'before-face-dimensions-70x15.json', {'recorded_utc': now,
        'files': {rel(paths[k]): v for k, v in before.items()}, 'protected_sha256': protected})
    write(output, decision)
    u['dimension_decisions'].append(decision | {'approval_record': rel(output)})
    u['dimension_confirmation_counts'] = {'components': len({x['component_id'] for x in u['dimension_decisions']}),
        'face_size_decisions': len(u['dimension_decisions'])}
    assert u['dimension_confirmation_counts'] == {'components': 8, 'face_size_decisions': 8}
    card = copy.deepcopy(source_card)
    card.update({'prepared_utc': now, 'revision_kind': 'OWNER_FACE_DIMENSIONS_AND_DEPENDENT_GUESS_REVISION',
        'supersedes_review_record': rel(source_card_path), 'supersedes_review_sha256': sha(source_card_path),
        'owner_face_dimensions_cm': decision['confirmed_dimensions_cm'], 'dimension_approval': rel(output)})
    dimension, weight, material, fixing, price, availability = card['specification_review_items']
    assert dimension['proposal_id'] == 'EMBED-SHELLS-WHITE-DIMENSIONS' and weight['proposal_id'] == 'EMBED-SHELLS-WHITE-WEIGHT'
    dimension.update({'display': '70 H × 15 W cm — owner-stated face size; depth5–7cm remains an unapproved guess',
        'status': 'FACE SIZE OWNER STATED; DEPTH PROPOSAL UNAPPROVED', 'owner_face_size_confirmed': True,
        'owner_approved': False, 'partially_confirmed_field': 'height_and_width_only',
        'value': {'owner_stated_height_cm': 70, 'owner_stated_width_cm': 15, 'proposed_depth_range_cm': [5, 7], 'measured_dimensions_cm': None},
        'basis': 'Owner states70×15. Centimetres and portrait axes are interpreted from the current review. This supersedes the100×25face guess only; maximum projection remains unknown.',
        'source_refs': [rel(output)]})
    weight.update({'display': 'Approximately4–6kg — revised analogy to other70×15cm reliefs; actual panel unweighed',
        'value': {'proposed_range_kg': [4, 6], 'actual_weighed_kg': None, 'actual_construction_confirmed': False},
        'basis': 'Owner face size is70×15cm. A different Frozen Fish70×15cm template has a historical calculated4–6kg range and a dated retail estimate6kg. This supports a weak discussion analogy only; Embedded Shells thickness, backing, binder and dry mass are unknown. The prior8–12kg metre-long analogy is withdrawn; no proportional mass scaling is claimed.',
        'source_refs': [rel(output), 'manufacture-stevensons:Sheet1!row70/Approximate Weight of each piece in Standard Size A ', rel(retail_path) + ':line43'],
        'owner_approved': False})
    price.update({'display': '£250–£350 per panel — revised discussion range; no matched individual offer or owner price approval',
        'value': {'proposed_range_gbp': [250, 350], 'exact_existing_offer_confirmed': False, 'owner_price_approved': False},
        'basis': 'Dated2025retail table gives262.50GBP for a different70×15cm Frozen Fish panel. The250–350GBP range is a fresh discussion guess for Embedded Shells, not a price found for this sculpture. The earlier500–700GBP metre-long analogy is withdrawn. No set-price division or geometric price scaling is used.',
        'source_refs': [rel(output), rel(retail_path) + ':line43'], 'owner_approved': False})
    card['source_conflicts'].append('Owner face size70×15supersedes100×25guess. Previous8–12kg and500–700GBP metre-long analogies withdrawn; replacement weight/price guesses remain unapproved.')
    card['open_gaps'] = [x.replace('Measured face and maximum depth', 'Maximum depth; unit/axis interpretation and measurement method remain explicit') for x in card['open_gaps']]
    assert len(card['specification_review_items']) == 6 and not any(x['owner_approved'] for x in card['specification_review_items'])
    write(new_card_path, card)
    supplement = {'schema_version': 1, 'recorded_utc': now, 'owner_dimension_receipt': rel(output),
        'original_review': rel(source_card_path), 'original_review_sha256': sha(source_card_path),
        'revised_review': rel(new_card_path), 'revised_review_sha256': sha(new_card_path),
        'owner_confirmed_fields': ['Face70×15cm, with contextual unit/axis interpretation'],
        'withdrawn_guesses': {'face_cm': [100, 25], 'weight_kg': [8, 12], 'individual_price_gbp': [500, 700]},
        'revised_unapproved_guesses': {'weight_kg': [4, 6], 'individual_price_gbp': [250, 350]},
        'same_face_size_does_not_establish_same_design_or_material': True,
        'other_design_analogy_claims': claims, 'retail_analogy_source': rel(retail_path), 'retail_analogy_source_sha256': sha(retail_path),
        'other_fields_and_name_approval_pending': True, 'physical_specs_verified': False}
    write(HERE / 'dimension-revision-supplement.json', supplement)
    target = progress['reviews']['BC-EMBED-SHELLS']
    target.update({'review_record': rel(new_card_path), 'original_review_record': rel(source_card_path),
        'owner_face_dimensions_cm': decision['confirmed_dimensions_cm'], 'dimension_approval': rel(output),
        'dimension_unit_interpretation': decision['unit_interpretation'], 'dimension_axis_interpretation': decision['axis_interpretation'],
        'specification_proposals': copy.deepcopy(card['specification_review_items']), 'gaps': card['open_gaps'],
        'source_conflicts': card['source_conflicts'], 'source_specifications_recorded': True,
        'specification_review_status': 'OWNER FACE SIZE RECORDED; DEPTH AND OTHER FIVE GROUPS STILL PENDING',
        'proposal_revision_supplement': rel(HERE / 'dimension-revision-supplement.json')})
    state = 'Embedded Shells face70×15cm recorded; name/identity, depth and other specifications remain pending'
    cp.update({'current_review_record': rel(new_card_path), 'current_dimension_answer_recorded': True,
        'current_dimension_approval': rel(output), 'current_partial_specification_answer_recorded': True,
        'current_owner_face_dimensions_cm': decision['confirmed_dimensions_cm'], 'state': state,
        'answer_state': 'Face70×15cmowner stated, centimetres/axes interpreted from context. No name Keep or other specification approval inferred.',
        'current_component_source_notes': [x['display'] for x in card['specification_review_items']],
        'question_scope': card['scope'] + ' Owner face70×15cmnow recorded; revised weight/price guesses remain unapproved.', 'updated_utc': now})
    component['interactive_review_state'].update({'state': state, 'current_dimension_answer_recorded': True,
        'current_owner_face_dimensions_cm': decision['confirmed_dimensions_cm'], 'specification_proposals_approved': False})
    component['current_component_review_record'] = rel(new_card_path)
    component['last_owner_dimension_decision'] = rel(output)
    component['updated_utc'] = u['updated_utc'] = progress['updated_utc'] = now
    docs['root']['current_component_review'] = copy.deepcopy(component)
    docs['root']['updated_utc'] = now
    assert not cp['current_answer_recorded'] and not cp['current_specification_answer_recorded']
    assert not target['identity_confirmed'] and not target['specifications_approved']
    assert cp['parallel_import_queue'] == before['walkthrough']['parallel_import_queue']
    assert cp['parallel_owner_reviews'] == before['walkthrough']['parallel_owner_reviews']
    assert u['identity_confirmation_counts'] == before['user']['identity_confirmation_counts']
    assert u['specification_approval_counts'] == before['user']['specification_approval_counts']
    assert all(progress['reviews'][k] == v for k, v in before['progress']['reviews'].items() if k != 'BC-EMBED-SHELLS')
    assert all(sha(path) == digests[k] for k, path in paths.items()), 'Shared writer collision'
    assert all(sha(Path(path)) == digest for path, digest in protected.items())
    for key, path in paths.items():
        write(path, docs[key])
        assert read(path) == docs[key]
    assert read(paths['root'])['current_component_review'] == read(paths['component'])
    event = {'event_id': decision['decision_id'], 'event': 'OWNER_FACE_DIMENSIONS_RECORDED', 'recorded_utc': now,
        'component_id': 'BC-EMBED-SHELLS', 'dimension_receipt': rel(output), 'face_cm': [70, 15],
        'unit_interpreted_from_cm_context': True, 'name_approval_inferred': False,
        'other_specification_approval_inferred': False, 'dependent_guesses_revised_not_approved': True}
    for path in [REVIEWS / 'identity_review_journal.jsonl', ROOT / 'review_journal.jsonl']:
        with path.open('a') as f:
            f.write(json.dumps(event, ensure_ascii=False) + '\n')
    result = {'status': 'PASS', 'owner_face_cm': [70, 15], 'name_approval_pending': True, 'depth_unapproved': True,
        'revised_weight_guess_kg': [4, 6], 'revised_price_guess_gbp': [250, 350],
        'other_specification_approval_inferred': False, 'baseline_model_workbook_original_card_unchanged': True,
        'stable_Dropbox_image_and_folder_IDs_preserved': True, 'checkpoint_copies_match': True}
    write(HERE / 'dimensions-70x15-readback.json', result)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
