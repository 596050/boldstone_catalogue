"""Content and concurrency oracles for overlapping sealed-object verification."""
from concurrent.futures import ThreadPoolExecutor
import threading

import pytest

from research_workflows import objects

Store = objects.ObjectStore


@pytest.fixture
def committed(tmp_path):
    store = Store(tmp_path / 'store', max_object_mb=1, max_store_mb=8, min_free_mb=1)
    identities = []
    for label in ('first', 'second'):
        source = tmp_path / label
        source.mkdir()
        (source / 'value.txt').write_text(label)
        identities.append(store.ingest(source))
    return store, identities


@pytest.mark.parametrize('phase', ['tree', 'archive'])
def test_same_object_reads_never_overlap_and_metadata_stays_available(committed, monkeypatch, phase):
    store, (identity, _) = committed
    attribute = 'verify_tree' if phase == 'tree' else 'sha'
    original = getattr(objects, attribute)
    entered, release, overlap, second_called = (threading.Event() for _ in range(4))
    guard, counters = threading.Lock(), {'active': 0, 'calls': 0}

    def checked(*args, **kwargs):
        with guard:
            counters['active'] += 1
            counters['calls'] += 1
            if counters['active'] > 1:
                overlap.set()
        entered.set()
        try:
            assert release.wait(5), 'fixture was not released'
            return original(*args, **kwargs)
        finally:
            with guard:
                counters['active'] -= 1

    def second():
        second_called.set()
        return store.get(identity)

    monkeypatch.setattr(objects, attribute, checked)
    with ThreadPoolExecutor(max_workers=3) as pool:
        first = pool.submit(store.get, identity)
        try:
            assert entered.wait(2)
            later = pool.submit(second)
            assert second_called.wait(2)
            # Metadata must remain responsive even while full verification waits.
            assert pool.submit(store.status, identity).result(timeout=2)['state'] == 'committed'
            assert not overlap.wait(.15), 'the same input bytes were verified concurrently'
        finally:
            release.set()
        assert first.result(timeout=5) == later.result(timeout=5)
    assert counters == {'active': 0, 'calls': 2}  # Both callers rehash, no reused digest.
    assert not store.verification_locks


def test_unrelated_objects_verify_concurrently(committed, monkeypatch):
    store, identities = committed
    original = objects.verify_tree
    together = threading.Barrier(2)

    def checked(*args, **kwargs):
        together.wait(timeout=3)
        return original(*args, **kwargs)

    monkeypatch.setattr(objects, 'verify_tree', checked)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(store.get, identities))
    assert {path.name for path, _ in results} == set(identities)


@pytest.mark.parametrize('changed', ['data', 'archive'])
def test_later_caller_rehashes_changed_bytes(committed, changed):
    store, (identity, _) = committed
    root, _ = store.get(identity)
    path = root / ('data/value.txt' if changed == 'data' else 'archive.tar.gz')
    old = path.read_bytes()
    # A same-size change must be caught; sizes or prior successful hashes are insufficient.
    path.write_bytes(old[:-1] + bytes([old[-1] ^ 1]))
    with pytest.raises((ValueError, OSError, EOFError)):
        store.get(identity)
    path.write_bytes(old)
    assert store.get(identity)[0] == root


def test_waiters_each_fail_then_fresh_attempt_recovers(committed, monkeypatch):
    store, (identity, _) = committed
    original = objects.verify_tree
    entered, release, second_called = (threading.Event() for _ in range(3))
    calls = []

    def fail(*args, **kwargs):
        calls.append(threading.get_ident())
        entered.set()
        assert release.wait(5), 'fixture was not released'
        raise ValueError('controlled verification failure')

    def second():
        second_called.set()
        return store.get(identity)

    monkeypatch.setattr(objects, 'verify_tree', fail)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(store.get, identity)
        try:
            assert entered.wait(2)
            later = pool.submit(second)
            assert second_called.wait(2)
        finally:
            release.set()
        for result in (first, later):
            with pytest.raises(ValueError, match='controlled verification failure'):
                result.result(timeout=5)
    assert len(calls) == 2
    assert not store.verification_locks
    monkeypatch.setattr(objects, 'verify_tree', original)
    store.get(identity)
    assert not store.verification_locks
