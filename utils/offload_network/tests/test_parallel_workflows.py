"""Measured parallel execution, bounded admission, DAG ordering and two workers.

Real HTTP and isolated subprocess workdirs; trusted-local is not an OS sandbox.
The timestamps are comparable because these simulated remote hosts share one OS.
"""

import json
import threading
import time
from contextlib import ExitStack, contextmanager
from pathlib import Path

import pytest

from offload_service.http_api import Server
from research_workflows.client import Client, collection_objects, verify_collection
from research_workflows.common import atomic, load
from research_workflows.compressed import data_view
from research_workflows.planner import plan
from research_workflows.project_queue import ProjectQueue
from research_workflows.simulation import configuration
from research_workflows.worker import WorkflowWorker

PROGRAM = """import json, os, pathlib, sys, time
from model import predict
node, delay, destination, *sources = sys.argv[1:]
start = time.monotonic_ns()
values = [json.loads(pathlib.Path(p).read_text()) for p in sources]
score = sum(predict(v['value']) for v in values)
time.sleep(float(delay))
pathlib.Path(destination).write_text(json.dumps({
    'schema': 'parallel.fixture.v1', 'node': node, 'value': score,
    'start_ns': start, 'end_ns': time.monotonic_ns(), 'pid': os.getpid(),
    'workdir': str(pathlib.Path.cwd()), 'input_values': [v['value'] for v in values]
}))
"""


def request(root, identity, *, delay="0.6"):
    root.mkdir(parents=True)
    code, data = root / "code", root / "data"
    code.mkdir()
    data.mkdir()
    (code / "job.py").write_text(PROGRAM)
    (code / "model.py").write_text("def predict(value):\n    return value * 2\n")
    atomic(data / "raw.json", {"value": 7})

    def job(node, parents=()):
        inputs = (
            {p: {"mode": "artifact_ref", "job": p, "output": "result"} for p in parents}
            if parents else {"raw": {"mode": "bundle", "source": str(data)}}
        )
        sources = ["{input." + p + "}/result.json" for p in parents] if parents else ["{input.raw}/raw.json"]
        return {
            "id": node, "kind": "producer", "runtime": "python",
            "capsule": {"source": str(code)}, "entrypoint": "job.py",
            "args": [node, "0" if parents else delay, "{output.result}", *sources],
            "inputs": inputs, "depends_on": list(parents),
            "outputs": {"result": {"type": "json", "schema": "parallel.fixture.v1",
                                   "path": "artifacts/result.json"}},
        }

    return {
        "schema": "marketmaker.research_offload_workflow.v1",
        "submission_id": identity,
        "return_policy": {"include_inputs": True},
        "jobs": [job("alpha"), job("beta"), job("gamma"), job("compare", ("alpha", "beta", "gamma"))],
    }


@contextmanager
def host(root, *, slots=2, limits=None):
    config = configuration()
    config["capacity"].update(limits or {})
    with WorkflowWorker(root, [], backend="trusted-local", workflow_config=config,
                        concurrency=slots, min_free_mb=0) as worker:
        server = Server(("127.0.0.1", 0), worker, "parallel-test-" + "s" * 43)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield worker, Client(f"http://127.0.0.1:{server.server_port}", server.token)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
            assert not thread.is_alive()


def terminal(client, identity, worker):
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        state = client.workflow_status(identity)
        if state["terminal"]:
            assert state["state"] == "completed", state
            return state
        assert not worker.stop.is_set(), "worker stopped unexpectedly"
        time.sleep(0.05)
    pytest.fail("parallel fixture exceeded deadline")


def measurements(collection):
    verify_collection(collection, max_bytes=64 << 20)
    manifest = load(collection / "DELIVERY.json")["manifest"]
    objects, _ = collection_objects(collection)
    result = {}
    for node in ("alpha", "beta", "gamma", "compare"):
        with data_view(objects / manifest["objects"][node + ".result"], max_bytes=64 << 20) as view:
            result[node] = load(view / "result.json")
    assert result["compare"]["start_ns"] >= max(result[n]["end_ns"] for n in ("alpha", "beta", "gamma"))
    assert result["compare"]["value"] == 84
    assert len({r["pid"] for r in result.values()}) == 4
    assert len({r["workdir"] for r in result.values()}) == 4
    return result


