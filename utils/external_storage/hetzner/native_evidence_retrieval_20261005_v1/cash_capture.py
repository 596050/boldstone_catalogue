"""One bounded extension of the already authenticated demo account cash scope.

Reuses the inspected Reader authentication/GET transport. No dealing adapter,
activity re-fetch, account switch, live host, raw authentication retention, or
assignment of account-level cash to a strategy. Run once; preserve outputs.
"""
from __future__ import annotations

import fcntl
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
SOURCE = ROOT / "research/utility/retained_demo_history_readback_20261005_v1/capture.py"
SOURCE_SHA = "2a366733970c9f369fbf6236cf5256fb3afa4c6cc58dee79e29b353fde39af4b"
PRIOR = SOURCE.parent / "run_01/AUTH_STATUS.json"
ACCOUNT_KEY = "088901091cf54f0f1ea43c61e7501e946815651a815cf4bdcb1e77c6c5b11abd"
RUNTIME = ROOT / ".runtime/ig_pair_forward_v1"
CENTRAL = Path("/Volumes/Toshiba 2TB/other_data/research/artifacts/native_evidence_retrieval_20261005_v1/broker_cash_extension")
OUTPUT = HERE / "BROKER_CASH_EXTENSION.json"
FULL = ("2026-07-26", "2026-09-25")
FALLBACK = [("2026-07-26", "2026-08-25"), ("2026-08-26", "2026-09-25")]
CAP = 32 * 1024 * 1024


def stamp():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    data = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    if len(data) > 256 * 1024:
        raise RuntimeError("metadata_budget_exceeded")
    with path.open("xb") as f:
        os.fchmod(f.fileno(), 0o600)
        f.write(data)
        f.flush()
        os.fsync(f.fileno())


def process_owners():
    """Keep only PID and command hash; never retain process command secrets."""
    output = subprocess.check_output(["ps", "-axo", "pid=,ppid=,args="], text=True, timeout=10)
    records = []
    for line in output.splitlines():
        fields = line.strip().split(None, 2)
        if len(fields) == 3:
            records.append((int(fields[0]), int(fields[1]), fields[2]))
    parents = {pid: parent for pid, parent, _ in records}
    ancestors = set()
    pid = os.getpid()
    while pid and pid not in ancestors:
        ancestors.add(pid)
        pid = parents.get(pid, 0)
    pattern = re.compile(r"utils/ig_index|ig_pair_forward|retained_demo_history_readback_20261005_v1/capture\.py|native_evidence_retrieval_20261005_v1/cash_capture\.py")
    return [{"pid": pid, "command_sha256": hashlib.sha256(command.encode()).hexdigest()}
            for pid, _, command in records if pid not in ancestors and pattern.search(command)]


def liveness(held):
    result = {"observed_at": stamp(), "status": "DEFERRED", "locks": []}
    result["matching_processes"] = process_owners()
    if result["matching_processes"]:
        result["reason"] = "possible_ig_runtime_or_reader_process"
        return result
    paths = sorted(RUNTIME.rglob("*.lock"))
    required = RUNTIME / ACCOUNT_KEY / "account.lock"
    if required not in paths:
        result["reason"] = "original_account_lock_missing"
        return result
    for path in paths:
        handle = path.open("rb")
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            handle.close()
            result["locks"].append({"path": str(path), "status": "HELD_BY_OTHER"})
            result["reason"] = "runtime_lock_owned"
            return result
        held.append(handle)
        result["locks"].append({"path": str(path), "status": "ACQUIRED_WITHOUT_WRITE"})
    journals = list(RUNTIME.glob("*/journal.sqlite3"))
    if len(journals) != 1 or journals[0].parent.name != ACCOUNT_KEY:
        result["reason"] = "journal_account_identity_ambiguous"
        return result
    if any(p.with_name(p.name + "-wal").exists() for p in journals):
        result["reason"] = "journal_wal_present"
        return result
    paths = journals + [ROOT / "frozen_models_running/ig_index/carry_zrev_96_ig_spreadbet_v1/.runtime/fills.jsonl"]
    if not all(p.is_file() for p in paths):
        result["reason"] = "runtime_source_absent"
        return result
    handles = subprocess.run(["/usr/sbin/lsof", "-t", "--", *map(str, paths)], capture_output=True, text=True, timeout=10)
    result["open_handle_pids"] = sorted(set(handles.stdout.split()))
    result["lsof_returncode"] = handles.returncode
    result["lsof_stderr_present"] = bool(handles.stderr)
    if handles.returncode not in (0, 1) or handles.stderr or handles.stdout.strip():
        result["reason"] = "runtime_handles_or_probe_uncertain"
        return result
    result["runtime_sources_before"] = [{"path": str(p), "bytes": p.stat().st_size, "sha256": digest(p)} for p in paths]
    result["status"] = "PASS_NO_OBSERVED_ACTIVE_OWNER"
    result["scope"] = "Local process, existing runtime locks and file handles; not global session ownership proof. Locks retained through capture."
    return result


