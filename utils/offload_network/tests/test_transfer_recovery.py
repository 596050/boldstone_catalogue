"""Regression tests for crash-safe uploads, downloads and source collection."""

import errno
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from research_workflows import client as client_module
from research_workflows.common import atomic, load, sha
from research_workflows.objects import ObjectStore, pack
from research_workflows.project_queue import ProjectQueue
from tests.test_project_return import freeze
from tests.test_project_return import project as project_fixture
from tests.test_research_workflows import api as api_fixture
from tests.test_research_workflows import compiled, drive
from tests.test_research_workflows import worker as worker_fixture

api, worker, project = api_fixture, worker_fixture, project_fixture


def archive_fixture(tmp_path):
    source = tmp_path / "data"
    source.mkdir()
    (source / "payload.txt").write_text("audit fixture\n" * 100)
    archive = tmp_path / "object.tar.gz"
    ref = pack(source, archive)
    return archive, ref["object_sha256"]


def store(root):
    return ObjectStore(root, max_object_mb=1, max_store_mb=8, min_free_mb=1)


def test_upload_begin_recovers_after_hard_exit_before_metadata(tmp_path):
    archive, ident = archive_fixture(tmp_path)
    root = tmp_path / "store"
    program = """
import os, sys
from research_workflows import objects
objects.atomic = lambda *args, **kwargs: os._exit(73)
objects.ObjectStore(sys.argv[1], max_object_mb=1, max_store_mb=8, min_free_mb=1).begin(sys.argv[2], int(sys.argv[3]))
"""
    proc = subprocess.run(
        [sys.executable, "-c", program, str(root), ident, str(archive.stat().st_size)],
        check=False, timeout=20,
    )
    assert proc.returncode == 73
    assert (root / "uploads" / (ident + ".part")).is_file()
    # Expected: a new worker reconciles its own empty interrupted upload.
    recovered = store(root).begin(ident, archive.stat().st_size)
    assert recovered["state"] == "uploading" and recovered["offset"] == 0


def test_committed_upload_recovery_removes_only_redundant_staging(tmp_path):
    archive, ident = archive_fixture(tmp_path)
    root = tmp_path / "store"
    target = store(root)
    target.begin(ident, archive.stat().st_size)
    target.append(ident, 0, archive.read_bytes())
    program = """
import os, sys
from pathlib import Path
from research_workflows import objects
original = objects.sync_directory
def crash(path):
    if Path(path) == Path(sys.argv[1]) / 'objects':
        os._exit(74)
    original(path)
objects.sync_directory = crash
objects.ObjectStore(sys.argv[1], max_object_mb=1, max_store_mb=8, min_free_mb=1).commit(sys.argv[2])
"""
    proc = subprocess.run(
        [sys.executable, "-c", program, str(root), ident], check=False, timeout=20,
    )
    assert proc.returncode == 74
    restarted = store(root)
    assert restarted.commit(ident)["state"] == "committed"
    assert sha(restarted.directory(ident) / "archive.tar.gz") == ident
    # Expected: idempotent commit finishes the interrupted cleanup.
    assert not (root / "uploads" / (ident + ".part")).exists()
    assert not (root / "uploads" / (ident + ".json")).exists()


def test_download_disk_full_preserves_verified_archive_for_retry(tmp_path, api, worker, monkeypatch):
    archive, ident = archive_fixture(tmp_path)
    target = worker.workflows.objects
    target.begin(ident, archive.stat().st_size)
    target.append(ident, 0, archive.read_bytes())
    target.commit(ident)
    output = tmp_path / "downloads"
    original = client_module.atomic

    def disk_full(path, value):
        if Path(path).name == "RECEIVED.json":
            raise OSError(errno.ENOSPC, "synthetic metadata disk full after download")
        return original(path, value)

    monkeypatch.setattr(client_module, "atomic", disk_full)
    with pytest.raises(OSError, match="synthetic metadata disk full"):
        api.download_object(ident, output, archive_only=True)
    assert target.status(ident)["state"] == "committed"  # remote evidence survives
    # Expected: retry does not need another payload transfer after full download.
    assert (output / (ident + ".part")).is_file()
    assert sha(output / (ident + ".part")) == ident
    monkeypatch.setattr(client_module, "atomic", original)
    open_response = api.open

    def no_payload(path, *args, **kwargs):
        assert not path.endswith("/archive"), "completed payload must not be downloaded twice"
        return open_response(path, *args, **kwargs)

    monkeypatch.setattr(api, "open", no_payload)
    received = api.download_object(ident, output, archive_only=True)
    assert sha(received / "archive.tar.gz") == ident
    assert not (output / (ident + ".part")).exists()


