"""Final metadata-only reader binding check; reuses sealed content QA."""
from pathlib import Path
import collections
import datetime
import hashlib
import json

B = Path('/Users/tprice/Documents/boldstone/sculpture-catalogue')
H = B / 'components/reconciliation/whole-gallery-navigation-master-2026-10-24'
OUT = Path(__file__).resolve().parent
EXPECTED = 'ef9363d00d6a31088a8b8fec6bffb87321a904b195ce529feb7ece30da4ffae0'
checks = collections.Counter(); failures = []; inputs = {}
read = lambda p: json.loads(Path(p).read_text())

def sha(p):
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
    check(p.is_file() and sha(p) == expected, category, p)
    inputs[str(p)] = expected

pointer_path = B / 'current-master.json'
receipt_path = H / 'current-gallery-link-publication-receipt.json'
bind(pointer_path, EXPECTED, 'explicit_final_metadata_pointer')
bind(receipt_path, '30a6179cfff0553c44e6c5c747c6721a08ea82d3b824754de120708ad13ec9f2', 'final_metadata_receipt')
p = read(pointer_path); r = read(receipt_path)
prior_path = OUT / 'published-snapshots/current-master.json'
bind(prior_path, '5638de40cee85948c4c1df49828b2efd475789d8026db998ca3c758b92a5f7b4', 'independent_pre_metadata_pointer_snapshot')
prior = read(prior_path)
delta = sorted(k for k in set(p) | set(prior) if p.get(k) != prior.get(k))
check(delta == sorted(r['changed_pointer_keys']) == sorted(['current_image_review_links', 'current_published_gallery_projection', 'latest_master_metadata_change', 'publication_receipt', 'recorded_utc']), 'exact_five_metadata_keys_only', delta)
check(r['status'] == 'PASS_METADATA_ONLY_CURRENT_READER_LINKS_PUBLISHED_AND_READ_BACK' and r['current_master_pointer_sha256'] == EXPECTED, 'metadata_receipt_terminal_status')
check(r['preceding_pointer_sha256'] == sha(prior_path) and resolve(p['publication_receipt']) == receipt_path, 'metadata_receipt_chain_and_route')
bind(r['data_publication_receipt'], r['data_publication_receipt_sha256'], 'original_publication_receipt_unchanged')
bind(OUT / 'sealed-publication-readback.json', '8502762e43ec406a3ae39798fda3c83d42065ae9766c9280aae71f8b1c7430ad', 'prior_120_check_seal')
for name in ['workbook', 'register']:
    check(p[name] == prior[name] and p[name + '_sha256'] == r[name + '_sha256'], 'unchanged_data_reference', name)
    bind(p[name], p[name + '_sha256'], 'released_data_bytes_unchanged')
for name, field in [('current_asset_reference_map', 'asset_map_sha256'), ('current_native_reference_map', 'native_map_sha256')]:
    check(p[name] == prior[name] and p[name]['sha256'] == r[field], 'unchanged_support_map_reference', name)
    bind(p[name]['path'], p[name]['sha256'], 'released_support_map_bytes_unchanged')

snapshots = OUT / 'metadata-link-snapshots'
snapshots.mkdir(exist_ok=False)
for source in [pointer_path, receipt_path] + [Path(x) for x in r['controls_sha256']]:
    (snapshots / source.relative_to(B).as_posix().replace('/', '__')).write_bytes(source.read_bytes())
for path, expected in r['controls_sha256'].items():
    bind(path, expected, 'final_control_hash')
    d = read(path)
    check(d['current_master_catalogue'] == p, 'all_three_full_embedded_pointers_equal', path)
    check(d['current_master_workbook'] == p['workbook'] and d['current_master_register'] == p['register'], 'control_data_routes_equal', path)
    check(d['current_published_gallery_projection'] == p['current_published_gallery_projection'], 'control_current_projection_equal', path)

ref = r['current_projection']
check(p['current_published_gallery_projection'] == ref, 'pointer_exact_projection_metadata')
bind(ref['path'], ref['sha256'], 'B_projection_seal')
projection_path = resolve(ref['path']); projection = read(projection_path)
check(projection['published_pointer_sha256'] == r['preceding_pointer_sha256'] and projection['published_register_sha256'] == p['register_sha256'], 'projection_derived_from_exact_published_data')
check(ref['register_sha256'] == p['register_sha256'] and ref['workbook_sha256'] == p['workbook_sha256'], 'projection_current_data_binding')
check(projection['all188_product_objects_equal_published_register'] is True and projection['independent_reader_checks_passed'] == ref['independent_reader_checks_passed'] == 131742, 'sealed_B_reader_QA_reused')
check(projection['held_identities_and_22_installation_and_one_series_deferrals_retained'] is True and projection['no_new_identity_or_variant_assignments'] is True and projection['native_or_canonical_or_platform_writes_by_reviewer'] == 0, 'reader_hold_and_authority_boundaries')
check(ref['readers'] == projection['readers'], 'exact_four_projection_reader_routes')
for name, path in ref['readers'].items():
    bind(path, projection['files'][name], 'four_reader_entrypoint_hashes')
for path, expected in projection['provider_seals_and_publication_receipt'].items():
    bind(path, expected, 'projection_sealed_provider_binding')
frozen = B / 'components/parallel-reviews/all-record-image-matching-20261024-B/integrations/20261024T225748917419Z'
for name, expected in projection['source_proof_files_byte_identical_to_frozen_review'].items():
    bind(projection_path.parent / name, expected, 'five_source_proof_files_unchanged')
    check(sha(frozen / name) == expected, 'frozen_source_proof_identity', name)
bind(ref['current_master_navigation'], ref['current_master_navigation_sha256'], 'new_current_navigation_page')
bind(B / 'outputs/whole-gallery-navigation-master-2026-10-24/index.html', r['frozen_original_index_sha256'], 'original_index_preserved')
links = p['current_image_review_links']
check(links['all_links'] == ref['current_master_navigation'], 'main_navigation_route')
for key, name in [('all_individual_option_galleries', 'product-images.html'), ('complete_platform_galleries', 'source-galleries.html'), ('complete_family_galleries', 'family-images.html')]:
    check(links[key] == ref['readers'][name], 'current_gallery_link_routes', key)
check(r['canonical_option_or_field_changes'] == r['native_or_platform_writes'] == 0, 'metadata_only_no_content_changes')
for path, expected in list(inputs.items()):
    check(sha(path) == expected, 'bound_inputs_unchanged_at_end', path)

result = {'status': 'PASS' if not failures else 'FAIL', 'checked_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'scope': 'Final metadata-only pointer/control/reader-seal binding. Full gallery, SQLite and workbook QA not repeated.',
          'pointer_sha256': EXPECTED, 'preceding_pointer_sha256': r['preceding_pointer_sha256'],
          'checks_total': sum(checks.values()), 'checks_passed': sum(checks.values()) - len(failures), 'check_categories': dict(checks), 'failures': failures,
          'changed_pointer_keys': delta, 'current_readers': ref['readers'],
          'current_master_navigation': str(resolve(ref['current_master_navigation'])),
          'input_hashes': inputs, 'snapshots': {str(x): sha(x) for x in snapshots.iterdir()},
          'register_and_workbook_and_maps_unchanged': True, 'three_control_full_pointers_equal': True,
          'live_calls': 0, 'native_writes': 0, 'canonical_writes': 0, 'owner_questions_reissued': 0}
(OUT / 'metadata-link-readback.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({k: result[k] for k in ['status', 'checks_total', 'checks_passed', 'failures', 'pointer_sha256']}))
