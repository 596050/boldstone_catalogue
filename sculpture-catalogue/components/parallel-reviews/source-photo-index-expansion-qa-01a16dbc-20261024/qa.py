"""Frozen index and one-file navigation QA; writes only this private QA lane."""
import hashlib
import json
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

B = Path('/Users/tprice/Documents/boldstone/sculpture-catalogue')
H = B / 'components/reconciliation/source-component-review-and-flower-links-2026-10-24'
OUT = Path(__file__).resolve().parent
FREEZE_SHA = '2a53952e0065430e57fd0e9854eac9211a784822774ae8588b7e99d2929c8ef5'
FID, PARENT = 'id:cnqzTNngPVsAAAAAAAyh5Q', 'id:cnqzTNngPVsAAAAAAAyh5A'
COUNTS = {'review_packets': 9, 'retained_source_offers': 30, 'existing_options': 27,
          'full_qualified_working_fields': 162, 'new_platform_pairs': 0,
          'new_physical_verifications': 0, 'new_product_records': 0}
REFS = {'O002', 'O003', 'O004', 'O006', 'O007', 'O008', 'O009', 'O010', 'O011', 'O027', 'O047',
        'O053', 'O054', 'O055', 'O056', 'O057', 'O061', 'O062', 'O064', 'O065', 'O069', 'O070',
        'O071', 'O072', 'O074', 'O075', 'O076', 'O077', 'O078', 'O080'}
POINTER_KEYS = {'recorded_utc', 'publication_receipt', 'current_source_photo_review_index',
                'latest_master_metadata_change', 'current_asset_reference_map',
                'current_native_reference_map', 'latest_acanthus_flower_case_navigation'}
CONTROL_KEYS = (POINTER_KEYS - {'recorded_utc', 'publication_receipt'}) | {'updated_utc', 'current_master_catalogue'}
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
read = lambda path: json.loads(Path(path).read_text())
diff = lambda before, after: {k for k in set(before) | set(after) if before.get(k) != after.get(k)}
checks = []


def check(name, passed, detail=None):
    checks.append({'check': name, 'pass': bool(passed), 'detail': detail})


def files_from_seal(path):
    seal = read(path)
    entries = seal['files']
    entries = entries.items() if isinstance(entries, dict) else [(x['path'], x['sha256']) for x in entries]
    return {str(Path(name) if Path(name).is_absolute() else Path(path).parent / name):
            value if isinstance(value, str) else value['sha256'] for name, value in entries}


baseline = read(OUT / 'pre-expansion-baseline.json')
freeze = read(H / 'candidate-freeze.json')
manifest = read(H / 'input-manifest.json')
before = read(manifest['pointer']['snapshot'])
candidate = read(H / 'prepared-pointer.json')
check('Exact handed-off frozen identity', sha(H / 'candidate-freeze.json') == FREEZE_SHA)
check('All fourteen frozen artifacts exact', len(freeze['frozen_artifacts']) == 14 and all(sha(p) == expected for p, expected in freeze['frozen_artifacts'].items()))
check('Source pointer matches independent baseline', manifest['pointer']['sha256'] == baseline['pointer_sha256'] == sha(OUT / 'pointer.before.json'))
for name, entry in manifest.items():
    check('Frozen source snapshot/current bytes: ' + name, sha(entry['path']) == sha(entry['snapshot']) == entry['sha256'])
for name, entry in baseline['data_files'].items():
    check('Original published data preserved: ' + name, sha(entry['path']) == entry['sha256'])
check('Exact seven pointer fields changed', diff(before, candidate) == POINTER_KEYS, sorted(diff(before, candidate)))
check('Prior asset/native descriptor history retained exactly', candidate['current_asset_reference_map']['preceding_reference'] == before['current_asset_reference_map']
      and candidate['current_native_reference_map']['preceding_reference'] == before['current_native_reference_map'])
register = read(manifest['register']['path'])
options = {x['product_id']: x for x in register['options']}
old_assets, old_native = read(manifest['asset_map']['path']), read(manifest['native_map']['path'])
assets = read(B / candidate['current_asset_reference_map']['path'])
native = read(B / candidate['current_native_reference_map']['path'])
check('New asset/native map descriptors exact', sha(B / candidate['current_asset_reference_map']['path']) == candidate['current_asset_reference_map']['sha256']
      and sha(B / candidate['current_native_reference_map']['path']) == candidate['current_native_reference_map']['sha256'])
