#!/usr/bin/env python3
"""Audit frozen source/BOM associations; never promote family or set links to variants."""
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter, defaultdict
import hashlib
import json
import re

B = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent
MASTER = B / 'inputs/master-register.json'
MASTER_SHA = '30ff291d6b6fe0aad3a2bc39e121de4ef838c09afceb5f7ab11c78ea7fa71e2c'
raw = MASTER.read_bytes()
assert hashlib.sha256(raw).hexdigest() == MASTER_SHA
g = json.loads(raw)
now = datetime.now(timezone.utc).isoformat()
ledger_binding = g['master_input_manifest']['owner_ledger']
ledger_path = Path(ledger_binding['snapshot'])
ledger_raw = ledger_path.read_bytes()
assert hashlib.sha256(ledger_raw).hexdigest() == ledger_binding['sha256']
ledger = json.loads(ledger_raw)
selected_owner_records = []
for category, indices in [('component_identity_relationship_decisions', [2, 3, 4, 5, 6, 7]), ('finish_reference_equivalence_decisions', [0, 1]), ('dimension_decisions', [20])]:
    for index in indices:
        selected_owner_records.append({'category': category, 'index': index, 'record': ledger[category][index], 'evidence_ref': {'path': str(ledger_path), 'sha256': ledger_binding['sha256'], 'json_pointer': f'/{category}/{index}'}})
options = g['options']
op_by_id = {x['product_id']: x for x in options}
offers = {x['offer_ref']: x for x in g['source_offer_edges']}
offer_indices = {x['offer_ref']: i for i, x in enumerate(g['source_offer_edges'])}
coverage = {x['offer_ref']: x for x in g['source_platform_offer_coverage']}
coverage_indices = {x['offer_ref']: i for i, x in enumerate(g['source_platform_offer_coverage'])}
dispositions = {x['source_component_id']: x for x in g['source_component_dispositions']}
scope_to_ids = defaultdict(set)
component_to_ids = defaultdict(set)
for o in options:
    for scope in o['source_scopes']:
        scope_to_ids[scope].add(o['product_id'])
    for cid in [o.get('canonical_component_id'), o['canonical_key'].split('|')[0]]:
        if cid:
            component_to_ids[cid].add(o['product_id'])
alias_scope_to_ids = defaultdict(set)
for alias in g['aliases']:
    if alias['relationship'] in ['HISTORICAL_FINISH_ALIAS', 'ORIENTATION_OPTION', 'SELECTED_IMAGE_REFERENCE_ALIAS', 'SAME_DESIGN_SOURCE_ALIAS']:
        alias_scope_to_ids[alias['source']].update(t for t in alias['targets'] if t in op_by_id)

# The source-image channel is independent of the nominal product/BOM channel. A retained
# confirmed source image plus an explicit scoped media configuration may resolve the
# photographed design even when old nominal candidate_scope_keys remain ambiguous.
media_bindings = {}
for offer_ref, edge in offers.items():
    c = coverage[offer_ref]; source = edge['source_offer']
    matches = []
    if source.get('image_file_id') and c['source_sale_scope'] == 'Sale component' and 'unresolved' not in source.get('image_state', '').lower():
        for ci, config in enumerate(g['source_media_configuration_coverage']):
            file_match = source['image_file_id'] in config.get('example_file_ids', [])
            folder_match = bool(source.get('image_folder_id') and source['image_folder_id'] in config.get('baseline_solo_folder_ids', []))
            if file_match or folder_match:
                ids = [v for v in config.get('exact_supported_target_ids', []) if v in op_by_id]
                if ids:
                    matches.append({'configuration_index': ci, 'configuration_id': config['configuration_id'], 'source_file_id': source['image_file_id'], 'source_folder_id': source.get('image_folder_id'), 'file_match': file_match, 'solo_folder_match': folder_match, 'product_ids': ids})
    media_bindings[offer_ref] = {'target_ids': sorted({v for m in matches for v in m['product_ids']}), 'evidence': matches, 'binding_basis': 'Retained confirmed source image mapping plus exact file ID or scoped solo-folder association; not a new filename or title inference.'}


def ref(pointer):
    return {'path': str(MASTER), 'sha256': MASTER_SHA, 'json_pointer': pointer}


def source_component_options(cid):
    found = set(component_to_ids.get(cid, set()))
    for target in dispositions.get(cid, {}).get('component_targets', []):
        found.update(component_to_ids.get(target, set()))
    return found


def scope_options(scope):
    return scope_to_ids.get(scope, set()) | alias_scope_to_ids.get(scope, set())


