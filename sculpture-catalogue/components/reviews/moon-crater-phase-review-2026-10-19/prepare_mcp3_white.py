"""Stage the individual MCP3 White reference without approving specifications."""
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
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temp.replace(path)


def main():
    output = HERE / 'mcp3-white/component-review.json'
    assert not output.exists()
    paths = {'progress': REVIEWS / 'specification_review_progress.json',
        'walkthrough': REVIEWS / 'walkthrough_checkpoint.json',
        'component': ROOT / 'components/checkpoint.json', 'root': ROOT / 'checkpoint.json'}
    docs = {k: read(path) for k, path in paths.items()}
    before = copy.deepcopy(docs)
    hashes = {k: sha(path) for k, path in paths.items()}
    p, cp, c = (docs[k] for k in ['progress', 'walkthrough', 'component'])
    assert cp['current_component_id'] == 'BC-MCP-2' and cp['current_size_finish_variant_id'] == 'MCP2-VERDIGRIS-RUST'
    assert cp['current_answer_recorded'] and cp['next_review_after_keep'] == {'component_id': 'BC-MCP-3', 'review_number': 73}
    assert 'BC-MCP-3' not in p['reviews'] and docs['root']['current_component_review'] == c
    assert not any(x['component_id'] == 'BC-MCP-3' for x in cp['parallel_owner_reviews'])
    protected = {str(path): sha(path) for path in [REVIEWS / 'user_classifications.json',
        ROOT / 'components/evidence/component_register.json', ROOT / cp['register_workbook'],
        ROOT / cp['current_review_record'], ROOT / cp['last_identity_approval'], ROOT / cp['last_completed_family_first_pass']]}
    model = read(ROOT / 'components/evidence/component_register.json')
    offer = next(x for x in model['platform_records'] if x['offer_ref'] == 'O005')
    assert offer['sq_id'] == '6a41390021dbe14148c0b933' and offer['sku'] == 'SQ6211184' and not offer['sh_handle']
    maker = read(HERE / 'maker-source-reference.json')
    assert sha(Path(maker['source_local_path'])) == maker['source_sha256']
    row = next(x for x in maker['extracted_rows'] if x['row'] == 43)
    assert row['values']['Product Code A'] == 'MCP3-25x25'
    labelled = next(x for x in maker['labelled_reference_images'] if x['code'] == 'MCP3-25x25')
    assert labelled['picture']['index'] == 17
    assert all(sha(Path(path)) == digest for path, digest in maker['labelled_image_sha256'].items())
    census = read(HERE / 'mcp3-initial-census.json')
    assert all(not x['result']['has_more'] and not x['result']['cursor'] for x in census['listings'])
    white = next(x for x in census['listings'] if x['path'].endswith(' White'))
    assert len(white['result']['entries']) == 9
    previews = read(HERE / 'mcp3-white/preview-cache.json')
    assert len(previews) == 9 and all(sha(Path(x['preview'])) == x['sha256'] for x in previews)
    originals = read(HERE / 'mcp3-white/original-download-receipts.json')['entries']
    assert len(originals) == 2
    for entry in originals:
        raw = Path(entry['local_path']).read_bytes()
        assert len(raw) == entry['size'] and hashlib.sha256(raw).hexdigest() == entry['sha256']
        assert hashlib.sha256(b''.join(hashlib.sha256(raw[i:i+4194304]).digest() for i in range(0, len(raw), 4194304))).hexdigest() == entry['content_hash']
    metadata_doc = read(HERE / 'mcp3-white/selected-metadata.json')
    metadata = {x['requested_id']: x for x in metadata_doc['entries']}
    folders = {x['requested_id']: x['result']['folder'] for x in read(HERE / 'mcp3-white/folder-metadata.json')['entries']}
    links = {x['file_name']: x for x in read(HERE / 'mcp3-white/metadata-links.json')['results']}
    primary_id, closeup_id, folder_id = 'id:cnqzTNngPVsAAAAAAAylPw', 'id:cnqzTNngPVsAAAAAAAuTCg', 'id:cnqzTNngPVsAAAAAAAyipQ'
    primary, folder = metadata[primary_id]['file'], folders[folder_id]
    assert primary['path_display'].rsplit('/', 1)[0] == folder['path_display']
    previous_metadata = {x['requested_id']: x['file'] for x in read(HERE / 'selected-metadata.json')['entries']}
    series_receipts = {x['id']: x for x in read(HERE / 'download-receipts.json')}
    for fid in ['id:cnqzTNngPVsAAAAAAAugDQ', 'id:cnqzTNngPVsAAAAAAA512A']:
        current, old = metadata[fid]['file'], previous_metadata[fid]
        assert all(current[k] == old[k] for k in ['id', 'rev', 'size', 'path_display'])
        assert sha(Path(series_receipts[fid]['local_path'])) == series_receipts[fid]['sha256']
    previous = read(HERE / 'mcp2-white/component-review.json')
    card = json.loads(json.dumps(previous).replace('MCP2', 'MCP3').replace('mcp2', 'mcp3').replace('Phase 2', 'Phase 3').replace('row42', 'row43').replace('Row42', 'Row43'))
    items = card['specification_review_items']
    items[0]['basis'] = 'Maker row43 gives one MCP3 cast250×250mm with40–60mm side depth; numbered Trade2025 row3 also gives25×25cm. No set value or coloured listing depth is transferred.'
    items[3]['basis'] = 'Historical White maker row43 specifies one small stainless rear fixing, centred in the upper third and aligned from the top across the series. All9 current White files show fronts/details; actual White rear hardware, attachment and load remain unverified.'
    items[4]['basis'] = '150GBP is a discussion proposal rounded from the dated owner Retail2025 individual White156.25GBP. Trade78GBP and the draft130.84/78/62 values retain separate source scopes; no quartet price is divided and the coloured offer price is not applied to White.'
    assert len(items) == 6 and all(not x['owner_approved'] and not x['physical_specs_verified'] for x in items)
    now = datetime.now(timezone.utc).isoformat()
    order = [{'component_id': 'BC-MCP-3', 'review_number': 73, 'variant_id': 'MCP3-WHITE', 'label': 'Moon Crater Phase 3 — White (MCP3)'},
        {'component_id': 'BC-MCP-3', 'review_number': 73, 'variant_id': 'MCP3-VERDIGRIS-RUST', 'variant_only_review': True, 'label': 'Moon Crater Phase 3 — Verdigris and Rust (MCP3)'}]
    pending = {'scope': 'Rust quartet and2+3 arrangements require exact per-image MCP3 member/finish attribution.',
        'group_refs': ['G205', 'G222'], 'folder_ids': ['id:cnqzTNngPVsAAAAAAAyiqA', 'id:cnqzTNngPVsAAAAAAAyiqQ'],
        'target_position': None, 'isolated_Rust_offer_confirmed': False, 'owner_identity_approved': False}
    mapping = {'platform_record_level': {'squarespace_id': None, 'shopify_handle': None, 'shared_sku': None, 'status': 'EXACT WHITE OFFER AND PLATFORM PAIR UNCONFIRMED'},
        'related_coloured_offer_only': {'offer_ref': 'O005', 'squarespace_id': offer['sq_id'], 'sku': offer['sku'], 'shopify_handle': None,
            'title': offer['title'], 'linked_file_id_in_frozen_export': offer['image_file_id'], 'linked_folder_id_in_frozen_export': offer['image_folder_id'],
            'status': 'FROZEN SUPPLIED COLOURED OFFER EVIDENCE ONLY; NOT WHITE; CURRENT PUBLIC IMAGE AND PRICE TO RECHECK WITH COLOURED FINISH'},
        'dropbox_component_level': {'clean_reference_file_id': primary_id, 'folder_id': folder_id, 'native_closeup_file_id': closeup_id,
            'series_file_id': previous['series_image_id'], 'series_folder_id': previous['series_folder_id'],
            'series_position': 'Bottom left in exact027 photograph', 'maker_code': 'MCP3-25x25',
            'status': 'LABELLED MAKER017 AND NUMBERED TRADE3 PLUS EXACT SERIES GEOMETRY; OWNER IDENTITY PENDING',
            'render_edit_lineage_verified': False, 'same_physical_cast_between_images_verified': False},
        'individual_component_level': {'component_id': 'BC-MCP-3', 'quantity': 1, 'separate_from_other_three_quartet_designs': True, 'whole_set_dimensions_weight_price_transferred': False}}
    coverage = {'complete_individual_clean_reference': True, 'native_solo_closeups': True, 'uncropped_original_individual_front': False,
        'original_series_reference': True, 'indoor_exhibition_reference': True, 'verified_client_home_or_garden_installation': False,
        'White_finished_rear': False, 'White_fixing_detail': False, 'clean_reference_edit_lineage_verified': False,
        'scope': 'All9 current White previews viewed; clean008 and native001 full files hash-verified/viewed.001–007/009 are close-ups. Exact027 and025 show MCP3 bottom left; positions not transferred to other renditions.'}
    card.update({'prepared_utc': now, 'review_number': 73, 'family_review_total': 2, 'family_total_scope':
        'Two known individual MCP3 finish folders:White and Verdigris/Rust. Rust arrangements remain separately pending; reference counts are not physical sculpture or mould counts.',
        'proposed_name': order[0]['label'], 'primary_image_id': primary_id, 'primary_folder_id': folder_id,
        'primary_image_link': links[primary_id]['copy_link_url'], 'primary_folder_link': links[folder_id]['copy_link_url'],
        'original_closeup_id': closeup_id, 'original_closeup_link': links[closeup_id]['copy_link_url'],
        'series_image_id': previous['series_image_id'], 'series_folder_id': previous['series_folder_id'],
        'series_image_link': previous['series_image_link'], 'series_folder_link': previous['series_folder_link'],
        'series_target_position': 'Bottom left in exact027 photograph', 'exhibition_image_id': previous['exhibition_image_id'],
        'exhibition_image_link': previous['exhibition_image_link'], 'exhibition_target_position': 'Bottom left in exact025 photograph; venue not independently authenticated',
        'metadata_checked_utc': metadata_doc['checked_utc'], 'specification_review_items': items, 'platform_mapping': mapping,
        'photo_coverage': coverage, 'pending_arrangement_component_review': pending,
        'next_review_after_keep': order[1], 'next_global_component': {'component_id': 'BC-MCP-4', 'review_number': 74}})
    card['open_gaps'][0] = 'Owner White MCP3 name and depicted identity'
    audit = {'schema_version': 1, 'prepared_utc': now, 'maker_source': rel(HERE / 'maker-source-reference.json'), 'maker_code': 'MCP3-25x25',
        'maker_row': row, 'labelled_reference': labelled, 'dated_price_source': rel(HERE / 'dated-price-source-scope.json'),
        'current_census': rel(HERE / 'mcp3-initial-census.json'), 'current_White_files': 9, 'all_White_previews_viewed': True,
        'White_originals_viewed': [primary_id, closeup_id], 'White_original_hash_receipts': rel(HERE / 'mcp3-white/original-download-receipts.json'),
        'series_originals_current_head_checked_and_viewed': ['id:cnqzTNngPVsAAAAAAAugDQ', 'id:cnqzTNngPVsAAAAAAA512A'],
        'exact_series_position': 'Bottom left in027 and025', 'geometry': 'Central convex boss with outer ring broad at lower edge and tapering near upper-right; labelled maker017 and Trade3 support MCP3.',
        'clean_reference_cream_tone_is_new_finish_confirmation': False, 'same_cast_or_edit_lineage_verified': False,
        'whole_family_completed': False, 'remaining_finish': order[1], 'Rust_arrangements_pending': pending, 'physical_specs_verified': False}
    write(HERE / 'mcp3-white/before-staging.json', {'recorded_utc': now, 'files': {rel(paths[k]): v for k,v in before.items()}, 'protected_sha256': protected})
    write(output, card)
    write(HERE / 'mcp3-white/source-audit.json', audit)
    p['reviews']['BC-MCP-3'] = {'reviewed_utc': now, 'review_number': 73, 'proposed_name': card['proposed_name'], 'size_finish_variant_id': 'MCP3-WHITE',
        'identity_confirmed': False, 'specifications_approved': False, 'physical_specs_verified': False, 'source_specifications_recorded': True,
        'specification_proposals': copy.deepcopy(items), 'primary_image_id': primary_id, 'primary_folder_id': folder_id,
        'review_record': rel(output), 'platform_mapping': mapping, 'photo_coverage': coverage, 'gaps': card['open_gaps'],
        'pending_size_finish_variants': order[1:], 'pending_arrangement_component_review': pending, 'review_family_scope': card['review_family_scope']}
    p['family_review_progress']['Moon Crater Phase 3'] = {'family': 'Moon Crater Phase', 'review_scope': card['family_total_scope'],
        'status': 'FIRST_PASS_IN_PROGRESS', 'updated_utc': now, 'review_reference_cards_answered': 0, 'review_reference_total': 2,
        'reference_total_is_sculpture_count': False, 'specifications_complete': False}
    state = 'Awaiting MCP3 White name; all six specification groups pending; historical weight differences retained'
    cp.update({'current_component_id': 'BC-MCP-3', 'current_review_number': 73, 'current_size_finish_variant_id': 'MCP3-WHITE',
        'current_component_layout_id': None, 'proposed_name': card['proposed_name'], 'state': state, 'current_review_record': rel(output),
        'current_family_review_number': 1, 'current_family_review_total': 2, 'active_family': 'Moon Crater Phase 3', 'family_review_order': order,
        'family_first_pass_complete': False, 'current_answer_recorded': False, 'current_specification_answer_recorded': False,
        'current_dimension_answer_recorded': False, 'current_partial_specification_answer_recorded': False, 'current_dimension_approval': None,
        'current_owner_face_dimensions_cm': None, 'current_identity_relationship_answer_recorded': False, 'current_identity_relationship_approval': None,
        'canonical_depicted_name': None, 'current_separate_saleable_design': None, 'working_version_user_approved': False,
        'review_decision_mode': card['review_decision_mode'], 'question_scope': card['scope'],
        'answer_state': 'MCP2 known individual finish names kept; MCP3 White identity and specifications pending.',
        'primary_image': {'file_id': primary_id, 'name': primary['name'], 'path_display': primary['path_display'], 'copy_link_url': card['primary_image_link'], 'open_in_dropbox_url': links[primary_id]['open_in_dropbox_url']},
        'containing_folder': {'folder_id': folder_id, 'name': folder['name'], 'path_display': folder['path_display'], 'copy_link_url': card['primary_folder_link'], 'open_in_dropbox_url': links[folder_id]['open_in_dropbox_url']},
        'metadata_checked_utc': metadata_doc['checked_utc'], 'family_review_evidence': rel(HERE / 'mcp3-white/source-audit.json'),
        'displayed_identity_evidence_file_ids': [primary_id], 'displayed_identity_evidence_folder_ids': [folder_id],
        'current_component_source_notes': [x['display'] for x in items], 'family_counting_note': card['family_total_scope'],
        'next_review_after_keep': order[1], 'updated_utc': now})
    c['interactive_review_state'].update({'current_component_id': 'BC-MCP-3', 'review_number': 73, 'current_size_finish_variant_id': 'MCP3-WHITE',
        'current_component_layout_id': None, 'current_name': card['proposed_name'], 'state': state, 'active_family': 'Moon Crater Phase 3',
        'family_review_number': 1, 'family_review_total': 2, 'specification_proposals_approved': False, 'working_version_user_approved': False,
        'review_decision_mode': card['review_decision_mode']})
    c['current_component_review_record'] = rel(output)
    c['last_family_media_review'] = {'family': 'Moon Crater Phase', 'review_scope': 'MCP3 White9 files plus exact reused series photographs',
        'observed_utc': census['checked_utc'], 'files': 9, 'folders': 1, 'full_new_originals': 2,
        'evidence': rel(HERE / 'mcp3-white/source-audit.json'), 'workbook_contains_this_live_media_audit': False}
    c['updated_utc'] = p['updated_utc'] = now
    docs['root']['current_component_review'] = copy.deepcopy(c)
    docs['root']['updated_utc'] = now
    assert all(p['reviews'][k] == v for k,v in before['progress']['reviews'].items())
    assert p['offer_photo_bindings'] == before['progress']['offer_photo_bindings']
    for key in ['parallel_import_queue', 'parallel_owner_reviews', 'parallel_evidence_flags', 'pending_specification_reviews', 'next_serialized_parallel_import', 'last_parallel_import']:
        assert cp[key] == before['walkthrough'][key], key
    assert all(sha(path) == hashes[k] for k,path in paths.items())
    assert all(sha(Path(path)) == digest for path,digest in protected.items())
    for key,path in paths.items():
        write(path, docs[key])
        assert read(path) == docs[key]
    result = {'status': 'PASS', 'current_name': card['proposed_name'], 'all_six_groups_unapproved': True,
        'maker_row': 43, 'numbered_trade_row': 3, 'known_individual_finish_reference_count': 2,
        'exact027and025_position': 'Bottom left', 'White_exact_platform_offer_unconfirmed': True,
        'native_closeup_clean_reference_and_weight_differences_preserved': True,
        'prior_approvals_parallel_queues_model_workbook_preserved': True,
        'checkpoint_copies_match': read(paths['root'])['current_component_review'] == read(paths['component'])}
    write(HERE / 'mcp3-white/review-validation.json', result)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