check('Same6656 asset IDs and4490 native IDs', set(assets) == set(old_assets) and len(assets) == 6656
      and set(native['current_objects']) == set(old_native['current_objects']) and len(native['current_objects']) == 4490)
check('Exactly one changed asset and one changed native file', {k for k in assets if assets[k] != old_assets[k]} == {FID}
      and {k for k in native['current_objects'] if native['current_objects'][k] != old_native['current_objects'][k]} == {FID})
asset_keys = {'path', 'display_path', 'folder_path', 'image_url', 'folder_url', 'latest_scoped_navigation_observation'}
check('Only six declared asset metadata fields change', diff(old_assets[FID], assets[FID]) == asset_keys)
check('Five asset navigation values differ by capitalization only', all(old_assets[FID][k].lower() == assets[FID][k].lower() for k in asset_keys - {'latest_scoped_navigation_observation'}))
check('Native file changes only two path strings', diff(old_native['current_objects'][FID], native['current_objects'][FID]) == {'path', 'display_path'}
      and all(old_native['current_objects'][FID][k].lower() == native['current_objects'][FID][k].lower() for k in ['path', 'display_path']))
check('Same actual parent, filename, size and all integrity/role metadata',
      assets[FID]['folder_id'] == old_assets[FID]['folder_id'] == PARENT
      and native['current_objects'][FID]['parent_id'] == old_native['current_objects'][FID]['parent_id'] == PARENT
      and native['current_objects'][PARENT] == old_native['current_objects'][PARENT] == baseline['before_native_parent'])
check('File path now agrees exactly with existing parent', native['current_objects'][FID]['display_path'].rsplit('/', 1)[0] == native['current_objects'][PARENT]['display_path']
      and assets[FID]['display_path'] == native['current_objects'][FID]['display_path']
      and assets[FID]['path'] == native['current_objects'][FID]['path'])
check('Only native objects/history top-level fields change', diff(old_native, native) == {'current_objects', 'verified_path_change_history'})
history = native['verified_path_change_history']
check('Prior native history intact plus one zero-move observation', history[:-1] == old_native['verified_path_change_history']
      and history[-1]['file_id'] == FID and history[-1]['parent_id'] == PARENT
      and history[-1]['actual_parent_changes'] == history[-1]['native_writes'] == 0)
observation = assets[FID]['latest_scoped_navigation_observation']
check('One-file observation receipt hash and scope', sha(observation['source']) == observation['sha256'] == history[-1]['source_sha256']
      and observation['file_id'] == FID and observation['parent_id'] == PARENT and observation['original_content_hash_reverified'] is False)
raw = read(observation['source'])
file_record = next(x for x in raw['records'] if x['id'] == FID)
parent_record = next(x for x in raw['records'] if x['id'] == PARENT)
check('Observation supports exact file and parent paths', file_record['path_display'] == assets[FID]['display_path']
      and parent_record['path_display'] == native['current_objects'][PARENT]['display_path']
      and file_record['rev'] == observation['rev'] and raw['native_writes'] == 0)
case = read(H / 'flower-case-navigation.json')
case_ref = candidate['latest_acanthus_flower_case_navigation']
check('Case receipt/descriptor bound and explicitly no native change', sha(case_ref['path']) == case_ref['sha256']
      and case['file_id'] == case_ref['file_id'] == FID and case['folder_id'] == case_ref['folder_id'] == PARENT
      and case['actual_file_or_folder_parent_changes'] == case['native_writes'] == case_ref['actual_parent_changes'] == case_ref['native_writes'] == 0
      and case['same_component_and_roles'] is True)
check('Case old/new links exactly match asset-map delta', all(case['previous_reference'][k] == old_assets[FID][k] and case['fresh_reference'][k] == assets[FID][k] for k in ['path', 'image_url', 'folder_url']))
nref = candidate['current_native_reference_map']
check('Latest native scope is one path refresh with zero new objects/moves/byte claims', nref['cumulative_object_count'] == 4490
      and nref['same_id_file_paths_refreshed_in_latest_scope'] == 1
      and all(nref[k] == 0 for k in ['actual_file_parent_changes_in_latest_scope', 'actual_folder_parent_changes_in_latest_scope', 'new_native_objects', 'native_writes_by_master_import', 'fresh_original_content_hash_verifications_in_latest_scope']))

