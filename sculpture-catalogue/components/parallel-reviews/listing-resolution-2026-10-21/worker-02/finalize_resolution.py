#!/usr/bin/env python3
"""Finish the bounded source audit without altering catalogue or platform records."""
from __future__ import annotations

import collections
import copy
import hashlib
import json
import pathlib
from datetime import datetime, timezone

HERE = pathlib.Path(__file__).resolve().parent
TASK = HERE.parent
ROOT = pathlib.Path('/Users/tprice/Documents/boldstone/sculpture-catalogue')
PACK = pathlib.Path('/Users/tprice/Library/Application Support/BoldstoneImageConsistency/product-evidence-resolution-20261016T201618Z')
B_DIR = ROOT / 'components/reconciliation/cup-frozen-manual-move-readback-2026-10-21'
sources = {}

def digest(data):
    return hashlib.sha256(data).hexdigest()

def load(p, expected=None):
    p = pathlib.Path(p)
    b = p.read_bytes()
    h = digest(b)
    if expected:
        assert h == expected, (str(p), h)
    sources[str(p)] = {'path': str(p), 'sha256': h, 'bytes': len(b)}
    return json.loads(b)

def ref(p, pointer=None):
    r = copy.deepcopy(sources[str(p)])
    if pointer is not None:
        r['json_pointer'] = pointer
    return r

def receipt(p):
    p = pathlib.Path(p)
    b = p.read_bytes()
    r = {'path': str(p), 'sha256': digest(b), 'bytes': len(b)}
    sources[str(p)] = r
    return copy.deepcopy(r)

def save(name, data):
    p = HERE / name
    assert p.parent == HERE
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')

pre = load(HERE / 'OPTION_RESOLUTION_PRELIMINARY.json')
prior_receipts = load(HERE / 'SOURCE_RECEIPTS_PRELIMINARY.json')
for s in prior_receipts['sources']:
    assert digest(pathlib.Path(s['path']).read_bytes()) == s['sha256'], ('source drift', s['path'])
    sources[s['path']] = s
master_path = TASK / 'inputs/master-register.json'
master = load(master_path, '7760b44a4d52ff3b78c893d5b86ef174814b48c29f7e41814c8a01a42af5326d')
fresh_path = TASK / 'worker-01/FRESH_PUBLIC_INVENTORY.json'
fresh = load(fresh_path, '4445986b548ef256c7ab2f4f8c80f34ade0f590ce9e9e6adbdf4ea9118726bfd')
native_path = HERE / 'SOURCE_NATIVE_CLAIMS.json'
native = load(native_path)
plan = load(HERE / 'VISUAL_INSPECTION_PLAN.json')
gallery_path = PACK / 'Public_Gallery_References.json'
gallery = load(gallery_path)
model_path = ROOT / 'components/evidence/component_register.json'
model = load(model_path)
progress_path = ROOT / 'components/reviews/specification_review_progress.json'
progress = load(progress_path)
maker_path = PACK / 'Manufacturing_Sheet_Extract.json'
maker = load(maker_path)
o009_manifest_path = TASK / 'additional-public/o009/MANIFEST.json'
o009 = load(o009_manifest_path)
b_overlay_path = B_DIR / 'CURRENT_REFERENCE_OVERLAY.json'
b_findings_path = B_DIR / 'IMAGE_ROLE_FINDINGS.json'
b_seal_path = B_DIR / 'SEAL.json'
b_overlay = load(b_overlay_path, '00541273bdb37215d8f313e2aedf69b6535481309ad284b97f5802a7e558416e')
b_findings = load(b_findings_path, 'e557506233a2a03a41046e7fa4fe3a077efe1bb70766cba8e10321db9fc21588')
load(b_seal_path, '570640267873ff5d7c5c1d16c13b1c0ad643193f81f811db39c22b193d008c3d')
boundary_path = TASK / 'worker-01/BOUNDARY_INVENTORY_SUPPLEMENT.json'
boundary = load(boundary_path)

assets = {a['id']: a for a in model['assets']}
option_by_id = {o['product_id']: (i, o) for i, o in enumerate(master['options'])}
public_by_id = {p['native_product_id']: (i, p) for i, p in enumerate(fresh['products'])}
components = {c['component_id']: c for c in master['components']}
all_inspections = []
for item in plan:
    image = copy.deepcopy(item)
    image['viewed_with'] = 'tools.view_image'
    image['visual_review_completed'] = True
    image['local_bytes_receipt'] = receipt(item['path'])
    image['source_resolution_limit'] = 'Cached full-frame reference/thumbnail or public rendition; no calibrated dimensions, chemical composition, actual stock or installation authenticity certified.'
    all_inspections.append(image)
