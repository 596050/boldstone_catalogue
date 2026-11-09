"""Independent candidate batches, using synthetic data and native testing stages."""

import os
import threading
from copy import deepcopy
from pathlib import Path

import pytest

from offload_service.http_api import Server
from research_workflows import batch
from research_workflows.capsule import research_selection, snapshot
from research_workflows.client import Client, verify_collection
from research_workflows.common import atomic, load, sha
from research_workflows.planner import plan
from research_workflows.simulation import configuration
from research_workflows.spec import validate
from research_workflows.worker import WorkflowWorker


def request():
    return {
        "schema": batch.SCHEMA,
        "submission_id": "batch-unit",
        "defaults": {
            "runtime": "python",
            "capsule": "a" * 64,
            "args": ["--data", "{input.data}/cases.jsonl"],
            "inputs": {"data": {"mode": "source_ref", "source": "raw"}},
        },
        "data_sources": {"raw": {"mode": "bundle", "object_sha256": "b" * 64}},
        "candidates": [{"id": "alpha", "model": "alpha.py"}, {"id": "beta", "model": "beta.py"}],
    }


def test_batch_expands_to_independent_single_model_jobs():
    raw = request()
    raw["candidates"][1]["resources"] = {"cpus": 0.5}
    spec = validate(batch.expand(raw))
    assert len(spec["jobs"]) == 2
    assert spec["jobs"][0]["args"][:2] == ["--model", "alpha.py"]
    assert spec["jobs"][1]["args"][:2] == ["--model", "beta.py"]
    assert spec["jobs"][0]["inputs"]["data"] == {"mode": "bundle", "object_sha256": "b" * 64}
    assert spec["jobs"][1]["resources"]["cpus"] == 0.5
    assert all(not j["depends_on"] for j in spec["jobs"])
    assert validate(spec) == spec
    assert raw["defaults"]["inputs"]["data"]["mode"] == "source_ref"


@pytest.mark.parametrize(
    "change",
    [
        lambda r: r["candidates"].append(deepcopy(r["candidates"][0])),
        lambda r: r["candidates"][0].update(model="/Users/source/model.py"),
        lambda r: r["defaults"].update(args=["--model", "hidden.py"]),
        lambda r: r["defaults"].update(args=["--model-list", "hidden.json"]),
        lambda r: r["defaults"].update(args=["--model-li=hidden.json"]),
        lambda r: r["defaults"].update(args=["--data", "C:\\data\\raw.csv"]),
        lambda r: r["defaults"]["inputs"]["data"].update(source="missing"),
        lambda r: r["defaults"].update(unknown=True),
    ],
)
def test_invalid_batch_contracts_are_rejected(change):
    raw = request()
    change(raw)
    with pytest.raises(ValueError):
        validate(batch.expand(raw))


def test_subset_does_not_broaden_authorized_source_selection():
    raw = request()
    raw["data_sources"]["raw"] = {"mode": "bundle", "source": "raw", "include": ["gold"]}
    raw["candidates"][0]["inputs"] = {
        "data": {"mode": "source_ref", "source": "raw", "include": ["oil.csv"]}
    }
    with pytest.raises(ValueError, match="broadens"):
        batch.expand(raw)
    raw["candidates"][0]["inputs"]["data"]["include"] = ["gold/minute.csv"]
    assert batch.expand(raw)["jobs"][0]["inputs"]["data"]["include"] == ["gold/minute.csv"]


def test_cross_candidate_dependencies_and_false_rosters_are_rejected():
    raw = request()
    raw["candidates"][1]["inputs"] = {
        "data": {"mode": "artifact_ref", "job": "alpha", "output": "research_evidence"}
    }
    with pytest.raises(ValueError, match="another candidate"):
        validate(batch.expand(raw))
    spec = validate(batch.expand(request()))
    spec["batch"]["candidates"][1]["model"] = "wrong.py"
    with pytest.raises(ValueError, match="invocation"):
        validate(spec)


