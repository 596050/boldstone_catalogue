"""Bounded publication receipt/pointer/control readback; no content QA rerun."""
from pathlib import Path
import collections
import datetime
import hashlib
import json

B = Path('/Users/tprice/Documents/boldstone/sculpture-catalogue')
H = B / 'components/reconciliation/whole-gallery-navigation-master-2026-10-24'
OUT = Path(__file__).resolve().parent
EXPECTED_POINTER = '5638de40cee85948c4c1df49828b2efd475789d8026db998ca3c758b92a5f7b4'
EXPECTED_RECEIPT = 'e1bf10e0f42df0d936f94005b4c1679b5ac1eea8c74f4532e4e0ca0d243fa80d'
checks = collections.Counter()
failures = []
inputs = {}

def load(p):
    return json.loads(Path(p).read_text())

def digest(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

def check(ok, category, context=''):
    checks[category] += 1
    if not ok:
        failures.append({'category': category, 'context': str(context)})

def resolve(p):
    p = Path(p)
    return p if p.is_absolute() else B / p

def bind(p, expected, category):
    p = resolve(p)
    check(p.is_file() and digest(p) == expected, category, p)
    inputs[str(p)] = expected

pointer_path = B / 'current-master.json'
receipt_path = H / 'publication-receipt.json'
bind(pointer_path, EXPECTED_POINTER, 'explicit_final_pointer')
bind(receipt_path, EXPECTED_RECEIPT, 'published_receipt')
pointer = load(pointer_path)
receipt = load(receipt_path)
snapshots = OUT / 'published-snapshots'
snapshots.mkdir(exist_ok=False)
for p in [pointer_path, receipt_path] + [Path(x) for x in receipt['controls_sha256']]:
    (snapshots / p.relative_to(B).as_posix().replace('/', '__')).write_bytes(p.read_bytes())

check(receipt['status'] == 'PASS_PUBLISHED_AND_READ_BACK' and receipt['current_master_pointer_sha256'] == EXPECTED_POINTER, 'receipt_status_and_pointer')
check(receipt['preceding_pointer_sha256'] == '64e22f7c3aaca874817b11b497294c4b40b17564b717ce7c05e41ffbc44f22b7', 'preceding_baseline_bound')
check(resolve(pointer['publication_receipt']) == receipt_path, 'pointer_routes_to_final_receipt')
for key in ['workbook', 'register']:
    check(resolve(pointer[key]) == resolve(receipt[key]) and pointer[key + '_sha256'] == receipt[key + '_sha256'], 'pointer_file_identity', key)
    bind(pointer[key], pointer[key + '_sha256'], 'published_file_hash')
for key, field in [('current_asset_reference_map', 'asset_map_sha256'), ('current_native_reference_map', 'native_map_sha256')]:
    ref = pointer[key]
    check(ref['sha256'] == receipt[field], 'published_map_identity', key)
    bind(ref['path'], ref['sha256'], 'published_map_hash')
check(pointer['current_native_reference_map']['cumulative_object_count'] == 7061, 'native_wrapper_count_metadata')

for path, expected in receipt['controls_sha256'].items():
    bind(path, expected, 'published_control_hash')
    control = load(path)
    check(control['current_master_catalogue'] == pointer, 'full_embedded_pointer_equal', path)
    check(control['current_complete_gallery_mapping'] == pointer['current_complete_gallery_mapping'], 'full_gallery_metadata_equal', path)
    check(control['current_master_workbook'] == pointer['workbook'] and control['current_master_register'] == pointer['register'], 'control_scalar_routes_equal', path)
    if 'workbook' in control:
        check(control['workbook'] == pointer['workbook'], 'control_legacy_workbook_route_equal', path)

evidence = {}
for key, ref in receipt['verification'].items():
    bind(ref['path'], ref['sha256'], 'publication_readback_receipt_hash')
    item = load(resolve(ref['path'])); evidence[key] = item
    check(item['status'].startswith('PASS') and not item.get('failures'), 'prior_readback_terminal_PASS', key)
    if 'workbook_sha256' in item:
        check(item['workbook_sha256'] == receipt['workbook_sha256'], 'prior_readback_workbook_binding', key)
    if 'register_sha256' in item:
        check(item['register_sha256'] == receipt['register_sha256'], 'prior_readback_register_binding', key)
check(evidence['workbook_link_addendum']['after_workbook_sha256'] == receipt['workbook_sha256'] and evidence['workbook_link_addendum']['additional_local_report_target_changes'] == 69 and evidence['workbook_link_addendum']['value_formula_style_changes_in_this_addendum'] == 0, 'final_69_report_links_only_addendum')
check(evidence['current_data']['asset_map_sha256'] == receipt['asset_map_sha256'] and evidence['current_data']['native_map_sha256'] == receipt['native_map_sha256'], 'prior_readback_support_map_bindings')
check(evidence['current_data']['physical_commercial_or_identity_changes'] == 0 and receipt['new_physical_or_commercial_field_values'] == 0 and receipt['external_writes'] == 0, 'release_preserves_physical_commercial_boundaries')

qa_ref = receipt['independent_workbook_qa']
bind(qa_ref['path'], qa_ref['sha256'], 'independent_final_workbook_QA_seal')
qa = load(resolve(qa_ref['path']))
check(qa['status'] == 'PASS_INDEPENDENT_FINAL_WORKBOOK_QA_WITH_REPORT_ROUTING' and qa['candidate_sha256'] == receipt['workbook_sha256'], 'workbook_QA_exact_released_bytes')
check((qa['prior_saved_package_checks_passed'], qa['prior_artifact_tool_value_reads_passed'], qa['final_delta_link_checks_passed']) == (110076, 44, 69), 'sealed_QA_scope_reused_without_rerun')
check(qa['native_Excel_runtime_evaluated'] is False, 'native_runtime_boundary_retained')
for path, expected in qa['files'].items():
    bind(path, expected, 'independent_QA_declared_artifact_hash')

mapping = pointer['current_complete_gallery_mapping']
for key in ['source_gallery_handoff', 'independent_source_gallery_qa', 'complete_native_roles', 'remaining_work']:
    ref = mapping[key]
    bind(ref['path'], ref['sha256'], 'published_source_evidence_binding')
check(mapping['counts'] == receipt['complete_gallery_counts'], 'published_gallery_count_metadata_equal')
check((mapping['counts']['squarespace_exact_photo_uncertainties'], mapping['counts']['shopify_exact_photo_uncertainties'], mapping['counts']['native_roles_retained_uncertain']) == (29, 3, 4), 'retained_source_and_role_uncertainties')
check(mapping['new_exact_platform_variant_assignments'] == mapping['new_physical_verifications'] == mapping['native_or_platform_writes'] == 0, 'gallery_claim_boundaries')
for key, path in mapping['readers'].items():
    check(resolve(path).is_file(), 'retained_reader_entrypoint_exists', key)
check('frozen baseline readers preserve the old selected references' in mapping['scope'] and 'Current reader projection follows publication' in mapping['scope'], 'preprojection_reader_boundary_explicit')
remaining = load(mapping['remaining_work']['path'])
check(remaining['held_identities']['frozen_fish_legacy_vs_FFS2'] == 'EXACT_PAIR_OWNER_ANSWER_PENDING_IN_EXISTING_PROMPT', 'FFL1_owner_hold_retained')
check(remaining['deferred_photography']['installation_gaps'] == 22 and remaining['deferred_photography']['series_gaps'] == 1, 'deferred_photography_retained')
check((receipt['active_options'], receipt['retained_options'], receipt['retained_component_ids'], receipt['working_design_groups']) == (188, 189, 112, 110), 'release_catalogue_count_metadata')
for p, expected in list(inputs.items()):
    check(digest(p) == expected, 'inputs_unchanged_at_readback_end', p)

result = {'status': 'PASS' if not failures else 'FAIL', 'checked_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'scope': 'Bounded postpublication pointer, three controls, exact file hashes and sealed terminal receipts. Full gallery and workbook QA not repeated. B current reader projection remains a subsequent metadata-only publication.',
          'pointer_sha256': EXPECTED_POINTER, 'publication_receipt_sha256': EXPECTED_RECEIPT,
          'checks_total': sum(checks.values()), 'checks_passed': sum(checks.values()) - len(failures), 'check_categories': dict(checks), 'failures': failures,
          'published_register_sha256': receipt['register_sha256'], 'published_workbook_sha256': receipt['workbook_sha256'],
          'independent_workbook_QA': qa_ref, 'counts': receipt['complete_gallery_counts'],
          'input_hashes': inputs, 'snapshots': {str(p): digest(p) for p in snapshots.iterdir()},
          'live_calls': 0, 'native_writes': 0, 'canonical_writes': 0, 'owner_questions_reissued': 0}
out = OUT / 'independent-publication-readback.json'
out.write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({k: result[k] for k in ['status', 'checks_total', 'checks_passed', 'failures', 'pointer_sha256']}))
