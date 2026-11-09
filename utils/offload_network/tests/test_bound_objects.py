"""Bound capture preserves transport identity and validates bytes sent to tar."""
from contextlib import contextmanager
import hashlib
import os
from pathlib import Path

import pytest

from research_workflows import bound_objects
from research_workflows.common import inventory
from research_workflows.objects import pack, extract_object


def source(tmp_path):
    root = tmp_path / 'source'; (root / 'nested').mkdir(parents=True)
    (root / 'first.bin').write_bytes(bytes(range(256))*4097)
    (root / 'nested/second.bin').write_bytes(b'duplicate\n'*100)
    (root / 'empty.bin').write_bytes(b'')
    return root, inventory(root)


def test_same_archive_bytes_with_exactly_one_source_read(tmp_path, monkeypatch):
    root, expected = source(tmp_path)
    original = pack(root, tmp_path / 'original.tar.gz', max_bytes=4 << 20)
    opened, byte_counts, progress = [], {}, []
    original_open = bound_objects._open_source
    @contextmanager
    def observed(path):
        opened.append(path); byte_counts[path] = 0
        with original_open(path) as stream:
            class Reader:
                def read(self, size=-1):
                    result = stream.read(size); byte_counts[path] += len(result)
                    return result
                def fileno(self): return stream.fileno()
            yield Reader()
    monkeypatch.setattr(bound_objects, '_open_source', observed)
    actual = bound_objects.pack(root, tmp_path / 'bound.tar.gz', expected, max_bytes=4 << 20,
        progress=lambda *row: progress.append(row))
    assert actual == original
    assert (tmp_path / 'bound.tar.gz').read_bytes() == (tmp_path / 'original.tar.gz').read_bytes()
    assert len(opened) == len(expected) == len(set(opened))
    assert sum(byte_counts.values()) == sum(row['bytes'] for row in expected.values())
    assert progress[-1][0] == len(expected) and progress[-1][2] == sum(byte_counts.values())
    extract_object(tmp_path / 'bound.tar.gz', tmp_path / 'expanded', max_bytes=4 << 20)
    assert inventory(tmp_path / 'expanded/data') == expected


def test_changed_stream_is_rejected_even_when_source_file_is_unchanged(tmp_path, monkeypatch):
    root, expected = source(tmp_path); original_open = bound_objects._open_source
    @contextmanager
    def corrupted(path):
        with original_open(path) as stream:
            class Reader:
                def read(self, size=-1):
                    block = stream.read(size)
                    return bytes([block[0]^1])+block[1:] if block else block
                def fileno(self): return stream.fileno()
            yield Reader()
    monkeypatch.setattr(bound_objects, '_open_source', corrupted)
    with pytest.raises(ValueError, match='streamed source bytes'):
        bound_objects.pack(root, tmp_path / 'failed.tar.gz', expected, max_bytes=4 << 20)
    assert inventory(root) == expected  # before/after source hashes cannot detect this bad stream
    assert (tmp_path / 'failed.tar.gz').is_file()


def test_explicit_selection_does_not_capture_unlisted_files(tmp_path):
    root, expected = source(tmp_path)
    selected = {'empty.bin': expected['empty.bin']}
    result = bound_objects.pack(root, tmp_path / 'selected.tar.gz', selected)
    assert result['content_manifest']['files'] == selected


def test_wrong_predeclared_identity_is_not_replaced_with_current_hash(tmp_path):
    root, expected = source(tmp_path)
    expected['first.bin']['sha256'] = hashlib.sha256(b'other').hexdigest()
    with pytest.raises(ValueError, match='declared file identity'):
        bound_objects.pack(root, tmp_path / 'wrong.tar.gz', expected, max_bytes=4 << 20)


def test_size_limit_rejects_before_opening_any_source_or_output(tmp_path, monkeypatch):
    root, expected = source(tmp_path)
    def forbidden(*args): pytest.fail('oversized manifest reached source reads')
    monkeypatch.setattr(bound_objects, '_open_source', forbidden)
    with pytest.raises(ValueError, match='before reading'):
        bound_objects.pack(root, tmp_path / 'wrong.tar.gz', expected, max_bytes=10)
    assert not (tmp_path / 'wrong.tar.gz').exists()


@pytest.mark.skipif(os.name == 'nt', reason='creating symlinks needs developer privileges')
def test_linked_source_and_output_inside_source_are_refused(tmp_path):
    root, expected = source(tmp_path)
    with pytest.raises(ValueError, match='inside its source'):
        bound_objects.pack(root, root / 'object.tar.gz', expected, max_bytes=4 << 20)
    target = root / 'first.bin'; renamed = root / 'real.bin'; target.rename(renamed)
    target.symlink_to(renamed.name)
    with pytest.raises(ValueError, match='symlink'):
        bound_objects.pack(root, tmp_path / 'wrong.tar.gz', expected, max_bytes=4 << 20)
