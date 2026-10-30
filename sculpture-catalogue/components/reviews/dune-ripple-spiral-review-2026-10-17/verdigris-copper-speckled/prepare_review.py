"""Prepare a separately scoped speckled reference, without inheriting a sale offer."""
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
REVIEWS = ROOT / 'components/reviews'


def read(p):
    return json.loads(p.read_text())


def write(p, value):
    p.parent.mkdir(parents=True, exist_ok=True)
    t = p.with_name(p.name + '.tmp')
    t.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    t.replace(p)


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def rel(p):
    return str(p.relative_to(ROOT))


paths = {'walkthrough': REVIEWS / 'walkthrough_checkpoint.json', 'progress': REVIEWS / 'specification_review_progress.json',
         'component': ROOT / 'components/checkpoint.json', 'root': ROOT / 'checkpoint.json'}
docs = {k: read(p) for k, p in paths.items()}
cp, progress, component = (docs[k] for k in ['walkthrough', 'progress', 'component'])
out = HERE / 'component-review.json'
if cp.get('current_review_record') == rel(out):
    print('ALREADY_PREPARED')
    raise SystemExit(0)
assert cp['current_component_id'] == 'BC-DR-SPIRAL' and cp['current_size_finish_variant_id'] == 'DR-SPIRAL-VERDIGRIS' and cp['current_answer_recorded']
assert docs['root']['current_component_review'] == component
prior = HERE.parent / 'verdigris'
pale_approval, white_approval = prior / 'identity-approval.json', HERE.parent / 'identity-approval.json'
assert read(pale_approval)['user_statement'] == 'Keep “Dune Ripple Spiral — Verdigris”'
assert read(pale_approval)['identity_confirmed'] and not read(pale_approval)['specifications_approved']
protected = [ROOT / 'components/evidence/component_register.json', ROOT / cp['register_workbook'],
    REVIEWS / 'user_classifications.json', prior / 'component-review.json', pale_approval,
    HERE.parent / 'component-review.json', white_approval]
hashes = {p: sha(p) for p in protected}
parent = progress['reviews']['BC-DR-SPIRAL']
parent_before = {k: copy.deepcopy(v) for k, v in parent.items() if k not in ['size_finish_variants', 'pending_size_finish_variants']}
old_variants = copy.deepcopy(parent['size_finish_variants'])
now = datetime.now(timezone.utc).isoformat()
write(HERE / 'before-speckled-review.json', {'recorded_utc': now,
    'files': {rel(paths[k]): v for k, v in docs.items()}, 'protected_sha256': {rel(p): value for p, value in hashes.items()}})
meta = read(HERE / 'metadata-links.json')
file, folder = meta['primary_metadata']['file'], meta['folder_metadata']['folder']
assert file['id'] == 'id:cnqzTNngPVsAAAAAAAye4A' and folder['id'] == 'id:cnqzTNngPVsAAAAAAAye2A'
assert file['path_display'].rsplit('/', 1)[0] == folder['path_display']
assert read(HERE / 'primary-original-reuse-check.json')['status'] == 'PASS'
for key, listing in meta['listings'].items():
    assert not listing['has_more'] and not listing['cursor']
    assert {x['file_id']: x for x in listing['entries']} == {
        x['file_id']: x for x in read(prior / 'metadata-links.json')['listings'][key]['entries']}
assert sum(len(x['entries']) for x in meta['listings'].values()) == 42
original = read(HERE / 'primary-original-reuse-check.json')['original_receipt']
series = read(HERE / 'series-download-receipts.json')
assert len(series) == 1 and series[0]['id'] == 'id:cnqzTNngPVsAAAAAAAygwg'
for receipt in [original, series[0]]:
    data = Path(receipt['local_path']).read_bytes()
    h = hashlib.sha256(b''.join(hashlib.sha256(data[i:i + 4194304]).digest() for i in range(0, len(data), 4194304))).hexdigest()
    assert len(data) == receipt['size'] and hashlib.sha256(data).hexdigest() == receipt['sha256']
    assert h == receipt['content_hash'] == receipt['dropbox_content_hash_verified']