for i, asset in enumerate(o009['assets']):
    r = receipt(asset['path'])
    assert r['sha256'] == asset['sha256'] and r['bytes'] == asset['bytes']
    all_inspections.append({'role': 'fresh_native_media', 'offer_ref': 'O009', 'native_product_id': asset['native_product_id'], 'native_media_id': asset['native_media_id'], 'native_asset_url': asset['requested_url'], 'path': asset['path'], 'local_bytes_receipt': r, 'download_receipt': ref(o009_manifest_path, f'/assets/{i}'), 'viewed_with': 'tools.view_image', 'visual_review_completed': True, 'scope': 'Four complete source images/angles show the generic Verdigris appearance; not the densely copper-speckled kept reference.'})

# Extra inspected frames used for precise negative/border distinctions.
extra_ids = ['id:cnqzTNngPVsAAAAAAAygZw', 'id:cnqzTNngPVsAAAAAAAygZg', 'id:cnqzTNngPVsAAAAAAAuRUA', 'id:cnqzTNngPVsAAAAAAAygbA', 'id:cnqzTNngPVsAAAAAAAygaA', 'id:cnqzTNngPVsAAAAAAAye3g', 'id:cnqzTNngPVsAAAAAAAyfkg', 'id:cnqzTNngPVsAAAAAAAyfkw', 'id:cnqzTNngPVsAAAAAAAylYg', 'id:cnqzTNngPVsAAAAAAAylZA']
for fid in extra_ids:
    a = assets[fid]
    all_inspections.append({'role': 'supplemental_kept_or_historical_reference', 'file_id': fid, 'folder_id': a['folder_id'], 'path': a['thumb'], 'baseline_content_hash': a['content_hash'], 'local_bytes_receipt': receipt(a['thumb']), 'viewed_with': 'tools.view_image', 'visual_review_completed': True, 'scope': 'Geometry/depicted appearance only; encoded original and physical specimen equivalence not certified.'})
negative_public_keys = ['cd8fa637ba2ef72970f43d1b0b669ee2ce18e78bb0b1a7ad510936039cd4bc62', '2defab026ade1b130d8bd7ac1e928ff450d34c8eddd9335fd5db3a16c4ee4eac', 'ed0172ff8924bf44f0829b28d0e1a450d882eadb9f930abaec1ce5ec9d6a9bf0', 'ab1fb55bb1d5606bac16afec582ce31d458fecb1897919e1a338d5c0b4d331b5']
for key in negative_public_keys:
    i, g = next((i, g) for i, g in enumerate(gallery['records']) if key in g['image_path'])
    all_inspections.append({'role': 'candidate_native_media_not_bound_to_kept_scope', 'offer_ref': 'O007', 'path': g['image_path'], 'native_asset_url': g['image_url'], 'gallery_ref': ref(gallery_path, f'/records/{i}'), 'local_bytes_receipt': receipt(g['image_path']), 'viewed_with': 'tools.view_image', 'visual_review_completed': True, 'finding': 'Verdigris/rust-looking circular relief shown, but not the same photograph/patina layout as the kept MCP1 reference. Caption colour words and spherical geometry do not independently establish an exact maker-labelled option alias.'})

