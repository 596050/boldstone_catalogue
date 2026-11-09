"""Capture full daily vintages, compile unchanged rules and expose timed targets.

Both models use the last genuine source row. Execution is the first observed
tradeable quote after publication and the next regular session's 09:30 ET. This
deliberately versions the execution clock separately from both old simulations
and Carry96's synthetic next-row close schedule. Crash90 NEVER receives a dummy
close: its current-row return is an input to the hedge.
"""
from __future__ import annotations

import argparse
import inspect
import io
import json
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import research  # noqa: F401 - retained, explicitly resolved model dependencies
from backtest.iqfeed_panel import load_iqfeed_daily_panel
from frozen_models_running.ig_index.carry_zrev_96_ig_spreadbet_v1 import target_model as carry
from frozen_models_running.ig_index.carry_zrev_96_crash90_top1_ig_spreadbet_v1.historical_input import load_checkpoint, load_frozen_rule
from ib_gateway.strategy_research import BarPanel
from research.testing_stages.stage_01_data.iqfeed_refresh import SCHEMA, refresh
from utils.data_paths import resolve_path
from utils.trading.calendar import last_completed_session, next_nyse_session

from . import MODELS, VERSION
from .common import atomic_json, digest_bytes, digest_file, identity, parse_stamp, stamp, utcnow

NY = ZoneInfo("America/New_York")
BEGIN = "2011-01-03"
CRASH_PARENT_WARMUP = "2009-12-01"


def verify_rule_bindings():
    path = Path(__file__).with_name("RULE_BINDINGS.json")
    bindings = json.loads(path.read_text())
    if bindings["schema"] != "ig_pair_forward_rule_bindings.v1":
        raise ValueError("invalid rule binding manifest")
    for source, expected in bindings["files"].items():
        if digest_file(source) != expected:
            raise ValueError(f"pinned rule dependency changed; separately version the provider: {source}")
    return digest_file(path)


def implementation_files():
    """Pin loaded local transitive implementation files, not just the wrapper."""
    records = {}
    for name, module in list(sys.modules.items()):
        if name.startswith(("backtest.", "ib_gateway.", "frozen_models_running.",
                            "utils.ig_index.forward_pair_v1", "utils.trading.calendar")):
            path = getattr(module, "__file__", None)
            if path and path.endswith(".py"):
                records[str(Path(path).resolve())] = digest_file(path)
    return records


def capture(end=None, history_start=CRASH_PARENT_WARMUP):
    verify_rule_bindings()
    date.fromisoformat(history_start)
    if history_start > CRASH_PARENT_WARMUP:
        raise ValueError("capture must include the original Crash90 parent warm-up")
    end = end or last_completed_session()
    if end > last_completed_session():
        raise ValueError("cannot capture an unfinished daily session")
    root = resolve_path("research_artifacts", require_exists=True) / "ig_pair_forward_v1"
    token = utcnow().strftime("%Y%m%dT%H%M%S%fZ")
    folder = root / token
    folder.mkdir(parents=True, exist_ok=False)
    symbols = list(carry.iqfeed_spec.SIGNAL_UNIVERSE_SYMBOLS)
    manifest = {"schema": SCHEMA, "versions": str(folder / "raw_versions"),
                "entries": [{"symbol": symbol, "cadence": "daily", "history_start": history_start,
                             "path": str(folder / "raw" / (symbol + ".txt"))}
                            for symbol in symbols]}
    atomic_json(folder / "REQUEST.json", manifest)
    receipt = refresh(manifest, end, folder / "refresh", workers=2)
    # The collector uses the already authenticated IQConnect service. It does
    # not launch/reconfigure a service or mutate the shared source directories.
    failures = [x for x in receipt["entries"] if x.get("status") != "UPDATED" or x.get("last") != end]
    if len(receipt["entries"]) != len(symbols) or failures:
        raise RuntimeError(f"incomplete IQFeed capture; retained receipt: {folder / 'refresh/REFRESH.json'}")
    return compile_capture(folder)


def subset(panel, rows, columns=None):
    columns = list(range(len(panel.symbols))) if columns is None else columns
    ix = np.ix_(rows, columns)
    return BarPanel(symbols=[panel.symbols[x] for x in columns],
                    timestamps=[panel.timestamps[x] for x in rows],
                    days=[panel.days[x] for x in rows], day_index=np.arange(len(rows)),
                    **{k: np.asarray(getattr(panel, k)[ix]) for k in ("open", "high", "low", "close", "volume")})


