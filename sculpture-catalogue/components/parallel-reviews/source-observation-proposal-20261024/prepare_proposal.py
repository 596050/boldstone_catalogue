"""Prepare an additive source-observation proposal; never write the catalogue.

Inputs are previously sealed evidence. This script does not query platforms,
reparse the native exports, re-audit sources, or apply a master/workbook change.
"""
from __future__ import annotations

import hashlib
import html
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/Users/tprice/Documents/boldstone/sculpture-catalogue')
LANE = Path(__file__).resolve().parent
REVIEWS = ROOT / 'components/parallel-reviews'
BASE = ROOT / 'components/reconciliation/leaf-form-owner-display-correction-master-2026-10-24/canonical-master-register.json'
BASE_SHA = '2205546ab8502b4723d1eb9597c6da4104f8df18e7addcfd1ad9d9a4df328c16'
TARGET = 'current_authenticated_squarespace_inventory_observation'
NOW = datetime.now(timezone.utc).isoformat()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def ref(path):
    p = Path(path)
    return {'path': str(p), 'sha256': sha(p)}


def load_pinned(path, expected):
    p = Path(path)
    if sha(p) != expected:
        raise ValueError(f'Pinned input changed: {p}')
    return json.loads(p.read_text())


def save(name, value):
    with (LANE / name).open('x') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write('\n')


base = load_pinned(BASE, BASE_SHA)
index_path = REVIEWS / 'source-integration-index-20261024/source-integration-index.json'
index = load_pinned(index_path, 'bc7ea5eb36a43834db53e3c227b1c8c00ab65ab2025acbe4b47c447624ab5d4a')
join_path = REVIEWS / 'source-integration-index-20261024/exact-source-join-index.json'
joins = load_pinned(join_path, 'f3921457eeeec64eb44e71f3c80bcc174c2059b812c67ff79d33535bcaeb2007')
sq_ref = joins['squarespace_evidence']
sq = load_pinned(sq_ref['path'], sq_ref['sha256'])
pair_ref = joins['historical_shopify_pair_evidence']
pairs = load_pinned(pair_ref['path'], pair_ref['sha256'])
assert TARGET not in base, 'Target already exists: main must reconcile, never overwrite.'
assert len(sq['entries']) == 80 and len(joins['historical_shopify_pairs']) == 37

edges = {e['offer_ref']: (i, e) for i, e in enumerate(base['source_offer_edges'])}
options = {o['product_id']: o for o in base['options']}
join_by_offer = {e['offer_ref']: e for e in joins['squarespace_retained_offer_joins']}
leaf_index, leaf_edge = edges['O028']
leaf_override = leaf_edge['current_owner_depiction_correction']
owner_ref = {
    'offer_ref': 'O028',
    'decision_id': leaf_override['decision_id'],
    'base_register': ref(BASE),
    'json_pointer': f'/source_offer_edges/{leaf_index}/current_owner_depiction_correction',
    'meaning': 'One Leaf Form design shown twice; native sale quantity and physical cast quantity remain unconfirmed.',
    'precedence': 'This owner correction governs current catalogue interpretation; corroborated source wording does not supersede it.',
}