visual_cases = [
    {'case_id': 'O038_TO_DR_WAVES_VERDIGRIS_RUST', 'option_ids': ['BSI-09C1A55D460D'], 'offer_refs': ['O038'], 'result': 'SOURCE_SUPPORTED_SINGLE_COMPONENT_DESIGN_FINISH_AND_RECORDED_SIZE_LINK', 'compared_kept_families': ['BC-DR-WAVE1', 'BC-DR-SPIRAL'], 'source_image_scope': 'One native O038 media item; its exact URL is retained by the 21 October collection. Cached public rendition viewed against the identical photographed primary arqdg and all kept Wave appearances/contexts.', 'discriminating_features': ['The same vertical wavy-ridge composition and staggered ridge terminations.', 'Same sparse copper/rust patches, including long marks on left ridges and dark patch near the lower right channel.', 'Same photograph, framing and pale background; not the broad nearly solid-rust, muted generic-Verdigris or Blue-Verdigris/Bronze references.'], 'native_unit_evidence': 'Individually carved and cast 35cm x20cm x6cm, Verdigris copper and rust; singular work marked SOLD, similar sculpture by enquiry.', 'limits': ['Photographic match establishes depicted design/finish source scope, not physical measurement or chemical formulation.', 'SOLD description and native unlimited setting remain separate claims; no current stock or commission readiness verified.', 'Current public product retains a previously cached image URL; O038 image bytes were not freshly fetched by this worker.']},
    {'case_id': 'O006_TO_MCP4_VERDIGRIS_RUST', 'option_ids': ['BSI-46F6DB226213'], 'offer_refs': ['O006'], 'result': 'SOURCE_SUPPORTED_SINGLE_COMPONENT_OWNER_NAMED_APPEARANCE_AND_RECORDED_SIZE_LINK', 'compared_kept_families': ['BC-MCP-4'], 'source_image_scope': 'All eight O006 native gallery URLs match the cached public-reference index; each cached image was viewed. Compared all four kept MCP4 finish primaries and relevant context images.', 'discriminating_features': ['Large rust-coloured patch extending from upper centre down the right half of the circular face.', 'Isolated rust patch at lower-left/left-middle and matching small-patch outline near lower-right.', 'Matching corner speckles, circular edge position and panel outline in the owner-kept Verdigris/Rust reference.', 'Silver/Bronze, even Verdigris and White references visibly depict different appearance treatments; no scope merge.'], 'native_unit_evidence': 'Single wall sculpture with source-stated25×25×6cm and one current native variant.', 'limits': ['Owner-kept clean reference and public gallery are different shots; no original-byte equality or independent physical-cast verification asserted.', 'Native body says faux Verdigris on copper and concave relief; owner states plaster composite with faux Verdigris/rust. Preserve both source wordings; no chemistry/curvature certification.', 'Native current price150GBP differs from owner-accepted working175GBP.', 'Source does not enumerate both owner fixing choices; actual installed hardware and physical stock remain unverified.', 'Current collection retains cached gallery URLs; fresh O006 image bytes were not fetched by this worker.']},
    {'case_id': 'O009_FRESH_GALLERY_RETAINS_GENERIC_VERDIGRIS', 'option_ids': ['BSI-4536FDCA0DA9', 'BSI-9299D69FEF08'], 'offer_refs': ['O009'], 'result': 'PRIOR_GENERIC_VERDIGRIS_LINK_RETAINED; HISTORICAL_HERO_BINDING_CONFLICT; NO_REALLOCATION', 'source_image_scope': 'All four freshly downloaded native O009 images plus every kept Spiral primary and relevant context; both yegw and ye4A inspected separately.', 'discriminating_features': ['Fresh native images match yegw: broad turquoise channels, thin reddish/copper ridge streaks and sparse irregular bottom-edge copper patches.', 'Speckled ye4A and historical wide-shot hero ye3g have a denser, uniform copper-speckled treatment; source-folder membership does not make them the same offered finish.', 'The four native records supply no finish option attribute selecting the speckled finish.'], 'native_unit_evidence': 'One35×21×6cm faux-Verdigris-on-copper single sculpture with native variant dd19e6d1-9e97-40e7-aec2-581bd7fac273 /SQ0059342.', 'correction_scope': 'Append precise historical source-hero/current-native-gallery applicability conflict. Preserve both canonical options and the existing generic Verdigris native record linkage. Do not reuse its SKU as a second speckled variant.'},
    {'case_id': 'MCP1_FINISH_COMPATIBILITY_WITHOUT_EXACT_DESIGN_ALIAS', 'option_ids': ['BSI-EBD43DF0704F'], 'offer_refs': ['O007'], 'result': 'CANDIDATE_RETAINED; NO_FORCED_EXACT_NATIVE_MATCH', 'source_image_scope': 'Four cached full public frames and five retained MCP1 Verdigris/Rust views inspected.', 'finding': 'Native captions explicitly mention rust/green patina and source body states25×25×6cm. This improves finish/size compatibility evidence. Source images have a different patina layout from the kept reference and no explicit maker-code/owner alias joins the source gallery to this named option. Different hand-applied surface layouts need not be different designs; neither sameness nor a new variant is invented.'},
    {'case_id': 'MOONPHASE_BORDER_GAP', 'option_ids': ['BSI-65A93033A200', 'BSI-4515726BBC18'], 'offer_refs': ['O065', 'O074'], 'result': 'UNBORDERED_NATIVE_PRIMARY_DOES_NOT_ENUMERATE_BORDERED_VARIANT', 'source_image_scope': 'Kept unbordered native-source primaries yfkg/yfkw compared with kept bordered primaries ylYg/ylZA.', 'finding': 'The standalone bordered references have complete rectangular outer frames. The native primary photos show neighbouring unbordered reliefs and variant attributes are empty. Source30cm core dimensions do not establish bordered outer dimensions or an individual border SKU.'}
]
save('VISUAL_COMPARISONS.json', {'schema': 'boldstone.listing-resolution-visual-comparisons.v1', 'cases': visual_cases, 'inspections': all_inspections, 'counts': {'inspection_records': len(all_inspections), 'unique_paths_viewed': len({x['path'] for x in all_inspections}), 'all_kept_Dune_Spiral_options_compared': 8, 'all_kept_Dune_Wave_options_compared': 5, 'all_kept_MCP4_options_compared': 4}, 'private_uploads': 0, 'image_edits': 0, 'physical_measurements_or_stock_certifications': 0})

