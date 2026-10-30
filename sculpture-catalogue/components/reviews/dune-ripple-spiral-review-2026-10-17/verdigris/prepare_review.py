"""Review the pale verdigris spiral and retain different appearance references."""
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
assert cp['current_component_id'] == 'BC-DR-SPIRAL' and cp['current_size_finish_variant_id'] == 'DR2-WHITE' and cp['current_answer_recorded']
assert docs['root']['current_component_review'] == component
white_approval = HERE.parent / 'identity-approval.json'
assert read(white_approval)['user_statement'] == 'Keep “Dune Ripple Spiral — White (DR2)”'
assert not read(white_approval)['specifications_approved']
protected = [ROOT / 'components/evidence/component_register.json', ROOT / cp['register_workbook'],
             REVIEWS / 'user_classifications.json', HERE.parent / 'component-review.json', white_approval]
hashes = {p: sha(p) for p in protected}
parent = progress['reviews']['BC-DR-SPIRAL']
parent_before = {k: copy.deepcopy(v) for k, v in parent.items() if k not in ['size_finish_variants', 'pending_size_finish_variants']}
old_variants = copy.deepcopy(parent.get('size_finish_variants', {}))
now = datetime.now(timezone.utc).isoformat()
write(HERE / 'before-verdigris-review.json', {'recorded_utc': now, 'files': {rel(paths[k]): v for k, v in docs.items()},
      'protected_sha256': {rel(p): value for p, value in hashes.items()}})
meta = read(HERE / 'metadata-links.json')
file, folder = meta['primary_metadata']['file'], meta['folder_metadata']['folder']
assert file['id'] == 'id:cnqzTNngPVsAAAAAAAyegw' and folder['id'] == 'id:cnqzTNngPVsAAAAAAAye2A'
assert file['path_display'].rsplit('/', 1)[0] == folder['path_display']
assert {k: len(v['entries']) for k, v in meta['listings'].items()} == {'solo': 34, 'solo_context': 0, 'series': 7, 'series_context': 1}
assert all(not v['has_more'] and not v['cursor'] for v in meta['listings'].values())
receipts = read(HERE / 'download-receipts.json') + read(HERE / 'front-rear-download-receipts.json') + [read(HERE / 'listing-front-download-receipt.json')]
for r in receipts:
    data = Path(r['local_path']).read_bytes()
    h = hashlib.sha256(b''.join(hashlib.sha256(data[i:i + 4194304]).digest() for i in range(0, len(data), 4194304))).hexdigest()
    assert len(data) == r['size'] and hashlib.sha256(data).hexdigest() == r['sha256']
    assert h == r['content_hash'] == r['dropbox_content_hash_verified']
