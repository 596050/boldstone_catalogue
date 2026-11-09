"""A created workspace still needs space for its declared future writes."""
from types import SimpleNamespace

import pytest

from offload_service import core
from offload_service.core import Template, Worker
from research_workflows.simulation import configuration
from research_workflows.worker import WorkflowWorker


@pytest.mark.parametrize("worker_class", [Worker, WorkflowWorker])
@pytest.mark.parametrize("written_bytes", [0, 4096])
def test_running_workspace_creation_does_not_release_future_growth(
    tmp_path, monkeypatch, worker_class, written_bytes
):
    code = tmp_path / "code"
    code.mkdir()
    script = code / "job.py"
    script.write_text("from pathlib import Path\nPath('result.txt').write_text('result')\n")
    template = Template("growth", script, code_dir=code, max_work_mb=8, max_output_mb=2)
    options = {"backend": "trusted-local", "min_free_mb": 16, "concurrency": 2}
    if worker_class is WorkflowWorker:
        config = configuration()
        config["runtimes"]["python"]["max_work_mb"] = 8
        config["capacity"]["max_work_mb"] = 16
        options["workflow_config"] = config
    with worker_class(tmp_path / "worker", [template], **options) as worker:
        worker.submit({"job_id": "growing-job", "template": "growth", "args": []})
        first = worker._claim()
        assert first is not None
        workspace = worker.root / "work" / first[1]
        workspace.mkdir()
        if written_bytes:
            (workspace / "initial-output").write_bytes(b"x" * written_bytes)
        worker.submit({"job_id": "waiting-job", "template": "growth", "args": []})
        before = dict(worker.db.execute("SELECT * FROM jobs WHERE id='waiting-job'").fetchone())
        # Both jobs may still write almost 8 MiB. Admitting the second with
        # 28 MiB free would leave about 12 MiB, below the retained 16 MiB reserve.
        monkeypatch.setattr(core.shutil, "disk_usage", lambda _: SimpleNamespace(free=28 << 20))
        assert worker._claim() is None
        after = dict(worker.db.execute("SELECT * FROM jobs WHERE id='waiting-job'").fetchone())
        assert after == before
        running = worker.db.execute("SELECT state,attempt FROM jobs WHERE id='growing-job'").fetchone()
        assert tuple(running) == ("running", first[1])
        assert not (worker.root / "work" / "waiting-job").exists()