entries = pre['entries']
by_id = {e['option_id']: e for e in entries}
for e in entries:
    _, o = option_by_id[e['option_id']]
    cid = e['canonical_component_id'] or e['canonical_design_id']
    sids = e['source_evidence']['source_component_ids']
    e['source_native_claims_refs'] = [f'SOURCE_NATIVE_CLAIMS.json#/offers/{off}' for off in e['related_offer_refs']]
    e['source_evidence']['current_review_scope_refs'] = []
    for sid in sids:
        if sid in progress.get('reviews', {}):
            e['source_evidence']['current_review_scope_refs'].append(ref(progress_path, '/reviews/' + sid))
    if cid in progress.get('catalogue_design_aliases', {}):
        e['source_evidence']['current_review_scope_refs'].append(ref(progress_path, '/catalogue_design_aliases/' + cid))
    rows = {row for c in model['components'] if c['component_id'] in sids for row in c.get('maker_rows', [])}
    e['source_evidence']['maker_rows'] = [{'row': v['row'], 'source': ref(maker_path, f'/{i}'), 'scope': 'Historical labelled maker standard, principally White AC730; not physical verification of coloured/current cast or native variant.'} for i, v in enumerate(maker) if v['row'] in rows]
    e['source_evidence']['source_BOM_individual_sale_unit_check'] = {'related_offer_refs': e['related_offer_refs'], 'whole_set_or_gallery_sku_reused': False, 'whole_set_values_divided': False, 'same_mould_vs_numbered_position_distinction_preserved': True}
    e['draft_individual_listing']['creation_is_not_authorized_or_performed_by_this_packet'] = True
    e['review_status'] = 'COMPLETE_BOUNDED_SOURCE_AUDIT; SUPPORTED_LINK_OR_PRECISE_SCOPE_GAP_RECORDED'
    e['required_next_evidence_kind'] = 'Authenticated account/draft lookup for this canonical individual option, or the exact stated source identity/configuration binding. No repeat broad manufacture/name/working-specification approvals.'
    e['reference_epoch'] = 'Frozen master reference, plus separately cited B readback where applicable. Parent owns final current-path rebasing.'
    if cid in {'BC-CR-RING', 'BC-CR-SPIRAL', 'BC-FFL-1', 'BC-FFS-1', 'BC-FFS-2', 'BC-FFS-3'}:
        e['moved_reference_review'] = {'overlay': ref(b_overlay_path), 'role_findings': ref(b_findings_path), 'changes_identity_specifications_or_coverage': False, 'conclusion': 'Cup Ring right-hand position owner-confirmed; new isolated Pink/Brown appearances are not certified White reference replacements. Frozen Fish Long100×22 remains image-unbound. FP1/FP2 folder numbers do not identify Fingerprint or CRS codes.', 'native_listing_link_added': False}
        if cid == 'BC-CR-RING':
            e['scope_reason'] += ' The21October readback confirms Cup Ring on the right of paired reference5zqA; three new isolated Pink/Brown images do not establish a complete White replacement or an existing native listing.'
        elif cid == 'BC-FFL-1':
            e['scope_reason'] += ' The21October readback expressly retains the Long100×22 image gap; moved crop files show adjacent portions without full edges/scale and are context only.'
    if e['option_id'] == 'BSI-9299D69FEF08':
        e['scope_reason'] += ' All four fresh O009 images match the separate generic Verdigris yegw reference. The old source-register hero ye3g matches this speckled appearance instead, so retain a historical/current photo-applicability conflict and do not assign SQ0059342 to a second variant.'
        e['remaining_evidence_gaps'].append('Exact native listing/variant for densely speckled Verdigris-and-Copper ye4A; current O009 is a different retained appearance. Historical hero metadata alone is insufficient.')
        e['visual_comparison_ref'] = 'VISUAL_COMPARISONS.json#/cases/2'
    elif e['option_id'] == 'BSI-EBD43DF0704F':
        e['remaining_evidence_gaps'] = ['Exact source-gallery to maker-labelled/owner-kept MCP1 design alias. Native media captions support rust/verdigris appearance and25cm dimensions, but generic spherical geometry/different patina layouts cannot alone resolve the exact scope.', 'If no existing exact option after authenticated admin lookup, use draft canonical reference and distinct proposed SKU; do not invent a pure-Verdigris catalogue option or a new mould.']
        e['visual_comparison_ref'] = 'VISUAL_COMPARISONS.json#/cases/3'
    elif e['option_id'] in {'BSI-65A93033A200', 'BSI-4515726BBC18'}:
        e['visual_comparison_ref'] = 'VISUAL_COMPARISONS.json#/cases/4'

