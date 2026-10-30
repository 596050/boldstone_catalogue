"""Independent local QA for the frozen Echo navigation-only publication."""
import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from zipfile import ZipFile

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[2]
H = BASE / 'components/reconciliation/echo-sound-approved-navigation-metadata-2026-10-24'
SOURCE = BASE.parent / 'reports/dropbox-echo-sound-23-approved-moves-20261024T191800Z'
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
parser = argparse.ArgumentParser()
parser.add_argument('--published', action='store_true')
args = parser.parse_args()
checks = []
def check(name, condition):
    assert condition, name
    checks.append(name)

freeze_path = H / 'candidate-freeze.json'
freeze_sha = sha(freeze_path)
freeze = read(freeze_path)
check('Frozen candidate status', freeze['status'] == 'FROZEN_ECHO_METADATA_ONLY_CANDIDATE')
check('Every frozen candidate file matches', all(sha(p) == s for p, s in freeze['frozen_artifacts'].items()))
inputs = read(H / 'input-manifest.json')
check('Every preserved input snapshot matches', all(sha(x['snapshot']) == x['sha256'] for x in inputs.values()))
mutable_controls = {'pointer', 'review_progress', 'component_checkpoint', 'root_checkpoint'}
check('All unchanged live inputs match their snapshots', all(sha(x['path']) == x['sha256'] for k, x in inputs.items() if not args.published or k not in mutable_controls))
before = read(inputs['pointer']['snapshot'])
p = read(H / 'prepared-pointer.json')
for kind in ['register', 'workbook', 'audit']:
    check(kind + ' byte identity retained', sha(inputs[kind]['path']) == freeze['candidate_' + kind + '_sha256'] == inputs[kind]['sha256'])
check('Register and workbook paths retained', all(p[k] == before[k] for k in ['register', 'register_sha256', 'workbook', 'workbook_sha256']))
check('Audit metadata retained', p['latest_image_coverage_audit'] == before['latest_image_coverage_audit'])
native_seal = read(SOURCE / 'execution-seal.json')
check('Native execution sealed', native_seal['status'] == 'NATIVE_EXECUTION_COMPLETE_VERIFIED')
check('Every sealed native receipt matches', all(sha(SOURCE / f['path']) == f['sha256'] for f in native_seal['files']))
overlay = read(SOURCE / 'current-reference-overlay.json')
validation = read(SOURCE / 'validation.json')
gallery = read(SOURCE / 'all-current-echo-sound-image-folder-links.json')
by_id = {r['file_id']: r for r in gallery}
moves = {r['file_id']: r for r in overlay['specific_file_maps']}
check('23 distinct approved moves and 180 distinct originals', len(moves) == 23 and len(gallery) == len(by_id) == 180)
check('Sealed original-byte scope retained', validation['all_180_original_ID_name_format_size_client_time_and_bytes_preserved'] and validation['only_23_approved_file_paths_and_parent_IDs_changed'])
check('Selected four options remain untouched', validation['selected_four_options_primary_context_ID_path_parent_role_unchanged'])
check('Dark finish and other families remain untouched', validation['dark_finish_001_101_102_remain_unmoved'] and validation['Chiswick_015_and_Bone_no_mutations_by_this_lane'])
check('Folder census and byte total agree', len(overlay['current_folders']) == 9 and sum(r['size'] for r in gallery) == 1092139502 and Counter(r['folder_id'] for r in gallery) == Counter({r['folder_id']: r['files'] for r in overlay['current_folders']}))
for fid, move in moves.items():
    row = by_id[fid]
    assert row['name'] == Path(move['old_path']).name == Path(move['new_path']).name
    assert row['folder_path'] == str(Path(move['new_path']).parent)
    assert row['folder_id'] == move['new_parent_id']
    assert all(row[k] == move[k] for k in ['sha256', 'dropbox_content_hash', 'size'])
