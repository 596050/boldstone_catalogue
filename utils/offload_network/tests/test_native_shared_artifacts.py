"""Returned compressed ledgers need the same byte proof as ordinary ledgers."""
import gzip
import hashlib
import os
from copy import deepcopy
from pathlib import Path
import subprocess

import pytest

from research_workflows.common import atomic, digest, load
from research_workflows.output_manifest import native_summary
from tests.test_native_report_limits import evidence


PREFIX = "/work/artifacts/testing"


def packed(root, codec="gzip"):
    job, worker = evidence(root)
    job["resources"] = {"max_work_mb": 1}
    plain = worker / "ledger.txt"
    raw = plain.read_bytes()
    encoded = gzip.compress(raw, mtime=0) if codec == "gzip" else raw
    ident = hashlib.sha256(raw).hexdigest()
    relative = "shared/blobs/" + ident[:2] + "/" + ident + "/data" + (".gz" if codec == "gzip" else "")
    blob = root / relative
    blob.parent.mkdir(parents=True)
    blob.write_bytes(encoded)
    item = {"sha256": ident, "encoded_sha256": hashlib.sha256(encoded).hexdigest(),
            "bytes": len(raw), "encoded_bytes": len(encoded), "codec": codec,
            "path": PREFIX + "/" + relative}
    manifest = {"schema": "marketmaker.shared_artifacts.v1", "store": PREFIX + "/shared",
                "files": {"ledger.txt": item}}
    save_manifest(worker, manifest)
    plain.unlink()
    return job, worker, blob, manifest


def save_manifest(worker, manifest):
    value = deepcopy(manifest)
    value.pop("manifest_id", None)
    value["manifest_id"] = digest(value)
    atomic(worker / "ARTIFACTS.json", value)


@pytest.mark.parametrize("codec", ["gzip", "identity"])
def test_relocated_return_verifies_encoded_and_decoded_ledger(tmp_path, codec):
    job, _, _, _ = packed(tmp_path, codec)
    result = native_summary(None, job, native_directory=tmp_path)
    assert result["verification"] == "NATIVE_PLANS_RECEIPTS_AND_ARTIFACT_REFERENCES"
    assert result["statistical_verdict"] == "FAILED"


@pytest.mark.parametrize("change", ["encoded_hash", "decoded_hash", "decoded_size", "encoded_size",
                                  "codec", "outside_store", "outside_output", "oversized", "manifest_hash"])
def test_invalid_packed_evidence_is_rejected(tmp_path, change):
    job, worker, blob, manifest = packed(tmp_path)
    item = manifest["files"]["ledger.txt"]
    if change == "encoded_hash": item["encoded_sha256"] = "0" * 64
    elif change == "decoded_hash":
        raw = b"changed ledger!\n"
        encoded = gzip.compress(raw, mtime=0)
        blob.write_bytes(encoded)
        item.update(encoded_bytes=len(encoded), encoded_sha256=hashlib.sha256(encoded).hexdigest(), bytes=len(raw))
    elif change == "decoded_size": item["bytes"] -= 1
    elif change == "encoded_size": item["encoded_bytes"] += 1
    elif change == "codec": item["codec"] = "pickle"
    elif change == "outside_store": item["path"] = PREFIX + "/elsewhere/data.gz"
    elif change == "outside_output": manifest["store"] = "/outside/shared"
    elif change == "oversized": item["bytes"] = (1 << 20) + 1
    save_manifest(worker, manifest)
    if change == "manifest_hash":
        value = load(worker / "ARTIFACTS.json"); value["manifest_id"] = "0" * 64
        atomic(worker / "ARTIFACTS.json", value)
    with pytest.raises((ValueError, OSError)):
        native_summary(None, job, native_directory=tmp_path)


def test_plain_copy_cannot_mask_a_corrupt_packed_ledger(tmp_path):
    job, worker, blob, _ = packed(tmp_path)
    (worker / "ledger.txt").write_text("retained ledger\n")
    blob.write_bytes(b"corrupt encoded evidence")
    with pytest.raises((ValueError, OSError)):
        native_summary(None, job, native_directory=tmp_path)


def test_packed_reference_outside_model_inventory_is_also_verified(tmp_path):
    job, worker, _, _ = packed(tmp_path)
    path = tmp_path / "stage_04_replay/evaluation/RESULT.json"
    value = load(path)
    value["additional_evidence"] = {"path": PREFIX + "/" + str(worker.relative_to(tmp_path)) + "/ledger.txt",
                                    "sha256": next(iter(value["models"]["one"]["artifacts"].values()))}
    atomic(path, value)
    assert native_summary(None, job, native_directory=tmp_path)["statistical_verdict"] == "FAILED"


def test_packed_blob_symlink_is_rejected(tmp_path):
    job, _, blob, _ = packed(tmp_path)
    other = tmp_path / "elsewhere.gz"
    blob.rename(other)
    blob.symlink_to(other)
    with pytest.raises(ValueError, match="symlink"):
        native_summary(None, job, native_directory=tmp_path)


@pytest.mark.skipif(not os.environ.get("OFFLOAD_RESEARCH_TEST_IMAGE"), reason="explicit Docker image required")
def test_actual_sealed_encoder_is_readable_after_docker_return(tmp_path):
    job, worker = evidence(tmp_path)
    job["resources"] = {"max_work_mb": 1}
    repository = Path(os.environ["NATIVE_ARTIFACT_PACK_REPO"]).resolve()
    script = (
        "import json,sys;sys.path.insert(0,'/repo');"
        "from research.testing_stages.runtime.artifact_store import pack;"
        "from pathlib import Path;"
        "worker=Path('/work/artifacts/testing/stage_04_replay/evaluation/one');"
        "files=json.loads((worker/'WORKER.json').read_text())['artifacts'];"
        "pack(worker,files,'/work/artifacts/testing/shared',minimum=1)"
    )
    subprocess.run(["/usr/local/bin/docker", "--context", "desktop-linux", "run", "--rm",
                    "--pull=never", "--network=none", "--read-only", "--cpus=0.25",
                    "--memory=256m", "--pids-limit=64", "--tmpfs", "/tmp:rw,size=16m",
                    "--mount", "type=bind,source=" + str(repository) + ",target=/repo,readonly",
                    "--mount", "type=bind,source=" + str(tmp_path) + ",target=/work/artifacts/testing",
                    "--entrypoint", "python", os.environ["OFFLOAD_RESEARCH_TEST_IMAGE"],
                    "-B", "-I", "-c", script], check=True, capture_output=True, timeout=30)
    assert not (worker / "ledger.txt").exists()
    assert load(worker / "ARTIFACTS.json")["files"]["ledger.txt"]["codec"] == "gzip"
    assert native_summary(None, job, native_directory=tmp_path)["statistical_verdict"] == "FAILED"
