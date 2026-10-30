"""Independent local Wave navigation/import readback, without native requests."""
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
D = ROOT / 'components/reconciliation/wave-moonshadow-mixed-scene-master-2026-10-24'
NATIVE = ROOT.parent / 'reports/dropbox-wave-moonshadow-mixed-scene-moves-20261024T014335Z'
OUT = ROOT / 'outputs/wave-moonshadow-mixed-scene-master-2026-10-24'
REG_SHA = '06acd3dc3abb1146d79845dc5c895ee164f0c87ab97800fbe4d0e04e5be88f96'
AUDIT_SHA = '5614cae122df4342f5ec0bf1ac4abeb074b976287498659e3e64d84303a97a10'
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
checks = []


def check(label, value, detail=None):
    checks.append({'name': label, 'passed': bool(value), 'detail': detail})


check('Exact observed candidate register revision pinned', sha(D / 'canonical-master-register.json') == REG_SHA)
check('Exact existing Leaf photo-audit bytes preserved', sha(D / 'image-coverage-current.json') == AUDIT_SHA)
inputs = read(D / 'input-manifest.json')
check('All retained input snapshots match recorded exact hashes', all(sha(Path(x['snapshot'])) == x['sha256'] for x in inputs.values()))
old, new = read(D / 'inputs/master_register.before'), read(D / 'canonical-master-register.json')
check('Base is exact published Leaf2205546a', sha(D / 'inputs/master_register.before') == '2205546ab8502b4723d1eb9597c6da4104f8df18e7addcfd1ad9d9a4df328c16')
check('All189 complete option records unchanged', old['options'] == new['options'] and len(new['options']) == 189)
check('Active188 and retired option identities unchanged', old['active_option_ids'] == new['active_option_ids'] and len(new['active_option_ids']) == 188 and old['retired_option_ids'] == new['retired_option_ids'])
check('All81 source offers and28 source sets unchanged including raw assertions/BOMs', old['source_offer_edges'] == new['source_offer_edges'] and old['source_sets'] == new['source_sets'] and len(new['source_offer_edges']) == 81 and len(new['source_sets']) == 28)
check('All listing source links, evidence, resolutions, action drafts and copy projections unchanged', all(old[k] == new[k] for k in ['current_listing_source_links', 'current_listing_match_evidence', 'current_listing_issues', 'current_listing_resolution', 'current_listing_resolution_details', 'listing_resolution_native_action_drafts', 'current_existing_listing_copy_projections']))
check('All Leaf owner correction semantics and provenance unchanged', old['current_owner_depiction_corrections'] == new['current_owner_depiction_corrections'] and old['latest_leaf_form_owner_depiction_import'] == new['latest_leaf_form_owner_depiction_import'])
changed_existing = {k for k in old if old[k] != new.get(k)}
check('Only existing audit-reference metadata fields changed in register', changed_existing == {'latest_image_coverage_audit', 'latest_active_photo_source_review'}, sorted(changed_existing))
check('Exactly three new dated navigation/source observation top-level fields', set(new) - set(old) == {'latest_wave_moonshadow_native_navigation_import', 'current_authenticated_squarespace_inventory_observation', 'latest_authenticated_source_observation_import'})

