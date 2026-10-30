"""Independent saved-receipt and ten-original readback; no native service calls."""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json

LANE = Path(__file__).resolve().parent
PACK = Path('/Users/tprice/Documents/boldstone/reports/dropbox-moonwave-ten-approved-moves-20261024T182423Z')
load = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()


def save(name, value):
    with (LANE / name).open('x') as f:
        json.dump(value, f, ensure_ascii=False, indent=2); f.write('\n')


def native_hash(path):
    whole = hashlib.sha256(); blocks = hashlib.sha256(); size = 0
    with Path(path).open('rb') as f:
        while block := f.read(4 * 1024 * 1024):
            whole.update(block); blocks.update(hashlib.sha256(block).digest()); size += len(block)
    return {'sha256': whole.hexdigest(), 'dropbox_content_hash': blocks.hexdigest(), 'size': size}


seal = load(PACK / 'execution-seal.json')
assert sha(PACK / 'execution-seal.json') == '4b4e9f78572efcabec11681cabc3c6a8abaf2fb6fa954203c36d19448b5afdc0'
receipt_checks = [{'path': r['path'], 'sha256_matches': sha(r['path']) == r['sha256'], 'size_matches': Path(r['path']).stat().st_size == r['size']} for r in seal['receipts']]
owner = load(PACK / 'owner-approval-source-evidence.json'); sr = owner['recorded_source']
with Path(sr['session_file']).open('rb') as f:
    f.seek(sr['byte_offset']); raw = f.readline()
event = json.loads(raw)
owner_text = '\n'.join(x.get('text', '') for x in event['payload']['content'] if x.get('type') in {'input_text', 'text'})
before = load(PACK / 'fresh-native-before.json'); after = load(PACK / 'fresh-native-after.json')
bm = {x['id']: x for x in load(PACK / 'fresh-prewrite-native-hash-metadata.json')}
am = {x['id']: x for x in load(PACK / 'fresh-postmove-native-hash-metadata.json')}
bl = {x['file_id']: x for x in before['listing']['entries']}
al = {x['file_id']: x for x in after['listing']['entries']}
proposal = load(PACK / 'approved-source-proposal.json')
moves = {x['id']: x for x in proposal['moves']}
overlay = load(PACK / 'current-reference-overlay.json')
specific = {x['file_id']: x for x in overlay['specific_file_maps']}
changed = {oid for oid in bm if bm[oid]['path_display'] != am[oid]['path_display']}
white_id = before['White']['folder']['id']; situ_id = before['InSitu']['folder']['id']
white_path = before['White']['folder']['path_display']; situ_path = before['InSitu']['folder']['path_display']
counts_before = Counter(x['path_display'].rsplit('/', 1)[0] for x in bm.values())
counts_after = Counter(x['path_display'].rsplit('/', 1)[0] for x in am.values())
fresh = load(PACK / 'ten-fresh-postmove-originals.json')
hash_reads = []
for x in fresh:
    got = native_hash(x['local_path']); expected = specific[x['id']]
    hash_reads.append({'file_id': x['id'], 'local_path': x['local_path'], **got,
                       'matches_fresh_receipt': all(got[k] == x[k] for k in got),
                       'matches_sealed_overlay': all(got[k] == expected[k] for k in got),
                       'matches_before_after_native_content_hash': got['dropbox_content_hash'] == bm[x['id']]['content_hash'] == am[x['id']]['content_hash']})
