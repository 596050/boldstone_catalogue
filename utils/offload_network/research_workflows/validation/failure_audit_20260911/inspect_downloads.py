"""Read-only exported snapshot and bounded verification; never starts acquisition.

All generated audit receipts go to --out, not the live archive. Only atomically
exported manifests/status are read for live queues: even a read-only SQLite
transaction can block writes on the external drive. No live database is opened.
"""

import argparse
import csv
import json
import os
import shutil
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from utils.data_paths import ensure_external_storage, resolve_source_location
from utils.iqfeed.macroeconomics import archive as iq
from utils.macroeconomics import archive as economic


def snapshot():
    storage = ensure_external_storage(force=True)
    root = resolve_source_location("iqfeed_macroeconomics")
    econ = resolve_source_location("macroeconomic_releases")
    report = {
        "at_utc": datetime.now(timezone.utc).isoformat(),
        "storage": {k: str(v) for k, v in storage.items() if k != "marker_path"},
        "free_bytes": shutil.disk_usage(root).free,
        "collector_reserve_bytes": 20 << 30,
        "local_free_bytes": shutil.disk_usage(Path.cwd()).free,
        "read_only": True,
    }
    print("Reading exported IQFeed manifest; no live SQLite connection", flush=True)
    manifest_path = root / "metadata/MANIFEST.csv"
    with manifest_path.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    categories = defaultdict(lambda: {"counts": Counter(), "rows": 0})
    special = []
    for row in rows:
        folder = row["raw_file"].split("/")
        category = "/".join(folder[1:3]) if folder[:1] == ["iqfeed"] else row["kind"]
        category += "/" + row["cadence"]
        categories[category]["counts"][row["status"]] += 1
        if row["status"] in {"COMPLETE", "COMPLETE_WITH_ANOMALIES"}:
            categories[category]["rows"] += int(row["rows"] or 0)
        if row["kind"] != "dated_contract":
            special.append({
                "id": row["job_id"], "symbol": row["symbol"], "cadence": row["cadence"],
                "status": row["status"], "rows": int(row["rows"] or 0),
                "first": row["first"], "last": row["last"], "errors": row["errors"],
            })
    binding = json.loads((root / "metadata/ARCHIVE.json").read_text())
    current = {p.name: iq.file_sha(p) for p in Path(iq.__file__).parent.glob("*.py")}
    status = json.loads((root / "metadata/STATUS.json").read_text())
    try:
        os.kill(status["pid"], 0)
        pid_live = True
    except ProcessLookupError:
        pid_live = False
    report["iqfeed"] = {
        "counts": dict(Counter(row["status"] for row in rows)),
        "total_jobs": len(rows), "categories": dict(categories), "non_dated_series": special,
        "retained_rows_in_complete_jobs": sum(v["rows"] for v in categories.values()),
        "manifest_export_modified_at_utc": datetime.fromtimestamp(manifest_path.stat().st_mtime, timezone.utc).isoformat(),
        "manifest_sha256": iq.file_sha(manifest_path),
        "collector_code_matches_archive_binding": current == binding["code_sha256"],
        "cutoff": binding["cutoff"], "status": status, "status_pid_live": pid_live,
        "full_archive_reverification": "NOT_RUN_ON_ACTIVE_OR_IO_BUSY_DRIVE", "stop_file_exists": (root / "metadata/STOP").exists(),
    }
    print("Reading exported economic releases manifest", flush=True)
    economic_rows = json.loads((econ / "metadata/MANIFEST.json").read_text())
    report["economic_releases"] = {
        "status": json.loads((econ / "metadata/STATUS.json").read_text()),
        "manifest_counts": dict(Counter(row["state"] for row in economic_rows)),
        "queue_jobs": len(economic_rows),
        "stop_file_exists": (econ / "metadata/STOP").exists(),
    }
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--verify-economic", action="store_true")
    args = parser.parse_args()
    result = snapshot()
    if args.verify_economic:
        root = resolve_source_location("macroeconomic_releases")
        # Keep production verification unchanged; intercept only its final audit
        # receipt publication so this check cannot mutate the Toshiba archive.
        with patch.object(economic, "atomic_json") as writer:
            result["economic_releases"]["fresh_verification"] = economic.verify(root)
            assert writer.call_count == 1
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "receipt": str(args.out), "at_utc": result["at_utc"],
        "iqfeed_counts": result["iqfeed"]["counts"],
        "iqfeed_rows": result["iqfeed"]["retained_rows_in_complete_jobs"],
        "economic_counts": result["economic_releases"]["manifest_counts"],
        "economic_verification": result["economic_releases"].get("fresh_verification"),
    }))


if __name__ == "__main__":
    main()
