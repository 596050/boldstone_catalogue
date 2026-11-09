"""Small verified returns must fit without reserving a runtime's worst case."""

import io
import tarfile

import pytest

from lib.live_files import live_tree_bytes
from tests.test_research_workflows import compiled, drive, worker as worker_fixture
from v2.safe_archive import expansion_budget, extract_tar, open_archive

worker = worker_fixture


def completed_execution(tmp_path, worker):
    spec, _ = compiled(tmp_path, worker)
    worker.workflows.submit(spec)
    worker.workflows.tick()
    assert worker.process_next()
    first = worker.db.execute("SELECT id,attempt,state FROM jobs ORDER BY sequence LIMIT 1").fetchone()
    assert first["state"] == "succeeded"
    return spec, dict(first)


def test_small_returns_and_dependencies_fit_below_maximum_output_reservation(tmp_path, worker):
    spec, first = completed_execution(tmp_path, worker)
    store = worker.workflows.objects
    # Plenty for these real tiny outputs; less than the runtime's maximum
    # allowance. No capacity method or archive inspection is mocked.
    store.max_store = live_tree_bytes(store.root) + (8 << 20)
    result = drive(worker, spec["submission_id"])
    assert result["state"] == "completed"
    assert all(node["state"] == "succeeded" for node in result["nodes"])
    current = worker.db.execute("SELECT attempt FROM jobs WHERE id=?", (first["id"],)).fetchone()
    assert current["attempt"] == first["attempt"]
    assert live_tree_bytes(store.root) <= store.max_store


def test_real_capacity_failure_preserves_completed_execution_for_publication_retry(tmp_path, worker):
    spec, first = completed_execution(tmp_path, worker)
    store = worker.workflows.objects
    store.max_store = live_tree_bytes(store.root)
    worker.workflows.tick()
    state = worker.workflows.status(spec["submission_id"])
    node = next(n for n in state["nodes"] if n["job_id"] == first["id"])
    assert node["state"] == "verifying"
    assert node["error"] == "output storage capacity exhausted"
    assert worker.db.execute("SELECT state FROM jobs WHERE id=?", (first["id"],)).fetchone()[0] == "succeeded"
    assert not list(store.root.glob(".publish-*"))
    store.max_store = live_tree_bytes(store.root) + (8 << 20)
    assert drive(worker, spec["submission_id"])["state"] == "completed"
    assert worker.db.execute("SELECT attempt FROM jobs WHERE id=?", (first["id"],)).fetchone()[0] == first["attempt"]


def make_archive(path, entries):
    with tarfile.open(path, "w:gz") as stream:
        for name, body, kind in entries:
            member = tarfile.TarInfo(name)
            member.size, member.type = len(body), kind
            if kind == tarfile.SYMTYPE:
                member.linkname = "outside"
            stream.addfile(member, io.BytesIO(body))


@pytest.mark.parametrize("entries,limits", [
    ([("../escape", b"x", tarfile.REGTYPE)], {}),
    ([("link", b"", tarfile.SYMTYPE)], {}),
    ([("A", b"a", tarfile.REGTYPE), ("a", b"b", tarfile.REGTYPE)], {}),
    ([("compressed", b"x" * (1 << 20), tarfile.REGTYPE)], {"max_bytes": 4096}),
    ([("a", b"a", tarfile.REGTYPE), ("b", b"b", tarfile.REGTYPE)], {"max_members": 1}),
])
def test_sizing_and_extraction_enforce_identical_archive_limits(tmp_path, entries, limits):
    archive = tmp_path / "return.tar.gz"
    make_archive(archive, entries)
    with pytest.raises(ValueError):
        expansion_budget(archive, **limits)
    with open_archive(archive) as stream, pytest.raises(ValueError):
        extract_tar(stream, tmp_path / "extracted", **limits)


def test_observed_expansion_cannot_be_exceeded_by_changed_archive(tmp_path):
    archive = tmp_path / "return.tar.gz"
    make_archive(archive, [("result", b"abc", tarfile.REGTYPE)])
    expanded, members = expansion_budget(archive)
    assert (expanded, members) == (3, 1)
    make_archive(archive, [("result", b"abcd", tarfile.REGTYPE)])
    with open_archive(archive) as stream, pytest.raises(ValueError, match="limits"):
        extract_tar(stream, tmp_path / "extracted", max_bytes=expanded, max_members=members)