observations = []
for n, entry in enumerate(sq['entries']):
    join = join_by_offer[entry['offer_ref']]
    edge_index, edge = edges[entry['offer_ref']]
    # Referential safety for this additive proposal, not a repeat source audit.
    assert edge['source_offer']['sq_id'] == entry['native_product_id']
    assert edge['source_offer']['sku'] == entry['sku']
    assert (join['native_product_id'], join['native_variant_id'], join['sku']) == (
        entry['native_product_id'], entry['native_variant_id'], entry['sku'])
    item = {
        'offer_ref': entry['offer_ref'],
        'observed_native_source_tuple': {
            'product_id': entry['native_product_id'],
            'variant_id': entry['native_variant_id'],
            'sku_raw': entry['sku'],
        },
        'source_evidence': {**sq_ref, 'json_pointer': f'/entries/{n}'},
        'source_record_locator': deepcopy(entry['source']),
        'product_header_data_record_1based': entry['product_header_data_record_1based'],
        'current_base_historical_source_pointer': f'/source_offer_edges/{edge_index}/source_offer',
        'historical_comparison_source_register': deepcopy(sq['sources'][0]),
        'historical_comparison_source_pointer': entry['historical_source_locator'],
        'observed_source_url': entry['current_source_url_from_export'],
        'observed_first_source_image_url': entry['source_first_image_url'],
        'image_scope': 'Export metadata only; not a new viewed image, per-variant binding, or verified current Dropbox reference.',
        'fields': deepcopy(entry['fields']),
        'previously_reported_all_nine_comparisons_equal': entry['all_nine_compared_fields_equal'],
        'existing_related_option_ids': deepcopy(join['existing_related_option_ids']),
        'catalogue_association_scope': join['association_scope'],
        'source_image_binding_state_retained': entry['source_image_binding_state_retained'],
        'exact_individual_configuration_certified_by_observation': False,
        'physical_specifications_verified_by_observation': False,
        'component_sku_assignment_proposed': False,
    }
    if entry['offer_ref'] == 'O028':
        item['current_owner_interpretation_reference'] = deepcopy(owner_ref)
    observations.append(item)

historical_pairs = []
paired_rows = []
for pair_join in joins['historical_shopify_pairs']:
    n = int(pair_join['evidence_locator'].removeprefix('/rows/'))
    row = pairs['rows'][n]
    assert row['historical_shopify_handle'] == pair_join['historical_shopify_handle']
    assert row['result'] == 'DOCUMENTED_PAIR_PRESENT_WITH_EXACT_SKU'
    paired_rows.append(row)
    # Preserve the sealed comparison; old navigation remains in its original packet.
    copied = {k: deepcopy(v) for k, v in row.items() if k != 'catalogue_references'}
    copied['source_evidence'] = {**pair_ref, 'json_pointer': f'/rows/{n}'}
    copied['navigation_policy'] = 'Use latest main-register option links for review; original comparison navigation stays in the sealed evidence packet.'
    historical_pairs.append(copied)

qualifications = [
    'Observation time is the authenticated Squarespace export capture, not the proposal preparation or future import time. No new platform read was performed.',
    'The captured Physical-product inventory has208 products/376 variants. The80 joins cover the retained source offers only, not every variant or all188 catalogue options.',
    'Exact product ID, variant ID and source SKU identify a captured source row; they do not establish an exact current individual finish/size/build match.',
    'All720 field observations retain raw strings. Description comparisons use the original normalized-text comparison; source HTML is retained separately from current catalogue copy.',
    'Raw exported price agreement is not price adoption or currency equivalence. Raw size/weight strings have no encoded units. Stock and visibility settings do not verify physical stock or a live purchasable offer.',
    'The37 Shopify comparisons use a historical export. Current Shopify access, numeric product/variant IDs, inventory and publication remain unverified.',
    'The O028 owner correction remains authoritative for current interpretation. Do not infer two physical casts, divide source price/weight, or assign the historical arrangement SKU to the individual sculpture.',
    'Rust O051/O067 retain the same source SKU and differing raw prices. The current working price and collision/action holds remain unchanged.',
    'O006/O007 source-photo binding uncertainties, four conditional Wall Circle assignments, all photo holds and the deferred Frozen Fish identity remain unchanged.',
    'No missing-offer/absence inference, new component SKU, catalogue identity, physical verification or native write payload is proposed.',
]