check('All 23 identities, parents and sealed byte attributes agree', True)
new_assets = read(H / 'current-assets.json')
old_assets = read(inputs['assets']['snapshot'])
check('Asset ID population retained', new_assets.keys() == old_assets.keys())
changed_assets = {fid for fid in new_assets if new_assets[fid] != old_assets[fid]}
check('Only the 23 approved asset records change', changed_assets == set(moves))
allowed = {'folder_id', 'path', 'display_path', 'folder_path', 'image_url', 'folder_url', 'full', 'current_original_evidence'}
for fid, move in moves.items():
    a, old, row = new_assets[fid], old_assets[fid], by_id[fid]
    assert a['file_id'] == fid and a['name'] == old['name'] == row['name']
    assert a['folder_id'] == row['folder_id'] and a['display_path'] == move['new_path']
    assert all(a[k] == row[k] for k in ['image_url', 'folder_url'])
    assert all(a.get(k) == v for k, v in old.items() if k not in allowed)
    assert set(a) - set(old) <= allowed
    assert a['current_original_evidence']['sha256'] == row['sha256']
    assert a['current_original_evidence']['dropbox_content_hash'] == row['dropbox_content_hash']
check('23 current asset links and retained non-navigation fields agree', True)
native = read(H / 'current-native-reference-map.json')
old_native = read(inputs['native_map']['snapshot'])
check('All 4300 previous native objects retained exactly', len(old_native['current_objects']) == 4300 and all(native['current_objects'].get(k) == v for k, v in old_native['current_objects'].items()))
new_ids = set(native['current_objects']) - set(old_native['current_objects'])
expected_native = {o['file_id']: o for o in overlay['objects']}
for scope_root in overlay['preserved_scope_roots']:
    expected_native[scope_root['id']] = {'current_path': scope_root['path_display']}
check('Exactly 190 existing native objects represented', new_ids == set(expected_native) and len(new_ids) == 190)
for fid, expected in expected_native.items():
    n = native['current_objects'][fid]
    assert n['file_id'] == fid and n['display_path'] == expected['current_path']
    if 'current_parent_id' in expected:
        assert n['parent_id'] == expected['current_parent_id']
check('All added native object IDs, paths and parents agree', True)
check('Explicit native and asset map pointers match', p['current_native_reference_map']['sha256'] == sha(BASE / p['current_native_reference_map']['path']) == sha(H / 'current-native-reference-map.json') and p['current_asset_reference_map']['sha256'] == sha(BASE / p['current_asset_reference_map']['path']) == sha(H / 'current-assets.json'))
reg = read(inputs['register']['snapshot'])
tokens = [s.encode() for move in moves.values() for s in [move['file_id'], Path(move['new_path']).name]]
check('No moved file IDs or filenames in the unchanged register', not any(t in Path(inputs['register']['snapshot']).read_bytes() for t in tokens))
with ZipFile(inputs['workbook']['snapshot']) as book:
    hits = [name for name in book.namelist() if name.endswith(('.xml', '.rels')) and any(t in book.read(name) for t in tokens)]
check('No moved file IDs or filenames in the unchanged workbook', not hits)
pointer_allowed = {'recorded_utc', 'status', 'publication_receipt', 'current_image_review_links', 'next_catalogue_actions', 'current_native_reference_map', 'latest_master_metadata_change', 'current_asset_reference_map', 'latest_echo_sound_approved_native_navigation', 'latest_read_only_source_photo_review', 'latest_scoped_water_feature_coverage'}
check('All unrelated pointer fields retained', all(p.get(k) == v for k, v in before.items() if k not in pointer_allowed) and set(p) - set(before) <= pointer_allowed)
updates = read(H / 'prepared-control-paths.json')
for key, path in updates.items():
    control = read(path)
    old = read(inputs[key]['snapshot'])
    assert control['current_master_catalogue'] == p
    for k, v in old.items():
        if k not in pointer_allowed | {'updated_utc', 'current_master_catalogue'}:
            assert control.get(k) == v, (key, k)
    for k in pointer_allowed - {'recorded_utc', 'status', 'publication_receipt'}:
        if k in control:
            assert control[k] == p[k], (key, k)