def dimensions(text):
    """Read explicit cross-separated cm claims only; never decode raw unitless cells/SKUs."""
    if not text:
        return None
    text = str(text).split('\n')[0]
    if re.search(r'\b(?:diameter|dia\b|circular)', text, re.I):
        return None
    unit = r'\s*(?:cm)?\s*(?:(?:H|W|D|wide|high|deep)\s*)?'
    match = re.search(r'(\d+(?:\.\d+)?)' + unit + r'[×x]\s*(\d+(?:\.\d+)?)' + unit, text, re.I)
    if not match:
        return None
    face = [float(match.group(1)), float(match.group(2))]
    rest = text[match.end():]
    depth_match = re.match(r'\s*[×x]\s*(\d+(?:\.\d+)?)(?![\d.])', rest)
    depth = None
    if depth_match and not re.match(r'\s*[-–—]\s*\d', rest[depth_match.end():]):
        depth = float(depth_match.group(1))
    return {'recorded_face_numbers_cm': face, 'recorded_single_depth_cm': depth, 'new_axis_assignment': False}


def size_assessment(o, member, cov, source_offer, explicit_scope):
    sources = []
    if member and member['original_bom'].get('component_dimensions_source_cm'):
        sources.append(('BOM_COMPONENT_CLAIM_CM', member['original_bom']['component_dimensions_source_cm']))
    if cov.get('source_each_cm'):
        sources.append(('SOURCE_EACH_COMPONENT_CLAIM_CM', cov['source_each_cm']))
    # Overall dimensions are usable as a single object's source claim only for an actual single sale.
    if cov['source_sale_scope'] == 'Sale component' and cov.get('source_overall_cm'):
        sources.append(('SINGLE_OBJECT_SOURCE_OVERALL_CLAIM_CM', cov['source_overall_cm']))
    if cov['source_sale_scope'] == 'Sale component' and source_offer.get('native_description'):
        sources.append(('DATED_SINGLE_OFFER_DESCRIPTION', source_offer['native_description']))
    parsed_source = next(((kind, text, dimensions(text)) for kind, text in sources if dimensions(text)), None)
    current_text = o['specifications']['Dimensions / depth']['display']
    current = dimensions(current_text)
    known_version = cov['offer_ref'] in {'O046', 'O058', 'O059', 'O079'}
    if known_version and explicit_scope:
        status = 'KNOWN_SOURCE_VS_CURRENT_WORKING_VERSION_CONFLICT'
    elif parsed_source and current:
        src = parsed_source[2]
        if sorted(src['recorded_face_numbers_cm']) != sorted(current['recorded_face_numbers_cm']):
            status = 'SOURCE_FACE_NUMBERS_DIFFER_FROM_CURRENT_WORKING_CLAIM'
        elif src['recorded_single_depth_cm'] is not None and current['recorded_single_depth_cm'] is not None:
            status = 'NUMERIC_DIMENSION_CLAIMS_COMPATIBLE_UNMEASURED' if src['recorded_single_depth_cm'] == current['recorded_single_depth_cm'] else 'FACE_COMPATIBLE_DEPTH_CLAIMS_DIFFER'
        else:
            status = 'FACE_NUMBERS_COMPATIBLE_DEPTH_OR_AXIS_APPLICABILITY_UNRESOLVED'
    else:
        status = 'DIMENSION_APPLICABILITY_NOT_ESTABLISHED'
    return {
        'state': status,
        'option_working_dimensions': current_text,
        'option_parsed_explicit_claim': current,
        'source_dimension_claims': [{'kind': k, 'text': t} for k, t in sources if k != 'DATED_SINGLE_OFFER_DESCRIPTION' or dimensions(t)],
        'source_parsed_explicit_claim': {'kind': parsed_source[0], 'numbers': parsed_source[2]} if parsed_source else None,
        'limits': 'Numeric comparison is of dated source and labelled current working claims, not physical measurement, calibrated image sizing, axis equivalence or proof of a manufactured version. Unitless raw platform cells and SKU numbers are not converted. Whole-set dimensions are never allocated.',
    }


def build_class(o):
    scopes = [x.split('|', 1)[1] if '|' in x else x for x in o['source_scopes']]
    return 'WATER_FEATURE_BUILD' if any('WATER-FEATURE' in s or '-WATER-' in s or s == 'CHISWICK-WATER' for s in scopes) else 'BUILD_NOT_SEPARATELY_CERTIFIED'