value = {
    'schema': 'boldstone.authenticated-squarespace-source-observation.v1',
    'observation_id': 'SQ-ADMIN-EXPORT-20261024T005645Z-RETAINED80',
    'prepared_utc': NOW,
    'status': 'PROPOSED_ADDITIVE_DATED_SOURCE_OBSERVATION_NOT_IMPORTED',
    'squarespace_source_clock': deepcopy(index['source_clocks']['squarespace']),
    'sealed_source_field_evidence': deepcopy(sq_ref),
    'sealed_source_join_index': ref(join_path),
    'inventory_scope': {'product_type': 'Physical', 'reported_products': 208, 'reported_variants': 376,
                        'evidence': deepcopy(index['packets'][0]['seal'])},
    'retained_offer_observations': observations,
    'historical_shopify_comparison': {
        'status': 'HISTORICAL_COMPARISON_ONLY_CURRENT_SHOPIFY_UNVERIFIED',
        'source_clock_and_limits': deepcopy(index['source_clocks']['shopify']),
        'evidence': deepcopy(pair_ref),
        'previously_reported_counts': deepcopy(pairs['counts']),
        'pairs': historical_pairs,
        'current_authenticated_inventory_verified': False,
        'unpaired_historical_draft': pairs['deferred_case'],
    },
    'owner_interpretation_precedence': owner_ref,
    'unpaired_retained_source_offer': deepcopy(joins['unpaired_source_offer']),
    'qualifications': qualifications,
    'counts': {'retained_squarespace_source_tuples': 80, 'source_field_observations': 720,
               'historical_shopify_pairs': 37, 'new_catalogue_identity_matches': 0,
               'new_exact_individual_configuration_verifications': 0,
               'new_physical_verifications': 0, 'current_shopify_products_verified': 0,
               'proposed_component_sku_assignments': 0, 'native_action_payloads': 0},
}

field_rules = {
    'Title': 'Source title only; does not rename an accepted catalogue option.',
    'Description': 'Raw source HTML and normalized comparison only; does not replace owner-corrected product copy.',
    'Price': 'Raw source price string; preserve accepted working price and separate currency qualifications.',
    'Visible': 'Captured source visibility flag; no fresh public availability claim.',
    'Stock': 'Captured native stock setting; no manufactured-stock quantity claim.',
    'Weight': 'Raw source value without encoded units; no measured-weight conversion.',
    'Length': 'Raw source value without encoded units; no measured dimension.',
    'Width': 'Raw source value without encoded units; no measured dimension.',
    'Height': 'Raw source value without encoded units; no measured dimension.',
}
field_map = {
    'schema': 'boldstone.source-observation-proposed-field-map.v1',
    'base_register': ref(BASE),
    'target_json_pointer': '/' + TARGET,
    'proposed_operation': 'Main writer may add one separate root object after rebasing; no existing field replacement.',
    'object_sections': [
        {'target': '/' + TARGET + '/squarespace_source_clock', 'from': str(index_path) + '#/source_clocks/squarespace'},
        {'target': '/' + TARGET + '/retained_offer_observations', 'from': sq_ref['path'] + '#/entries', 'join': 'Existing offer_ref + exact product ID and source SKU; variant ID retained from sealed source.'},
        {'target': '/' + TARGET + '/historical_shopify_comparison/pairs', 'from': pair_ref['path'] + '#/rows', 'scope': 'Historical only; omit outdated navigation projection, retaining original packet.'},
        {'target': '/' + TARGET + '/owner_interpretation_precedence', 'from': str(BASE) + owner_ref['json_pointer']},
    ],
    'raw_field_map': [
        {'csv_column': f['csv_column'], 'target_member': 'retained_offer_observations[*].fields[*].current_csv_value_raw',
         'retained_historical_field': f['historical_source_key'], 'qualification': field_rules[f['csv_column']]}
        for f in sq['entries'][0]['fields']
    ],
    'preservation_rule': 'Every existing master root key and nested value remains unchanged by this addition, including all source snapshots/BOMs, owner O028 correction, options, specifications, prices, native action flags, photo policies and exact-match status.',
    'master_only_integration_requirements': [
        'Rebase onto the latest published master after Leaf Form and Wave filing imports;2205546a is the pinned proposal baseline, not a command to reset that master.',
        'If the target key already exists, reconcile observation_id/source export SHA; do not overwrite or duplicate an existing observation.',
        'Maintain source capture time separately from import time. Any workbook display is source-evidence metadata; no replacement of Specifications values or historical source cells is proposed.',
        'Retain O028 current owner override by stable offer_ref and owner decision ID when resolving a changed array position.',
    ],
    'workbook_cell_replacements_proposed': [],
    'native_write_payloads': [],
}
proposal = {
    'schema': 'boldstone.additive-source-observation-proposal.v1',
    'prepared_utc': NOW,
    'status': 'PREPARED_FOR_MAIN_WRITER_NOT_APPLIED',
    'base_register': ref(BASE),
    'proposed_key': TARGET,
    'proposed_value': value,
    'field_map': str(LANE / 'field-map.json'),
    'shared_register_or_workbook_writes': 0,
    'new_source_audits_or_live_reads': 0,
}
save('source-observation-proposal.json', proposal)
save('field-map.json', field_map)