def peak(rows):
    events = [(r["start_ns"], 1) for r in rows] + [(r["end_ns"], -1) for r in rows]
    active = maximum = 0
    for _, delta in sorted(events):
        active += delta
        maximum = max(maximum, active)
    return maximum


@pytest.mark.parametrize("slots,limits,expected", [
    (2, {}, 2),
    (1, {}, 1),
    (4, {"cpus": 1}, 1),
    (4, {"memory_mb": 512}, 1),
    (4, {"pids": 128}, 1),
    (4, {"max_work_mb": 128}, 1),
])
def test_parallel_jobs_obey_slots_and_aggregate_resources(tmp_path, slots, limits, expected, record_property):
    with host(tmp_path / "worker", slots=slots, limits=limits) as (worker, client):
        compiled = tmp_path / "compiled"
        plan(request(tmp_path / "source", "parallel"), compiled)
        client.submit_plan(compiled)
        # Original data/code may disappear before the source disconnects.
        (tmp_path / "source").rename(tmp_path / "withdrawn-source")
        worker.start()
        terminal(client, "parallel", worker)
        collection = tmp_path / "returned"
        client.collect("parallel", collection)
        result = measurements(collection)
        actual = peak(list(result.values()))
        assert actual == expected
        record_property("observed_peak_jobs", actual)
        record_property("timings", json.dumps(result, sort_keys=True))


def test_two_workers_execute_in_parallel_while_source_is_disconnected_and_return_to_origins(tmp_path, record_property):
    with ExitStack() as stack:
        hosts = [stack.enter_context(host(tmp_path / ("worker-" + str(i)))) for i in range(2)]
        project = tmp_path / "project"
        bulk = tmp_path / "bulk"
        bulk.mkdir()
        settings = load(Path(__file__).parents[1] / "research_workflows/project.json")
        settings.update(project_root=str(project), evidence={"directory": str(bulk), "relative": "offload"})
        settings["storage"].update(min_free_mb=1, local_min_free_mb=1, max_store_mb=128)
        settings["workers"] = {}
        plans, origins = [], []
        for i, (_, client) in enumerate(hosts):
            name = "worker-" + str(i)
            token = tmp_path / (name + ".token")
            token.write_text(client.token)
            settings["workers"][name] = {"url": client.url, "token_file": str(token)}
            origin = project / "research/candidates/parallel" / (name + "_20260911_v1")
            origin.mkdir(parents=True)
            (origin / "README.md").write_text("Original local research record.\n")
            origins.append({node: [origin.relative_to(project).as_posix()] for node in ("alpha", "beta", "gamma", "compare")})
            compiled = tmp_path / ("compiled-" + str(i))
            plan(request(tmp_path / ("source-" + str(i)), name, delay="1.5"), compiled)
            plans.append(compiled)
        config = project / "project.json"
        atomic(config, settings)
        with ProjectQueue(config) as source:
            for i, compiled in enumerate(plans):
                source.enqueue(compiled, "worker-" + str(i), origins[i])
            assert all(r["phase"] == "remote" for r in source.sync(now=True))
        for i, (worker, _) in enumerate(hosts):
            plans[i].rename(tmp_path / ("withdrawn-plan-" + str(i)))
            (tmp_path / ("source-" + str(i))).rename(tmp_path / ("withdrawn-source-" + str(i)))
            worker.start()
        # No ProjectQueue/source process runs while admitted DAGs execute.
        for i, (worker, client) in enumerate(hosts):
            terminal(client, "worker-" + str(i), worker)
        with ProjectQueue(config) as restarted:
            finished = restarted.sync(now=True)
            assert all(r["phase"] == "completed" for r in finished), finished
            assert sum(len(r["publications"]) for r in finished) == 8
            all_measurements = []
            for i, result in enumerate(finished):
                collection = restarted.project.bulk() / "collections" / result["workflow_id"] / result["delivery_sha256"]
                timings = measurements(collection)
                assert peak(list(timings.values())) == 2
                all_measurements.extend(timings.values())
                for path in result["publications"]:
                    record = load(project / path / "RUN_RESULT.json")
                    assert record["binding"]["origins"] == origins[i]
                    assert result["worker"] == "worker-" + str(i)
            assert peak(all_measurements) == 4
            assert all(p.read_text() == "Original local research record.\n" for p in project.glob("research/candidates/*/*/README.md"))
            record_property("observed_peak_jobs_across_workers", 4)
            record_property("origin_records_returned", 8)
            record_property("timings", json.dumps(all_measurements, sort_keys=True))
