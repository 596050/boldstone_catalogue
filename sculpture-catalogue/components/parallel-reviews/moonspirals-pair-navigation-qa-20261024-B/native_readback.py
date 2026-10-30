import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path('/Users/tprice/Documents/boldstone')
SOURCE = ROOT / 'reports/dropbox-moonspirals-three-pair-moves-20261024T143451Z'
OWN = Path(__file__).parent
IDS = {'id:cnqzTNngPVsAAAAAAAucCw', 'id:cnqzTNngPVsAAAAAAAuR4Q', 'id:cnqzTNngPVsAAAAAAAuigw'}
SOURCE_ID = 'id:cnqzTNngPVsAAAAAAAyi8Q'
DEST_ID = 'id:cnqzTNngPVsAAAAAAAyi8w'

def load(name):
    return json.loads((SOURCE / name).read_text())

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

checks = []
def check(name, passed, details=None):
    checks.append({'name': name, 'passed': bool(passed), 'details': details})

seal_path = SOURCE / 'execution-seal.json'
seal_sha = sha(seal_path)
seal = load('execution-seal.json')
overlay = load('current-reference-overlay.json')
before = load('fresh-native-before.json')
after = load('fresh-native-after.json')
maps = {x['file_id']: x for x in overlay['specific_file_maps']}
pre_hash = {x['id']: x for x in load('fresh-prewrite-native-hash-metadata.json')}
post_hash = {x['id']: x for x in load('fresh-postmove-native-hash-metadata.json')}
pre_entries = {x['file_id']: x for x in before['listing']['entries']}
post_entries = {x['file_id']: x for x in after['listing']['entries']}
fresh = {x['id']: x for x in load('three-fresh-postmove-originals.json')}

check('complete_native_seal_all_receipt_bytes_and_hashes',
      seal['status'] == 'COMPLETE_VERIFIED' and
      all(Path(r['path']).stat().st_size == r['size'] and sha(r['path']) == r['sha256'] for r in seal['receipts']))
check('complete_before_and_after_listings_same157_ids',
      not before['listing']['has_more'] and not after['listing']['has_more'] and
      not before['listing']['cursor'] and not after['listing']['cursor'] and
      len(pre_entries) == len(post_entries) == 157 and set(pre_entries) == set(post_entries))
check('exact_three_authorized_file_maps_to_existing_pair_folder',
      set(maps) == IDS and all(m['old_parent_id'] == SOURCE_ID and m['new_parent_id'] == DEST_ID for m in maps.values()) and
      not overlay['prefix_maps'] and not overlay['created_folders'] and not overlay['deleted_files'] and not overlay['deleted_folders'])
check('same148_originals_names_sizes_and_provider_content_hashes',
      len(pre_hash) == len(post_hash) == 148 and set(pre_hash) == set(post_hash) and
      all(all(pre_hash[i][k] == post_hash[i][k] for k in ['id', 'name', 'size', 'content_hash']) for i in pre_hash))
check('family_byte_total_preserved',
      sum(v['size'] for v in pre_hash.values()) == sum(v['size'] for v in post_hash.values()) == 416784106)
check('only_three_file_paths_changed',
      {i for i in pre_hash if pre_hash[i]['path_display'] != post_hash[i]['path_display']} == IDS and
      all(pre_hash[i]['path_display'] == maps[i]['old_path'] and post_hash[i]['path_display'] == maps[i]['new_path'] for i in IDS))
check('all157_object_names_types_and_client_times_preserved',
      all(all(pre_entries[i].get(k) == post_entries[i].get(k) for k in ['file_id', 'name', 'object_type', 'client_modified']) for i in pre_entries))
check('all_nine_folder_ids_paths_and_names_unchanged',
      len([e for e in pre_entries.values() if e['object_type'] == 'folder']) == 9 and
      all(all(e.get(k) == post_entries[i].get(k) for k in ['file_id', 'name', 'path'])
          for i, e in pre_entries.items() if e['object_type'] == 'folder'))
src_path = before['source']['folder']['path_display']
dst_path = before['destination']['folder']['path_display']
def count_parent(records, path):
    return sum(str(Path(r['path_display']).parent) == path for r in records.values())
check('source22_to19_and_destination28_to31',
      (count_parent(pre_hash, src_path), count_parent(post_hash, src_path), count_parent(pre_hash, dst_path), count_parent(post_hash, dst_path)) == (22, 19, 28, 31))
check('three_fresh_original_downloads_exact_ids', set(fresh) == IDS)
readbacks = []
for fid, record in fresh.items():
    p = Path(record['local_path'])
    raw = p.read_bytes()
    whole = hashlib.sha256(raw).hexdigest()
    block_hash = hashlib.sha256(b''.join(hashlib.sha256(raw[i:i + 4 * 1024 * 1024]).digest()
                                       for i in range(0, len(raw), 4 * 1024 * 1024))).hexdigest()
    readbacks.append({'file_id': fid, 'local_path': str(p), 'size': len(raw), 'sha256': whole,
                      'dropbox_content_hash': block_hash, 'matched':
                      len(raw) == record['size'] == maps[fid]['size'] == pre_hash[fid]['size'] and
                      whole == record['sha256'] == maps[fid]['sha256'] and
                      block_hash == record['dropbox_content_hash'] == pre_hash[fid]['content_hash'] == post_hash[fid]['content_hash'] and
                      record['path_display'] == maps[fid]['new_path']})
check('three_originals_rehashed_match_before_after_native_hashes_and_sha256',
      len(readbacks) == 3 and all(x['matched'] for x in readbacks), readbacks)
check('overlay_only_three_path_and_parent_changes',
      {r['file_id'] for r in overlay['objects'] if r['old_path'] != r['current_path']} == IDS and
      {r['file_id'] for r in overlay['objects'] if r['old_parent_id'] != r['current_parent_id']} == IDS)
check('overlay_three_links_target_current_parent_and_unchanged_names',
      all(r['current_name'] == r['old_name'] and r['current_parent_id'] == DEST_ID and
          r['current_path'] == maps[r['file_id']]['new_path'] and
          'Moonspiral%201%20and%20Moonspiral%202%20White%20In%20Situ' in r['current_native_url']
          for r in overlay['objects'] if r['file_id'] in IDS))
check('seal_bytes_stable_through_independent_readback', sha(seal_path) == seal_sha)
result = {'status': 'PASS' if all(c['passed'] for c in checks) else 'FAIL',
          'recorded_utc': datetime.now(timezone.utc).isoformat(),
          'checks_passed': sum(c['passed'] for c in checks), 'checks_total': len(checks), 'checks': checks,
          'native_seal': {'path': str(seal_path), 'sha256': seal_sha},
          'scope': 'Independent sealed receipt integrity and148 before/after metadata comparisons, with fresh local-byte rehash of exactly three moved originals. The unchanged145 original binaries were not rehashed by this reviewer. No new native calls or shared writes.'}
output = OWN / 'native-readback.json'
assert not output.exists(), 'Preserve previous results before rerunning'
output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'status': result['status'], 'checks_passed': result['checks_passed'], 'checks_total': result['checks_total'],
                  'failed': [c for c in checks if not c['passed']], 'path': str(output), 'sha256': sha(output)}))
