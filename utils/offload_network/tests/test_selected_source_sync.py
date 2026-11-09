"""A bounded source watcher must not enter an unrelated long admission."""
from copy import deepcopy

import pytest

from research_workflows.cli import parser
from research_workflows.project_queue import ProjectQueue
from tests.test_project_return import api, project, worker
from tests.test_research_workflows import compiled, drive


def enqueue_two(tmp_path, worker, config, origins):
    identities = ("long-admission", "small-independent")
    for identity in identities:
        root = tmp_path/identity; root.mkdir()
        _, directory = compiled(root, worker, edit=lambda raw, identity=identity:
            raw.update(submission_id=identity, return_policy={"include_inputs": True}))
        with ProjectQueue(config) as queue:
            queue.enqueue(directory, "local", origins)
    return identities


def test_selected_reconciliation_admits_and_returns_only_selected_workflow(tmp_path, worker, project, monkeypatch):
    config, origins = project
    first, second = enqueue_two(tmp_path, worker, config, origins)
    poll = ProjectQueue._poll_remote
    seen = []

    def reject_unrelated(self, row, *args):
        assert row["id"] == second, "unrelated slow admission was contacted"
        seen.append(row["id"])
        return poll(self, row, *args)

    monkeypatch.setattr(ProjectQueue, "_poll_remote", reject_unrelated)
    with ProjectQueue(config) as queue:
        untouched = deepcopy(queue._row(first))
        queue.sync(now=True, workflows=[second])
        assert queue._row(first) == untouched
    assert drive(worker, submission=second)["state"] == "completed"
    with ProjectQueue(config) as reopened:
        rows = reopened.sync(now=True, workflows=[second])
        assert reopened._row(first) == untouched
        assert reopened._row(second)["phase"] == "completed"
        assert len(next(row for row in rows if row["workflow_id"] == second)["publications"]) == 3
        assert reopened.sync(workflows=[]) == reopened.status()
    assert set(seen) == {second}
    assert [row[0] for row in worker.db.execute("SELECT id FROM workflows")] == [second]


def test_invalid_selection_rejected_before_any_remote_or_local_mutation(tmp_path, worker, project, monkeypatch):
    config, origins = project
    first, second = enqueue_two(tmp_path, worker, config, origins)
    monkeypatch.setattr(ProjectQueue, "_poll_remote", lambda *args: pytest.fail("invalid selector reached remote"))
    with ProjectQueue(config) as queue:
        before = [deepcopy(queue._row(key)) for key in (first, second)]
        for invalid in (second, [second, second], [second, "missing-workflow"], [True], {second}):
            with pytest.raises((ValueError, KeyError)):
                queue.sync(workflows=invalid)
            assert [queue._row(key) for key in (first, second)] == before


def test_cli_accepts_repeated_workflow_selector():
    args = parser().parse_args(["sync", "--config", "project.json", "--watch",
        "--workflow", "one", "--workflow", "two"])
    assert args.workflow == ["one", "two"]