assert meta['series_metadata']['file']['path_display'].rsplit('/', 1)[0] == meta['series_folder_metadata']['folder']['path_display']
links = {x['file_name']: x for x in meta['previews']}
primary, containing = links[file['id']], links[folder['id']]
vid = 'DR-SPIRAL-VERDIGRIS-COPPER-SPECKLED'
name = 'Dune Ripple Spiral — Verdigris and Copper'
standard = 'manufacture-stevensons:Sheet1!row55; related white standard only'
items = [
    {'proposal_id': vid + '-DIMENSIONS', 'field': 'Individual dimensions and depth',
     'value': {'proposed_dimensions_cm': [35, 21, 6], 'related_white_face_cm': [35, 20], 'related_white_side_depth_range_cm': [5, 7], 'actual_measured_dimensions_cm': None},
     'display': 'Approximately 35 H × 21 W × 6 D cm — working guess; actual panel unmeasured',
     'status': 'UNAPPROVED ANALOGY GUESS; NOT AN EXACT LISTING CLAIM',
     'basis': 'Related white DR2 standard gives35×20cm and5–7cm side depth; separately kept pale listing gives35×21×6cm. Propose35×21×6for discussion only. Similar mould appearance does not prove this specimen’s dimensions or transfer the pale listing claim.',
     'source_refs': [standard, rel(prior / 'component-review.json')]},
    {'proposal_id': vid + '-WEIGHT', 'field': 'Individual dry weight',
     'value': {'proposed_weight_kg': 4, 'working_estimate_range_kg': [3, 5], 'actual_weighed_kg': None},
     'display': 'Approximately 4 kg (working range3–5kg) — guess; not weighed',
     'status': 'UNAPPROVED ANALOGY ESTIMATE',
     'basis': 'Historical white DR2 maker standard calculates3–5kg. Current binder, average material thickness, cavity and reinforcement are unknown. No conversion of unencoded native weights or division of set weight is used.',
     'source_refs': [standard]},
    {'proposal_id': vid + '-MATERIAL', 'field': 'Material and finish',
     'value': {'proposed_substrate': 'Cast mineral composite', 'visual_finish_description': 'Verdigris/copper-effect surface with dense brown metallic-coloured speckling', 'actual_binder': None, 'actual_metal_content': None, 'reinforcement': None, 'sealing': None},
     'display': 'Cast mineral composite with verdigris/copper-effect finish — guess; binder and metal content unknown',
     'status': 'UNAPPROVED MATERIAL GUESS AND VISUAL FINISH DESCRIPTION',
     'basis': '005original shows a complete two-curl panel with dense copper/brown-coloured speckling on a turquoise surface. Cast mineral composite is inferred from related works. Colour and a white rear candidate do not establish copper metal, bronze, gypsum or AC730.',
     'source_refs': [rel(HERE / 'primary-original-reuse-check.json'), standard]},
    {'proposal_id': vid + '-FIXING', 'field': 'Fixing',
     'value': {'proposed_hanging_points': 1, 'proposed_type': 'Recessed rear keyhole hanger', 'candidate_rear_file_id': 'id:cnqzTNngPVsAAAAAAAye2Q', 'exact_front_back_match_verified': False, 'actual_hardware': None, 'attachment': None, 'rated_load': None},
     'display': 'One recessed rear keyhole fixing — guess; exact rear,hardware and load unconfirmed',
     'status': 'UNAPPROVED GUESS FROM RELATED TEMPLATE AND UNASSIGNED REAR',
     'basis': 'Related white DR2 instructions specify one rear fixing; folder015shows a single keyhole plate. Its relationship to this speckled005front remains unverified. No metal grade, exact placement, attachment or load capacity is certified.',
     'source_refs': [standard, rel(prior / 'front-rear-download-receipts.json')]},
    {'proposal_id': vid + '-PRICE', 'field': 'Individual retail price',
     'value': {'proposed_amount': 200, 'currency': 'GBP', 'sale_unit': 'One depicted speckled verdigris/copper-effect panel', 'exact_existing_offer_confirmed': False, 'owner_price_approval': False, 'finish_costing_confirmed': False},
     'display': '£200 per individual panel — working price guess; no exact offer or quote confirmed',
     'status': 'UNAPPROVED COMMERCIAL PROPOSAL',
     'basis': 'Discussion proposal based on the dated white DR2 £175 retail draft plus a provisional £25 finishing allowance,not measured production costing. The separately matched pale O009 £45 offer is not transferred to this reference or a new commission.',
     'source_refs': [rel(HERE.parent / 'component-review.json') + ':DR2-WHITE-PRICE']},
    {'proposal_id': vid + '-AVAILABILITY', 'field': 'Availability',
     'value': {'proposed_sale_policy': 'Made to order individually / enquire', 'physical_stock_quantity': None, 'manufacture_or_reproducibility_confirmed': False, 'production_capacity': None, 'lead_time': None},
     'display': 'Made to order individually / enquire — proposal; stock,reproducibility and lead time unknown',
     'status': 'UNAPPROVED SALE POLICY; PHYSICAL AVAILABILITY UNKNOWN',
     'basis': 'Solo and series images do not establish current stock,manufacture or reproducibility. No native stock4,InStock,SOLD or other version’s capacity is inherited. Made-to-order is a proposed policy requiring owner confirmation.',
     'source_refs': [rel(HERE / 'primary-original-reuse-check.json'), rel(HERE / 'series-download-receipts.json')]},
]
mapping = {'status': 'EXACT INDIVIDUAL SQUARESPACE/SHOPIFY OFFER UNCONFIRMED', 'squarespace_id': None,
    'shopify_handle': None, 'shared_sku': None, 'primary_file_id': file['id'], 'primary_folder_id': folder['id'],
    'related_source_candidate': {'offer_ref': 'O009', 'sku': 'SQ0059342', 'scope': 'Pale027listing already separately kept. Whether speckled005is another finish/stage/cast of it is unresolved; no binding inferred.'},
    'native_claims_not_transferred': ['35×21×6cm exact source applicability', '£45source price', 'native stock4', 'publicInStock'],
    'source_pale_identity_approval': rel(pale_approval), 'exact_mould_or_physical_cast_equivalence_confirmed': False,
    'native_platform_accounts_or_public_gallery_refreshed_this_turn': False}
