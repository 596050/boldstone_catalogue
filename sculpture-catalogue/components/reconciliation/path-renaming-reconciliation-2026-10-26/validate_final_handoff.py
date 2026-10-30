"""Independently read saved rename receipts. No Dropbox, app or catalogue writes.

Only this reconciliation directory receives an audit result. An initial plan or
an unfinished async batch can never be treated as final native path evidence.
"""
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from urllib.parse import quote
import hashlib
import json
import re
import unicodedata

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[2]
NATIVE = Path('/Users/tprice/BoldstoneMigration/path-renaming-20261026')
read = lambda path: json.loads(Path(path).read_text())
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
checks = 0


def check(condition, message):
    global checks
    checks += 1
    if not condition:
        raise AssertionError(message)


def finish(status, **details):
    result = {'status': status, 'checked_utc': datetime.now(timezone.utc).isoformat(),
              'checks': checks, 'root_live_native_calls': 0,
              'root_app_review_and_shared_catalogue_writes': 0,
              'audit_scope': 'Independent readback of saved native receipts; no fresh native API verification.',
              **details}
    (HERE / 'final-handoff-readback.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'current_selected_references'}, indent=2))


def prefix(path):
    parent = PurePosixPath(path).parent

    def slug(text):
        text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode().lower()
        return re.sub(r'[^a-z0-9]+', '-', text.replace('&', ' and ')).strip('-')

    return slug(parent.parent.name) + '__' + slug(parent.name) + '__'


def main():
    pointer_path = BASE / 'current-master.json'
    pointer_sha = sha(pointer_path)
    pointer = read(pointer_path)
    check(sha(BASE / pointer['register']) == pointer['register_sha256'], 'Canonical register binding')
    missing_inputs = [] if (NATIVE / 'completion.json').is_file() else ['completion.json']
    if missing_inputs:
        finish('WAITING_FOR_FINAL_NATIVE_HANDOFF', missing_inputs=missing_inputs,
               canonical_pointer_sha256=pointer_sha, publication_held=True)
        return

    completion = read(NATIVE / 'completion.json')
    overlay_path = Path(completion['current_filename_paths']).resolve()
    check(overlay_path.is_relative_to(NATIVE) and overlay_path.name == 'current-filename-paths.json', 'Completed immutable overlay is task scoped')
    overlay = read(overlay_path)
    verification_path = Path(overlay['verification'])
    check(verification_path.resolve() == Path(completion['verification']).resolve(), 'Exact completed verifier receipt path')
    check(verification_path.is_relative_to(NATIVE) and verification_path.parent == overlay_path.parent, 'Versioned verification attempt scope')
    check(sha(verification_path) == overlay['verification_sha256'], 'Verifier receipt hash')
    verified = read(verification_path)
    check(verified['status'] == 'PASS' and not verified['errors'], 'Final verifier passed')
    check(completion['state'] == 'completed', 'Terminal filename completion')
    check(completion['current_filename_paths_sha256'] == sha(overlay_path), 'Completion binds final paths')
    check(Path(completion['current_filename_paths']).resolve() == overlay_path.resolve(), 'Completion paths identity')
    final_path = Path(verified['native_final'])
    check(final_path.resolve() == (verification_path.parent / 'native-final-independent.json').resolve(), 'Exact saved native snapshot')
    check(sha(final_path) == verified['native_final_sha256'], 'Saved native snapshot hash')
    check(sha(NATIVE / 'manifest.json') == verified['manifest_sha256'], 'Manifest evidence identity')
    check(overlay['namespace_id'] == '202238505', 'Boldstone namespace')

    before = {}
    for name in ['native-before.json', 'workshop-before.json']:
        for row in read(NATIVE / name)['entries']:
            check(row['id'] not in before, 'Unique initial scoped ID')
            before[row['id']] = row
    final = read(final_path)
    current = {}
    for scope in ['wall', 'workshop']:
        for row in final[scope]['entries']:
            check(row['id'] not in current, 'Unique current scoped ID')
            current[row['id']] = row
    old_files = {i: row for i, row in before.items() if row['kind'] == 'file'}
    current_files = {i: row for i, row in current.items() if row['kind'] == 'file'}
    paths = {row['id']: row for row in overlay['files']}
    check(len(paths) == len(overlay['files']), 'Unique final overlay IDs')
    check(set(paths) == set(current_files), 'Overlay exhausts captured current file IDs')
    check(len({row['path'].casefold() for row in paths.values()}) == len(paths), 'Unique current case-insensitive paths')
    absent = set(old_files) - set(current_files)
    check(set(overlay['externally_deleted_ids']) == absent, 'Exact external absence set')
    check(set(verified['external_deletion_receipts']) == absent, 'Every missing ID has a recorded deletion receipt')
    for fid, proof in verified['external_deletion_receipts'].items():
        check(proof['state'] in ('deleted', 'already_absent') and bool(proof['checked_utc']), 'Recorded absence receipt ' + fid)

    sequences = defaultdict(list)
    for fid, row in paths.items():
        observed = current_files[fid]
        for key in ['id', 'path', 'name', 'parent_id', 'size', 'content_hash']:
            check(row.get(key) == observed.get(key), 'Overlay/current ' + key)
        check(row['path'].startswith('/BOLDSTONE MASTER/'), 'Master-only scoped path')
        check(row['parent_id'] in current and current[row['parent_id']]['kind'] == 'folder', 'Actual native parent ID')
        check(str(PurePosixPath(row['path']).parent) == current[row['parent_id']]['path'], 'Actual native parent path')
        check(row['image_url'] == 'https://www.dropbox.com/preview' + quote(row['path'], safe='/'), 'Observed image link')
        check(row['folder_url'] == 'https://www.dropbox.com/home' + quote(current[row['parent_id']]['path'], safe='/'), 'Observed folder link')
        extension = PurePosixPath(row['name']).suffix
        match = re.fullmatch(re.escape(prefix(row['path'])) + r'(\d{3,})' + re.escape(extension), row['name'])
        check(bool(match), 'Filename matches current containing folder')
        sequences[row['parent_id']].append(int(match.group(1)))
        if fid in old_files:
            old = old_files[fid]
            for key in ['id', 'size', 'content_hash', 'client_modified', 'parent_id',
                        'has_explicit_shared_members', 'sharing_info_present', 'read_only',
                        'parent_shared_folder_id', 'file_lock_present']:
                check(old.get(key) == row.get(key), 'Preserved ' + key)
            check(PurePosixPath(old['name']).suffix == extension, 'Preserved original extension')
    for sequence in sequences.values():
        check(sorted(sequence) == list(range(1, len(sequence) + 1)), 'Contiguous actual-folder sequence')
    for fid, row in before.items():
        if row['kind'] != 'folder':
            continue
        check(fid in current, 'Original folder retained')
        for key in ['name', 'path', 'parent_id', 'sharing_info_present']:
            check(row.get(key) == current[fid].get(key), 'Original folder ' + key + ' unchanged')
    proofs = {(row['id'], row['original_url_sha256']): row
              for row in read(verification_path.parent / 'shared-link-survival.json')['checks']}
    links_checked = 0
    for old in read(NATIVE / 'links-before.json')['links']:
        if old['id'] not in current:
            continue
        proof = proofs.get((old['id'], old['url_sha256']))
        check(proof is not None and proof.get('original_link_resolves_to_same_id') is True, 'Recorded original shared-link survival')
        for key in ['resolved_visibility', 'effective_audience', 'link_access_level', 'expires']:
            check(old.get(key) == proof['current'].get(key), 'Recorded shared-link ' + key)
        links_checked += 1
    check(links_checked == verified['preserved_scoped_shared_links'], 'Exact preserved-link receipt count')

    register = read(BASE / pointer['register'])
    selected = []
    for option in register['options']:
        if option['product_id'] not in register['active_option_ids']:
            continue
        for role, key in [('primary', 'file_id'), ('context', 'context_file_id')]:
            fid = option.get(key)
            if fid in paths:
                row = paths[fid]
                selected.append({'product_id': option['product_id'], 'name': option['name'], 'role': role,
                                 'file_id': fid, 'folder_id': row['parent_id'],
                                 'image_url': row['image_url'], 'folder_url': row['folder_url']})
    check(sha(pointer_path) == pointer_sha, 'Canonical pointer still held')
    finish('PASS_SAVED_FINAL_NATIVE_RECEIPTS_PENDING_APP_HANDOFF_AND_PUBLICATION',
           canonical_pointer_sha256=pointer_sha, final_overlay=str(overlay_path),
           final_overlay_sha256=sha(overlay_path), current_scoped_files=len(paths),
           workshop_files=sum('/Products/Workshop and Moulding/' in r['path'] for r in paths.values()),
           externally_deleted_ids=len(absent), preserved_shared_links=links_checked,
           selected_reference_links=len(selected), current_selected_references=selected,
           publication_held=True, remaining=['Owning-session final app release handoff',
           'Revalidate queued Primary choices at the current review event cutoff',
           'Immutable register/gallery/workbook reconciliation and independent readback'])


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        finish('FAIL_SAVED_FINAL_NATIVE_HANDOFF_CHECK', error=str(error), publication_held=True)
        raise
