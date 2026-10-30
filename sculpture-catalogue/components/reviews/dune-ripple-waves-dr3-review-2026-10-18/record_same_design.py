"""Record the owner's reference-level equivalence without merging historical moulds."""
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
    out = HERE / 'owner-same-design-decision.json'
    assert not out.exists(), 'Decision already recorded'
    paths = {'user': REVIEWS / 'user_classifications.json', 'progress': REVIEWS / 'specification_review_progress.json',
             'walkthrough': REVIEWS / 'walkthrough_checkpoint.json', 'component': ROOT / 'components/checkpoint.json',
             'root': ROOT / 'checkpoint.json'}
    docs = {k: read(p) for k, p in paths.items()}
    old = copy.deepcopy(docs)
    digests = {k: sha(p) for k, p in paths.items()}
    u, p, cp, c = (docs[k] for k in ['user', 'progress', 'walkthrough', 'component'])
    assert cp['current_component_id'] == 'BC-DR-WAVE3' and not cp['current_answer_recorded']
    assert docs['root']['current_component_review'] == c
    card_path = HERE / 'component-review.json'
    card = read(card_path)
    prior_path = ROOT / card['prior_DR1_reference']['review_record']
    prior = read(prior_path)
    prior_keep = ROOT / p['reviews']['BC-DR-WAVE1']['identity_approval']
    meta = read(HERE / 'same-design-current-references.json')
    refs = {x['request_id']: x for x in meta['metadata']}
    folder_id = card['primary_folder_id']
    assert folder_id == prior['primary_folder_id']
    for v in [card, prior]:
        f = refs[v['primary_image_id']]['file']
        assert f['id'] == v['primary_image_id'] and f['path_display'].rsplit('/', 1)[0] == refs[folder_id]['folder']['path_display']
    protected_paths = [card_path, prior_path, prior_keep, ROOT / 'components/evidence/component_register.json', ROOT / cp['register_workbook']]
    protected = {str(x): sha(x) for x in protected_paths}
    now = datetime.now(timezone.utc).isoformat()
    decision = {'schema_version': 1, 'decision_id': 'DUNE-WHITE-WAVE:001-016:SAME-DEPICTED-DESIGN:2026-10-18',
        'recorded_utc': now, 'user_statement': 'They are the same: Is this a separate DR3 component, or the same design as the earlier DR1 photograph?',
        'preceding_question': card['code_relationship_question'], 'status': 'OWNER CONFIRMED SAME DEPICTED DESIGN',
        'relationship': 'SAME_DEPICTED_DESIGN', 'canonical_component_id': 'BC-DR-WAVE1',
        'canonical_size_finish_variant_id': 'DR1-WHITE', 'retained_name': 'Dune Ripple Waves — White (DR1)',
        'reviewed_source_component_id': 'BC-DR-WAVE3', 'reviewed_source_variant_id': 'DR3-WHITE',
        'review_record': rel(card_path), 'review_record_sha256': sha(card_path),
        'prior_review_record': rel(prior_path), 'prior_review_record_sha256': sha(prior_path),
        'prior_identity_approval': rel(prior_keep), 'prior_identity_approval_sha256': sha(prior_keep),
        'reference_images': [{'file_id': v['primary_image_id'], 'folder_id': v['primary_folder_id'],
            'image_link': v['primary_image_link'], 'folder_link': v['primary_folder_link'],
            'current_metadata': refs[v['primary_image_id']]['file']} for v in [prior, card]],
        'current_folder_metadata': refs[folder_id]['folder'], 'metadata_checked_utc': meta['checked_utc'],
        'scope': 'These two pictured references depict one design. Preserve the approved DR1 name; do not create a second saleable component solely from photograph016 or its proposed DR3 label.',
        'counting_scope': 'Two reviewed image references, one depicted design. No whole-catalogue or physical stock count inferred.',
        'applies_to_entire_source_component': False, 'new_name_approval': False,
        'historical_maker_code_equivalence_confirmed': False, 'same_physical_cast_confirmed': False,
        'same_mould_confirmed': False, 'specifications_approved': False, 'physical_specs_verified': False,
        'source_code_discrepancy': 'Maker rows54/56 label DR1/DR3 separately. Photo001 was provisionally bound to DR1; the owner confirms photo001 and016 show the same design. Historical code allocation and any other distinct wave remain open.',
        'workbook_contains_this_decision': False, 'remote_files_changed': False, 'live_platform_records_changed': False}
    write(HERE / 'before-same-design.json', {'recorded_utc': now, 'files': {rel(paths[k]): v for k, v in old.items()}, 'protected_sha256': protected})
    write(out, decision)
    u.setdefault('component_identity_relationship_decisions', []).append(decision | {'approval_record': rel(out)})
    group = {'identity_group_id': 'DUNE-WHITE-WAVE-DR1-REVIEWED-REFERENCES',
        'canonical_component_id': 'BC-DR-WAVE1', 'canonical_size_finish_variant_id': 'DR1-WHITE',
        'canonical_name': decision['retained_name'], 'file_ids': [x['file_id'] for x in decision['reference_images']],
        'folder_ids': [folder_id], 'depicted_design_count': 1, 'review_reference_count': 2,
        'source_component_ids': ['BC-DR-WAVE1', 'BC-DR-WAVE3'], 'applies_to_entire_source_component': False,
        'relationship_decision': rel(out), 'same_physical_cast_confirmed': False, 'same_mould_confirmed': False,
        'historical_maker_codes_reconciled': False}
    p.setdefault('depicted_reference_identity_groups', {})[group['identity_group_id']] = group
    target = p['reviews']['BC-DR-WAVE3']
    target.update({'depicted_identity_resolved': True, 'depicted_identity_relationship': 'SAME_AS_PREVIOUS_DR1_REFERENCE',
        'canonical_depicted_component_id': 'BC-DR-WAVE1', 'canonical_depicted_name': decision['retained_name'],
        'separate_saleable_design_from_selected_reference': False, 'relationship_approval': rel(out),
        'code_relationship_status': 'PICTURED DESIGN EQUIVALENCE CONFIRMED; HISTORICAL DR1/DR3 CODE ALLOCATION OPEN',
        'specification_review_status': 'SIX SOURCE PROPOSALS RETAINED UNAPPROVED; NO DUPLICATE COMPONENT CREATED',
        'gaps': ['Reconcile historical maker DR1/DR3 labels and series positions; these two references show the same design'] + target['gaps'][1:]})
    p['reviews']['BC-DR-WAVE1'].update({'additional_same_design_reference_file_ids': [card['primary_image_id']],
        'reference_identity_relationship': rel(out), 'historical_maker_code_reconciliation_pending': True})
    family = {'family': 'Dune Ripple', 'status': 'FIRST_PASS_REFERENCE_IDENTITY_QUESTIONS_ANSWERED',
        'completed_utc': now, 'review_reference_count': 14, 'latest_relationship_decision': rel(out),
        'review_reference_count_is_individual_sculpture_count': False,
        'specifications_complete': False, 'historical_maker_codes_reconciled': False,
        'scope': 'Named finishes and references reviewed; final DR3 candidate is the same depicted design as the earlier DR1 photo. Physical cast counts, historical DR1/DR3 allocation, specification approvals and export remain pending.'}
    p.setdefault('family_review_progress', {})['Dune Ripple'] = family
    state = 'Dune Ripple first-pass references answered; same-design duplicate resolved; bounded import before review45'
    cp.update({'current_answer_recorded': True, 'current_identity_relationship_answer_recorded': True,
        'current_identity_relationship_approval': rel(out), 'canonical_depicted_name': decision['retained_name'],
        'state': state, 'answer_state': decision['scope'] + ' Six specification fields remain unapproved.',
        'family_first_pass_complete': True, 'last_completed_family_first_pass': family,
        'updated_utc': now})
    c['interactive_review_state'].update({'state': state, 'current_identity_relationship_answer_recorded': True,
        'canonical_depicted_name': decision['retained_name'], 'current_separate_saleable_design': False})
    c['last_identity_relationship_decision'] = rel(out)
    c['last_completed_family_first_pass'] = family
    c['updated_utc'] = p['updated_utc'] = u['updated_utc'] = now
    docs['root']['current_component_review'] = copy.deepcopy(c)
    docs['root']['updated_utc'] = now
    assert u['identity_confirmation_counts'] == old['user']['identity_confirmation_counts']
    assert u['specification_approval_counts'] == old['user']['specification_approval_counts']
    assert cp['parallel_import_queue'] == old['walkthrough']['parallel_import_queue']
    assert all(sha(path) == digests[k] for k, path in paths.items()), 'Shared writer collision'
    assert all(sha(Path(k)) == v for k, v in protected.items())
    for k, path in paths.items():
        write(path, docs[k])
        assert read(path) == docs[k]
    assert read(paths['root'])['current_component_review'] == read(paths['component'])
    assert not target['identity_confirmed'] and not target['specifications_approved']
    event = {'event_id': decision['decision_id'], 'event': 'SAME_DEPICTED_DESIGN_CONFIRMED', 'recorded_utc': now,
        'decision_record': rel(out), 'canonical_component_id': 'BC-DR-WAVE1', 'duplicate_reference_file_id': card['primary_image_id'],
        'new_sculpture_created': False, 'specification_approval_inferred': False}
    for path in [REVIEWS / 'identity_review_journal.jsonl', ROOT / 'review_journal.jsonl']:
        with path.open('a') as f:
            f.write(json.dumps(event, ensure_ascii=False) + '\n')
    result = {'status': 'PASS', 'two_review_references_one_depicted_design': True, 'prior_DR1_name_preserved': True,
        'new_DR3_name_approval': False, 'six_specification_groups_unapproved': True,
        'physical_cast_and_mould_equivalence_unconfirmed': True, 'historical_maker_code_reconciliation_pending': True,
        'baseline_model_workbooks_and_prior_receipts_unchanged': True, 'checkpoint_copies_match': True}
    write(HERE / 'same-design-readback.json', result)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