assert len(receipts) == 4 and any(r['id'] == file['id'] for r in receipts)
public = read(HERE / 'public-page-http-receipt.json')
assert public['status'] == 'PASS' and sha(Path(public['local_path'])) == public['sha256']
product = public['products'][0]
assert product['offers']['sku'] == 'SQ0059342' and product['offers']['price'] == 45
gallery = read(HERE / 'public-gallery-download-receipts.json')
assert len(gallery) == 4 and all(x['status'] == 'PASS' and sha(Path(x['local_path'])) == x['sha256'] for x in gallery)
native = read(HERE / 'native-platform-source-check.json')
assert native['status'] == 'PASS' and len(native['matches']['SS Wall Products']) == 1 and not native['matches']['SH Wall Products']
links = {x['file_name']: x for x in meta['previews']}
primary, containing = links[file['id']], links[folder['id']]
model = read(ROOT / 'components/evidence/component_register.json')
offer = next(x for x in model['platform_records'] if x['offer_ref'] == 'O009')
vid, name = 'DR-SPIRAL-VERDIGRIS', 'Dune Ripple Spiral — Verdigris'
source_url = offer['source_url']
items = [
    {'proposal_id': vid + '-DIMENSIONS', 'field': 'Individual dimensions and depth',
     'value': {'listing_dimensions_cm': [35, 21, 6], 'working_dimension_order': 'Height,width,depth', 'actual_measured_dimensions_cm': None},
     'display': '35 H × 21 W × 6 D cm — native/public listing claim; actual cast unmeasured',
     'status': 'EXPLICIT INDIVIDUAL SOURCE CLAIM; CAST APPLICABILITY SUBJECT TO OWNER REVIEW',
     'basis': 'Original Squarespace row14 and current public visible description state35×21×6cm. Use explicit centimetre text, not unencoded13.8/8.3/2.4raw fields. Historical white DR2 35×20cm is separately scoped.', 'source_refs': [source_url, 'SS Wall Products!row14/Description']},
    {'proposal_id': vid + '-WEIGHT', 'field': 'Individual dry weight',
     'value': {'proposed_weight_kg': 4, 'working_estimate_range_kg': [3, 5], 'native_raw_weight': 11, 'native_weight_unit': 'Unencoded', 'actual_weighed_kg': None},
     'display': 'Approximately 4 kg (working range3–5kg) — guess; actual cast unweighed',
     'status': 'UNAPPROVED ANALOGY ESTIMATE',
     'basis': 'Related white DR2 maker standard calculates3–5kg. The original Squarespace weight11has no encoded unit and is not interpreted as11kg or converted from pounds. No exact green binder or dry weight established.', 'source_refs': ['manufacture-stevensons:Sheet1!row55 analogy only', rel(HERE / 'native-platform-source-check.json')]},
    {'proposal_id': vid + '-MATERIAL', 'field': 'Material and finish',
     'value': {'proposed_substrate': 'Sand/mineral cast composite', 'source_finish': 'Hand-painted faux verdigris on copper', 'source_ingredient_claim': 'Sand/natural materials', 'actual_binder': None, 'actual_metal_content': None, 'reinforcement': None, 'sealing': None},
     'display': 'Sand/mineral cast composite — guess; faux verdigris/copper surface described; binder unconfirmed',
     'status': 'SOURCE SURFACE/INGREDIENT CLAIM AND UNAPPROVED SUBSTRATE GUESS',
     'basis': 'Visible text describes natural materials and faux verdigris on copper; current JSON-LD also describes sand. This does not certify solid copper, actual metal content, plaster or AC730. Cast composite is a working interpretation; rear white material is not a chemical identification.', 'source_refs': [source_url, rel(HERE / 'public-page-http-receipt.json')]},
    {'proposal_id': vid + '-FIXING', 'field': 'Fixing',
     'value': {'proposed_hanging_points': 1, 'proposed_type': 'Concealed rear keyhole plate', 'candidate_rear_file_id': 'id:cnqzTNngPVsAAAAAAAye2Q', 'exact_front_back_match_verified': False, 'actual_hardware': None, 'attachment': None, 'rated_load': None},
     'display': 'One recessed keyhole fixing — proposal from rear015candidate; exact front/back match unconfirmed',
     'status': 'CANDIDATE REAR EVIDENCE; NOT EXACT CAST VERIFICATION',
     'basis': 'Downloaded015original shows a white recessed back with a single metal keyhole plate. No rear appears in the4current public gallery photos. Folder placement alone does not assign this back to selected pale027, speckled013 or blue/bronze refs; metal grade, attachment and load remain unknown.', 'source_refs': [rel(HERE / 'front-rear-download-receipts.json')]},
    {'proposal_id': vid + '-PRICE', 'field': 'Individual retail price',
     'value': {'source_amount': 45, 'currency': 'GBP', 'sale_unit': 'One listed pale verdigris spiral panel', 'owner_price_approval': False, 'new_commission_quote': None},
     'display': '£45 per listed individual panel — public/native source price; owner approval pending',
     'status': 'CURRENT PUBLIC SOURCE PRICE; NOT A GUARANTEED NEW COMMISSION QUOTE',
     'basis': 'Current directHTTP200, public web text and original native export agree45; public JSON-LD explicitly encodesGBP. Price is scoped to O009selected listing appearance,not all34folder images, another finish or a new commission.', 'source_refs': [source_url, rel(HERE / 'native-platform-source-check.json')]},
    {'proposal_id': vid + '-AVAILABILITY', 'field': 'Availability',
     'value': {'source_status': 'Listed for purchase; schema InStock', 'native_historical_stock_field': 4, 'physical_stock_quantity_verified': None, 'production_capacity': None, 'lead_time': None, 'proposed_fallback': 'Enquire individually; made to order only if owner confirms reproducibility'},
     'display': 'Listed for purchase; actual stock, reproducibility and lead time unconfirmed',
     'status': 'PUBLIC OFFER STATE; PHYSICAL AVAILABILITY UNKNOWN',
     'basis': 'Current visible BuyNow and structuredInStock are platform states. Original stock4is a dated native field,not a current physical count. Do not infer four sculptures, production readiness or made-to-order capacity from it.', 'source_refs': [source_url, rel(HERE / 'native-platform-source-check.json')]},
]
mapping = {'offer_ref': 'O009', 'squarespace_id': '6a4199ab16d56f3a046f502f', 'shopify_handle': None,
    'sku': 'SQ0059342', 'shared_sku': None, 'source_ss_row': 14,
    'platform_pair_status': 'ONE SQUARESPACE SKU ROW; NO SHOPIFY COUNTERPART IN PROVIDED ORIGINAL EXPORT',
    'dropbox_status': 'PALE027DESIGN/FINISH VISUALLY MATCHES THE CURRENT FOUR-IMAGE LISTING; OWNER REVIEW PENDING',
    'primary_file_id': file['id'], 'primary_folder_id': folder['id'], 'native_previous_candidate_id': 'id:cnqzTNngPVsAAAAAAAye3g',
    'previous_candidate_scope': '013more speckled reference retained separately; no automatic45GBP/size/stock transfer',
    'exact_physical_cast_or_listing_photo_byte_identity_verified': False, 'mould_DR2_and_other_finish_equivalence_confirmed': False,
    'live_platform_admins_refreshed': False, 'current_public_gallery_images_downloaded': 4}