def state_arrays(rule, base, close):
    shorts = rule.clip_short(base)
    mean, se, count = rule.expanding_signed_mean_se(shorts, close)
    return {"short_sum": rule.matured_signed_sum(shorts, close), "short_count": count,
            "short_mean": mean, "short_se": se,
            "short_last": rule.last_signed_interval(shorts, close),
            "long_loss_fraction": rule.last_loss_fraction(rule.clip_long(base), close)}


def compare_array(a, b):
    a, b = np.asarray(a), np.asarray(b)
    if a.shape != b.shape:
        return {"exact": False, "shape_mismatch": [list(a.shape), list(b.shape)]}
    finite = np.isfinite(a) & np.isfinite(b)
    eq = (a == b) | (np.isnan(a) & np.isnan(b))
    return {"exact": bool(np.all(eq)), "different_cells": int(np.sum(~eq)),
            "missingness_differences": int(np.sum(np.isfinite(a) != np.isfinite(b))),
            "max_abs_difference": float(np.max(np.abs(a[finite] - b[finite]))) if np.any(finite) else None}


def compile_capture(folder, receipt_path=None):
    rule_bindings_sha = verify_rule_bindings()
    folder = Path(folder).resolve()
    receipt_path = Path(receipt_path).resolve() if receipt_path is not None else folder / "refresh/REFRESH.json"
    receipt_path.relative_to(folder)
    receipt = json.loads(receipt_path.read_text())
    symbols = list(carry.iqfeed_spec.SIGNAL_UNIVERSE_SYMBOLS)
    entries = receipt["entries"]
    if sorted(x["symbol"] for x in entries) != sorted(symbols):
        raise ValueError("source receipt does not bind the exact 96-name roster")
    sources = {}
    observations = []
    source_receipts = {str(receipt_path): digest_file(receipt_path)}
    for observed_entry in entries:
        entry = observed_entry
        # Resuming a partial capture retains its failed receipt. The collector
        # reports unchanged successful files as CURRENT; bind their original
        # authenticated response clock through the hashed freshness record.
        if entry.get("status") == "CURRENT":
            previous = folder / "raw" / ("." + entry["symbol"] + ".txt.freshness.json")
            entry = json.loads(previous.read_text())
            if entry["sha256"] != observed_entry["sha256"]:
                raise ValueError("resumed source vintage differs from its response receipt")
            source_receipts[str(previous)] = digest_file(previous)
        path = folder / "raw" / (entry["symbol"] + ".txt")
        if (entry.get("status") != "UPDATED" or Path(entry["path"]).resolve() != path
                or entry.get("last") != receipt["requested_end"]
                or not entry.get("requested_begin") or entry["requested_begin"] > CRASH_PARENT_WARMUP
                or digest_file(path) != entry["sha256"]):
            raise ValueError("missing, changed or unbound authenticated source")
        observations.append(parse_stamp(entry["observed_at_utc"]))
        sources[str(path)] = entry["sha256"]
    before = implementation_files()
    raw = load_iqfeed_daily_panel(folder / "raw", min_rows=1)
    warm_rows = np.flatnonzero(np.asarray(raw.days) >= CRASH_PARENT_WARMUP).tolist()
    warm_panel = subset(raw, warm_rows, [raw.symbols.index(s) for s in symbols])
    if warm_panel.days[0] != CRASH_PARENT_WARMUP:
        raise ValueError("missing original Crash90 parent warm-up history")
    evaluation_rows = np.flatnonzero(np.asarray(warm_panel.days) >= BEGIN).tolist()
    panel = subset(warm_panel, evaluation_rows)
    if panel.days[0] != BEGIN or panel.days[-1] != receipt["requested_end"]:
        raise ValueError("panel endpoints differ from full-history source contract")
    if not np.all(np.isfinite(panel.close[-1]) & (panel.close[-1] > 0)):
        raise ValueError("incomplete last close")
    missing_recent = carry._missing_recent_completed_sessions(panel)
    if missing_recent:
        raise ValueError(f"recent session gaps change row-indexed rebalancing: {missing_recent}")
    weights = carry._candidate_positions(panel)
    old, provenance = load_checkpoint()
    if old["symbols"].tolist() != symbols:
        raise ValueError("checkpoint roster order differs")
    base = np.sign(weights).astype(np.int8)
    base[:, ~old["tradable"]] = 0
    # Original R09 parent uses the 2009-12-01 formula origin, then resets its
    # evaluation cash and short statistics at 2011-01-03. Current Carry96's
    # published source contract starts its formula at 2011. Keep both origins.
    crash_parent_weights = carry._candidate_positions(warm_panel)[evaluation_rows]
    crash_parent = np.sign(crash_parent_weights).astype(np.int8)
    crash_parent[:, ~old["tradable"]] = 0
    rule = load_frozen_rule()
    crash = rule.two_sided_long_crash90_top1(crash_parent, panel.close, require_last_win=True, hurdle=.90, warmup=60)
    states = state_arrays(rule, crash_parent, panel.close)
    old_base = old["desired_direction"].astype(np.int8).copy()
    old_base[:, ~old["tradable"]] = 0
    old_crash = rule.two_sided_long_crash90_top1(old_base, old["close"], require_last_win=True, hurdle=.90, warmup=60)
    old_states = state_arrays(rule, old_base, old["close"])
    new_dates = {d: i for i, d in enumerate(panel.days)}
    pairs = [(i, new_dates[str(d)]) for i, d in enumerate(old["days"]) if str(d) in new_dates]
    oi, ni = np.asarray(pairs).T
    comparisons = {"close": compare_array(old["close"][oi], panel.close[ni]),
                   "carry96_directions": compare_array(old_base[oi], base[ni]),
                   "crash90_parent_directions": compare_array(old_base[oi], crash_parent[ni]),
                   "crash90_directions": compare_array(old_crash[oi], crash[ni]),
                   **{key: compare_array(old_states[key][oi], states[key][ni]) for key in states}}
    common_days = [str(old["days"][i]) for i in oi]
    exact = len(pairs) == len(old["days"]) and all(x["exact"] for x in comparisons.values())
    # Independently recompile two prefixes to check that later closes do not
    # alter already issued rows. This is causal rule evidence, not vintage PIT.
    checks = []
    for length in sorted(set([min(len(old["days"]), len(panel.days)), len(panel.days) - 1])):
        prefix = subset(panel, list(range(length)))
        b = np.sign(carry._candidate_positions(prefix)).astype(np.int8)
        b[:, ~old["tradable"]] = 0
        warm_prefix = subset(warm_panel, np.flatnonzero(np.asarray(warm_panel.days) <= prefix.days[-1]).tolist())
        bp = np.sign(carry._candidate_positions(warm_prefix)[evaluation_rows[:length]]).astype(np.int8)
        bp[:, ~old["tradable"]] = 0
        c = rule.two_sided_long_crash90_top1(bp, prefix.close, require_last_win=True, hurdle=.90, warmup=60)
        ok = np.array_equal(b, base[:length]) and np.array_equal(bp, crash_parent[:length]) and np.array_equal(c, crash[:length])
        checks.append({"sessions": length, "unchanged": bool(ok)})
        if not ok:
            raise ValueError("prefix causality failed")
    after = implementation_files()
    if any(after.get(p) != sha for p, sha in before.items()):
        raise ValueError("model dependency changed during compilation")
    if any(digest_file(p) != sha for p, sha in sources.items()):
        raise ValueError("source changed during compilation")
    code_folder = folder / "implementation"
    code_folder.mkdir(exist_ok=False)
    code_archive = {}
    for path, sha in after.items():
        contents = Path(path).read_bytes()
        if digest_bytes(contents) != sha:
            raise ValueError("implementation changed before archival")
        saved = code_folder / (sha + ".py")
        if not saved.exists():
            with saved.open("xb") as stream:
                stream.write(contents)
        code_archive[path] = str(saved)
    arrays = {"days": np.asarray(panel.days), "symbols": np.asarray(symbols),
              **{k: getattr(panel, k) for k in ("open", "high", "low", "close", "volume")},
              "carry96_weights": weights, "carry96": base, "crash90": crash,
              "crash90_parent": crash_parent, "crash90_parent_weights": crash_parent_weights,
              "tradable": old["tradable"], **states}
    # Exclusive creation prevents silently replacing a published source/state.
    archive = folder / "PANEL_AND_STATE.npz"
    with archive.open("xb") as stream:
        np.savez_compressed(stream, **arrays)
    result = {"schema": "ig_pair_forward_provider.v1", "version": VERSION,
              "created_at": stamp(), "source_observed_at": max(observations).isoformat(),
              "source_vendor": "DTN_IQFeed_authenticated_IQConnect_HDT",
              "source_adjustments": "HDT split-adjusted complete requested vintage; no dividend total-return adjustment inferred",
              "historical_point_in_time_vintages": False,
              "source_files": sources, "source_receipt_sha256": digest_file(receipt_path),
              "source_receipts": source_receipts,
              "state_origins": {"carry96_formula": BEGIN, "crash90_parent_formula": CRASH_PARENT_WARMUP,
                                "crash90_short_statistics": BEGIN},
              "implementation_files": after, "archive_sha256": digest_file(archive),
              "implementation_archive": code_archive, "numpy_version": np.__version__,
              "rule_bindings_sha256": rule_bindings_sha,
              "first_day": panel.days[0], "last_day": panel.days[-1], "sessions": len(panel.days),
              "frozen_historical_comparator": provenance,
              "continuity": {"exact_numeric_continuity": exact,
                  "status": "EXACT_NUMERIC_CONTINUITY" if exact else "SEPARATE_SOURCE_REPLAY_REQUIRED",
                  "common_sessions": len(pairs), "missing_historical_sessions": sorted(set(old["days"].tolist()) - set(common_days)),
                  "extra_overlap_sessions": sorted(set(d for d in panel.days if d <= str(old["days"][-1])) - set(common_days)),
                  "comparisons": comparisons,
                  "corporate_action_semantics_equal": None,
                  "corporate_action_note": "Serialized old inputs do not prove equal split/dividend conventions. Numeric overlap alone is insufficient."},
              "prefix_checks": checks, "performance_evidence_inherited": False}
    result["provider_id"] = identity(result)
    atomic_json(folder / "PROVIDER.json", result)
    return folder