def ss_binding(off):
    data = native['offers'][off]['Squarespace']
    assert len(data['variants']) == 1
    v = data['variants'][0]
    return {'platform': 'Squarespace', 'offer_ref': off, 'native_product_id': data['native_product_id'], 'native_variant_id': v['native_variant_id'], 'sku_raw': v['sku'], 'option_attributes': v['option_attributes'], 'url': data['url'], 'source_locator': v['source_locator'], 'presence_scope': 'PUBLIC_COLLECTION_OBSERVED_2026_10_21; NO_AUTHENTICATED_ADMIN_VERIFICATION', 'native_price': v['price'], 'native_stock_setting': v['stock_setting']}

def upgrade(oid, off, case, qualifiers):
    e = by_id[oid]
    ss = ss_binding(off)
    e['proposed_disposition'] = 'INDIVIDUAL_SOURCE_RECORD_LINKED_WITH_RECORDED_CONFIGURATION_AND_COMMERCIAL_QUALIFICATIONS'
    e['new_supported_native_matches'] = [dict(ss, match_grade='SOURCE_SUPPORTED_INDIVIDUAL_DESIGN_OWNER_NAMED_APPEARANCE_RECORDED_SIZE_AND_SALE_UNIT', exact_logical_option_scope_supported=True, all_six_native_fields_equal_to_working_fields=False, physical_configuration_verified=False, visual_comparison_ref=f'VISUAL_COMPARISONS.json#/cases/{case}', qualifications=qualifiers)]
    sh = native['offers'][off]['Shopify']
    if sh.get('variants'):
        assert len(sh['variants']) == 1
        v = sh['variants'][0]
        e['new_supported_native_matches'].append({'platform': 'Shopify', 'offer_ref': off, 'handle': sh['handle'], 'numeric_product_id': None, 'numeric_variant_id': None, 'sku_raw': v['sku_raw'], 'option_tuple': v['option_tuple'], 'source_row': v['source_row'], 'source_inventory_ref': v['source_inventory_ref'], 'match_grade': 'HISTORICAL_NATIVE_EXPORT_SINGLE_UNIT_DESIGN_FINISH_AND_RECORDED_SIZE_LINK', 'exact_logical_option_scope_supported': True, 'current_live_inventory_verified': False, 'physical_configuration_verified': False, 'qualifications': qualifiers})
    e['exact_logical_owner_working_configuration_match_supported'] = True
    e['logical_match_scope'] = ['Depicted design', 'Owner-named finish appearance', 'Recorded face/depth size', 'Individual wall-sculpture sale unit']
    e['logical_match_limits'] = ['Working values remain source/owner qualified; actual dimensions, mass, composition and hardware unverified.', 'Both fixing choices are owner-offered catalogue choices; native records do not enumerate hardware variants.', 'No claim that all six working fields equal native copy, or that the source photographed specimen is currently available.']
    e['delta_vs_prior']['new_individual_native_link'] = True
    e['visual_comparison_ref'] = f'VISUAL_COMPARISONS.json#/cases/{case}'
    e['remaining_evidence_gaps'] = qualifiers
    e['required_next_evidence_kind'] = 'Use the existing supported native record. Reconcile the specifically documented price/copy/hardware-choice differences before any separately authorized platform edit; no duplicate individual product is proposed.'
    e['draft_individual_listing']['status'] = 'NO_NEW_LISTING_REQUIRED_IN_CHECKED_NATIVE_SCOPE; EXISTING_RECORD_TARGET_SUPPORTED'
    e['draft_individual_listing']['proposed_sku'] = None
    e['draft_individual_listing']['sku_state'] = 'EXISTING_NATIVE_SKU_RECORDED_SEPARATELY; NO_NEW_SKU_PROPOSED'
    e['draft_individual_listing']['current_native_target'] = ss