coverage = {'complete_individual_front': True, 'side_and_detail_available': True, 'wall_mounted_front_reference': True,
    'dedicated_in_situ_folder_files': 0, 'series_candidate_available': True,
    'exact_selected_appearance_series_match_verified': False, 'verified_client_installation_provenance': False,
    'rear_candidate_available': True, 'exact_rear_matched': False, 'physical_stock_inferred': False,
    'scope': 'Complete42file audit:34solo+0dedicatedcontext+7relatedseries+1seriescontext. All42cached thumbnails reviewed this turn;4Dropbox originals and4public gallery originals downloaded/hash verified/viewed. Pale027,more densely speckled013/005,andblue/bronze refs remain distinct appearance scopes with unknown physical/mould relationship. No same-cast inference for the rear or series candidate.'}
extra_id = 'DR-SPIRAL-VERDIGRIS-COPPER-SPECKLED'
if not any(x['variant_id'] == extra_id for x in cp['family_review_order']):
    at = next(i for i, x in enumerate(cp['family_review_order']) if x['variant_id'] == vid)
    cp['family_review_order'].insert(at + 1, {'component_id': 'BC-DR-SPIRAL', 'review_number': 37,
        'variant_id': extra_id, 'label': 'More densely speckled verdigris/copper reference; compare with pale listing and blue/bronze',
        'primary_candidate_file_id': 'id:cnqzTNngPVsAAAAAAAye4A', 'requires_owner_relationship_check': True,
        'exact_mould_relationship_confirmed': False})