@pytest.mark.parametrize("after_move", [False, True])
def test_abrupt_download_finalization_recovers_without_payload_or_orphan_copies(
    tmp_path, api, worker, monkeypatch, after_move
):
    archive, ident = archive_fixture(tmp_path)
    target = worker.workflows.objects
    target.begin(ident, archive.stat().st_size)
    target.append(ident, 0, archive.read_bytes())
    target.commit(ident)
    output = tmp_path / "downloads"
    program = """
import os, sys
from pathlib import Path
from research_workflows import client
if sys.argv[5] == 'True':
    original = client.os.replace
    def crash(source, target):
        original(source, target)
        if Path(target).name == 'archive.tar.gz':
            os._exit(75)
    client.os.replace = crash
else:
    client.sync_tree = lambda *args: os._exit(75)
client.Client(sys.argv[1], sys.argv[2]).download_object(sys.argv[3], Path(sys.argv[4]), archive_only=True)
"""
    result = subprocess.run(
        [sys.executable, "-c", program, api.url, api.token, ident, str(output), str(after_move)],
        check=False, timeout=20,
    )
    assert result.returncode == 75
    stage = output / ("." + ident + ".receiving")
    assert stage.is_dir()
    open_response = api.open

    def no_payload(path, *args, **kwargs):
        assert not path.endswith("/archive")
        if after_move:
            pytest.fail("fully verified staging must recover without a remote connection")
        return open_response(path, *args, **kwargs)

    monkeypatch.setattr(api, "open", no_payload)
    recovered = api.download_object(ident, output, archive_only=True)
    assert sha(recovered / "archive.tar.gz") == ident
    assert {p.name for p in output.iterdir()} == {ident}


def test_unbound_nonempty_upload_is_retained_not_adopted(tmp_path):
    from offload_service.core import Conflict

    archive, ident = archive_fixture(tmp_path)
    target = store(tmp_path / "store")
    part = target.root / "uploads" / (ident + ".part")
    part.write_bytes(b"ambiguous bytes")
    with pytest.raises(Conflict, match="unbound nonempty"):
        target.begin(ident, archive.stat().st_size)
    assert part.read_bytes() == b"ambiguous bytes"
    assert not part.with_suffix(".json").exists()


def test_corrupt_redundant_upload_is_retained_for_inspection(tmp_path):
    archive, ident = archive_fixture(tmp_path)
    target = store(tmp_path / "store")
    target.begin(ident, archive.stat().st_size)
    target.append(ident, 0, archive.read_bytes())
    target.commit(ident)
    part = target.root / "uploads" / (ident + ".part")
    part.write_bytes(b"corrupt staging")
    with pytest.raises(ValueError, match="staging changed"):
        target.commit(ident)
    assert part.read_bytes() == b"corrupt staging"
    assert sha(target.get(ident)[0] / "archive.tar.gz") == ident


def test_compressed_collection_uses_retained_storage_not_expanded_size(tmp_path, worker, project):
    config, origins = project

    def enlarge_capsule(raw):
        code = Path(raw["jobs"][0]["capsule"]["source"])
        (code / "unused_fixture.txt").write_text("a" * (3 << 20))
        raw["return_policy"] = {"include_inputs": True}

    spec, directory = compiled(tmp_path, worker, edit=enlarge_capsule)
    settings = load(config)
    settings["storage"]["max_store_mb"] = 2
    atomic(config, settings)
    with ProjectQueue(config) as queue:
        queue.enqueue(directory, "local", origins)
        queue.sync(now=True)
    assert drive(worker)["state"] == "completed"
    delivery = worker.workflows.delivery(spec["submission_id"])
    identities = set(delivery["manifest"]["objects"].values())
    archives = sum(worker.workflows.objects.status(i)["bytes"] for i in identities)
    assert archives < (100 << 10)  # all actual retained payloads fit comfortably
    with ProjectQueue(config) as queue:
        result = queue.sync(now=True)[0]
        assert result["phase"] == "completed", result


def test_transient_collection_free_space_does_not_need_manual_attention(
    tmp_path, worker, project, monkeypatch
):
    config, origins = project
    _, directory = freeze(tmp_path, worker)
    with ProjectQueue(config) as queue:
        queue.enqueue(directory, "local", origins)
        queue.sync(now=True)
    assert drive(worker)["state"] == "completed"
    original = shutil.disk_usage

    def low_free(path):
        actual = original(path)
        return type(actual)(actual.total, actual.total - (8 << 20), 8 << 20)

    with monkeypatch.context() as patcher:
        patcher.setattr(shutil, "disk_usage", low_free)
        with ProjectQueue(config) as queue:
            held = queue.sync(now=True)[0]
    assert "free-space budget" in held["error"]
    with ProjectQueue(config) as queue:
        # Physical free space is restored; ordinary sync should retry the transfer.
        recovered = queue.sync(now=True)[0]
        assert recovered["phase"] == "completed", recovered
