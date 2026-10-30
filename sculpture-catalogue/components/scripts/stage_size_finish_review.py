"""Advance an answered component to one complete, unapproved finish review."""
import argparse
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REVIEWS = ROOT / 'components/reviews'


def read(p):
    return json.loads(p.read_text())


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def write(p, value):
    temporary = p.with_name(p.name + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(p)


def rel(p):
    return str(p.relative_to(ROOT))


def stage(source):
    source = source.resolve()
    assert source.is_relative_to(REVIEWS)
    review = read(source)
    paths = {'walkthrough': REVIEWS / 'walkthrough_checkpoint.json', 'progress': REVIEWS / 'specification_review_progress.json',
             'component': ROOT / 'components/checkpoint.json', 'root': ROOT / 'checkpoint.json'}
    docs = {key: read(path) for key, path in paths.items()}
    cp, progress, component = (docs[k] for k in ['walkthrough', 'progress', 'component'])
    if cp.get('current_review_record') == rel(source):
        assert read(source.parent / 'review-validation.json')['status'] == 'PASS'
        return {'status': 'ALREADY_PREPARED'}
    cid, vid = review['component_id'], review['size_finish_variant_id']
    assert cp['current_component_id'] == cid and cp['current_answer_recorded']
    assert cp['next_review_after_keep']['component_id'] == cid and cp['next_review_after_keep']['size_finish_variant_id'] == vid
    assert review['variant_only_review'] and not review['identity_confirmed'] and not review['specifications_approved']
    assert not review['physical_specs_verified'] and review['photo_coverage']['complete_individual_front']
    assert review['family_review_total'] == len(cp['family_review_order'])
    items = review['specification_review_items']
    assert len(items) == len({x['proposal_id'] for x in items}) == 6
    assert all(not x.get('owner_approved', False) for x in items)
    assert docs['root']['current_component_review'] == component
    metadata = read(ROOT / review['reference_refresh'])
    file, folder = metadata['primary_metadata']['file'], metadata['folder_metadata']['folder']
    assert file['id'] == review['primary_image_id'] and folder['id'] == review['primary_folder_id']
    assert file['path_display'].rsplit('/', 1)[0] == folder['path_display']
    assert all(not x['has_more'] and not x['cursor'] for x in metadata['listings'].values())
    audit_path = ROOT / review['source_audit']
    audit = read(audit_path)
    assert audit['status'] == 'PASS'
    for path, expected in audit['evidence_sha256'].items():
        assert sha(Path(path)) == expected
    protected_paths = [source, audit_path, ROOT / 'components/evidence/component_register.json',
        ROOT / cp['register_workbook'], REVIEWS / 'user_classifications.json', ROOT / cp['current_review_record'],
        ROOT / cp['last_identity_approval'], ROOT / review['parent_identity_approval']]
    protected = {str(p): sha(p) for p in protected_paths}
    shared_hashes = {key: sha(path) for key, path in paths.items()}
    now = datetime.now(timezone.utc).isoformat()
    write(source.parent / 'before-stage-review.json', {'recorded_utc': now,
        'files': {rel(paths[k]): v for k, v in docs.items()}, 'protected_sha256': protected})
    before_reviews = copy.deepcopy(progress['reviews'])
    parent = progress['reviews'][cid]
    variants = parent.setdefault('size_finish_variants', {})
    assert vid not in variants
    variants[vid] = {'reviewed_utc': now, 'identity_confirmed': False, 'specifications_approved': False,
        'proposals_approved': False, 'physical_specs_verified': False, 'proposed_name': review['proposed_name'],
        'size_finish_variant_id': vid, 'review_record': rel(source), 'primary_image_id': file['id'], 'primary_folder_id': folder['id'],
        'specification_proposals': copy.deepcopy(items), 'platform_mapping': copy.deepcopy(review['platform_mapping']),
        'photo_coverage': copy.deepcopy(review['photo_coverage']), 'parent_design_relationship_status': review['parent_design_relationship_status']}
    pending = parent.get('pending_size_finish_variants', [])
    assert any(x['variant_id'] == vid for x in pending)
    for x in pending:
        if x['variant_id'] == vid:
            x.update({'review_status': 'AWAITING DEPICTED NAME; SIX SPECIFICATION GROUPS SEPARATELY PENDING', 'review_record': rel(source)})
    progress['updated_utc'] = now
    links = {x['file_name']: x for x in metadata['previews']}
    state = 'Awaiting ' + review['proposed_name'] + ' depicted name/identity; six source/working groups remain pending'
    cp.update({'current_size_finish_variant_id': vid, 'proposed_name': review['proposed_name'], 'state': state,
        'primary_image': {'file_id': file['id'], 'name': file['name'], 'path_display': file['path_display'],
            'copy_link_url': review['primary_image_link'], 'open_in_dropbox_url': links[file['id']]['open_in_dropbox_url']},
        'containing_folder': {'folder_id': folder['id'], 'name': folder['name'], 'path_display': folder['path_display'],
            'copy_link_url': review['primary_folder_link'], 'open_in_dropbox_url': links[folder['id']]['open_in_dropbox_url']},
        'current_answer_recorded': False, 'current_specification_answer_recorded': False, 'current_dimension_answer_recorded': False,
        'working_version_user_approved': False, 'current_review_record': rel(source),
        'review_decision_mode': 'SIZE_FINISH_VARIANT_NAME_AND_SPECIFICATIONS', 'current_family_review_number': review['family_review_number'],
        'family_review_evidence': review['reference_refresh'], 'answer_state': 'No answer yet. Named Keep confirms depicted name/identity only; all six specification groups remain pending.',
        'question_scope': review['scope'], 'metadata_checked_utc': review['metadata_checked_utc'],
        'next_review_after_keep': copy.deepcopy(review['next_review_after_keep']),
        'displayed_identity_evidence_file_ids': [file['id']], 'displayed_identity_evidence_folder_ids': [folder['id']],
        'current_component_source_notes': [x['display'] for x in items], 'updated_utc': now})
    component['interactive_review_state'].update({'current_size_finish_variant_id': vid, 'current_name': review['proposed_name'],
        'state': state, 'family_review_number': review['family_review_number'], 'family_review_total': review['family_review_total'],
        'specification_proposals_approved': False, 'working_version_user_approved': False,
        'review_decision_mode': 'SIZE_FINISH_VARIANT_NAME_AND_SPECIFICATIONS'})
    component.update({'current_component_review_record': rel(source), 'updated_utc': now,
        'last_family_media_review': {'family': review['family'], 'finish': review['proposed_name'],
            'observed_utc': review['metadata_checked_utc'], 'files': sum(len(x['entries']) for x in metadata['listings'].values()),
            'folders': len(metadata['listings']), 'scope': review['photo_coverage']['scope'],
            'evidence': review['reference_refresh'], 'workbook_contains_this_live_media_audit': False}})
    docs['root']['current_component_review'] = copy.deepcopy(component)
    docs['root']['updated_utc'] = now
    for old_cid, before in before_reviews.items():
        if old_cid != cid:
            assert progress['reviews'][old_cid] == before
        else:
            for key, value in before.items():
                if key == 'size_finish_variants':
                    for old_vid, old_value in value.items():
                        assert parent[key][old_vid] == old_value
                elif key != 'pending_size_finish_variants':
                    assert parent[key] == value
    assert all(sha(paths[k]) == value for k, value in shared_hashes.items()), 'Shared writer collision'
    for key, path in paths.items():
        write(path, docs[key])
        assert read(path) == docs[key]
    assert read(paths['root'])['current_component_review'] == read(paths['component'])
    assert all(sha(Path(path)) == value for path, value in protected.items())
    result = {'status': 'PASS', 'variant_id': vid, 'source_audit': review['source_audit'], 'six_unapproved_groups': 6,
        'prior_owner_decisions_model_workbook_and_ledger_unchanged': True, 'queues_and_reservations_unchanged': True,
        'root_and_component_agree': True, 'remote_files_changed': False}
    write(source.parent / 'review-validation.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--review', required=True)
    args = parser.parse_args()
    p = Path(args.review)
    print(json.dumps(stage(p if p.is_absolute() else ROOT / p)))