total = len(cp['family_review_order'])
assert total == 14
next_review = {'component_id': 'BC-DR-SPIRAL', 'review_number': 37, 'size_finish_variant_id': extra_id,
               'family_review_number': 8, 'requires_owner_relationship_check': True}
review = {'schema_version': 1, 'prepared_utc': now, 'component_id': 'BC-DR-SPIRAL',
    'canonical_design_name': 'Dune Ripple Spiral — DR2', 'proposed_name': name, 'display_name': name, 'family': 'Dune Ripple',
    'review_number': 37, 'family_review_number': 7, 'family_review_total': total, 'size_finish_variant_id': vid,
    'variant_only_review': True, 'review_decision_mode': 'SIZE_FINISH_VARIANT_NAME_AND_SPECIFICATIONS',
    'parent_identity_approval': rel(white_approval), 'parent_design_relationship_status': 'Source-assisted family allocation; exact mould/cast/finish relationships remain provisional',
    'scope': 'Only the selected paler027verdigris reference. More speckled013/005andblue-bronze references are separate pending review,not proven additional manufactured sculptures.',
    'primary_image_id': file['id'], 'primary_folder_id': folder['id'], 'primary_image_link': primary['copy_link_url'],
    'primary_folder_link': containing['copy_link_url'], 'metadata_checked_utc': meta['checked_utc'],
    'reference_refresh': rel(HERE / 'metadata-links.json'), 'original_download_receipts': [rel(HERE / 'download-receipts.json'),
        rel(HERE / 'front-rear-download-receipts.json'), rel(HERE / 'listing-front-download-receipt.json')],
    'public_page_receipts': rel(HERE / 'public-page-http-receipt.json'),
    'public_image_receipts': rel(HERE / 'public-gallery-download-receipts.json'),
    'native_platform_source_check': rel(HERE / 'native-platform-source-check.json'),
    'appearance_reference_clusters': rel(HERE / 'appearance-reference-clusters.json'),
    'specification_review_items': items, 'platform_mapping': mapping, 'source_offer_snapshots': [offer],
    'photo_coverage': coverage, 'identity_confirmed': False, 'specifications_approved': False, 'physical_specs_verified': False,
    'candidate_rear_image_id': 'id:cnqzTNngPVsAAAAAAAye2Q', 'candidate_rear_image_link': links['id:cnqzTNngPVsAAAAAAAye2Q']['copy_link_url'],
    'series_candidate_image_id': 'id:cnqzTNngPVsAAAAAAAygwg', 'series_candidate_folder_id': 'id:cnqzTNngPVsAAAAAAAyiaQ',
    'series_candidate_image_link': links['id:cnqzTNngPVsAAAAAAAygwg']['copy_link_url'],
    'series_candidate_scope': 'Related three-panel appearance reference only; exact pale027finish/cast link unconfirmed',
    'source_conflicts': ['Explicit35×21×6listing versus white35×20standard', 'Native raw11weight has no encoded unit',
        'Native stock4and publicInStockversus unverified physical inventory', 'Pale,speckled and blue/bronze image appearances are not one-to-one cast/mould evidence'],
    'open_gaps': ['Owner name/identity approval for pale027reference', 'Actual size,weight,binder,metal content,reinforcement,sealing and care',
        'Exact front/back match,fixing hardware/attachment/load', 'Current physical stock,manufacture,capacity and lead time',
        'Shopify counterpart or new individual offer if needed', 'Exact finish/cast relation across34files and related series/context; true client-installation provenance'],
    'next_review_after_keep': next_review, 'next_global_component_id': 'BC-DR-WAVE3',
    'remote_files_changed': False, 'live_platform_records_changed': False}
