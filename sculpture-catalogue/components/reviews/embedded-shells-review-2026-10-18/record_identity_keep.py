"""Keep the owner's depicted name; preserve the separately stated face and pending fields."""
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


def write(p, value):
    t = p.with_name(p.name + '.tmp')
    t.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    t.replace(p)


def main():
    output = HERE / 'identity-approval.json'
    assert not output.exists(), 'Already kept'
    paths = {'user': REVIEWS / 'user_classifications.json', 'progress': REVIEWS / 'specification_review_progress.json',
        'walkthrough': REVIEWS / 'walkthrough_checkpoint.json', 'component': ROOT / 'components/checkpoint.json', 'root': ROOT / 'checkpoint.json'}
    docs = {k: read(p) for k, p in paths.items()}
    before = copy.deepcopy(docs)
    hashes = {k: sha(p) for k, p in paths.items()}
    u, p, cp, c = (docs[k] for k in ['user', 'progress', 'walkthrough', 'component'])
    assert cp['current_component_id'] == 'BC-EMBED-SHELLS' and not cp['current_answer_recorded']
    assert cp['current_dimension_answer_recorded'] and docs['root']['current_component_review'] == c
    card_path = ROOT / cp['current_review_record']
    card = read(card_path)
    face = {'height': 70, 'width': 15, 'depth': None}
    assert card['proposed_name'] == 'Embedded Shells — White' and card['owner_face_dimensions_cm'] == face
    target = p['reviews']['BC-EMBED-SHELLS']
    assert target['owner_face_dimensions_cm'] == face and not target['identity_confirmed']
    assert not any(x['component_id'] == 'BC-EMBED-SHELLS' for x in u['decisions'])
    protected = {str(x): sha(x) for x in [card_path, ROOT / card['dimension_approval'],
        ROOT / 'components/evidence/component_register.json', ROOT / cp['register_workbook']]}
    now = datetime.now(timezone.utc).isoformat()
    decision = {'schema_version': 1, 'decision_id': 'BC-EMBED-SHELLS:identity:keep', 'recorded_utc': now,
        'component_id': 'BC-EMBED-SHELLS', 'size_finish_variant_id': 'EMBED-SHELLS-WHITE',
        'canonical_name': card['proposed_name'], 'confirmed_name': card['proposed_name'], 'proposed_name_at_review': card['proposed_name'],
        'review_number': 45, 'family_review_number': 1, 'action': 'keep', 'user_statement': 'Keep “Embedded Shells — White”',
        'identity_status': 'USER CONFIRMED', 'status': 'USER CONFIRMED NAME AND DEPICTED IDENTITY ONLY',
        'scope': 'Keep this depicted individual off-white shell-relief name and identity. Previously stated70×15cmface is preserved separately. Depth, other specification guesses, manufacture, stock and exact offers are unapproved.',
        'confirmed_fields': ['Component name', 'Depicted individual component identity', 'Retain individual component catalogue record'],
        'not_confirmed': ['Depth/maximum projection', 'Actual weight', 'Material/binder/shell inclusions/backing/finish/sealing',
            'Fixing hardware/count/attachment/load', 'Individual price', 'Availability/stock/reproducibility/lead time',
            'Physical manufacture/mould inventory', 'Exact Squarespace/Shopify match', 'Setting provenance'],
        'identity_confirmed': True, 'specifications_approved': False, 'proposals_approved': False,
        'approved_proposal_ids': [], 'physical_specs_verified': False, 'physical_manufacture_confirmed': False,
        'proposal_source': rel(card_path), 'proposal_source_sha256': sha(card_path),
        'prior_owner_face_dimensions_cm': face, 'prior_dimension_approval': card['dimension_approval'],
        'evidence_file_id': card['primary_image_id'], 'containing_folder_id': card['primary_folder_id'],
        'evidence_file_ids': [card['primary_image_id']], 'containing_folder_ids': [card['primary_folder_id']],
        'image_link': card['primary_image_link'], 'folder_link': card['primary_folder_link'],
        'remote_files_changed': False, 'live_platform_records_changed': False,
        'workbook_status': 'Unchanged; owner identity decision recorded in local overlay for later export.'}
    write(HERE / 'before-identity-keep.json', {'recorded_utc': now, 'files': {rel(paths[k]): v for k, v in before.items()}, 'protected_sha256': protected})
    write(output, decision)
    u['decisions'].append(decision | {'approval_record': rel(output)})
    u['identity_confirmation_counts'] = identity_counts(u)
    target.update({'identity_confirmed': True, 'canonical_name': card['proposed_name'], 'identity_confirmed_utc': now,
        'identity_approval': rel(output), 'specification_review_status': 'NAME KEPT; OWNER70×15FACE PRESERVED; DEPTH AND FIVE OTHER GROUPS PENDING',
        'gaps': [x for x in target['gaps'] if x != 'Owner name and identity']})
    pending = {'component_id': 'BC-EMBED-SHELLS', 'size_finish_variant_id': 'EMBED-SHELLS-WHITE',
        'canonical_name': card['proposed_name'], 'identity_approved': True, 'specifications_approved': False,
        'owner_face_dimensions_cm': face, 'dimension_approval': card['dimension_approval'],
        'pending_fields': ['Depth/maximum projection'] + [x['field'] for x in card['specification_review_items'][1:]],
        'review_record': rel(card_path), 'identity_approval': rel(output), 'image_link': card['primary_image_link'],
        'folder_link': card['primary_folder_link'], 'scope': decision['scope']}
    assert not any(x['component_id'] == 'BC-EMBED-SHELLS' for x in cp['pending_specification_reviews'])
    cp['pending_specification_reviews'].append(pending)
    family = {'family': 'Embedded Shells', 'status': 'FIRST_PASS_DEPICTED_IDENTITY_QUESTION_ANSWERED',
        'completed_utc': now, 'review_reference_count': 1, 'identity_approval': rel(output),
        'specifications_complete': False, 'scope': 'One individual depicted design named.70×15cmface previously supplied; remaining fields and manufacture unresolved.'}
    p.setdefault('family_review_progress', {})['Embedded Shells'] = family
    state = 'Embedded Shells White name kept;70×15cmface preserved; depth and other specifications pending'
    cp.update({'current_answer_recorded': True, 'state': state, 'answer_state': decision['scope'],
        'last_identity_approval': rel(output), 'family_first_pass_complete': True, 'last_completed_family_first_pass': family,
        'updated_utc': now})
    c['interactive_review_state'].update({'state': state, 'explicit_identity_confirmations': u['identity_confirmation_counts']['component_designs'],
        'components_with_any_identity_scope': u['identity_confirmation_counts']['components_with_any_identity_scope'],
        'specification_proposals_approved': False, 'current_owner_face_dimensions_cm': face})
    c['last_completed_family_first_pass'] = family
    c['last_identity_approval'] = rel(output)
    c['updated_utc'] = p['updated_utc'] = u['updated_utc'] = now
    docs['root']['current_component_review'] = copy.deepcopy(c)
    docs['root']['updated_utc'] = now
    assert u['specification_approval_counts'] == before['user']['specification_approval_counts']
    assert u['dimension_confirmation_counts'] == before['user']['dimension_confirmation_counts']
    assert u['identity_confirmation_counts']['component_designs'] == 39
    assert cp['parallel_import_queue'] == before['walkthrough']['parallel_import_queue']
    assert cp['parallel_owner_reviews'] == before['walkthrough']['parallel_owner_reviews']
    assert target['owner_face_dimensions_cm'] == face and not target['specifications_approved']
    assert all(sha(path) == hashes[k] for k, path in paths.items()), 'Shared writer collision'
    assert all(sha(Path(path)) == digest for path, digest in protected.items())
    for key, path in paths.items():
        write(path, docs[key])
        assert read(path) == docs[key]
    assert read(paths['root'])['current_component_review'] == read(paths['component'])
    event = {'event_id': decision['decision_id'], 'event': 'COMPONENT_NAME_AND_DEPICTED_IDENTITY_KEPT',
        'recorded_utc': now, 'component_id': 'BC-EMBED-SHELLS', 'identity_approval': rel(output),
        'owner_face_cm_preserved': [70, 15], 'new_specification_approval_inferred': False}
    for path in [REVIEWS / 'identity_review_journal.jsonl', ROOT / 'review_journal.jsonl']:
        with path.open('a') as f:
            f.write(json.dumps(event, ensure_ascii=False) + '\n')
    result = {'status': 'PASS', 'kept_name': card['proposed_name'], 'owner_face_cm_preserved': [70, 15],
        'specification_approval_inferred': False, 'baseline_model_workbook_and_source_card_unchanged': True,
        'queues_and_reservations_preserved': True, 'checkpoint_copies_match': True}
    write(HERE / 'identity-keep-readback.json', result)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
