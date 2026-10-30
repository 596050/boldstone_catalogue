"""Publish a reviewed evidence index through the pointer and three controls only."""
import argparse
import hashlib
import json
import os
from urllib.parse import parse_qs, unquote, urlparse

def dropbox_path(url):
    u = urlparse(url)
    path = unquote(u.path)
    for prefix in ["/preview", "/home"]:
        if path.startswith(prefix + "/"):
            path = path[len(prefix):]
            break
    preview = parse_qs(u.query).get("preview")
    return path.rstrip("/") + ("/" + preview[0] if preview else "")
from datetime import datetime, timezone
from pathlib import Path

H = Path(__file__).resolve().parent
B = H.parents[2]
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
parser = argparse.ArgumentParser(description=__doc__)
mode = parser.add_mutually_exclusive_group(required=True)
mode.add_argument('--prepare', action='store_true')
mode.add_argument('--apply', action='store_true')
args = parser.parse_args()

def write_bytes(path, value):
    path = Path(path)
    temp = path.with_name(path.name + '.source-photo-index-tmp')
    with temp.open('wb') as stream:
        stream.write(value)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)

def write(path, value):
    write_bytes(path, (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode())

assert not (H / 'publication-receipt.json').exists(), 'Index already published; inspect the receipt.'
manifest = read(H / 'input-manifest.json')
candidate = read(H / 'prepared-pointer.json')
old = read(manifest['pointer']['snapshot'])
freeze = read(H / 'candidate-freeze.json')
assert freeze['frozen_artifacts']
for path, expected in freeze['frozen_artifacts'].items():
    assert sha(path) == expected, path
for key, entry in manifest.items():
    assert sha(entry['path']) == sha(entry['snapshot']) == entry['sha256'], key
assert candidate['register_sha256'] == old['register_sha256'] == freeze['candidate_register_sha256']
assert candidate['workbook_sha256'] == old['workbook_sha256'] == freeze['candidate_workbook_sha256']
allowed_pointer_keys = {'recorded_utc', 'publication_receipt', 'current_source_photo_review_index', 'latest_master_metadata_change'}
assert {k: v for k, v in candidate.items() if k not in allowed_pointer_keys} == {k: v for k, v in old.items() if k not in allowed_pointer_keys}
index_ref = candidate['current_source_photo_review_index']
assert sha(B / index_ref['path']) == index_ref['sha256']
assert sha(B / index_ref['review']) == index_ref['review_sha256']
index = read(B / index_ref['path'])
assert index['counts'] == index_ref['counts']
assert index['counts'] == {'review_packets': 14, 'retained_source_offers': 46, 'existing_options': 43,
    'full_qualified_working_fields': 258, 'new_platform_pairs': 0, 'new_physical_verifications': 0, 'new_product_records': 0}
for path, expected in index['provider_files'].items():
    assert sha(path) == expected, path
register = read(B / candidate['register'])
options = {o['product_id']: o for o in register['options']}
assets = read(B / candidate['current_asset_reference_map']['path'])
assert len(index['existing_option_records']) == 43
for recorded in index['existing_option_records']:
    option = options[recorded['product_id']]
    assert option['product_id'] in register['active_option_ids']
    assert len(recorded['master_fields']) == 6 and recorded['master_fields'] == option['master_fields']
    for key in ['product_id', 'name', 'file_id', 'folder_id', 'image_url', 'folder_url', 'canonical_component_id']:
        assert recorded[key] == option[key], (recorded['product_id'], key)
    assert recorded['folder_id'] == assets[option['file_id']]['folder_id']
    assert all(dropbox_path(recorded[k]) == dropbox_path(assets[option['file_id']][k]) for k in ['image_url', 'folder_url'])

qa_ref = read(H / 'independent-qa-reference.json')
assert sha(qa_ref['path']) == qa_ref['sha256'] and sha(qa_ref['seal_path']) == qa_ref['seal_sha256']
qa = read(qa_ref['path'])
assert qa['status'] == 'PASS' and qa['checks_passed'] == qa['checks_total']
assert qa['candidate_freeze_sha256'] == sha(H / 'candidate-freeze.json')
assert qa['candidate_register_sha256'] == candidate['register_sha256']
assert qa['candidate_workbook_sha256'] == candidate['workbook_sha256']
assert qa['frozen_artifacts']
for path, expected in qa['frozen_artifacts'].items():
    assert sha(path) == expected, path
seal = read(qa_ref['seal_path'])
seal_files = seal['files']
seal_files = seal_files.items() if isinstance(seal_files, dict) else [(x['path'], x['sha256']) for x in seal_files]
for path, expected in seal_files:
    path = Path(path)
    path = path if path.is_absolute() else Path(qa_ref['seal_path']).parent / path
    expected = expected if isinstance(expected, str) else expected['sha256']
    assert sha(path) == expected, path

prepared_paths = read(H / 'prepared-control-paths.json')
expected_destinations = {manifest[f'control_{i}']['path'] for i in range(3)}
assert set(prepared_paths) == expected_destinations
control_updates = {}
allowed_control_keys = {'updated_utc', 'current_master_catalogue', 'current_source_photo_review_index', 'latest_master_metadata_change'}
for destination, prepared in prepared_paths.items():
    value = read(prepared)
    before = read(destination)
    assert before['current_master_catalogue'] == old and value['current_master_catalogue'] == candidate
    assert value['current_source_photo_review_index'] == index_ref
    assert value['latest_master_metadata_change'] == candidate['latest_master_metadata_change']
    assert {k: v for k, v in value.items() if k not in allowed_control_keys} == {k: v for k, v in before.items() if k not in allowed_control_keys}
    control_updates[Path(destination)] = Path(prepared).read_bytes()
if args.prepare:
    print('ALL_SOURCE_PHOTO_INDEX_GUARDS_PASS_PREPARED_ONLY')
    raise SystemExit(0)

updates = {**control_updates, B / 'current-master.json': (H / 'prepared-pointer.json').read_bytes()}
originals = {Path(x['path']): Path(x['snapshot']).read_bytes() for x in manifest.values() if Path(x['path']) in updates}
for key, entry in manifest.items():
    assert sha(entry['path']) == entry['sha256'], key
applied = []
try:
    for path, content in updates.items():
        assert path.read_bytes() == originals[path], path
        write_bytes(path, content)
        applied.append(path)
    assert read(B / 'current-master.json') == candidate
    assert all(read(path)['current_master_catalogue'] == candidate for path in control_updates)
    for key in ['register', 'workbook', 'native_map', 'asset_map', 'audit']:
        assert sha(manifest[key]['path']) == manifest[key]['sha256'], key
except Exception:
    for path in reversed(applied):
        if path.read_bytes() == updates[path]:
            write_bytes(path, originals[path])
    raise

receipt = {'status': 'PASS_PUBLISHED_AND_READ_BACK', 'publication_mode': 'SOURCE_PHOTO_EVIDENCE_INDEX_METADATA_ONLY',
    'recorded_utc': candidate['recorded_utc'], 'committed_utc': datetime.now(timezone.utc).isoformat(),
    'preceding_publication_receipt': old['publication_receipt'], 'preceding_pointer_sha256': manifest['pointer']['sha256'],
    'current_master_pointer_sha256': sha(B / 'current-master.json'), 'source_photo_review_index': index_ref,
    'register': str(B / candidate['register']), 'register_sha256': candidate['register_sha256'],
    'workbook': str(B / candidate['workbook']), 'workbook_sha256': candidate['workbook_sha256'],
    'audit_sha256': manifest['audit']['sha256'], 'controls_sha256': {str(path): sha(path) for path in control_updates},
    'all_five_data_artifacts_byte_identical': True, 'new_native_or_platform_writes': 0,
    'counts': index['counts'], 'independent_qa': qa_ref, 'candidate_freeze_sha256': sha(H / 'candidate-freeze.json')}
write(H / 'publication-receipt.json', receipt)
write(H / 'post-publication-readback.json', {'status': 'PASS', 'pointer_and_three_controls_equal_candidate': True,
    'all_five_data_artifacts_byte_identical': True, 'current_pointer_sha256': sha(B / 'current-master.json'),
    'source_photo_review_index': index_ref, 'all_43_current_options_and_258_fields_match': True})
print(json.dumps(receipt, ensure_ascii=False, indent=2))
