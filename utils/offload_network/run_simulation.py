#!/usr/bin/env python3
"""Generate a retained, inspectable simulated-network integration run."""
from __future__ import annotations

import json
import pathlib
import sys
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from simulator import JobRequest, SimulatedNetwork, SourceRequest


def main() -> int:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_root = ROOT / "simulated_network" / "runs" / stamp
    source = run_root / "configured_sources" / "market_data"
    source.mkdir(parents=True)
    (source / "prices.csv").write_text("symbol,close\nABC,101.25\nXYZ,88.50\n")
    jobs = run_root / "job_inputs"
    jobs.mkdir()
    success = jobs / "success.py"
    success.write_text(
        "import csv,json,pathlib,sys\n"
        "rows=list(csv.DictReader(pathlib.Path('blobs/data/prices.csv').open()))\n"
        "pathlib.Path('result.json').write_text(json.dumps({'rows':rows,'arg':sys.argv[1]}))\n"
        "pathlib.Path('artifacts').mkdir()\n"
        "pathlib.Path('artifacts/worker.txt').write_text('isolated')\n"
    )
    failure = jobs / "failure.py"
    failure.write_text("raise RuntimeError('intentional simulated remote error')\n")
    timeout = jobs / "timeout.py"
    timeout.write_text("import time\ntime.sleep(10)\n")

    network = SimulatedNetwork(
        run_root,
        workers={"windows-01": "windows", "linux-01": "linux", "mac-01": "macos"},
        sources={"market-data": source},
    )
    source_request = [SourceRequest("market-data", "prices.csv", "data/prices.csv", "prices")]
    requests = [
        JobRequest(str(success), "windows-01", args=["windows"],
                   metadata={"scenario": "success-with-source"}, sources=source_request),
        JobRequest(str(success), "linux-01", args=["linux"],
                   metadata={"scenario": "success-linux"}, sources=source_request),
        JobRequest(str(failure), "mac-01", metadata={"scenario": "remote-exception"}),
        JobRequest(str(timeout), "windows-01", timeout_s=0.2,
                   metadata={"scenario": "timeout"}),
        JobRequest(str(success), "mac-01", args=["missing"],
                   metadata={"scenario": "missing-source"},
                   sources=[SourceRequest("market-data", "missing.csv", "data/prices.csv")]),
    ]
    for request in requests:
        network.enqueue(request)
    envelopes = network.drain()
    summary = {
        "run_root": str(run_root),
        "jobs": len(envelopes),
        "succeeded": sum(e["status"] == "succeeded" for e in envelopes),
        "failed": sum(e["status"] == "failed" for e in envelopes),
        "scenario_status": {e["metadata"]["scenario"]: e["status"] for e in envelopes},
        "receipts": [str(network.controller / "receipts" / f"{e['job_id']}.json") for e in envelopes],
    }
    (run_root / "SUMMARY.json").write_text(json.dumps(summary, indent=2, sort_keys=True))
    latest = ROOT / "simulated_network" / "LATEST.txt"
    latest.write_text(str(run_root) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["succeeded"] == 2 and summary["failed"] == 3 else 1


if __name__ == "__main__":
    raise SystemExit(main())