descriptor = candidate['current_source_photo_review_index']
index_path, html_path = B / descriptor['path'], B / descriptor['review']
index = read(index_path)
check('Index JSON/HTML descriptors exact', sha(index_path) == descriptor['sha256'] and sha(html_path) == descriptor['review_sha256'])
check('Exact9/30/27/162 counts without authority upgrades', index['counts'] == descriptor['counts'] == COUNTS)
check('Unchanged register/workbook and explicit new asset descriptor', index['source_register_sha256'] == candidate['register_sha256'] == baseline['register_sha256']
      and index['source_workbook_sha256'] == candidate['workbook_sha256'] == baseline['workbook_sha256']
      and index['current_asset_map'] == candidate['current_asset_reference_map'])
check('Exact thirty source references and exclusion of later B batch', set(index['retained_source_offer_refs']) == REFS and len(index['retained_source_offer_refs']) == 30
      and not ({'O005', 'O052', 'O068', 'O073'} & REFS))
provider_files, refs, option_ids = {}, set(), set()
for packet in index['review_packets']:
    label = Path(packet['seal']).parent.name
    members = files_from_seal(packet['seal'])
    check('Exact provider seal/members: ' + label, sha(packet['seal']) == packet['seal_sha256'] and all(sha(p) == expected for p, expected in members.items()))
    check('Sealed review and passed verification: ' + label, members.get(packet['review_json']) == packet['review_sha256'] == sha(packet['review_json'])
          and members.get(packet['verification']) == packet['verification_sha256'] == sha(packet['verification'])
          and packet['review'] in members and read(packet['verification'])['status'] == 'PASS')
    provider_files.update(members)
    provider_files[packet['seal']] = packet['seal_sha256']
    review = read(packet['review_json'])
    source_records = review.get('source_records', review.get('cases', []))
    component_records = review.get('components', review.get('individual_options', review.get('cases', [])))
    source_refs = {x.get('offer_ref', x.get('ref')) for x in source_records}
    ids = {x.get('product_id', x.get('option_id')) for x in component_records}
    check('Provider source/component scope preserved: ' + label, source_refs == set(packet['offer_refs']) and ids == set(packet['option_ids']))
    refs.update(packet['offer_refs'])
    option_ids.update(packet['option_ids'])
check('Nine provider unions are exactly thirty sources and twenty-seven options', len(index['review_packets']) == 9 and refs == REFS and len(option_ids) == 27)
records = index['existing_option_records']
check('Exactly the existing active27 option IDs', len(records) == 27 and {x['product_id'] for x in records} == option_ids <= set(register['active_option_ids']))
for record in records:
    option = options[record['product_id']]
    asset = assets[record['file_id']]
    check('Complete selected record and six full field objects: ' + record['product_id'], all(record[k] == option[k] for k in ['name', 'canonical_component_id', 'file_id', 'folder_id', 'image_url', 'folder_url', 'master_fields'])
          and len(record['master_fields']) == 6 and all(record[k] == asset[k] for k in ['file_id', 'folder_id', 'image_url', 'folder_url']))
check('All162 complete qualified objects retained', sum(len(x['master_fields']) for x in records) == 162)
check('Twelve continuation cards remain existing scoped options', len(index['continuation_components']) == 12 and all(x['option_id'] in option_ids for x in index['continuation_components']))
directory = index['read_only_directory_review']
check('Four sealed directory link/validation artifacts exact', len(directory['sealed_link_files']) == 4 and all(sha(p) == expected for p, expected in directory['sealed_link_files'].items()))
directory_members = files_from_seal(directory['seal'])
check('Directory linked receipts match original immutable review seal',
      all(path == directory['seal'] or directory_members.get(path) == expected for path, expected in directory['sealed_link_files'].items()))
validation = read(directory['validation'])
check('316 directory observations remain read-only, no move approval', directory['originals'] == validation['originals'] == 316
      and set(directory['families']) == {'Leaf Growth', 'Fountain Palm'}
      and validation['native_writes'] == validation['canonical_writes'] == 0 and validation['observations_are_not_move_approval'] is True)
