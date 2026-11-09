"""Recheck previous genuine research results without fitting or publishing again."""

import hashlib
import json
import tarfile
from datetime import datetime, timezone
from pathlib import Path

from research_workflows.client import collection_objects, verify_collection
from research_workflows.common import load, sha


def main():
    here = Path(__file__).resolve().parent
    previous = load(here.parent / "project_recovery_20260911/GENUINE_RETURN.json")
    collection = Path(previous["collection"])
    receipt = verify_collection(collection, max_bytes=8192 << 20)
    assert receipt["delivery_sha256"] == previous["delivery_sha256"]
    cache, _ = collection_objects(collection)
    delivery = load(collection / "DELIVERY.json")["manifest"]
    checked = []
    for result in previous["native_result_reads"]:
        port = result["node"] + ".research_evidence"
        if "sha256" not in result:
            assert port not in delivery["objects"]
            continue
        ident = delivery["objects"][port]
        with tarfile.open(cache / ident / "archive.tar.gz", "r:gz") as archive:
            raw = archive.extractfile("data/RESULT.json").read()
        assert hashlib.sha256(raw).hexdigest() == result["sha256"]
        checked.append({"node": result["node"], "sha256": result["sha256"]})
    origin_roots = set()
    for filename, digest in previous["origin_records"].items():
        path = Path(filename)
        assert sha(path) == digest
        publication = load(path.parent / "PUBLICATION.json")
        for name, expected in publication["files"].items():
            assert sha(path.parent / name) == expected
        origin_roots.add(path.parents[4])
    assert len(origin_roots) == 1
    origin = origin_roots.pop()
    for filename, digest in previous["original_candidate_files"].items():
        assert sha(origin / filename) == digest
    result = {
        "status": "PASS", "at_utc": datetime.now(timezone.utc).isoformat(),
        "jobs_executed": 0, "collection_objects": len(receipt["collected_objects"]),
        "delivery_sha256": receipt["delivery_sha256"],
        "origin_records_unchanged": len(previous["origin_records"]),
        "original_candidate_files_unchanged": len(previous["original_candidate_files"]),
        "native_results_exact": checked,
        "missing_data_branch_has_no_fabricated_result": True,
        "production_files_modified": False,
    }
    (here / "GENUINE_RECHECK.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