def load_provider(folder):
    folder = Path(folder)
    record = json.loads((folder / "PROVIDER.json").read_text())
    expected = record.pop("provider_id")
    if identity(record) != expected:
        raise ValueError("provider manifest identity mismatch")
    record["provider_id"] = expected
    data = (folder / "PANEL_AND_STATE.npz").read_bytes()
    if digest_bytes(data) != record["archive_sha256"]:
        raise ValueError("provider archive changed")
    with np.load(io.BytesIO(data), allow_pickle=False) as archive:
        arrays = {name: archive[name].copy() for name in archive.files}
    return record, arrays


def publish_targets(folder, model, output):
    if model not in MODELS:
        raise ValueError("unknown model")
    provider, arrays = load_provider(folder)
    now = utcnow()
    if provider["last_day"] != last_completed_session(now):
        raise ValueError("source is stale for forward publication")
    source_day = date.fromisoformat(provider["last_day"])
    # A conservative 16:10 close completion rule is safe on early-close days.
    # Market status is checked again at execution; no simulated quote is used.
    complete = datetime.combine(source_day, time(16, 10), NY)
    if now < complete or now < parse_stamp(provider["source_observed_at"]):
        raise ValueError("source not available at publication")
    earliest = datetime.combine(next_nyse_session(source_day), time(9, 30), NY)
    out = {"schema": "ig_pair_forward_target.v1", "version": VERSION, "model": model,
           "provider_id": provider["provider_id"], "source_folder": str(Path(folder).resolve()),
           "source_day": source_day.isoformat(), "rule_row_day": source_day.isoformat(),
           "source_observed_at": provider["source_observed_at"], "published_at": now.isoformat(),
           "not_before": max(now, earliest).isoformat(),
           "effective_session": earliest.date().isoformat(),
           "execution_contract": "first_observed_tradeable_quote_after_publication_and_next_session_open.v1",
           "schedule_change_from_old_adapter": True,
           "targets": dict(zip(arrays["symbols"].tolist(), arrays[model][-1].astype(float).tolist())),
           "reference_prices": dict(zip(arrays["symbols"].tolist(), arrays["close"][-1].tolist())),
           "performance_evidence_inherited": False}
    out["target_id"] = identity(out)
    output = Path(output)
    if output.exists():
        raise FileExistsError("target publication is immutable; use a new output")
    atomic_json(output, out, private=True)
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    cap = sub.add_parser("capture"); cap.add_argument("--end"); cap.add_argument("--history-start", default=CRASH_PARENT_WARMUP)
    comp = sub.add_parser("compile"); comp.add_argument("folder", type=Path); comp.add_argument("--receipt", type=Path)
    pub = sub.add_parser("publish"); pub.add_argument("folder", type=Path)
    pub.add_argument("--model", choices=MODELS, required=True)
    pub.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "capture":
        print(capture(args.end, args.history_start), flush=True)
    elif args.command == "compile":
        print(compile_capture(args.folder, args.receipt), flush=True)
    else:
        result = publish_targets(args.folder, args.model, args.output)
        print(json.dumps({k: result[k] for k in ("model", "target_id", "source_day", "not_before")}))


if __name__ == "__main__":
    main()