check('Exactly65 provider artifacts plus4 separately sealed directory links', len(provider_files) == 65 and provider_files == index['provider_files'] and len(directory['sealed_link_files']) == 4)
check('No new physical or platform authority in index interpretation', 'No new platform pairs, products or physical specifications are certified.' in index['interpretation'])
controls = read(H / 'prepared-control-paths.json')
check('Exactly three original control destinations', set(controls) == set(baseline['controls']))
for target, prepared in controls.items():
    entry = next(x for x in manifest.values() if x['path'] == target)
    old, new = read(entry['snapshot']), read(prepared)
    check('Exact seven control metadata fields only: ' + target, diff(old, new) == CONTROL_KEYS)
    check('Full pointer and all scoped descriptors synchronized: ' + target, old['current_master_catalogue'] == before and new['current_master_catalogue'] == candidate
          and all(new[k] == candidate[k] for k in POINTER_KEYS - {'recorded_utc', 'publication_receipt'}) and new['updated_utc'] == candidate['recorded_utc'])


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        self.links.extend(v for k, v in attrs if k == 'href' and v)


parser = Links()
parser.feed(html_path.read_text())


class Anchors(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()

    def handle_starttag(self, tag, attrs):
        self.ids.update(value for key, value in attrs if value and (key == 'id' or tag == 'a' and key == 'name'))


anchor_results = []
for card in index['continuation_components']:
    url = urlsplit(card['review'])
    target = Path(unquote(url.path))
    anchors = Anchors()
    anchors.feed(target.read_text())
    anchor_results.append({'option_id': card['option_id'], 'review': card['review'],
                           'anchor_exists': bool(url.fragment) and unquote(url.fragment) in anchors.ids})
check('All twelve continuation report fragments resolve to real section IDs', len(anchor_results) == 12 and all(x['anchor_exists'] for x in anchor_results), anchor_results)
local = []
for url in parser.links:
    parsed = urlsplit(url)
    if parsed.scheme in ['', 'file'] and parsed.path:
        path = Path(unquote(parsed.path))
        local.append(path if path.is_absolute() else html_path.parent / path)
check('All local index/report links exist', all(x.is_file() for x in local), len(local))
check('Nine provider reviews and directory review linked', {Path(x['review']) for x in index['review_packets']} | {Path(directory['review'])} <= set(local))
check('All27 selected image and folder URLs linked', all(x[k] in parser.links for x in records for k in ['image_url', 'folder_url']))
check('Frozen candidate remains unchanged after QA', sha(H / 'candidate-freeze.json') == FREEZE_SHA and all(sha(p) == expected for p, expected in freeze['frozen_artifacts'].items()))
result = {'status': 'PASS' if all(x['pass'] for x in checks) else 'FAIL', 'recorded_utc': datetime.now(timezone.utc).isoformat(),
          'phase': 'FROZEN_CANDIDATE', 'checks_passed': sum(x['pass'] for x in checks), 'checks_total': len(checks), 'checks': checks,
          'candidate_freeze_sha256': FREEZE_SHA, 'candidate_register_sha256': candidate['register_sha256'],
          'candidate_workbook_sha256': candidate['workbook_sha256'], 'candidate_pointer_sha256': sha(H / 'prepared-pointer.json'),
          'candidate_asset_map_sha256': candidate['current_asset_reference_map']['sha256'],
          'candidate_native_map_sha256': candidate['current_native_reference_map']['sha256'],
          'frozen_artifacts': freeze['frozen_artifacts'], 'counts': COUNTS, 'source_pointer_sha256': baseline['pointer_sha256'],
          'new_source_media_reviews': 0, 'live_calls': 0, 'native_or_platform_or_shared_writes': 0,
          'scope': 'Index/proof link and one-ID path-case QA only. Provider source/photo findings remain at their original scopes and clocks.'}
(OUT / 'candidate-readback.json').write_text(json.dumps(result, indent=2) + '\n')
(OUT / 'sealed-candidate-handoff.json').write_text(json.dumps({'status': result['status'], 'recorded_utc': result['recorded_utc'],
    'files': {n: sha(OUT / n) for n in ['qa.py', 'candidate-readback.json', 'pre-expansion-baseline.json', 'pointer.before.json']}}, indent=2) + '\n')
print(json.dumps({k: result[k] for k in ['status', 'checks_passed', 'checks_total', 'candidate_pointer_sha256', 'counts']}, indent=2))
print('QA receipt:', OUT / 'candidate-readback.json')
print('QA seal SHA256:', sha(OUT / 'sealed-candidate-handoff.json'))
for failed in [x for x in checks if not x['pass']]:
    print('FAIL', failed)
raise SystemExit(0 if result['status'] == 'PASS' else 1)