def test_indirect_cross_candidate_dependency_cannot_hide_in_a_shared_producer():
    raw = request()
    raw["jobs"] = [
        {
            "id": "shared",
            "kind": "producer",
            "runtime": "python",
            "capsule": "a" * 64,
            "entrypoint": "main.py",
            "inputs": {
                "data": {"mode": "artifact_ref", "job": "alpha", "output": "research_evidence"}
            },
            "outputs": {"data": {"type": "tree", "path": "artifacts/data"}},
        }
    ]
    raw["candidates"][1]["inputs"] = {
        "data": {"mode": "artifact_ref", "job": "shared", "output": "data"}
    }
    with pytest.raises(ValueError, match="another candidate"):
        validate(batch.expand(raw))


def test_bundled_example_and_local_roster_tampering(tmp_path):
    example = Path(__file__).resolve().parents[1] / "research_workflows/examples/batch/request.json"
    raw = load(example)
    raw["defaults"]["capsule"] = "a" * 64
    result = plan(raw, tmp_path / "compiled", base=example.parent)
    assert result["independent_candidates"] == 2
    spec = load(tmp_path / "compiled/WORKFLOW.json")
    assert len(spec["jobs"]) == 6
    candidate = next(j for j in spec["jobs"] if j["id"] == "candidate-a")
    assert set(candidate["depends_on"]) == {"candidate-a--select", "candidate-a--cases"}
    assert candidate["inputs"]["prepared"]["job"] == "candidate-a--cases"
    roster = load(tmp_path / "compiled/BATCH_PLAN.json")
    roster["candidates"][0]["id"] = "tampered"
    atomic(tmp_path / "compiled/BATCH_PLAN.json", roster)
    with pytest.raises(ValueError, match="compiled candidate roster changed"):
        Client("http://127.0.0.1:1", "t" * 43).submit_plan(tmp_path / "compiled")


def test_partial_candidate_result_roster_keeps_every_candidate():
    spec = validate(batch.expand(request()))
    manifest = {
        "workflow": spec,
        "final": False,
        "status": {
            "workflow_id": "batch-unit",
            "workflow_sha256": "c" * 64,
            "nodes": [
                {"id": j["id"], "outputs": None, "state": "waiting", "attempt": 0, "error": None}
                for j in spec["jobs"]
            ],
        },
    }
    results = batch.candidate_results(manifest, {})
    assert results["final"] is False
    assert {c["id"]: c["state"] for c in results["candidates"]} == {
        "alpha": "waiting",
        "beta": "waiting",
    }
    assert all(c["native_result"] is None for c in results["candidates"])


def test_shared_sources_pack_once_without_importing_candidates(tmp_path, monkeypatch):
    from research_workflows import planner

    code = tmp_path / "code"
    code.mkdir()
    (code / "main.py").write_text("raise RuntimeError('never import during planning')\n")
    data = tmp_path / "data"
    data.mkdir()
    (data / "cases.jsonl").write_text('{"input":1,"target":"yes"}\n')
    raw = request()
    raw["defaults"]["capsule"] = {"source": str(code)}
    raw["data_sources"]["raw"] = {"mode": "bundle", "source": str(data)}
    raw["data_sources"]["unused"] = {"mode": "bundle", "source": "/must/not/be/read"}
    calls = []
    original = planner.snapshot

    def counted(*args, **kwargs):
        calls.append(args[0])
        return original(*args, **kwargs)

    monkeypatch.setattr(planner, "snapshot", counted)
    result = plan(raw, tmp_path / "compiled")
    assert len(calls) == 2
    assert len(list((tmp_path / "compiled/objects").glob("*.tar.gz"))) == 2
    assert result["independent_candidates"] == 2
    assert result["plugin_code_executed"] is False
    assert load(tmp_path / "compiled/BATCH_PLAN.json")["schema"] == batch.ROSTER_SCHEMA