coverage = {'complete_individual_front': True, 'detail_views_available': True, 'wall_mounted_front_reference': True,
    'series_arrangement_reference_available': True, 'series_reference_position': 'Centre spiral in a three-panel arrangement',
    'series_design_and_general_finish_appearance_compatible': True, 'exact_finish_and_same_physical_cast_verified': False,
    'dedicated_in_situ_folder_files': 0, 'confirmed_room_garden_or_client_installation_for_selected_reference': False,
    'candidate_rear_available': True, 'exact_rear_matched': False, 'physical_stock_inferred': False,
    'scope': 'Fresh complete42file census across4folders unchanged from previous verdigris audit. Prior42cached-image visual audit retained as dated evidence. Reused005individual original independently rehashed/current revision checked and viewed again; one complete3panel series original newly downloaded/hash verified/viewed. Rear015viewed again but remains unassigned; no all-folder,exact-cast,mould or stock equivalence inferred.'}
next_review = {'component_id': 'BC-DR-SPIRAL', 'review_number': 37, 'size_finish_variant_id': 'DR-SPIRAL-RUST',
               'family_review_number': 9, 'requires_exact_design_allocation_check': True}
review = {'schema_version': 1, 'prepared_utc': now, 'component_id': 'BC-DR-SPIRAL',
    'canonical_design_name': 'Dune Ripple Spiral — DR2', 'proposed_name': name, 'display_name': name, 'family': 'Dune Ripple',
    'review_number': 37, 'family_review_number': 8, 'family_review_total': 14, 'size_finish_variant_id': vid,
    'variant_only_review': True, 'review_decision_mode': 'SIZE_FINISH_VARIANT_NAME_AND_SPECIFICATIONS',
    'parent_identity_approval': rel(white_approval), 'prior_pale_identity_approval': rel(pale_approval),
    'parent_design_relationship_status': 'Separate appearance reference pending owner relationship check; not proof of another physical sculpture,mould or stock unit',
    'scope': 'Only selected speckled005depicted finish/name. Distinction from pale027orblue/bronze may be finish,photo processing,cast or production stage; relationship remains unresolved.',
    'primary_image_id': file['id'], 'primary_folder_id': folder['id'], 'primary_image_link': primary['copy_link_url'],
    'primary_folder_link': containing['copy_link_url'], 'metadata_checked_utc': meta['checked_utc'],
    'reference_refresh': rel(HERE / 'metadata-links.json'), 'primary_original_reuse_check': rel(HERE / 'primary-original-reuse-check.json'),
    'original_download_receipts': [rel(HERE / 'series-download-receipts.json')],
    'appearance_reference_clusters': rel(prior / 'appearance-reference-clusters.json'),
    'specification_review_items': items, 'platform_mapping': mapping, 'photo_coverage': coverage,
    'series_image_id': series[0]['id'], 'series_folder_id': 'id:cnqzTNngPVsAAAAAAAyiaQ',
    'series_image_link': links[series[0]['id']]['copy_link_url'], 'series_position': 'Centre panel in three-piece arrangement',
    'series_match_scope': 'Visual design and general verdigris/copper appearance compatible; exact finish/cast relationship unconfirmed',
    'candidate_rear_image_id': 'id:cnqzTNngPVsAAAAAAAye2Q', 'candidate_rear_image_link': links['id:cnqzTNngPVsAAAAAAAye2Q']['copy_link_url'],
    'identity_confirmed': False, 'specifications_approved': False, 'physical_specs_verified': False,
    'open_gaps': ['Owner name/depicted finish approval; exact relationship to pale027andblue/bronze references',
        'Actual height,width,maximum depth and dry weight', 'Actual binder,metal content,reinforcement,sealing,care and exterior suitability',
        'Exact rear,fixing attachment,hardware and load', 'Exact individual Squarespace/Shopify offer and sharedSKU',
        'Current price,physical stock,reproducibility,production capacity and lead time',
        'Same-cast/finish relationship in series; genuine client/room/garden installation provenance'],
    'source_conflicts': ['Related white35×20standard versus pale35×21listing applicability; no actual speckled measurements',
        'Same-folder pale,speckled and blue/bronze appearances are not physical inventory units',
        'The £45pale source offer is not an exact price/stock/finish match for this review'],
    'next_review_after_keep': next_review, 'next_global_component_id': 'BC-DR-WAVE3',
    'remote_files_changed': False, 'live_platform_records_changed': False}
