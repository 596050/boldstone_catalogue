"""Competing source copies must preserve exact archives and queue identities."""
import errno
import json
import threading
from pathlib import Path

import pytest

from lib.file_lock import file_lock
from research_workflows.common import sha
import research_workflows.project_queue as pq
from research_workflows.project_queue import ProjectQueue
from tests.test_project_return import project as project_fixture
from tests.test_research_workflows import api as api_fixture, worker as worker_fixture, compiled
from tests.test_source_sync_concurrency import freeze_at

project, api, worker = project_fixture, api_fixture, worker_fixture


@pytest.mark.parametrize("same_workflow", [False, True])
def test_competing_enqueues_keep_first_published_archive(
    tmp_path, worker, project, monkeypatch, same_workflow
):
    config, origins = project
    _, first = freeze_at(tmp_path / "first", worker, "first-copy")
    _, second = freeze_at(tmp_path / "second", worker, "second-copy")
    if same_workflow:
        second = first
    objects = sorted(p.name for p in (first / "objects").glob("*.tar.gz"))
    assert objects == sorted(p.name for p in (second / "objects").glob("*.tar.gz"))
    ident = objects[0].removesuffix(".tar.gz")
    entered, release = threading.Event(), threading.Event()
    copy = pq.shutil.copyfileobj
    errors, results = [], []

    def paused(incoming, output, *args):
        if threading.current_thread().name == "first-outbox-copy" and Path(incoming.name).stem.startswith(ident):
            entered.set()
            assert release.wait(15), "competing enqueue did not release first copy"
        return copy(incoming, output, *args)

    def enqueue_first():
        try:
            with ProjectQueue(config) as queue:
                results.append(queue.enqueue_receipt(first, "local", origins, lock_timeout=5))
        except BaseException as error:
            errors.append(error)

    monkeypatch.setattr(pq.shutil, "copyfileobj", paused)
    thread = threading.Thread(target=enqueue_first, name="first-outbox-copy", daemon=True)
    thread.start()
    try:
        assert entered.wait(10), "first copy did not enter the declared interleaving"
        with ProjectQueue(config) as queue:
            result = queue.enqueue_receipt(second, "local", origins, lock_timeout=5)
            assert result["queue_acknowledged"] is True
            target = queue.project.bulk() / "outbox" / objects[0]
            before = target.stat()
            assert sha(target) == ident
    finally:
        release.set()
        thread.join(timeout=15)
    assert not thread.is_alive()
    assert not errors, repr(errors)
    assert results[0]["queue_acknowledged"] is True
    after = target.stat()
    assert (before.st_ino, before.st_size, before.st_mtime_ns) == (after.st_ino, after.st_size, after.st_mtime_ns)
    assert sha(target) == ident
    assert not list(target.parent.glob("*.copying"))
    with ProjectQueue(config) as queue:
        assert len(queue.status()) == (1 if same_workflow else 2)
        assert queue.enqueue_receipt(second, "local", origins) == result
        for row in queue.db.execute("SELECT objects FROM requests"):
            assert all(sha(target.parent / (obj + ".tar.gz")) == obj for obj in json.loads(row["objects"]))


def test_different_object_enqueue_finishes_while_copy_is_paused(tmp_path, worker, project, monkeypatch):
    config, origins = project
    first_spec, first = freeze_at(tmp_path / "first", worker, "slow-object")
    other = tmp_path / "other"
    other.mkdir()

    def edit(raw):
        (other / "code/job.py").write_text((other / "code/job.py").read_text() + "\n# distinct capsule\n")
        raw.update(submission_id="independent-object", return_policy={"include_inputs": True})

    second_spec, second = compiled(other, worker, edit=edit)
    ident = first_spec["jobs"][0]["capsule"]
    assert second_spec["jobs"][0]["capsule"] != ident
    entered, release = threading.Event(), threading.Event()
    original, errors = pq.shutil.copyfileobj, []

    def paused(incoming, output, *args):
        if Path(incoming.name).name == ident + ".tar.gz":
            entered.set()
            assert release.wait(15)
        return original(incoming, output, *args)

    def slow():
        try:
            with ProjectQueue(config) as queue:
                queue.enqueue_receipt(first, "local", origins, lock_timeout=5)
        except BaseException as error:
            errors.append(error)

    monkeypatch.setattr(pq.shutil, "copyfileobj", paused)
    thread = threading.Thread(target=slow, daemon=True)
    thread.start()
    try:
        assert entered.wait(10)
        with ProjectQueue(config) as queue:
            with file_lock(queue.root / "queue.lock", timeout=0):
                pass
            assert queue.enqueue_receipt(second, "local", origins)["queue_acknowledged"] is True
    finally:
        release.set()
        thread.join(timeout=15)
    assert not thread.is_alive() and not errors


