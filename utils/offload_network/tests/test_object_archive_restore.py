"""A completed store may retain archives; execution must restore verified bytes."""
from concurrent.futures import ThreadPoolExecutor
import shutil

import pytest

from offload_service.core import CapacityError
from research_workflows import objects
from research_workflows.common import atomic, load, sha
from research_workflows.compressed import compact_object


@pytest.fixture
def archived(tmp_path):
    source = tmp_path / 'source'
    source.mkdir()
    (source / 'run.py').write_text('print("retained identity")\n')
    store = objects.ObjectStore(tmp_path / 'store', max_object_mb=1,
                                max_store_mb=8, min_free_mb=1)
    identity = store.ingest(source)
    root, manifest = store.get(identity)
    compact_object(root, identity, max_bytes=store.max_bytes)
    assert not (root / 'data').exists()
    return store, identity, root, manifest, source


def test_idempotent_ingest_then_execution_restores_same_bytes(archived):
    store, identity, root, manifest, source = archived
    marker = (root / 'ARCHIVE_ONLY.json').read_bytes()
    commit = (root / 'COMMITTED.json').read_bytes()
    assert store.ingest(source) == identity
    assert store.get(identity) == (root, manifest)
    assert (root / 'data/run.py').read_bytes() == (source / 'run.py').read_bytes()
    assert sha(root / 'archive.tar.gz') == identity
    assert (root / 'ARCHIVE_ONLY.json').read_bytes() == marker
    assert (root / 'COMMITTED.json').read_bytes() == commit
    assert load(root / 'RESTORED.json')['object_sha256'] == identity


@pytest.mark.parametrize('mutation', ['missing_marker', 'false_marker', 'archive', 'interrupted_compaction'])
def test_unbound_or_corrupt_retention_is_not_restored(archived, mutation):
    store, identity, root, _, _ = archived
    if mutation == 'missing_marker':
        (root / 'ARCHIVE_ONLY.json').unlink()
    elif mutation == 'false_marker':
        row = load(root / 'ARCHIVE_ONLY.json')
        row['manifest_sha256'] = 'a' * 64
        atomic(root / 'ARCHIVE_ONLY.json', row)
    elif mutation == 'archive':
        with (root / 'archive.tar.gz').open('ab') as stream:
            stream.write(b'unbound suffix')
    else:
        (root / 'data.compacting').mkdir()
    with pytest.raises((ValueError, OSError)):
        store.get(identity)
    assert not (root / 'data').exists()
    assert not list((store.root / 'uploads').glob('.restore-*'))


@pytest.mark.parametrize('limit', ['store', 'reserve'])
def test_restoration_obeys_capacity_before_expansion(archived, monkeypatch, limit):
    store, identity, root, _, _ = archived
    if limit == 'store':
        store.max_store = 1
    else:
        usage = shutil.disk_usage(store.root)
        monkeypatch.setattr(objects.shutil, 'disk_usage',
                            lambda path: usage._replace(free=store.reserve))
    with pytest.raises(CapacityError):
        store.get(identity)
    assert not (root / 'data').exists()
    assert sha(root / 'archive.tar.gz') == identity


def test_concurrent_consumers_expand_once_then_reverify(archived, monkeypatch):
    store, identity, root, manifest, _ = archived
    original = objects.extract_object
    calls = []
    def counted(*args, **kwargs):
        calls.append(args)
        return original(*args, **kwargs)
    monkeypatch.setattr(objects, 'extract_object', counted)
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(store.get, [identity] * 3))
    assert results == [(root, manifest)] * 3
    assert len(calls) == 1
    (root / 'data/run.py').write_text('corrupt expanded bytes')
    with pytest.raises(ValueError):
        store.get(identity)
    assert len(calls) == 1  # A damaged live tree is not silently replaced.


def test_failed_extraction_retains_archive_and_can_be_retried(archived, monkeypatch):
    store, identity, root, manifest, _ = archived
    original = objects.extract_object
    def fail(archive, destination, **kwargs):
        destination.mkdir()
        (destination / 'partial').write_text('incomplete')
        raise OSError('controlled extraction failure')
    monkeypatch.setattr(objects, 'extract_object', fail)
    with pytest.raises(OSError, match='controlled extraction'):
        store.get(identity)
    assert not (root / 'data').exists()
    assert not list((store.root / 'uploads').glob('.restore-*'))
    assert sha(root / 'archive.tar.gz') == identity
    monkeypatch.setattr(objects, 'extract_object', original)
    assert store.get(identity) == (root, manifest)
