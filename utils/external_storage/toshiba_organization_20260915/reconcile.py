"""Independently reconcile every recorded file before any empty-root cleanup."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
from organize import HERE, MOUNT, atomic_json, inventory, utc, validate_volume
from registry import verified_actions, sha
from build_plan import route


def rows(path):
    with gzip.open(path, 'rt') as f:
        for line in f:
            yield json.loads(line)


def absolute_relative(prefix, suffix):
    return prefix if suffix == '.' else prefix + '/' + suffix


def metadata(row):
    return row['bytes'], row['mtime_ns'], row.get('inode') if row['bytes'] else None


def audit():
    validate_volume()
    plan = json.loads((HERE / 'PLAN.json').read_text())
    verified = verified_actions(plan)
    if len(verified) != len(plan['actions']):
        raise RuntimeError(f'{len(plan["actions"]) - len(verified)} moves remain; full cleanup is not authorized by the evidence yet')
    output = HERE / 'reconciliation'
    output.mkdir(exist_ok=True)
    expected, expected_directories, category_counts = {}, set(), {}
    for row in rows(HERE / 'census_repaired/DIRECTORIES.jsonl.gz'):
        target, action = route(row['path'], verified)
        if action is not None:
            expected_directories.add(target)
    samples = 0
    for action in plan['actions']:
        ident = hashlib.sha256((action['source'] + '\0' + action['target']).encode()).hexdigest()[:24]
        folder = HERE / 'execution/moves' / ident
        receipt = json.loads((folder / 'RECEIPT.json').read_text())
        counts = category_counts.setdefault(action['category'], Counter())
        samples += receipt['samples_verified']
        for row in rows(folder / 'BEFORE.jsonl.gz'):
            source = absolute_relative(action['source'], row['relative'])
            target = absolute_relative(action['target'], row['relative'])
            if row['kind'] == 'directory':
                expected_directories.add(target)
            elif row['kind'] == 'file':
                if source in expected:
                    raise RuntimeError('Duplicate file in move receipts: ' + source)
                expected[source] = (target, *metadata(row))
                counts['files'] += 1
                counts['bytes'] += row['bytes']
            else:
                raise RuntimeError('Unexpected non-file/non-directory requires explicit reconciliation')
    # Compare the independently collected pre-organization census with the
    # immediate pre-rename inventories. Concurrent additions/changes are retained
    # explicitly; a missing original file blocks successful reconciliation.
    initial_missing = initial_changed = initial_files = 0
    matched_sources = set()
    with gzip.open(output / 'CENSUS_TO_MOVE_DIFFERENCES.jsonl.gz', 'wt') as out:
        for row in rows(HERE / 'census_repaired/FILES.jsonl.gz'):
            source = row['path']
            if not source.startswith(('marketmaker/', 'marketmaker_v2/', 'macroeconomics/')):
                continue
            initial_files += 1
            observed = expected.get(source)
            if observed is None:
                initial_missing += 1
                out.write(json.dumps({'kind': 'missing_from_move_inventories', 'source': source, 'census': row}) + '\n')
            else:
                matched_sources.add(source)
                if metadata(row) != observed[1:]:
                    initial_changed += 1
                    out.write(json.dumps({'kind': 'changed_before_move', 'source': source,
                                          'census_metadata': metadata(row), 'move_metadata': observed[1:]}) + '\n')
        for source in expected.keys() - matched_sources:
            out.write(json.dumps({'kind': 'added_before_move', 'source': source, 'move': expected[source]}) + '\n')
    added_before = len(expected) - len(matched_sources)
    del matched_sources
    total_files = len(expected)
    total_bytes = sum(v[1] for v in expected.values())
    target_expected = {value[0]: value[1:] for value in expected.values()}
    if len(target_expected) != len(expected):
        raise RuntimeError('Duplicate destination in move inventories')
    del expected
    # Separate traversal of the actual final namespaces, with every file read
    # through the filesystem metadata API again. No receipt substitution.
    post_counts = {}
    for root in ['raw_price_data', 'other_data']:
        print('Independent final traversal: ' + root, flush=True)
        post_counts[root] = inventory(MOUNT / root, output / (root + '.jsonl.gz'), sample_limit=0)
    missing_directories = set(expected_directories)
    changed_after = unexpected_after = matched_after = 0
    known_new = {'raw_price_data/.marketmaker-storage-identity.json'}
    with gzip.open(output / 'MOVE_TO_FINAL_DIFFERENCES.jsonl.gz', 'wt') as out:
        for root in post_counts:
            for row in rows(output / (root + '.jsonl.gz')):
                target = absolute_relative(root, row['relative'])
                if row['kind'] == 'directory':
                    missing_directories.discard(target)
                    continue
                if row['kind'] != 'file':
                    raise RuntimeError('Unexpected final entry kind')
                before = target_expected.pop(target, None)
                if before is None:
                    if target not in known_new:
                        unexpected_after += 1
                        out.write(json.dumps({'kind': 'added_after_move', 'target': target, 'final': row}) + '\n')
                else:
                    matched_after += 1
                    if metadata(row) != before:
                        changed_after += 1
                        out.write(json.dumps({'kind': 'changed_after_move', 'target': target,
                                              'before': before, 'after': metadata(row)}) + '\n')
        for target, before in target_expected.items():
            out.write(json.dumps({'kind': 'missing_after_move', 'target': target, 'before': before}) + '\n')
        for target in missing_directories:
            out.write(json.dumps({'kind': 'directory_missing_after_move', 'target': target}) + '\n')
    success = not (initial_missing or target_expected or missing_directories or changed_after)
    result = {
        'schema': 'toshiba.organization.reconciliation.v1', 'at_utc': utc(),
        'status': 'PASS' if success else 'REQUIRES_RECONCILIATION_NO_CLEANUP',
        'plan_sha256': sha(HERE / 'PLAN.json'), 'verified_moves': len(verified),
        'preserved_files_at_move': total_files, 'preserved_logical_bytes_at_move': total_bytes,
        'initial_project_files': initial_files, 'missing_initial_files': initial_missing,
        'files_added_before_move': added_before, 'files_changed_before_move': initial_changed,
        'matched_final_files': matched_after, 'missing_final_files': len(target_expected),
        'missing_final_directories': len(missing_directories), 'files_changed_after_move': changed_after,
        'files_added_after_move': unexpected_after, 'content_samples_verified': samples,
        'category_counts': category_counts, 'final_buckets': post_counts,
        'verification_scope': 'Every file path, length, mtime and non-empty file inode; directory namespace; selected full or head/tail SHA256 samples. Same-volume renames preserve payload extents. Not a full payload hash or independent backup.',
        'untouched_os_namespaces': ['.Spotlight-V100', '.Trashes', '$RECYCLE.BIN', 'System Volume Information', '.fseventsd'],
        'container_policy': 'All archives and disk images preserved intact; tar member inventory retained for three legacy bundles; disk image interiors not independently enumerated',
    }
    atomic_json(output / 'RESULT.json', result)
    print(json.dumps({k:v for k,v in result.items() if k not in {'final_buckets', 'category_counts'}}, indent=2), flush=True)
    if not success:
        raise SystemExit(2)


def cleanup():
    validate_volume()
    result = json.loads((HERE / 'reconciliation/RESULT.json').read_text())
    if result['status'] != 'PASS' or result['plan_sha256'] != sha(HERE / 'PLAN.json'):
        raise RuntimeError('Successful current-plan reconciliation is required')
    actions = []
    for relative in ['marketmaker/data', 'marketmaker']:
        path = MOUNT / relative
        if path.exists():
            # Kernel rmdir removes ONLY an empty directory, including hidden
            # entries. No recursive deletion, wildcard or payload unlink.
            path.rmdir()
            actions.append({'operation': 'rmdir', 'path': str(path), 'at_utc': utc()})
    v2 = MOUNT / 'marketmaker_v2'
    if not v2.is_dir():
        raise RuntimeError('marketmaker_v2 root must remain in place')
    remaining = [p.name for p in v2.iterdir()]
    atomic_json(HERE / 'DELETION_READINESS.json', {
        'at_utc': utc(), 'marketmaker_removed': not (MOUNT / 'marketmaker').exists(),
        'operations': actions, 'marketmaker_v2_root_retained': True,
        'marketmaker_v2_remaining_entries': remaining,
        'marketmaker_v2_ready_for_empty_directory_removal': not remaining,
        'payload_files_deleted': 0, 'reconciliation_sha256': sha(HERE / 'reconciliation/RESULT.json'),
    })
    print((HERE / 'DELETION_READINESS.json').read_text(), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['audit', 'cleanup'])
    args = parser.parse_args()
    audit() if args.command == 'audit' else cleanup()
