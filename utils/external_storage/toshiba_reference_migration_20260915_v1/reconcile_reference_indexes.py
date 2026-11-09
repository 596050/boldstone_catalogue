#!/usr/bin/env python3
"""Independently reconcile reference streams, document identities and scope lists."""
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import posixpath

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024**2), b''):
            value.update(block)
    return value.hexdigest()


def read_lines(path):
    with gzip.open(path, 'rt') as stream:
        for line in stream:
            yield json.loads(line)


def main():
    config = json.loads((ROOT / 'data_paths.json').read_text())
    mount = config['external_storage']['mount_point'].rstrip('/')
    mapping = {**config['container_relocations'], **config['path_relocations']}
    failures = Counter()
    examples = []

    def fail(kind, detail):
        failures[kind] += 1
        if len(examples) < 30:
            examples.append({'kind': kind, 'detail': detail})

    def validate_reference(ref):
        original, current, prefix = (ref[k] for k in ('original', 'current', 'mapping_prefix'))
        absolute = original.startswith(mount + '/')
        relative = original[len(mount) + 1:] if absolute else original
        if prefix not in mapping or '..' in relative.split('/'):
            fail('unknown_or_escaping_prefix', ref)
            return
        relative = posixpath.normpath(relative)
        if relative != prefix and not relative.startswith(prefix + '/'):
            fail('reference_prefix_mismatch', ref)
            return
        tail = relative[len(prefix):].lstrip('/')
        expected = (mount + '/' if absolute else '') + mapping[prefix] + ('/' + tail if tail else '')
        if expected != current:
            fail('reference_translation_mismatch', ref)

    groups = {
        'local': ('LOCAL_REFERENCE_FILES_SCOPED.txt', ['local_reference_index', 'local_reference_retry']),
        'additional_local': ('ADDITIONAL_LOCAL_REFERENCE_FILES.txt', ['additional_local_reference_index']),
        'compressed_local': ('COMPRESSED_LOCAL_REFERENCE_FILES.txt', ['compressed_local_reference_index']),
        'external': ('EXTERNAL_REFERENCE_FILES.txt', ['external_reference_index', 'external_reference_resume']),
        'final_authority': ('FINAL_AUTHORITY_REFERENCE_FILES.txt', ['final_authority_reference_index']),
        'final_authority_followup': ('FINAL_AUTHORITY_REFERENCE_FILES.txt', ['final_authority_followup']),
    }
    summaries, unique, supersessions = {}, {}, []
    binaries = {x['path']: x for x in json.loads((HERE / 'BINARY_METADATA_ACCOUNTING.json').read_text())}
    for group, (scope_file, directories) in groups.items():
        expected_paths = set((HERE / scope_file).read_text().splitlines()) - {''}
        group_documents = {}
        part_reports = []
        for directory in directories:
            base = HERE / directory
            summary_file = base / 'SUMMARY.json'
            if directory == 'external_reference_resume':
                summary = json.loads(summary_file.read_text())
                if summary['status'] != 'COMPLETE' or summary.get('errors', 0):
                    raise ValueError('Resumed external audit has unresolved errors')
            documents = {}
            for row in read_lines(base / 'DOCUMENTS.jsonl.gz'):
                if row['path'] in documents or row['path'] in group_documents:
                    fail('duplicate_document_within_group', row['path'])
                documents[row['path']] = row
            actual = Counter()
            rows = 0
            for record in read_lines(base / 'CURRENT_REFERENCES.jsonl.gz'):
                identity = record['document']
                declared = documents.get(identity['path'])
                if declared is None or any(identity[k] != declared[k] for k in ('bytes', 'sha256', 'mtime_ns')):
                    fail('document_identity_mismatch', identity['path'])
                if record.get('original_bytes_preserved') is not True:
                    fail('unbound_original', identity['path'])
                for reference in record['references']:
                    validate_reference(reference)
                actual[identity['path']] += len(record['references'])
                rows += 1
                if rows % 10000 == 0:
                    print(json.dumps({'part': directory, 'index_rows_checked': rows}), flush=True)
            for name, row in documents.items():
                if actual[name] != row['references']:
                    fail('reference_count_mismatch', name)
            part = {'directory': directory, 'documents': len(documents),
                    'documents_with_references': sum(bool(x['references']) for x in documents.values()),
                    'references': sum(actual.values()), 'bytes_read': sum(x['bytes'] for x in documents.values()),
                    'index_records': rows,
                    'index_sha256': digest(base / 'CURRENT_REFERENCES.jsonl.gz'),
                    'documents_sha256': digest(base / 'DOCUMENTS.jsonl.gz'),
                    'mapping_snapshot_sha256': digest(base / 'PATH_RELOCATIONS.json')}
            part_reports.append(part)
            group_documents.update(documents)
            print(json.dumps({'verified_part': part}), flush=True)
        binary_paths = set(binaries) if group == 'external' else set()
        accounted = set(group_documents) | binary_paths
        missing, unexpected = sorted(expected_paths - accounted), sorted(accounted - expected_paths)
        if missing or unexpected or binary_paths.intersection(group_documents):
            fail('scope_coverage_mismatch', {'group': group, 'missing': missing[:20], 'unexpected': unexpected[:20]})
        summaries[group] = {'candidate_files': len(expected_paths), 'documents_read': len(group_documents),
                            'binary_files_accounted': len(binary_paths),
                            'references': sum(x['references'] for x in group_documents.values()),
                            'missing_files': missing, 'unexpected_files': unexpected,
                            'scope_list_sha256': digest(HERE / scope_file), 'parts': part_reports}
        for name, row in group_documents.items():
            if name in unique:
                previous = unique[name]
                supersessions.append({'path': name, 'previous_group': previous['group'], 'current_group': group,
                                      'before_sha256': previous['sha256'], 'after_sha256': row['sha256'],
                                      'before_references': previous['references'], 'after_references': row['references']})
                if not group.startswith('final_authority') and previous['sha256'] != row['sha256']:
                    fail('unexplained_cross_group_change', name)
            unique[name] = {**row, 'group': group}

    member_counts = Counter()
    members = 0
    for row in read_lines(HERE / 'CONTAINER_METADATA_REFERENCES.jsonl.gz'):
        if row['container_sha256'] != binaries[row['container']]['sha256']:
            fail('container_identity_mismatch', row['container'])
        for reference in row['references']:
            validate_reference(reference)
        member_counts[row['container']] += len(row['references'])
        members += 1
    for name, row in binaries.items():
        if member_counts[name] != row.get('references', 0):
            fail('container_reference_count_mismatch', name)

    out = {
        'schema': 'marketmaker.storage_reference_reconciliation.v1',
        'verified_at_utc': datetime.now(timezone.utc).isoformat(),
        'status': 'PASS' if not failures else 'FAIL',
        'groups': summaries, 'superseded_document_versions': supersessions,
        'unique_text_or_compressed_documents': len(unique),
        'unique_binary_documents_accounted': len(binaries),
        'unique_source_files_accounted': len(unique) + len(binaries),
        'unique_document_reference_occurrences': sum(x['references'] for x in unique.values()),
        'metadata_container_members': members,
        'metadata_container_reference_occurrences': sum(member_counts.values()),
        'total_current_reference_occurrences': sum(x['references'] for x in unique.values()) + sum(member_counts.values()),
        'failures': dict(failures), 'failure_examples': examples,
        'source_mutations_by_audits': 0,
        'verification_scope': 'Every indexed reference was independently translated and checked; every document count and source identity was reconciled to its index and supplied candidate lists. Final authority versions supersede earlier observations of the same three files. Current references can name historical absent or prospective outputs; index membership is not a claim that each referenced object exists.',
        'limits': 'This is not an atomic filesystem snapshot. Original data payloads and sealed historical receipts remain unchanged. General opaque archives and disk-image interiors are excluded; five small sealed metadata TAR containers were indexed separately without extraction.'
    }
    target = HERE / 'FINAL_REFERENCE_RECONCILIATION.json'
    with target.open('x') as stream:
        json.dump(out, stream, indent=2)
        stream.write('\n')
    print(json.dumps({k: v for k, v in out.items() if k not in ('groups', 'superseded_document_versions')}), flush=True)
    if failures:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
