"""Prepare the white DR2 individual after the verified bounded peer import."""
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REVIEWS = ROOT / 'components/reviews'


def read(p):
    return json.loads(p.read_text())


def write(p, value):
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
assert cp['current_component_id'] == 'BC-DR-WAVE1' and cp['current_size_finish_variant_id'] == 'DR-WAVES-BLUE-VERDIGRIS' and cp['current_answer_recorded']
assert docs['root']['current_component_review'] == component
assert cp['next_serialized_parallel_import']['status'] == 'APPLIED_AND_VERIFIED'
assert read(ROOT / cp['next_serialized_parallel_import']['receipt'])['identity_receipts'] == 13
assert read(ROOT / 'components/reviews/parallel-import-2026-10-17-batch3/independent-readback.json')['status'] == 'PASS'
prior_approval = ROOT / cp['last_identity_approval']
assert read(prior_approval)['user_statement'] == 'Keep “Dune Ripple Waves — Blue Verdigris and Bronze”'
assert not read(prior_approval)['specifications_approved']
protected = [ROOT / 'components/evidence/component_register.json', ROOT / cp['register_workbook'],
             REVIEWS / 'user_classifications.json', ROOT / cp['current_review_record'], prior_approval]
hashes = {p: sha(p) for p in protected}
old_reviews = copy.deepcopy(progress['reviews'])
now = datetime.now(timezone.utc).isoformat()
write(HERE / 'before-white-spiral-review.json', {'recorded_utc': now, 'files': {rel(paths[k]): v for k, v in docs.items()},
      'protected_sha256': {rel(p): value for p, value in hashes.items()}})