special_notes = {
    'O001': ['Family offer only for the seven WC visual names. The144 native pattern/diameter/lighting rows are separately retained, with no exact WC01–WC07 name-to-pattern alias. Swatch composition equality is not encoded-byte or physical-object equality.'],
    'O003': ['Concave Moon Silver/Bronze is a retained historical finish alias into MCP4 Silver/Bronze25; it does not create another Concave product or transfer50cm White dimensions.'],
    'O006': ['The source has blank image_file_id and image_folder_id and explicit exact-file-unresolved state. Both current MCP4 Verdigris25 and Verdigris/Rust are25cm scopes; the owner equivalence covers G216/G217 and former Concave G052/G053 files only. No exact source image joins this offer to either file set.'],
    'O007': ['Green/verdigris listing cannot be assigned to a pure Verdigris option invented from the existing Verdigris/Rust review.'],
    'O008': ['Blue title is historically associated with MCP2 Verdigris/Rust source image scope; it is not authority to match the separate Blue Splashes option by title.'],
    'O010': ['Gallery proposes three members while text says each; source sale quantity remains unresolved.'],
    'O015': ['Photographed design is bound to Moon Water Catcher White by retained confirmed hero file id:cnqzTNngPVsAAAAAAArqUQ, folder id:cnqzTNngPVsAAAAAAAyiQg and CFG-DC03A2397C. Select that photographed identity, while title/SKU/intended-Concave BOM and50×50 claims remain conflicting nominal evidence. Concave→MCP4 consolidation does not turn this hero into MCP4 White25 or resolve its current51×48 configuration conflict.'],
    'O017': ['Four set positions include documented repeated/rotated mould geometry. Current three raked-design options are not four independent variants; preserve original BOM positions.'],
    'O020': ['Two30cm source members do not by themselves quote the later45×40 Timeless option. Preserve member size/version limits.'],
    'O028': ['Two-panel35cm set uses LF1/LF2 opposite orientations of one White option; set quantity remains two, current logical option remains one. Set£600 and mass are not divided.'],
    'O030': ['Five set positions map four current public Moonphase designs: historical MP1 and MP5 both map current Moonphase Four. No fifth current design/SKU invented.'],
    'O034': ['BS-2P-55.85 and Shopify handle test-4 describe the pair only. Bone1/Bone2 are separate current enquiry records without established individual source offers; no set price/mass apportionment.'],
    'O039': ['Another source offer points at the same Gold design scope as O002; compare exact product IDs, raw copy and version evidence before considering duplicate or alias.'],
    'O040': ['Hero is Moonspiral Two even though SKU is MS-1-70.50. Mixed two-panel gallery views are context; literal number matching must not select Moonspiral One.'],
    'O046': ['GS-1-30.30 source30×30 differs from current owner-confirmed45×40. Accepted£250 is a working ask for current size, not a confirmed old-SKU quote for45×40.'],
    'O051': ['O051/O067 reuse EBAY-188654649217. Equal historical SKU/source image is a duplicate-review candidate, not proof of current duplicate live listings.'],
    'O053': ['Palm Form One source is associated with current BC-DP-PALM2; retain the documented crosswalk rather than number/title joining.'],
    'O054': ['Palm Form Two source is associated with current BC-DP-PALM1; retain the documented crosswalk rather than number/title joining.'],
    'O055': ['Native parts cell says1, but retained sale scope/BOM is a multi-component arrangement. Do not use raw parts alone as an individual-product decision.'],
    'O056': ['Native parts cell says1, but retained sale scope/BOM is a multi-component arrangement.'],
    'O057': ['Echo gallery proposes two members, but text says each; no certified one-member or pair variant selected.'],
    'O058': ['LF-1-40.20 copy is40×20×6 and gypsum; current White standard is35×35×6 with AC730 working hypothesis. The current£350 working ask does not make this an exact size/material quote.'],
    'O059': ['Moonwater source circular50×8 and gypsum copy differs from current rectangular51×48 maker/working version.'],
    'O064': ['Silver/Bronze source is associated through retained Concave→MCP4 finish alias, not title similarity or an independent Concave design.'],
    'O067': ['O051/O067 reuse EBAY-188654649217; retain both source records pending native duplicate verification.'],
    'O070': ['Historic plain moon numbers MP1/MP5 consolidate into current Moonphase Four. Silver single source does not match bordered, White or Gold options automatically.'],
    'O072': ['Raw native parts1 is not authority to turn the retained Echo arrangement into a standalone member SKU.'],
    'O079': ['BWS-1-55.55 source55×55 is not current80W×60H. Accepted£1,100 is an independent current working proposal, not an exact native55cm quote.'],
    'SH-DRAFT': ['Historical blank-SKU triptych draft is context/member evidence only; no exact current individual Long/Short variant match.'],
}

