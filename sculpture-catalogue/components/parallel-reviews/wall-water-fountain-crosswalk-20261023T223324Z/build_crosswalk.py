from __future__ import annotations

import collections
import datetime
import hashlib
import html
import json
import pathlib
import re
import urllib.parse

HERE = pathlib.Path(__file__).resolve().parent
ROOT = pathlib.Path('/Users/tprice/Documents/boldstone/sculpture-catalogue')
REPORTS = pathlib.Path('/Users/tprice/Documents/boldstone/reports')
WALL = '/BOLDSTONE MASTER/Products/01 Wall Sculptures'
NOW = datetime.datetime.now(datetime.timezone.utc).isoformat()


def read(path):
    return json.loads(pathlib.Path(path).read_text())


def sha(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


def clean_path(value):
    value = str(value or '')
    if value.startswith('ns:'):
        value = '/' + value.split('//', 1)[1].lstrip('/')
    return value.rstrip('/')


def inside(value):
    value = clean_path(value)
    return value == WALL or value.startswith(WALL + '/')


def url_path(value):
    u = urllib.parse.urlparse(value)
    p = urllib.parse.unquote(u.path)
    if p.startswith('/home/'):
        p = p[len('/home'):]
        preview = urllib.parse.parse_qs(u.query).get('preview')
        return p + '/' + preview[0] if preview else p
    if p.startswith('/preview/'):
        return p[len('/preview'):]
    return ''


def browse(path):
    return 'https://www.dropbox.com/home' + urllib.parse.quote(clean_path(path), safe='/')


pointer = read(HERE / 'baseline-pointer.json')
register_path = ROOT / pointer['register']
register = read(register_path)
assert sha(register_path) == pointer['register_sha256']
model_ref = register['master_input_manifest']['source_component_model']
model_path = pathlib.Path(model_ref['snapshot'])
model = read(model_path)
assert sha(model_path) == model_ref['sha256']
map_ref = pointer['current_native_reference_map']
map_path = ROOT / map_ref['path']
native_map = read(map_path)
assert sha(map_path) == map_ref['sha256']
family_path = ROOT / 'components/reconciliation/deco004-photo-and-physical-review-2026-10-23/fresh-family-inventory.json'
families = read(family_path)
structure_path = REPORTS / 'dropbox-existing-image-filing-review-20261023T214900Z/native-source-snapshot.json'
structure = read(structure_path)
policy_path = REPORTS / 'dropbox-water-fountains-wall-category-policy-20261023T215628Z/policy-and-current-structure.json'
policy = read(policy_path)

inputs = [
    {'path': str(p), 'sha256': sha(p), 'scope': scope}
    for p, scope in [
        (register_path, 'Published local catalogue baseline; not live platform inventory'),
        (model_path, 'Frozen historical in-root component/group and platform snapshot model'),
        (map_path, 'Retained current native reference map; scoped, not a whole-library census'),
        (family_path, 'Sealed same-day relevant-family inventories; reused without live reads'),
        (structure_path, 'Sealed in-root Bone Water/Knightsbridge/Coral source snapshot'),
        (policy_path, 'Owner inclusion/cancellation policy only; outside-root contents excluded'),
    ]
]

# Only in-root entries are admitted from retained inventories.
observed = {}
for record in families['records']:
    if not inside(record.get('display_path')):
        continue
    for page in record.get('pages', []):
        payload = page.get('structuredContent', {})
        for entry in payload.get('entries', []):
            if entry and inside(entry.get('path_display') or entry.get('path')):
                observed[entry['file_id']] = dict(entry, observation_source=str(family_path))
for entry in structure['files']:
    if inside(entry.get('path_display') or entry.get('path')):
        observed[entry['file_id']] = dict(entry, observation_source=str(structure_path))
for fid, obj in native_map['current_objects'].items():
    if inside(obj.get('display_path') or obj.get('path')):
        observed[fid] = dict(obj, observation_source=str(map_path))

active = set(register['active_option_ids'])
options = {v['product_id']: v for v in register['options']}
water_ids = [
    v['product_id'] for v in register['options']
    if v['product_id'] in active
    and (re.search(r'water|fountain|catcher|knightsbridge', v['name'], re.I)
         or str(v.get('build_class', '')).lower() == 'water feature')
]
historical_groups = [
    v for v in model['groups']
    if inside(v.get('path'))
    and re.search(r'water|fountain|catcher', v.get('name', '') + ' ' + v.get('family', ''), re.I)
]
assets_by_folder = collections.defaultdict(set)
for asset in model['assets']:
    if inside(asset.get('path')):
        assets_by_folder[asset.get('folder_id')].add(asset['id'])
dispositions = {v['source_component_id']: v for v in register['source_component_dispositions']}
current_components = {v['component_id'] for v in register['components']}


def normalized_components(old):
    result = set()
    for cid in old:
        d = dispositions.get(cid)
        if d:
            result.update(d.get('component_targets', []))
        elif cid in current_components:
            result.add(cid)
    return sorted(result)


group_rows, excluded = [], []
for g in historical_groups:
    fid = g['id']
    current = native_map['current_objects'].get(fid)
    if current and not inside(current.get('display_path') or current.get('path')):
        excluded.append({
            'group_ref': g['group_ref'], 'historical_folder_id': fid,
            'historical_in_root_name': g['name'], 'historical_role': g.get('role'),
            'disposition': 'EXCLUDE_CURRENT_OUTSIDE_ROOT_PROCESS_SOURCE',
            'reason': 'Retained current map places this making/process folder outside the permitted root. No current contents or links imported.',
            'current_assets_inspected': 0, 'count_increment': 0,
        })
        continue
    file_ids = assets_by_folder[fid]
    exact_folder = sorted(
        oid for oid in active
        if fid in [options[oid].get('folder_id'), options[oid].get('context_folder_id')]
    )
    exact_file = sorted(
        oid for oid in active
        if file_ids.intersection([options[oid].get('file_id'), options[oid].get('context_file_id')])
    )
    obs = observed.get(fid, {})
    path = clean_path(obs.get('display_path') or obs.get('path_display') or obs.get('path') or g['path'])
    folder_url = browse(path)
    grade = 'REUSED_RETAINED_NATIVE_SCOPE' if obs else 'HISTORICAL_GROUP_ONLY_PATH_NOT_LIVE_RECHECKED'
    if not obs and exact_file:
        # The historical Chiswick solo folder was replaced. Use the existing
        # catalogue destination and disclose that the old folder ID is not current.
        candidate = options[exact_file[0]]
        if candidate.get('folder_id') != fid:
            folder_url = candidate['folder_url']
            grade = 'HISTORICAL_FOLDER_JOIN_BY_STABLE_FILE_TO_CURRENT_CATALOGUE_DESTINATION'
    group_rows.append({
        'group_ref': g['group_ref'], 'historical_folder_id': fid,
        'historical_name': g['name'], 'historical_path': g['path'],
        'source_role': g.get('role'), 'source_component_ids': g.get('component_ids', []),
        'normalized_component_candidates': normalized_components(g.get('component_ids', [])),
        'existing_option_joins_by_folder_id': exact_folder,
        'existing_option_joins_by_file_id': exact_file,
        'folder_url': folder_url, 'reference_grade': grade,
        'member_identity_grade': 'Retained group association only; no new member/position/finish assignment',
        'count_increment': 0,
    })

offers = {v['offer_ref']: v for v in register['source_platform_offer_coverage']}
source_offers = {v['offer_ref']: v for v in model['platform_records']}


def listing_evidence(o):
    c = o.get('current_listing_reconciliation', {})
    variants = []
    for platform, state in c.get('platforms', {}).items():
        for item in state.get('supported_individual_native_variants', []):
            v = item.get('native_variant', item)
            variants.append({
                'platform': platform, 'offer_ref': item.get('offer_ref'),
                'native_product_id': v.get('native_product_id'),
                'native_variant_id': v.get('native_variant_id'),
                'sku_raw': v.get('sku_raw'), 'relationship': item.get('relationship'),
                'source_locator': v.get('source_locator'),
                'grade': 'Retained snapshot-supported tuple; current account/configuration/stock not certified',
            })
    related = set(o.get('related_platform_offer_refs', []))
    for ref, offer in offers.items():
        if o['product_id'] in offer.get('related_product_ids', []):
            related.add(ref)
    return {
        'overall_disposition': c.get('overall_disposition'),
        'current_source_resolution': o.get('current_listing_resolution', {}).get('current_source_resolution_disposition'),
        'snapshot_individual_variants': variants,
        'related_offer_refs': sorted(related),
        'individual_platform_source_evidence': bool(variants),
        'source_supported_refs': o.get('source_supported_platform_scope_refs', []),
        'live_admin_or_hidden_draft_inventory_checked_this_pass': False,
    }


case_rows = []
for oid in water_ids:
    o = options[oid]
    l = listing_evidence(o)
    case_rows.append({
        'case_id': 'WALL-WATER:' + oid, 'record_kind': 'EXISTING_CATALOGUE_OPTION',
        'option_id': oid, 'canonical_design_id': o['canonical_design_id'],
        'name': o['name'], 'sale_unit': o['sale_unit'],
        'file_id': o['file_id'], 'folder_id': o['folder_id'],
        'image_url': o['image_url'], 'folder_url': o['folder_url'],
        'context_file_id': o.get('context_file_id'), 'context_folder_id': o.get('context_folder_id'),
        'context_image_url': o.get('context_image_url'), 'context_folder_url': o.get('context_folder_url'),
        'source_group_refs': [g['group_ref'] for g in group_rows if oid in set(g['existing_option_joins_by_folder_id'] + g['existing_option_joins_by_file_id'])],
        'listing': l,
        'catalogue_disposition': 'ALREADY_PRESENT_DO_NOT_CREATE_DUPLICATE_OPTION',
        'platform_disposition': l['overall_disposition'],
        'next_dependency': (
            'Retain existing snapshot tuple and recorded configuration conflicts; no platform edits authorized.'
            if l['individual_platform_source_evidence'] else
            'Exact individual platform record/configuration remains unsupported in checked snapshots. Do not assert live absence or reuse a family/set SKU.'
        ),
        'new_option_count_increment': 0,
    })

moonwhite = options['BSI-6FE9343F889E']
case_rows.append({
    'case_id': 'WALL-WATER:MSW-SECOND-MEMBER',
    'record_kind': 'EXISTING_WALL_OPTION_WITH_WATER_SOURCE_BINDING_GAP',
    'option_id': moonwhite['product_id'], 'canonical_design_id': moonwhite['canonical_design_id'],
    'name': 'Moon and Shellwave 2 — White: water-scene member mapping',
    'file_id': moonwhite['file_id'], 'folder_id': moonwhite['folder_id'],
    'image_url': moonwhite['image_url'], 'folder_url': moonwhite['folder_url'],
    'water_source_group_ref': 'G194',
    'water_source_file_id': 'id:cnqzTNngPVsAAAAAAAubvA',
    'water_scene_image_url': options['BSI-D886F539DD3E']['image_url'],
    'water_scene_folder_url': options['BSI-D886F539DD3E']['folder_url'],
    'existing_source_components': ['BC-MSW-MOON', 'BC-MSW-SPIRAL'],
    'existing_water_option': 'BSI-D886F539DD3E',
    'listing': listing_evidence(moonwhite),
    'catalogue_disposition': 'BOTH_DESIGNS_EXIST_NO_NEW_DESIGN_ESTABLISHED',
    'next_dependency': 'G194 historically associates both designs. Only design1 has an explicitly Water Feature-labelled current option. Exact water-build/sale-unit/selected-member binding for design2 is unresolved; ordinary set listings do not prove it. No new option or source binding proposed.',
    'new_option_count_increment': 0,
})

arrangement = next(v for v in register['arrangement_context_references'] if v['reference_id'] == 'REF-MOONPHASE-WATER-FEATURE-WHITE-01')
g253 = next(v for v in group_rows if v['group_ref'] == 'G253')
case_rows.append({
    'case_id': 'WALL-WATER:MOONPHASE-ARRANGEMENT',
    'record_kind': 'EXISTING_ARRANGEMENT_REFERENCE_WITH_MEMBER_BINDING_GAP',
    'option_id': None, 'reference_id': arrangement['reference_id'], 'name': arrangement['name'],
    'file_id': arrangement['file_id'], 'folder_id': arrangement['folder_id'],
    'image_url': arrangement['image_url'], 'folder_url': arrangement['folder_url'],
    'historical_source_component_ids': g253['source_component_ids'],
    'normalized_current_design_candidates': g253['normalized_component_candidates'],
    'confirmed_member_option_ids': arrangement['confirmed_member_option_ids'],
    'related_historical_wall_set_offer': 'O030',
    'related_source_sku': offers['O030']['source_sku'],
    'related_sku_scope': 'Historical five-piece dry-wall set, not a verified water-feature or individual panel SKU',
    'catalogue_disposition': 'ARRANGEMENT_ALREADY_RETAINED_NO_ADDITIONAL_PRODUCT_ESTABLISHED',
    'next_dependency': 'Five historical manufacturing source codes collapse to four current design identities. Exact water-layout member options, sale unit and water-build applicability remain unbound. Keep historic O030 five-piece quantity separate from current design count and this depicted water arrangement.',
    'new_option_count_increment': 0,
})

# Related offers are included only through existing graph edges or the explicitly
# retained wall-set reference. No title-only listing match is introduced.
related_refs = {'O030'}
for row in case_rows:
    related_refs.update(row.get('listing', {}).get('related_offer_refs', []))
offer_rows = []
for ref in sorted(related_refs):
    v = offers[ref]
    original = source_offers.get(ref, {})
    offer_rows.append({
        **{k: v.get(k) for k in ['offer_ref', 'platform', 'source_title', 'source_sku', 'squarespace_id', 'shopify_handle', 'source_url', 'source_sale_scope', 'native_parts', 'component_ids', 'related_product_ids', 'exact_supported_target_ids', 'coverage_state', 'canonical_graph_coverage_state']},
        'frozen_model_source_sku': original.get('sku'),
        'frozen_model_squarespace_id': original.get('sq_id'),
        'frozen_model_shopify_handle': original.get('sh_handle'),
        'no_current_live_platform_verification': True,
        'historical_source_not_new_canonical_product': True,
    })

function_rules = [
    {'scope': 'Deco Fountain / Fountain Palm Egyptian', 'source_ref': 'O014',
     'existing_target': 'BSI-BB6D7F02662A',
     'disposition': 'FUNCTION_OR_ALIAS_LABEL_ALREADY_MAPPED_TO_EXISTING_DESIGN',
     'basis': 'Existing source graph and native listing tuple map the retained Deco Fountain name to the existing Egyptian White option. No extra sculpture follows from a function label.'},
    {'scope': 'Moon and Shellwave water scene', 'source_group': 'G194',
     'disposition': 'FUNCTION_SCENE_IS_NOT_A_THIRD_DESIGN',
     'basis': 'Two existing design identities are recorded in the historical group. Water-build and sale-unit bindings remain separate source questions.'},
    {'scope': 'Moonphases water scene', 'source_group': 'G253',
     'disposition': 'ARRANGEMENT_FUNCTION_IS_NOT_A_NEW_COMPONENT_IDENTITY',
     'basis': 'Arrangement is retained; exact member option bindings are unset. Historical5 source codes are normalized to4 current design identities.'},
    {'scope': 'Japanese Raked Water naming', 'source_ref': 'O017',
     'disposition': 'LEXICAL_WATER_NAME_DOES_NOT_ESTABLISH_FOUNTAIN_FUNCTION',
     'basis': 'Retained source describes an ordinary Raked Spiral wall arrangement. No water-build inference or new water-feature record is introduced.'},
]
explicit_function_labels = []
for dataset in ['source_review_reconciliation', 'source_component_dispositions']:
    for i, v in enumerate(register[dataset]):
        if re.search(r'function.only|function-only|function only', json.dumps(v), re.I):
            explicit_function_labels.append({'dataset': dataset, 'index': i})

summary = {
    'recorded_utc': NOW, 'scope': WALL,
    'baseline_register': pointer['register'], 'baseline_register_sha256': pointer['register_sha256'],
    'existing_named_water_options': len(water_ids),
    'existing_options_with_snapshot_individual_variant_evidence': sum(bool(r['listing']['individual_platform_source_evidence']) for r in case_rows[:len(water_ids)]),
    'existing_options_without_snapshot_individual_variant_evidence': sum(not r['listing']['individual_platform_source_evidence'] for r in case_rows[:len(water_ids)]),
    'historical_source_groups_checked': len(historical_groups),
    'eligible_retained_in_root_groups': len(group_rows),
    'historical_groups_excluded_current_outside_root': len(excluded),
    'crosswalk_cases': len(case_rows), 'related_retained_offer_records': len(offer_rows),
    'mapping_gap_cases': ['WALL-WATER:MSW-SECOND-MEMBER', 'WALL-WATER:MOONPHASE-ARRANGEMENT'],
    'explicit_function_only_tag_search': {'matches': explicit_function_labels, 'scope': 'Only current register source-review reconciliation and source-component dispositions; not global historical absence'},
    'new_designs_or_missing_current_options_established': 0,
    'new_option_count_increment': 0, 'new_owner_questions': 0,
    'new_image_reviews': 0, 'live_reads': 0,
    'canonical_or_workbook_writes': 0, 'dropbox_content_writes': 0, 'platform_writes': 0,
    'limitations': [
        'This is a crosswalk of explicitly tagged retained local records, not a visual census or a certified whole-library water-feature count.',
        'Historical source group associations are not fresh file-level finish, position or water-build certifications.',
        'No current authenticated admin, hidden/draft listing, stock or exact physical configuration was checked.',
        'Snapshot non-match does not establish live listing absence. Set/family SKUs are not assigned to individual water panels.',
        'Outside-root category inventory, cancelled consolidations, archives and their images are excluded.',
        'Current187 active options remain a catalogue count, not physical stock or an independently certified full-library total.',
    ],
    'owner_policy_retained': {'owner_message': policy['owner_message'], 'knightsbridge_stays_in_wall_root': True, 'outbound_move_cancelled': True},
}

checks = {
    'published_register_hash': sha(register_path) == pointer['register_sha256'],
    'frozen_source_model_hash': sha(model_path) == model_ref['sha256'],
    'current_reference_map_hash': sha(map_path) == map_ref['sha256'],
    '11_existing_seed_options': len(water_ids) == 11,
    'all_seed_options_active': set(water_ids).issubset(active),
    '3_existing_snapshot_variant_options': summary['existing_options_with_snapshot_individual_variant_evidence'] == 3,
    '8_existing_options_without_individual_snapshot_tuple': summary['existing_options_without_snapshot_individual_variant_evidence'] == 8,
    '20_historical_groups_accounted': len(historical_groups) == len(group_rows) + len(excluded) == 20,
    '19_current_inroot_source_groups': len(group_rows) == 19,
    'making_process_outside_scope_excluded': len(excluded) == 1 and excluded[0]['group_ref'] == 'G165',
    'Moonphase_historical5_current4': len(g253['source_component_ids']) == 5 and len(g253['normalized_component_candidates']) == 4,
    'Moonphase_exact_members_remain_unbound': arrangement['confirmed_member_option_ids'] == [],
    'no_active_Moonphase5': not any(re.search(r'Moonphase\s+(Five|5)\b', options[v]['name'], re.I) for v in active),
    'all_case_image_urls_within_root': all(inside(url_path(v['image_url'])) for v in case_rows),
    'all_case_folder_urls_within_root': all(inside(url_path(v['folder_url'])) for v in case_rows),
    'all_group_urls_within_root': all(inside(url_path(v['folder_url'])) for v in group_rows),
    'all_admitted_native_paths_within_root': all(inside(v.get('display_path') or v.get('path_display') or v.get('path')) for v in observed.values()),
    'unique_cases': len({v['case_id'] for v in case_rows}) == len(case_rows),
    'no_count_increment': all(v['new_option_count_increment'] == 0 for v in case_rows),
    'existing_reference_ids_retained': all(v.get('option_id') in active for v in case_rows if v.get('option_id')),
    'offer_skus_retained_from_snapshot': all(v['source_sku'] == v['frozen_model_source_sku'] for v in offer_rows),
    'offer_native_product_ids_retained': all(v['squarespace_id'] == v['frozen_model_squarespace_id'] for v in offer_rows),
    'offer_shopify_handles_retained': all(v['shopify_handle'] == v['frozen_model_shopify_handle'] for v in offer_rows),
    'input_files_still_match': all(sha(v['path']) == v['sha256'] for v in inputs),
}

outputs = {
    'input-manifest.json': inputs, 'current-option-and-source-crosswalk.json': case_rows,
    'in-root-group-crosswalk.json': group_rows, 'scope-exclusions.json': excluded,
    'retained-platform-offers.json': offer_rows, 'function-and-arrangement-dispositions.json': function_rules,
    'summary.json': summary,
}
for name, value in outputs.items():
    (HERE / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')

e = lambda value: html.escape(str(value), quote=True)
rows = []
for v in case_rows:
    l = v.get('listing', {})
    skus = sorted({z['sku_raw'] for z in l.get('snapshot_individual_variants', []) if z.get('sku_raw')})
    evidence = ', '.join(skus) or ('No supported individual snapshot tuple' if l else 'Arrangement/member mapping unresolved')
    rows.append('<tr><td>' + e(v['name']) + '<br><small>' + e(v.get('option_id') or v.get('reference_id')) + '</small></td><td><a href="' + e(v['image_url']) + '">Image</a> · <a href="' + e(v['folder_url']) + '">Folder</a></td><td>' + e(evidence) + '</td><td>' + e(v['next_dependency']) + '</td></tr>')
page = '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Wall Sculptures water-feature crosswalk</title><style>body{font:16px/1.5 system-ui;color:#202020;margin:32px;max-width:1250px}table{border-collapse:collapse;width:100%}th,td{padding:12px;border:1px solid #ccc;text-align:left;vertical-align:top}th{background:#eee}a{color:#164f93}small{overflow-wrap:anywhere}</style><h1>Wall Sculptures: water-feature catalogue and source crosswalk</h1><p>Eleven existing named water/fountain options, plus two existing-record mapping questions. Three of the eleven have retained individual-listing variant evidence; eight have no supported individual tuple in the checked snapshots. No products or counts changed.</p><table><thead><tr><th>Record</th><th>Dropbox sources</th><th>Retained listing evidence</th><th>Remaining dependency</th></tr></thead><tbody>' + ''.join(rows) + '</tbody></table><p>All links are inside the permitted Wall Sculptures root. Listing details are retained snapshots, not a live account inventory. Exact scene origins, stock, physical specifications and water-system performance remain unverified.</p></html>'
(HERE / 'water-feature-crosswalk.html').write_text(page)
checks['13_case_report_rows_26_links'] = page.count('<tr><td>') == len(case_rows) == 13 and page.count('<a href=') == 26

validation = {'recorded_utc': NOW, 'status': 'PASS' if all(checks.values()) else 'FAIL', 'checks': checks, 'checks_passed': sum(checks.values()), 'checks_total': len(checks), 'failed': [k for k, v in checks.items() if not v]}
(HERE / 'validation.json').write_text(json.dumps(validation, indent=2) + '\n')
manifest = {'recorded_utc': NOW, 'status': validation['status'], 'scope': WALL, 'files': [{'path': str(HERE / name), 'sha256': sha(HERE / name)} for name in [*outputs, 'water-feature-crosswalk.html', 'validation.json', 'build_crosswalk.py']], 'summary': summary, 'checks_passed': validation['checks_passed'], 'checks_total': validation['checks_total'], 'canonical_applied': False}
handoff = HERE / 'sealed-handoff.json'
handoff.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n')
print(json.dumps({'status': validation['status'], 'checks': f"{validation['checks_passed']}/{validation['checks_total']}", 'failed': validation['failed'], 'handoff': str(handoff), 'sha256': sha(handoff), 'report': str(HERE / 'water-feature-crosswalk.html'), 'summary_counts': {k: summary[k] for k in ['existing_named_water_options', 'existing_options_with_snapshot_individual_variant_evidence', 'existing_options_without_snapshot_individual_variant_evidence', 'eligible_retained_in_root_groups', 'crosswalk_cases', 'related_retained_offer_records']}}, indent=2))
assert all(checks.values())