write(out, review)
parent.setdefault('size_finish_variants', {})[vid] = {'reviewed_utc': now, 'identity_confirmed': False,
    'specifications_approved': False, 'proposals_approved': False, 'physical_specs_verified': False,
    'proposed_name': name, 'size_finish_variant_id': vid, 'review_record': rel(out),
    'primary_image_id': file['id'], 'primary_folder_id': folder['id'], 'specification_proposals': copy.deepcopy(items),
    'platform_mapping': mapping, 'photo_coverage': coverage, 'parent_design_relationship_status': review['parent_design_relationship_status']}
for pending in parent['pending_size_finish_variants']:
    if pending['variant_id'] == vid:
        pending.update({'review_status': 'AWAITING PALE VERDIGRIS NAME; SIX GROUPS PENDING', 'review_record': rel(out)})
parent['pending_size_finish_variants'].append({'variant_id': extra_id, 'status': 'MORE SPECKLED APPEARANCE RELATIONSHIP PENDING; NO AUTOMATIC OFFER TRANSFER'})
progress['updated_utc'] = now
cp.update({'current_size_finish_variant_id': vid, 'proposed_name': name,
    'state': 'Awaiting pale verdigris spiral name/identity; source SKU linked to Squarespace only and six groups remain scoped',
    'primary_image': {'file_id': file['id'], 'name': file['name'], 'path_display': file['path_display'],
                      'copy_link_url': primary['copy_link_url'], 'open_in_dropbox_url': primary['open_in_dropbox_url']},
    'containing_folder': {'folder_id': folder['id'], 'name': folder['name'], 'path_display': folder['path_display'],
                          'copy_link_url': containing['copy_link_url'], 'open_in_dropbox_url': containing['open_in_dropbox_url']},
    'current_answer_recorded': False, 'current_specification_answer_recorded': False, 'current_dimension_answer_recorded': False,
    'working_version_user_approved': False, 'current_review_record': rel(out), 'review_decision_mode': review['review_decision_mode'],
    'current_family_review_number': 7, 'current_family_review_total': total, 'family_review_evidence': rel(HERE / 'metadata-links.json'),
    'answer_state': 'No answer yet. Named Keep approves selected027name/depicted identity only; six groups remain separately pending.',
    'question_scope': 'Keep Dune Ripple Spiral—Verdigris for selected pale027reference. Exact mould/cast,more speckled reference,body chemistry,rear and stock remain unconfirmed.',
    'metadata_checked_utc': meta['checked_utc'], 'next_review_after_keep': next_review,
    'displayed_identity_evidence_file_ids': [file['id']], 'displayed_identity_evidence_folder_ids': [folder['id']],
    'current_component_source_notes': [x['display'] for x in items], 'updated_utc': now})
cp['family_counting_note'] = '14planned owner review cards,not14physical sculptures. Added separate speckled verdigris/copper reference pending relationship clarification; preserve exact native offer applicability.'
later = [('BC-FP-RIGHT', 'DEPICTED_DESIGN_NAME_ONLY_RECEIPT', 'components/parallel-reviews/fp-panels-2026-10-17/right-verdigris/identity-approval.json'),
         ('BC-SM-SPIRAL', 'NAME_ONLY_IDENTITY_RECEIPT', 'components/parallel-reviews/spiralmoon-2026-10-17/spiralmoon-one-white/review-approval.json')]
for cid, kind, path in later:
    if (ROOT / path).exists() and not any(x['receipt'] == path for x in cp['parallel_import_queue']):
        cp['parallel_import_queue'].append({'component_id': cid, 'variant_id': None, 'scope_kind': kind, 'receipt': path,
            'receipt_sha256': sha(ROOT / path), 'status': 'RECEIVED AFTER BATCH3 CUTOFF; PENDING NEXT BOUNDED IMPORT',
            'approval_imported': False, 'recorded_utc': now, 'scope': 'Verify exact owner statement and source/current references before import; no six-group,physical manufacture or missing-photo completion inferred.'})