upgrade('BSI-09C1A55D460D', 'O038', 0, ['Retain source SOLD wording and similar-commission-by-enquiry policy; native unlimited=True is not physical stock.', 'Native/public and historical Shopify describe35×20×6cm, Verdigris copper/rust, one sculpture. Exact formulation, installed fixing, weighed mass and current commission quote/lead time remain unverified.', 'Current public image URL points to a cached16October rendition; no new original/cast verification.'])
by_id['BSI-09C1A55D460D']['scope_reason'] = 'O038 public/native description explicitly offers one35×20×6cm Verdigris copper/rust Dune Ripple sculpture, marked SOLD with a similar-commission enquiry. Its sole public gallery image is the same photograph as the kept arqdg primary. The current public variant and the historical Shopify handle/SKU are therefore source-supported for this logical individual option, with stock/formulation/fixing and source-date qualifications retained.'
upgrade('BSI-46F6DB226213', 'O006', 1, ['Native current price150GBP differs from owner-accepted working175GBP; neither value overwritten.', 'Source faux-Verdigris-on-copper/concave wording and owner plaster-composite/faux-rust description retained independently. No chemical formulation or physical curvature certification.', 'Owner4kg dry mass and keyhole/French-cleat choice are not freshly verified native hardware/weight claims. Native source does not enumerate both fixing choices.', 'Current native collection retains all eight cached source gallery URLs. Patina/geometry comparison supports the owner-named appearance; same original encoded file or independently verified physical cast is not claimed.'])
by_id['BSI-46F6DB226213']['scope_reason'] = 'All eight source gallery references for O006 depict the distinctive rust/verdigris treatment matching the owner-kept MCP4 Verdigris/Rust reference; other kept MCP4 finishes were compared and remain separate. The single native variant states25×25×6cm, compatible with the owner working face/depth. Link the existing native record for this logical option while preserving the150GBP native versus175GBP owner price and all material/hardware qualifications.'

prior_positive = {'option_id': 'BSI-4536FDCA0DA9', 'canonical_key': 'BC-DR-SPIRAL|DR-SPIRAL-VERDIGRIS', 'prior_disposition': option_by_id['BSI-4536FDCA0DA9'][1]['current_listing_reconciliation']['overall_disposition'], 'proposed_disposition': 'RETAIN_EXISTING_INDIVIDUAL_SOURCE_RECORD_LINK', 'offer_ref': 'O009', 'native_binding': ss_binding('O009'), 'prior_positive_association_changed': False, 'newly_resolved_99_scope_option': False, 'included_in_new_positive_count': False, 'finding': 'All four fresh native photos match the generic Verdigris kept primary yegw. Retained historical source hero ye3g depicts the other speckled appearance; append that source-image applicability conflict without merging options or reusing SKU for the speckled option.', 'visual_comparison_ref': 'VISUAL_COMPARISONS.json#/cases/2', 'both_canonical_options_preserved': True, 'six_working_fields_changed': False}
save('PRIOR_POSITIVE_ASSOCIATION_AUDIT.json', {'schema': 'boldstone.prior-positive-association-audit.v1', 'entries': [prior_positive], 'counts': {'prior_positive_options_audited': 1, 'prior_positive_associations_changed': 0, 'prior_positive_downgrades': 0, 'prior_positive_upgrades_counted_as_new': 0}, 'historical_source_photo_corrections_are_not_native_SKU_reallocations': True})

# All draft SKUs are explicitly not native; identity uncertainty is a condition, not absence.
groups = collections.defaultdict(list)
for e in entries:
    if e['draft_individual_listing']['proposed_sku']:
        groups[e['draft_individual_listing']['proposed_product_group_id']].append(e['draft_individual_listing'])
draft_groups = [{'proposed_product_group_id': k, 'status': 'DRAFT_NOT_NATIVE; NO_PLATFORM_WRITE', 'grouping_basis': 'Only this immutable canonical component/design; finish/size/build scopes stay individually identified.', 'variants': v, 'set_offer_not_reused_as_individual_product': True, 'creation_condition': 'Authenticated native product/draft lookup plus the specific identity/configuration/media gap in each option disposition.'} for k, v in groups.items()]
save('DRAFT_LISTING_GROUPS.json', {'schema': 'boldstone.proposed-individual-listing-groups.v1', 'counts': {'draft_groups': len(draft_groups), 'draft_variants': sum(len(g['variants']) for g in draft_groups), 'new_native_products_or_variants_created': 0}, 'groups': draft_groups, 'individual_prices_weights_and_dimensions_are_not_set_allocations': True, 'do_not_treat_as_platform_execution_authority': True})

