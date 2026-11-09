"""Completed nodes return independently; snapshot retries never chase live state."""
import errno
from copy import deepcopy

import pytest

from research_workflows.client import Client, verify_collection
from research_workflows.common import atomic, load, sha
from research_workflows.project_queue import ProjectQueue
from research_workflows.project_storage import Project
from research_workflows.publication import publish, resolve_record
from lib.file_lock import file_lock
from tests.test_project_return import project as _project, freeze
from tests.test_research_workflows import api as _api, worker as _worker, drive

project, api, worker = _project, _api, _worker


def prepared(tmp_path, worker, project, enabled=True):
    config, origins = project
    raw = load(config)
    raw["recovery"]["collect_completed_nodes"] = enabled
    atomic(config, raw)
    spec, directory = freeze(tmp_path, worker)
    with ProjectQueue(config) as queue:
        queue.enqueue(directory, "local", origins)
        queue.sync(now=True)
    worker.workflows.tick()
    worker.process_next()
    worker.workflows.tick()
    status = worker.workflows.status(spec["submission_id"])
    assert not status["terminal"]
    assert next(n for n in status["nodes"] if n["id"] == "bundle")["state"] == "succeeded"
    return config, spec


def test_partial_return_uses_shared_collection_lock_without_holding_metadata_lock(
    tmp_path, worker, project, monkeypatch
):
    config, spec = prepared(tmp_path, worker, project)
    raw = load(config)
    raw['recovery']['collection_lock_scope'] = 'separate'
    atomic(config, raw)
    collect, calls = Client.collect, []

    def checked(client, *args, **kwargs):
        assert kwargs.get('partial') is True
        with ProjectQueue(config) as queue:
            with pytest.raises(TimeoutError):
                with file_lock(queue.root / 'collection.lock', timeout=0):
                    pass
            with file_lock(queue.root / 'queue.lock', timeout=0):
                pass
        calls.append(True)
        return collect(client, *args, **kwargs)

    monkeypatch.setattr(Client, 'collect', checked)
    with ProjectQueue(config) as queue:
        result = queue.sync(now=True)[0]
        assert result['phase'] == 'remote' and result['publications']
    assert calls == [True]
    assert worker.db.execute('SELECT COUNT(*) FROM workflow_deliveries WHERE acknowledged IS NOT NULL').fetchone()[0] == 0


def test_finished_node_is_published_before_sibling_and_final_reuses_objects(tmp_path, worker, project):
    config, spec = prepared(tmp_path, worker, project)
    with ProjectQueue(config) as queue:
        state = queue.sync(now=True)[0]
        assert state["phase"] == "remote" and len(state["publications"]) == 2
        original = {path: sha(queue.project.root/path/"RUN_RESULT.json") for path in state["publications"]}
        for path in original:
            record = load(queue.project.root/path/"RUN_RESULT.json")
            assert record["node"]["id"] == "bundle" and record["node"]["state"] == "succeeded"
            assert record["collection_scope"] == "terminal_nodes_of_incomplete_workflow"
            assert not verify_collection(queue.project.bulk()/record["evidence"]["collection_relative"])["final"]
            resolved = resolve_record(queue.project, queue.project.root/path, "bundle.__input_values__", "values.json")
            assert load(resolved)["values"] == [2, 3, 5]
        initial_objects = {p.name: sha(p/"archive.tar.gz") for p in (queue.project.bulk()/"objects").iterdir() if p.is_dir()}
        assert queue.sync(now=True)[0]["publications"] == state["publications"]
        assert queue.db.execute("SELECT COUNT(*) FROM partial_deliveries").fetchone()[0] == 1
    assert worker.db.execute("SELECT COUNT(*) FROM workflow_deliveries WHERE acknowledged IS NOT NULL").fetchone()[0] == 0
    assert drive(worker)["terminal"]
    with ProjectQueue(config) as queue:
        state = queue.sync(now=True)[0]
        assert state["phase"] == "completed" and len(state["publications"]) == 5
        assert {path: sha(queue.project.root/path/"RUN_RESULT.json") for path in original} == original
        for key, value in initial_objects.items():
            assert sha(queue.project.bulk()/"objects"/key/"archive.tar.gz") == value
        assert all(not (p/"data").exists() for p in (queue.project.bulk()/"objects").iterdir() if p.is_dir())
    assert worker.db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 4
    assert worker.db.execute("SELECT COUNT(*) FROM workflow_deliveries WHERE acknowledged IS NOT NULL").fetchone()[0] == 1


def test_disabled_partial_policy_preserves_final_only_behavior(tmp_path, worker, project):
    config, _ = prepared(tmp_path, worker, project, enabled=False)
    with ProjectQueue(config) as queue:
        state = queue.sync(now=True)[0]
        assert state["phase"] == "remote" and state["publications"] == []
        assert queue.db.execute("SELECT COUNT(*) FROM partial_deliveries").fetchone()[0] == 0