seal = read(NATIVE / 'execution-seal.json')
overlay = read(NATIVE / 'current-reference-overlay.json')
links = read(NATIVE / 'all-current-wave-moonshadow-image-folder-links.json')
check('Exact completed native seal and current overlay bytes pinned', sha(NATIVE / 'execution-seal.json') == 'f068c9042ab6f00250fb7ca8623698a7d6f6a3e49a2bd04ebf1b28ba01035189' and sha(NATIVE / 'current-reference-overlay.json') == '0d52d0e2d2d24bde2efc2f6db4032fd96a43c6e4a846170053a5c2e74d5bf196')
check('All22 sealed native receipt files still exact', len(seal['receipts']) == 22 and all(sha(Path(x['path'])) == x['sha256'] for x in seal['receipts']))
check('Native source inventory is59 unique image IDs and seven folders', len(links) == len({x['file_id'] for x in links}) == 59 and len(overlay['current_folders']) == 7)
check('Native source image bytes total144923086 with recorded original hashes', sum(x['size'] for x in links) == 144923086 and all(x['sha256'] and x['dropbox_content_hash'] for x in links))
maps = overlay['specific_file_maps']
folder = overlay['created_folders'][0]
file_ids = {'id:cnqzTNngPVsAAAAAAArqLg', 'id:cnqzTNngPVsAAAAAAAuXZA'}
folder_id = 'id:cnqzTNngPVsAAAAAAA6Vsg'
check('Exactly two approved files moved into exact new6Vsg folder', len(maps) == 2 and {x['file_id'] for x in maps} == file_ids and len(overlay['created_folders']) == 1 and folder['file_id'] == folder_id and all(x['current_parent_id'] == folder_id for x in maps))
check('Native move evidence preserves filenames/client times/bytes with no deletes', all(x['old_name'] == x['current_name'] and x['old_client_modified'] == x['current_client_modified'] and x['pre_move_sha256_identical'] is True for x in maps) and not overlay['deleted_files'] and not overlay['deleted_folders'])
parent_counts = Counter(x['folder_id'] for x in links)
check('New folder has2 images and source ThreePanelScene folder has5', parent_counts[folder_id] == 2 and parent_counts['id:cnqzTNngPVsAAAAAAAyjHQ'] == 5)

old_map, new_map = read(D / 'inputs/native_map.before'), read(D / 'current-native-reference-map.json')
objects = {x['file_id']: x for x in overlay['objects']}
check('Native map adds only new folder and removes no known object', set(new_map['current_objects']) - set(old_map['current_objects']) == {folder_id} and not (set(old_map['current_objects']) - set(new_map['current_objects'])))
errors = []
for fid, x in objects.items():
    m = new_map['current_objects'].get(fid, {})
    expected = {'path': x['current_ns_path'], 'display_path': x['current_path'], 'name': x['current_name'], 'parent_id': x['current_parent_id'], 'size': x['size']}
    if any(m.get(k) != v for k, v in expected.items()):
        errors.append(fid)
check('All66 current native-map objects exactly agree with completed overlay', len(objects) == 66 and not errors, errors)
check('All native-map objects outside approved family unchanged', all(v == new_map['current_objects'][fid] for fid, v in old_map['current_objects'].items() if fid not in objects))
check('Historical native path aliases preserved with only three approved additions', all(new_map['old_path_to_id'].get(k) == v for k, v in old_map['old_path_to_id'].items()) and len(set(new_map['old_path_to_id']) - set(old_map['old_path_to_id'])) == 3 and all(new_map['old_path_to_id'][k] in file_ids | {folder_id} for k in set(new_map['old_path_to_id']) - set(old_map['old_path_to_id'])))

old_assets, assets = read(D / 'inputs/report_assets.before'), read(D / 'current-assets.json')
check('Asset index retains all6656 IDs without creation/deletion', set(old_assets) == set(assets) and len(assets) == 6656)
changes = {fid for fid in assets if assets[fid] != old_assets[fid]}
repairs = read(D / 'auxiliary-current-asset-navigation-repairs.json')
repair_ids = {x['file_id'] for x in repairs}
check('Only two moved IDs plus39 auxiliary Wave image IDs changed', changes == file_ids | repair_ids and len(changes) == 41 and len(repair_ids) == 39 and repair_ids <= set(objects) and not (repair_ids & file_ids))
check('All78 auxiliary repairs are exact display_path/folder_path fields', len(repairs) == 78 and Counter(x['field'] for x in repairs) == {'display_path': 39, 'folder_path': 39} and all(x['before'] == old_assets[x['file_id']][x['field']] and x['current'] == assets[x['file_id']][x['field']] for x in repairs))
check('Unmoved auxiliary asset entries change no other property', all({k: v for k, v in assets[fid].items() if k not in ['display_path', 'folder_path']} == {k: v for k, v in old_assets[fid].items() if k not in ['display_path', 'folder_path']} for fid in repair_ids))


def file_path(url):
    u = urlsplit(url)
    path = unquote(u.path)
    if path.startswith('/preview/'):
        return path[len('/preview'):]
    if path.startswith('/home/'):
        path = path[len('/home'):]
        preview = parse_qs(u.query).get('preview')
        return path + '/' + preview[0] if preview else path
    return None


