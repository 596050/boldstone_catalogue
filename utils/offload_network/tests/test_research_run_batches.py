"""Versioned multi-model runs keep exact candidate/comparator roles and results."""

import os
from copy import deepcopy
from pathlib import Path

import pytest

from research_workflows import batch
from research_workflows.common import atomic, digest, load
from research_workflows.spec import validate


def request():
    return {
        "schema": batch.RUN_SCHEMA,
        "submission_id": "multi-model-batch",
        "defaults": {
            "runtime": "python",
            "capsule": "a" * 64,
            "benchmarks": ["reference.py"],
            "args": ["--checks"],
        },
        "runs": [
            {"id": "group", "models": ["one.py", "two.py"]},
            {"id": "head-to-head", "models": ["two.py"], "benchmarks": ["one.py"]},
            {"id": "reverse", "models": ["one.py"], "benchmarks": ["two.py"]},
            {"id": "standalone", "models": ["one.py"], "benchmarks": []},
        ],
    }


def test_multiple_models_and_arbitrary_per_run_comparators():
    raw = request()
    spec = validate(batch.expand(raw))
    assert spec["jobs"][0]["args"] == [
        "--model",
        "one.py",
        "--model",
        "two.py",
        "--benchmark",
        "reference.py",
        "--checks",
    ]
    assert spec["jobs"][1]["args"][:4] == ["--model", "two.py", "--benchmark", "one.py"]
    assert spec["jobs"][2]["args"][:4] == ["--model", "one.py", "--benchmark", "two.py"]
    assert spec["jobs"][3]["args"] == ["--model", "one.py", "--checks"]
    assert batch.result_filename(spec) == "RUNS.json"
    assert validate(spec) == spec
    assert raw == request()


@pytest.mark.parametrize(
    "change",
    [
        lambda r: r["runs"][0].update(models=[]),
        lambda r: r["runs"][0].update(models=["one.py", "one.py"]),
        lambda r: r["runs"][0].update(models=["/host/private.py"]),
        lambda r: r["runs"][0].update(benchmarks=["one.py"]),
        lambda r: r["runs"][0].update(benchmarks=["reference.py", "reference.py"]),
        lambda r: r["runs"][0].update(model="unexpected.py"),
        lambda r: r["defaults"].update(args=["--benchmark", "hidden.py"]),
        lambda r: r["defaults"].update(args=["--benchmark-li=hidden.txt"]),
        lambda r: r["runs"][0].update(args=["--mod=hidden.py"]),
        lambda r: r.update(schema=batch.SCHEMA),
    ],
)
def test_invalid_or_ambiguous_model_roles_are_rejected(change):
    raw = request()
    change(raw)
    with pytest.raises((ValueError, KeyError)):
        validate(batch.expand(raw))


@pytest.mark.parametrize(
    "field,value",
    [
        ("models", ["replacement.py"]),
        ("benchmarks", ["hidden.py"]),
        ("comparison_policy", "best_only"),
    ],
)
def test_roster_is_bound_to_exact_invocation(field, value):
    spec = validate(batch.expand(request()))
    spec["batch"]["runs"][0][field] = value
    with pytest.raises(ValueError):
        validate(spec)


def test_generated_models_from_shared_training_are_dependencies_of_every_consumer():
    raw = request()
    raw["jobs"] = [
        {
            "id": "train",
            "kind": "producer",
            "runtime": "python",
            "capsule": "a" * 64,
            "entrypoint": "train.py",
            "outputs": {"models": {"type": "tree", "path": "artifacts/models"}},
        }
    ]
    raw["defaults"]["inputs"] = {
        "trained": {"mode": "artifact_ref", "job": "train", "output": "models"}
    }
    raw["runs"][0]["models"] = ["{input.trained}/one.py", "{input.trained}/two.py"]
    spec = validate(batch.expand(raw))
    assert all("train" in j["depends_on"] for j in spec["jobs"] if j["kind"] == "testing")


def test_returned_multi_model_roster_keeps_waiting_failed_and_negative_runs():
    spec = validate(batch.expand(request()))
    states = ["succeeded", "failed", "waiting", "blocked_dependency"]
    manifest = {
        "workflow": spec,
        "final": False,
        "status": {
            "workflow_id": spec["submission_id"],
            "workflow_sha256": digest(spec),
            "nodes": [
                {
                    "id": j["id"],
                    "state": state,
                    "attempt": 1,
                    "error": None,
                    "outputs": {"native_result": {"statistical_verdict": "FAILED"}}
                    if state == "succeeded"
                    else None,
                }
                for j, state in zip(spec["jobs"], states)
            ],
        },
    }
    result = batch.candidate_results(deepcopy(manifest), {})
    assert result["schema"] == batch.RUN_RESULT_SCHEMA
    assert [r["state"] for r in result["runs"]] == states
    assert result["runs"][0]["models"] == ["one.py", "two.py"]
    assert result["runs"][0]["native_result"]["statistical_verdict"] == "FAILED"
    assert result["scientific_family_aggregation"] == "NOT_PERFORMED"


def test_native_multi_model_local_worker_and_verified_cli(tmp_path, capsys):
    image = os.environ.get("OFFLOAD_RESEARCH_TEST_IMAGE")
    if not image:
        pytest.skip("needs opt-in prebuilt research image")
    if not (Path(__file__).resolve().parents[3] / "research/testing_stages/testing.py").is_file():
        pytest.skip("native testing framework is not in this checkout")
    from research_workflows.cli import main
    from research_workflows.client import verify_collection
    from research_workflows.local import run
    from research_workflows.planner import plan
    from tests.test_research_batches import native_fixture

    raw, data, models = native_fixture(tmp_path)
    raw["schema"] = batch.RUN_SCHEMA
    raw["defaults"]["benchmarks"] = [raw["defaults"]["args"][1]]
    raw["defaults"]["args"] = raw["defaults"]["args"][2:]
    raw["runs"] = raw.pop("candidates")
    for entry in raw["runs"]:
        entry["models"] = [entry.pop("model")]
    raw["runs"][0]["models"].append("{input.models}/negative.py")
    raw["runs"][1]["benchmarks"] = ["{input.models}/negative.py"]
    raw["runs"][2]["benchmarks"] = ["{input.models}/good.py"]
    plan(raw, tmp_path / "plan")

    def withdraw():
        data.rename(tmp_path / "withdrawn-data")
        models.rename(tmp_path / "withdrawn-models")

    record = run(tmp_path / "plan", tmp_path / "local", image=image, admitted_hook=withdraw)
    assert record["worker_stopped"] and record["requester_exit_code"] == 0
    returned = tmp_path / "local/returned"
    roster = load(returned / "RUNS.json")
    assert {r["id"]: r["state"] for r in roster["runs"]} == {
        "bundled": "succeeded", "registered": "succeeded", "negative": "succeeded",
        "broken": "failed", "missing": "blocked_dependency"}
    assert len(roster["runs"][0]["models"]) == 2
    assert roster["runs"][0]["native_result"]["statistical_verdict"] == "FAILED"
    assert main(["runs", "--result", str(returned), "--run", "bundled"]) == 0
    assert '"bundled"' in capsys.readouterr().out
    verify_collection(returned)
    roster["runs"][0]["benchmarks"] = ["tampered.py"]
    atomic(returned / "RUNS.json", roster)
    with pytest.raises(ValueError, match="candidate result index changed"):
        verify_collection(returned)