summary = {'assigned_options': len(entries), 'prior_dispositions': dict(collections.Counter(e['prior_disposition'] for e in entries)), 'proposed_dispositions': dict(collections.Counter(e['proposed_disposition'] for e in entries)), 'new_source_supported_individual_options': sum(e['delta_vs_prior']['new_individual_native_link'] for e in entries), 'new_supported_platform_record_links': sum(len(e['new_supported_native_matches']) for e in entries), 'source_scope_gaps_or_identity_candidates_retained': sum(not e['delta_vs_prior']['new_individual_native_link'] for e in entries), 'prior_positive_associations_changed': 0, 'prior_positive_downgrades': 0, 'catalogue_options_added_removed_merged': 0, 'six_working_field_groups_preserved': len(entries) * 6, 'six_working_field_groups_changed': 0, 'draft_listing_groups': len(draft_groups), 'draft_only_SKUs': sum(len(g['variants']) for g in draft_groups), 'native_SKUs_invented': 0, 'Shopify_numeric_IDs_invented': 0, 'remote_calls_by_this_worker': 0, 'shared_or_platform_writes': 0}
payload = {'schema': 'boldstone.nonwall-listing-resolution.v1', 'prepared_utc': datetime.now(timezone.utc).isoformat(), 'worker_number': 2, 'status': 'COMPLETE_BOUNDED_EVIDENCE_AUDIT; NO_NATIVE_PLATFORM_WRITE', 'frozen_master': ref(master_path), 'fresh_public_inventory': ref(fresh_path), 'public_boundary_supplement': ref(boundary_path), 'counts': summary, 'entries': entries, 'global_limits': ['Every assigned option occurs once; a formal unresolved/source-gap disposition is not an exact native match.', 'Fresh Squarespace public source contains203products/370variants. Additional numeric-boundary checks added no products. Advertised208 discrepancy and hidden/draft/admin limits remain.', 'Shopify remains a136product/160variant historical export with unexported numeric IDs/quantity null, no connected store/domain and no live absence claim.', 'Maker custom-order metal effects and water-feature services are evidenced generally; generic capabilities do not enumerate an exact native variant/SKU.', 'Two native source links concern the logical kept option scope; physical specification verification remains false and all six working fields are preserved.', 'Owner manufacture/affirmative-working/fixing-choice/weight policies persist. No repetitive blanket approval question is introduced.', 'Other evidence lane owns Cup Ring/Frozen Fish reference provenance/Long image gap. Its sealed role findings add no identity/specification/coverage changes.', 'No decomposition of owner-deferred group/collection photographs, set-SKU reuse or whole-set specification division occurred.']}
save('OPTION_RESOLUTIONS.json', payload)

# Validate the final data independently against raw native sources and frozen options.
checks = []
def check(name, condition, detail=None):
    checks.append({'check': name, 'pass': bool(condition), 'detail': detail})
check('all99 unique assigned option IDs', len(entries) == len({e['option_id'] for e in entries}) == 99)
expected = {o['product_id'] for o in master['options'] if o['current_listing_reconciliation']['overall_disposition'] in {'NO_SUPPORTED_INDIVIDUAL_ASSOCIATION_IN_CHECKED_SOURCES', 'RELATED_FAMILY_ONLY_NO_INDIVIDUAL_MATCH', 'GALLERY_OR_DRAFT_CONTEXT_SALE_UNIT_UNRESOLVED', 'INDIVIDUAL_LISTING_CANDIDATE_SCOPE_UNRESOLVED'}}
check('exact assigned set, no Wall Circle rows', {e['option_id'] for e in entries} == expected and all(not e['canonical_key'].startswith('BC-WALL-CIRCLE|') for e in entries))
check('exactly two new source-supported individual option links', summary['new_source_supported_individual_options'] == 2)
for e in entries:
    _, orig = option_by_id[e['option_id']]
    check('six working fields preserved ' + e['option_id'], e['draft_individual_listing']['six_working_fields'] == orig['master_fields'] and len(orig['master_fields']) == 6)
    check('logical and physical status separate ' + e['option_id'], e['physical_configuration_verified'] is False and all(not m['physical_configuration_verified'] for m in e['new_supported_native_matches']))
    check('draft/native identifiers separate ' + e['option_id'], e['draft_individual_listing']['proposed_sku'] in {None, 'DRAFT-' + e['option_id']})
    check('all options have precise reasons and remaining scope limits ' + e['option_id'], bool(e['scope_reason']) and bool(e['remaining_evidence_gaps']) and bool(e['source_evidence']['frozen_option']))
    for m in e['new_supported_native_matches']:
        if m['platform'] == 'Squarespace':
            pi, p = public_by_id[m['native_product_id']]
            v = next(v for v in p['variants'] if v['native_variant_id'] == m['native_variant_id'])
            check('native product variant SKU triple ' + e['option_id'], v['sku'] == m['sku_raw'] and v['option_attributes'] == m['option_attributes'])
            loc = v['source_locator']
            raw = load(loc['path'], loc['body_sha256'])
            q = raw
            for token in loc['json_pointer'].strip('/').split('/'):
                q = q[int(token)] if isinstance(q, list) else q[token.replace('~1', '/').replace('~0', '~')]
            check('raw native variant readback ' + e['option_id'], q['id'] == m['native_variant_id'] and q['sku'] == m['sku_raw'])
        else:
            check('historical Shopify null unexported IDs ' + e['option_id'], m['numeric_product_id'] is None and m['numeric_variant_id'] is None and m['current_live_inventory_verified'] is False)
            check('historical Shopify source row preserved ' + e['option_id'], m['source_row']['logical_row_including_header'] == 368 and m['sku_raw'] == 'VDR-1-35.20')