write(out, review)
parent['size_finish_variants'][vid] = {'reviewed_utc': now, 'identity_confirmed': False, 'specifications_approved': False,
    'proposals_approved': False, 'physical_specs_verified': False, 'proposed_name': name, 'size_finish_variant_id': vid,
    'review_record': rel(out), 'primary_image_id': file['id'], 'primary_folder_id': folder['id'],
    'specification_proposals': copy.deepcopy(items), 'platform_mapping': mapping, 'photo_coverage': coverage,
    'parent_design_relationship_status': review['parent_design_relationship_status']}
for x in parent['pending_size_finish_variants']:
    if x['variant_id'] == vid:
        x.update({'review_status': 'AWAITING SPECKLED DEPICTED NAME; ALL SIX GUESSES PENDING', 'review_record': rel(out)})
progress['updated_utc'] = now
cp.update({'current_size_finish_variant_id': vid, 'proposed_name': name,
    'state': 'Awaiting speckled verdigris/copper spiral depicted name/identity; all six guesses and exact platform match pending',
    'primary_image': {'file_id': file['id'], 'name': file['name'], 'path_display': file['path_display'],
                      'copy_link_url': primary['copy_link_url'], 'open_in_dropbox_url': primary['open_in_dropbox_url']},
    'containing_folder': {'folder_id': folder['id'], 'name': folder['name'], 'path_display': folder['path_display'],
                          'copy_link_url': containing['copy_link_url'], 'open_in_dropbox_url': containing['open_in_dropbox_url']},
    'current_answer_recorded': False, 'current_specification_answer_recorded': False, 'current_dimension_answer_recorded': False,
    'working_version_user_approved': False, 'current_review_record': rel(out), 'review_decision_mode': review['review_decision_mode'],
    'current_family_review_number': 8, 'family_review_evidence': rel(HERE / 'metadata-links.json'),
    'answer_state': 'No answer yet. Named Keep approves selected speckled name/depicted identity only; no new physical inventory,mould,offer or specifications inferred.',
    'question_scope': 'Keep Dune Ripple Spiral—Verdigris and Copper for speckled005reference; all six working guesses remain separately pending.',
    'metadata_checked_utc': meta['checked_utc'], 'next_review_after_keep': next_review,
    'displayed_identity_evidence_file_ids': [file['id']], 'displayed_identity_evidence_folder_ids': [folder['id']],
    'current_component_source_notes': [x['display'] for x in items], 'updated_utc': now})