edge_rows = []
option_rows = []
for oi, o in enumerate(options):
    pid = o['product_id']
    related_edges = []
    for offer_ref, edge in offers.items():
        cov = coverage[offer_ref]
        source = edge['source_offer']
        source_scopes = cov.get('candidate_current_review_scope_keys', [])
        scope_matches = [s for s in source_scopes if pid in scope_options(s)]
        supported = pid in cov.get('exact_supported_target_ids', [])
        family_ids = set(cov.get('covered_family_product_ids', [])) | set(cov.get('related_product_ids', []))
        overlay = g.get('master_platform_association_overlays', {}).get(offer_ref, {})
        overlay_related = pid in overlay.get('related_option_ids', [])
        media = media_bindings[offer_ref]
        media_bound = len(media['target_ids']) == 1 and pid in media['target_ids']
        member_matches = []
        for mi, member in enumerate(edge['members']):
            ids = source_component_options(member['source_component_id'])
            for cid in member.get('canonical_component_targets', []):
                ids.update(component_to_ids.get(cid, set()))
            if pid in ids or member['source_component_id'] in {s.split('|')[0] for s in o['source_scopes']}:
                member_matches.append((mi, member))
        if not (scope_matches or supported or pid in family_ids or overlay_related or member_matches or media_bound):
            continue
        source_scope = cov['source_sale_scope']
        set_offer = source_scope == 'Sale arrangement components'
        historical = offer_ref == 'SH-DRAFT' or 'blank description/SKU' in source_scope.lower()
        gallery = 'unresolved' in source_scope.lower() or 'Gallery' in source_scope
        scoped = bool(scope_matches or supported or media_bound)
        member = member_matches[0][1] if len(member_matches) == 1 else None
        size = size_assessment(o, member, cov, source, scoped)
        # Multiple original BOM positions remain intact; only a source-equivalent explicit claim can be used.
        if len(member_matches) > 1:
            dimensions_set = {m['original_bom'].get('component_dimensions_source_cm', '') for _, m in member_matches}
            if len(dimensions_set) == 1:
                size = size_assessment(o, member_matches[0][1], cov, source, scoped)
        conflict = size['state'] in {'KNOWN_SOURCE_VS_CURRENT_WORKING_VERSION_CONFLICT', 'SOURCE_FACE_NUMBERS_DIFFER_FROM_CURRENT_WORKING_CLAIM', 'FACE_COMPATIBLE_DEPTH_CLAIMS_DIFFER'}
        ambiguous = bool(cov.get('flags')) and not supported and offer_ref not in {'O034'}
        if offer_ref == 'O015' and media_bound:
            relation = 'BOUND_PHOTOGRAPHED_DESIGN_CURRENT_CONFIGURATION_CONFLICT'
        elif offer_ref == 'O015':
            relation = 'CONFLICTING_TITLE_OR_INTENDED_BOM_ONLY_NOT_THE_BOUND_HERO_DESIGN'
        elif o.get('option_family_id') == 'BC-WALL-CIRCLE' or o['canonical_key'].startswith('BC-WALL-CIRCLE|'):
            relation = 'FAMILY_OFFER_ONLY_EXACT_VISUAL_NATIVE_PATTERN_ALIAS_UNRESOLVED'
        elif historical:
            relation = 'HISTORICAL_DRAFT_CONTEXT_MEMBER_ASSOCIATION'
        elif gallery:
            relation = 'GALLERY_MEMBER_ASSOCIATION_SALE_UNIT_UNRESOLVED'
        elif not scoped:
            relation = 'SIBLING_OR_FAMILY_OPTION_ASSOCIATION_ONLY'
        elif set_offer:
            relation = 'SOURCE_SET_MEMBER_SCOPE_ASSOCIATION'
        elif conflict:
            relation = 'SINGLE_SOURCE_OFFER_CURRENT_VERSION_CONFLICT'
        elif (supported or media_bound) and (not ambiguous or media_bound):
            relation = 'SOURCE_SUPPORTED_STANDALONE_OPTION_CANDIDATE'
        else:
            relation = 'SINGLE_SOURCE_OFFER_SCOPE_CANDIDATE_UNRESOLVED'
        sku = source.get('sku', cov.get('source_sku', ''))
        exact_media = bool(o.get('file_id') and o.get('file_id') == cov.get('source_image_file_id'))
        bom_media = [m['original_bom']['bom_id'] for _, m in member_matches if o.get('file_id') and o['file_id'] in str(m['original_bom'].get('example_file_ids', '')).splitlines()]
        alias_refs = [ref(f'/aliases/{i}') for i, a in enumerate(g['aliases']) if a['source'] in source_scopes and pid in a['targets']]
        join_basis = []
        if scope_matches: join_basis.append({'kind': 'EXPLICIT_CURRENT_REVIEW_SCOPE_ASSOCIATION', 'source_scopes': scope_matches})
        if supported: join_basis.append({'kind': 'RETAINED_SUPPORTED_DESIGN_FINISH_TARGET', 'limits': cov.get('exact_supported_target_basis')})
        if member_matches: join_basis.append({'kind': 'RETAINED_SOURCE_BOM_COMPONENT_DISPOSITION', 'bom_ids': [m['original_bom']['bom_id'] for _, m in member_matches]})
        if pid in family_ids: join_basis.append({'kind': 'RETAINED_FAMILY_OR_RELATED_OPTION_TARGET'})
        if overlay_related: join_basis.append({'kind': 'EXPLICIT_MASTER_ASSOCIATION_OVERLAY', 'mapping_state': overlay['mapping_state'], 'exact_upgrade': overlay.get('exact_individual_match_upgraded')})
        if media_bound: join_basis.append({'kind': 'BOUND_RETAINED_SOURCE_HERO_DESIGN', 'configuration_ids': [m['configuration_id'] for m in media['evidence']], 'source_image_file_id': source.get('image_file_id'), 'source_image_folder_id': source.get('image_folder_id')})
        row = {
            'edge_id': f'{pid}::{offer_ref}', 'product_id': pid, 'canonical_key': o['canonical_key'], 'offer_ref': offer_ref,
            'source_offer_identity': {'squarespace_product_id': cov.get('squarespace_id'), 'shopify_handle': cov.get('shopify_handle'), 'source_sku': sku, 'source_title': cov['source_title'], 'source_url': cov['source_url'], 'source_platform_label': cov['platform']},
            'relationship': relation, 'join_basis': join_basis,
            'separate_join_dimensions': {
                'listing_presence_freshness': 'PRESERVED_DATED_SOURCE_RECORD; NATIVE_CURRENT_INVENTORY_CHECK_REQUIRED',
                'design_image_identity': 'BOUND_TO_THIS_CURRENT_DESIGN_FINISH_SCOPE' if media_bound else 'CONFLICTING_NOMINAL_TITLE_BOM_ONLY' if offer_ref == 'O015' else 'RETAINED_DESIGN_FINISH_SCOPE_ASSOCIATION' if supported else 'CANDIDATE_SCOPE_ONLY' if scoped else 'FAMILY_OR_SIBLING_SCOPE_ONLY',
                'exact_configuration_compatibility': 'SOURCE_CURRENT_WORKING_CLAIM_CONFLICT' if conflict else 'NATIVE_VISUAL_PATTERN_ALIAS_UNRESOLVED' if offer_ref == 'O001' else 'NOT_FULLY_ESTABLISHED_BY_EXISTING_SOURCE_EVIDENCE',
                'sale_unit_scope': 'SET_MEMBER_ONLY' if set_offer else 'GALLERY_SALE_QUANTITY_UNRESOLVED' if gallery else 'HISTORICAL_DRAFT' if historical else 'SINGLE_SOURCE_OFFER',
            },
            'existing_source_listing_correction_candidate': bool(conflict and scoped and (supported or media_bound)),
            'product_design_match_is_not_erased_by_configuration_conflict': bool(scoped and (supported or media_bound)),
            'matching_original_bom_rows': [{'bom_id': m['original_bom']['bom_id'], 'source_component_id': m['source_component_id'], 'position': m['position'], 'quantity': m['quantity'], 'member_scope': m['original_bom']['scope'], 'source_component_dimensions_cm': m['original_bom'].get('component_dimensions_source_cm')} for _, m in member_matches],
            'compatibility': {
                'product_id': {'state': 'DATED_SOURCE_PLATFORM_PRODUCT_ID_RECORDED_NOT_NEWLY_ACCOUNT_VERIFIED' if cov.get('squarespace_id') else 'SOURCE_PRODUCT_ID_NOT_RECORDED', 'source_id': cov.get('squarespace_id')},
                'sku': {'state': 'SET_OR_ARRANGEMENT_SKU_NOT_INDIVIDUAL_MEMBER_SKU' if set_offer else 'HISTORICAL_SOURCE_SKU_CANDIDATE_NOT_EXACT_CURRENT_VARIANT_PROOF' if sku else 'NO_SOURCE_SKU', 'value': sku, 'exact_current_option_variant_id': None},
                'design': {'state': 'BOUND_RETAINED_SOURCE_HERO_DESIGN' if media_bound else 'CONFLICTING_NOMINAL_TITLE_OR_BOM_NOT_THE_BOUND_PHOTOGRAPHED_DESIGN' if offer_ref == 'O015' else 'EXPLICIT_SCOPED_DESIGN_ASSOCIATION' if scoped else 'EXPLICIT_COMPONENT_FAMILY_ASSOCIATION_ONLY', 'title_similarity_used': False},
                'finish': {'state': 'SOURCE_REVIEW_FINISH_SCOPE_SUPPORTED_CHEMISTRY_NOT_CERTIFIED' if supported or media_bound else 'SOURCE_FINISH_SCOPE_CANDIDATE_UNRESOLVED' if scoped else 'OTHER_OR_UNSPECIFIED_REVIEW_FINISH_SCOPE', 'current_source_scopes': o['source_scopes'], 'associated_source_review_scopes': source_scopes},
                'size': size,
                'build': {'state': 'DISTINCT_CURRENT_WATER_FEATURE_BUILD_NOT_COVERED_BY_SIBLING_ASSOCIATION' if build_class(o) == 'WATER_FEATURE_BUILD' and not scoped else 'REVIEW_OPTION_ASSOCIATED_BUILD_APPLICABILITY_NOT_INDEPENDENTLY_CERTIFIED' if scoped else 'BUILD_SCOPE_UNRESOLVED', 'current_build_evidence_class': build_class(o), 'limits': 'Water-feature, standard wall, lighting and hardware choices are not interchangeable. Standing working approval does not certify source platform variant identity.'},
                'orientation': {'state': 'CURRENT_ORIENTATION_CHOICE_RETAINS_SOURCE_SET_POSITIONS' if o.get('orientation_options') else 'ORIGINAL_SOURCE_BOM_POSITION_RETAINED_NO_NEW_ALIAS', 'current_orientation_options': o.get('orientation_options', [])},
                'sale_unit': {'state': 'SET_MEMBER_NOT_STANDALONE' if set_offer else 'UNRESOLVED_GALLERY_SALE_QUANTITY' if gallery else 'HISTORICAL_DRAFT' if historical else 'SINGLE_SOURCE_SALE_COMPONENT', 'source_sale_scope': source_scope, 'native_parts_raw': cov.get('native_parts'), 'source_bom_position_count': len(edge['members'])},
            },
            'media_evidence': {'same_stable_source_hero_file_id': exact_media, 'option_primary_in_bom_example_rows': bom_media, 'bound_source_hero_product_ids': media['target_ids'], 'unique_bound_hero_target_for_this_option': media_bound, 'scoped_media_configuration_evidence': media['evidence'], 'limits': 'Bound photographed identity remains separate from physical size, material, build, intended sale unit and exact current platform variant.'},
            'source_match_flags_retained': cov.get('flags', []), 'source_cautions_retained': cov.get('source_cautions'), 'source_audit_notes_retained': cov.get('audit_notes', []), 'historical_source_flags_do_not_reverse_current_identity_or_specification_acceptance': True,
            'special_join_limits': special_notes.get(offer_ref, []), 'source_scope_notes': cov.get('scope_note'),
            'exact_current_platform_variant_match_certified': False, 'new_platform_variant_id_invented': False,
            'count_increment': 0, 'evidence_refs': [ref(f'/options/{oi}'), ref(f'/source_offer_edges/{offer_indices[offer_ref]}'), ref(f'/source_platform_offer_coverage/{coverage_indices[offer_ref]}')] + alias_refs + [ref(f"/source_media_configuration_coverage/{m['configuration_index']}") for m in media['evidence']],
        }
        related_edges.append(row);edge_rows.append(row)
    relations = {r['relationship'] for r in related_edges}
    if 'FAMILY_OFFER_ONLY_EXACT_VISUAL_NATIVE_PATTERN_ALIAS_UNRESOLVED' in relations:
        disposition = 'WALL_CIRCLE_FAMILY_ASSOCIATION_EXACT_VISUAL_VARIANT_UNRESOLVED'
    elif 'SOURCE_SUPPORTED_STANDALONE_OPTION_CANDIDATE' in relations:
        disposition = 'RETAINED_STANDALONE_OPTION_CANDIDATE_FOR_NATIVE_VERIFICATION'
    elif 'SINGLE_SOURCE_OFFER_SCOPE_CANDIDATE_UNRESOLVED' in relations:
        disposition = 'RETAINED_SINGLE_OFFER_CANDIDATE_SCOPE_UNRESOLVED'
    elif 'SINGLE_SOURCE_OFFER_CURRENT_VERSION_CONFLICT' in relations:
        disposition = 'RETAINED_SINGLE_OFFER_CURRENT_WORKING_VERSION_CONFLICT'
    elif 'BOUND_PHOTOGRAPHED_DESIGN_CURRENT_CONFIGURATION_CONFLICT' in relations:
        disposition = 'EXISTING_SOURCE_PHOTOGRAPHED_DESIGN_CORRECTION_CANDIDATE'
    elif 'SOURCE_SET_MEMBER_SCOPE_ASSOCIATION' in relations:
        disposition = 'SET_MEMBER_ONLY_IN_RETAINED_SCOPED_SOURCES'
    elif related_edges and relations <= {'HISTORICAL_DRAFT_CONTEXT_MEMBER_ASSOCIATION', 'GALLERY_MEMBER_ASSOCIATION_SALE_UNIT_UNRESOLVED'}:
        disposition = 'GALLERY_OR_HISTORICAL_CONTEXT_ONLY'
    elif related_edges:
        disposition = 'ONLY_SIBLING_FAMILY_OR_CONTEXT_SCOPE_ASSOCIATIONS'
    else:
        disposition = 'NO_RETAINED_SOURCE_OFFER_ASSOCIATION'
    non_offer = []
    for ai, alias in enumerate(g['aliases']):
        if pid in alias['targets'] or o.get('canonical_component_id') in alias['targets']:
            non_offer.append({'kind': 'RETAINED_ALIAS_OR_FAMILY_RELATION', 'relationship': alias['relationship'], 'source': alias['source'], 'targets': alias['targets'], 'reason': alias['reason'], 'creates_listing_edge': False, 'evidence_ref': ref(f'/aliases/{ai}')})
    for mi, member in enumerate(g['confirmed_arrangement_member_edges']):
        if member['product_id'] == pid:
            non_offer.append({'kind': 'CONFIRMED_ARRANGEMENT_MEMBER_REFERENCE', 'reference_id': member['reference_id'], 'relationship': member['relationship'], 'creates_listing_edge': False, 'confirms_same_physical_cast': member['confirms_same_physical_cast'], 'evidence_ref': ref(f'/confirmed_arrangement_member_edges/{mi}')})
    for entry in selected_owner_records:
        d = entry['record']
        if d.get('component_id', '').startswith('BC-LUCIANO-') and d.get('canonical_component_id') == o.get('canonical_component_id'):
            non_offer.append({'kind': 'SCOPED_HISTORICAL_PROJECT_POSITION_REFERENCE', 'source': d['component_id'], 'canonical_component_id': d['canonical_component_id'], 'position': d['position'], 'position_owner_stated': d['position_owner_stated'], 'position_basis': d['position_basis'], 'individual_finish_assigned': d['individual_finish_assigned_by_this_correction'], 'same_physical_cast_or_mould_confirmed': d['same_physical_cast_or_mould_confirmed'], 'creates_listing_edge': False, 'evidence_ref': entry['evidence_ref']})
    safe = sorted({v['kind'] for r in related_edges for v in r['join_basis']})
    unsafe = []
    for r in related_edges:
        if r['relationship'] != 'SOURCE_SUPPORTED_STANDALONE_OPTION_CANDIDATE': unsafe.append({'offer_ref': r['offer_ref'], 'reason': r['relationship']})
        if r['compatibility']['size']['state'] in {'KNOWN_SOURCE_VS_CURRENT_WORKING_VERSION_CONFLICT', 'SOURCE_FACE_NUMBERS_DIFFER_FROM_CURRENT_WORKING_CLAIM', 'FACE_COMPATIBLE_DEPTH_CLAIMS_DIFFER'}: unsafe.append({'offer_ref': r['offer_ref'], 'reason': r['compatibility']['size']['state']})
        if r['source_match_flags_retained']: unsafe.append({'offer_ref': r['offer_ref'], 'reason': 'RETAINED_SOURCE_LIMITS', 'flags': r['source_match_flags_retained']})
    option_rows.append({'product_id': pid, 'canonical_key': o['canonical_key'], 'name': o['name'], 'canonical_component_id': o.get('canonical_component_id'), 'option_family_id': o.get('option_family_id'), 'source_scopes': o['source_scopes'], 'current_scope_mapping': [{'offer_ref': r['offer_ref'], 'current_option_source_scopes': o['source_scopes'], 'source_review_scope_keys': r['compatibility']['finish']['associated_source_review_scopes'], 'source_hero_design_target_ids': r['media_evidence']['bound_source_hero_product_ids'], 'relationship': r['relationship']} for r in related_edges], 'disposition': disposition, 'listing_presence_and_freshness': {'retained_source_association_present': bool(related_edges), 'freshness_scope': 'Dated frozen81-offer source only; native inventory lanes supply current SS and snapshot/current Shopify status', 'live_absence_or_live_duplicate_claimed': False}, 'source_offer_refs': [r['offer_ref'] for r in related_edges], 'standalone_candidate_offer_refs': [r['offer_ref'] for r in related_edges if r['relationship'] == 'SOURCE_SUPPORTED_STANDALONE_OPTION_CANDIDATE'], 'set_member_offer_refs': [r['offer_ref'] for r in related_edges if r['relationship'] == 'SOURCE_SET_MEMBER_SCOPE_ASSOCIATION'], 'safe_identity_reasons': safe, 'unsafe_exact_configuration_reasons': unsafe, 'no_exact_current_variant_evidenced_by_this_lane': True, 'exact_source_variant_ids_attached': [], 'candidate_edge_ids': [r['edge_id'] for r in related_edges], 'non_offer_relations': non_offer, 'owner_working_approval_is_not_platform_match': True, 'evidence_ref': ref(f'/options/{oi}')})

