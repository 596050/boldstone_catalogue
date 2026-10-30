"""Present the prepared LF2 position after the LF1 name-only answer."""
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


def write(path, value):
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temp.replace(path)


def dbx_hash(path):
    chunks = []
    with path.open('rb') as f:
        while block := f.read(4 * 1024 * 1024):
            chunks.append(hashlib.sha256(block).digest())
    return hashlib.sha256(b''.join(chunks)).hexdigest()


def main():
    output = HERE / 'lf2-white/component-review.json'
    assert not output.exists(), 'LF2 already staged'
    paths = {'progress': REVIEWS / 'specification_review_progress.json',
             'walkthrough': REVIEWS / 'walkthrough_checkpoint.json',
             'component': ROOT / 'components/checkpoint.json', 'root': ROOT / 'checkpoint.json'}
    docs = {key: read(path) for key, path in paths.items()}
    before = copy.deepcopy(docs)
    hashes = {key: sha(path) for key, path in paths.items()}
    p, cp, c = (docs[key] for key in ['progress', 'walkthrough', 'component'])
    assert cp['current_component_layout_id'] == 'LEAF-FORM-LF1-WHITE' and cp['current_answer_recorded']
    assert docs['root']['current_component_review'] == c
    keep_path = ROOT / cp['last_identity_approval']
    keep = read(keep_path)
    assert keep['component_layout_id'] == 'LEAF-FORM-LF1-WHITE' and not keep['specifications_approved']
    draft_path = HERE / 'lf2-white/component-review.draft.json'
    card = read(draft_path)
    assert card['component_layout_id'] == 'LEAF-FORM-LF2-WHITE'
    assert cp['next_review_after_keep']['component_layout_id'] == card['component_layout_id']
    protected_paths = [REVIEWS / 'user_classifications.json', draft_path, keep_path,
        HERE / 'lf1-white/component-review.json', HERE / 'source-audit.json',
        ROOT / 'components/evidence/component_register.json', ROOT / cp['register_workbook']]
    protected = {str(path): sha(path) for path in protected_paths}
    meta = read(HERE / 'metadata-links.json')
    refresh_path = HERE / 'lf2-white/current-reference-refresh.json'
    refresh = read(refresh_path)
    fresh = {x['requested_id']: x['result'] for x in refresh['entries']}
    prior = {x['request_id']: x for x in meta['metadata']}
    file = fresh[card['primary_image_id']]['file']
    folder = fresh[card['primary_folder_id']]['folder']
    assert file['id'] == card['primary_image_id'] and folder['id'] == card['primary_folder_id']
    assert file['path_display'].rsplit('/', 1)[0] == folder['path_display']
    originals = read(HERE / 'download-receipts.json')
    verified = []
    for file_id in [card['primary_image_id'], card['pair_image_id']]:
        current = fresh[file_id]['file']
        assert all(current[key] == prior[file_id]['file'][key] for key in ['id', 'rev', 'size', 'path_display'])
        receipt = next(x for x in originals if x['id'] == file_id)
        local = Path(receipt['local_path'])
        assert local.stat().st_size == receipt['size'] == current['size']
        assert sha(local) == receipt['sha256'] and dbx_hash(local) == receipt['content_hash']
        verified.append({'file_id': file_id, 'rev': current['rev'], 'sha256': receipt['sha256'],
            'dropbox_content_hash': receipt['content_hash'], 'bytes': receipt['size'],
            'current_metadata_matches_previous_download': True})
    now = datetime.now(timezone.utc).isoformat()
    card.pop('draft_state')
    card.update({'prepared_utc': now, 'review_state': 'AWAITING OWNER NAME AND INDIVIDUAL POSITION IDENTITY',
        'prepared_draft': rel(draft_path), 'prepared_draft_sha256': sha(draft_path),
        'metadata_checked_utc': refresh['checked_utc'], 'reference_refresh': rel(refresh_path)})
    dimensions, material = card['specification_review_items'][0], card['specification_review_items'][2]
    dimensions['value']['related_LF1_single_listing_dimensions_cm'] = dimensions['value'].pop('single_listing_dimensions_cm')
    dimensions.update({'display': '35×35×6cm per panel in pair listing; historical LF2 side depth5–7cm; actual LF2 unmeasured',
        'status': 'PER-PANEL SOURCE STANDARD; ACTUAL LF2 UNMEASURED; RELATED LF1 SIZE CONFLICT SEPARATE',
        'source_refs': [rel(HERE / 'maker-source-reference.json'), rel(HERE / 'public-reader-source.json'),
            card['primary_image_id'], card['pair_image_id']]})
    material['value']['related_LF1_single_listing_material_claim'] = material['value'].pop('single_listing_material_claim')
    material['status'] = 'HISTORICAL LF2 MAKER STANDARD; ACTUAL CAST COMPOSITION UNCONFIRMED'
    card['source_conflicts'] = [
        'Related LF1 single listing says40×20×6cm despite square LF1photo. This does not establish a40×20LF2version or override the35×35LF2standard.',
        'LF2maker source specifies AC730white marble standard; related LF1gypsum wording is not confirmed LF2composition.',
        '350GBPfor LF2 is a proposal from related LF1offer; exact LF2standalone offer/price unconfirmed.600GBPpair price is not divided.',
        'Current usable mould inventory, exact physical cast identity and rear orientation compatibility unknown.']
    card['open_gaps'][1] = 'Measure actual LF2face/depth; retain related LF1single-listing version conflict separately'
    assert len(card['specification_review_items']) == 6
    assert all(not x['owner_approved'] and not x['physical_specs_verified'] for x in card['specification_review_items'])
    assert card['platform_mapping']['single_offer']['sku'] is None
    write(HERE / 'lf2-white/before-stage-review.json', {'recorded_utc': now,
        'files': {rel(paths[key]): value for key, value in before.items()}, 'protected_sha256': protected})
    write(output, card)
    parent = p['reviews']['BC-LEAF-FORM']
    target = parent['component_layouts'][card['component_layout_id']]
    assert not target['identity_confirmed'] and parent['component_layouts']['LEAF-FORM-LF1-WHITE']['identity_confirmed']
    target.pop('draft_state')
    target.update({'reviewed_utc': now, 'review_state': card['review_state'], 'review_record': rel(output),
        'specification_proposals': copy.deepcopy(card['specification_review_items']),
        'gaps': copy.deepcopy(card['open_gaps'])})
    assert len(parent['pending_component_layouts']) == 1
    assert parent['pending_component_layouts'][0]['component_layout_id'] == card['component_layout_id']
    parent['pending_component_layouts'] = []
    assert p['family_review_progress']['Leaf Form']['review_reference_cards_answered'] == 1
    state = 'Awaiting Leaf Form2White LF2/PositionB individual name; all six source/proposal groups pending'
    links = {x['file_name']: x for x in meta['previews']}
    cp.update({'current_component_layout_id': card['component_layout_id'],
        'current_size_finish_variant_id': card['size_finish_variant_id'],
        'proposed_name': card['proposed_name'], 'state': state, 'current_review_record': rel(output),
        'current_family_review_number': 2, 'current_family_review_total': 3,
        'current_answer_recorded': False, 'current_specification_answer_recorded': False,
        'current_dimension_answer_recorded': False, 'current_dimension_approval': None,
        'current_partial_specification_answer_recorded': False, 'current_owner_face_dimensions_cm': None,
        'current_identity_relationship_answer_recorded': False, 'current_identity_relationship_approval': None,
        'canonical_depicted_name': None, 'current_separate_saleable_design': None,
        'working_version_user_approved': False, 'question_scope': card['scope'],
        'answer_state': 'LF1name/position kept. LF2name and all six specifications remain unapproved; Gold reference follows.',
        'primary_image': {'file_id': file['id'], 'name': file['name'], 'path_display': file['path_display'],
            'copy_link_url': card['primary_image_link'], 'open_in_dropbox_url': links[file['id']]['open_in_dropbox_url']},
        'containing_folder': {'folder_id': folder['id'], 'name': folder['name'], 'path_display': folder['path_display'],
            'copy_link_url': card['primary_folder_link'], 'open_in_dropbox_url': links[folder['id']]['open_in_dropbox_url']},
        'metadata_checked_utc': refresh['checked_utc'], 'family_review_evidence': rel(refresh_path),
        'displayed_identity_evidence_file_ids': [file['id']], 'displayed_identity_evidence_folder_ids': [folder['id']],
        'current_component_source_notes': [x['display'] for x in card['specification_review_items']],
        'next_review_after_keep': card['next_review_after_keep'], 'updated_utc': now})
    c['interactive_review_state'].update({'current_component_layout_id': card['component_layout_id'],
        'current_size_finish_variant_id': card['size_finish_variant_id'], 'current_name': card['proposed_name'],
        'family_review_number': 2, 'state': state, 'specification_proposals_approved': False,
        'working_version_user_approved': False})
    c['current_component_review_record'] = rel(output)
    c['updated_utc'] = p['updated_utc'] = now
    docs['root']['current_component_review'] = copy.deepcopy(c)
    docs['root']['updated_utc'] = now
    for key in ['parallel_import_queue', 'parallel_owner_reviews', 'parallel_evidence_flags', 'pending_specification_reviews']:
        assert cp[key] == before['walkthrough'][key]
    assert parent['component_layouts']['LEAF-FORM-LF1-WHITE'] == before['progress']['reviews']['BC-LEAF-FORM']['component_layouts']['LEAF-FORM-LF1-WHITE']
    assert parent['pending_size_finish_variants'] == before['progress']['reviews']['BC-LEAF-FORM']['pending_size_finish_variants']
    assert not parent['identity_confirmed']
    assert all(p['reviews'][key] == value for key, value in before['progress']['reviews'].items() if key != 'BC-LEAF-FORM')
    assert all(sha(path) == hashes[key] for key, path in paths.items()), 'Shared writer collision'
    assert all(sha(Path(path)) == digest for path, digest in protected.items())
    for key, path in paths.items():
        write(path, docs[key])
        assert read(path) == docs[key]
    result = {'status': 'PASS', 'current_name': card['proposed_name'], 'component_layout_id': card['component_layout_id'],
        'verified_current_references': verified, 'all_six_groups_unapproved': True,
        'related_LF1_size_material_price_scope_explicit': True, 'LF2_exact_standalone_platform_match_unconfirmed': True,
        'whole_pair_price_and_mass_not_divided': True, 'LF1_approval_frozen_draft_model_workbook_unchanged': True,
        'imports_reservations_previous_approvals_preserved': True,
        'checkpoint_copies_match': read(paths['root'])['current_component_review'] == read(paths['component'])}
    write(HERE / 'lf2-white/review-validation.json', result)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
