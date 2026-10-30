"""Stage the individual Mediterranean panel with six explicitly conditional proposals."""
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
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(path)


def verify_original(receipt):
    path = Path(receipt['local_path'])
    data = path.read_bytes()
    assert len(data) == receipt['size'] and sha(path) == receipt['sha256']
    chunk_hash = hashlib.sha256(b''.join(hashlib.sha256(data[i:i+4194304]).digest() for i in range(0, len(data), 4194304))).hexdigest()
    assert chunk_hash == receipt['content_hash']
    return {'file_id': receipt['id'], 'local_path': str(path), 'sha256': sha(path),
            'bytes': len(data), 'dropbox_chunk_hash': chunk_hash, 'visually_inspected': True}


def main():
    card_path = HERE / 'component-review.json'
    assert not card_path.exists(), 'Already frozen'
    paths = {'walkthrough': REVIEWS / 'walkthrough_checkpoint.json', 'progress': REVIEWS / 'specification_review_progress.json',
        'component': ROOT / 'components/checkpoint.json', 'root': ROOT / 'checkpoint.json'}
    docs = {key: read(path) for key, path in paths.items()}
    before = copy.deepcopy(docs)
    hashes = {key: sha(path) for key, path in paths.items()}
    cp, progress, component = (docs[key] for key in ['walkthrough', 'progress', 'component'])
    assert cp['current_component_id'] == 'BC-FOUNTAIN-EG'
    assert cp['current_size_finish_variant_id'] == 'FOUNTAIN-EG-DARK-REFERENCE-RELATIONSHIP' and cp['current_answer_recorded']
    assert cp['next_review_after_keep']['component_id'] == 'BC-FOUNTAIN-MED'
    assert docs['root']['current_component_review'] == component
    assert 'BC-FOUNTAIN-MED' not in progress['reviews']
    relation_path = ROOT / cp['current_identity_relationship_approval']
    relation = read(relation_path)
    assert relation['relationship'] == 'SAME_DEPICTED_FINISH' and not relation['specifications_approved']
    model_path = ROOT / 'components/evidence/component_register.json'
    model = read(model_path)
    native = next(x for x in model['components'] if x['component_id'] == 'BC-FOUNTAIN-MED')
    assert native['group_refs'] == ['G164', 'G166'] and native['offer_refs'] == []
    meta_path = HERE / 'metadata-links.json'
    meta = read(meta_path)
    assert [len(x['entries']) for x in meta['listings']] == [7, 2]
    assert all(not x['has_more'] and not x['cursor'] for x in meta['listings'])
    selected = {x['file']['id'] if x.get('file') else x['folder']['id']: x for x in meta['metadata']}
    primary = selected['id:cnqzTNngPVsAAAAAAAylDA']['file']
    folder = selected['id:cnqzTNngPVsAAAAAAAyiig']['folder']
    links = {x['file_name']: x for x in meta['previews']}
    assert primary['path_display'].rsplit('/', 1)[0] == folder['path_display']
    previews = read(HERE / 'image-review-index.json')['cached_previews']
    assert len(previews) == 9 and all(sha(Path(x['preview_path'])) == x['sha256'] for x in previews)
    fresh = read(HERE / 'download-receipts.json')
    assert len(fresh) == 3
    originals = [verify_original(x) for x in fresh]
    white_dir = HERE.parent / 'fountain-palm-egyptian-review-2026-10-18'
    paired = next(x for x in read(white_dir / 'download-receipts.json') if x['id'] == 'id:cnqzTNngPVsAAAAAAAugew')
    previous_pair_meta = next(x['file'] for x in read(white_dir / 'metadata-links.json')['metadata']
                              if x.get('file', {}).get('id') == paired['id'])
    assert all(selected[paired['id']]['file'][key] == previous_pair_meta[key] for key in ['id', 'rev', 'size'])
    originals.append(verify_original(paired) | {'reused_cached_original_current_revision_unchanged': True})
    now = datetime.now(timezone.utc).isoformat()
    source_ref = rel(HERE / 'public-source-reference.json')
    white_card_path = white_dir / 'component-review.json'
    source_text_dir = ROOT / 'components/evidence/price-source-review-2026-10-17'
    text_hits = []
    for path in sorted(source_text_dir.glob('*.txt')):
        hits = [{'line': i+1, 'text': line} for i, line in enumerate(path.read_text().splitlines())
                if any(term in line.lower() for term in ['mediterranean', 'fountain'])]
        text_hits.append({'path': str(path), 'sha256': sha(path), 'hits': hits})
    write(HERE / 'document-platform-check.json', {'checked_utc': now,
        'baseline_component_offer_refs': native['offer_refs'],
        'baseline_component_claims': [x for x in model['claims'] if x.get('component_id') == 'BC-FOUNTAIN-MED'],
        'text_search': text_hits, 'trade_reed_fountain_image_review': rel(white_dir / 'trade-page11.png'),
        'trade_reed_fountain_image_sha256': sha(white_dir / 'trade-page11.png'),
        'trade_visual_observation': 'The pictured Reed Fountain has the dense Egyptian channels; it does not establish a Mediterranean specification.',
        'scope': 'No exact Mediterranean platform pair or specification row was established in these reviewed sources. This is not proof that no such record exists elsewhere.'})
    items = []

    def item(suffix, field, display, value, basis, sources):
        items.append({'proposal_id': 'FOUNTAIN-MED-WHITE-' + suffix, 'field': field, 'display': display,
            'value': value, 'status': 'UNAPPROVED WORKING GUESS; COMPONENT APPLICABILITY UNCONFIRMED',
            'basis': basis, 'source_refs': sources, 'owner_approved': False, 'physical_specs_verified': False})

    item('DIMENSIONS', 'Individual dimensions and depth', 'Approximately100 H ×50 W ×6 D cm — companion-size guess; unmeasured',
        {'proposed_dimensions_cm': [100, 50, 6], 'actual_measured_cm': None},
        'Portrait2:1appearance and paired display support a100×50companion hypothesis using Egyptian source scale. The two panels occupy different positions/distances; photographs are not calibrated and cannot establish actual size or maximum projection. No set dimension is divided.', [primary['id'], paired['id'], source_ref])
    item('WEIGHT', 'Individual dry weight', 'Approximately15kg — conditional guess assuming comparable construction to Egyptian White; unweighed',
        {'proposed_weight_kg': 15, 'actual_weighed_kg': None, 'same_construction_as_Egyptian_confirmed': False},
        'Use the related Egyptian Shopify15kg value as a planning analogy only, conditional on comparable dimensions, thickness, substrate and backing. Different relief/construction could change mass; no image-derived or calculated mass is claimed.', [rel(white_card_path)])
    item('MATERIAL', 'Material and finish', 'Cast mineral composite with white/cream stone-like finish — hypothesis; binder and recipe unknown',
        {'visible_finish': 'White/cream, fine speckled stone-like surface', 'proposed_substrate': 'Cast mineral composite',
         'actual_binder': None, 'reinforcement': None, 'sealer': None},
        'The image shows a pale fine-grained surface; that does not distinguish gypsum, cementitious or other mineral/resin binders. Nearby Egyptian AC730process evidence is not material proof for Mediterranean. Exterior/weather/water suitability and care remain unknown.', [primary['id'], 'id:cnqzTNngPVsAAAAAAAuY1g'])
    item('FIXING', 'Fixing', 'Concealed rear fixing(s) — proposal; type, count, attachment and rated load unknown',
        {'proposed_scheme': 'Concealed rear fixing(s)', 'hardware_type': None, 'count': None, 'rated_load': None},
        'The clean wall-front image shows no hardware, and native views show the panel leaning near workshop boards or grass. None of the9reviewed images exposes a finished rear; wall display alone does not establish the fixing specification.', [rel(meta_path)])
    item('PRICE', 'Individual retail price', '£900 per panel — discussion proposal using related Egyptian price; no exact Mediterranean offer',
        {'proposed_price_gbp': 900, 'owner_price_approved': False, 'exact_Mediterranean_offer_confirmed': False},
        'The freshly checked related Deco Fountain/Egyptian public offer is900GBP. Use900only as an explicit owner-review proposal for a similarly sized Mediterranean panel; design differences, production costs and desired price are unconfirmed. No set-price split or existing Mediterranean selling price is claimed.', [source_ref])
    item('AVAILABILITY', 'Availability', 'Made to order / enquire — policy proposal; stock, reproducibility and lead time unknown',
        {'proposed_policy': 'Made to order / enquire subject to production confirmation',
         'physical_stock': None, 'reproducibility': None, 'lead_time': None},
        'Past photographed panels do not prove current stocked casts, a usable mould, repeatable production or delivery date. Proposed sale policy needs owner confirmation.', [rel(meta_path)])
    coverage = {'complete_individual_front': True, 'native_outdoor_workshop_context': True,
        'paired_family_display_available': True, 'paired_display_reference_file_ids': ['id:cnqzTNngPVsAAAAAAAugew', 'id:cnqzTNngPVsAAAAAAAubmQ'],
        'paired_display_component_position': 'Mediterranean is the sparse-channel panel standing on grass at the right; Egyptian is mounted on brick.',
        'indoor_room_setting_established': False, 'individual_finished_rear': False, 'fixing_detail': False,
        'standalone_client_installation_provenance_confirmed': False, 'same_physical_cast_in_all_views_verified': False,
        'scope': 'Fresh complete7individual +2paired file census, all9previews inspected. Three fresh individual originals and one reused/hash-verified unchanged paired original viewed. The edited clean-front wall photograph is not verified client-installation evidence. No whole moulding-process folder assignment.'}
    mapping = {'status': 'EXACT INDIVIDUAL MEDITERRANEAN PLATFORM OFFER UNCONFIRMED',
        'squarespace_id': None, 'shopify_handle': None, 'shared_sku': None, 'individual_offer_confirmed': False,
        'related_Egyptian_offer_ref': 'O014', 'related_Egyptian_shared_sku': 'DF-1-100.50',
        'related_offer_transferred': False, 'live_Shopify_account_refreshed': False}
    next_review = copy.deepcopy(cp['after_main_family_next_unclaimed'])
    assert next_review == {'component_id': 'BC-LEAF-CURVE', 'review_number': 66}
    next_review['label'] = 'Leaf Curve — review its individual finish references'
    card = {'schema_version': 1, 'prepared_utc': now, 'component_id': 'BC-FOUNTAIN-MED', 'review_number': 54,
        'family': 'Fountain Palm', 'family_review_number': 4, 'family_review_total': 4,
        'family_total_scope': 'Four reference cards/questions across Egyptian White, Egyptian Bronze/Verdigris, a finish relationship and Mediterranean White; not four physical sculptures.',
        'size_finish_variant_id': 'FOUNTAIN-MED-WHITE', 'proposed_name': 'Fountain Palm Mediterranean — White',
        'display_name': 'Fountain Palm Mediterranean — White', 'review_decision_mode': 'INDIVIDUAL_COMPONENT_NAME_AND_SPECIFICATIONS',
        'scope': 'One sparse-channel rectangular component, reviewed separately from the dense-channel Egyptian design and from paired arrangements. Name approval and specification approval are separate.',
        'primary_image_id': primary['id'], 'primary_folder_id': folder['id'],
        'primary_image_link': links[primary['id']]['copy_link_url'], 'primary_folder_link': links[folder['id']]['copy_link_url'],
        'native_front_reference_id': 'id:cnqzTNngPVsAAAAAAAuUGg',
        'native_front_reference_link': links['id:cnqzTNngPVsAAAAAAAuUGg']['copy_link_url'],
        'paired_display_reference_id': paired['id'], 'paired_display_folder_id': 'id:cnqzTNngPVsAAAAAAAyiiQ',
        'paired_display_reference_link': links[paired['id']]['copy_link_url'],
        'paired_display_folder_link': links['id:cnqzTNngPVsAAAAAAAyiiQ']['copy_link_url'],
        'metadata_checked_utc': meta['selected_metadata_checked_utc'], 'reference_refresh': rel(meta_path),
        'originals_verified_and_viewed': originals, 'specification_review_items': items,
        'platform_mapping': mapping, 'photo_coverage': coverage,
        'source_review': rel(HERE / 'document-platform-check.json'), 'related_public_source': source_ref,
        'identity_confirmed': False, 'specifications_approved': False, 'physical_specs_verified': False,
        'open_gaps': ['Owner depicted name/identity', 'Actual face size, maximum projection and dry weight',
            'Actual binder, backing, reinforcement, sealing, care and weather suitability',
            'Finished rear/fixing hardware, attachment, count and load', 'Owner individual price, stock, reproducibility and lead time',
            'Exact Squarespace/Shopify counterpart and shared SKU', 'Indoor setting and verified client installation photograph/provenance',
            'Exact physical manufacture/mould identity and process allocation'],
        'next_review_after_keep': next_review, 'remote_files_changed': False, 'live_platform_records_changed': False}
    write(card_path, card)
    evidence = [model_path, white_card_path, relation_path, HERE / 'metadata-links.json',
        HERE / 'download-receipts.json', HERE / 'image-review-index.json', HERE / 'public-source-reference.json',
        HERE / 'document-platform-check.json', white_dir / 'trade-page11.png']
    evidence += [Path(x['local_path']) for x in originals] + [Path(x['preview_path']) for x in previews]
    write(HERE / 'source-audit.json', {'status': 'PASS', 'checked_utc': now,
        'fresh_census_files': 9, 'previews_inspected': 9, 'fresh_originals_viewed': 3, 'reused_unchanged_originals_viewed': 1,
        'exact_component_source_specification_found': False, 'evidence_sha256': {str(path): sha(path) for path in sorted(set(evidence))}})
    protected = {str(path): sha(path) for path in [REVIEWS / 'user_classifications.json', model_path,
        ROOT / cp['register_workbook'], relation_path, card_path, white_card_path, white_dir / 'identity-approval.json',
        white_dir / 'bronze-verdigris/identity-approval.json']}
    write(HERE / 'before-stage-review.json', {'recorded_utc': now,
        'files': {rel(paths[key]): value for key, value in before.items()}, 'protected_sha256': protected})
    progress['reviews']['BC-FOUNTAIN-MED'] = {'reviewed_utc': now, 'review_number': 54,
        'proposed_name': card['proposed_name'], 'size_finish_variant_id': card['size_finish_variant_id'],
        'identity_confirmed': False, 'specifications_approved': False, 'physical_specs_verified': False,
        'specification_proposals': copy.deepcopy(items), 'primary_image_id': primary['id'], 'primary_folder_id': folder['id'],
        'review_record': rel(card_path), 'platform_mapping': mapping, 'photo_coverage': coverage, 'gaps': card['open_gaps']}
    progress['family_review_progress']['Fountain Palm'].update({'updated_utc': now, 'current_component_id': 'BC-FOUNTAIN-MED',
        'review_reference_cards_answered': 3, 'review_reference_total': 4, 'reference_total_is_sculpture_count': False})
    progress['updated_utc'] = now
    state = 'Awaiting Fountain Palm Mediterranean White individual name; six guesses pending'
    cp.update({'current_component_id': 'BC-FOUNTAIN-MED', 'current_review_number': 54,
        'current_size_finish_variant_id': card['size_finish_variant_id'], 'proposed_name': card['proposed_name'],
        'state': state, 'current_review_record': rel(card_path), 'current_family_review_number': 4,
        'current_family_review_total': 4, 'active_family': 'Fountain Palm', 'family_first_pass_complete': False,
        'current_answer_recorded': False, 'current_identity_relationship_answer_recorded': False,
        'current_identity_relationship_approval': None, 'canonical_depicted_name': None, 'current_separate_saleable_design': None,
        'current_specification_answer_recorded': False, 'current_dimension_answer_recorded': False,
        'current_partial_specification_answer_recorded': False, 'current_dimension_approval': None,
        'current_owner_face_dimensions_cm': None, 'working_version_user_approved': False,
        'review_decision_mode': card['review_decision_mode'], 'question_scope': card['scope'],
        'answer_state': 'No Mediterranean name or specification approval yet. Egyptian blue/darker two-reference finish grouping is recorded separately.',
        'primary_image': {'file_id': primary['id'], 'name': primary['name'], 'path_display': primary['path_display'],
            'copy_link_url': card['primary_image_link'], 'open_in_dropbox_url': links[primary['id']]['open_in_dropbox_url']},
        'containing_folder': {'folder_id': folder['id'], 'name': folder['name'], 'path_display': folder['path_display'],
            'copy_link_url': card['primary_folder_link'], 'open_in_dropbox_url': links[folder['id']]['open_in_dropbox_url']},
        'family_review_evidence': rel(meta_path), 'metadata_checked_utc': meta['selected_metadata_checked_utc'],
        'next_review_after_keep': next_review, 'displayed_identity_evidence_file_ids': [primary['id']],
        'displayed_identity_evidence_folder_ids': [folder['id']],
        'current_component_source_notes': [x['display'] for x in items],
        'family_counting_note': card['family_total_scope'], 'updated_utc': now})
    component['interactive_review_state'].update({'current_component_id': 'BC-FOUNTAIN-MED', 'review_number': 54,
        'current_size_finish_variant_id': card['size_finish_variant_id'], 'current_name': card['proposed_name'],
        'state': state, 'active_family': 'Fountain Palm', 'family_review_number': 4, 'family_review_total': 4,
        'current_identity_relationship_answer_recorded': False, 'canonical_depicted_name': None,
        'current_separate_saleable_design': None, 'current_dimension_answer_recorded': False,
        'current_owner_face_dimensions_cm': None, 'specification_proposals_approved': False,
        'working_version_user_approved': False, 'review_decision_mode': card['review_decision_mode']})
    component['current_component_review_record'] = rel(card_path)
    component['last_family_media_review'] = {'family': 'Fountain Palm', 'design': 'Mediterranean White',
        'observed_utc': meta['selected_metadata_checked_utc'], 'files': 9, 'folders': 2,
        'scope': coverage['scope'], 'evidence': rel(meta_path), 'workbook_contains_this_live_media_audit': False}
    component['updated_utc'] = now
    docs['root']['current_component_review'] = copy.deepcopy(component)
    docs['root']['updated_utc'] = now
    assert all(progress['reviews'][key] == value for key, value in before['progress']['reviews'].items())
    for key in ['parallel_import_queue', 'parallel_owner_reviews', 'parallel_evidence_flags', 'pending_specification_reviews']:
        assert cp[key] == before['walkthrough'][key]
    assert all(sha(path) == hashes[key] for key, path in paths.items()), 'Shared writer collision'
    assert all(sha(Path(path)) == digest for path, digest in protected.items())
    for key, path in paths.items():
        write(path, docs[key])
        assert read(path) == docs[key]
    result = {'status': 'PASS', 'current_component': 'BC-FOUNTAIN-MED', 'six_unapproved_guesses': 6,
        'fresh_complete_file_census': 9, 'originals_verified_and_viewed': 4,
        'Egyptian_identity_and_finish_decisions_preserved': True, 'exact_Mediterranean_offer_unconfirmed': True,
        'ledger_model_workbook_prior_reviews_unchanged': True, 'checkpoint_copies_match': read(paths['root'])['current_component_review'] == read(paths['component'])}
    write(HERE / 'review-validation.json', result)
    print(json.dumps(result))
    print(json.dumps({'image': card['primary_image_link'], 'folder': card['primary_folder_link'], 'paired': card['paired_display_reference_link']}))


if __name__ == '__main__':
    main()