def esc(s):
    return html.escape(str(s), quote=True)


def link(url, label):
    return f'<a href="{esc(url)}">{esc(label)}</a>' if url else esc(label + ' unavailable')


sections = []
for item in sorted(observations, key=lambda x: (x['offer_ref'] not in ['O051', 'O067', 'O028'], x['offer_ref'])):
    title = next(f['current_csv_value_raw'] for f in item['fields'] if f['csv_column'] == 'Title')
    rows = ''.join(f'<tr><td>{esc(f["field"])}</td><td>{esc(f["current_csv_value_raw"])}</td></tr>' for f in item['fields'])
    nav = []
    for oid in item['existing_related_option_ids']:
        o = options[oid]
        nav.append(f'<li>{esc(o["name"])} — {link(o.get("image_url"), "Image")} · {link(o.get("folder_url"), "Folder")}</li>')
    owner_note = '<p><strong>Owner correction: one design shown twice. The old source wording below remains a dated source claim.</strong></p>' if item['offer_ref'] == 'O028' else ''
    sections.append(f'<details><summary>{esc(item["offer_ref"])} — {esc(title)}</summary>{owner_note}<p>Captured source SKU: {esc(item["observed_native_source_tuple"]["sku_raw"])}</p><ul>{"".join(nav)}</ul><p>Existing related catalogue options only; this does not certify exact sale configurations.</p><table><thead><tr><th>Source field</th><th>Captured raw value</th></tr></thead><tbody>{rows}</tbody></table></details>')
page = '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Source observation proposal</title><style>body{font:16px/1.5 system-ui;max-width:1050px;margin:36px auto;padding:0 20px;color:#203029}a{color:#096446}details{border:1px solid #cbd7cf;border-radius:6px;padding:12px;margin:12px 0}summary{cursor:pointer;font-weight:650}table{border-collapse:collapse;width:100%;table-layout:fixed}td,th{border:1px solid #d5ded7;padding:8px;vertical-align:top;text-align:left;overflow-wrap:anywhere}td:first-child,th:first-child{width:22%}.note{background:#f0f5f1;padding:16px}</style><h1>Website source evidence proposed for catalogue integration</h1>'
page += f'<p class="note">Prepared for the main catalogue writer; not imported. Reuses80 Squarespace source records and37 historical Shopify comparisons. Source capture: {esc(value["squarespace_source_clock"]["captured_utc"])}. No new source audit.</p>'
page += '<p>Catalogue specifications and prices retain their accepted qualifications. Leaf Form remains one design shown twice. No current Shopify inventory has been verified.</p><p>' + link('source-observation-proposal.json', 'Proposed JSON object') + ' · ' + link('field-map.json', 'Field map and import conditions') + '</p>'
page += '<ul>' + ''.join(f'<li>{esc(q)}</li>' for q in qualifications) + '</ul>'
page += '<h2>Existing source records and related catalogue image links</h2><p>Image and folder links are from the pinned Leaf Form candidate. The main writer must retain any later verified folder changes during import.</p>' + ''.join(sections)
page += '</html>\n'
with (LANE / 'review.html').open('x') as f:
    f.write(page)

