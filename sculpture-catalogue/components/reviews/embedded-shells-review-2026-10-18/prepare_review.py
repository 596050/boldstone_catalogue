"""Stage Embedded Shells after the verified bounded import; all six fields are proposals."""
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


def write(p, value):
    t = p.with_name(p.name + '.tmp')
    t.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    t.replace(p)


def main():
    card_path = HERE / 'component-review.json'
    assert not card_path.exists(), 'Review already frozen'
    paths = {'walkthrough': REVIEWS / 'walkthrough_checkpoint.json', 'progress': REVIEWS / 'specification_review_progress.json',
        'component': ROOT / 'components/checkpoint.json', 'root': ROOT / 'checkpoint.json'}
    docs = {k: read(p) for k, p in paths.items()}
    before = copy.deepcopy(docs)
    digests = {k: sha(p) for k, p in paths.items()}
    cp, progress, component = (docs[k] for k in ['walkthrough', 'progress', 'component'])
    assert cp['current_component_id'] == 'BC-DR-WAVE3' and cp['current_answer_recorded'] and cp['family_first_pass_complete']
    assert cp['next_review_after_keep']['component_id'] == 'BC-EMBED-SHELLS' and not cp['next_review_after_keep']['requires_pending_parallel_import']
    assert cp['next_serialized_parallel_import']['status'] == 'APPLIED_AND_VERIFIED'
    assert read(ROOT / cp['last_parallel_import']['receipt'])['identity_receipts'] == 18
    assert read(ROOT / cp['current_identity_relationship_approval'])['relationship'] == 'SAME_DEPICTED_DESIGN'
    assert docs['root']['current_component_review'] == component
    model_path = ROOT / 'components/evidence/component_register.json'
    model = read(model_path)
    source_component = next(x for x in model['components'] if x['component_id'] == 'BC-EMBED-SHELLS')
    assert source_component['offer_refs'] == [] and source_component['maker_rows'] == []
    assert not [x for x in model['claims'] if x.get('component_id') == 'BC-EMBED-SHELLS']
    packet_path = ROOT / 'components/parallel-preparation/20261017T164751Z/worker-01/packets.json'
    packet = next(x for x in read(packet_path)['entries'] if x['component_id'] == 'BC-EMBED-SHELLS')
    write(HERE / 'advisory-packet-used.json', {'source': rel(packet_path), 'source_sha256': sha(packet_path), 'packet': packet})
    meta = read(HERE / 'metadata-links.json')
    assert [(x['key'], len(x['entries']), x['has_more'], x['cursor']) for x in meta['listings']] == [('solo', 1, False, ''), ('context', 11, False, '')]
    refs = {x['request_id']: x for x in meta['metadata']}
    file = refs['id:cnqzTNngPVsAAAAAAAyk1w']['file']
    folder = refs['id:cnqzTNngPVsAAAAAAAykCQ']['folder']
    assert file['path_display'].rsplit('/', 1)[0] == folder['path_display']
    thumbnails = read(HERE / 'image-review-index.json')['cached_previews']
    assert len(thumbnails) == 12
    originals = read(HERE / 'download-receipts.json')
    assert len(originals) == 3
    for receipt in originals:
        p = Path(receipt['local_path'])
        assert p.stat().st_size == receipt['size'] and sha(p) == receipt['sha256']
        b = p.read_bytes()
        assert hashlib.sha256(b''.join(hashlib.sha256(b[i:i+4194304]).digest() for i in range(0, len(b), 4194304))).hexdigest() == receipt['content_hash']
    links = {x['file_name']: x for x in meta['previews']}
    source_dir = ROOT / 'components/evidence/price-source-review-2026-10-17'
    retail = source_dir / 'Retail PRICE List 2025.docx.txt'
    previous = source_dir / 'previous_retail_source.txt'
    assert '100cm x 22cm' in retail.read_text() and '550' in retail.read_text()
    assert 'Embedded Shells' not in retail.read_text() and 'Embedded Shells' not in previous.read_text()
    now = datetime.now(timezone.utc).isoformat()
    items = []

    def item(suffix, field, display, value, basis, sources):
        items.append({'proposal_id': 'EMBED-SHELLS-WHITE-' + suffix, 'field': field, 'display': display,
            'value': value, 'status': 'UNAPPROVED WORKING GUESS; NOT AN OBJECT-SPECIFIC SOURCE SPECIFICATION',
            'basis': basis, 'source_refs': sources, 'owner_approved': False, 'physical_specs_verified': False})

    item('DIMENSIONS', 'Individual dimensions and depth', 'Approximately 100 H × 25 W × 5–7 D cm — working guess; all measurements unconfirmed',
        {'proposed_height_cm': 100, 'proposed_width_cm': 25, 'proposed_depth_range_cm': [5, 7], 'measured_dimensions_cm': None},
        'The complete front shows a roughly4-to-1 tall panel. Absolute scale and depth cannot be recovered from the photograph. Metre-long reliefs in dated price records are analogies only;100×25×5–7is a discussion hypothesis.',
        [file['id'], rel(retail) + ':line61', rel(HERE / 'advisory-packet-used.json')])
    item('WEIGHT', 'Individual dry weight', 'Approximately 8–12 kg — weak analogy assuming a metre-long mineral-composite panel; not weighed',
        {'proposed_range_kg': [8, 12], 'actual_weighed_kg': None, 'assumed_size_and_construction_confirmed': False},
        'Dated retail draft gives10kg for different100×22cm long reliefs. This is not an Embedded Shells weight; actual size, average material thickness, backing and binder are unknown. No density calculation or division of set weight is claimed.',
        [rel(retail) + ':line61', rel(HERE / 'advisory-packet-used.json')])
    item('MATERIAL', 'Material and finish', 'Cast mineral composite with an off-white textured finish and shell motifs — working hypothesis; binder and real-shell inclusions unknown',
        {'visible_appearance': 'Off-white coarse textured relief with raised spiral shell-like motifs', 'proposed_construction': 'Cast mineral composite', 'actual_binder': None, 'actual_shell_inclusions': None, 'sealer': None},
        'Front appearance supports the colour, texture and motifs only. It cannot establish Jesmonite, gypsum, concrete, real marble, actual embedded shells, reinforcement or outdoor suitability.', [file['id']])
    item('FIXING', 'Fixing', 'Concealed rear fixing — planning proposal; type, number, attachment and load unknown',
        {'proposed_scheme': 'Concealed rear fixing', 'hardware_type': None, 'count': None, 'rated_load': None},
        'No rear image or component-specific fixing instruction found in the12current views. A concealed fixing is a catalogue placeholder, not an installation specification.', [rel(HERE / 'metadata-links.json')])
    item('PRICE', 'Individual retail price', '£500–£700 per panel — tentative discussion range; no matched individual offer',
        {'proposed_range_gbp': [500, 700], 'exact_existing_offer_confirmed': False, 'owner_price_approved': False},
        'A different100×22cm white relief is550GBP in the dated2025draft; an earlier dated generic long-relief figure is432.41GBP. Neither names Embedded Shells. The range is an owner-discussion guess; no set price allocated.',
        [rel(retail) + ':line61', rel(previous), rel(HERE / 'advisory-packet-used.json')])
    item('AVAILABILITY', 'Availability', 'Made to order / enquire — proposed policy only; production, stock and lead time unknown',
        {'proposed_policy': 'Made to order / enquire subject to production confirmation', 'physical_stock': None, 'reproducibility': None, 'lead_time': None},
        'Photographs do not confirm current mould availability, manufacture, a physical stocked cast or lead time. Sale policy needs owner confirmation.', [rel(HERE / 'advisory-packet-used.json')])
    coverage = {'complete_individual_front': True, 'detail_views_available': True, 'room_setting_available': True,
        'brick_wall_setting_available': True, 'exact_series_or_multi_panel_arrangement_found': False, 'rear': False,
        'actual_client_installation_provenance_confirmed': False, 'same_physical_cast_in_context_confirmed': False,
        'scope': 'Fresh complete1solo+11context census; all12previews viewed and3originals freshly downloaded/hash-verified/viewed. Historical brick-wall image is cropped at ends; current primary shows all edges. Room views visually repeat the motifs, with scene provenance unconfirmed. No separate series arrangement or rear found in these folders.'}
    mapping = {'status': 'EXACT SQUARESPACE/SHOPIFY INDIVIDUAL OFFER UNCONFIRMED IN REVIEWED EXPORTS',
        'squarespace_id': None, 'shopify_handle': None, 'shared_sku': None, 'source_component_offer_refs': [],
        'scope': 'No offer or maker row is bound to BC-EMBED-SHELLS in the preserved source model. Similar long relief prices supply analogies only.',
        'live_platform_records_refreshed': False}
    next_review = {'component_id': 'BC-FACET-MOUND', 'review_number': 46}
    card = {'schema_version': 1, 'prepared_utc': now, 'component_id': 'BC-EMBED-SHELLS', 'review_number': 45,
        'family': 'Embedded Shells', 'family_review_number': 1, 'family_review_total': 1,
        'size_finish_variant_id': 'EMBED-SHELLS-WHITE', 'canonical_design_name': 'Embedded Shells',
        'proposed_name': 'Embedded Shells — White', 'display_name': 'Embedded Shells — White',
        'review_decision_mode': 'COMPONENT_NAME_AND_SPECIFICATIONS', 'scope': 'One depicted complete individual off-white shell-relief panel. Name approval is separate from six working guesses and from construction, manufacture or stock confirmation.',
        'primary_image_id': file['id'], 'primary_folder_id': folder['id'],
        'primary_image_link': links[file['id']]['copy_link_url'], 'primary_folder_link': links[folder['id']]['copy_link_url'],
        'context_image_id': 'id:cnqzTNngPVsAAAAAAAyk1Q', 'context_folder_id': 'id:cnqzTNngPVsAAAAAAAyiiA',
        'context_image_link': links['id:cnqzTNngPVsAAAAAAAyk1Q']['copy_link_url'],
        'context_folder_link': links['id:cnqzTNngPVsAAAAAAAyiiA']['copy_link_url'],
        'historical_brick_wall_image_id': 'id:cnqzTNngPVsAAAAAAAuaTQ',
        'historical_brick_wall_image_link': links['id:cnqzTNngPVsAAAAAAAuaTQ']['copy_link_url'],
        'metadata_checked_utc': meta['checked_utc'], 'reference_refresh': rel(HERE / 'metadata-links.json'),
        'specification_review_items': items, 'platform_mapping': mapping, 'photo_coverage': coverage,
        'source_component_snapshot': source_component, 'advisory_packet': rel(HERE / 'advisory-packet-used.json'),
        'source_conflicts': ['No Embedded Shells dimensions, weight, fixing or individual-price source is established. All six proposed fields remain provisional.',
            'A shell-like appearance and folder name do not prove actual shells or a particular composite. Context imagery does not certify physical installation or exterior suitability.'],
        'open_gaps': ['Owner name and identity', 'Measured face and maximum depth', 'Actual dry weight',
            'Binder, backing, reinforcement, shell inclusions, finish and sealing', 'Rear photograph, actual hardware and fixing/load details',
            'Individual price and current stock/reproducibility/lead time', 'Exact individual platform match',
            'Setting provenance; any intended series relationship'],
        'identity_confirmed': False, 'specifications_approved': False, 'physical_specs_verified': False,
        'next_review_after_keep': next_review, 'next_global_component_id': 'BC-FACET-MOUND',
        'remote_files_changed': False, 'live_platform_records_changed': False}
    evidence = [model_path, packet_path, retail, previous] + [Path(x['local_path']) for x in originals] + [Path(x['preview_path']) for x in thumbnails]
    evidence += [p for p in HERE.iterdir() if p.is_file()]
    write(HERE / 'source-audit.json', {'status': 'PASS', 'checked_utc': now, 'current_files_audited': 12,
        'fresh_originals_hash_verified_and_viewed': 3, 'object_specific_six_fields_established': False,
        'evidence_sha256': {str(p): sha(p) for p in sorted(set(evidence))}})
    write(card_path, card)
    protected_paths = [model_path, ROOT / cp['register_workbook'], REVIEWS / 'user_classifications.json',
        ROOT / cp['current_review_record'], ROOT / cp['current_identity_relationship_approval'], card_path]
    protected = {str(x): sha(x) for x in protected_paths}
    write(HERE / 'before-stage-review.json', {'recorded_utc': now, 'files': {rel(paths[k]): v for k, v in before.items()}, 'protected_sha256': protected})
    assert 'BC-EMBED-SHELLS' not in progress['reviews']
    progress['reviews']['BC-EMBED-SHELLS'] = {'reviewed_utc': now, 'review_number': 45,
        'proposed_name': card['proposed_name'], 'size_finish_variant_id': card['size_finish_variant_id'],
        'identity_confirmed': False, 'specifications_approved': False, 'physical_specs_verified': False,
        'source_specifications_recorded': False, 'working_guesses_recorded': True, 'specification_proposals': copy.deepcopy(items),
        'primary_image_id': file['id'], 'primary_folder_id': folder['id'], 'review_record': rel(card_path),
        'platform_mapping': mapping, 'photo_coverage': coverage, 'gaps': card['open_gaps']}
    progress['updated_utc'] = now
    state = 'Awaiting Embedded Shells White name/identity; six specification guesses separately pending'
    cp['last_identity_relationship_approval'] = cp['current_identity_relationship_approval']
    cp.update({'current_component_id': 'BC-EMBED-SHELLS', 'current_review_number': 45,
        'current_size_finish_variant_id': card['size_finish_variant_id'], 'proposed_name': card['proposed_name'],
        'state': state, 'current_review_record': rel(card_path), 'active_family': 'Embedded Shells',
        'current_family_review_number': 1, 'current_family_review_total': 1,
        'family_review_order': [{'component_id': 'BC-EMBED-SHELLS', 'review_number': 45, 'variant_id': card['size_finish_variant_id'], 'label': card['proposed_name']}],
        'family_first_pass_complete': False, 'current_answer_recorded': False, 'current_specification_answer_recorded': False,
        'current_dimension_answer_recorded': False, 'current_identity_relationship_answer_recorded': False,
        'current_identity_relationship_approval': None, 'canonical_depicted_name': None, 'working_version_user_approved': False,
        'review_decision_mode': card['review_decision_mode'], 'question_scope': card['scope'],
        'answer_state': 'No answer yet; all six fields are unapproved guesses with their source and assumption limits.',
        'primary_image': {'file_id': file['id'], 'name': file['name'], 'path_display': file['path_display'],
            'copy_link_url': card['primary_image_link'], 'open_in_dropbox_url': links[file['id']]['open_in_dropbox_url']},
        'containing_folder': {'folder_id': folder['id'], 'name': folder['name'], 'path_display': folder['path_display'],
            'copy_link_url': card['primary_folder_link'], 'open_in_dropbox_url': links[folder['id']]['open_in_dropbox_url']},
        'family_review_evidence': card['reference_refresh'], 'metadata_checked_utc': meta['checked_utc'],
        'next_review_after_keep': next_review, 'after_main_family_next_unclaimed': next_review,
        'displayed_identity_evidence_file_ids': [file['id']], 'displayed_identity_evidence_folder_ids': [folder['id']],
        'current_component_source_notes': [x['display'] for x in items], 'updated_utc': now})
    component['interactive_review_state'].update({'current_component_id': card['component_id'], 'review_number': 45,
        'current_size_finish_variant_id': card['size_finish_variant_id'], 'current_name': card['proposed_name'], 'state': state,
        'family_review_number': 1, 'family_review_total': 1, 'specification_proposals_approved': False,
        'working_version_user_approved': False, 'review_decision_mode': card['review_decision_mode'],
        'current_identity_relationship_answer_recorded': False, 'canonical_depicted_name': None, 'current_separate_saleable_design': None})
    component['current_component_review_record'] = rel(card_path)
    component['last_family_media_review'] = {'family': 'Embedded Shells', 'observed_utc': meta['checked_utc'],
        'files': 12, 'folders': 2, 'scope': coverage['scope'], 'evidence': card['reference_refresh'], 'workbook_contains_this_live_media_audit': False}
    component['updated_utc'] = now
    docs['root']['current_component_review'] = copy.deepcopy(component)
    docs['root']['updated_utc'] = now
    assert all(progress['reviews'][k] == v for k, v in before['progress']['reviews'].items())
    assert cp['parallel_import_queue'] == before['walkthrough']['parallel_import_queue']
    assert cp['parallel_owner_reviews'] == before['walkthrough']['parallel_owner_reviews']
    assert all(sha(p) == digests[k] for k, p in paths.items()), 'Shared writer collision'
    assert all(sha(Path(p)) == value for p, value in protected.items())
    for key, path in paths.items():
        write(path, docs[key])
        assert read(path) == docs[key]
    result = {'status': 'PASS', 'current_component': card['component_id'], 'review_number': 45,
        'six_unapproved_working_guesses': 6, 'fresh_files_audited': 12, 'fresh_originals_hash_verified_and_viewed': 3,
        'prior_DR_same_design_decision_preserved': True, 'bounded_import_applied_and_preserved': True,
        'ledger_model_workbook_and_prior_review_unchanged': True, 'root_and_component_checkpoint_match': read(paths['root'])['current_component_review'] == read(paths['component'])}
    write(HERE / 'review-validation.json', result)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