def summarize(receipt, body, start, end):
    rows = body.get("transactions")
    metadata = body.get("metadata")
    page = metadata.get("pageData", {}) if isinstance(metadata, dict) else {}
    valid = isinstance(rows, list) and all(isinstance(row, dict) for row in rows)
    rows = rows if valid else []
    expected_size = metadata.get("size") if isinstance(metadata, dict) else None
    full_page = (receipt.get("status") == "OBSERVED" and valid
                 and type(expected_size) is int and expected_size == len(rows)
                 and page.get("pageNumber") == 1
                 and page.get("totalPages") in ({0, 1} if not rows else {1})
                 and page.get("pageSize") in {0, len(rows)})
    utc = [row.get("dateUtc") for row in rows]
    parsed = []
    for value in utc:
        try:
            parsed.append(datetime.fromisoformat(value.replace("Z", "+00:00")).date().isoformat())
        except (ValueError, TypeError, AttributeError):
            parsed.append(None)
    inside = all(value is not None and start <= value <= end for value in parsed)
    dates = [value for value in utc if isinstance(value, str)]
    return {"label": receipt["label"], "requested_from": start, "requested_to": end,
            "page_metadata": metadata, "rows": len(rows), "rows_schema_valid": valid,
            "api_reports_complete_page": full_page, "date_utc_all_within_requested_dates": inside,
            "date_utc_unparseable_count": sum(value is None for value in parsed),
            "date_utc_raw_extent": [min(dates), max(dates)] if dates else None,
            "transaction_types": dict(Counter(str(row.get("transactionType")) for row in rows)),
            "currencies": dict(Counter(str(row.get("currency")) for row in rows)),
            "cash_transaction_values": dict(Counter(str(row.get("cashTransaction")) for row in rows)),
            "complete": full_page and inside,
            "scope": "API-reported rows for date-only query; not proof of lifetime history, actual fills, or per-model attribution."}