def test_partial_download_restart_uses_pinned_snapshot_after_worker_finishes(tmp_path, worker, project, monkeypatch):
    config, _ = prepared(tmp_path, worker, project)
    download = Client.download_object
    first = []

    def interrupt(self, *args, **kwargs):
        if not first:
            first.append(True)
            raise ConnectionResetError("synthetic partial-object connection interruption")
        return download(self, *args, **kwargs)

    monkeypatch.setattr(Client, "download_object", interrupt)
    with ProjectQueue(config) as queue:
        state = queue.sync(now=True)[0]
        assert state["phase"] == "remote" and state["transport_failures"] == 1 and not state["publications"]
        pinned = queue.db.execute("SELECT digest FROM partial_deliveries").fetchone()[0]
    drive(worker)
    monkeypatch.setattr(Client, "download_object", download)
    with ProjectQueue(config) as queue:
        state = queue.sync(now=True)[0]
        assert state["phase"] == "remote" and len(state["publications"]) == 2
        assert all(path.endswith(pinned) for path in state["publications"])
        assert state["transport_failures"] == 0
        assert queue.sync(now=True)[0]["phase"] == "completed"


def test_partial_publication_crash_resumes_without_overwriting(tmp_path, worker, project, monkeypatch):
    from research_workflows import project_queue
    config, _ = prepared(tmp_path, worker, project)
    first = []

    def crash(*args, **kwargs):
        paths = publish(*args, **kwargs)
        if not first:
            first.append(True)
            raise OSError(errno.ENOSPC, "synthetic crash after origin publication before queue commit")
        return paths

    monkeypatch.setattr(project_queue, "publish", crash)
    with ProjectQueue(config) as queue:
        state = queue.sync(now=True)[0]
        assert state["transport_failures"] == 1 and state["phase"] == "remote"
        files = list(queue.project.root.glob("research/candidates/*/*/offload_runs/*/*/*/RUN_RESULT.json"))
        before = {p: sha(p) for p in files}
        assert len(before) == 2
    with ProjectQueue(config) as queue:
        state = queue.sync(now=True)[0]
        assert len(state["publications"]) == 2 and state["transport_failures"] == 0
        assert {p: sha(p) for p in before} == before
    assert worker.db.execute("SELECT COUNT(*) FROM workflow_deliveries WHERE acknowledged IS NOT NULL").fetchone()[0] == 0


def test_corrupt_pinned_snapshot_is_rejected_before_download(tmp_path, worker, api):
    from tests.test_research_workflows import compiled
    spec, directory = compiled(tmp_path, worker)
    api.submit_plan(directory)
    delivery = api.request("/v2/workflows/"+spec["submission_id"]+"/snapshot")
    bad = deepcopy(delivery)
    bad["manifest"]["final"] = not bad["manifest"]["final"]
    with pytest.raises(ValueError, match="invalid pinned"):
        api.collect(spec["submission_id"], tmp_path/"must-not-exist", partial=True, expected_delivery=bad)
    assert not (tmp_path/"must-not-exist").exists()


def test_partial_config_is_explicit_boolean(project):
    config, _ = project
    value = load(config)
    value["recovery"]["collect_completed_nodes"] = 1
    atomic(config, value)
    with pytest.raises(ValueError, match="collect_completed_nodes must be boolean"):
        Project(config)


def test_failed_and_blocked_nodes_are_retained_without_publishing_live_ancestors(tmp_path, worker, project):
    from tests.test_research_workflows import compiled
    config, origins = project
    raw = load(config); raw["recovery"]["collect_completed_nodes"] = True
    atomic(config, raw)
    spec, directory = compiled(tmp_path, worker, edit=lambda value: (
        value.update(return_policy={"include_inputs": True}),
        value["jobs"][0].update(args=["deliberate-unknown-command"])))
    with ProjectQueue(config) as queue:
        queue.enqueue(directory, "local", origins)
        queue.sync(now=True)
    worker.workflows.tick(); worker.process_next(); worker.workflows.tick()
    with ProjectQueue(config) as queue:
        state = queue.sync(now=True)[0]
        assert state["phase"] == "remote" and len(state["publications"]) == 2
        for relative in state["publications"]:
            record = load(queue.project.root/relative/"RUN_RESULT.json")
            assert record["node"]["id"] == "bundle" and record["node"]["state"] == "failed"
    assert drive(worker)["state"] == "completed_with_errors"
    with ProjectQueue(config) as queue:
        state = queue.sync(now=True)[0]
        assert state["phase"] == "completed"
        assert any(load(queue.project.root/p/"RUN_RESULT.json")["node"]["state"] == "blocked_dependency" for p in state["publications"])


def test_frontier_keeps_exhausted_interruption_and_dependency_failure():
    status = {"nodes": [{"id": "running", "state": "running"},
        {"id": "blocked", "state": "blocked_dependency"}, {"id": "stopped", "state": "interrupted"}]}
    assert [n["id"] for n in ProjectQueue._frontier(status)] == ["blocked", "stopped"]