# Reverse coverage preserves all81 offers and all122 original positions, including repeated geometries.
offer_rows = []
for offer_ref, source_edge in offers.items():
    rows = [r for r in edge_rows if r['offer_ref'] == offer_ref]
    members = []
    for mi, m in enumerate(source_edge['members']):
        members.append({'bom_id': m['original_bom']['bom_id'], 'source_component_id': m['source_component_id'], 'canonical_component_targets': m['canonical_component_targets'], 'position': m['position'], 'quantity': m['quantity'], 'source_bom_record': m['original_bom'], 'related_current_option_ids': [r['product_id'] for r in rows if m['original_bom']['bom_id'] in [v['bom_id'] for v in r['matching_original_bom_rows']]], 'evidence_ref': ref(f'/source_offer_edges/{offer_indices[offer_ref]}/members/{mi}')})
    offer_rows.append({'offer_ref': offer_ref, 'source_offer': source_edge['source_offer'], 'source_sale_scope': coverage[offer_ref]['source_sale_scope'], 'original_bom_positions': members, 'candidate_option_edge_ids': [r['edge_id'] for r in rows], 'exact_current_option_variant_match_certified': False, 'evidence_refs': [ref(f'/source_offer_edges/{offer_indices[offer_ref]}'), ref(f'/source_platform_offer_coverage/{coverage_indices[offer_ref]}')]})