meta = read(HERE / 'metadata-links.json')
file, folder = meta['primary_metadata']['file'], meta['folder_metadata']['folder']
assert file['id'] == 'id:cnqzTNngPVsAAAAAAAykwA' and folder['id'] == 'id:cnqzTNngPVsAAAAAAAyiaA'
assert file['path_display'].rsplit('/', 1)[0] == folder['path_display']
assert {k: len(v['entries']) for k, v in meta['listings'].items()} == {'solo': 9, 'solo_context': 0, 'series': 23, 'series_context': 7}
assert all(not v['has_more'] and not v['cursor'] for v in meta['listings'].values())
receipt = read(HERE / 'download-receipts.json')[0]
data = Path(receipt['local_path']).read_bytes()
assert len(data) == file['size'] == receipt['size'] and hashlib.sha256(data).hexdigest() == receipt['sha256']
dbhash = hashlib.sha256(b''.join(hashlib.sha256(data[i:i + 4194304]).digest() for i in range(0, len(data), 4194304))).hexdigest()
assert dbhash == receipt['content_hash'] == receipt['dropbox_content_hash_verified']
assert read(HERE / 'series-original-reuse-check.json')['status'] == 'PASS'
links = {x['file_name']: x for x in meta['previews']}
primary, containing = links[file['id']], links[folder['id']]
model = read(ROOT / 'components/evidence/component_register.json')
maker = [x for x in model['claims'] if x.get('component_id') == 'BC-DR-SPIRAL' and 'manufacture-stevensons:Sheet1!row55/' in x.get('source_ref', '')]
assert len(maker) == 5
label_path = Path('/Users/tprice/Library/Application Support/BoldstoneImageConsistency/product-evidence-resolution-20261016T201618Z/Manufacturing_Labelled_References.json')
label = next(x for x in read(label_path) if x['row'] == 55)
assert label['code'] == 'DR2-35x20'
vid, name = 'DR2-WHITE', 'Dune Ripple Spiral — White (DR2)'
standard = 'manufacture-stevensons:Sheet1!row55'
items = [
    {'proposal_id': vid + '-DIMENSIONS', 'field': 'Individual dimensions and depth',
     'value': {'source_face_height_cm': 35, 'source_face_width_cm': 20, 'source_side_depth_range_cm': [5, 7], 'actual_measured_dimensions_cm': None},
     'display': 'Approximately 35 H × 20 W × 5–7 D cm — historical maker standard; actual panel unmeasured',
     'status': 'HISTORICAL WHITE DR2 STANDARD; CURRENT CAST APPLICABILITY UNVERIFIED',
     'basis': 'Maker row55 gives approximately350×200mm with side measurement50–70mm. Coloured35×21×6cm and gold35×20×5cm are other scoped source versions; no photo-based measurement or silent harmonization.', 'source_refs': [standard]},
    {'proposal_id': vid + '-WEIGHT', 'field': 'Individual dry weight',
     'value': {'maker_calculated_range_kg': [3, 5], 'dated_individual_estimates_kg': [4.5, 5], 'actual_weighed_kg': None},
     'display': 'Approximately 3–5 kg — maker calculated estimate; not weighed',
     'status': 'HISTORICAL CALCULATED ESTIMATE; NOT ACTUAL WEIGHING',
     'basis': 'Maker row55 calculates3–5kg for the white standard. Dated drafts estimate4.5or5kg. Gold and other coloured native product claims remain separate; arrangement weights are not divided.',
     'source_refs': [standard, rel(HERE / 'advisory-packet-used.json') + ':specifications.weight']},
    {'proposal_id': vid + '-MATERIAL', 'field': 'Material and finish',
     'value': {'historical_standard_substrate': 'Jesmonite AC730', 'historical_standard_finish': 'White marble stone finish', 'actual_binder': None, 'reinforcement': None, 'sealing': None},
     'display': 'Jesmonite AC730, white marble stone finish — historical maker specification; exact cast unconfirmed',
     'status': 'SOURCE STANDARD; PICTURED CAST COMPOSITION UNVERIFIED',
     'basis': 'Maker row55 explicitly specifies White Marble Stone Finish Jesmonite AC730. White appearance alone does not confirm composition. Two warm/gold-coloured detail views in this folder are not proof of gold leaf, a separate manufactured version or the same white cast.', 'source_refs': [standard]},
    {'proposal_id': vid + '-FIXING', 'field': 'Fixing',
     'value': {'historical_hanging_points': 1, 'historical_material': 'Stainless steel', 'historical_position': 'Centre rear in upper third', 'actual_hardware': None, 'attachment': None, 'rated_load': None},
     'display': 'One small stainless-steel rear fixing, centre back in upper third — maker instruction; hardware unverified',
     'status': 'HISTORICAL SOURCE INSTRUCTION; EXACT REAR AND LOAD UNVERIFIED',
     'basis': 'Row55 specifies one small stainless fixing aligned at the same height as other series pieces. No matching rear was identified among the9solo and previously reviewed30shared white views. No exact fixing type or load rating is certified.', 'source_refs': [standard]},
    {'proposal_id': vid + '-PRICE', 'field': 'Individual retail price',
     'value': {'proposed_amount': 175, 'currency': 'GBP', 'sale_unit': 'One selected white DR2 panel', 'dated_white_retail_references_gbp': [146.09, 175], 'dated_trade_reference_gbp': 87, 'current_exact_white_offer_confirmed': False},
     'display': '£175 per individual white panel — proposed from the 2025 retail draft',
     'status': 'UNAPPROVED WORKING PRICE; NOT A CURRENT MATCHED OFFER',
     'basis': 'Named2025retail draft gives175each, within the prepared170–220discussion range. Earlier146.09retail and87trade are separately dated price classes. Do not transfer coloured gold,verdigris,copper or rust prices to this white panel.',
     'source_refs': [rel(HERE / 'advisory-packet-used.json') + ':specifications.individual_price']},
    {'proposal_id': vid + '-AVAILABILITY', 'field': 'Availability',
     'value': {'proposed_sale_policy': 'Made to order individually / enquire', 'physical_stock_quantity': None, 'production_capacity': None, 'lead_time': None},
     'display': 'Made to order individually / enquire — proposal; stock and lead time unknown',
     'status': 'UNAPPROVED SALE POLICY; PHYSICAL AVAILABILITY UNKNOWN',
     'basis': 'Source instructions and photographs do not establish current finished inventory, reproducibility or production lead time. Repeated panels in a room image do not prove multiple physical stock units.',
     'source_refs': [rel(HERE / 'advisory-packet-used.json') + ':specifications.availability']},
]
related = [x for x in model['platform_records'] if x['offer_ref'] in ['O002', 'O009', 'O039', 'O052', 'O068']]
mapping = {'scope': 'Selected white DR2 individual only', 'squarespace_id': None, 'shopify_handle': None, 'shared_sku': None,
    'individual_offer_confirmed': False, 'status': 'EXACT WHITE INDIVIDUAL OFFER UNCONFIRMED IN REVIEWED EXPORTS',
    'related_coloured_offer_refs': [x['offer_ref'] for x in related],
    'related_unique_platform_pair': {'offer_ref': 'O039', 'squarespace_id': '6a555a777b54f252fef707d4',
        'shopify_handle': 'golden-spiral-dune-ripple', 'shared_sku': 'GDRS-1-35.20',
        'scope': 'Gold individual source only; not transferred to the white panel'},
    'related_prices_are_dated_source_snapshots': True, 'live_platform_admins_refreshed': False}