def main():
    if OUTPUT.exists() or CENTRAL.exists():
        raise RuntimeError("preserve_existing_capture")
    result = {"status": "NOT_EVALUABLE", "started_at": stamp(), "requested_dates_inclusive": list(FULL),
              "environment": "demo", "expected_account_key": ACCOUNT_KEY,
              "max_gets": 4, "max_retained_raw_bytes": CAP, "request_timeout_seconds": 25,
              "minimum_get_spacing_seconds": 14, "get_allowlist": ["/accounts", "/history/transactions"],
              "no_orders_submitted": True, "no_account_switch": True, "no_live_account_access": True,
              "no_activity_recapture": True, "no_model_cash_assignment": True,
              "authentication_bodies_or_headers_retained": False, "full_goal_satisfied": False,
              "ranges": [], "receipts": [], "get_count": 0}
    held = []
    reader = None
    try:
        if digest(SOURCE) != SOURCE_SHA:
            raise RuntimeError("inspected_reader_bytes_changed")
        if json.loads(PRIOR.read_text()).get("account_key") != ACCOUNT_KEY:
            raise RuntimeError("original_account_guard_changed")
        result["source_refs"] = [{"path": str(p), "sha256": digest(p)} for p in [SOURCE, PRIOR, Path(__file__)]]
        result["liveness"] = liveness(held)
        if result["liveness"]["status"] != "PASS_NO_OBSERVED_ACTIVE_OWNER":
            result["status"] = "DEFERRED_ACTIVE_OWNER_OR_UNCERTAIN"
            return
        if shutil.disk_usage(CENTRAL.parent).free < 100_000_000_000 or shutil.disk_usage(HERE).free < 1024**3:
            result["status"] = "DEFERRED_STORAGE_RESERVE"
            return
        spec = importlib.util.spec_from_file_location("retained_demo_reader", SOURCE)
        original = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(original)
        assert original.BASE == "https://demo-api.ig.com/gateway/deal"
        original.CENTRAL = CENTRAL
        original.LIMIT = CAP
        values = original.dotenv_values(ROOT / ".env")
        selected = os.environ.get("IG_ACCOUNT_ID") or values.get("IG_ACCOUNT_ID")
        identity = original.sha(original.canonical({"environment": "demo", "account_id": selected}))
        values.clear()
        selected = None
        if identity != ACCOUNT_KEY:
            result["status"] = "DEFERRED_CONFIGURED_ACCOUNT_MISMATCH"
            return
        CENTRAL.mkdir(mode=0o700)

        class CashReader(original.Reader):
            def get(self, path, params, version, label):
                if self.count >= 4:
                    raise RuntimeError("four_get_budget_exhausted")
                if path == "/accounts":
                    okay = not params and version == "1" and label == "accounts"
                elif path == "/history/transactions":
                    okay = (version == "2" and set(params) == {"type", "from", "to", "pageSize"}
                            and params["type"] == "ALL" and params["pageSize"] == 0
                            and (params["from"], params["to"]) in [FULL, *FALLBACK])
                else:
                    okay = False
                if not okay:
                    raise ValueError("narrow_cash_allowlist_rejected")
                return super().get(path, params, version, label)

        reader = CashReader()
        result["auth"] = reader.authenticate()
        if result["auth"]["status"] != "AUTHENTICATED":
            result["status"] = "AUTHENTICATION_UNAVAILABLE"
            return
        if reader.account_key != ACCOUNT_KEY:
            result["status"] = "ACCOUNT_IDENTITY_FAILED"
            return
        r, b = reader.get("/accounts", {}, "1", "accounts")
        chosen = [a for a in b.get("accounts", []) if a.get("accountId") == reader.headers["IG-ACCOUNT-ID"]]
        okay = (r["status"] == "OBSERVED" and len(chosen) == 1
                and chosen[0].get("accountType") == "SPREADBET" and chosen[0].get("currency") == "GBP")
        result["account_guard"] = {"status": "PASS" if okay else "FAIL", "account_key": reader.account_key,
                                   "account_type": chosen[0].get("accountType") if len(chosen) == 1 else None,
                                   "currency": chosen[0].get("currency") if len(chosen) == 1 else None}
        if not okay:
            result["status"] = "ACCOUNT_TYPE_OR_CURRENCY_FAILED"
            return

        def request(start, end, label):
            r, b = reader.get("/history/transactions", {"type": "ALL", "from": start, "to": end, "pageSize": 0}, "2", label)
            result["ranges"].append(summarize(r, b, start, end))
            return r

        r = request(*FULL, "cash_full_scope")
        if r.get("error_code") == "error.request.invalid.date-range":
            result["date_error_fallback_used"] = True
            for number, dates in enumerate(FALLBACK, 1):
                request(*dates, f"cash_half_{number}")
            required = result["ranges"][1:]
        else:
            result["date_error_fallback_used"] = False
            required = result["ranges"]
        complete = bool(required) and all(r["complete"] for r in required)
        result["required_range_labels"] = [r["label"] for r in required]
        result["complete_requested_scope_by_api_metadata"] = complete
        result["status"] = "COMPLETE_DEMO_CASH_SOURCE_EXTENSION" if complete else "PARTIAL_OR_UNAVAILABLE_DEMO_CASH_SOURCE"
    except Exception as exc:
        result["status"] = "DEFERRED_OR_FAILED"
        result["exception_type"] = type(exc).__name__
        # Do not serialize exception messages, HTTP requests or response headers.
    finally:
        if reader is not None:
            result["get_count"] = reader.count
            result["receipts"] = reader.receipts
            reader.headers = None
            reader.session.close()
        prior = result.get("liveness", {}).get("runtime_sources_before", [])
        result["runtime_sources_unchanged"] = all(Path(r["path"]).is_file() and digest(Path(r["path"])) == r["sha256"] for r in prior) if prior else None
        result["central_raw_bytes"] = sum(p.stat().st_size for p in CENTRAL.rglob("*") if p.is_file()) if CENTRAL.exists() else 0
        result["finished_at"] = stamp()
        result["limitations"] = ["Query dates are broker date-only arguments; source receipt time is current UTC.",
                                 "Account-level WITH and other cash rows remain unassigned to models.",
                                 "No historical unit schedule, entitlement reconstruction or full economics established."]
        if result["central_raw_bytes"] > CAP or result["get_count"] > 4:
            result["status"] = "BOUND_VIOLATION"
        save(OUTPUT, result)
        for handle in held:
            fcntl.flock(handle, fcntl.LOCK_UN)
            handle.close()
        print(json.dumps({"status": result["status"], "get_count": result["get_count"],
                          "central_raw_bytes": result["central_raw_bytes"], "metadata": str(OUTPUT)}), flush=True)


if __name__ == "__main__":
    main()
