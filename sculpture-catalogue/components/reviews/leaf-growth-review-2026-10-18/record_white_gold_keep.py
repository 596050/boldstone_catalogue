"""Record the intended White/Gold identity; close reference review with specification/photo gaps intact."""
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
    output = HERE / 'white-gold/identity-approval.json'
    assert not output.exists(), 'White/Gold identity already kept'
    paths = {'user': REVIEWS / 'user_classifications.json', 'progress': REVIEWS / 'specification_review_progress.json',
        'walkthrough': REVIEWS / 'walkthrough_checkpoint.json', 'component': ROOT / 'components/checkpoint.json',
        'root': ROOT / 'checkpoint.json'}
    docs = {key: read(path) for key, path in paths.items()}
    before = copy.deepcopy(docs)
    hashes = {key: sha(path) for key, path in paths.items()}
    u, p, cp, c = (docs[key] for key in ['user', 'progress', 'walkthrough', 'component'])
    variant = 'LEAF-GROWTH-WHITE-GOLD'
    assert cp['current_component_id'] == 'BC-LEAF-GROWTH' and cp['current_size_finish_variant_id'] == variant
    assert not cp['current_answer_recorded'] and docs['root']['current_component_review'] == c
    card_path = ROOT / cp['current_review_record']
    card = read(card_path)
    assert card['proposed_name'] == 'Leaf Growth — White and Gold Leaf'
    target = p['reviews']['BC-LEAF-GROWTH']['size_finish_variants'][variant]
    assert not target['identity_confirmed']
    assert not any(x.get('size_finish_variant_id') == variant for x in u['size_finish_variant_decisions'])
    protected_paths = [card_path, HERE / 'component-review.json', HERE / 'identity-approval.json',
        ROOT / 'components/evidence/component_register.json', ROOT / cp['register_workbook']]
    protected = {str(path): sha(path) for path in protected_paths}
    current = read(HERE / 'white-gold/keep-current-reference.json')
    file = current['result']['file']
    prior = next(x['file'] for x in read(HERE / 'selected-metadata.json')['entries'] if x['requested_id'] == file['id'])
    assert all(file[key] == prior[key] for key in ['id', 'rev', 'size', 'path_display'])
    assert file['id'] == card['primary_image_id']
    now = datetime.now(timezone.utc).isoformat()
    scope = ('Keep the White and Gold Leaf name and intended Leaf Growth component identity for the reviewed detail reference. '
        'All six conditional specifications remain unapproved, including100×30×6cm,18kgproposal, binder/real gold content, '
        'rear fixing, uncosted900GBPprice and availability. Full-panel outline, in-situ/series/rear photographs, '
        'actual cast/mould, exact Gold platform offer and White18kgversus12kgdifference remain unresolved.')
    decision = {'schema_version': 1, 'decision_id': 'BC-LEAF-GROWTH:LEAF-GROWTH-WHITE-GOLD:identity:keep',
        'recorded_utc': now, 'component_id': 'BC-LEAF-GROWTH', 'size_finish_variant_id': variant,
        'canonical_name': card['proposed_name'], 'confirmed_name': card['proposed_name'], 'review_number': 68,
        'family_review_number': 2, 'action': 'keep', 'user_statement': 'Keep “Leaf Growth — White and Gold Leaf”',
        'status': 'USER CONFIRMED DETAIL-REFERENCE NAME AND INTENDED COMPONENT IDENTITY ONLY',
        'identity_confirmed': True, 'scope': scope, 'complete_panel_outline_visually_verified': False,
        'specifications_approved': False, 'proposals_approved': False, 'approved_proposal_ids': [],
        'physical_specs_verified': False, 'physical_manufacture_confirmed': False,
        'confirmed_fields': ['White/Gold finish name', 'Intended Leaf Growth identity of reviewed cropped reference'],
        'not_confirmed': [x['field'] for x in card['specification_review_items']] +
            ['Full panel silhouette/dimensions', 'Real gold composition', 'Physical cast/mould inventory', 'Exact Gold platform offer'],
        'proposal_source': rel(card_path), 'proposal_source_sha256': sha(card_path),
        'primary_file_id': file['id'], 'evidence_file_id': file['id'], 'primary_folder_id': card['primary_folder_id'],
        'evidence_file_ids': [file['id']], 'containing_folder_ids': [card['primary_folder_id']],
        'image_link': card['primary_image_link'], 'folder_link': card['primary_folder_link'],
        'current_dropbox_reference': {'file_id': file['id'], 'folder_id': card['primary_folder_id'],
            'file_path': file['path_display'], 'rev': file['rev'], 'bytes': file['size'],
            'checked_utc': current['checked_utc'], 'changed_since_owner_card': False,
            'image_url': card['primary_image_link'], 'folder_url': card['primary_folder_link'], 'scope': 'Cropped detail reference only'},
        'remote_files_changed': False, 'live_platform_records_changed': False,
        'workbook_status': 'Unchanged; name/identity saved in local review overlay for later export.'}
    write(HERE / 'white-gold/before-identity-keep.json', {'recorded_utc': now,
        'files': {rel(paths[key]): value for key, value in before.items()}, 'protected_sha256': protected})
    write(output, decision)
    u['size_finish_variant_decisions'].append(decision | {'approval_record': rel(output)})
    u['identity_confirmation_counts'] = identity_counts(u)
    target.update({'identity_confirmed': True, 'canonical_name': card['proposed_name'], 'identity_confirmed_utc': now,
        'identity_approval': rel(output), 'complete_panel_outline_visually_verified': False,
        'specification_review_status': 'INTENDED DETAIL-REFERENCE NAME KEPT; SIX GROUPS AND MISSING FULL PANEL PHOTOS PENDING',
        'gaps': [x for x in target['gaps'] if x != 'Owner detail-reference name and intended Leaf Growth identity']})
    assert not any(x.get('size_finish_variant_id') == variant for x in cp['pending_specification_reviews'])
    cp['pending_specification_reviews'].append({'component_id': 'BC-LEAF-GROWTH', 'size_finish_variant_id': variant,
        'canonical_name': card['proposed_name'], 'identity_approved': True, 'specifications_approved': False,
        'pending_fields': [x['field'] for x in card['specification_review_items']], 'review_record': rel(card_path),
        'identity_approval': rel(output), 'image_link': card['primary_image_link'], 'folder_link': card['primary_folder_link'], 'scope': scope})
    family = copy.deepcopy(p['family_review_progress']['Leaf Growth'])
    assert family['review_reference_cards_answered'] == 1 and family['review_reference_total'] == 2
    family.update({'status': 'FIRST_PASS_REFERENCE_REVIEWS_COMPLETE_SPECIFICATIONS_AND_PHOTOS_PENDING',
        'updated_utc': now, 'review_reference_cards_answered': 2, 'last_identity_approval': rel(output),
        'first_pass_reference_review_complete': True, 'specifications_complete': False, 'physical_specs_verified': False})
    family_path = HERE / 'family-first-pass-review.json'
    write(family_path, family | {'scope': 'Two named references answered; all12specification groups unapproved. Gold complete-panel/installation/series/rear images remain missing. No physical sculpture or mould total inferred.',
        'component_ids': ['BC-LEAF-GROWTH'], 'approved_name_records': [rel(HERE / 'identity-approval.json'), rel(output)],
        'next_review': cp['next_review_after_keep'], 'workbook_contains_this_first_pass': False})
    family['first_pass_record'] = rel(family_path)
    p['family_review_progress']['Leaf Growth'] = family
    state = 'Leaf Growth names kept; reference first pass complete; specifications/photos pending; Moon Crater Phase1 next'
    cp.update({'current_answer_recorded': True, 'state': state, 'answer_state': scope, 'last_identity_approval': rel(output),
        'last_size_finish_variant_identity_approval': rel(output), 'last_completed_size_finish_variant_id': variant,
        'family_first_pass_complete': True, 'last_completed_family_first_pass': rel(family_path), 'updated_utc': now})
    c['interactive_review_state'].update({'state': state, 'last_identity_approval': rel(output),
        'explicit_size_finish_variant_names_confirmed': u['identity_confirmation_counts']['explicit_size_finish_variant_names'],
        'last_completed_size_finish_variant_id': variant, 'specification_proposals_approved': False})
    c.update({'last_identity_approval': rel(output), 'last_completed_family_first_pass': rel(family_path), 'updated_utc': now})
    u['updated_utc'] = p['updated_utc'] = now
    docs['root']['current_component_review'] = copy.deepcopy(c)
    docs['root']['updated_utc'] = now
    assert u['identity_confirmation_counts'] == before['user']['identity_confirmation_counts'] | {'explicit_size_finish_variant_names': 73}
    for key in before['user']:
        if key not in ['size_finish_variant_decisions', 'identity_confirmation_counts', 'updated_utc']:
            assert u[key] == before['user'][key], key
    assert u['size_finish_variant_decisions'][:-1] == before['user']['size_finish_variant_decisions']
    assert p['reviews']['BC-LEAF-GROWTH']['specification_proposals'] == before['progress']['reviews']['BC-LEAF-GROWTH']['specification_proposals']
    assert all(p['reviews'][key] == value for key, value in before['progress']['reviews'].items() if key != 'BC-LEAF-GROWTH')
    for key in ['parallel_import_queue', 'parallel_owner_reviews', 'parallel_evidence_flags']:
        assert cp[key] == before['walkthrough'][key]
    assert cp['pending_specification_reviews'][:-1] == before['walkthrough']['pending_specification_reviews']
    assert all(sha(path) == hashes[key] for key, path in paths.items()), 'Shared writer collision'
    assert all(sha(Path(path)) == digest for path, digest in protected.items())
    for key, path in paths.items():
        write(path, docs[key])
        assert read(path) == docs[key]
    event = {'event_id': decision['decision_id'], 'event': 'SIZE_FINISH_DETAIL_REFERENCE_NAME_AND_IDENTITY_KEPT',
        'recorded_utc': now, 'component_id': 'BC-LEAF-GROWTH', 'size_finish_variant_id': variant,
        'identity_approval': rel(output), 'new_specification_approval_inferred': False}
    for path in [REVIEWS / 'identity_review_journal.jsonl', ROOT / 'review_journal.jsonl']:
        with path.open('a') as f:
            f.write(json.dumps(event, ensure_ascii=False) + '\n')
    result = {'status': 'PASS', 'kept_name': card['proposed_name'], 'all_six_groups_unapproved': True,
        'missing_full_panel_and_context_photos_preserved': True, 'family_reference_names_answered': '2 of 2',
        'previous_reviews_imports_reservations_model_workbook_and_source_cards_preserved': True,
        'checkpoint_copies_match': read(paths['root'])['current_component_review'] == read(paths['component'])}
    write(HERE / 'white-gold/identity-keep-readback.json', result)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