# Verify the saved proposal itself; do not re-audit platforms or the frozen source packets.
saved = json.loads((LANE / 'source-observation-proposal.json').read_text())
sv = saved['proposed_value']
checks = {
    'proposal_is_pinned_to_requested_leaf_candidate': saved['base_register']['sha256'] == BASE_SHA,
    'target_key_absent_in_pinned_base': TARGET not in base,
    'exactly_eighty_unique_source_offer_refs': len(sv['retained_offer_observations']) == len({x['offer_ref'] for x in sv['retained_offer_observations']}) == 80,
    'all720_raw_and_comparison_field_objects_copied_without_changes': all(x['fields'] == y['fields'] for x, y in zip(sv['retained_offer_observations'], sq['entries'])) and sum(len(x['fields']) for x in sv['retained_offer_observations']) == 720,
    'thirtyseven_historical_pairs_preserved_without_stale_navigation_projection': all({k:v for k,v in x.items() if k not in ['source_evidence','navigation_policy']} == {k:v for k,v in y.items() if k != 'catalogue_references'} for x,y in zip(sv['historical_shopify_comparison']['pairs'], paired_rows)) and len(sv['historical_shopify_comparison']['pairs']) == 37,
    'source_clock_preserved': sv['squarespace_source_clock'] == index['source_clocks']['squarespace'],
    'owner_override_referenced_by_stable_decision': sv['owner_interpretation_precedence']['decision_id'] == leaf_override['decision_id'],
    'no_configuration_or_physical_or_component_sku_upgrade': all(not x['exact_individual_configuration_certified_by_observation'] and not x['physical_specifications_verified_by_observation'] and not x['component_sku_assignment_proposed'] for x in sv['retained_offer_observations']),
    'no_current_shopify_upgrade': not sv['historical_shopify_comparison']['current_authenticated_inventory_verified'] and all(not x['current_shopify_presence_verified'] for x in sv['historical_shopify_comparison']['pairs']),
    'every_existing_root_value_survives_pure_addition': all(({**base, TARGET: sv})[k] == v for k,v in base.items()),
    'pinned_base_bytes_unchanged': sha(BASE) == BASE_SHA,
    'saved_review_contains_eighty_source_sections': page.count('<details>') == 80,
}
validation = {'status': 'PASS_SAVED_PROPOSAL_READBACK' if all(checks.values()) else 'FAIL_SAVED_PROPOSAL_READBACK',
              'checks': checks, 'scope': 'Serialization, reference and additive-shape checks only. No repeated source, physical, native, live platform or candidate publication audit.',
              'passed': sum(checks.values()), 'total': len(checks), 'recorded_utc': NOW,
              'pre_save_builder_correction': 'Initial pre-save count assertion treated all38 comparison rows as37 pairs. Corrected to reuse the37 exact sealed join locators, retaining the one unpaired Frozen Fish row solely as the existing deferred reference. No evidence or shared file was changed.'}
save('proposal-readback.json', validation)
if not all(checks.values()):
    raise RuntimeError('Saved proposal validation failed; retain outputs for diagnosis.')
seal = {'schema': 'boldstone.sealed-source-observation-proposal.v1', 'recorded_utc': NOW,
        'status': 'SEALED_ADDITIVE_SOURCE_OBSERVATION_PROPOSAL_NOT_IMPORTED',
        'base_register': ref(BASE), 'proposed_key': TARGET,
        'files': [ref(LANE / n) for n in ['source-observation-proposal.json', 'field-map.json', 'review.html', 'proposal-readback.json', 'prepare_proposal.py']],
        'reused_evidence': [ref(index_path), ref(join_path), deepcopy(sq_ref), deepcopy(pair_ref)],
        'scope': 'One separate proposed source-observation object and field map. Main alone integrates after current owner/Wave changes. No shared writes, new audits, owner questions or native payloads.',
        'shared_writes': 0, 'native_or_platform_writes': 0}
save('sealed-handoff.json', seal)
print(json.dumps({'status': seal['status'], 'proposal_readback': validation['status'],
                  'checks': f'{validation["passed"]}/{validation["total"]}',
                  'seal': ref(LANE / 'sealed-handoff.json'), 'review': str(LANE / 'review.html')}, indent=2))
