"""Probe newly supported CRC when-issued aliases on the existing IQFeed service.

Source feasibility only. Never starts IQConnect, changes authentication or
entitlements, replaces retained data, or infers historical broker availability.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import urllib.error
import urllib.request

from utils.data_paths import resolve_path
from research.utility.crc_historical_source_recovery_20260913_v1 import probe
from utils.iqfeed.macroeconomics import archive

HERE = Path(__file__).resolve().parent
GUIDE = "https://ws1.dtn.com/IQ/Guide/stocks_nyse.html"


def ref(path):
    path = Path(path)
    payload = path.read_bytes()
    return {"path": str(path.resolve()), "bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest()}


def capture_guide(root):
    receipt = {"url": GUIDE, "started_at_utc": probe.now()}
    request = urllib.request.Request(GUIDE, headers={
        "User-Agent": "Mozilla/5.0 historical-source-research",
        "Accept": "text/html",
    })
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = response.read(2 * 1024**2 + 1)
            if len(body) > 2 * 1024**2:
                raise ValueError("Public symbol guide exceeds 2 MiB cap")
            path = root / "dtn_stocks_nyse.html"
            with path.open("xb") as stream:
                stream.write(body)
            receipt.update(status="CAPTURED", http_status=response.status,
                           final_url=response.url, body=ref(path),
                           headers={k: response.headers.get(k) for k in
                                    ("Content-Type", "Content-Length", "Last-Modified", "ETag")})
    except (OSError, urllib.error.URLError, ValueError) as error:
        receipt.update(status="FAILED", failure={"type": type(error).__name__,
                                                 "message": str(error)})
    receipt["completed_at_utc"] = probe.now()
    probe.save(root / "dtn_stocks_nyse.receipt.json", receipt)
    return receipt


def main():
    output = HERE / "IQFEED_PROBE.json"
    root = resolve_path("research_artifacts", require_exists=True) / HERE.name / "iqfeed_probe"
    if root.exists() or output.exists():
        raise FileExistsError("Retain every attempt; this run is create-only")
    root.mkdir()
    (root / "incomplete").mkdir()
    probe.guard(root)
    specs = [
        {"symbol": "CRCQQ", "cadence": "daily", "begin": "20141113", "end": "20141114",
         "label": "crcqq_daily_control"},
        {"symbol": "CRC*", "cadence": "minute", "begin": "20141113", "end": "20141202",
         "label": "crc_when_issued_star"},
        {"symbol": "CRCWI", "cadence": "minute", "begin": "20141113", "end": "20141202",
         "label": "crc_when_issued_nyse"},
    ]
    result = {
        "started_at_utc": probe.now(), "scope": "SOURCE_FEASIBILITY_ONLY",
        "source_root": str(root), "code": ref(__file__),
        "collector": ref(archive.__file__), "retained_probe_helper": ref(probe.__file__),
        "source_evidence": {
            "dtn_suffix_guide": GUIDE,
            "nyse_crcwi_november_2014": "https://www.nyse.com/publicdocs/nyse/data/Monthly_Consolidated_Volume_by_Symbol_201411.pdf",
            "issuer_when_issued_dates": "https://www.sec.gov/Archives/edgar/data/1609253/000110465914073169/a14-22833_2ex99d1.htm",
        },
        "closest_retained_runs": [
            ref(Path(probe.__file__).parent / "run_01/RESULT.json"),
            ref(Path(probe.__file__).parent.parent / "crc_predecessor_source_identity_20260913_v1/run_01/RESULT.json"),
            ref(Path(probe.__file__).parent.parent / "crc_predecessor_source_identity_20260913_v1/run_02/RESULT.json"),
        ],
        "changed_component": "Supported when-issued source alias, not a predictive candidate",
        "unresolved_question": "Does the running service retain minute history under CRC* or CRCWI?",
        "matched_control": "CRCQQ daily 2014-11-13 to 2014-11-14, inside previously returned history",
        "meaningful_effect": "At least one independently identity-verified missing original CRC minute observation",
        "falsifying_probe_result": "Request-specific completed NO_DATA for the newly supported aliases; scoped to these commands and dates",
        "specifications": specs,
        "caps": {"history_seconds_per_request": 60, "history_response_bytes": 256 * 1024**2,
                 "public_guide_bytes": 2 * 1024**2, "external_free_reserve_bytes": 20 * 1024**3},
        "service_policy": "Existing 127.0.0.1:9100 only; nonblocking cooperative lock; no startup, reconfiguration, authentication change or lock removal",
        "historical_timestamp_meaning": "UNVERIFIED_FOR_RETURNED_ALIAS. Request asks end-labelled minute bars; current retrieval clocks do not establish historical customer receipt or broker execution clocks.",
        "native_broker_units": "NOT_ESTABLISHED", "performance_qualification": "NOT_ESTABLISHED",
        "full_comparison": "NOT_EVALUABLE", "histories": [],
    }
    result["guide_capture"] = capture_guide(root)
    try:
        with probe.shared_lock():
            result["cooperative_lock"] = "ACQUIRED_WITHOUT_WAIT"
            for spec in specs:
                receipt = probe.history(root, **spec)
                result["histories"].append(receipt)
                if not receipt["protocol_acknowledged"]:
                    result["remaining_specs_skipped"] = specs[len(result["histories"]):]
                    result["stop_reason"] = "Existing service did not acknowledge protocol; no service changes attempted"
                    break
        result["status"] = "BOUNDED_PROBES_FINISHED"
    except BlockingIOError:
        result["cooperative_lock"] = "BUSY_NO_WAIT_NO_UNLOCK"
        result["status"] = "SKIPPED_BUSY"
    except OSError as error:
        result["status"] = "LOCAL_PRECONDITION_FAILED"
        result["failure"] = {"type": type(error).__name__, "message": str(error)}
    result["completed_at_utc"] = probe.now()
    result["artifact_files"] = [ref(path) for path in sorted(root.rglob("*")) if path.is_file()]
    probe.save(output, result)
    print(json.dumps({"status": result["status"], "output": str(output),
                      "guide_capture": result["guide_capture"]["status"],
                      "histories": [{"symbol": r["spec"]["symbol"], "status": r["status"],
                                     "rows": r["rows"]} for r in result["histories"]]}), flush=True)


if __name__ == "__main__":
    main()