def native_fixture(root):
    repo = Path(__file__).resolve().parents[3]
    capsule = root / "capsule"
    capsule.mkdir()
    snapshot(repo, capsule / "repo", include=research_selection(repo), resolve_code_links=True)
    producer = Path(__file__).resolve().parents[1] / "research_workflows/examples/batch"
    models, raw = root / "models", root / "raw"
    models.mkdir()
    raw.mkdir()
    for key, expression in (("good", "'yes'"), ("negative", "'no'"), ("benchmark", "'no'")):
        (models / (key + ".py")).write_text(
            "TESTING_MODEL={'api_version':1,'model_id':" + repr(key) + "}\n"
            "def predict(observation, context):\n    return " + expression + "\n"
        )
    (models / "crash.py").write_text(
        "TESTING_MODEL={'api_version':1,'model_id':'crash'}\n"
        "def predict(observation, context):\n    raise RuntimeError('controlled candidate failure')\n"
    )
    for filename, count in (("one.csv", 100), ("two.csv", 120)):
        (raw / filename).write_text(
            "observation,signal,target\n"
            + "".join(f"{n},yes,{'yes' if n % 10 else 'no'}\n" for n in range(count))
        )
    settings = root / "settings"
    settings.mkdir()
    atomic(
        settings / "criteria.json",
        {
            "schema": "marketmaker.generic_criteria.v1",
            "contract_id": "synthetic_batch_only",
            "metrics": {
                "accuracy": {
                    "rule": "ideal_gap",
                    "direction": "higher",
                    "ideal": 1,
                    "amount": "1/2",
                }
            },
        },
    )
    atomic(
        settings / "statistics.json",
        {
            "schema": "marketmaker.statistical_comparison_config.v1",
            "dependence": "independent_cases",
            "block_length": 1,
            "hac_lags": 0,
            "replications": 199,
            "seed": 94,
            "min_observations": 60,
        },
    )
    result = {
        "schema": batch.SCHEMA,
        "submission_id": "native-candidate-batch",
        "defaults": {
            "runtime": "python",
            "capsule": {"source": str(capsule)},
            "testing": {"through": "statistics"},
            "inputs": {
                "models": {"mode": "bundle", "source": str(models)},
                "settings": {"mode": "bundle", "source": str(settings)},
                "prepared": {"mode": "artifact_ref", "job": "cases", "output": "prepared"},
            },
            "args": [
                "--benchmark",
                "{input.models}/benchmark.py",
                "--data",
                "{input.prepared}/cases.jsonl",
                "--criteria",
                "{input.settings}/criteria.json",
                "--statistics-config",
                "{input.settings}/statistics.json",
                "--seeds",
                "0",
                "1",
                "--checks",
                "--no-early-stop",
            ],
        },
        "data_sources": {"raw": {"mode": "bundle", "source": str(raw)}},
        "candidates": [],
        "return_policy": {"include_inputs": True},
    }
    for key, model, filename in (
        ("bundled", "good", "one.csv"),
        ("registered", "good", "two.csv"),
        ("negative", "negative", "one.csv"),
        ("broken", "crash", "one.csv"),
        ("missing", "good", "absent.csv"),
    ):
        selector = root / (key + "-selector")
        selector.mkdir()
        atomic(selector / "selection.json", {"file": filename})
        result["candidates"].append(
            {
                "id": key,
                "model": "{input.models}/" + model + ".py",
                "prepare": [
                    {
                        "id": "select",
                        "capsule": {"source": str(producer), "include": ["prepare.py"]},
                        "entrypoint": "prepare.py",
                        "inputs": {
                            "raw": {"mode": "source_ref", "source": "raw"},
                            "selection": {"mode": "bundle", "source": str(selector)},
                        },
                        "args": [
                            "select",
                            "{input.raw}",
                            "{input.selection}/selection.json",
                            "{output.selected}",
                        ],
                        "outputs": {
                            "selected": {
                                "type": "tree",
                                "path": "artifacts/selected",
                                "delivery": "remote",
                            }
                        },
                    },
                    {
                        "id": "cases",
                        "capsule": {"source": str(producer), "include": ["prepare.py"]},
                        "entrypoint": "prepare.py",
                        "inputs": {
                            "raw": {"mode": "artifact_ref", "job": "select", "output": "selected"}
                        },
                        "args": ["cases", "{input.raw}", "unused", "{output.prepared}"],
                        "outputs": {"prepared": {"type": "tree", "path": "artifacts/prepared"}},
                    },
                ],
            }
        )
    return result, raw, models


