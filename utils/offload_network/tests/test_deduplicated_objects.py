"""Deduplication changes representation, never original bytes or safety limits."""
import gzip
import io
from pathlib import Path
import tarfile

import pytest

from research_workflows.common import inventory, load, sha
from research_workflows.objects import ObjectStore, extract_object, object_expansion_budget, pack
from research_workflows.deduplicated_objects import verify, materialize
from research_workflows.compressed import verify_archive


def reports(root):
    root.mkdir()
    content = bytes(range(256)) * 1024
    (root / 'report.json').write_bytes(content)
    (root / 'nested').mkdir()
    (root / 'nested/report-copy.json').write_bytes(content)
    (root / 'third.json').write_bytes(content)
    (root / 'empty.txt').write_bytes(b'')
    return root


def test_roundtrip_one_payload_per_content_and_all_original_paths(tmp_path):
    source = reports(tmp_path / 'report')
    original = inventory(source)
    packed = pack(source, tmp_path / 'report.tar.gz', deduplicate=True)
    record = verify(tmp_path / 'report.tar.gz', packed['content_manifest'], max_bytes=1 << 20)
    assert record['file_count'] == 4 and record['payload_count'] == 2
    assert record['logical_bytes'] == 3 * record['unique_payload_bytes']
    extracted = tmp_path / 'out'
    extract_object(tmp_path / 'report.tar.gz', extracted, max_bytes=1 << 20)
    assert inventory(extracted / 'data') == original
    assert all(not member.islnk() and not member.issym()
               for member in tarfile.open(tmp_path / 'report.tar.gz'))
    assert inventory(source) == original


def test_deterministic_and_legacy_inputs_unchanged(tmp_path):
    source = reports(tmp_path / 'report')
    a = pack(source, tmp_path / 'a.gz', deduplicate=True)
    b = pack(source, tmp_path / 'b.gz', deduplicate=True)
    assert a == b
    old = pack(source, tmp_path / 'old.gz')
    assert old['content_manifest']['schema'] == 'marketmaker.offload_object.v1'
    extract_object(tmp_path / 'old.gz', tmp_path / 'legacy', max_bytes=1 << 20)
    assert inventory(tmp_path / 'legacy/data') == inventory(source)


def test_logical_expansion_budget_still_counts_duplicate_files(tmp_path):
    source = reports(tmp_path / 'report')
    pack(source, tmp_path / 'data.gz', deduplicate=True)
    with pytest.raises(ValueError, match='expansion limit'):
        object_expansion_budget(tmp_path / 'data.gz', max_bytes=400000)
    assert source.exists()


def test_selected_duplicate_can_materialize_without_exporting_other_paths(tmp_path):
    source = reports(tmp_path / 'report')
    r = pack(source, tmp_path / 'data.gz', deduplicate=True)
    wanted = {'nested/report-copy.json': r['content_manifest']['files']['nested/report-copy.json']}
    materialize(tmp_path / 'data.gz', tmp_path / 'selected', r['content_manifest'], files=wanted, max_bytes=1 << 20)
    assert inventory(tmp_path / 'selected') == wanted


@pytest.mark.parametrize('damage', ['payload', 'missing', 'duplicate', 'symlink', 'hardlink', 'path'])
def test_corrupted_or_unsafe_payloads_are_rejected_before_materialization(tmp_path, damage):
    source = reports(tmp_path / 'report')
    r = pack(source, tmp_path / 'good.gz', deduplicate=True)
    with tarfile.open(tmp_path / 'good.gz') as original, tarfile.open(tmp_path / 'bad.gz', 'w:gz') as bad:
        for index, member in enumerate(original):
            data = original.extractfile(member).read()
            if index == 1:
                if damage == 'missing': continue
                if damage == 'payload': data = bytes([data[0] ^ 1]) + data[1:] if data else b'x'
                if damage in ('symlink', 'hardlink'):
                    member.type = tarfile.SYMTYPE if damage == 'symlink' else tarfile.LNKTYPE
                    member.linkname = '../../outside'; member.size = 0; data = b''
                if damage == 'path': member.name = '../outside'
            if member.isreg(): member.size = len(data)
            bad.addfile(member, io.BytesIO(data))
            if index == 1 and damage == 'duplicate': bad.addfile(member, io.BytesIO(data))
    with pytest.raises(ValueError):
        extract_object(tmp_path / 'bad.gz', tmp_path / 'out', max_bytes=1 << 20)
    assert not (tmp_path / 'out/data').exists()


def test_object_store_commits_deduplicated_output_and_verifies_archive_only(tmp_path):
    source = reports(tmp_path / 'report')
    store = ObjectStore(tmp_path / 'store', min_free_mb=1, max_object_mb=2, max_store_mb=10)
    identity = store.ingest(source, deduplicate=True)
    root, manifest = store.get(identity)
    assert inventory(root / 'data') == inventory(source)
    verify_archive(root, identity, manifest, max_bytes=2 << 20)
    assert sha(root / 'archive.tar.gz') == identity
    copied = pack(root / 'data', tmp_path / 'returned-input.tar.gz')
    assert copied['object_sha256'] == identity
    assert copied['content_manifest'] == manifest