check('All three prepared controls synchronized with unrelated state retained', len(updates) == 3)
summary = read(H / 'import-summary.json')
check('Importer and native scopes separately recorded', summary['local_originals_rehashed_by_importer'] == 23 and summary['new_original_binary_downloads_by_importer'] == summary['native_or_platform_writes_by_importer'] == 0 and validation['fresh_postmove_original_downloads'] == 23)
check('No new specification, physical or platform claims', all(summary[k] == 0 for k in ['new_specifications', 'new_physical_verifications', 'new_platform_pairs']) and summary['active_options'] == 188 and summary['retained_component_ids'] == 112 and summary['working_design_groups'] == 110)
class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
    def handle_starttag(self, tag, attributes):
        if tag == 'a':
            self.links.append(dict(attributes).get('href', ''))
for name, expected_ids in [('moved-23-current-image-folder-links.html', set(moves)), ('all-current-echo-sound-image-folder-links.html', set(by_id))]:
    parser = Links()
    parser.feed((SOURCE / name).read_text())
    assert all(by_id[fid]['image_url'] in parser.links and by_id[fid]['folder_url'] in parser.links for fid in expected_ids)
check('Both galleries contain every expected current image and folder link', True)
latest = p['latest_echo_sound_approved_native_navigation']
check('Echo pointer evidence and scope match', latest['overlay_sha256'] == sha(SOURCE / 'current-reference-overlay.json') and latest['execution_seal_sha256'] == sha(SOURCE / 'execution-seal.json') and (latest['White'], latest['InSitu'], latest['family_originals']) == (93, 25, 180))
if args.published:
    check('Published pointer matches frozen candidate bytes', sha(BASE / 'current-master.json') == sha(H / 'prepared-pointer.json'))
    check('Three published controls match prepared bytes', all(sha(inputs[k]['path']) == sha(path) for k, path in updates.items()))
    receipt = read(H / 'publication-receipt.json')
    check('Metadata publication receipt verified', receipt['status'] == 'PASS_PUBLISHED_AND_READ_BACK' and receipt['candidate_freeze_sha256'] == freeze_sha)
check('Candidate freeze and all artifacts still match after QA', sha(freeze_path) == freeze_sha and all(sha(path) == s for path, s in freeze['frozen_artifacts'].items()))
record = {'status': 'PASS', 'recorded_utc': datetime.now(timezone.utc).isoformat(), 'phase': 'PUBLISHED_READBACK' if args.published else 'FROZEN_CANDIDATE_QA',
    'checks_passed': len(checks), 'checks_total': len(checks), 'checks': checks,
    'candidate_freeze_sha256': freeze_sha, 'frozen_artifacts': freeze['frozen_artifacts'],
    'candidate_register_sha256': freeze['candidate_register_sha256'], 'candidate_workbook_sha256': freeze['candidate_workbook_sha256'],
    'candidate_audit_sha256': freeze['candidate_audit_sha256'], 'candidate_pointer_sha256': sha(H / 'prepared-pointer.json'),
    'candidate_native_map_sha256': sha(H / 'current-native-reference-map.json'), 'candidate_asset_map_sha256': sha(H / 'current-assets.json'),
    'native_execution_seal_sha256': sha(SOURCE / 'execution-seal.json'), 'unchanged_native_objects': 4300,
    'existing_native_objects_added': 190, 'asset_records_changed': 23, 'gallery_files': 180, 'gallery_folders': 9,
    'original_bytes': 1092139502, 'new_live_calls': 0, 'original_binary_reads_or_rehashes_by_this_QA': 0, 'shared_writes': 0}
name = 'published-readback.json' if args.published else 'candidate-readback.json'
output = HERE / name
assert not output.exists(), 'Retain previous proof; use a new version for a revised candidate'
output.write_text(json.dumps(record, indent=2) + '\n')
if not args.published:
    seal = {'status': 'SEALED_INDEPENDENT_ECHO_METADATA_QA', 'files': [{'path': str(p), 'sha256': sha(p)} for p in [Path(__file__), output]]}
    (HERE / 'sealed-handoff.json').write_text(json.dumps(seal, indent=2) + '\n')
print(json.dumps({'status': record['status'], 'phase': record['phase'], 'checks_passed': len(checks), 'checks_total': len(checks),
    'output': str(output), 'sha256': sha(output), 'seal_sha256': sha(HERE / 'sealed-handoff.json') if not args.published else None}, indent=2))