coverage = {'complete_individual_front': True, 'detail': True, 'series_arrangement': True, 'room_context_in_series': True,
    'standalone_white_in_situ_folder_files': 0, 'confirmed_standalone_client_installation': False,
    'exact_rear_matched': False, 'installation_provenance': 'UNCONFIRMED', 'physical_stock_inferred': False,
    'series_position': 'Centre in selected three-panel reference',
    'room_position': 'Spiral design repeated at positions2and4in the selected four-panel room context; not a physical inventory count',
    'solo_folder_colour_ambiguity': 'Two warm/gold-coloured closeups remain ambiguous; do not assume all9files are one white cast or certified gold finish',
    'scope': 'Fresh complete39file census:9solo,0standalonecontext,23series,7seriescontext. All9solo cached thumbnails viewed this turn. The30shared series/context entries are unchanged from the previous complete white audit and retain dated visual review. One primary original newly downloaded/hash verified; two previous complete series/room originals rehashed and viewed again. Other36originals not downloaded in this turn.'}
next_review = {'component_id': 'BC-DR-SPIRAL', 'review_number': 37, 'size_finish_variant_id': 'DR-SPIRAL-VERDIGRIS',
               'family_review_number': 7, 'requires_exact_design_allocation_check': True}
review = {'schema_version': 1, 'prepared_utc': now, 'component_id': 'BC-DR-SPIRAL',
    'canonical_design_name': 'Dune Ripple Spiral — DR2', 'proposed_name': name, 'display_name': name,
    'family': 'Dune Ripple', 'maker_code': 'DR2-35x20', 'review_number': 37,
    'family_review_number': 6, 'family_review_total': 13, 'size_finish_variant_id': vid, 'variant_only_review': False,
    'review_decision_mode': 'COMPONENT_NAME_AND_SPECIFICATIONS',
    'scope': 'One depicted white panel with two spiral curls. Named Keep confirms this depicted name/identity only. Maker association remains source-assisted; other finishes and physical casts are reviewed separately.',
    'primary_image_id': file['id'], 'primary_folder_id': folder['id'], 'primary_image_link': primary['copy_link_url'],
    'primary_folder_link': containing['copy_link_url'], 'metadata_checked_utc': meta['checked_utc'],
    'reference_refresh': rel(HERE / 'metadata-links.json'), 'primary_original_receipts': rel(HERE / 'download-receipts.json'),
    'series_original_reuse_check': rel(HERE / 'series-original-reuse-check.json'),
    'image_review_index': rel(HERE / 'image-review-index.json'), 'maker_claims': maker, 'maker_labelled_reference': label,
    'maker_labelled_reference_source': str(label_path), 'maker_design_association': 'PROVISIONAL SOURCE-ASSISTED DR2 ASSOCIATION; labelled small reference compared with full primary',
    'advisory_preparation': rel(HERE / 'advisory-packet-used.json'), 'specification_review_items': items,
    'platform_mapping': mapping, 'related_coloured_offer_snapshots': related, 'photo_coverage': coverage,
    'series_image_id': 'id:cnqzTNngPVsAAAAAAAykvw', 'series_folder_id': 'id:cnqzTNngPVsAAAAAAAyiag',
    'series_image_link': links['id:cnqzTNngPVsAAAAAAAykvw']['copy_link_url'], 'series_position': 'Centre panel',
    'room_context_image_id': 'id:cnqzTNngPVsAAAAAAAykvA',
    'room_context_image_link': links['id:cnqzTNngPVsAAAAAAAykvA']['copy_link_url'],
    'identity_confirmed': False, 'specifications_approved': False, 'physical_specs_verified': False,
    'open_gaps': ['Confirm depicted white name/identity and DR2maker association', 'Actual dimensions/maximumprojection and dry weight',
        'Actual binder,reinforcement,sealing,care and exterior suitability', 'Exact rear,fixing attachment,wall hardware and load',
        'Current individual175GBPprice approval,production readiness,stock and lead time',
        'Exact white Squarespace/Shopify individual offer/sharedSKU', 'Standalone actual installation photograph and provenance',
        'Ambiguous warm-colour details and physical cast relationships; no wholesale folder identity'],
    'next_review_after_keep': next_review, 'next_global_component_id': 'BC-DR-WAVE3',
    'remote_files_changed': False, 'live_platform_records_changed': False}
