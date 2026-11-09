"""Recheck real returned model evidence and compact only its redundant expansions."""

import argparse
import json
from pathlib import Path

from lib.file_lock import file_lock
from research_workflows.client import verify_collection
from research_workflows.common import atomic, load, sha
from research_workflows.compressed import compact_collection
from research_workflows.project_storage import Project
from research_workflows.publication import resolve_record


def sizes(root):
    paths = [root, *root.rglob("*")]
    return {"logical_bytes": sum(p.stat().st_size for p in paths if p.is_file()),
            "allocated_bytes": sum(getattr(p.stat(), "st_blocks", 0) * 512 for p in paths),
            "files": sum(p.is_file() for p in paths)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--collection", type=Path, required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        raise FileExistsError("use a fresh validation report path")
    project = Project(args.config)
    collection = args.collection.absolute()
    root = project.bulk()
    collection.relative_to(root)
    candidate = project.origin(args.candidate)
    retained = {p.name: sha(p) for p in candidate.iterdir() if p.is_file()}
    records = sorted((candidate / "offload_runs").glob("*/*/*/RUN_RESULT.json"))
    record_hashes = {str(p): sha(p) for p in records}
    before = sizes(root)
    receipt_before = verify_collection(collection, max_bytes=8 << 30)
    with file_lock(project.state / "queue.lock", timeout=0):
        compacted = compact_collection(project, collection)
    receipt = verify_collection(collection, max_bytes=8 << 30)
    assert receipt == receipt_before
    manifest = load(collection / "DELIVERY.json", max_bytes=16 << 20)["manifest"]
    reads = []
    for path in records:
        record = load(path)
        key = record["node"]["id"] + ".research_evidence"
        if key not in record["evidence"]["ports"]:
            reads.append({"node": record["node"]["id"], "state": record["node"]["state"],
                          "readback": "NO_NATIVE_OUTPUT_EXPECTED"})
            continue
        result = resolve_record(project, path.parent, key, "RESULT.json")
        obj = manifest["objects"][key]
        expected = load(root / "objects" / obj / "OBJECT.json")["files"]["RESULT.json"]["sha256"]
        assert sha(result) == expected
        reads.append({"node": record["node"]["id"], "state": record["node"]["state"],
                      "sha256": expected, "readback": "EXACT_NATIVE_RESULT_BYTES",
                      "native_status": load(result)["status"]})
    assert {p.name: sha(p) for p in candidate.iterdir() if p.is_file()} == retained
    assert {str(p): sha(p) for p in records} == record_hashes
    assert all(not (root / "objects" / obj / "data").exists() for obj in receipt["collected_objects"])
    report = {"status": "PASS", "schema": "marketmaker.offload_recovery_retention_validation.v1",
              "collection": str(collection), "delivery_sha256": receipt["delivery_sha256"],
              "original_candidate_files": retained, "origin_records": record_hashes,
              "records_unchanged": True, "jobs_executed": 0, "model_performance_reinterpreted": False,
              "before": before, "after": sizes(root), "compacted_objects": len(compacted),
              "native_result_reads": reads, "archive_retained": True,
              "read_cache": sizes(project.state / "read-cache")}
    atomic(args.report, report)
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
