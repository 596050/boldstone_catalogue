"""Pin the reviewed local package; this never calls a platform or master writer."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument("--independent-audit", required=True)
args = parser.parse_args()
if (BASE / "SEAL.json").exists():
    raise SystemExit("Already sealed; preserve the existing packet and use a new addendum.")


def binding(path):
    p = Path(path)
    p = p if p.is_absolute() else BASE / p
    raw = p.read_bytes()
    return {"path": str(p), "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}


validation = json.loads((BASE / "VALIDATION.json").read_text())
assert validation["status"] == "PASS_BOUNDED_EVIDENCE_AND_DRAFTS"
audit = Path(args.independent_audit)
audit = audit if audit.is_absolute() else BASE / audit
assert audit.is_file()
audit_record = json.loads(audit.read_text())
audit_status = audit_record.get("status", "")
assert audit_status.startswith("PASS"), audit_status
payload = json.loads((BASE / "LISTING_RESOLUTION.json").read_text())
now = datetime.now(timezone.utc).isoformat()
handoff = {
    "schema": "boldstone.listing-resolution-import-ready-handoff.v1",
    "recorded_utc": now,
    "status": "SEALED_EVIDENCE_AND_DRAFT_OVERLAY_READY_FOR_SOLE_WRITER_IMPORT",
    "sole_writer_thread": "01a144ab-1a7c-7223-a403-73a4d53d70ff",
    "payload": binding("LISTING_RESOLUTION.json"),
    "import_plan": binding("IMPORT_PLAN.json"),
    "scope_state": binding("COMPLETION_SCOPE.json"),
    "counts": payload["counts"],
    "latest_verified_rebase": binding("REBASE_CUP_FROZEN.json"),
    "local_validation": binding("VALIDATION.json"),
    "independent_validation": binding(audit),
    "four_correction_independent_audit": binding("worker-01/addendum-validation/FOUR_LISTING_CORRECTIONS_AUDIT.json"),
    "seal": "SEAL.json",
    "shared_master_import_performed_by_A": False,
    "platform_execution_performed": False,
    "required_final_receipt": "Coordinator publication plus independent A readback of exact current register/workbook bytes and scoped values. Native execution must have separate receipts.",
}
(BASE / "HANDOFF.json").write_text(json.dumps(handoff, ensure_ascii=False, indent=2) + "\n")
artifacts = []
for p in sorted(BASE.rglob("*")):
    if p.is_file() and p != BASE / "SEAL.json":
        raw = p.read_bytes()
        artifacts.append({"relative_path": str(p.relative_to(BASE)), "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)})
seal = {
    "schema": "boldstone.immutable-listing-resolution-seal.v1",
    "sealed_utc": now,
    "status": "SEALED_IMPORT_READY_BOUNDED_EVIDENCE_AND_DRAFTS",
    "artifacts": artifacts,
    "artifact_count": len(artifacts),
    "rule": "Listed bytes are immutable. Later publication/readback receipts may be added as separate artifacts; never rewrite listed files or treat this seal as native execution.",
    "platform_writes": 0,
    "shared_master_writes_by_A": 0,
}
(BASE / "SEAL.json").write_text(json.dumps(seal, ensure_ascii=False, indent=2) + "\n")
for e in artifacts:
    assert hashlib.sha256((BASE / e["relative_path"]).read_bytes()).hexdigest() == e["sha256"]
print(json.dumps({"status": "SEALED_AND_READBACK_PASS", "artifacts": len(artifacts), "seal": binding("SEAL.json"), "payload": binding("LISTING_RESOLUTION.json"), "handoff": binding("HANDOFF.json")}, indent=2))