duplicate_clusters = []
for label, field in [('SOURCE_SQUARESPACE_PRODUCT_ID', 'squarespace_id'), ('SOURCE_SHOPIFY_HANDLE', 'shopify_handle'), ('SOURCE_SKU', 'source_sku'), ('SOURCE_IMAGE_FILE_ID', 'source_image_file_id')]:
    buckets = defaultdict(list)
    for offer_ref, c in coverage.items():
        if c.get(field):buckets[str(c[field])].append(offer_ref)
    for value, refs in buckets.items():
        if len(refs) > 1:
            duplicate_clusters.append({'axis': label, 'source_value': value, 'source_offer_refs': refs, 'meaning': 'Same retained source key/image across source records; check exact native product/variant identity and current state before declaring duplicate live offers or merging records.', 'count_increment': 0})

source_binding = {'path': str(MASTER), 'sha256': MASTER_SHA, 'bytes': len(raw)}
payload = {'schema': 'boldstone.all184-existing-source-option-offer-evidence.v1', 'prepared_utc': now, 'worker_number': 3, 'scope': 'Frozen local source/BOM evidence audit only. Parent native inventory lanes decide actual current SS/Shopify variant joins.', 'source_binding': source_binding, 'scoped_owner_evidence_binding': {'path': str(ledger_path), 'sha256': ledger_binding['sha256']}, 'title_similarity_used_for_joins': False, 'option_associations': {r['product_id']: r for r in option_rows}, 'records': option_rows, 'candidate_edges': edge_rows, 'counts': {'options': len(option_rows), 'source_offers': len(offer_rows), 'original_bom_positions': sum(len(r['original_bom_positions']) for r in offer_rows), 'candidate_edges': len(edge_rows), 'option_dispositions': dict(Counter(r['disposition'] for r in option_rows)), 'edge_relationships': dict(Counter(r['relationship'] for r in edge_rows)), 'exact_current_variant_matches_certified_by_this_lane': 0}, 'global_limits': ['No missing-live-listing or live-duplicate conclusion is drawn from this dated81-offer source snapshot.', 'Source supported target IDs mean retained design/finish scope evidence, not exact account variant/specimen certification.', 'All current names, owner specification acceptances, manufacture policies, option counts and source histories remain unchanged.', 'Matching source IDs/SKUs, finish wording and numeric dimensions are separate checks. Native/current inventory must settle product and variant IDs.', 'No whole-set price, weight, dimensions or stock are allocated to an individual member.', 'Unscaled images, file/folder names, gallery membership and accepted guesses do not establish variant compatibility.'], 'shared_writes': 0, 'remote_reads': 0, 'remote_writes': 0}
reverse = {'schema': 'boldstone.all81-source-offer-bom-reverse-evidence.v1', 'prepared_utc': now, 'source_binding': source_binding, 'offers': offer_rows, 'duplicate_key_review_clusters': duplicate_clusters, 'wall_circle_native_family_layer': {'source_offer_ref': 'O001', 'native_rows': g['wall_circle_native_options'], 'native_row_count': len(g['wall_circle_native_options']), 'current_visual_option_ids': [r['product_id'] for r in option_rows if r['canonical_key'].startswith('BC-WALL-CIRCLE|')], 'exact_visual_option_aliases_established': 0, 'count_treatment': '144 source combinations and seven visual options overlap; neither an extra family product nor144 mapped current appearances is created.', 'evidence_ref': ref('/wall_circle_native_options')}}
assert len(option_rows) == 184 and len({r['product_id'] for r in option_rows}) == 184
assert len(offer_rows) == 81 and sum(len(r['original_bom_positions']) for r in offer_rows) == 122
assert len({r['edge_id'] for r in edge_rows}) == len(edge_rows)
assert hashlib.sha256(MASTER.read_bytes()).hexdigest() == MASTER_SHA
OUT.mkdir(parents=True, exist_ok=True)
owner_evidence = {'schema': 'boldstone.scoped-owner-source-alias-evidence.v1', 'source_binding': {'path': str(ledger_path), 'sha256': ledger_binding['sha256']}, 'records': selected_owner_records, 'application_limits': ['Concave design consolidation and finish-file equivalence do not bind an offer whose exact source file is unknown.', 'Luciano displayed-position references do not assign White/Sandstone finish, current SKU, dimensions or physical cast equality.', 'Moonshell Lava arrangement member references do not create a platform listing or an additional product.']}
for filename, obj in [('source_mapping_evidence.json', payload), ('offer_bom_evidence.json', reverse), ('owner_alias_evidence.json', owner_evidence)]:
    (OUT / filename).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'counts': payload['counts'], 'duplicate_key_review_clusters': duplicate_clusters, 'files': [str(OUT / 'source_mapping_evidence.json'), str(OUT / 'offer_bom_evidence.json')]}, ensure_ascii=False, indent=2))
