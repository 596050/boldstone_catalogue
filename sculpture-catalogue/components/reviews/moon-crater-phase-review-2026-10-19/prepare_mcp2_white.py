"""Stage one MCP2 White panel using its labelled individual maker record."""
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


def write(p, j):
    p.parent.mkdir(parents=True, exist_ok=True)
    t = p.with_name(p.name + '.tmp')
    t.write_text(json.dumps(j, ensure_ascii=False, indent=2) + '\n')
    t.replace(p)


def main():
    output = HERE / 'mcp2-white/component-review.json'
    assert not output.exists()
    paths = {'progress': REVIEWS / 'specification_review_progress.json',
        'walkthrough': REVIEWS / 'walkthrough_checkpoint.json',
        'component': ROOT / 'components/checkpoint.json', 'root': ROOT / 'checkpoint.json'}
    docs = {k: read(p) for k, p in paths.items()}; before = copy.deepcopy(docs)
    hashes = {k: sha(p) for k, p in paths.items()}
    p, cp, c = (docs[k] for k in ['progress', 'walkthrough', 'component'])
    assert cp['current_component_id'] == 'BC-MCP-1' and cp['current_answer_recorded']
    assert cp['next_review_after_keep'] == {'component_id': 'BC-MCP-2', 'review_number': 72}
    assert read(ROOT / cp['last_identity_approval'])['user_statement'] == 'Keep “Moon Crater Phase 1 — Verdigris and Rust (MCP1)”'
    assert docs['root']['current_component_review'] == c and 'BC-MCP-2' not in p['reviews']
    assert not any(x['component_id'] == 'BC-MCP-2' for x in cp['parallel_owner_reviews'])
    protected_paths = [REVIEWS / 'user_classifications.json', ROOT / 'components/evidence/component_register.json',
        ROOT / cp['register_workbook'], ROOT / cp['current_review_record'], ROOT / cp['last_identity_approval'],
        ROOT / cp['last_completed_family_first_pass']]
    protected = {str(x): sha(x) for x in protected_paths}
    model = read(ROOT / 'components/evidence/component_register.json')
    offer = next(x for x in model['platform_records'] if x['offer_ref'] == 'O008')
    assert offer['sq_id'] == '6a4173a2870e0e6bc1e10bf2' and offer['sku'] == 'SQ5572436' and not offer['sh_handle']
    maker = read(HERE / 'maker-source-reference.json')
    assert sha(Path(maker['source_local_path'])) == maker['source_sha256']
    row = next(x for x in maker['extracted_rows'] if x['row'] == 42)
    assert row['values']['Product Code A'] == 'MCP2-25x25'
    labelled = next(x for x in maker['labelled_reference_images'] if x['code'] == 'MCP2-25x25')
    assert labelled['picture']['index'] == 16
    assert all(sha(Path(path)) == digest for path, digest in maker['labelled_image_sha256'].items())
    listings = read(HERE / 'mcp2-initial-census.json')
    assert all(not x['result']['has_more'] and not x['result']['cursor'] for x in listings['listings'])
    white = next(x for x in listings['listings'] if x['path'].endswith('/Moon Crater Phase 2 White'))
    assert len(white['result']['entries']) == 5
    previews = read(HERE / 'mcp2-white/preview-cache.json')
    assert len(previews) == 5 and all(sha(Path(x['preview'])) == x['sha256'] for x in previews)
    originals = read(HERE / 'mcp2-white/original-download-receipts.json')['entries']
    assert len(originals) == 2
    for x in originals:
        raw = Path(x['local_path']).read_bytes()
        assert len(raw) == x['size'] and hashlib.sha256(raw).hexdigest() == x['sha256']
        assert hashlib.sha256(b''.join(hashlib.sha256(raw[i:i+4194304]).digest() for i in range(0, len(raw), 4194304))).hexdigest() == x['content_hash']
    metadata = read(HERE / 'mcp2-white/selected-metadata.json')
    links = {x['file_name']: x for x in read(HERE / 'mcp2-white/metadata-links.json')['results']}
    primary_id, closeup_id, folder_id = 'id:cnqzTNngPVsAAAAAAAylPg', 'id:cnqzTNngPVsAAAAAAAucyQ', 'id:cnqzTNngPVsAAAAAAAyipg'
    primary = next(x['file'] for x in metadata['entries'] if x['requested_id'] == primary_id)
    folder = next(x['result']['folder'] for x in read(HERE / 'mcp1-verdigris-rust/keep-current-reference.json')['metadata'] if x['requested_id'] == folder_id)
    assert primary['path_display'].rsplit('/', 1)[0] == folder['path_display']
    prior_card = read(HERE / 'mcp1-white/component-review.json')
    items = copy.deepcopy(prior_card['specification_review_items'])
    for x in items:
        x['proposal_id'] = x['proposal_id'].replace('MCP1-WHITE-', 'MCP2-WHITE-')
        x['basis'] = x['basis'].replace('row41', 'row42').replace('Row41', 'Row42').replace('MCP1', 'MCP2')
        assert not x['owner_approved'] and not x['physical_specs_verified']
    items[0]['basis'] = 'Maker row42explicitly gives one MCP2cast250×250mm with40–60mm side depth. Numbered owner Trade2025row2and White Retail2025also state25×25cm each. No quartet dimensions are divided; no coloured listing claim is transferred to White.'
    items[3]['basis'] = 'Maker row42specifies one small stainless fixing centred in the upper third, aligned from the top across the series. All five MCP2White references show fronts/details; its actual rear hardware and load remain unseen. The unpaired rear candidate previously reviewed for MCP1Verdigris/Rust is not transferred to MCP2White.'
    items[3]['source_refs'] = [rel(HERE / 'maker-source-reference.json')]
    items[4]['basis'] = '150GBPis a discussion proposal rounded from owner Retail2025individual White156.25GBP. Trade78GBPand the draft130.84/78/62stack retain their distinct dated source scope. No set price is divided and no coloured-offer price is adopted as the White price.'
    now = datetime.now(timezone.utc).isoformat()
    order = [{'component_id': 'BC-MCP-2', 'review_number': 72, 'variant_id': 'MCP2-WHITE', 'label': 'Moon Crater Phase 2 — White (MCP2)'},
        {'component_id': 'BC-MCP-2', 'review_number': 72, 'variant_id': 'MCP2-BLUE-SPLASHES', 'variant_only_review': True, 'label': 'Moon Crater Phase 2 — Blue Splashes (MCP2)'},
        {'component_id': 'BC-MCP-2', 'review_number': 72, 'variant_id': 'MCP2-VERDIGRIS-RUST', 'variant_only_review': True, 'label': 'Moon Crater Phase 2 — Verdigris and Rust (MCP2)'}]
    pending = {'scope': 'Rust references appear in quartet and2+3/2+4arrangements; exact member and finish attribution needs a separate per-image review.',
        'group_refs': ['G205', 'G222', 'G223'], 'folder_ids': ['id:cnqzTNngPVsAAAAAAAyiqA', 'id:cnqzTNngPVsAAAAAAAyiqQ', 'id:cnqzTNngPVsAAAAAAAyiqg'],
        'target_position': None, 'isolated_Rust_offer_confirmed': False, 'owner_identity_approved': False}
    mapping = {'platform_record_level': {'squarespace_id': None, 'shopify_handle': None, 'shared_sku': None,
        'status': 'EXACT WHITE OFFER AND PLATFORM PAIR UNCONFIRMED'},
        'related_coloured_offer_only': {'offer_ref': 'O008', 'squarespace_id': offer['sq_id'], 'sku': offer['sku'],
            'shopify_handle': None, 'title': offer['title'], 'linked_file_id_in_frozen_export': offer['image_file_id'],
            'linked_folder_id_in_frozen_export': offer['image_folder_id'],
            'status': 'SUPPLIED COLOURED OFFER EVIDENCE; NOT WHITE; LIVE ACCOUNT AND EXACT CURRENT IMAGE TO RECHECK WITH COLOURED FINISH'},
        'dropbox_component_level': {'clean_reference_file_id': primary_id, 'folder_id': folder_id,
            'native_closeup_file_id': closeup_id, 'series_file_id': prior_card['series_image_id'],
            'series_folder_id': prior_card['series_folder_id'], 'series_position': 'Top right in exact027photograph',
            'maker_code': 'MCP2-25x25', 'status': 'LABELLED MAKER/TRade2 AND EXACT SERIES GEOMETRY COMPARISON; OWNER IDENTITY PENDING',
            'render_edit_lineage_verified': False, 'same_physical_cast_between_images_verified': False},
        'individual_component_level': {'component_id': 'BC-MCP-2', 'quantity': 1,
            'separate_from_other_three_quartet_designs': True, 'whole_set_dimensions_weight_price_transferred': False}}
    coverage = {'complete_individual_clean_reference': True, 'native_solo_closeups': True,
        'uncropped_original_individual_front': False, 'original_series_reference': True,
        'indoor_exhibition_reference': True, 'verified_client_home_or_garden_installation': False,
        'White_finished_rear': False, 'White_fixing_detail': False, 'clean_reference_edit_lineage_verified': False,
        'scope': 'All5MCP2White previews inspected; clean004and native001 originals downloaded/hash-verified/viewed.001/002/003/005are close-ups. Reused original027and exhibition025show MCP2top-right; position not applied to every other rendition.'}
    card = {'schema_version': 1, 'prepared_utc': now, 'component_id': 'BC-MCP-2', 'review_number': 72,
        'family': 'Moon Crater Phase', 'review_family_scope': 'Moon Crater Phase 2',
        'family_review_number': 1, 'family_review_total': 3,
        'family_total_scope': 'Three known individual MCP2finish folders:White, Blue Splashes, Verdigris/Rust. Rust arrangements remain separately pending; these are reference-card counts, not physical sculptures or moulds.',
        'size_finish_variant_id': 'MCP2-WHITE', 'proposed_name': order[0]['label'],
        'review_decision_mode': 'COMPONENT_NAME_AND_DEPICTED_IDENTITY_ONLY', 'identity_decision_destination': 'decisions',
        'scope': 'One White MCP2panel, separately saleable from the other three quartet designs. Name approval is separate from six historical/conditional specification groups.',
        'primary_image_id': primary_id, 'primary_folder_id': folder_id,
        'primary_image_link': links[primary_id]['copy_link_url'], 'primary_folder_link': links[folder_id]['copy_link_url'],
        'primary_image_scope': 'Complete clean reference; source editing/production history unverified',
        'original_closeup_id': closeup_id, 'original_closeup_link': links[closeup_id]['copy_link_url'],
        'series_image_id': prior_card['series_image_id'], 'series_folder_id': prior_card['series_folder_id'],
        'series_image_link': prior_card['series_image_link'], 'series_folder_link': prior_card['series_folder_link'],
        'series_target_position': 'Top right in exact027photograph',
        'exhibition_image_id': prior_card['exhibition_image_id'], 'exhibition_image_link': prior_card['exhibition_image_link'],
        'exhibition_target_position': 'Top right in exact025photograph; venue not independently authenticated',
        'metadata_checked_utc': metadata['checked_utc'], 'reference_refresh': rel(HERE / 'mcp2-white/selected-metadata.json'),
        'specification_review_items': items, 'platform_mapping': mapping, 'photo_coverage': coverage,
        'pending_arrangement_component_review': pending, 'identity_confirmed': False,
        'specifications_approved': False, 'physical_specs_verified': False,
        'individual_sale_unit': {'quantity': 1, 'description': 'One MCP2White component panel', 'live_listing_prepared_or_published': False},
        'open_gaps': ['Owner White MCP2name and depicted identity', 'Actual measured dimensions/depth and weighed mass;2–4/4/5kgsource differences',
            'Cast-specific binder, reinforcement, sealer and care', 'White rear hardware/attachment/load',
            'Current individual price, stock, mould condition and lead time', 'Exact White Squarespace/Shopify offer and shared SKU',
            'Uncropped native standalone front, authenticated installation and clean-image lineage', 'Rust arrangement member positions and exact finish applicability'],
        'next_review_after_keep': order[1], 'next_global_component': {'component_id': 'BC-MCP-3', 'review_number': 73},
        'remote_files_changed': False, 'live_platform_records_changed': False}
    audit = {'schema_version': 1, 'prepared_utc': now, 'maker_source': rel(HERE / 'maker-source-reference.json'),
        'maker_code': 'MCP2-25x25', 'maker_row': row, 'labelled_reference': labelled,
        'dated_price_source': rel(HERE / 'dated-price-source-scope.json'),
        'White_current_census': rel(HERE / 'mcp2-initial-census.json'), 'current_White_files': 5,
        'all_White_previews_viewed': True, 'White_originals_viewed': [primary_id, closeup_id],
        'White_original_hash_receipts': rel(HERE / 'mcp2-white/original-download-receipts.json'),
        'reused_series_originals': [{'file_id': card['series_image_id'], 'target': 'Top right'},
            {'file_id': card['exhibition_image_id'], 'target': 'Top right'}],
        'source_and_clean_geometry': 'Central convex boss with a circular collar whose broad outer portion extends toward the lower right; labelled maker016and numbered trade2support MCP2. No same-cast or edit-lineage identity inferred.',
        'whole_family_completed': False, 'remaining_finishes_not_approved': order[1:],
        'Rust_arrangement_attribution': pending, 'source_cards_and_workbook_unchanged': True}
    write(HERE / 'mcp2-white/before-staging.json', {'recorded_utc': now,
        'files': {rel(paths[k]): value for k, value in before.items()}, 'protected_sha256': protected})
    write(output, card); write(HERE / 'mcp2-white/source-audit.json', audit)
    p['reviews']['BC-MCP-2'] = {'reviewed_utc': now, 'review_number': 72, 'proposed_name': card['proposed_name'],
        'size_finish_variant_id': 'MCP2-WHITE', 'identity_confirmed': False, 'specifications_approved': False,
        'physical_specs_verified': False, 'source_specifications_recorded': True, 'specification_proposals': copy.deepcopy(items),
        'primary_image_id': primary_id, 'primary_folder_id': folder_id, 'review_record': rel(output),
        'platform_mapping': mapping, 'photo_coverage': coverage, 'gaps': card['open_gaps'],
        'pending_size_finish_variants': order[1:], 'pending_arrangement_component_review': pending, 'review_family_scope': card['review_family_scope']}
    p['family_review_progress']['Moon Crater Phase 2'] = {'family': 'Moon Crater Phase',
        'review_scope': card['family_total_scope'], 'status': 'FIRST_PASS_IN_PROGRESS', 'updated_utc': now,
        'review_reference_cards_answered': 0, 'review_reference_total': 3,
        'reference_total_is_sculpture_count': False, 'specifications_complete': False}
    state = 'Awaiting MCP2White name; all six specification groups pending; weight-source differences retained'
    cp.update({'current_component_id': 'BC-MCP-2', 'current_review_number': 72, 'current_size_finish_variant_id': 'MCP2-WHITE',
        'current_component_layout_id': None, 'proposed_name': card['proposed_name'], 'state': state,
        'current_review_record': rel(output), 'current_family_review_number': 1, 'current_family_review_total': 3,
        'active_family': 'Moon Crater Phase 2', 'family_review_order': order, 'family_first_pass_complete': False,
        'current_answer_recorded': False, 'current_specification_answer_recorded': False, 'current_dimension_answer_recorded': False,
        'current_partial_specification_answer_recorded': False, 'current_dimension_approval': None, 'current_owner_face_dimensions_cm': None,
        'current_identity_relationship_answer_recorded': False, 'current_identity_relationship_approval': None,
        'canonical_depicted_name': None, 'current_separate_saleable_design': None, 'working_version_user_approved': False,
        'review_decision_mode': card['review_decision_mode'], 'question_scope': card['scope'],
        'answer_state': 'MCP1known individual names saved; MCP2White identity and specifications pending.',
        'primary_image': {'file_id': primary_id, 'name': primary['name'], 'path_display': primary['path_display'],
            'copy_link_url': card['primary_image_link'], 'open_in_dropbox_url': links[primary_id]['open_in_dropbox_url']},
        'containing_folder': {'folder_id': folder_id, 'name': folder['name'], 'path_display': folder['path_display'],
            'copy_link_url': card['primary_folder_link'], 'open_in_dropbox_url': links[folder_id]['open_in_dropbox_url']},
        'metadata_checked_utc': metadata['checked_utc'], 'family_review_evidence': rel(HERE / 'mcp2-white/source-audit.json'),
        'displayed_identity_evidence_file_ids': [primary_id], 'displayed_identity_evidence_folder_ids': [folder_id],
        'current_component_source_notes': [x['display'] for x in items], 'family_counting_note': card['family_total_scope'],
        'next_review_after_keep': card['next_review_after_keep'], 'updated_utc': now})
    c['interactive_review_state'].update({'current_component_id': 'BC-MCP-2', 'review_number': 72,
        'current_size_finish_variant_id': 'MCP2-WHITE', 'current_component_layout_id': None,
        'current_name': card['proposed_name'], 'state': state, 'active_family': 'Moon Crater Phase 2',
        'family_review_number': 1, 'family_review_total': 3, 'specification_proposals_approved': False,
        'working_version_user_approved': False, 'review_decision_mode': card['review_decision_mode']})
    c['current_component_review_record'] = rel(output)
    c['last_family_media_review'] = {'family': 'Moon Crater Phase', 'review_scope': 'MCP2White only plus reused exact series images',
        'observed_utc': listings['checked_utc'], 'files': 5, 'folders': 1, 'full_new_originals': 2,
        'evidence': rel(HERE / 'mcp2-white/source-audit.json'), 'workbook_contains_this_live_media_audit': False}
    c['updated_utc'] = p['updated_utc'] = now
    docs['root']['current_component_review'] = copy.deepcopy(c); docs['root']['updated_utc'] = now
    assert all(p['reviews'][k] == value for k, value in before['progress']['reviews'].items())
    for k in ['parallel_import_queue', 'parallel_owner_reviews', 'parallel_evidence_flags', 'pending_specification_reviews',
              'next_serialized_parallel_import', 'last_parallel_import']:
        assert cp[k] == before['walkthrough'][k], k
    assert all(p['family_review_progress'][k] == value for k, value in before['progress']['family_review_progress'].items())
    assert all(sha(path) == hashes[k] for k, path in paths.items())
    assert all(sha(Path(path)) == digest for path, digest in protected.items())
    for k, path in paths.items():
        write(path, docs[k]); assert read(path) == docs[k]
    result = {'status': 'PASS', 'current_name': card['proposed_name'], 'all_six_groups_unapproved': True,
        'source_maker_row': 42, 'MCP2_is_one_individual_sale_unit': True,
        'exact027and025series_position': 'Top right', 'native_solo_closeup_and_clean_reference_limits_retained': True,
        'White_exact_platform_offer_unconfirmed': True, 'source_weight_versions_preserved': True,
        'other_finishes_and_Rust_arrangements_pending': True,
        'prior_approvals_parallel_queues_model_workbook_and_MCP1first_pass_preserved': True,
        'checkpoint_copies_match': read(paths['root'])['current_component_review'] == read(paths['component'])}
    write(HERE / 'mcp2-white/review-validation.json', result)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