asset_errors = []
for source in links:
    a = assets[source['file_id']]
    obj = objects[source['file_id']]
    if not (a['name'] == source['name'] and a['bytes'] == source['size'] and
            a['source_content_hash'] == source['dropbox_content_hash'] and
            a['folder_id'] == source['folder_id'] and a['display_path'] == obj['current_path'] and
            a['path'] == obj['current_ns_path'] and
            a['folder_path'] == 'ns:202238505/' + source['folder_path'] and
            file_path(a['image_url']) == obj['current_path'] and file_path(a['folder_url']) == source['folder_path']):
        asset_errors.append(source['file_id'])
check('All59 saved asset names/bytes/hashes/parents/paths/URLs match completed source inventory', not asset_errors, asset_errors)
check('Moved assets preserve client/cache/hash facts and add only navigation history', all(assets[x['file_id']]['client_modified'] == old_assets[x['file_id']]['client_modified'] and assets[x['file_id']]['modified_time'] == x['current_server_modified'] and all(assets[x['file_id']][k] == old_assets[x['file_id']][k] for k in ['file_id', 'name', 'bytes', 'source_content_hash', 'full', 'thumb', 'source_bytes', 'current_original_content_rehashed']) and len(assets[x['file_id']]['historical_same_id_navigation']) >= 1 for x in maps))
check('Selected current reference refresh list remains empty', read(D / 'current-reference-fields-refreshed.json') == [])
check('Photo requests, existing role audit, physical ledger and owner review state unchanged', all(read(D / dest) == read(Path(inputs[key]['snapshot'])) for dest, key in [('photo-review-queue.json', 'report_reviews'), ('guided-owner-review-state.json', 'review_state')]) and sha(D / 'image-coverage-current.json') == inputs['audit']['sha256'] and read(D / 'physical-source-audit.json') == read(ROOT / 'components/reconciliation/leaf-form-owner-display-correction-master-2026-10-24/physical-source-audit.json'))


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []
    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.urls.extend(v for k, v in attrs if k == 'href')


page = OUT / 'all-current-wave-moonshadow-images.html'
parser = Links()
parser.feed(page.read_text())
linked_paths = {file_path(url) for url in parser.urls}
check('Current report links every59 exact image and seven actual containing folders', all(objects[x['file_id']]['current_path'] in linked_paths and x['folder_path'] in linked_paths for x in links))
check('Candidate retains Leaf1design/2depictions semantics and physical uncertainty', new['current_owner_depiction_corrections'][0]['current_interpretation'] == old['current_owner_depiction_corrections'][0]['current_interpretation'])
check('New source observations are additive with zero new physical/identity matches', new['latest_authenticated_source_observation_import']['source_product_sku_tuples'] == 80 and new['latest_authenticated_source_observation_import']['historical_shopify_pairs'] == 37 and new['latest_authenticated_source_observation_import']['new_identity_or_physical_configuration_matches'] == 0 and new['latest_authenticated_source_observation_import']['existing_working_values_changed'] == 0)
check('Candidate and native frozen source bytes stayed exact through readback', sha(D / 'canonical-master-register.json') == REG_SHA and sha(D / 'image-coverage-current.json') == AUDIT_SHA and sha(NATIVE / 'execution-seal.json') == 'f068c9042ab6f00250fb7ca8623698a7d6f6a3e49a2bd04ebf1b28ba01035189')
result = {'recorded_utc': datetime.now(timezone.utc).isoformat(), 'status': 'PASS' if all(x['passed'] for x in checks) else 'FAIL',
          'checks_passed': sum(x['passed'] for x in checks), 'checks_total': len(checks), 'checks': checks,
          'candidate_register_sha256': sha(D / 'canonical-master-register.json'), 'candidate_audit_sha256': sha(D / 'image-coverage-current.json'),
          'native_source_seal_sha256': sha(NATIVE / 'execution-seal.json'),
          'scope': 'Independent saved data/navigation and HTML-link readback only. Native original-byte verification is the separate sealed directory-lane evidence; A made no live reads and did not open a pending workbook. Detailed80+37 attachment semantics belong to B.',
          'native_and_shared_writes_by_A': 0}
with (HERE / 'candidate-data-readback-001.json').open('x', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
    f.write('\n')
print(json.dumps({'status': result['status'], 'passed': result['checks_passed'], 'total': len(checks), 'failed': [x for x in checks if not x['passed']]}))
raise SystemExit(0 if result['status'] == 'PASS' else 1)
