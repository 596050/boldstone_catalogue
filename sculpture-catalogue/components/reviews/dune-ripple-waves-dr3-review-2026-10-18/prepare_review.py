"""Prepare and stage the DR3 source-photo review without resolving DR1 aliases."""
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


def write(path, data):
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(path)


def main():
    card_path = HERE / 'component-review.json'
    assert not card_path.exists(), 'Review already frozen'
    paths = {'walkthrough': REVIEWS / 'walkthrough_checkpoint.json', 'progress': REVIEWS / 'specification_review_progress.json',
             'component': ROOT / 'components/checkpoint.json', 'root': ROOT / 'checkpoint.json'}
    docs = {key: read(path) for key, path in paths.items()}
    before = copy.deepcopy(docs)
    shared_sha = {key: sha(path) for key, path in paths.items()}
    cp, progress, component = (docs[key] for key in ['walkthrough', 'progress', 'component'])
    assert cp['current_size_finish_variant_id'] == 'DR-SPIRAL-BRONZE-VERDIGRIS' and cp['current_answer_recorded']
    assert cp['next_review_after_keep']['component_id'] == 'BC-DR-WAVE3' and 'BC-DR-WAVE3' not in progress['reviews']
    assert cp['review_order'][37] == 'BC-DR-WAVE3' and len(cp['family_review_order']) == 14
    assert docs['root']['current_component_review'] == component
    prior = ROOT / cp['last_identity_approval']
    assert read(prior)['user_statement'] == 'Keep “Dune Ripple Spiral — Bronze and Verdigris”'
    assert not read(prior)['specifications_approved']
    meta = read(HERE / 'metadata-links.json')
    file, folder = meta['primary_metadata']['file'], meta['folder_metadata']['folder']
    assert file['id'] == 'id:cnqzTNngPVsAAAAAAA50IA' and folder['id'] == 'id:cnqzTNngPVsAAAAAAArseQ'
    assert all(not x['has_more'] and not x['cursor'] for x in meta['listings'].values())
    assert {k: len(v['entries']) for k, v in meta['listings'].items()} == {'solo': 20, 'solo_context': 0, 'series': 23, 'series_context': 7}
    cache = read(HERE / 'image-review-index.json')['cached_previews']
    assert len(cache) == 50
    original_receipts = read(HERE / 'download-receipts.json') + [read(HERE / 'garden-download-receipt.json')]
    reuse = read(HERE / 'series-original-reuse-check.json')
    assert reuse['status'] == 'PASS'
    original_receipts.append(reuse['original_receipt'])
    for receipt in original_receipts:
        path = Path(receipt['local_path'])
        assert path.stat().st_size == receipt['size'] and sha(path) == receipt['sha256']
        data = path.read_bytes()
        content = hashlib.sha256(b''.join(hashlib.sha256(data[i:i + 4194304]).digest() for i in range(0, len(data), 4194304))).hexdigest()
        assert content == receipt['content_hash'] == receipt['dropbox_content_hash_verified']
    comparison = read(HERE / 'maker-image-comparison.json')
    assert comparison['maker_row'] == 56 and comparison['aligned_size_luma_correlation'] > .98
    assert comparison['visually_complete_individual_front'] and not comparison['physical_mould_cast_identity_certified']
    maker_reuse = read(HERE / 'maker-original-reuse-check.json')
    assert maker_reuse['status'] == 'PASS' and sha(Path(maker_reuse['local_path'])) == maker_reuse['sha256']
    model_path = ROOT / 'components/evidence/component_register.json'
    model = read(model_path)
    claims = [x for x in model['claims'] if x['component_id'] == 'BC-DR-WAVE3' and 'row56/' in x.get('source_ref', '')]
    assert len(claims) == 5
    old_white = ROOT / 'components/reviews/dune-ripple-waves-dr1-review-2026-10-17/component-review.json'
    old_card = read(old_white)
    packet_ref = rel(HERE / 'advisory-packet-used.json')
    items = []

    def item(suffix, field, value, display, status, basis, refs):
        items.append({'proposal_id': 'DR3-WHITE-' + suffix, 'field': field, 'value': value, 'display': display,
                      'status': status, 'basis': basis, 'source_refs': refs, 'owner_approved': False})

    row = 'manufacture-stevensons:Sheet1!row56'
    item('DIMENSIONS', 'Individual dimensions and depth',
         {'source_face_cm': [35, 20], 'source_side_depth_range_cm': [5, 7], 'actual_measured_dimensions_cm': None},
         'Approximately 35 H × 20 W × 5–7 D cm — historical maker standard; actual panel unmeasured',
         'SOURCE STANDARD; CAST APPLICABILITY PENDING', 'Row56 states approximately350×200mm with50–70mm side. No coloured35×21×6cm transfer or division of set dimensions.', [row])
    item('WEIGHT', 'Individual dry weight',
         {'maker_calculated_range_kg': [3, 5], 'dated_generic_estimates_kg': [4.5, 5], 'actual_weighed_kg': None},
         'Approximately 3–5 kg — historical calculated estimate; not weighed', 'SOURCE ESTIMATE; NOT ACTUAL WEIGHING',
         'Maker row56 calculates3–5kg. Generic family retail estimates4.5/5kg have provisional DR3 applicability. No set mass division.', [row, packet_ref])
    item('MATERIAL', 'Material and finish',
         {'historical_standard': 'Jesmonite AC730, white marble stone finish', 'actual_binder': None, 'reinforcement': None, 'sealing': None},
         'Jesmonite AC730, white marble stone finish — historical maker specification; pictured composition unverified',
         'SOURCE STANDARD; PHYSICAL COMPOSITION UNKNOWN', 'Row56 specifies this manufacturing standard. A matched source photograph does not verify binder, reinforcement, sealer, care or exterior suitability of a particular cast.', [row])
    item('FIXING', 'Fixing',
         {'historical_points': 1, 'historical_material': 'Stainless steel', 'historical_position': 'Centre rear, upper third', 'actual_hardware': None, 'attachment': None, 'rated_load': None},
         'One small stainless-steel rear fixing, centre back in upper third — historical instruction; actual hardware unconfirmed',
         'SOURCE INSTRUCTION; EXACT REAR AND LOAD UNKNOWN', 'Row56 specifies one stainless fixing aligned with the series. No matching rear in50source views. Keyhole type, attachment, wall hardware and load are not certified.', [row])
    item('PRICE', 'Individual retail price',
         {'proposed_amount': 175, 'currency': 'GBP', 'sale_unit': 'One individual white DR3 panel', 'exact_existing_offer_confirmed': False},
         '£175 per individual panel — working proposal from the dated generic Dune Ripple retail draft',
         'UNAPPROVED PRICE PROPOSAL', 'Generic family reference175GBP supplies a discussion proposal, not a directly matched DR3 offer. Earlier146.09retail and87trade remain separate dated classes; no set-price division.', [packet_ref])
    item('AVAILABILITY', 'Availability',
         {'proposed_sale_policy': 'Made to order individually / enquire', 'physical_stock_quantity': None, 'reproducibility': None, 'lead_time': None},
         'Made to order individually / enquire — proposal; stock, reproducibility and lead time unknown',
         'UNAPPROVED SALE POLICY', 'Maker instructions and photographs do not establish current stock, mould inventory, production capacity or lead time.', [packet_ref])
    links = {x['file_name']: x for x in meta['previews']}
    now = datetime.now(timezone.utc).isoformat()
    mapping = {'status': 'EXACT WHITE DR3 SQUARESPACE/SHOPIFY OFFER UNCONFIRMED', 'squarespace_id': None,
        'shopify_handle': None, 'shared_sku': None, 'primary_file_id': file['id'], 'primary_folder_id': folder['id'],
        'related_coloured_offer_refs': ['O004', 'O038', 'O051', 'O067'], 'coloured_mould_allocation_confirmed': False,
        'live_platform_accounts_or_public_pages_refreshed': False}
    coverage = {'complete_individual_front': True, 'detail_views_available': True, 'rear': False,
        'series_reference_available': True, 'garden_setting_in_series_available': True,
        'exact_DR1_DR3_series_position_allocation_confirmed': False, 'same_cast_in_series_or_setting_verified': False,
        'confirmed_standalone_installation_photo': False, 'client_installation_provenance': False,
        'scope': 'Current50-file census across4white folders; all50cached previews viewed. Three candidate originals and one garden original newly downloaded/hash verified/viewed; clean series original freshly rehashed/viewed.016shows all panel edges and matches maker43;019/020are tighter views. No rear or standalone setting established.'}
    next_review = {'component_id': 'BC-EMBED-SHELLS', 'review_number': 45, 'requires_pending_parallel_import': True}
    card = {'schema_version': 1, 'prepared_utc': now, 'component_id': 'BC-DR-WAVE3', 'canonical_design_name': 'Dune Ripple Waves — DR3',
        'proposed_name': 'Dune Ripple Waves — White (DR3)', 'display_name': 'Dune Ripple Waves — White (DR3)',
        'family': 'Dune Ripple', 'maker_code': 'DR3-35x20', 'review_number': 38, 'family_review_number': 14, 'family_review_total': 14,
        'size_finish_variant_id': 'DR3-WHITE', 'variant_only_review': False, 'review_decision_mode': 'COMPONENT_NAME_AND_SPECIFICATIONS',
        'scope': 'Selected complete white016source photograph. DR3maker photo association supported; relation to earlier named DR1image001 and series positions requires owner review. Name approval does not certify mould, cast, manufacture or specifications.',
        'primary_image_id': file['id'], 'primary_folder_id': folder['id'], 'primary_image_link': links[file['id']]['copy_link_url'],
        'primary_folder_link': links[folder['id']]['copy_link_url'], 'metadata_checked_utc': meta['checked_utc'],
        'reference_refresh': rel(HERE / 'metadata-links.json'), 'source_audit': rel(HERE / 'source-audit.json'),
        'maker_claims': claims, 'maker_labelled_references': read(HERE / 'maker-labelled-references.json'),
        'maker_source_file_id': 'id:cnqzTNngPVsAAAAAAAuDJA', 'maker_photo_comparison': rel(HERE / 'maker-image-comparison.json'),
        'specification_review_items': items, 'platform_mapping': mapping, 'photo_coverage': coverage,
        'prior_DR1_reference': {'component_id': 'BC-DR-WAVE1', 'file_id': old_card['primary_image_id'],
            'folder_id': old_card['primary_folder_id'], 'image_link': old_card['primary_image_link'], 'review_record': rel(old_white),
            'scope': 'Previously kept name/depicted identity preserved. Source001looks similar to current016; code/mould relationship unresolved. Previous right-panel series association is not promoted to certified DR1allocation.'},
        'code_relationship_question': 'Is this a separate DR3 component or the same design as the earlier DR1 photograph?',
        'series_image_id': 'id:cnqzTNngPVsAAAAAAAykvw', 'series_folder_id': 'id:cnqzTNngPVsAAAAAAAyiag',
        'series_image_link': links['id:cnqzTNngPVsAAAAAAAykvw']['copy_link_url'],
        'series_position': 'Exact DR1/DR3positional allocation retained as unresolved; no silent left/right reassignment',
        'garden_image_id': 'id:cnqzTNngPVsAAAAAAAykuw', 'garden_folder_id': 'id:cnqzTNngPVsAAAAAAAykvg',
        'garden_image_link': links['id:cnqzTNngPVsAAAAAAAykuw']['copy_link_url'],
        'source_conflicts': ['Maker rows54/56name separate DR1/DR3moulds, but prior001photo code binding is provisional and looks similar to current016.',
            'Current full016original and maker43match supersede the advisory isolated-photo gap only; prior evidence and owner name are unchanged.',
            'White source standards and generic dated prices are not verified current cast facts or individual offers.'],
        'open_gaps': ['Resolve DR1image001versus DR3image016relationship and exact series code positions',
            'Measure actual face/depth and dry weight', 'Confirm binder, reinforcement, sealing and care',
            'Exact rear, hardware attachment/type, wall fixing and load', 'Owner individual price and availability; physical stock, reproducibility and lead time',
            'Exact white DR3 platform offer; standalone installation and scene provenance'],
        'identity_confirmed': False, 'specifications_approved': False, 'physical_specs_verified': False,
        'next_review_after_keep': next_review, 'next_global_component_id': 'BC-EMBED-SHELLS',
        'family_first_pass_complete': False, 'remote_files_changed': False, 'live_platform_records_changed': False}
    evidence = [p for p in HERE.iterdir() if p.is_file()] + [model_path, old_white, prior, Path(maker_reuse['local_path'])]
    evidence += [Path(x['preview_path']) for x in cache] + [Path(x['local_path']) for x in original_receipts]
    evidence += [Path(x['picture']['path']) for x in card['maker_labelled_references']]
    audit = {'status': 'PASS', 'checked_utc': now, 'current_file_references_reviewed': 50, 'new_originals_verified_and_viewed': 4,
        'reused_series_original_rehashed_and_viewed': 1, 'maker_original_revision_and_sha_unchanged': True,
        'complete_individual_DR3_source_photo_located': True, 'prior_advisory_isolated_gap_superseded_for_selected_reference': True,
        'DR1_DR3_alias_or_physical_cast_equivalence_resolved': False, 'evidence_sha256': {str(p): sha(p) for p in sorted(set(evidence))}}
    write(HERE / 'source-audit.json', audit)
    write(card_path, card)
    protected = {str(p): sha(p) for p in [card_path, HERE / 'source-audit.json', model_path, old_white, prior,
        REVIEWS / 'user_classifications.json', ROOT / cp['register_workbook'], ROOT / cp['current_review_record']]}
    write(HERE / 'before-stage-review.json', {'recorded_utc': now, 'files': {rel(paths[k]): v for k, v in before.items()}, 'protected_sha256': protected})
    progress['reviews']['BC-DR-WAVE3'] = {'reviewed_utc': now, 'review_number': 38, 'proposed_name': card['proposed_name'],
        'size_finish_variant_id': 'DR3-WHITE', 'identity_confirmed': False, 'specifications_approved': False, 'physical_specs_verified': False,
        'source_specifications_recorded': True, 'specification_proposals': copy.deepcopy(items), 'maker_claims': claims,
        'primary_image_id': file['id'], 'primary_folder_id': folder['id'], 'review_record': rel(card_path),
        'platform_mapping': mapping, 'photo_coverage': coverage, 'gaps': card['open_gaps'],
        'code_relationship_status': 'OWNER REVIEW REQUIRED; PRIOR DR1NAME/IMAGE PRESERVED'}
    progress['updated_utc'] = now
    state = 'Awaiting White DR3 name/identity and DR1photo relationship; six specifications separately pending'
    cp.update({'current_component_id': 'BC-DR-WAVE3', 'current_review_number': 38, 'current_size_finish_variant_id': 'DR3-WHITE',
        'proposed_name': card['proposed_name'], 'state': state, 'current_review_record': rel(card_path),
        'primary_image': {'file_id': file['id'], 'name': file['name'], 'path_display': file['path_display'],
            'copy_link_url': card['primary_image_link'], 'open_in_dropbox_url': links[file['id']]['open_in_dropbox_url']},
        'containing_folder': {'folder_id': folder['id'], 'name': folder['name'], 'path_display': folder['path_display'],
            'copy_link_url': card['primary_folder_link'], 'open_in_dropbox_url': links[folder['id']]['open_in_dropbox_url']},
        'current_answer_recorded': False, 'current_specification_answer_recorded': False, 'current_dimension_answer_recorded': False,
        'working_version_user_approved': False, 'review_decision_mode': 'COMPONENT_NAME_AND_SPECIFICATIONS',
        'current_family_review_number': 14, 'current_family_review_total': 14, 'family_review_evidence': card['reference_refresh'],
        'question_scope': card['scope'] + ' ' + card['code_relationship_question'], 'answer_state': 'No answer yet; names, code relationship and specifications remain separate scopes.',
        'metadata_checked_utc': meta['checked_utc'], 'next_review_after_keep': next_review,
        'displayed_identity_evidence_file_ids': [file['id']], 'displayed_identity_evidence_folder_ids': [folder['id']],
        'current_component_source_notes': [x['display'] for x in items], 'updated_utc': now})
    component['interactive_review_state'].update({'current_component_id': 'BC-DR-WAVE3', 'review_number': 38,
        'current_size_finish_variant_id': 'DR3-WHITE', 'current_name': card['proposed_name'], 'state': state,
        'family_review_number': 14, 'family_review_total': 14, 'specification_proposals_approved': False,
        'working_version_user_approved': False, 'review_decision_mode': 'COMPONENT_NAME_AND_SPECIFICATIONS'})
    component['current_component_review_record'] = rel(card_path)
    component['last_family_media_review'] = {'family': 'Dune Ripple', 'finish': 'White DR3 and mixed white-series source photos',
        'observed_utc': meta['checked_utc'], 'files': 50, 'folders': 4, 'scope': coverage['scope'],
        'evidence': card['reference_refresh'], 'workbook_contains_this_live_media_audit': False}
    component['updated_utc'] = now
    docs['root']['current_component_review'] = copy.deepcopy(component)
    docs['root']['updated_utc'] = now
    assert all(progress['reviews'][cid] == value for cid, value in before['progress']['reviews'].items())
    assert all(sha(paths[key]) == value for key, value in shared_sha.items()), 'Shared writer collision'
    for key, path in paths.items():
        write(path, docs[key])
        assert read(path) == docs[key]
    assert all(sha(Path(path)) == value for path, value in protected.items())
    assert read(paths['root'])['current_component_review'] == read(paths['component'])
    result = {'status': 'PASS', 'current_component': 'BC-DR-WAVE3', 'family_card': 14, 'six_unapproved_groups': 6,
        'complete_single_source_photo_available': True, 'prior_DR1_name_and_image_unchanged': True,
        'DR1_DR3_relationship_unresolved': True, 'prior_decisions_model_ledger_and_workbook_unchanged': True,
        'next_pending_parallel_import_not_applied': True, 'remote_files_changed': False}
    write(HERE / 'review-validation.json', result)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
