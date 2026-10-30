"""Prepare one blue/bronze plain-wave review without transferring other offers."""
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
    temporary = p.with_name(p.name + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(p)


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def rel(p):
    return str(p.relative_to(ROOT))


def verify_original(receipt):
    data = Path(receipt['local_path']).read_bytes()
    blocks = b''.join(hashlib.sha256(data[i:i + 4194304]).digest()
                      for i in range(0, len(data), 4194304))
    assert len(data) == receipt['size']
    assert hashlib.sha256(blocks).hexdigest() == receipt['content_hash'] == receipt['dropbox_content_hash_verified']
    assert hashlib.sha256(data).hexdigest() == receipt['sha256']


paths = {'walkthrough': REVIEWS / 'walkthrough_checkpoint.json',
         'progress': REVIEWS / 'specification_review_progress.json',
         'component': ROOT / 'components/checkpoint.json', 'root': ROOT / 'checkpoint.json'}
docs = {key: read(p) for key, p in paths.items()}
cp, progress, component = (docs[k] for k in ['walkthrough', 'progress', 'component'])
out = HERE / 'component-review.json'
if cp.get('current_review_record') == rel(out):
    print('ALREADY_PREPARED')
    raise SystemExit(0)
assert cp['current_component_id'] == 'BC-DR-WAVE1'
assert cp['current_size_finish_variant_id'] == 'DR-WAVES-VERDIGRIS-RUST' and cp['current_answer_recorded']
assert docs['root']['current_component_review'] == component
prior = HERE.parent / 'verdigris-rust'
white_approval = HERE.parent / 'identity-approval.json'
approval = read(prior / 'identity-approval.json')
assert approval['user_statement'] == 'Keep “Dune Ripple Waves — Verdigris and Rust”'
assert approval['identity_confirmed'] and not approval['specifications_approved']
protected = [ROOT / 'components/evidence/component_register.json', ROOT / cp['register_workbook'],
             REVIEWS / 'user_classifications.json', white_approval,
             prior / 'component-review.json', prior / 'identity-approval.json']
hashes = {p: sha(p) for p in protected}
user = read(REVIEWS / 'user_classifications.json')
assert user['specification_approval_counts']['proposal_groups'] == 61
parent = progress['reviews']['BC-DR-WAVE1']
protected_parent = {k: copy.deepcopy(v) for k, v in parent.items()
                    if k not in ['size_finish_variants', 'pending_size_finish_variants']}
old_variants = copy.deepcopy(parent['size_finish_variants'])
now = datetime.now(timezone.utc).isoformat()
write(HERE / 'before-blue-verdigris-review.json',
      {'recorded_utc': now, 'files': {rel(paths[k]): value for k, value in docs.items()},
       'protected_sha256': {rel(p): value for p, value in hashes.items()}})

meta = read(HERE / 'metadata-links.json')
file = meta['primary_metadata']['file']
folder = meta['folder_metadata']['folder']
assert file['id'] == 'id:cnqzTNngPVsAAAAAAAykuA'
assert folder['id'] == 'id:cnqzTNngPVsAAAAAAAyiYg'
assert file['path_display'].rsplit('/', 1)[0] == folder['path_display']
previous = read(prior / 'metadata-links.json')
for key, listing in meta['listings'].items():
    assert not listing['has_more'] and not listing['cursor']
    assert {x['file_id']: x for x in listing['entries']} == {
        x['file_id']: x for x in previous['listings'][key]['entries']}
assert sum(len(x['entries']) for x in meta['listings'].values()) == 78
originals = read(HERE / 'download-receipts.json')
context = read(HERE / 'context-download-receipts.json')
assert len(originals) == 1 and len(context) == 3
for receipt in originals + context:
    verify_original(receipt)
assert originals[0]['id'] == file['id'] and originals[0]['size'] == file['size']
alternate = next(x for x in read(HERE.parent / 'verdigris/download-receipts.json')
                 if x['id'] == 'id:cnqzTNngPVsAAAAAAAyg_Q')
verify_original(alternate)
old_meta = read(HERE.parent / 'verdigris/metadata-initial.json')
old_alt = next(x for x in old_meta['listings']['solo']['entries']
               if x['file_id'] == alternate['id'])
assert meta['alternate_metadata']['file']['size'] == alternate['size'] == old_alt['file']['size']
write(HERE / 'alternate-original-reuse-check.json',
      {'status': 'PASS', 'checked_utc': now, 'current_metadata': meta['alternate_metadata'],
       'original_receipt': alternate, 'scope': 'Existing original hash recalculated and viewed again; exact same cast or mould across references remains unconfirmed.'})
public_candidate = read(HERE / 'O009-candidate-image-receipt.json')
assert public_candidate['status'] == 'PASS'
assert sha(Path(public_candidate['local_path'])) == public_candidate['sha256']

links = {x['file_name']: x for x in meta['previews']}
folder_links = {x['file_name']: x for x in meta['context_folder_previews']}
primary, containing = links[file['id']], links[folder['id']]
vid = 'DR-WAVES-BLUE-VERDIGRIS'
name = 'Dune Ripple Waves — Blue Verdigris and Bronze'
standard = 'manufacture-stevensons:Sheet1!row54; related white standard only'
items = [
    {'proposal_id': vid + '-DIMENSIONS', 'field': 'Individual dimensions and depth',
     'value': {'proposed_dimensions_cm': [35, 20, 6], 'related_side_depth_range_cm': [5, 7], 'actual_measured_dimensions_cm': None},
     'display': 'Approximately 35 H × 20 W × 6 D cm — guess; actual panel unmeasured',
     'status': 'UNAPPROVED GUESS FROM RELATED STANDARD; EXACT MOULD UNCONFIRMED',
     'basis': 'Use related white DR1 35×20 cm face and 5–7 cm side depth only as an analogy. Photographs provide no reliable scale. Do not treat this as owner size approval, transfer another finish’s measurements or settle DR1/DR3 allocation.',
     'source_refs': [standard]},
    {'proposal_id': vid + '-WEIGHT', 'field': 'Individual dry weight',
     'value': {'proposed_weight_kg': 4, 'working_estimate_range_kg': [3, 5], 'actual_weighed_kg': None},
     'display': 'Approximately 4 kg (working range 3–5 kg) — guess; not weighed',
     'status': 'UNAPPROVED ANALOGY ESTIMATE; NOT A MEASURED OR STATISTICAL INTERVAL',
     'basis': 'Related white maker standard calculates 3–5 kg. Actual binder, thickness, cavity and reinforcement are unknown. Do not transfer O038’s 5000 g product claim or divide an arrangement weight.',
     'source_refs': [standard]},
    {'proposal_id': vid + '-MATERIAL', 'field': 'Material and finish',
     'value': {'proposed_substrate': 'Cast mineral composite', 'visual_finish_description': 'Blue-green verdigris appearance with bronze/copper-coloured ridge highlights', 'actual_binder': None, 'actual_metal_content': None, 'actual_reinforcement': None, 'actual_sealing': None},
     'display': 'Cast mineral composite with blue-green patina and bronze-effect ridges — guess; binder and metal content unknown',
     'status': 'UNAPPROVED MATERIAL GUESS AND VISUAL FINISH DESCRIPTION',
     'basis': 'The downloaded individual original shows a blue-green textured surface and brown metallic-coloured ridges. Appearance does not identify actual bronze/copper, AC730 or plaster. Related white AC730 and other finish descriptions remain analogies.',
     'source_refs': [rel(HERE / 'download-receipts.json'), standard]},
    {'proposal_id': vid + '-FIXING', 'field': 'Fixing',
     'value': {'proposed_hanging_points': 1, 'proposed_type': 'Concealed rear fixing, probably keyhole', 'verified_rear_image_file_id': None, 'actual_hardware': None, 'attachment': None, 'rated_load': None},
     'display': 'One concealed rear fixing, probably keyhole — guess; exact rear and hardware unconfirmed',
     'status': 'UNAPPROVED ANALOGY; NO EXACT FRONT TO BACK MATCH',
     'basis': 'One rear fixing appears in related maker instructions and related backs show keyhole plates. No particular back is matched to this selected front. Do not certify material, position, attachment, wall suitability or load.',
     'source_refs': [standard, rel(HERE.parent / 'verdigris/rear-download-receipts.json')]},
    {'proposal_id': vid + '-PRICE', 'field': 'Individual retail price',
     'value': {'proposed_amount': 250, 'currency': 'GBP', 'sale_unit': 'One depicted blue/bronze wave panel', 'exact_existing_individual_offer_confirmed': False, 'owner_price_approval': False},
     'display': '£250 per individual panel — working price guess; no exact offer or new quote confirmed',
     'status': 'UNAPPROVED COMMERCIAL PROPOSAL; NOT AN EXISTING MATCHED PRICE',
     'basis': 'A discussion proposal using the separately identified metallic rust-patched O038 work’s £250 reference and the related white £175 draft. This does not transfer O038’s offer, SOLD status or price entitlement. The £45 O004 muted panel and O009 spiral are different scoped records.',
     'source_refs': [rel(prior / 'component-review.json'), rel(HERE.parent / 'component-review.json')]},
    {'proposal_id': vid + '-AVAILABILITY', 'field': 'Availability',
     'value': {'proposed_sale_policy': 'Made to order individually / enquire', 'physical_stock_quantity': None, 'manufacture_or_reproducibility_confirmed': False, 'production_capacity': None, 'lead_time': None},
     'display': 'Made to order individually / enquire — proposal; stock, reproducibility and lead time unknown',
     'status': 'UNAPPROVED SALE POLICY; NOT PHYSICAL AVAILABILITY',
     'basis': 'Individual, series and context images do not establish that this version is currently manufactured, reproducible or in stock. No stock or SOLD status is transferred from a differently finished source offer.',
     'source_refs': [rel(HERE / 'download-receipts.json'), rel(HERE / 'context-download-receipts.json')]},
]
model = read(ROOT / 'components/evidence/component_register.json')
offers = [x for x in model['platform_records'] if x['offer_ref'] in ['O004', 'O009', 'O038', 'O052']]
mapping = {'status': 'EXACT INDIVIDUAL PLATFORM OFFER UNCONFIRMED', 'squarespace_id': None,
           'shopify_handle': None, 'shared_sku': None, 'primary_file_id': file['id'],
           'primary_folder_id': folder['id'], 'native_offers_checked': [x['offer_ref'] for x in offers],
           'excluded_or_separately_scoped': {'O004': 'Muted green individual already reviewed separately',
               'O038': 'Bright rust-patched individual already kept separately',
               'O009': 'Current primary original visually checked: spiral panel, not this plain-wave panel',
               'O052': 'Copper spiral source; not this blue-green plain-wave finish'},
           'live_platform_admins_refreshed': False, 'mould_DR1_DR3_equivalence_confirmed': False}
coverage = {'complete_individual_front': True, 'alternate_individual_view': True,
            'series_arrangement_image_available': True, 'indoor_context_image_available': True,
            'garden_series_context_image_available': True, 'exact_rear_matched': False,
            'verified_client_installation_provenance': False,
            'same_physical_cast_across_images_verified': False,
            'exact_mould_identity_across_images_verified': False,
            'physical_stock_inferred': False,
            'scope': 'Fresh complete 78-file census across five folders unchanged from previous audit. One individual and three series/context originals downloaded, hash verified and viewed; alternate 014 original hash rechecked and viewed. Series wave at right, garden wave at left. Images depict compatible blue/bronze plain-wave references; exact cast, mould and genuine installation provenance remain unconfirmed.'}
context_items = []
folder_by_path = {x['folder']['path_display']: x['folder']['id'] for x in meta['context_folder_metadata']}
for receipt in context:
    fid = folder_by_path[receipt['path_display'].rsplit('/', 1)[0]]
    context_items.append({'file_id': receipt['id'], 'folder_id': fid,
                          'image_link': links[receipt['id']]['copy_link_url'],
                          'folder_link': folder_links[fid]['copy_link_url'],
                          'role': {'id:cnqzTNngPVsAAAAAAAykug': 'Series reference; selected plain-wave design at right',
                                   'id:cnqzTNngPVsAAAAAAAyg_g': 'Single-panel room context reference; installation provenance unconfirmed',
                                   'id:cnqzTNngPVsAAAAAAAykxw': 'Garden series context reference; wave at left; provenance unconfirmed'}[receipt['id']]})
next_review = {'component_id': 'BC-DR-SPIRAL', 'review_number': 37,
               'size_finish_variant_id': 'DR2-WHITE', 'family_review_number': 6,
               'requires_bounded_serialized_parallel_import_before_preparation': True}
review = {'schema_version': 1, 'prepared_utc': now, 'component_id': 'BC-DR-WAVE1',
          'canonical_design_name': 'Dune Ripple Waves', 'proposed_name': name, 'display_name': name,
          'family': 'Dune Ripple', 'review_number': 36, 'family_review_number': 5,
          'family_review_total': 13, 'size_finish_variant_id': vid, 'variant_only_review': True,
          'review_decision_mode': 'SIZE_FINISH_VARIANT_NAME_AND_SPECIFICATIONS',
          'parent_identity_approval': rel(white_approval),
          'parent_design_relationship_status': 'Organizational component bucket only; exact coloured-wave mould, DR1/DR3 allocation and cast equivalence remain provisional',
          'scope': 'Selected blue-green plain-wave design with bronze-coloured ridge highlights. Keep depicts name/identity only; colour words do not certify actual metal, manufacture, mould or physical stock.',
          'primary_image_id': file['id'], 'primary_folder_id': folder['id'],
          'primary_image_link': primary['copy_link_url'], 'primary_folder_link': containing['copy_link_url'],
          'metadata_checked_utc': meta['checked_utc'], 'reference_refresh': rel(HERE / 'metadata-links.json'),
          'original_download_receipts': [rel(HERE / 'download-receipts.json'), rel(HERE / 'context-download-receipts.json')],
          'alternate_original_reuse_check': rel(HERE / 'alternate-original-reuse-check.json'),
          'advisory_preparation': rel(HERE.parent / 'advisory-packet-used.json'),
          'public_candidate_source_evidence': rel(HERE / 'candidate-public-web-evidence.json'),
          'excluded_O009_original_receipt': rel(HERE / 'O009-candidate-image-receipt.json'),
          'specification_review_items': items, 'platform_mapping': mapping, 'source_offer_snapshots': offers,
          'photo_coverage': coverage, 'context_images': context_items,
          'identity_confirmed': False, 'specifications_approved': False, 'physical_specs_verified': False,
          'source_conflicts': ['Related 35×20 maker standard versus other 35×21 finish listings; neither measures this cast',
              'Wave-relief title of O009 versus its spiral image; no plain-wave match inferred',
              'Visually compatible series/context versus unconfirmed exact geometry, mould, cast and installation provenance'],
          'open_gaps': ['Owner name/depicted design confirmation', 'Actual height,width,depth and dry weight',
              'Binder, actual metal content, reinforcement, sealing, care and exterior suitability',
              'Exact matching rear, fixing attachment and hardware/load', 'Exact Squarespace and Shopify offer/shared SKU',
              'Current individual price, physical manufacture, stock, capacity and lead time',
              'Series/context provenance, same-cast relation and DR1/DR3 mould allocation'],
          'next_review_after_keep': next_review, 'next_global_component_id': 'BC-DR-SPIRAL',
          'remote_files_changed': False, 'live_platform_records_changed': False}
write(out, review)
parent['size_finish_variants'][vid] = {'reviewed_utc': now, 'identity_confirmed': False,
    'specifications_approved': False, 'proposals_approved': False, 'physical_specs_verified': False,
    'proposed_name': name, 'size_finish_variant_id': vid, 'review_record': rel(out),
    'primary_image_id': file['id'], 'primary_folder_id': folder['id'],
    'specification_proposals': copy.deepcopy(items), 'platform_mapping': copy.deepcopy(mapping),
    'photo_coverage': copy.deepcopy(coverage), 'parent_design_relationship_status': review['parent_design_relationship_status']}
for pending in parent['pending_size_finish_variants']:
    if pending['variant_id'] == vid:
        pending.update({'review_status': 'AWAITING BLUE/BRONZE DEPICTED NAME; SIX GUESSES PENDING', 'review_record': rel(out)})
progress['updated_utc'] = now
cp.update({'current_size_finish_variant_id': vid, 'proposed_name': name,
    'state': 'Awaiting blue/bronze wave name and depicted identity; six guesses and exact platform offer remain unconfirmed',
    'primary_image': {'file_id': file['id'], 'name': file['name'], 'path_display': file['path_display'],
                      'copy_link_url': primary['copy_link_url'], 'open_in_dropbox_url': primary['open_in_dropbox_url']},
    'containing_folder': {'folder_id': folder['id'], 'name': folder['name'], 'path_display': folder['path_display'],
                          'copy_link_url': containing['copy_link_url'], 'open_in_dropbox_url': containing['open_in_dropbox_url']},
    'current_answer_recorded': False, 'current_specification_answer_recorded': False,
    'current_dimension_answer_recorded': False, 'working_version_user_approved': False,
    'current_review_record': rel(out), 'review_decision_mode': review['review_decision_mode'],
    'current_family_review_number': 5, 'family_review_evidence': rel(HERE / 'metadata-links.json'),
    'answer_state': 'No answer yet. Named Keep approves depicted name/identity only; all six working guesses remain pending.',
    'question_scope': 'Keep the selected blue-green plain-wave name and depicted identity; no exact mould, physical cast or platform equivalence inferred.',
    'metadata_checked_utc': meta['checked_utc'], 'next_review_after_keep': next_review,
    'displayed_identity_evidence_file_ids': [file['id']], 'displayed_identity_evidence_folder_ids': [folder['id']],
    'current_component_source_notes': [x['display'] for x in items], 'updated_utc': now})
cp['review_policy']['active_family_priority'] = 'Dune Ripple'

# Receive isolated peer artifacts only. Import waits for the explicit bounded checkpoint.
later = [
    (None, 'REVIEW_IMPORT_PACKAGE', 'components/parallel-reviews/spice-spiralfish-2026-10-17/IMPORT_PACKAGE.json'),
    ('BC-FP-LEFT', 'DEPICTED_DESIGN_NAME_ONLY_RECEIPT', 'components/parallel-reviews/fp-panels-2026-10-17/left-verdigris/identity-approval.json'),
    ('BC-FP-LEFT', 'OWNER_FACE_DIMENSION_RECEIPT_PENDING_TRANSCRIPT_CHECK', 'components/parallel-reviews/fp-panels-2026-10-17/left-verdigris/owner-face-dimensions.json')]
for cid, kind, receipt_path in later:
    if (ROOT / receipt_path).is_file() and not any(x['receipt'] == receipt_path for x in cp['parallel_import_queue']):
        cp['parallel_import_queue'].append({'component_id': cid, 'variant_id': None, 'receipt': receipt_path,
            'receipt_sha256': sha(ROOT / receipt_path), 'scope_kind': kind,
            'status': 'RECEIVED ONLY; PENDING NEXT BOUNDED SERIALIZED IMPORT', 'approval_imported': False,
            'recorded_utc': now, 'scope': 'Exact owner transcript, pre-answer card and current references require independent verification. No additional approvals inferred. Pair/detail-only photo gaps and provisional dimension units remain explicit.'})

# Continue the already authorized, existing peer lane with a free disjoint family.
session = '01a13fe6-495b-7253-b923-31823b4cbca8'
ack_path = ROOT / 'components/parallel-reviews/spiralmoon-2026-10-17/COORDINATOR_ACKNOWLEDGEMENT.json'
assert not ack_path.exists()
reservation = []
for cid, number in [('BC-SM-SPIRAL', 115), ('BC-SM-QUARTER', 116)]:
    assert cp['review_order'][number - 1] == cid
    assert not any(x['component_id'] == cid for x in cp['parallel_owner_reviews'])
    reservation.append({'component_id': cid, 'review_number': number, 'owner_session': session,
        'coordinator_acknowledgement': rel(ack_path), 'status': 'RESERVED FOR PARALLEL OWNER REVIEW; EXACT RECEIPTS REQUIRED FOR IMPORT',
        'approval_inferred': False, 'acknowledged_utc': now})
ack_path.parent.mkdir(parents=True, exist_ok=True)
write(ack_path, {'recorded_utc': now, 'reservation': reservation,
    'scope': 'Existing explicitly authorized peer lane after reserved112–114 first-pass package. Spiralmoon115–116 all finishes only. Main alone writes shared overlays/workbook. Isolated receipts; individual Dropbox image/folder plus six source-or-guess fields. Preserve incomplete images, design/manufacture uncertainty, and exact owner scope. No remote mutations.'})
cp['parallel_owner_reviews'].extend(reservation)
component['interactive_review_state'].update({'current_component_id': 'BC-DR-WAVE1', 'review_number': 36,
    'current_size_finish_variant_id': vid, 'current_name': name, 'state': cp['state'], 'active_family': 'Dune Ripple',
    'family_review_number': 5, 'family_review_total': 13, 'specification_proposals_approved': False,
    'working_version_user_approved': False, 'review_decision_mode': review['review_decision_mode']})
component['review_policy']['active_family_priority'] = 'Dune Ripple'
component['current_component_review_record'] = rel(out)
component['parallel_import_queue'] = copy.deepcopy(cp['parallel_import_queue'])
component['parallel_owner_reviews'] = copy.deepcopy(cp['parallel_owner_reviews'])
component['updated_utc'] = now
component['last_family_media_review'] = {'family': 'Dune Ripple', 'finish': 'Blue verdigris and bronze-coloured wave',
    'observed_utc': meta['checked_utc'], 'files': 78, 'folders': 5, 'scope': coverage['scope'],
    'evidence': rel(HERE / 'metadata-links.json'), 'workbook_contains_this_live_media_audit': False}
docs['root']['current_component_review'] = copy.deepcopy(component)
docs['root']['updated_utc'] = now
assert {k: v for k, v in parent.items() if k not in ['size_finish_variants', 'pending_size_finish_variants']} == protected_parent
for key, value in old_variants.items():
    assert parent['size_finish_variants'][key] == value
for key, p in paths.items():
    write(p, docs[key])
assert all(sha(p) == value for p, value in hashes.items())
assert read(paths['root'])['current_component_review'] == read(paths['component'])
assert read(paths['walkthrough'])['parallel_owner_reviews'] == read(paths['component'])['parallel_owner_reviews']
result = {'status': 'PASS', 'variant_id': vid, 'primary_and_three_context_originals_hash_verified_and_viewed': True,
          'alternate_original_hash_rechecked_and_viewed': True, 'complete78file_census_unchanged': True,
          'O009_primary_image_checked_and_excluded_as_spiral': True,
          'exact_platform_offer_unconfirmed': True, 'six_unapproved_working_specification_groups': len(items),
          'prior_names_and_specification_approvals_preserved': True, 'approved_groups_unchanged': 61,
          'model_workbook_classification_hashes_unchanged': True, 'root_and_component_checkpoints_identical': True,
          'existing_peer_lane_disjoint115_116_acknowledged': True,
          'no_physical_mould_stock_or_installation_provenance_inferred': True, 'remote_files_changed': False}
write(HERE / 'review-validation.json', result)
print(json.dumps(result))
