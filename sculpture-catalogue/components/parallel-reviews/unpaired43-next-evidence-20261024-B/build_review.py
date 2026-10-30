"""Refresh the existing 43 source comparisons; do not alter catalogue or platforms."""
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from html import escape
from html.parser import HTMLParser
from pathlib import Path
import hashlib
import json

ROOT = Path('/Users/tprice/Documents/boldstone')
CAT = ROOT / 'sculpture-catalogue'
LANE = Path(__file__).resolve().parent
OLD = CAT / 'components/parallel-reviews/unpaired43-source-triage-20261024'
EXPECTED_REGISTER = 'de9cd30b9dcf794576cb8e734cf41647c936da56b553b991d913fb7e3c8a8bbc'
EXPECTED_WORKBOOK = '172ec2c176479b7b1bd5c1b6920768b01e5c320ff9dc6d467d682cf1d3970dec'
SOURCE_KEY = 'current_authenticated_squarespace_inventory_observation'
FIELD_NAMES = ['Dimensions / depth', 'Weight', 'Material / finish', 'Fixing', 'Individual price', 'Availability']
NOW = datetime.now(timezone.utc).isoformat()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def objsha(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def ref(path):
    return {'path': str(path), 'sha256': sha(path)}


def load(path):
    return json.loads(Path(path).read_text())


def checked_ref(record):
    assert sha(record['path']) == record['sha256'], record['path']
    return deepcopy(record)


def save(name, value):
    with (LANE / name).open('x') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write('\n')


def e(value):
    return escape(str(value if value is not None else 'Not recorded'), quote=True)


def link(url, label):
    return f'<a href="{e(url)}">{e(label)}</a>'


pointer_ref = ref(CAT / 'current-master.json')
pointer = load(pointer_ref['path'])
master_path = CAT / pointer['register']
book_path = CAT / pointer['workbook']
assert sha(master_path) == pointer['register_sha256'] == EXPECTED_REGISTER
assert sha(book_path) == pointer['workbook_sha256'] == EXPECTED_WORKBOOK
master = load(master_path)
old = load(OLD / 'ordered-source-review.json')
old_seal = load(OLD / 'sealed-handoff.json')
for file_ref in old_seal['files']:
    checked_ref(file_ref)
old_master = load(checked_ref(old['baseline'])['path'])
source = master[SOURCE_KEY]
assert source == old_master[SOURCE_KEY], 'Captured source observations changed: review required.'
source_evidence = checked_ref(source['sealed_source_field_evidence'])
checked_ref(source['squarespace_source_clock']['raw_export'])
checked_ref(source['historical_shopify_comparison']['source_clock_and_limits']['raw_export'])
health_ref = checked_ref(master['current_primary_navigation_health'])
health = load(health_ref['path'])
health_by_id = {x['product_id']: x for x in health['rows']}
shopify_ref = ref(CAT / 'components/parallel-reviews/shopify-access-refresh-20261024T143835Z/readback.json')
assert shopify_ref['sha256'] == '8d43755eda0c5db7ffcfa1e0d0e86b986486d8a12df76199ebd6ca8be2dac259'
terracotta_ref = ref(ROOT / 'reports/catalogue-terminal-walkthrough-20261024/decowaves2-terracotta-source-review.json')
terracotta = load(terracotta_ref['path'])
assert terracotta['register_sha256'] == EXPECTED_REGISTER
assert terracotta['source_offer_refs_assigned'] == [] and terracotta['new_exact_matches'] == 0
options = {o['product_id']: (i, o) for i, o in enumerate(master['options'])}
offers = {o['offer_ref']: (i, o) for i, o in enumerate(master['source_offer_edges'])}
observations = {o['offer_ref']: (i, o) for i, o in enumerate(source['retained_offer_observations'])}
paired = {offer for pair in source['historical_shopify_comparison']['pairs'] for offer in pair['documented_offer_refs']}
unpaired = set(observations) - paired
assert len(paired) == 37 and len(unpaired) == 43
assert unpaired == {row['offer_ref'] for row in old['rows']}
groups = {oid: deepcopy(group) for group in master['current_working_design_group_projection']['groups'] for oid in group['active_option_ids']}
held_context_ids = set(master['current_global_context_owner_hold']['all_held_option_ids'])
assert len(held_context_ids) == 22
held_series_id = pointer['latest_scoped_series_owner_decisions']['held_series_option']
assert held_series_id == 'BSI-C3573D23A4B7'

# These notes update the review route, not the retained source claims or catalogue.
# The remaining evidence is for an exact native configuration claim, not a new
# condition on keeping the owner's accepted working product specification.
updates = {
 'O051': ('Source review complete; platform changes held', 'The two captured Rust records and their shared SKU have already been checked. Keep one Dune Ripple 1 — Rust working option.', 'Before native changes: confirm the chosen product/variant and collision action under the existing Squarespace write hold. Captured source prices and stock settings differ; neither replaces the £200 working estimate.'),
 'O067': ('Source review complete; platform changes held', 'Use the completed O051/O067 source comparison; do not restart the duplicate-identification question.', 'Before native changes: retain both source identities and the existing collision action hold. A shared SKU and four shared source photographs do not establish a physical cast or current stock.'),
 'O010': ('Platform configuration evidence', 'The catalogue already sells MP1, MP2 and MP3 individually. The gallery remains contextual; no new owner sale-unit question is needed.', 'An explicit mapping from the source product/variant to the intended individual phase is required before assigning its SKU. The gallery shows three members and the text says each; neither determines which phase a variant supplies.'),
 'O055': ('Platform configuration evidence', 'Palm Form One, Palm Form Two and Timeless Spiral remain separate purchasable components with their arrangement relationship retained.', 'Source-level member/variant selections distinguishing the individual panels from the arrangement are missing. The raw parts value 1 is not sufficient; compare O027, O053 and O054 without allocating set price or weight to members.'),
 'O056': ('Platform configuration evidence', 'The Palm Form Two / Timeless Spiral arrangement is retained separately from the individual components.', 'An explicit individual-member selection and applicable dimensions/depth are needed to certify an exact native configuration. Preserve O054 and O055 context; whole-offer price and weight are not per-member values.'),
 'O057': ('Platform configuration evidence', 'EP1 White and EP2 White remain individual catalogue options, with their gallery relationship retained.', 'The source text and variant record do not specify an EP1, EP2 or pair selection. Obtain that mapping before assigning an individual SKU; the catalogue sale-unit policy is already settled.'),
 'O060': ('Platform configuration evidence', 'Both owner-confirmed design links are recorded: Decowaves 1 Verdigris ↔ Frozen Decowaves 1 White, and Number 2 likewise. Do not ask those identity questions again.', 'O060 remains a Verdigris pair source. An explicit standalone finish/size/member variant is required for an exact individual platform match. The approved design links do not transfer source SKUs, prices, weights, mould or cast identity. Decowaves 2 Terracotta still has no exact retained direct offer match.'),
 'O072': ('Platform configuration evidence', 'EP1 Verdigris and EP2 Verdigris remain individual working options within the retained pair relationship.', 'The source describes a pair while its principal front imagery has a recorded completeness limitation. A source member/variant mapping is required; do not split the whole-offer weight or reopen a held photo question.'),
 'O058': ('Copy prepared; platform changes held', 'Leaf Form copy work is complete. The owner confirmed one sculpture design shown twice on the wall; no two-part interpretation remains.', 'Before applying prepared copy, bind the approved 35 × 35 working version to the intended source variant. The retained O058 text is 40 × 20; O028 does not confirm two casts, per-copy price or an individual SKU.'),
 'O059': ('Copy prepared; platform changes held', 'Moon Water Catcher copy work is complete; current image and folder URL capitalization has been corrected in the master.', 'The retained circular 50 × 8 source wording is not an exact configuration for the accepted 51 × 48 working version. Keep O015 identity quarantine separate and identify the intended native variant before applying prepared copy.'),
 'O079': ('Copy prepared; platform changes held', 'Bone Water Spiral copy work is complete; the accepted working version remains 80 W × 60 H cm.', 'The source SKU describes 55 × 55. Exact native configuration applicability remains unverified; do not adopt that size or certify a water-ready build from the photograph. Prepared copy awaits the existing platform write hold.'),
 'O002': ('Platform configuration evidence', 'Both Gold Dune Ripple source versions are retained; their observed amounts do not replace the current working price.', 'A size/version-specific mapping between O002, O039 and Dune Ripple 2 Gold is needed for an exact native variant decision. Keep captured visibility and each source identity distinct.'),
 'O003': ('Platform configuration evidence', 'The historical Concave Silver/Bronze alias remains associated with Moon Crater Phase 4 Silver/Bronze.', 'Resolve the exact 25 cm applicability across O003/O064 before selecting a native variant. The 50 cm White specification is a separate scope; no extra Concave product is needed.'),
 'O064': ('Platform configuration evidence', 'Use the same O003/O064 alias/version comparison; preserve O064’s captured hidden setting.', 'Exact size/configuration applicability is unresolved. Hidden is a captured visibility setting, not evidence of absent stock, retirement or a separate design.'),
 'O004': ('Platform configuration evidence', 'Dune Ripple 1 Verdigris retains both source version references and its accepted working details.', 'Determine the applicable O004/O038 size and finish version, preserving the source SOLD-versus-stock-setting conflict. Neither source alone proves current physical stock or the exact individual configuration.'),
 'O008': ('Platform configuration evidence', 'The recorded Blue-title source relationship to MCP2 Verdigris and Rust is retained.', 'Exact source-photo/finish applicability must be shown before a configuration claim. Title similarity does not permit moving this source identifier to Blue Splashes.'),
 'O009': ('Platform configuration evidence', 'The existing positive source relationship and the recorded historical hero-image qualification are both retained.', 'An exact specimen/finish binding remains unverified. Current Dropbox navigation does not resolve the generic Verdigris gallery versus speckled hero applicability conflict; no new photograph request is opened.'),
 'O011': ('Platform configuration evidence', 'The 25 cm spherical/concave association remains within MCP4 Verdigris, alongside qualified O006 scope.', 'The exact source specimen is unresolved. Bind the 25 cm source configuration explicitly; do not transfer dimensions from the separate 50 cm White offer.'),
 'O049': ('Platform configuration evidence', 'Frozen Fish Two Terracotta remains associated with its existing single-panel source; current default face size is 70 H × 15 W cm.', 'Confirm source configuration applicability without using the shared rear image with Frozen Deco as identity or fitted-hardware proof. The separate legacy Frozen Fish identity question stays deferred.'),
 'O050': ('Platform configuration evidence', 'O050 remains the Decowaves 1 Terracotta source. The completed local comparison excludes assigning it to Number 2 Terracotta.', 'Retain the Number 1 design scope and source size qualifiers. The shared reverse image with O049 cannot verify a cast or hardware. A separate exact source tuple is still needed for Number 2 Terracotta; O060 is only broader design/arrangement context.'),
 'O053': ('Platform configuration evidence', 'The documented crosswalk remains Palm Form One → BC-DP-PALM2.', 'Keep the crosswalk and compare the exact current size/finish/build before selecting a native variant. Source numbers and internal component numbers are not interchangeable join keys.'),
 'O054': ('Platform configuration evidence', 'The documented crosswalk remains Palm Form Two → BC-DP-PALM1.', 'Keep O054 distinct from O053, even though the source and component numbering differ. Exact size/finish/build applicability remains qualified.'),
 'O065': ('Platform configuration evidence', 'The standalone MP1 source link remains separate from O010’s three-member gallery.', 'The retained source does not establish exact applicability to every current MP1 size/build. Confirm that variant mapping without reopening the settled individual-sale policy.'),
 'O074': ('Platform configuration evidence', 'The standalone MP2 source link remains separate from O010’s three-member gallery.', 'The retained source does not establish exact applicability to every current MP2 size/build. Confirm that variant mapping without reopening the settled individual-sale policy.'),
 'O075': ('Platform configuration evidence', 'The standalone MP3 source link remains separate from O010’s three-member gallery.', 'The retained source does not establish exact applicability to every current MP3 size/build. Confirm that variant mapping without reopening the settled individual-sale policy.'),
 'O070': ('Platform configuration evidence', 'Moonphase Four Silver retains the historical MP1/MP5 orientation crosswalk.', 'Exact source configuration remains scoped to the accepted plain Silver option. The crosswalk does not extend the offer to bordered, White or Gold options.'),
 'O073': ('Platform configuration evidence', 'Azure remains one individually sold panel; the second, different panel in the room scene remains unallocated context.', 'Exact size/build applicability still needs a variant-specific source binding. Do not create another Azure option or enlarge its sale unit from the room scene.'),
 'O001': ('Owner-held Wall Circle review', 'Wall Circle remains deferred. Four conditional pattern assignments and three custom/unlisted appearance scopes are preserved.', 'Resume only after the owner releases the Wall Circle review. No exact appearance-to-pattern binding is added. Two saved primary IDs are marked deleted in Dropbox history; local historical originals are not replacements.'),
 'O006': ('Source-photo identity unresolved', 'Both qualified MCP4 Verdigris and Verdigris/Rust associations are retained, with their unresolved source file binding.', 'An exact source image ID/finish binding is missing. The G216/G217 and former Concave G052/G053 owner equivalence does not bind this source to either file set; current navigation cannot substitute for that evidence. No new question is opened.'),
 'O007': ('Source-photo identity unresolved', 'The existing MCP1 Verdigris and Rust working option remains; a pure Verdigris product is not created.', 'An exact source-photo/finish configuration is missing for the green/verdigris listing. Keep the uncertainty and existing review route; no new photo or identity question is opened.'),
}

rows = []
delta_rows = []
old_options = {o['product_id']: o for row in old['rows'] for o in row['related_current_options']}
for oid, previous in old_options.items():
    _, current = options[oid]
    fields_changed = [k for k in FIELD_NAMES if previous['working_fields'][k]['source_object_sha256'] != objsha(current['master_fields'][k])]
    delta = {k: {'before': previous[k], 'after': current[k]} for k in ['name', 'canonical_key', 'image_url', 'folder_url', 'file_id', 'folder_id'] if previous[k] != current[k]}
    assert not fields_changed, (oid, fields_changed)
    if delta:
        delta_rows.append({'product_id': oid, 'name': current['name'], 'changes': delta})

for previous in old['rows']:
    offer_ref = previous['offer_ref']
    obs_i, obs = observations[offer_ref]
    offer_i, offer_edge = offers[offer_ref]
    assert previous['native_source_tuple'] == obs['observed_native_source_tuple']
    assert previous['member_scope_object_sha256'] == objsha(offer_edge['members'])
    assert [o['product_id'] for o in previous['related_current_options']] == obs['existing_related_option_ids']
    op_rows = []
    for oid in obs['existing_related_option_ids']:
        oi, op = options[oid]
        navigation = health_by_id[oid]
        assert navigation['file_id'] == op['file_id'] and navigation['folder_id'] == op['folder_id']
        retained_relations = [(i, x) for i, x in enumerate(master['current_listing_match_evidence']['edges']) if x['offer_ref'] == offer_ref and x['product_id'] == oid]
        assert retained_relations
        op_rows.append({
            **{k: deepcopy(op[k]) for k in ['product_id', 'name', 'canonical_key', 'canonical_component_id', 'option_family_id', 'sale_unit', 'image_url', 'folder_url', 'file_id', 'folder_id', 'master_fields', 'current_listing_resolution', 'photo_coverage']},
            'current_option_pointer': f'/options/{oi}',
            'working_fields_pointer': f'/options/{oi}/master_fields',
            'working_field_sha256': {k: objsha(op['master_fields'][k]) for k in FIELD_NAMES},
            'working_design_group': deepcopy(groups.get(oid)),
            'group_scope_note': 'Existing component design group' if oid in groups else 'Family-scoped visual option; no component design group is assigned or inferred.',
            'owner_design_equivalence': deepcopy(op.get('current_owner_design_equivalence')),
            'retained_source_relations': [{'json_pointer': f'/current_listing_match_evidence/edges/{i}', 'full_object': deepcopy(x), 'object_sha256': objsha(x)} for i, x in retained_relations],
            'navigation_observation': deepcopy(navigation),
            'navigation_evidence': health_ref,
            'context_photograph_held': oid in held_context_ids,
            'series_photograph_held': oid == held_series_id,
            'no_new_selection_or_verification': True,
        })
    if offer_ref in updates:
        stage, settled, need = updates[offer_ref]
    else:
        stage = 'Platform configuration evidence'
        settled = 'The existing individual source relationship and all six accepted working fields are retained.'
        grades = sorted({x['full_object']['dimension_grade'] for op in op_rows for x in op['retained_source_relations']})
        if 'RECORDED_DIMENSION_OR_VERSION_CONFLICT' in grades:
            need = 'Resolve the retained source-versus-working size/version conflict before claiming an exact native configuration. Keep the accepted working measurements and estimates; no new physical measurement request is opened here.'
        elif 'SOURCE_SIZE_APPLICABILITY_PARTLY_OR_WHOLLY_UNRESOLVED' in grades:
            need = 'The source has a qualified design/finish relationship but size or build applicability remains unresolved. An explicit product/variant-to-current-option mapping is needed for an exact configuration claim.'
        else:
            need = 'Source numerical claims are compatible with the working scope, but this does not certify the exact current size/finish/build. Retain the recorded source relationship and obtain an explicit native variant mapping before claiming full configuration equivalence.'
        if offer_ref == 'O052':
            need += ' The Dune Ripple 2 Copper series-photo hold remains; this preparation does not reopen it.'
        if offer_ref == 'O063':
            settled += ' Current Frozen Fish face size is 70 H × 15 W cm; the historical 100 × 22 version is not the current default.'
            need += ' The separate historical blank-SKU Frozen Fish draft remains deferred.'
    comparators = []
    for comparator_ref in previous['next_comparison']['compare_offers']:
        ci, co = observations[comparator_ref]
        ei, ce = offers[comparator_ref]
        comparators.append({
            'offer_ref': comparator_ref,
            'source_observation_pointer': f'/{SOURCE_KEY}/retained_offer_observations/{ci}',
            'source_observation': deepcopy(co),
            'retained_source_offer_pointer': f'/source_offer_edges/{ei}/source_offer',
            'retained_source_offer': deepcopy(ce['source_offer']),
            'source_level_historical_pair_documented': comparator_ref in paired,
            'exact_current_individual_configuration_certified': False,
        })
    row = {
        'offer_ref': offer_ref,
        'captured_source_title': next(x['current_csv_value_raw'] for x in obs['fields'] if x['csv_column'] == 'Title'),
        'native_source_tuple': deepcopy(obs['observed_native_source_tuple']),
        'source_record_locator': deepcopy(obs['source_record_locator']),
        'source_url': obs['observed_source_url'],
        'source_observation_pointer': f'/{SOURCE_KEY}/retained_offer_observations/{obs_i}',
        'source_observation': deepcopy(obs),
        'retained_source_offer_pointer': f'/source_offer_edges/{offer_i}/source_offer',
        'retained_source_offer': deepcopy(offer_edge['source_offer']),
        'retained_member_scope': deepcopy(offer_edge['members']),
        'retained_member_scope_sha256': objsha(offer_edge['members']),
        'related_current_options': op_rows,
        'source_level_historical_pair_status': 'NO_DOCUMENTED_PAIR_IN_THE_RETAINED_HISTORICAL_SHOPIFY_COMPARISON',
        'current_shopify_absence_established': False,
        'comparison_group': previous['next_comparison']['case'],
        'previous_next_comparison_retained_for_provenance': deepcopy(previous['next_comparison']),
        'current_preparation': {'stage': stage, 'already_settled': settled, 'evidence_still_needed_for_exact_native_configuration': need,
            'purpose': 'This limits an exact platform-configuration claim; it does not revoke the accepted working product or require actual measurements before retaining estimates.',
            'owner_question_opened': False, 'platform_change_allowed': False},
        'comparison_source_records': comparators,
    }
    rows.append(row)

stage_order = {'Platform configuration evidence': 10, 'Copy prepared; platform changes held': 20, 'Source review complete; platform changes held': 30, 'Source-photo identity unresolved': 40, 'Owner-held Wall Circle review': 50}
rows.sort(key=lambda x: (stage_order[x['current_preparation']['stage']], x['previous_next_comparison_retained_for_provenance']['order'], x['offer_ref']))
for i, row in enumerate(rows, 1):
    row['review_position'] = i

packet = {
    'schema': 'boldstone.unpaired43.current-next-evidence.v1', 'prepared_utc': NOW,
    'status': 'LOCAL_PREPARATION_COMPLETE_NO_NEW_MATCHES_OR_SHARED_WRITES',
    'baseline': {'pointer': pointer_ref, 'register': ref(master_path), 'workbook': ref(book_path)},
    'source_clocks': deepcopy(old['source_clocks']) | {'current_master_publication': pointer['recorded_utc'], 'review_prepared_utc': NOW},
    'prior_review': ref(OLD / 'ordered-source-review.json'),
    'prior_seal': ref(OLD / 'sealed-handoff.json'),
    'unchanged_source_observation_object_sha256': objsha(source),
    'source_field_evidence': source_evidence,
    'partition': deepcopy(old['partition']),
    'counts': {'source_rows': len(rows), 'comparison_groups': len({x['comparison_group'] for x in rows}),
        'related_option_references': sum(len(x['related_current_options']) for x in rows), 'unique_related_options': len(old_options),
        'unique_working_field_objects_preserved': len(old_options) * 6, 'stages': dict(Counter(x['current_preparation']['stage'] for x in rows))},
    'changed_link_rows_since_prior_review': delta_rows,
    'current_owner_design_equivalence_edges': deepcopy(master['current_owner_design_equivalence_edges']),
    'leaf_owner_depiction_correction': deepcopy(offers['O028'][1]['current_owner_depiction_correction']),
    'completed_terracotta2_comparison': {'evidence': terracotta_ref, 'conclusion': deepcopy(terracotta)},
    'navigation_observation': {'evidence': health_ref, 'recorded_utc': health['recorded_utc'], 'history_recorded_utc': health['latest_history_recorded_utc'], 'counts': deepcopy(health['counts']), 'not_a_new_live_read': True},
    'standing_boundaries': {'missing_context_holds': sorted(held_context_ids), 'series_hold_option': held_series_id,
        'wall_circle_review_held': True, 'historical_frozen_fish_identity_deferred': True,
        'current_frozen_fish_size_policy': deepcopy(pointer['current_frozen_fish_size_policy']),
        'policy_metadata_source': pointer_ref,
        'squarespace_write_hold': deepcopy(pointer['platform_write_holds']),
        'shopify_access_evidence': shopify_ref, 'shopify_scope': 'Last signed-in selector showed no existing selectable store. This is not account-wide store absence; no new account information or repeated request this turn.',
        'other_session_claims': {'main': 'Sole canonical publisher', 'recovery': 'Pewter actual-physical-details question and six unapplied URL-capitalization proposals', 'directory': 'Replacement Moonwave mounted-view/detail criterion after withdrawal'},
        'moonwave_nine_photo_plan_withdrawn': True},
    'qualifications': [
        '43 are retained Squarespace sources without a documented historical Shopify pair, not 43 missing products or a current absence claim.',
        'All 37 documented pairs are source-level historical comparisons, not certification of exact individual configurations.',
        'The capture time for source data remains 2026-10-24T00:56:45.467073+00:00. Preparation time is not a new platform observation.',
        'Raw exported prices do not encode currency; raw shipping dimensions/weight do not encode units. Source stock/visibility settings do not verify a physical cast, stock or a live purchasable offer.',
        'Full six-field objects, assertions, source scopes, estimates, choices and owner-instructed made-to-order / 1–2-week policy are copied unchanged.',
        'Working catalogue entries remain accepted. Missing evidence limits only the more specific exact native configuration claim.',
        'Current photo coverage and existing navigation health are separate. Two saved Wall Circle image links are historical deleted-ID references, not current usable selections.',
        'No source HTML is executed; descriptions are displayed as escaped captured text.',
    ],
    'rows': rows,
    'new_exact_matches': 0, 'new_physical_verifications': 0, 'new_image_selections': 0,
    'native_api_calls': 0, 'shared_catalogue_or_platform_writes': 0, 'owner_questions': [], 'native_payloads': [],
}
save('next-evidence-review.json', packet)

cards = []
index = []
for row in rows:
    prep = row['current_preparation']
    index.append(f'<li>{link("#" + row["offer_ref"], row["offer_ref"] + " — " + row["captured_source_title"])} <small>{e(prep["stage"])}</small></li>')
    t = row['native_source_tuple']
    sources_html = []
    for co in row['comparison_source_records']:
        ob = co['source_observation']
        raw = {x['csv_column']: x['current_csv_value_raw'] for x in ob['fields']}
        nt = ob['observed_native_source_tuple']
        sources_html.append(f'<tr><td>{e(co["offer_ref"])}</td><td>{link(ob["observed_source_url"], raw["Title"])}</td><td>{e(nt["product_id"])}<br>{e(nt["variant_id"])}<br>{e(nt["sku_raw"])}</td><td>{e(raw["Price"])}</td><td>{e(raw["Visible"])}</td><td>{e(raw["Stock"])}</td></tr>')
    raw = {x['csv_column']: x['current_csv_value_raw'] for x in row['source_observation']['fields']}
    desc_text = next(x['current_comparison_value'] for x in row['source_observation']['fields'] if x['csv_column'] == 'Description')
    options_html = []
    for op in row['related_current_options']:
        nav = op['navigation_observation']
        deleted = nav.get('deletion_observed_in_exact_id_history', False)
        image_label = 'Saved image reference — ID marked deleted' if deleted else 'Individual image / selected reference'
        warning = f'<p class="warning">Saved image ID marked deleted at {e(nav.get("server_deleted_utc"))}. The folder remains a catalogue reference; no replacement has been selected. Historical local original is retained as evidence only.</p>' if deleted else ''
        qualifiers = list(dict.fromkeys(q for relation in op['retained_source_relations'] for q in (relation['full_object'].get('special_join_limits') or [])))
        qualifiers += list(dict.fromkeys(relation['full_object'].get('source_cautions_retained') for relation in op['retained_source_relations'] if relation['full_object'].get('source_cautions_retained')))
        field_rows = ''.join(f'<tr><th>{e(k)}</th><td>{e(op["master_fields"][k]["display"])}</td><td>{e(op["master_fields"][k].get("state"))}</td></tr>' for k in FIELD_NAMES)
        hold_text = ('Missing context photograph remains held. ' if op['context_photograph_held'] else '') + ('Series photograph remains held. ' if op['series_photograph_held'] else '')
        group_label = op['working_design_group']['working_design_group_id'] if op['working_design_group'] else 'Unassigned; visual option in family ' + op['option_family_id']
        options_html.append(f'<section class="option"><h3>{e(op["name"])}</h3><p>{link(op["image_url"], image_label)} · {link(op["folder_url"], "Containing folder")}</p>{warning}<p class="small">Option {e(op["product_id"])} · Component {e(op["canonical_component_id"])} · Working design group {e(group_label)}</p><p>{e(op["sale_unit"])}</p><p class="small">{e(hold_text)}</p><ul>{"".join("<li>" + e(x) + "</li>" for x in qualifiers)}</ul><details><summary>Six accepted working specifications and qualifications</summary><table><thead><tr><th>Specification</th><th>Working detail</th><th>Evidence state</th></tr></thead><tbody>{field_rows}</tbody></table></details><p class="small">Navigation: {e(nav["navigation_status"])}. This review reuses the saved metadata/history observation; it did not perform another live Dropbox check.</p></section>')
    cards.append(f'<article id="{row["offer_ref"]}" data-stage="{e(prep["stage"])}"><h2>{row["review_position"]}. {e(row["captured_source_title"])}</h2><p class="badge">{e(row["offer_ref"])} · {e(prep["stage"])}</p><p><strong>Already settled:</strong> {e(prep["already_settled"])}</p><p><strong>Remaining evidence for an exact platform configuration:</strong> {e(prep["evidence_still_needed_for_exact_native_configuration"])}</p><p class="small">This does not revoke the accepted working entry. No new owner question or platform edit is requested.</p><p>{link(row["source_url"], "Captured source listing")} · Product <code>{e(t["product_id"])}</code> · Variant <code>{e(t["variant_id"])}</code> · Source SKU <code>{e(t["sku_raw"])}</code></p><details><summary>Captured source claims and comparator records</summary><p>{e(desc_text)}</p><p>Retained sale scope: {e(row["retained_source_offer"].get("sale_unit_state"))}. These are dated source claims, distinct from the accepted working catalogue.</p><div class="scroll"><table><thead><tr><th>Ref</th><th>Source</th><th>Product / variant / SKU</th><th>Raw price</th><th>Visible</th><th>Stock setting</th></tr></thead><tbody>{"".join(sources_html)}</tbody></table></div><p class="small">The export does not encode currency or physical dimension/weight units. Captured stock and visibility are settings, not physical inventory.</p></details>{"".join(options_html)}</article>')

stages_html = ''.join(f'<option value="{e(k)}">{e(k)} ({v})</option>' for k, v in packet['counts']['stages'].items())
page = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Boldstone — 43 source comparisons</title>
<style>body{{font:16px/1.55 system-ui,sans-serif;color:#23362e;max-width:1120px;margin:32px auto;padding:0 20px}}a{{color:#086446}}h1,h2,h3{{line-height:1.25}}h2{{font-size:1.35rem}}h3{{font-size:1.15rem}}article{{border-top:3px solid #bdcfc3;margin:32px 0;padding-top:20px}}.option{{background:#f3f6f1;padding:16px;margin:16px 0;border-radius:8px}}.notice{{padding:18px;background:#e9f2ec;border-radius:8px}}.warning{{padding:12px;background:#fff0d5}}.small,small{{font-size:13px;color:#506358}}small{{display:block}}.badge{{font-weight:650}}table{{border-collapse:collapse;width:100%;table-layout:fixed}}th,td{{border:1px solid #c4d1c8;padding:8px;text-align:left;vertical-align:top;overflow-wrap:anywhere}}details{{margin:12px 0}}summary{{cursor:pointer;font-weight:650}}.scroll{{overflow-x:auto}}code{{overflow-wrap:anywhere}}li{{margin:8px 0}}label{{display:block;margin:16px 0}}select{{font:inherit;max-width:100%;padding:8px}}[hidden]{{display:none}}@media print{{article{{break-before:page}}select,label{{display:none}}details>*{{display:block}}}}</style></head><body>
<h1>43 source comparisons, refreshed</h1><p class="notice">These are 43 Squarespace source records with no documented pair in the historical Shopify comparison. They relate to <strong>48 existing catalogue options</strong>; they are not 43 missing products. All <strong>288 working specification fields</strong> are preserved.</p>
<p>Each item gives its existing source product, variant and SKU, current catalogue image/folder links, accepted specifications and the evidence still needed for a more specific platform configuration claim. Prepared {e(NOW)} from the published register.</p>
<p>Squarespace capture: 24 October 2026, 00:56 UTC. Shopify comparison: historical export, not a current inventory. The 37 documented source pairs do not establish exact individual configurations. Current Shopify access remains unresolved; no account question was repeated.</p>
<p><strong>Updated decisions:</strong> both Decowaves White/Verdigris design links are accepted; Leaf Form is one design displayed twice; Rust source review and the completed copy drafts are not reopened. Moon Water Catcher links follow the current master. Two Wall Circle saved primaries carry deleted-ID warnings; no replacements are selected.</p>
<p>The 22 missing-context holds, Dune Ripple 2 Copper series hold, Wall Circle deferral and historical Frozen Fish identity deferral remain. Squarespace changes remain on hold. Other sessions retain the Pewter measurements, six URL proposals and revised Moonwave classification question. The nine-photo Moonwave move proposal is withdrawn.</p>
<p>{link('next-evidence-review.json', 'Structured evidence and full field objects')} · {link('saved-readback.json', 'Saved review checks')} · {link(str(ROOT / 'reports/catalogue-terminal-walkthrough-20261024/decowaves2-terracotta-source-review.html'), 'Completed Decowaves 2 Terracotta comparison')}</p>
<label>Show items <select id="stage"><option value="">All 43 source records</option>{stages_html}</select></label><details><summary>All source records</summary><ol>{''.join(index)}</ol></details>
{''.join(cards)}
<script>document.getElementById('stage').addEventListener('change',function(){{for(const card of document.querySelectorAll('article')){{card.hidden=this.value!==''&&card.dataset.stage!==this.value;}}}});for(const a of document.querySelectorAll('a[href^="#"]')){{a.addEventListener('click',function(){{document.getElementById('stage').value='';for(const card of document.querySelectorAll('article'))card.hidden=false;}});}}</script></body></html>'''
with (LANE / 'review.html').open('x') as f:
    f.write(page + '\n')

class Parser(HTMLParser):
    def __init__(self):
        super().__init__(); self.ids = []; self.links = []; self.articles = 0
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'id' in attrs:
            self.ids.append(attrs['id'])
        if tag == 'article':
            self.articles += 1
        if tag == 'a':
            self.links.append(attrs['href'])

parsed = Parser(); parsed.feed((LANE / 'review.html').read_text())
saved = load(LANE / 'next-evidence-review.json')
all_saved_ops = [op for row in saved['rows'] for op in row['related_current_options']]
checks = {
    'exact_43_unpaired_partition_of_80_with_37_historical_source_pairs': len(saved['rows']) == 43 and {x['offer_ref'] for x in saved['rows']} == unpaired and len(paired) == 37 and not paired & unpaired and len(paired | unpaired) == 80,
    '58_option_references_48_distinct_options_288_distinct_fields': len(all_saved_ops) == 58 and len({x['product_id'] for x in all_saved_ops}) == 48 and len(old_options) * 6 == 288,
    'captured_observations_rebound_without_changed_source_data': source == old_master[SOURCE_KEY] and all(x['source_observation'] == observations[x['offer_ref']][1] for x in saved['rows']),
    'source_tuple_locator_and_members_exactly_preserved': all(x['native_source_tuple'] == observations[x['offer_ref']][1]['observed_native_source_tuple'] and x['source_record_locator'] == observations[x['offer_ref']][1]['source_record_locator'] and x['retained_member_scope'] == offers[x['offer_ref']][1]['members'] for x in saved['rows']),
    'full_six_field_objects_and_source_assertions_exactly_preserved': all(op['master_fields'] == options[op['product_id']][1]['master_fields'] and set(op['master_fields']) == set(FIELD_NAMES) for op in all_saved_ops),
    'all_288_field_hashes_unchanged_from_previous_review': all(old_options[oid]['working_fields'][k]['source_object_sha256'] == objsha(options[oid][1]['master_fields'][k]) for oid in old_options for k in FIELD_NAMES),
    'current_names_ids_and_image_folder_links_exactly_copied': all(all(op[k] == options[op['product_id']][1][k] for k in ['name', 'canonical_key', 'canonical_component_id', 'image_url', 'folder_url', 'file_id', 'folder_id']) for op in all_saved_ops),
    'only_prior_link_delta_is_two_Moon_Water_Catcher_urls': len(delta_rows) == 1 and delta_rows[0]['product_id'] == 'BSI-70C7029C1DB1' and set(delta_rows[0]['changes']) == {'image_url', 'folder_url'},
    'all_existing_relation_objects_and_resolutions_retained': all(op['current_listing_resolution'] == options[op['product_id']][1]['current_listing_resolution'] and all(rel['full_object'] == master['current_listing_match_evidence']['edges'][int(rel['json_pointer'].rsplit('/',1)[1])] for rel in op['retained_source_relations']) for op in all_saved_ops),
    'two_owner_design_equivalences_carried_without_configuration_transfer': len(saved['current_owner_design_equivalence_edges']) == 2 and saved['current_owner_design_equivalence_edges'] == master['current_owner_design_equivalence_edges'] and all(x['no_physical_mould_cast_or_specification_transfer'] for x in saved['current_owner_design_equivalence_edges']),
    'seven_Wall_Circle_visual_options_preserve_null_component_group': len([op for op in all_saved_ops if op['working_design_group'] is None]) == 7 and all(op['canonical_component_id'] is None and op['option_family_id'] == 'BC-WALL-CIRCLE' for op in all_saved_ops if op['working_design_group'] is None),
    'leaf_repeated_design_and_terracotta2_unresolved_match_preserved': saved['leaf_owner_depiction_correction'] == offers['O028'][1]['current_owner_depiction_correction'] and saved['completed_terracotta2_comparison']['conclusion'] == terracotta and terracotta['new_exact_matches'] == 0,
    '46_saved_primary_verifications_two_deleted_history_warnings': sum(bool(x['file_verified_by_id'] and x['actual_containing_folder_verified']) for x in health['rows']) == 46 and sum(bool(x.get('deletion_observed_in_exact_id_history')) for x in health['rows']) == 2 and all(op['navigation_observation'] == health_by_id[op['product_id']] for op in all_saved_ops),
    '22_context_one_series_and_existing_deferrals_preserved': len(saved['standing_boundaries']['missing_context_holds']) == 22 and saved['standing_boundaries']['series_hold_option'] == held_series_id and saved['standing_boundaries']['wall_circle_review_held'] and saved['standing_boundaries']['historical_frozen_fish_identity_deferred'],
    'every_source_has_a_specific_followup_without_new_question_or_write': all(x['current_preparation']['already_settled'] and x['current_preparation']['evidence_still_needed_for_exact_native_configuration'] and not x['current_preparation']['owner_question_opened'] and not x['current_preparation']['platform_change_allowed'] for x in saved['rows']),
    'all_43_cards_and_local_index_anchors_valid': parsed.articles == 43 and len(parsed.ids) == len(set(parsed.ids)) and all(a[1:] in parsed.ids for a in parsed.links if a.startswith('#')),
    'all_saved_image_folder_and_source_links_rendered': all(op['image_url'] in parsed.links and op['folder_url'] in parsed.links for op in all_saved_ops) and all(x['source_url'] in parsed.links for x in saved['rows']),
    'no_promoted_match_physical_selection_or_native_payload': saved['new_exact_matches'] == saved['new_physical_verifications'] == saved['new_image_selections'] == saved['native_api_calls'] == saved['shared_catalogue_or_platform_writes'] == 0 and saved['owner_questions'] == saved['native_payloads'] == [],
    'source_clocks_preserved_and_preparation_distinguished': saved['source_clocks']['authenticated_export_captured_utc'] == source['squarespace_source_clock']['captured_utc'] and saved['source_clocks']['review_prepared_utc'] == NOW,
    'baseline_register_workbook_and_pointer_unchanged_during_build': sha(master_path) == EXPECTED_REGISTER and sha(book_path) == EXPECTED_WORKBOOK and sha(pointer_ref['path']) == pointer_ref['sha256'],
}
validation = {'status': 'PASS' if all(checks.values()) else 'FAIL', 'recorded_utc': NOW, 'passed': sum(checks.values()), 'total': len(checks), 'checks': checks,
              'scope': 'Saved review and source-reference integrity only. No repeated live source audit, physical inspection, platform matching or canonical publication.'}
save('saved-readback.json', validation)
assert all(checks.values()), [k for k, v in checks.items() if not v]
seal = {'status': 'SEALED_LOCAL_NEXT_EVIDENCE_REVIEW', 'recorded_utc': NOW, 'baseline': saved['baseline'], 'counts': saved['counts'],
        'files': [ref(LANE / name) for name in ['build_review.py', 'build-attempt-01.json', 'build-attempt-02.json', 'build-attempt-03.json', 'next-evidence-review.json', 'review.html', 'saved-readback.json']],
        'checks_passed': validation['passed'], 'checks_total': validation['total'],
        'shared_writes': 0, 'native_calls': 0, 'new_owner_questions': 0,
        'publication_instruction': 'Main may link this local report after checking baseline guards. No catalogue data change is proposed. If the register changes, rebind affected fields and links before describing it as current.'}
save('sealed-handoff.json', seal)
print(json.dumps({'status': seal['status'], 'counts': seal['counts'], 'checks': f'{validation["passed"]}/{validation["total"]}', 'review': str(LANE / 'review.html'), 'seal': ref(LANE / 'sealed-handoff.json')}, indent=2))