later = [('components/parallel-reviews/spiralmoon-2026-10-17/IMPORT_PACKAGE.json',
          '37766f259f1e083dd9478400938732c9d6d67aa0287ab5fa474af64fbc29cc75', 'REVIEW_IMPORT_PACKAGE'),
         ('components/parallel-reviews/fp-panels-2026-10-17/IMPORT_PACKAGE.json',
          '10988ca03fb9329d4d2ba98f1c1307783c41fe0915c1c51ff36a33123dcc5487', 'REVIEW_IMPORT_PACKAGE_WITH_PARTIAL_FIELD_APPROVALS')]
for path, expected, kind in later:
    assert sha(ROOT / path) == expected
    if not any(x['receipt'] == path for x in cp['parallel_import_queue']):
        cp['parallel_import_queue'].append({'component_id': None, 'variant_id': None, 'scope_kind': kind,
            'receipt': path, 'receipt_sha256': expected, 'status': 'SEALED AFTER BATCH3 CUTOFF; PENDING NEXT BOUNDED IMPORT',
            'approval_imported': False, 'recorded_utc': now,
            'scope': 'Packages overlap previous receipts. Independently verify exact owner turns,pre-answer snapshots and current references. Fingerprint contains separate face-size and conditional single-weight approvals; no full-six-field approval or physical manufacture inferred.'})
component['interactive_review_state'].update({'current_size_finish_variant_id': vid, 'current_name': name,
    'state': cp['state'], 'family_review_number': 8, 'specification_proposals_approved': False,
    'working_version_user_approved': False, 'review_decision_mode': review['review_decision_mode']})
component.update({'current_component_review_record': rel(out), 'parallel_import_queue': copy.deepcopy(cp['parallel_import_queue']), 'updated_utc': now})
component['last_family_media_review'] = {'family': 'Dune Ripple', 'finish': 'Speckled verdigris/copper spiral reference',
    'observed_utc': meta['checked_utc'], 'files': 42, 'folders': 4, 'scope': coverage['scope'],
    'evidence': rel(HERE / 'metadata-links.json'), 'workbook_contains_this_live_media_audit': False}
docs['root']['current_component_review'] = copy.deepcopy(component)
docs['root']['updated_utc'] = now
assert {k: v for k, v in parent.items() if k not in ['size_finish_variants', 'pending_size_finish_variants']} == parent_before
for key, value in old_variants.items():
    assert parent['size_finish_variants'][key] == value
for key, path in paths.items():
    write(path, docs[key])
assert all(sha(p) == value for p, value in hashes.items())
assert read(paths['root'])['current_component_review'] == read(paths['component'])
result = {'status': 'PASS', 'variant_id': vid, 'current_primary_revision_and_original_hashes_verified': True,
    'one_new_complete_series_original_hash_verified_and_viewed': True, 'complete42file_census_unchanged': True,
    'six_guesses_separate_from_pale_listing_claims': True, 'no_45GBP_SKU_or_stock_transfer': True,
    'pale_white_and_all_prior_owner_decisions_unchanged': True, 'source_model_workbook_and_ledger_unchanged': True,
    'rear_finish_cast_and_installation_provenance_not_inferred': True, 'later_packages_queued_not_imported': True,
    'remote_files_changed': False}
write(HERE / 'review-validation.json', result)
print(json.dumps(result))