write(out, review)
assert 'BC-DR-SPIRAL' not in progress['reviews']
pending = [x for x in cp['family_review_order'] if x['component_id'] == 'BC-DR-SPIRAL' and x['variant_id'] != vid]
progress['reviews']['BC-DR-SPIRAL'] = {'reviewed_utc': now, 'identity_confirmed': False, 'specifications_approved': False,
    'physical_specs_verified': False, 'proposed_name': name, 'size_finish_variant_id': vid,
    'specification_proposals': copy.deepcopy(items), 'source_specifications_recorded': True, 'maker_claims': maker,
    'platform_mapping': mapping, 'primary_image_id': file['id'], 'primary_folder_id': folder['id'],
    'review_record': rel(out), 'photo_coverage': coverage, 'gaps': review['open_gaps'],
    'pending_size_finish_variants': [{'variant_id': x['variant_id'], 'status': 'AWAITING INDIVIDUAL FINISH/IDENTITY REVIEW'} for x in pending]}
progress['updated_utc'] = now
cp.update({'current_component_id': 'BC-DR-SPIRAL', 'current_review_number': 37, 'current_size_finish_variant_id': vid,
    'proposed_name': name, 'state': 'Awaiting individual white DR2 spiral name/identity; six source/working specification groups remain open',
    'primary_image': {'file_id': file['id'], 'name': file['name'], 'path_display': file['path_display'],
                      'copy_link_url': primary['copy_link_url'], 'open_in_dropbox_url': primary['open_in_dropbox_url']},
    'containing_folder': {'folder_id': folder['id'], 'name': folder['name'], 'path_display': folder['path_display'],
                          'copy_link_url': containing['copy_link_url'], 'open_in_dropbox_url': containing['open_in_dropbox_url']},
    'answer_state': 'No answer yet. Named Keep approves depicted name/identity only; source specifications and proposals stay separately pending.',
    'question_scope': 'Keep the selected individual white DR2spiral name and identity. Six groups retain historical/proposal/unknown states.',
    'metadata_checked_utc': meta['checked_utc'], 'current_answer_recorded': False,
    'current_specification_answer_recorded': False, 'current_dimension_answer_recorded': False, 'working_version_user_approved': False,
    'current_review_record': rel(out), 'review_decision_mode': 'COMPONENT_NAME_AND_SPECIFICATIONS',
    'active_family': 'Dune Ripple', 'current_family_review_number': 6,
    'family_review_evidence': rel(HERE / 'metadata-links.json'), 'next_review_after_keep': next_review,
    'displayed_identity_evidence_file_ids': [file['id']], 'displayed_identity_evidence_folder_ids': [folder['id']],
    'current_component_source_notes': [x['display'] for x in items], 'updated_utc': now})