@pytest.mark.parametrize("backend", ["trusted-local", "docker"])
def test_native_batch_offline_independent_results_and_dynamic_data(tmp_path, backend):
    if backend == "docker" and not os.environ.get("OFFLOAD_RESEARCH_TEST_IMAGE"):
        pytest.skip("needs opt-in prebuilt research image")
    if backend == "trusted-local":
        pytest.importorskip("numpy")
        pytest.importorskip("scipy")
    repo = Path(__file__).resolve().parents[3]
    if not (repo / "research/testing_stages/testing.py").is_file():
        pytest.skip("native testing framework is not in this checkout")
    raw_request, data, models = native_fixture(tmp_path)
    config = configuration(os.environ.get("OFFLOAD_RESEARCH_TEST_IMAGE", "python:3.12-slim"))
    config["runtimes"]["python"].update(
        timeout_s=180, memory_mb=1024, max_work_mb=256, max_output_mb=64
    )
    config["capacity"].update(memory_mb=2048, max_work_mb=512)
    config.update(max_object_mb=64, max_store_mb=2048)
    with WorkflowWorker(
        tmp_path / "worker", [], backend=backend, workflow_config=config, min_free_mb=0
    ) as worker:
        remote = worker.workflows.objects.register_dataset("synthetic-raw", "v1", data)
        raw_request["data_sources"]["registered"] = {"mode": "dataset_ref", **remote}
        raw_request["candidates"][1]["prepare"][0]["inputs"]["raw"] = {
            "mode": "source_ref",
            "source": "registered",
        }
        compiled = tmp_path / "compiled"
        plan(raw_request, compiled)
        (data / "one.csv").write_text("changed after snapshot\n")
        (models / "good.py").write_text("raise RuntimeError('changed after snapshot')\n")
        token = "b" * 43
        server = Server(("127.0.0.1", 0), worker, token)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            client = Client(f"http://127.0.0.1:{server.server_port}", token)
            admitted = client.submit_plan(compiled)
            assert not admitted["terminal"]
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
        assert not thread.is_alive()
        for _ in range(100):
            worker.workflows.tick()
            status = worker.workflows.status(raw_request["submission_id"])
            if status["terminal"]:
                break
            worker.process_next()
        assert status["terminal"], status
        nodes = {n["id"]: n for n in status["nodes"]}
        states = {
            key: nodes[key]["state"]
            for key in ("bundled", "registered", "negative", "broken", "missing")
        }
        assert states == {
            "bundled": "succeeded",
            "registered": "succeeded",
            "negative": "succeeded",
            "broken": "failed",
            "missing": "blocked_dependency",
        }, status
        assert nodes["missing--select"]["state"] == "failed"
        assert nodes["negative"]["outputs"]["native_result"]["statistical_verdict"] == "FAILED"
        assert nodes["bundled"]["outputs"]["native_result"]["statistical_verdict"] == "SUPPORTED"
        server = Server(("127.0.0.1", 0), worker, token)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            client = Client(f"http://127.0.0.1:{server.server_port}", token)
            returned = tmp_path / "returned"
            receipt = client.collect(raw_request["submission_id"], returned)
            assert receipt["final"] and receipt["workflow_state"] == "completed_with_errors"
            results = load(returned / "CANDIDATES.json")
            assert {c["id"]: c["state"] for c in results["candidates"]} == states
            assert verify_collection(returned) == receipt
            assert client.collect(raw_request["submission_id"], returned) == receipt
            index = load(returned / "INDEX.json")
            for key, rows in (("bundled", 100), ("registered", 120)):
                evidence = returned / index[key + ".research_evidence"]
                assert (evidence / "METRICS_COMPARISON.csv").is_file()
                assert list(evidence.rglob("observations_*.jsonl"))
                prepared = returned / index[key + "--cases.prepared"]
                assert len((prepared / "cases.jsonl").read_text().splitlines()) == rows
                assert sha(prepared / "raw.csv") == load(prepared / "SOURCE.json")["source_sha256"]
                assert (
                    nodes[key]["outputs"]["input_objects"]["prepared"]
                    == nodes[key + "--cases"]["outputs"]["ports"]["prepared"]["object_sha256"]
                )
            results["candidates"][0]["id"] = "tampered"
            atomic(returned / "CANDIDATES.json", results)
            with pytest.raises(ValueError, match="candidate result index changed"):
                verify_collection(returned)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
        assert not thread.is_alive()
