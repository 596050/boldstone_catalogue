#!/usr/bin/env python3
"""Read existing local evidence; write advisory closure records in this worker only."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

BASE = Path('/Users/tprice/Documents/boldstone/sculpture-catalogue')
OUT = Path(__file__).resolve().parent
PROGRESS = 'components/reviews/specification_review_progress.json'
CLASSIFICATIONS = 'components/reviews/user_classifications.json'
REGISTER = 'components/evidence/component_register.json'
GRAPH = 'components/reconciliation/individual-products-2026-10-20/canonical-products.json'
manifest = {}


def read(rel):
    path = BASE / rel
    raw = path.read_bytes()
    manifest[rel] = {'path': str(path), 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}
    return json.loads(raw)


def ref(rel, locator=None):
    if rel not in manifest:
        read(rel)
    result = {'path': rel, 'sha256': manifest[rel]['sha256']}
    if locator:
        result['json_locator'] = locator
    return result


p, u, register, graph = [read(rel) for rel in [PROGRESS, CLASSIFICATIONS, REGISTER, GRAPH]]
now = datetime.now(timezone.utc).isoformat()
products = {v['product_id']: v for v in graph['products']}
keys = ['dimensions', 'weight', 'material_finish', 'fixing', 'individual_price', 'availability']
graph_keys = dict(zip(keys, ['Dimensions / depth', 'Weight', 'Material / finish', 'Fixing', 'Individual price', 'Availability']))
nodes = {
    'chelsea': p['reviews']['BC-CHELSEA'],
    'golden': p['reviews']['BC-DP-SPIRAL']['size_finish_variants']['DP-SPIRAL-GOLD-45x40'],
    'leaf_lf1': p['reviews']['BC-LEAF-FORM']['component_layouts']['LEAF-FORM-LF1-WHITE'],
    'leaf_lf2': p['reviews']['BC-LEAF-FORM']['component_layouts']['LEAF-FORM-LF2-WHITE'],
    'bone': p['reviews']['BC-BONE-WATER'],
}
node_locators = {
    'chelsea': "$.reviews['BC-CHELSEA']",
    'golden': "$.reviews['BC-DP-SPIRAL'].size_finish_variants['DP-SPIRAL-GOLD-45x40']",
    'leaf_lf1': "$.reviews['BC-LEAF-FORM'].component_layouts['LEAF-FORM-LF1-WHITE']",
    'leaf_lf2': "$.reviews['BC-LEAF-FORM'].component_layouts['LEAF-FORM-LF2-WHITE']",
    'bone': "$.reviews['BC-BONE-WATER']",
}
standing = p['working_specification_acceptance_policy']
fixing_policy = p['global_fixing_choice_policy']
weight_policy = p['global_approximate_weight_policy']
policies = [standing, fixing_policy, weight_policy]
policy_refs = {v['policy_id']: ref(v['approval_record']) for v in policies}
ledger_indices = {
    'chelsea': [('specification_decisions', 4), ('dimension_decisions', 2), ('conditional_weight_estimate_decisions', 7)],
    'golden': [('dimension_decisions', 5), ('size_finish_variant_specification_decisions', 0)],
    'leaf': [('size_finish_variant_specification_decisions', 27), ('size_finish_variant_specification_decisions', 28)],
    'bone': [('dimension_decisions', 0), ('specification_decisions', 13)],
}
ledger_snapshots = {}
for case, indices in ledger_indices.items():
    ledger_snapshots[case] = [{'locator': f'$.{key}[{i}]', 'decision': u[key][i]} for key, i in indices]

receipt_paths = {
    'chelsea': [nodes['chelsea']['specification_approval'], 'components/reviews/chelsea-flower-show-dimensions-2026-10-17/dimensions-confirmed.json'],
    'golden': [nodes['golden']['specification_approval'], 'components/reviews/parallel-import-2026-10-17-batch2/decisions/BC-DP-SPIRAL/DP-SPIRAL-GOLD-45x40/dimension-approval.json'],
    'leaf': [nodes['leaf_lf1']['specification_approval'], nodes['leaf_lf2']['specification_approval'], 'components/reviews/leaf-form-review-2026-10-18/lf1-white/component-review.json', 'components/reviews/leaf-form-review-2026-10-18/lf2-white/component-review.json', 'components/reviews/leaf-form-review-2026-10-18/listing-image-comparison.json'],
    'bone': [nodes['bone']['specification_approval'], 'components/reviews/bone-water-spiral-review-2026-10-17/working-face-size-approval.json', 'components/reviews/bone-water-spiral-review-2026-10-17/component-review.json'],
}
receipts = {case: {rel: read(rel) for rel in rels} for case, rels in receipt_paths.items()}

transcript_specs = [
    ('01a144ab-1a7c-7223-a403-73a4d53d70ff', '/Users/tprice/.codex/sessions/2026/10/16/rollout-2026-10-16T13-23-46-01a144ab-1a7c-7223-a403-73a4d53d70ff.jsonl', [4670, 4677, 4829, 4836, 4963, 5084, 5091]),
    ('01a13fbf-1cbc-7511-8416-cf339051083e', '/Users/tprice/.codex/sessions/2026/10/15/rollout-2026-10-15T14-27-31-01a13fbf-1cbc-7511-8416-cf339051083e.jsonl', [9740, 9777, 9795, 18928]),
    ('01a13fe6-495b-7253-b923-31823b4cbca8', '/Users/tprice/.codex/sessions/2026/10/15/rollout-2026-10-15T15-10-19-01a13fe6-495b-7253-b923-31823b4cbca8.jsonl', [29180, 29769, 30053]),
]
transcript_excerpts = []
for session, path, wanted in transcript_specs:
    with Path(path).open() as fh:
        for line_number, raw in enumerate(fh, 1):
            if line_number in wanted:
                payload = json.loads(raw)
                transcript_excerpts.append({'session_id': session, 'path': path, 'line': line_number, 'raw_line_sha256_excluding_line_ending': hashlib.sha256(raw.rstrip('\r\n').encode()).hexdigest(), 'entry': payload})
            if line_number >= max(wanted):
                break
assert len(transcript_excerpts) == sum(len(x[2]) for x in transcript_specs)


def decision_refs(case):
    return [ref(CLASSIFICATIONS, v['locator']) for v in ledger_snapshots[case]]


def proposal_ids(product, field):
    return list(dict.fromkeys(v['proposal_id'] for v in product['specifications'][graph_keys[field]]['assertions']))


def field(case, product, name, display, value, evidence_state, justification, extra_refs=None, limits=None):
    source_nodes = ['leaf_lf1', 'leaf_lf2'] if case == 'leaf' else [case]
    current_review_ids = []
    initial_review_ids = []
    for n in source_nodes:
        initial = nodes[n]['specification_proposals'][keys.index(name)]
        initial_review_ids.append(initial.get('proposal_id', initial.get('id')))
        accepted = nodes[n].get('accepted_working_specifications', {}).get(name, initial)
        current_review_ids.append(accepted.get('proposal_id', accepted.get('id')))
    return {
        'proposed_normalization_id': f'PRICE-SIZE-CLOSURE-20261020:{case.upper()}:{name.upper()}',
        'display': display,
        'value': value,
        'existing_source_proposal_ids': proposal_ids(product, name),
        'current_accepted_review_proposal_ids': current_review_ids,
        'historical_initial_review_proposal_ids': initial_review_ids,
        'evidence_state': evidence_state,
        'owner_policy_justification': justification,
        'basis_refs': decision_refs(case) + [ref(PROGRESS, node_locators[n]) for n in source_nodes] + (extra_refs or []),
        'owner_working_acceptance_only': True,
        'physical_value_verified': False,
        'limits': limits or [],
    }


def record(case, product_id, working_version):
    product = products[product_id]
    return {
        'case_id': f'PRICE-SIZE-CLOSURE-20261020:{case.upper()}',
        'product_id': product_id,
        'canonical_key': product['canonical_key'],
        'name': product['name'],
        'source_scopes': product['source_scopes'],
        'orientation_options': product['orientation_options'],
        'working_version': working_version,
        'sale_unit': 'One panel; one selected orientation where offered',
        'action': 'NORMALIZE_CURRENT_WORKING_DISPLAY_AND_COMMERCIAL_POLICY; preserve all old raw assertions as historical evidence',
        'source_graph_ref': ref(GRAPH, f"$.products[?(@.product_id=='{product_id}') ]"),
        'approval_receipt_refs': [ref(rel) for rel in receipt_paths[case]],
        'owner_policy_refs': list(policy_refs.values()),
        'specifications': {},
        'legacy_source_annotations': [],
        'current_confirmed_platform_quote_gbp': None,
        'repeat_owner_confirmation_required': False,
        'physical_specs_certified': False,
        'current_stock_or_lead_time_certified': False,
        'platform_mapping_changed': False,
        'product_identity_or_count_changed': False,
        'sole_owner_writer_import_required': True,
        'new_individual_owner_reply_event': None,
    }


fixing_display = 'Keyhole fixing or French cleat — owner catalogue choice; actual installed hardware, count, attachment and load rating unverified.'
availability_display = 'Made to order / enquire — accepted working sale policy; finished stock, reproducibility and lead time unknown.'
fixing_value = {'catalogue_choice': ['KEYHOLE', 'FRENCH_CLEAT'], 'installed_hardware': None, 'hardware_count': None, 'load_rating': None}
availability_value = {'working_sale_policy': 'MADE_TO_ORDER_OR_ENQUIRE', 'current_stock_quantity': None, 'lead_time': None, 'reproducibility_verified': False}
records = []

chelsea = record('chelsea', 'BSI-F95020D6821C', 'Owner-confirmed Chelsea reference: 250 cm high × 100 cm wide; depth unknown.')
product = products[chelsea['product_id']]
defs = [
    ('dimensions', '250 cm high × 100 cm wide — owner confirmed; depth unknown.', {'height_cm': 250, 'width_cm': 100, 'depth_cm': None}, 'OWNER_STATED_FACE_DIMENSIONS; DEPTH_UNKNOWN', 'Owner explicitly supplied the larger face and confirmed both the depicted target and height/width orientation. The old 100×50 guess is superseded; the old 10 cm depth is not a measurement.', [], ['No measured maximum projection or packed dimensions.']),
    ('weight', 'Approximately 100 kg dry; broad working range 75–140 kg — conditional estimate for the 250 × 100 cm version; unweighed.', {'nominal_kg': 100, 'range_kg': [75, 140], 'basis': 'CONDITIONAL_COMPARATOR_ESTIMATE', 'dry_artwork_only': True}, 'OWNER_ACCEPTED_CONDITIONAL_WORKING_ESTIMATE', 'Retain the current size-specific estimate accepted under the global weight policy; do not reactivate the superseded 25 kg smaller-size guess.', [policy_refs[weight_policy['policy_id']]], ['Construction and mass remain unknown; not a shipping, operating or load-rated weight; does not apply to source002/G233.']),
    ('material_finish', 'Jesmonite AC730 with a pale stone finish — accepted working hypothesis; actual binder, recipe and reinforcement unverified.', {'working_material_hypothesis': 'Jesmonite AC730', 'working_finish_hypothesis': 'Pale stone finish', 'actual_recipe_verified': False}, 'ACCEPTED_WORKING_HYPOTHESIS', 'Retain the accepted material proposal with its original guess qualification under the standing working policy. No object-specific material certificate exists.', [policy_refs[standing['policy_id']]], ['Related maker templates are comparison evidence; colour in photographs does not establish chemistry.']),
    ('fixing', fixing_display, fixing_value, 'OWNER_CATALOGUE_CHOICE; INSTALLED_SYSTEM_UNKNOWN', 'Apply the later all-sculptures fixing choice; move the earlier two-stainless-fixing guess to evidence only.', [policy_refs[fixing_policy['policy_id']]], ['Neither fixing choice is certified as fitted or load-rated for this particular large panel.']),
    ('individual_price', 'Price on enquiry for the 250 × 100 cm working version.', {'commercial_policy': 'PRICE_ON_ENQUIRY', 'working_ask_gbp': None, 'currency': 'GBP', 'sale_unit': 'One 250 cm high × 100 cm wide panel', 'current_confirmed_quote_gbp': None}, 'OWNER_AUTHORIZED_ENQUIRY_POLICY; NO_APPLICABLE_CURRENT_QUOTE', 'The old £1,100 was a commercial proposal for a superseded 100×50 guess. The later size confirmation explicitly did not confirm price applicability. The current direct user task permits price on enquiry; normalize under that instruction without a repeated permission request.', [policy_refs[standing['policy_id']]], ['No Chelsea native offer or cost model established. The separate Moonwave £800 source is not a Chelsea quote.']),
    ('availability', availability_display, availability_value, 'ACCEPTED_WORKING_SALE_POLICY; STOCK_UNKNOWN', 'Retain the proposed made-to-order/enquire policy under standing acceptance; the photograph and manufacture policy do not establish inventory or delivery timing.', [policy_refs[standing['policy_id']]], ['No current stock, capacity or lead time asserted.']),
]
for args in defs:
    chelsea['specifications'][args[0]] = field('chelsea', product, *args)
chelsea['commercial_policy'] = 'PRICE_ON_ENQUIRY'
chelsea['legacy_source_annotations'] = [
    {'source_version': 'Initial 17 October guessed card', 'raw_claims': {'face_cm': [100, 50], 'depth_guess_cm': 10, 'weight_guess_kg': 25, 'weight_guess_range_kg': [20, 30], 'proposed_price_gbp': 1100, 'fixing_guess': 'Two rear stainless fixings'}, 'disposition': 'Superseded or inapplicable to current larger version; preserve evidence only. The original Keep is historical and does not silently reprice 250×100.', 'basis_refs': [ref(CLASSIFICATIONS, '$.specification_decisions[4]'), ref(CLASSIFICATIONS, '$.dimension_decisions[2]')]},
    {'source_version': 'O016 Moonwave / MW-1-74.35', 'raw_claims': {'price_reference_gbp': 800}, 'disposition': 'Different design and size; no Chelsea identity or commercial transfer.', 'basis_refs': [ref(REGISTER, "$.platform_records[?(@.offer_ref=='O016')]")]},
]
records.append(chelsea)

golden = record('golden', 'BSI-DB7FBD3E1323', 'Owner-corrected 45 × 40 × 5 cm Golden Spiral, White and Gold; retain recorded dimension order.')
product = products[golden['product_id']]
defs = [
    ('dimensions', '45 × 40 × 5 cm — owner confirmed, matching Timeless Spiral; dimension order retained as recorded.', {'dimensions_cm': [45, 40, 5], 'dimension_order': 'As owner-confirmed Timeless reference; new H/W labels not inferred'}, 'OWNER_CONFIRMED_DIMENSIONS', 'The owner corrected the same pictured gold object to the Timeless size. This is a correction of the current working product, not proof of two manufactured size variants.', [], ['No new axes or physical measurement asserted.']),
    ('weight', 'Approximately 10 kg; working range 8–12 kg — revised estimate for 45 × 40 × 5 cm; unweighed.', {'nominal_kg': 10, 'range_kg': [8, 12]}, 'ACCEPTED_WORKING_ESTIMATE', 'The corrected-size approval retains the revised estimate; global weight policy accepts applicable approximations. The 6 kg smaller-version estimate stays retired.', [policy_refs[weight_policy['policy_id']]], ['Actual cast construction and mass unverified.']),
    ('material_finish', 'Gold leaf finish — dated listing description; base material and leaf composition/purity unconfirmed.', {'finish_source_description': 'Gold leaf', 'base_material': None, 'leaf_composition': None, 'leaf_purity': None}, 'ACCEPTED_SOURCE_DESCRIPTION; COMPOSITION_UNKNOWN', 'Retain the accepted source-described finish. No material or metal purity is inferred from pixels or transferred from Timeless White.', [], ['Current object-specific material composition not certified.']),
    ('fixing', fixing_display, fixing_value, 'OWNER_CATALOGUE_CHOICE; INSTALLED_SYSTEM_UNKNOWN', 'Apply the later fixing choice; preserve the earlier concealed-fixing guess as evidence only.', [policy_refs[fixing_policy['policy_id']]], ['No hardware count or load rating established.']),
    ('individual_price', '£250 per panel — owner-accepted working ask for the corrected 45 × 40 × 5 cm version; current quote unverified.', {'commercial_policy': 'ACCEPTED_WORKING_ASK', 'working_ask_gbp': 250, 'currency': 'GBP', 'sale_unit': 'One 45 × 40 × 5 cm Golden Spiral panel', 'current_confirmed_quote_gbp': None}, 'EXPLICIT_OWNER_ACCEPTED_CORRECTED_SIZE_WORKING_PRICE', 'The sealed corrected-size specification decision explicitly accepts GBP250 for this size. Remove the stale needs-approval display; do not relabel the older 30×30 listing as a verified quote for 45×40.', [], ['The acceptance is a working commercial choice; no present platform price was read or asserted.']),
    ('availability', availability_display, availability_value, 'ACCEPTED_WORKING_SALE_POLICY; STOCK_UNKNOWN', 'Retain accepted made-to-order/enquire working policy with stock and lead time unknown.', [policy_refs[standing['policy_id']]], ['No current stock or production schedule asserted.']),
]
for args in defs:
    golden['specifications'][args[0]] = field('golden', product, *args)
golden['commercial_policy'] = 'ACCEPTED_WORKING_ASK'
golden['legacy_source_annotations'] = [
    {'source_version': 'O046 / GS-1-30.30, dated native listing snapshot 16–17 October 2026', 'raw_claims': {'description_dimensions_cm': [30, 30, 5], 'price_gbp': 250, 'old_weight_guess_kg': 6, 'old_weight_guess_range_kg': [5, 7]}, 'disposition': 'Retain the dated source claim and raw export dimensions independently. Its smaller-size applicability is superseded for the working product; the same numeric price is now a distinct owner-accepted working ask, not evidence that the original offer quoted the corrected size.', 'basis_refs': [ref(REGISTER, "$.platform_records[?(@.offer_ref=='O046')]"), ref(CLASSIFICATIONS, '$.dimension_decisions[5]'), ref(CLASSIFICATIONS, '$.size_finish_variant_specification_decisions[0]')]},
    {'source_version': 'O047 Timeless Spiral White / TS-1-45.40', 'raw_claims': {'dimensions_cm': [45, 40, 5], 'price_gbp': 500, 'weight_reference_kg': 10}, 'disposition': 'Owner-designated size comparator only; White price and chemistry not transferred to Golden.', 'basis_refs': [ref(REGISTER, "$.platform_records[?(@.offer_ref=='O047')]")]},
    {'source_version': '2025 retail standard, 45×40', 'raw_claims': {'historic_price_gbp': 345.28, 'estimated_weight_kg': 8}, 'disposition': 'Dated white-standard reference only; neither current Golden price nor object-specific weight.', 'basis_refs': [ref(REGISTER, '$.claims[2972]')]},
]
records.append(golden)

leaf = record('leaf', 'BSI-6581D83760F1', 'Nominal 35 × 35 × 6 cm White standard, one logical product with LF1 / LF2 orientation options; maker side depth range 5–7 cm.')
product = products[leaf['product_id']]
defs = [
    ('dimensions', '35 × 35 × 6 cm nominal per panel — accepted working standard; historical maker side depth 5–7 cm; unmeasured.', {'nominal_dimensions_cm': [35, 35, 6], 'historical_side_depth_range_cm': [5, 7], 'orientation_options': ['LF1', 'LF2']}, 'ACCEPTED_WORKING_SOURCE_STANDARD; UNMEASURED', 'Choose the square maker/pair standard for the current White working product, consistent with both accepted orientation cards. The competing single-listing size remains evidence only; acceptance does not prove it was a typo or another manufactured version.', [ref(REGISTER, '$.claims[125]'), ref(REGISTER, '$.claims[130]')], ['Nominal 6 cm and maker 5–7 cm are not two measured maxima. No current 40×20 product created from conflicting text.']),
    ('weight', '6–8 kg per panel — historical maker calculated estimate for the White standard; unweighed.', {'range_kg': [6, 8], 'per_panel': True, 'basis': 'HISTORICAL_MAKER_CALCULATED_ESTIMATE'}, 'ACCEPTED_WORKING_ESTIMATE', 'Retain maker per-component estimates accepted in both orientation reviews and by global weight policy. Do not divide the pair offer’s total weight.', [ref(REGISTER, '$.claims[127]'), ref(REGISTER, '$.claims[132]'), policy_refs[weight_policy['policy_id']]], ['Actual cast mass not measured.']),
    ('material_finish', 'Jesmonite AC730 with white marble stone finish — accepted working maker-template hypothesis; actual recipe unverified.', {'working_material_hypothesis': 'Jesmonite AC730', 'working_finish_source_description': 'White marble stone finish', 'actual_recipe_verified': False}, 'ACCEPTED_WORKING_MAKER_TEMPLATE; ACTUAL_RECIPE_UNKNOWN', 'Use the historical White standard as the current working material hypothesis. Retain the single-listing gypsum-composite claim in source evidence without presenting both as competing current specifications.', [], ['White marble stone finish describes the source finish, not certified marble composition.']),
    ('fixing', fixing_display, fixing_value, 'OWNER_CATALOGUE_CHOICE; INSTALLED_SYSTEM_UNKNOWN', 'Apply the later owner-wide keyhole/French-cleat choice. Keep the older single small stainless fixing instruction only as historical maker evidence.', [policy_refs[fixing_policy['policy_id']]], ['No fitted hardware, count or load certification for either orientation.']),
    ('individual_price', '£350 per panel — accepted working ask for the nominal 35 × 35 cm White standard, either LF1 or LF2 orientation; current quote unverified.', {'commercial_policy': 'ACCEPTED_WORKING_ASK', 'working_ask_gbp': 350, 'currency': 'GBP', 'sale_unit': 'One White panel in selected LF1 or LF2 orientation', 'current_confirmed_quote_gbp': None}, 'ACCEPTED_WORKING_PROPOSAL_UNDER_STANDING_POLICY', 'Both current orientation approvals accept GBP350 per panel as a working proposal, with exact listing applicability unknown. Retain that commercial choice for the one orientation product. This is not confirmation that O058 quoted the square standard, or that an exact LF2 offer exists.', [policy_refs[standing['policy_id']]], ['Not £300 from dividing a £600 pair. No set price is inherited or recomputed.']),
    ('availability', availability_display, availability_value, 'ACCEPTED_WORKING_SALE_POLICY; STOCK_UNKNOWN', 'Retain both orientations’ accepted made-to-order/enquire policy, with reproduction, stock and lead time unknown.', [policy_refs[standing['policy_id']]], ['No number of physical casts, stock or lead time asserted by the orientation grouping.']),
]
for args in defs:
    leaf['specifications'][args[0]] = field('leaf', product, *args)
leaf['commercial_policy'] = 'ACCEPTED_WORKING_ASK'
leaf['legacy_source_annotations'] = [
    {'source_version': 'O058 Leaf Form / LF-1-40.20, dated 16 October 2026 source', 'raw_claims': {'single_listing_dimensions_cm': [40, 20, 6], 'single_listing_price_gbp': 350, 'material_claim': 'Gypsum composite, stone finish', 'raw_single_export_weight': 4.0}, 'disposition': 'Keep the source size/material/weight conflict and exact listing uncertainty as evidence. No verified typo or distinct manufactured 40×20 version is invented. GBP350 current working ask has separate later policy acceptance.', 'basis_refs': [ref(REGISTER, "$.platform_records[?(@.offer_ref=='O058')]"), ref(REGISTER, '$.claims[1868]'), ref(REGISTER, '$.claims[1871]'), ref(REGISTER, '$.claims[1875]'), ref(REGISTER, '$.claims[1876]'), ref(REGISTER, '$.claims[1877]'), ref(REGISTER, '$.claims[1878]')]},
    {'source_version': 'O028 Two Leaf Forms / LF-2P-35.70', 'raw_claims': {'per_panel_dimensions_cm': [35, 35, 6], 'overall_pair_dimensions_cm': [35, 70, 6], 'pair_price_gbp': 600, 'pair_weight_reference_kg': 16}, 'disposition': 'Pair is context/composition evidence; no pair price or total mass divided into current per-panel fields.', 'basis_refs': [ref(REGISTER, "$.platform_records[?(@.offer_ref=='O028')]")]},
    {'source_version': 'Historical manufacturer LF1 row36 / LF2 row37 and orientation alias row34', 'raw_claims': {'face_mm': [350, 350], 'side_depth_range_mm': [50, 70], 'per_component_estimated_weight_kg': [6, 8], 'fixing_instruction': 'One small stainless rear fixing, centred in upper third', 'orientation_relationship': 'LF2 / LF1 same mould; opposite orientation'}, 'disposition': 'Adopt source standard and estimates as labelled working hypotheses. LF1/LF2 are one current orientation product as requested; do not merge or certify a number of physical casts.', 'basis_refs': [ref(REGISTER, "$.aliases[?(@.component_id=='BC-LEAF-FORM')]"), ref(REGISTER, '$.claims[125]'), ref(REGISTER, '$.claims[130]')]},
    {'source_version': '2025 retail standard, 35×35', 'raw_claims': {'historic_price_gbp': 241.54, 'estimated_weight_kg': 6}, 'disposition': 'Dated comparison only, not the current working ask or measured weight.', 'basis_refs': [ref(REGISTER, '$.claims[2969]')]},
]
records.append(leaf)

bone = record('bone', 'BSI-1E0C826D896E', 'BWS-MAKER-80x60: owner-accepted 80 cm wide × 60 cm high working version; historical estimated side depth 5–8 cm.')
product = products[bone['product_id']]
defs = [
    ('dimensions', '80 cm wide × 60 cm high — owner-accepted working face; approximately 5–8 cm deep — historical maker estimate, unmeasured.', {'width_cm': 80, 'height_cm': 60, 'estimated_side_depth_range_cm': [5, 8], 'max_projection_cm': None}, 'OWNER_ACCEPTED_WORKING_FACE; SOURCE_DEPTH_ESTIMATE', 'Owner Keep was scoped to the 80W×60H working face. The later six-field acceptance retains the maker depth estimate, without measuring the object or resolving the other source sizes.', [ref(REGISTER, '$.claims[23]')], ['Maximum projection and cast-specific measurements remain unknown.']),
    ('weight', '15–20 kg per panel — historical maker calculated estimate for the 80 × 60 cm version; unweighed.', {'range_kg': [15, 20], 'basis': 'HISTORICAL_MAKER_CALCULATED_ESTIMATE'}, 'ACCEPTED_WORKING_ESTIMATE', 'Retain the current B96 estimate and global weight policy acceptance. Do not transfer the square export’s raw number or the trade draft’s 14 kg.', [ref(REGISTER, '$.claims[25]'), policy_refs[weight_policy['policy_id']]], ['No measured mass or shipping weight established.']),
    ('material_finish', 'Jesmonite AC730 with white marble stone finish — accepted working maker-version hypothesis; actual recipe unverified.', {'working_material_hypothesis': 'Jesmonite AC730', 'working_finish_source_description': 'White marble stone finish', 'actual_recipe_verified': False}, 'ACCEPTED_WORKING_MAKER_TEMPLATE', 'Retain the accepted maker-version material as a working source hypothesis; do not certify current chemistry from acceptance or a photograph.', [], ['No actual-cast binder, recipe or reinforcement certificate.']),
    ('fixing', fixing_display, fixing_value, 'OWNER_CATALOGUE_CHOICE; INSTALLED_SYSTEM_UNKNOWN', 'Retain B96’s existing keyhole/French-cleat choice and later global owner instruction; leave old two-stainless-fixing maker instruction in evidence.', [policy_refs[fixing_policy['policy_id']]], ['No hardware count, actual attachment or load rating established.']),
    ('individual_price', '£1,100 per panel — accepted working ask for the 80 × 60 cm version; current quote unverified.', {'commercial_policy': 'ACCEPTED_WORKING_ASK', 'working_ask_gbp': 1100, 'currency': 'GBP', 'sale_unit': 'One 80 cm wide × 60 cm high working-version panel', 'current_confirmed_quote_gbp': None}, 'ACCEPTED_WORKING_COMMERCIAL_PROPOSAL_UNDER_STANDING_POLICY', 'B96 explicitly proposes GBP1100 for the 80×60 working version and accepts it under the standing policy. Retain this independent commercial proposal; the same-number native price is for 55×55 and is not evidence of an 80×60 platform quote.', [policy_refs[standing['policy_id']]], ['No independently established current retail quote for the 80×60 version.']),
    ('availability', availability_display, availability_value, 'ACCEPTED_WORKING_SALE_POLICY; STOCK_UNKNOWN', 'Retain B96’s accepted proposed sale policy. Historic manufacture and native Unlimited/InStock metadata do not establish finished stock or lead time.', [policy_refs[standing['policy_id']]], ['No production capacity, reproducibility, stock or lead time certified.']),
]
for args in defs:
    bone['specifications'][args[0]] = field('bone', product, *args)
bone['commercial_policy'] = 'ACCEPTED_WORKING_ASK'
bone['legacy_source_annotations'] = [
    {'source_version': 'BWS-SQUARE-NATIVE / O079 / BWS-1-55.55', 'raw_claims': {'description_dimensions_cm': [55, 55, 7], 'dated_price_gbp': 1100, 'raw_export_weight': 59.525, 'raw_weight_unit': 'Not encoded by the source cell'}, 'disposition': 'Separate source-version claim retained. No weight conversion or source-price applicability transferred to the selected rectangular version.', 'basis_refs': [ref(REGISTER, "$.platform_records[?(@.offer_ref=='O079')]"), ref(REGISTER, '$.claims[602]'), ref(REGISTER, '$.claims[606]'), ref('components/reviews/bone-water-spiral-review-2026-10-17/component-review.json', '$.source_versions')]},
    {'source_version': 'BWS-MAKER-80x60 / manufacturer Sheet1 row110', 'raw_claims': {'source_face_mm': [600, 800], 'estimated_side_depth_mm': [50, 80], 'calculated_estimated_weight_kg': [15, 20], 'material_standard': 'Jesmonite AC730 white marble stone finish', 'fixing_instruction': 'Two rear stainless fixings'}, 'disposition': 'Selected working face and labelled maker estimates/hypothesis retained. Historical fixing instruction is evidence only beside current catalogue choice.', 'basis_refs': [ref(REGISTER, '$.claims[23]'), ref(REGISTER, '$.claims[25]')]},
    {'source_version': 'BWS-TRADE-110x55 / SCULPTURE TRADE PRICE List 2025, PDF page11', 'raw_claims': {'face_cm': [110, 55], 'estimated_weight_kg': 14, 'trade_price_gbp': 756}, 'disposition': 'Dated trade/size reference only; not current retail price or current selected size. Local rendered page was inspected; no physical/version equivalence inferred from its photograph.', 'basis_refs': [ref('components/reviews/bone-water-spiral-review-2026-10-17/component-review.json', '$.source_versions')]},
]
records.append(bone)

authority = {
    'delegated_current_user_instruction': 'Reconcile remaining size/price conflicts using accepted working values or price on enquiry; Leaf Form LF1/LF2 White is one orientation product. Parent relayed direct user authority on 20 October 2026.',
    'exact_new_user_transcript_locator': None,
    'exact_new_user_locator_to_be_attached_by_sole_owner_writer': True,
    'existing_acceptance_events_reused': True,
    'new_owner_reply_or_approval_event_invented': False,
    'source_conflicts_physically_resolved': False,
    'scope': 'Advisory current working catalogue normalization; no shared import, publication, platform action, stock claim or hardware certification.',
}
source_snapshots = {
    'schema': 'boldstone.four-product-price-size-source-evidence.v1',
    'created_utc': now,
    'source_manifest': manifest,
    'progress_nodes': nodes,
    'classification_decisions': ledger_snapshots,
    'policy_nodes': {v['policy_id']: v for v in policies},
    'receipts': receipts,
    'source_products': [products[v['product_id']] for v in records],
    'source_component_records': [v for v in register['components'] if v['component_id'] in ['BC-CHELSEA', 'BC-DP-SPIRAL', 'BC-LEAF-FORM', 'BC-BONE-WATER']],
    'source_offer_records': [v for v in register['platform_records'] if v['offer_ref'] in ['O016', 'O028', 'O046', 'O047', 'O058', 'O079']],
    'raw_claims': [{'source_index': i, 'claim': v} for i, v in enumerate(register['claims']) if v['component_id'] in ['BC-CHELSEA', 'BC-DP-SPIRAL', 'BC-LEAF-FORM', 'BC-BONE-WATER']],
    'orientation_aliases': [v for v in register['aliases'] if v['component_id'] == 'BC-LEAF-FORM'],
    'transcript_excerpts': transcript_excerpts,
}
assert len(records) == 4
assert {r['product_id'] for r in records} == {'BSI-F95020D6821C', 'BSI-DB7FBD3E1323', 'BSI-6581D83760F1', 'BSI-1E0C826D896E'}
assert all(set(r['specifications']) == set(keys) for r in records)
assert all(f['existing_source_proposal_ids'] for r in records for f in r['specifications'].values())
assert all(not f['physical_value_verified'] for r in records for f in r['specifications'].values())
assert leaf['specifications']['individual_price']['existing_source_proposal_ids'] == ['LEAF-FORM-LF1-WHITE-PRICE', 'LEAF-FORM-LF2-WHITE-PRICE']
assert leaf['specifications']['individual_price']['current_accepted_review_proposal_ids'] == ['LEAF-FORM-LF1-WHITE:INDIVIDUAL_PRICE', 'LEAF-FORM-LF2-WHITE:INDIVIDUAL_PRICE']
assert 'GBP250 accepted as working individual price for the corrected size' in u['size_finish_variant_specification_decisions'][0]['scope']
assert nodes['bone']['accepted_working_specifications']['individual_price']['value']['proposed_amount'] == 1100
for path, metadata in manifest.items():
    assert hashlib.sha256((BASE / path).read_bytes()).hexdigest() == metadata['sha256'], f'Input changed during preparation: {path}'
packet = {
    'schema': 'boldstone.four-product-price-size-working-closure-proposals.v1',
    'created_utc': now,
    'worker': 'worker-03',
    'authority': authority,
    'bound_source_graph_sha256': manifest[GRAPH]['sha256'],
    'source_manifest': manifest,
    'records': records,
    'counts': {'records': 4, 'normalized_fields': 24, 'source_scopes': 5, 'accepted_working_asks': 3, 'price_on_enquiry': 1, 'current_platform_quotes_certified': 0, 'new_products': 0, 'new_individual_owner_replies': 0},
    'validation': {'status': 'PASS_ADVISORY_PACKAGE', 'six_fields_each': True, 'existing_field_proposal_ids_retained': True, 'source_hashes_unchanged_during_preparation': True, 'leaf_orientations_one_logical_product': True, 'remote_calls': 0, 'shared_state_writes': 0, 'new_source_facts_invented': False},
    'import_notes': ['The sole owner writer should attach the current direct-user authority locator and append a normalization/import event, without fabricating a new individual Keep reply.', 'Retain raw historical assertions/source rows unchanged. Normalized current displays choose a working policy; they do not prove the conflicting sources false or certify a new version.', 'Keep all platform/source linkages at their existing scope. No current price refresh was performed.', 'Do not use physical-manufacture policy as proof of finished inventory, capacity, hardware or lead time.'],
}
OUT.mkdir(parents=True, exist_ok=True)
for filename, data in [('source-evidence.json', source_snapshots), ('four-product-closure-proposals.json', packet)]:
    (OUT / filename).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'output': str(OUT / 'four-product-closure-proposals.json'), 'counts': packet['counts'], 'bound_graph_sha256': packet['bound_source_graph_sha256'], 'validation': packet['validation']}, indent=2))