cp['completed_serialized_parallel_import'] = copy.deepcopy(cp['next_serialized_parallel_import'])
cp['next_serialized_parallel_import'] = {'trigger': 'AFTER_DUNE_RIPPLE_FAMILY_FIRST_PASS_BEFORE_MAIN_REVIEW45',
    'status': 'PENDING_EXACT_TRANSCRIPT_SNAPSHOT_AND_CURRENT_REFERENCE_VERIFICATION', 'source_queue': 'parallel_import_queue',
    'approval_inferred': False}
later = [('DEPICTED_DESIGN_NAME_ONLY_RECEIPT', 'components/parallel-reviews/fp-panels-2026-10-17/left-white/identity-approval.json'),
         ('CONDITIONAL_SINGLE_WEIGHT_PROPOSAL_RECEIPT', 'components/parallel-reviews/fp-panels-2026-10-17/left-white/owner-weight-proposal-approval.json')]
for kind, path in later:
    if (ROOT / path).exists() and not any(x['receipt'] == path for x in cp['parallel_import_queue']):
        cp['parallel_import_queue'].append({'component_id': 'BC-FP-LEFT', 'variant_id': 'FP-LEFT-WHITE',
            'scope_kind': kind, 'receipt': path, 'receipt_sha256': sha(ROOT / path),
            'status': 'RECEIVED AFTER BATCH3 CUTOFF; PENDING NEXT BOUNDED IMPORT', 'approval_imported': False,
            'recorded_utc': now, 'scope': 'Verify exact yes response against immediate preceding question and frozen source. Name-only and conditional6kgworking-weight acceptance are separate; no other fields or actual physical specifications inferred.'})
component['interactive_review_state'].update({'current_component_id': 'BC-DR-SPIRAL', 'review_number': 37,
    'current_size_finish_variant_id': vid, 'current_name': name, 'state': cp['state'], 'active_family': 'Dune Ripple',
    'family_review_number': 6, 'family_review_total': 13, 'specification_proposals_approved': False,
    'working_version_user_approved': False, 'review_decision_mode': 'COMPONENT_NAME_AND_SPECIFICATIONS'})
component.update({'current_component_review_record': rel(out), 'parallel_import_queue': copy.deepcopy(cp['parallel_import_queue']),
                  'parallel_owner_reviews': copy.deepcopy(cp['parallel_owner_reviews']), 'updated_utc': now})
component['last_family_media_review'] = {'family': 'Dune Ripple', 'finish': 'White DR2spiral',
    'observed_utc': meta['checked_utc'], 'files': 39, 'folders': 4, 'scope': coverage['scope'],
    'evidence': rel(HERE / 'metadata-links.json'), 'workbook_contains_this_live_media_audit': False}
docs['root']['current_component_review'] = copy.deepcopy(component)
docs['root']['updated_utc'] = now
for cid, old in old_reviews.items():
    assert progress['reviews'][cid] == old
for key, p in paths.items():
    write(p, docs[key])
assert all(sha(p) == value for p, value in hashes.items())
assert read(paths['root'])['current_component_review'] == read(paths['component'])
result = {'status': 'PASS', 'component_id': 'BC-DR-SPIRAL', 'review_number': 37, 'family_review_number': 6,
    'complete_primary_original_hash_verified_and_viewed': True, 'maker_DR2_label_and5claims_checked': True,
    'complete39file_census': True, 'nine_solo_cached_thumbnails_viewed': True,
    'two_reused_series_room_originals_rehashed_and_viewed': True, 'shared30census_unchanged': True,
    'warm_colour_detail_ambiguity_and_no_rear_preserved': True, 'exact_white_platform_offer_unconfirmed': True,
    'six_specification_groups': 6, 'identity_or_specification_approval_inferred': False,
    'source_model_workbook_ledger_previous_reviews_unchanged': True, 'batch3_import_independently_verified_before_review37': True,
    'later_conditional_weight_and_name_receipts_queued_not_imported': True, 'remote_files_changed': False}
write(HERE / 'review-validation.json', result)
print(json.dumps(result))