allocations = [('01a13fbf-1cbc-7511-8416-cf339051083e', 'frozenfish-2026-10-18',
                [('BC-FFS-1', 55), ('BC-FFS-2', 56), ('BC-FFS-3', 57)], 'After existing Fingerprint51–52 first-pass package'),
               ('01a13fe6-495b-7253-b923-31823b4cbca8', 'strata-textures-2026-10-18',
                [('BC-STRATA', 117), ('BC-TEXTURE-WIDE', 118), ('BC-TEXTURE-TALL', 119)], 'After existing Spiralmoon115–116 first-pass package')]
for session, slug, members, trigger in allocations:
    ack = ROOT / 'components/parallel-reviews' / slug / 'COORDINATOR_ACKNOWLEDGEMENT.json'
    assert not ack.exists()
    reservation = []
    for cid, number in members:
        assert cp['review_order'][number - 1] == cid
        assert not any(x['component_id'] == cid for x in cp['parallel_owner_reviews'])
        reservation.append({'component_id': cid, 'review_number': number, 'owner_session': session,
            'coordinator_acknowledgement': rel(ack), 'status': 'RESERVED FOR EXISTING PARALLEL LANE AFTER CURRENT FIRST PASS',
            'start_trigger': trigger, 'approval_inferred': False, 'acknowledged_utc': now})
    write(ack, {'recorded_utc': now, 'reservation': reservation,
        'scope': trigger + '. All finishes in this disjoint block only. Existing explicitly authorized lane; isolated immutable receipts,individual Dropbox picture/folder plus six source-or-guess groups. Preserve lineage,mould,photo,manufacture and specification gaps. Main alone writes shared overlays/workbook; no remote mutations.'})
    cp['parallel_owner_reviews'].extend(reservation)
component['interactive_review_state'].update({'current_size_finish_variant_id': vid, 'current_name': name,
    'state': cp['state'], 'family_review_number': 7, 'family_review_total': total,
    'specification_proposals_approved': False, 'working_version_user_approved': False, 'review_decision_mode': review['review_decision_mode']})
component.update({'current_component_review_record': rel(out), 'parallel_import_queue': copy.deepcopy(cp['parallel_import_queue']),
                  'parallel_owner_reviews': copy.deepcopy(cp['parallel_owner_reviews']), 'updated_utc': now})
component['last_family_media_review'] = {'family': 'Dune Ripple', 'finish': 'Pale verdigris spiral',
    'observed_utc': meta['checked_utc'], 'files': 42, 'folders': 4, 'scope': coverage['scope'],
    'evidence': rel(HERE / 'metadata-links.json'), 'workbook_contains_this_live_media_audit': False}
docs['root']['current_component_review'] = copy.deepcopy(component)
docs['root']['updated_utc'] = now
assert {k: v for k, v in parent.items() if k not in ['size_finish_variants', 'pending_size_finish_variants']} == parent_before
for key, value in old_variants.items():
    assert parent['size_finish_variants'][key] == value
for key, p in paths.items():
    write(p, docs[key])
assert all(sha(p) == value for p, value in hashes.items())
assert read(paths['root'])['current_component_review'] == read(paths['component'])
result = {'status': 'PASS', 'variant_id': vid, 'primary027and3otherDropbox_originals_hash_verified_and_viewed': True,
    'all4current_public_gallery_originals_checked': True, 'complete42file_census_and_cached_visual_review': True,
    'original_workbook_unique_SS_SKU_and_no_SH_counterpart_verified': True, 'pale_speckled_bluebronze_references_separate': True,
    'one_additional_reference_card_not_physical_stock_added': True, 'rear_and_series_candidates_not_promoted_to_exact_matches': True,
    'six_specification_groups': 6, 'source_model_workbook_owner_ledger_and_white_approval_unchanged': True,
    'existing_peer_next_disjoint_blocks_reserved_after_current_first_pass': True, 'remote_files_changed': False}
write(HERE / 'review-validation.json', result)
print(json.dumps(result))
