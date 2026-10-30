"""Keep the Gold finish name/depicted LF2 identity; close reference first pass only."""
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
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    tmp.replace(path)


def main():
    output = HERE / 'gold/identity-approval.json'
    assert not output.exists(), 'Gold identity already recorded'
    paths = {'user': REVIEWS / 'user_classifications.json', 'progress': REVIEWS / 'specification_review_progress.json',
        'walkthrough': REVIEWS / 'walkthrough_checkpoint.json', 'component': ROOT / 'components/checkpoint.json',
        'root': ROOT / 'checkpoint.json'}
    docs = {key: read(path) for key, path in paths.items()}
    before = copy.deepcopy(docs)
    hashes = {key: sha(path) for key, path in paths.items()}
    u, p, cp, c = (docs[key] for key in ['user', 'progress', 'walkthrough', 'component'])
    variant = 'LEAF-FORM-GOLD'
    assert cp['current_component_id'] == 'BC-LEAF-FORM' and cp['current_size_finish_variant_id'] == variant
    assert not cp['current_answer_recorded'] and docs['root']['current_component_review'] == c
    card_path = ROOT / cp['current_review_record']
    card = read(card_path)
    assert card['proposed_name'] == 'Leaf Form 2 — Gold (LF2)' and not card['identity_confirmed']
    assert card['identity_decision_destination'] == 'size_finish_variant_decisions'
    target = p['reviews']['BC-LEAF-FORM']['size_finish_variants'][variant]
    assert not target['identity_confirmed']
    assert not any(x.get('size_finish_variant_id') == variant for x in u['size_finish_variant_decisions'])
    protected_paths = [card_path, ROOT / 'components/evidence/component_register.json', ROOT / cp['register_workbook'],
        HERE / 'lf1-white/component-review.json', HERE / 'lf1-white/identity-approval.json',
        HERE / 'lf2-white/component-review.json', HERE / 'lf2-white/identity-approval.json']
    protected = {str(path): sha(path) for path in protected_paths}
    current = read(HERE / 'gold/keep-current-reference.json')
    file = current['result']['file']
    prior = read(HERE / 'gold/current-reference-refresh.json')['entries'][0]['result']['file']
    assert all(file[key] == prior[key] for key in ['id', 'rev', 'size', 'path_display'])
    assert file['id'] == card['primary_image_id']
    now = datetime.now(timezone.utc).isoformat()
    scope = ('Keep Leaf Form2Gold name, visible Gold finish and depicted LF2/Position B identity only. '
        'All six conditional specifications remain unapproved, including35×35×6cm, conditional6–8kg, '
        'actual binder/gold-leaf composition, rear hardware, uncosted400GBPprice and availability. '
        'No physical Gold cast, mould equivalence, exact platform offer or room-scene provenance is confirmed.')
    decision = {'schema_version': 1, 'decision_id': 'BC-LEAF-FORM:LEAF-FORM-GOLD:identity:keep',
        'component_id': 'BC-LEAF-FORM', 'size_finish_variant_id': variant, 'recorded_utc': now,
        'canonical_name': card['proposed_name'], 'confirmed_name': card['proposed_name'],
        'review_number': 67, 'family_review_number': 3, 'action': 'keep',
        'user_statement': 'Keep “Leaf Form 2 — Gold (LF2)”',
        'status': 'USER CONFIRMED DEPICTED NAME AND FINISH/POSITION IDENTITY ONLY',
        'scope': scope, 'identity_confirmed': True, 'depicted_position_confirmed_by_owner': 'LF2/Position B',
        'specifications_approved': False, 'proposals_approved': False, 'approved_proposal_ids': [],
        'physical_specs_verified': False, 'physical_manufacture_confirmed': False,
        'confirmed_fields': ['Individual component finish name', 'Depicted LF2/Position B Gold identity'],
        'not_confirmed': [x['field'] for x in card['specification_review_items']] +
            ['Physical cast/mould inventory', 'Actual gold-leaf composition', 'Exact platform offer', 'Room-scene provenance'],
        'proposal_source': rel(card_path), 'proposal_source_sha256': sha(card_path),
        'primary_file_id': file['id'], 'evidence_file_id': file['id'], 'primary_folder_id': card['primary_folder_id'],
        'evidence_file_ids': [file['id']], 'containing_folder_ids': [card['primary_folder_id']],
        'image_link': card['primary_image_link'], 'folder_link': card['primary_folder_link'],
        'current_dropbox_reference': {'file_id': file['id'], 'folder_id': card['primary_folder_id'],
            'file_path': file['path_display'], 'rev': file['rev'], 'bytes': file['size'],
            'checked_utc': current['checked_utc'], 'changed_since_owner_card': False,
            'image_url': card['primary_image_link'], 'folder_url': card['primary_folder_link'],
            'scope': 'Selected room reference and depicted Gold LF2identity only; physical provenance unconfirmed'},
        'remote_files_changed': False, 'live_platform_records_changed': False,
        'workbook_status': 'Unchanged; name/identity overlay saved for later export.'}
    write(HERE / 'gold/before-identity-keep.json', {'recorded_utc': now,
        'files': {rel(paths[key]): value for key, value in before.items()}, 'protected_sha256': protected})
    write(output, decision)
    u['size_finish_variant_decisions'].append(decision | {'approval_record': rel(output)})
    u['identity_confirmation_counts'] = identity_counts(u)
    target.update({'identity_confirmed': True, 'canonical_name': card['proposed_name'],
        'identity_confirmed_utc': now, 'identity_approval': rel(output),
        'depicted_position_confirmed_by_owner': 'LF2/Position B',
        'specification_review_status': 'GOLD NAME AND DEPICTED LF2IDENTITY KEPT; ALL SIX CONDITIONAL GROUPS UNAPPROVED',
        'gaps': [x for x in target['gaps'] if x != 'Owner Gold name and depicted LF2position identity']})
    assert not any(x.get('size_finish_variant_id') == variant for x in cp['pending_specification_reviews'])
    cp['pending_specification_reviews'].append({'component_id': 'BC-LEAF-FORM', 'size_finish_variant_id': variant,
        'canonical_name': card['proposed_name'], 'identity_approved': True, 'specifications_approved': False,
        'pending_fields': [x['field'] for x in card['specification_review_items']],
        'review_record': rel(card_path), 'identity_approval': rel(output), 'image_link': card['primary_image_link'],
        'folder_link': card['primary_folder_link'], 'scope': scope})
    family = copy.deepcopy(p['family_review_progress']['Leaf Form'])
    assert family['review_reference_cards_answered'] == 2 and family['review_reference_total'] == 3
    family.update({'status': 'FIRST_PASS_REFERENCE_REVIEWS_COMPLETE_SPECIFICATIONS_PENDING', 'updated_utc': now,
        'review_reference_cards_answered': 3, 'last_identity_approval': rel(output),
        'first_pass_reference_review_complete': True, 'specifications_complete': False,
        'physical_specs_verified': False, 'reference_total_is_sculpture_count': False})
    family_path = HERE / 'family-first-pass-review.json'
    write(family_path, family | {'scope': 'Three named component-position/finish references answered; all18specification groups remain unapproved. No physical sculpture, cast or mould count inferred.',
        'component_ids': ['BC-LEAF-FORM'], 'approved_name_records': [rel(HERE / 'lf1-white/identity-approval.json'),
            rel(HERE / 'lf2-white/identity-approval.json'), rel(output)],
        'all_six_groups_pending_per_reference': True, 'next_review': cp['next_review_after_keep'],
        'workbook_contains_this_first_pass': False})
    family['first_pass_record'] = rel(family_path)
    p['family_review_progress']['Leaf Form'] = family
    state = 'Leaf Form Gold name kept; three reference identities answered; specifications pending; Leaf Growth next'
    cp.update({'current_answer_recorded': True, 'state': state, 'answer_state': scope,
        'last_identity_approval': rel(output), 'last_size_finish_variant_identity_approval': rel(output),
        'last_completed_size_finish_variant_id': variant, 'family_first_pass_complete': True,
        'last_completed_family_first_pass': rel(family_path), 'updated_utc': now})
    c['interactive_review_state'].update({'state': state,
        'explicit_size_finish_variant_names_confirmed': u['identity_confirmation_counts']['explicit_size_finish_variant_names'],
        'components_with_any_identity_scope': u['identity_confirmation_counts']['components_with_any_identity_scope'],
        'last_identity_approval': rel(output), 'last_completed_size_finish_variant_id': variant,
        'specification_proposals_approved': False})
    c.update({'last_identity_approval': rel(output), 'last_completed_family_first_pass': rel(family_path), 'updated_utc': now})
    u['updated_utc'] = p['updated_utc'] = now
    docs['root']['current_component_review'] = copy.deepcopy(c)
    docs['root']['updated_utc'] = now
    assert u['identity_confirmation_counts'] == before['user']['identity_confirmation_counts'] | {'explicit_size_finish_variant_names': 72}
    for key in before['user']:
        if key not in ['size_finish_variant_decisions', 'identity_confirmation_counts', 'updated_utc']:
            assert u[key] == before['user'][key], key
    assert u['size_finish_variant_decisions'][:-1] == before['user']['size_finish_variant_decisions']
    assert p['reviews']['BC-LEAF-FORM']['component_layouts'] == before['progress']['reviews']['BC-LEAF-FORM']['component_layouts']
    assert not p['reviews']['BC-LEAF-FORM']['identity_confirmed']
    assert all(p['reviews'][key] == value for key, value in before['progress']['reviews'].items() if key != 'BC-LEAF-FORM')
    for key in ['parallel_import_queue', 'parallel_owner_reviews', 'parallel_evidence_flags']:
        assert cp[key] == before['walkthrough'][key]
    assert cp['pending_specification_reviews'][:-1] == before['walkthrough']['pending_specification_reviews']
    assert all(sha(path) == hashes[key] for key, path in paths.items()), 'Shared writer collision'
    assert all(sha(Path(path)) == digest for path, digest in protected.items())
    for key, path in paths.items():
        write(path, docs[key])
        assert read(path) == docs[key]
    event = {'event_id': decision['decision_id'], 'event': 'SIZE_FINISH_NAME_AND_DEPICTED_POSITION_IDENTITY_KEPT',
        'component_id': 'BC-LEAF-FORM', 'size_finish_variant_id': variant, 'recorded_utc': now,
        'identity_approval': rel(output), 'new_specification_approval_inferred': False}
    for path in [REVIEWS / 'identity_review_journal.jsonl', ROOT / 'review_journal.jsonl']:
        with path.open('a') as f:
            f.write(json.dumps(event, ensure_ascii=False) + '\n')
    result = {'status': 'PASS', 'kept_name': card['proposed_name'], 'six_Gold_specifications_unapproved': True,
        'family_reference_names_answered': '3 of 3', 'family_specifications_complete': False,
        'previous_approvals_reservations_and_imports_preserved': True, 'model_workbook_source_cards_unchanged': True,
        'checkpoint_copies_match': read(paths['root'])['current_component_review'] == read(paths['component'])}
    write(HERE / 'gold/identity-keep-readback.json', result)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