all_native_skus = {v['sku'] for p in fresh['products'] for v in p['variants'] if v.get('sku')}
sh_variants_path = ROOT / 'components/parallel-reviews/listing-reconciliation-2026-10-20/worker-02/shopify_variants.json'
all_native_skus |= {v['sku_raw'] for v in load(sh_variants_path) if v.get('sku_raw')}
draft_skus = [v['proposed_sku'] for g in draft_groups for v in g['variants']]
check('draft97 SKUs unique and collide with no checked native SKU', len(draft_skus) == len(set(draft_skus)) == 97 and not set(draft_skus) & all_native_skus)
check('prior positive O009 retained not double counted', prior_positive['prior_positive_association_changed'] is False and prior_positive['included_in_new_positive_count'] is False and 'BSI-4536FDCA0DA9' not in by_id)
check('all fresh O009 image hashes and IDs bound', len(o009['assets']) == 4 and all(a['native_media_id'] in {x['id'] for x in public_by_id['6a4199ab16d56f3a046f502f'][1]['native_media_items']} for a in o009['assets']))
check('B role overlay no coverage changes', b_findings['current_coverage_changes'] == 0)
check('all image inspections have actual file bytes receipts', all(x['visual_review_completed'] and pathlib.Path(x['path']).is_file() and digest(pathlib.Path(x['path']).read_bytes()) == x['local_bytes_receipt']['sha256'] for x in all_inspections))
for p, s in list(sources.items()):
    check('source hash unchanged ' + p, digest(pathlib.Path(p).read_bytes()) == s['sha256'])
validation = {'schema': 'boldstone.nonwall-listing-resolution-validation.v1', 'prepared_utc': datetime.now(timezone.utc).isoformat(), 'status': 'PASS' if all(c['pass'] for c in checks) else 'FAIL', 'counts': {'checks': len(checks), 'passed': sum(c['pass'] for c in checks), 'failed': sum(not c['pass'] for c in checks)}, 'checks': checks, 'summary': summary, 'scope': 'Exact source readback/schema/coverage validation; not physical verification, hidden/admin platform census or independent visual reviewer approval.'}
save('VALIDATION.json', validation)
assert validation['status'] == 'PASS', [c for c in checks if not c['pass']]
save('SOURCE_RECEIPTS.json', {'schema': 'boldstone.nonwall-listing-resolution-source-receipts.v1', 'sources': list(sources.values()), 'all_source_hashes_unchanged_at_final_check': True, 'no_source_files_changed_by_this_worker': True})
output_names = ['OPTION_RESOLUTIONS.json', 'SOURCE_NATIVE_CLAIMS.json', 'CUSTOM_ORDER_COVERAGE.json', 'CHECKED_INVENTORY_SCOPE.json', 'VISUAL_COMPARISONS.json', 'PRIOR_POSITIVE_ASSOCIATION_AUDIT.json', 'DRAFT_LISTING_GROUPS.json', 'SOURCE_RECEIPTS.json', 'VALIDATION.json']
outputs = [receipt(HERE / name) for name in output_names]
save('SEALED_MANIFEST.json', {'schema': 'boldstone.nonwall-listing-resolution-seal.v1', 'sealed_utc': datetime.now(timezone.utc).isoformat(), 'status': 'SEALED_COMPLETE_BOUNDED_LOCAL_EVIDENCE_AUDIT', 'frozen_master_sha256': sources[str(master_path)]['sha256'], 'fresh_public_inventory_sha256': sources[str(fresh_path)]['sha256'], 'counts': summary, 'outputs': outputs, 'remote_calls_by_this_worker': 0, 'shared_writes': 0, 'platform_execution_performed': False, 'review_status_is_not_an_owner_approval_or_physical_specification_certification': True})
print(json.dumps({'status': 'SEALED', 'counts': summary, 'validation': validation['counts'], 'seal': receipt(HERE / 'SEALED_MANIFEST.json'), 'option_resolutions': receipt(HERE / 'OPTION_RESOLUTIONS.json')}, indent=2))
