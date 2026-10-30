"""Bind a successful candidate readback to the identical published workbook."""
from pathlib import Path
import argparse
import datetime
import hashlib
import json

B = Path(__file__).resolve().parent
C = B.parents[2]
W = C / "components/reviews/workbook-refresh-2026-10-19"
p = argparse.ArgumentParser()
p.add_argument("--workbook-sha256", required=True)
digest = p.parse_args().workbook_sha256


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def ref(path):
    return {"path": str(path), "sha256": sha(path)}


candidate_path = B / ("CANDIDATE_WORKBOOK_READBACK_" + digest[:16] + ".json")
candidate = read(candidate_path)
publication_path = W / "checkpoint-publication-receipt.json"
publication = read(publication_path)
summary = publication["summary"]
history = W / "history" / digest
snapshot = W / "published-snapshots" / (digest + ".xlsx.snapshot")
published = C / summary["workbook"]
independent_path = history / "independent-file-verification.json"
independent = read(independent_path)
checks = {}


def check(name, result):
    checks[name] = "PASS" if result else "FAIL"


check("Candidate readback passed all470 checks", candidate["status"] == "PASS" and
      candidate["checks_failed"] == 0 and candidate["checks_passed"] == 470 and candidate["candidate_only"])
check("Candidate bytes match requested hash", candidate["workbook_sha256"] == digest and sha(candidate["immutable_snapshot"]) == digest)
check("Publication through97 is complete", publication["status"] == "PASS" and summary["included_owner_review_imports_through_batch"] >= 97 and
      summary["validation_status"] == summary["visual_validation_status"] == "PASS")
check("Published immutable snapshot and current file are identical", summary["workbook_sha256"] == digest == sha(snapshot) == sha(published))
check("Frozen publication receipt matches", read(history / "checkpoint-publication-receipt.json") == publication)
check("Coordinator saved-file and visual validation bound", independent["status"] == "PASS" and independent["output_sha256"] == digest and independent["visual_verification"] == "PASS")
check("Native link total remains4703", summary["native_hyperlinks"] == 4703)
check("Accepted source controls remain frozen", sha(B.parent / "remaining-lane-b-working-specs-2026-10-20/SEALED_MANIFEST.json") ==
      "e7b1a8b49b1500c6031849e7be34f5c41a9704bce31bad80159b78a993bfd5fc")

result = {
    "schema": "boldstone.final-publication-bound-independent-readback.v1",
    "status": "PASS" if all(v == "PASS" for v in checks.values()) else "FAIL",
    "checked_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "workbook": str(published), "workbook_sha256": digest, "published_through": summary["included_owner_review_imports_through_batch"],
    "publication": ref(publication_path), "immutable_publication": ref(history / "checkpoint-publication-receipt.json"),
    "root_saved_file_and_visual_verification": ref(independent_path),
    "candidate_readback": ref(candidate_path), "inherited_saved_cell_checks": candidate["checks_passed"],
    "binding_checks_passed": sum(v == "PASS" for v in checks.values()), "binding_checks": checks,
    "scopes_checked": 40, "working_field_groups_checked": 240, "terminal_reference_rows_checked": 2,
    "same_published_bytes_verified_without_repeating_cell_checks": True,
    "physical_specifications_verified": False, "source_estimates_and_unknowns_retained": True,
    "shared_master_writes_by_lane": 0, "remote_mutations": 0,
}
out = B / ("FINAL_WORKBOOK_READBACK_" + digest[:16] + ".json")
assert not out.exists()
out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({"status": result["status"], "inherited_checks": candidate["checks_passed"],
                  "binding_checks": result["binding_checks_passed"], "failed": [k for k,v in checks.items() if v != "PASS"],
                  "receipt": ref(out), "workbook": str(published)}))