@pytest.mark.parametrize("failure", ["interrupted", "corrupt"])
def test_failed_copy_stays_inspectable_and_does_not_poison_retry(tmp_path, worker, project, monkeypatch, failure):
    config, origins = project
    _, directory = freeze_at(tmp_path / "source", worker, "copy-failure")
    original = pq.shutil.copyfileobj

    def faulty(incoming, output, *args):
        output.write(b"failed-copy-bytes")
        if failure == "interrupted":
            raise OSError(errno.ENOSPC, "synthetic interrupted copy")

    monkeypatch.setattr(pq.shutil, "copyfileobj", faulty)
    with ProjectQueue(config) as queue:
        with pytest.raises((OSError, ValueError), match="synthetic interrupted|copy changed"):
            queue.enqueue(directory, "local", origins)
        assert queue.status() == []
        cache = queue.project.bulk() / "outbox"
        failed = {p: sha(p) for p in cache.glob("*.copying")}
        assert len(failed) == 1 and not list(cache.glob("*.tar.gz"))
        monkeypatch.setattr(pq.shutil, "copyfileobj", original)
        assert queue.enqueue_receipt(directory, "local", origins)["queue_acknowledged"] is True
        assert {p: sha(p) for p in cache.glob("*.copying")} == failed


@pytest.mark.parametrize("location,kind", [("source", "corrupt"), ("source", "symlink"), ("target", "corrupt"), ("target", "symlink")])
def test_invalid_source_or_retained_target_cannot_be_acknowledged(tmp_path, worker, project, location, kind):
    config, origins = project
    _, directory = freeze_at(tmp_path / "source", worker, "invalid-object")
    source = sorted((directory / "objects").glob("*.tar.gz"))[0]
    with ProjectQueue(config) as queue:
        cache = queue.project.capacity() / "outbox"
        cache.mkdir()
        path = source if location == "source" else cache / source.name
        if kind == "corrupt":
            path.write_bytes(b"corrupt archive")
        else:
            real = tmp_path / "link-target"
            real.write_bytes(source.read_bytes())
            path.unlink(missing_ok=True)
            path.symlink_to(real)
        with pytest.raises(ValueError, match="exact bundled|retained outbox|symlink"):
            queue.enqueue(directory, "local", origins)
        assert queue.status() == []


@pytest.mark.parametrize("kind", ["corrupt", "symlink"])
def test_invalid_competing_publication_is_not_overwritten(tmp_path, worker, project, monkeypatch, kind):
    config, origins = project
    _, directory = freeze_at(tmp_path / "source", worker, "competing-invalid")
    original, injected = pq.shutil.copyfileobj, []

    def competing(incoming, output, *args):
        result = original(incoming, output, *args)
        target = Path(output.name).parent / Path(incoming.name).name
        if not injected:
            if kind == "corrupt":
                target.write_bytes(b"invalid competing archive")
            else:
                target.symlink_to(Path(incoming.name))
            injected.append(target)
        return result

    monkeypatch.setattr(pq.shutil, "copyfileobj", competing)
    with ProjectQueue(config) as queue:
        with pytest.raises(ValueError, match="retained outbox|symlink"):
            queue.enqueue(directory, "local", origins)
        assert queue.status() == []
    assert injected and len(list(injected[0].parent.glob("*.copying"))) == 1
    assert injected[0].is_symlink() if kind == "symlink" else injected[0].read_bytes() == b"invalid competing archive"


def test_outbox_bulk_io_holds_neither_publication_nor_queue_lock(tmp_path, worker, project, monkeypatch):
    config, origins = project
    _, directory = freeze_at(tmp_path / "source", worker, "short-publication-lock")
    original_sha, original_copy, original_sync = pq.sha, pq.shutil.copyfileobj, pq.sync_directory
    checked = set()
    with ProjectQueue(config) as queue:
        cache = queue.project.capacity() / "outbox"

        def check(path, operation):
            if Path(path).parent == cache:
                ident = Path(path).name.split(".")[0]
                with file_lock(queue.root / "outbox-locks" / (ident + ".lock"), timeout=0):
                    with file_lock(queue.root / "queue.lock", timeout=0):
                        checked.add(operation)

        def checked_sha(path):
            check(path, "hash")
            return original_sha(path)

        def checked_copy(incoming, output, *args):
            check(output.name, "copy")
            return original_copy(incoming, output, *args)

        def checked_sync(path):
            if path == cache:
                for target in cache.glob("*.tar.gz"):
                    check(target, "directory-fsync")
            return original_sync(path)

        monkeypatch.setattr(pq, "sha", checked_sha)
        monkeypatch.setattr(pq.shutil, "copyfileobj", checked_copy)
        monkeypatch.setattr(pq, "sync_directory", checked_sync)
        assert queue.enqueue_receipt(directory, "local", origins)["queue_acknowledged"] is True
    assert checked == {"hash", "copy", "directory-fsync"}
