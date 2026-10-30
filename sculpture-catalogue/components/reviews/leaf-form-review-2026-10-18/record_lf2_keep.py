"""Record the owner's LF2 name/position decision without approving specifications."""
import copy
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REVIEWS = ROOT / 'components/reviews'
sys.path.insert(0, str(ROOT / 'components/scripts'))
from review_decision_counts import identity_counts

read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
rel = lambda p: str(p.relative_to(ROOT))


def write(path, value):
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temp.replace(path)


def main():
    output = HERE / 'lf2-white/identity-approval.json'
    assert not output.exists(), 'LF2 decision already recorded'
    paths = {'user': REVIEWS / 'user_classifications.json',
             'progress': REVIEWS / 'specification_review_progress.json',
             'walkthrough': REVIEWS / 'walkthrough_checkpoint.json',
             'component': ROOT / 'components/checkpoint.json', 'root': ROOT / 'checkpoint.json'}
    docs = {key: read(path) for key, path in paths.items()}
    before = copy.deepcopy(docs)
    hashes = {key: sha(path) for key, path in paths.items()}
    u, p, cp, c = (docs[key] for key in ['user', 'progress', 'walkthrough', 'component'])
    layout_id = 'LEAF-FORM-LF2-WHITE'
    assert cp['current_component_id'] == 'BC-LEAF-FORM'
    assert cp['current_component_layout_id'] == layout_id and not cp['current_answer_recorded']
    assert docs['root']['current_component_review'] == c
    card_path = ROOT / cp['current_review_record']
    card = read(card_path)
    assert card['component_layout_id'] == layout_id and card['proposed_name'] == 'Leaf Form 2 — White (LF2)'
    assert not card['identity_confirmed'] and len(card['specification_review_items']) == 6
    parent = p['reviews']['BC-LEAF-FORM']
    target = parent['component_layouts'][layout_id]
    assert not parent['identity_confirmed'] and not target['identity_confirmed']
    assert not any(x['component_id'] == 'BC-LEAF-FORM' for x in u['decisions'])
    assert not any(x['component_layout_id'] == layout_id for x in u['component_layout_identity_decisions'])
    protected_paths = [card_path, HERE / 'lf2-white/component-review.draft.json',
                       HERE / 'lf1-white/identity-approval.json', HERE / 'lf1-white/component-review.json',
                       ROOT / 'components/evidence/component_register.json', ROOT / cp['register_workbook'],
                       REVIEWS / 'leaf-curve-review-2026-10-18/identity-approval.json']
    protected = {str(path): sha(path) for path in protected_paths}
    meta = read(HERE / 'metadata-links.json')
    file = next(x['file'] for x in meta['metadata'] if x['request_id'] == card['primary_image_id'])
    folder = next(x['folder'] for x in meta['metadata'] if x['request_id'] == card['primary_folder_id'])
    refresh = read(HERE / 'lf2-white/current-reference-refresh.json')
    fresh_file = next(x['result']['file'] for x in refresh['entries'] if x['requested_id'] == file['id'])
    assert all(file[key] == fresh_file[key] for key in ['id', 'rev', 'size', 'path_display'])
    assert card['metadata_checked_utc'] == refresh['checked_utc']
    now = datetime.now(timezone.utc).isoformat()
    scope = ('Keep LF2/Position B white panel name and depicted component-position identity only. '
             'All six source/proposal groups remain unapproved. The related LF1 single-listing 40×20 versus square-family 35×35 '
             'size conflict remains unresolved; no measured dimensions, weighed mass, actual binder, '
             'rear hardware, correct-size price, stock, physical cast or current mould inventory is confirmed.')
    decision = {
        'schema_version': 1, 'decision_id': 'BC-LEAF-FORM:LEAF-FORM-LF2-WHITE:identity:keep',
        'recorded_utc': now, 'component_id': 'BC-LEAF-FORM', 'component_layout_id': layout_id,
        'canonical_name': card['proposed_name'], 'confirmed_name': card['proposed_name'],
        'review_number': 67, 'family_review_number': 2, 'action': 'keep',
        'user_statement': 'Keep “Leaf Form 2 — White (LF2)”',
        'status': 'USER CONFIRMED DEPICTED NAME AND COMPONENT-POSITION IDENTITY ONLY',
        'identity_confirmed': True, 'scope': scope,
        'scope_kind': 'INDIVIDUAL COMPONENT LAYOUT; NOT A NEW PATTERN OR MOULD CLAIM',
        'source_parent_bucket': 'BC-LEAF-FORM', 'individual_component_record_required': True,
        'catalogue_component_id_reconciliation_pending': True,
        'confirmed_fields': ['Individual component name', 'Depicted LF2/Position B white identity'],
        'not_confirmed': [x['field'] for x in card['specification_review_items']] +
                         ['Physical manufacture/mould inventory', 'Exact-size standalone platform offer'],
        'specifications_approved': False, 'proposals_approved': False, 'approved_proposal_ids': [],
        'physical_specs_verified': False, 'physical_manufacture_confirmed': False,
        'proposal_source': rel(card_path), 'proposal_source_sha256': sha(card_path),
        'primary_file_id': file['id'], 'evidence_file_id': file['id'], 'reference_file_id': None,
        'primary_folder_id': folder['id'], 'evidence_file_ids': [file['id']],
        'containing_folder_ids': [folder['id']],
        'current_dropbox_reference': {'file_id': file['id'], 'folder_id': folder['id'],
            'file_path': file['path_display'], 'folder_path': folder['path_display'],
            'rev': file['rev'], 'bytes': file['size'], 'image_url': card['primary_image_link'],
            'folder_url': card['primary_folder_link'], 'checked_utc': refresh['checked_utc'],
            'changed_since_owner_card': False, 'image_scope': 'Owner-reviewed LF2 primary photograph'},
        'image_link': card['primary_image_link'], 'folder_link': card['primary_folder_link'],
        'remote_files_changed': False, 'live_platform_records_changed': False,
        'workbook_status': 'Unchanged; owner name/identity decision saved in review overlay for later export.'}
    write(HERE / 'lf2-white/before-identity-keep.json', {
        'recorded_utc': now, 'files': {rel(paths[key]): value for key, value in before.items()},
        'protected_sha256': protected})
    write(output, decision)
    u['component_layout_identity_decisions'].append(decision | {'approval_record': rel(output)})
    u['identity_confirmation_counts'] = identity_counts(u)
    target.update({'identity_confirmed': True, 'canonical_name': card['proposed_name'],
        'identity_confirmed_utc': now, 'identity_approval': rel(output),
        'specification_review_status': 'LF2 NAME AND POSITION KEPT; ALL SIX GROUPS UNAPPROVED',
        'gaps': [x for x in target['gaps'] if x != 'Owner LF2name and depicted component-position identity']})
    assert not any(x.get('component_layout_id') == layout_id for x in cp['pending_specification_reviews'])
    cp['pending_specification_reviews'].append({
        'component_id': 'BC-LEAF-FORM', 'component_layout_id': layout_id,
        'canonical_name': card['proposed_name'], 'identity_approved': True, 'specifications_approved': False,
        'pending_fields': [x['field'] for x in card['specification_review_items']],
        'review_record': rel(card_path), 'identity_approval': rel(output),
        'image_link': card['primary_image_link'], 'folder_link': card['primary_folder_link'], 'scope': scope})
    family = p['family_review_progress']['Leaf Form']
    assert family['review_reference_cards_answered'] == 1 and family['review_reference_total'] == 3
    family.update({'review_reference_cards_answered': 2, 'updated_utc': now,
                   'last_identity_approval': rel(output), 'specifications_complete': False})
    state = 'LF2 White name and position kept; all six groups pending; Gold reference next'
    cp.update({'current_answer_recorded': True, 'state': state, 'answer_state': scope,
        'last_identity_approval': rel(output), 'last_completed_component_layout_id': layout_id, 'updated_utc': now})
    c['interactive_review_state'].update({'state': state,
        'components_with_any_identity_scope': u['identity_confirmation_counts']['components_with_any_identity_scope'],
        'explicit_component_layout_names': u['identity_confirmation_counts']['explicit_component_layout_names'],
        'last_identity_approval': rel(output), 'last_completed_component_layout_id': layout_id,
        'specification_proposals_approved': False})
    c.update({'last_identity_approval': rel(output), 'last_completed_component_layout_id': layout_id, 'updated_utc': now})
    u['updated_utc'] = p['updated_utc'] = now
    docs['root']['current_component_review'] = copy.deepcopy(c)
    docs['root']['updated_utc'] = now
    assert u['identity_confirmation_counts'] == before['user']['identity_confirmation_counts'] | {
        'explicit_component_layout_names': 4, 'components_with_any_identity_scope': 83}
    for key in ['specification_approval_counts', 'dimension_confirmation_counts']:
        assert u[key] == before['user'][key]
    for key in before['user']:
        if key not in ['component_layout_identity_decisions', 'identity_confirmation_counts', 'updated_utc']:
            assert u[key] == before['user'][key], key
    assert u['component_layout_identity_decisions'][:-1] == before['user']['component_layout_identity_decisions']
    for key in ['parallel_import_queue', 'parallel_owner_reviews', 'parallel_evidence_flags']:
        assert cp[key] == before['walkthrough'][key]
    assert cp['pending_specification_reviews'][:-1] == before['walkthrough']['pending_specification_reviews']
    assert all(p['reviews'][key] == value for key, value in before['progress']['reviews'].items() if key != 'BC-LEAF-FORM')
    assert parent['component_layouts']['LEAF-FORM-LF1-WHITE'] == before['progress']['reviews']['BC-LEAF-FORM']['component_layouts']['LEAF-FORM-LF1-WHITE']
    assert not parent['identity_confirmed'] and not any(x['owner_approved'] for x in target['specification_proposals'])
    assert all(sha(path) == hashes[key] for key, path in paths.items()), 'Shared writer collision'
    assert all(sha(Path(path)) == digest for path, digest in protected.items())
    for key, path in paths.items():
        write(path, docs[key])
        assert read(path) == docs[key]
    event = {'event_id': decision['decision_id'], 'event': 'INDIVIDUAL_COMPONENT_LAYOUT_NAME_AND_IDENTITY_KEPT',
        'recorded_utc': now, 'component_id': 'BC-LEAF-FORM', 'component_layout_id': layout_id,
        'identity_approval': rel(output), 'new_specification_approval_inferred': False}
    for path in [REVIEWS / 'identity_review_journal.jsonl', ROOT / 'review_journal.jsonl']:
        with path.open('a') as f:
            f.write(json.dumps(event, ensure_ascii=False) + '\n')
    result = {'status': 'PASS', 'kept_name': card['proposed_name'], 'layout_ledger_used': True,
        'parent_pattern_approval_not_inferred': True, 'all_six_groups_unapproved': True,
        'family_reference_answers': '2 of 3', 'baseline_model_workbook_cards_unchanged': True,
        'previous_approvals_imports_and_reservations_preserved': True,
        'checkpoint_copies_match': read(paths['root'])['current_component_review'] == read(paths['component'])}
    write(HERE / 'lf2-white/identity-keep-readback.json', result)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
