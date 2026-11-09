"""Check resumed progress using small exported files, never the live queue DB."""

import json
import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path


def main():
    here = Path(__file__).resolve().parent
    resumed = json.loads((here / "IQFEED_RESUME.json").read_text())
    started = datetime.fromisoformat(resumed["started_at_utc"])
    status_path = Path(resumed["launch"]["status"])
    root = status_path.parent.parent
    pid = resumed["launch"]["started_pid"]
    snapshots = []
    for index in range(2):
        if index:
            time.sleep(20)
        os.kill(pid, 0)
        report = json.loads(status_path.read_text())
        if report["pid"] != pid or report["state"] != "DOWNLOADING":
            raise RuntimeError("the expected downloader is not reporting DOWNLOADING")
        if datetime.fromisoformat(report["updated_at_utc"]) < started:
            raise RuntimeError("stale exported status")
        # Read only a bounded tail of the text log; no SQLite access/reader lock.
        with (root / "logs/download.log").open("rb") as log:
            end = log.seek(0, os.SEEK_END)
            log.seek(max(0, end - 65536))
            tail = log.read().decode("utf-8", errors="replace")
        responses = []
        for line in tail.splitlines():
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if (
                "at" in item and "symbol" in item and "status" in item
                and datetime.fromisoformat(item["at"]) >= started
            ):
                responses.append(item)
        if not responses:
            raise RuntimeError("no processed IQFeed responses since restart")
        snapshots.append({
            "observed_at_utc": datetime.now(timezone.utc).isoformat(),
            "pid": pid, "state": report["state"],
            "status_updated_at_utc": report["updated_at_utc"],
            "counts": report["counts"], "jobs": report["jobs"],
            "retained_parsed_rows": report["retained_parsed_rows"],
            "current": report.get("current"), "log_size_bytes": end,
            "latest_processed_response": responses[-1],
        })
    first, last = snapshots
    if last["latest_processed_response"]["at"] <= first["latest_processed_response"]["at"]:
        raise RuntimeError("no new processed response between progress observations")
    def pending(snapshot):
        return snapshot["counts"].get("PENDING", 0) + snapshot["counts"].get("RUNNING", 0)

    if pending(last) >= pending(first):
        raise RuntimeError("unfinished queue count did not decrease")
    result = {
        "status": "PASS", "snapshots": snapshots,
        "unfinished_at_observation_end": pending(last),
        "new_jobs_processed_between_exported_snapshots": pending(first) - pending(last),
        "worker_intentionally_left_running": True,
        "source_cutoff_unchanged": resumed["cutoff_unchanged"],
        "verified_retained_responses_before_restart": resumed["review"]["verified_responses"],
        "archive_free_bytes": shutil.disk_usage(root).free,
        "live_sqlite_opened_by_verifier": False,
        "all_downloads_finished": False,
    }
    (here / "IQFEED_PROGRESS.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