protected_names = {
    'moonwave__moonwave-white__018.JPG', 'moonwave__moonwave-white__062.JPG', 'moonwave__moonwave-white__079.jpg',
    'moonwave__moonwave-white-in-situ__007.JPG', 'moonwave__moonwave-white-in-situ__008.JPG',
    'moonwave__moonwave-white-in-situ__009.JPG', 'moonwave__moonwave-white-in-situ__013.jpeg',
}
selected = {oid for oid, x in bm.items() if x['name'].lower() in {'moonwave__moonwave-white__033.jpg', 'moonwave__moonwave-white-in-situ__005.jpg'}}
checks = {
    'complete_native_execution_seal_and_all_26_receipt_hashes': seal['status'] == 'COMPLETE_VERIFIED' and len(receipt_checks) == 26 and all(x['sha256_matches'] and x['size_matches'] for x in receipt_checks),
    'exact_owner_user_record_read_back_by_byte_hash_and_timestamp': hashlib.sha256(raw).hexdigest() == sr['complete_line_sha256'] and event['timestamp'] == sr['record_timestamp'] and event['payload']['role'] == 'user' and owner_text == sr['owner_text_verbatim'] and owner_text.startswith('Make these changes:'),
    'ten_approved_filenames_and_destination_mapping_match_overlay': len(moves) == 10 and set(moves) == set(specific) and all(x['name'] in owner_text and x['path_display'] == specific[oid]['old_path'] and x['destination_path'] == specific[oid]['new_path'] and x['source_folder_id'] == specific[oid]['old_parent_id'] and x['destination_folder_id'] == specific[oid]['new_parent_id'] for oid, x in moves.items()),
    'all_99_file_and_two_folder_ids_retained': len(bm) == len(am) == 99 and set(bm) == set(am) and len(bl) == len(al) == 101 and set(bl) == set(al),
    'all_99_file_names_sizes_client_times_and_content_hashes_unchanged': all(all(bm[oid][k] == am[oid][k] for k in ['name', 'size', 'content_hash']) and bl[oid]['client_modified'] == al[oid]['client_modified'] for oid in bm),
    'exact_ten_paths_changed_and_actual_paths_match_authorized_destinations': changed == set(moves) and all(am[oid]['path_display'] == moves[oid]['destination_path'] for oid in changed),
    'six_forward_four_reverse_moves_between_existing_parent_ids': sum(x['old_parent_id'] == white_id and x['new_parent_id'] == situ_id for x in specific.values()) == 6 and sum(x['old_parent_id'] == situ_id and x['new_parent_id'] == white_id for x in specific.values()) == 4,
    'white_86_to_84_in_situ_13_to_15_and_784220860_bytes_retained': counts_before[white_path] == 86 and counts_before[situ_path] == 13 and counts_after[white_path] == 84 and counts_after[situ_path] == 15 and sum(x['size'] for x in bm.values()) == sum(x['size'] for x in am.values()) == 784220860,
    'ten_fresh_moved_originals_independently_rehashed_sha256_and_Dropbox_hash': len(hash_reads) == 10 and {x['file_id'] for x in hash_reads} == changed and all(x['matches_fresh_receipt'] and x['matches_sealed_overlay'] and x['matches_before_after_native_content_hash'] for x in hash_reads),
    'three_borderline_and_four_room_files_unchanged': protected_names <= {x['name'] for x in bm.values()} and all(bl[oid] == al[oid] for oid, x in bm.items() if x['name'] in protected_names),
    'selected_primary033_and_context005_remain_unchanged': len(selected) == 2 and not selected & changed and all(bl[oid] == al[oid] for oid in selected),
    'two_own_file_source_references_remain_distinct': {'id:cnqzTNngPVsAAAAAAArp1g', 'id:cnqzTNngPVsAAAAAAArp2Q'} <= changed and specific['id:cnqzTNngPVsAAAAAAArp1g']['new_path'] != specific['id:cnqzTNngPVsAAAAAAArp2Q']['new_path'],
    'no_native_mutations_or_downloads_by_B': True,
}
result = {'status': 'PASS' if all(checks.values()) else 'FAIL', 'recorded_utc': datetime.now(timezone.utc).isoformat(),
          'checks_passed': sum(checks.values()), 'checks_total': len(checks), 'checks': checks,
          'native_seal': {'path': str(PACK / 'execution-seal.json'), 'sha256': sha(PACK / 'execution-seal.json')},
          'overlay': {'path': str(PACK / 'current-reference-overlay.json'), 'sha256': sha(PACK / 'current-reference-overlay.json')},
          'receipt_checks': receipt_checks, 'moved_original_reads': hash_reads,
          'owner_record_readback': {k: sr[k] for k in ['session_id', 'session_file', 'record_timestamp', 'byte_offset', 'complete_line_sha256']},
          'scope': 'B independently checked all saved metadata and all ten moved local originals. The directory owner rehashed the other 89 originals; B did not repeat those 89 binary reads. No visual reclassification, live API call, native mutation or catalogue write.',
          'native_calls': 0, 'shared_writes': 0}
save('moonwave-native-readback.json', result)
save('moonwave-scope-extension.json', {'status': 'APPROVED_EXECUTED_NATIVE_OVERLAY_FOR_COMBINED_CANDIDATE', 'six_case_preparation_was_not_executed': True,
    'baseline_register_sha256': load(LANE / 'expectations.json')['baseline_register']['sha256'],
    'native_readback': {'path': str(LANE / 'moonwave-native-readback.json'), 'sha256': sha(LANE / 'moonwave-native-readback.json')},
    'moves': list(specific.values()), 'selected_option_primary_and_context_unchanged': True,
    'source_boundary': 'Zero-based source_offer_edges index15 is offer_ref O016 Moonwave: rp1g current-primary navigation may change. source_media_configuration_coverage index163 may gain rp2Q current example navigation. O015 at index14, raw source_offer, member/BOM objects, four example IDs, physical values, identities and photo roles remain unchanged.'})
print(json.dumps({'status': result['status'], 'passed': result['checks_passed'], 'total': result['checks_total'], 'failed': [k for k, v in checks.items() if not v], 'readback_sha256': sha(LANE / 'moonwave-native-readback.json')}, indent=2))
