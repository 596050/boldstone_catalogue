#!/usr/bin/env python3
"""Build the repository-root ``data_paths.json`` from external directory state.

The generator records legacy link targets before those links are removed.  On
later runs, absent ``missing_external`` entries are retained so unavailable
data is explicit rather than silently forgotten or represented by empty
directories.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from utils.data_paths import CONFIG_PATH, CONFIG_SCHEMA, CONFIGURED_DATA_ROOT
from utils.data_paths import resolve_data_path


ROOTS = {
    "data": "data",
    "raw": "data/raw",
    "raw_market": "data/raw/market",
    "raw_iqfeed": "data/raw/market/iqfeed",
    "raw_iqfeed_bars": "data/raw/market/iqfeed/bars",
    "raw_iqfeed_bars_daily": "data/raw/market/iqfeed/bars/daily",
    "raw_iqfeed_bars_intraday": "data/raw/market/iqfeed/bars/intraday",
    "raw_iqfeed_ticks": "data/raw/market/iqfeed/ticks",
    "raw_iqfeed_quotes": "data/raw/market/iqfeed/quotes",
    "raw_iqfeed_depth": "data/raw/market/iqfeed/depth",
    "raw_iqfeed_reference": "data/raw/market/iqfeed/reference",
    "raw_yahoo": "data/raw/market/yahoo",
    "raw_yahoo_bars": "data/raw/market/yahoo/bars",
    "raw_yahoo_actions": "data/raw/market/yahoo/actions",
    "raw_yahoo_fundamentals": "data/raw/market/yahoo/fundamentals",
    "raw_yahoo_metadata": "data/raw/market/yahoo/metadata",
    "raw_ibkr": "data/raw/market/ibkr",
    "raw_ibkr_bars": "data/raw/market/ibkr/bars",
    "raw_ibkr_quotes": "data/raw/market/ibkr/quotes",
    "raw_ibkr_trades": "data/raw/market/ibkr/trades",
    "raw_ibkr_depth": "data/raw/market/ibkr/depth",
    "raw_ibkr_reference": "data/raw/market/ibkr/reference",
    "raw_ig": "data/raw/broker/ig",
    "raw_ig_quotes": "data/raw/broker/ig/quotes",
    "raw_ig_fills": "data/raw/broker/ig/fills",
    "raw_ig_cash": "data/raw/broker/ig/cash",
    "raw_ig_funding": "data/raw/broker/ig/funding",
    "raw_ig_positions": "data/raw/broker/ig/positions",
    "raw_ig_markets": "data/raw/broker/ig/markets",
    "raw_other_market": "data/raw/market/other",
    "raw_non_price": "data/raw/non_price",
    "raw_non_price_corporate_actions": "data/raw/non_price/corporate_actions",
    "raw_non_price_sec": "data/raw/non_price/sec",
    "raw_non_price_finra": "data/raw/non_price/finra",
    "raw_non_price_nasdaq": "data/raw/non_price/nasdaq",
    "raw_non_price_cboe": "data/raw/non_price/cboe",
    "raw_non_price_macro": "data/raw/non_price/macro",
    "raw_non_price_news": "data/raw/non_price/news",
    "raw_non_price_fundamentals": "data/raw/non_price/fundamentals",
    "raw_non_price_reference": "data/raw/non_price/reference",
    "normalized": "data/normalized",
    "normalized_market": "data/normalized/market",
    "normalized_fundamentals": "data/normalized/fundamentals",
    "normalized_events": "data/normalized/events",
    "normalized_reference": "data/normalized/reference",
    "derived": "data/derived",
    "derived_features": "data/derived/features",
    "derived_labels": "data/derived/labels",
    "derived_panels": "data/derived/panels",
    "derived_factors": "data/derived/factors",
    "derived_execution": "data/derived/execution",
    "derived_diagnostics": "data/derived/diagnostics",
    "datasets": "data/datasets",
    "datasets_snapshots": "data/datasets/snapshots",
    "datasets_train": "data/datasets/train",
    "datasets_validation": "data/datasets/validation",
    "datasets_test": "data/datasets/test",
    "datasets_lockboxes": "data/datasets/lockboxes",
    "models": "data/models",
    "models_fitted": "data/models/fitted",
    "models_checkpoints": "data/models/checkpoints",
    "models_forecasts": "data/models/forecasts",
    "models_registries": "data/models/registries",
    "research": "data/research",
    "research_runs": "data/research/runs",
    "research_experiments": "data/research/experiments",
    "research_artifacts": "data/research/artifacts",
    "evidence": "data/evidence",
    "evidence_preregistrations": "data/evidence/preregistrations",
    "evidence_source_receipts": "data/evidence/source_receipts",
    "evidence_broker": "data/evidence/broker",
    "evidence_audits": "data/evidence/audits",
    "evidence_hashes": "data/evidence/hashes",
    "evidence_runtime": "data/evidence/runtime",
    "forward": "data/forward",
    "forward_market": "data/forward/market",
    "forward_broker": "data/forward/broker",
    "forward_predictions": "data/forward/predictions",
    "forward_evaluations": "data/forward/evaluations",
    "runtime": "data/runtime",
    "runtime_locks": "data/runtime/locks",
    "runtime_state": "data/runtime/state",
    "runtime_queues": "data/runtime/queues",
    "runtime_tmp": "data/runtime/tmp",
    "logs": "data/logs",
    "logs_collectors": "data/logs/collectors",
    "logs_legacy": "data/logs/legacy",
    "logs_models": "data/logs/models",
    "logs_research": "data/logs/research",
    "quarantine": "data/quarantine",
    "quarantine_incomplete": "data/quarantine/incomplete",
    "quarantine_corrupt": "data/quarantine/corrupt",
    "quarantine_rejected": "data/quarantine/rejected",
    "migration": "data/migration",
    "migration_inventories": "data/migration/inventories",
    "migration_receipts": "data/migration/receipts",
    "legacy": "data/legacy",
    "legacy_ibkr": "data/ibkr",
    "legacy_ig": "data/ig",
    "legacy_yahoo": "data/yahoo",
}

DATASET_SCAN_ROOTS = (
    "data/ibkr",
    "data/research",
    "data/ig",
    "data/yahoo",
    "data/forward",
)
STRUCTURAL_PATHS = frozenset(ROOTS.values())


def _load_previous(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if payload.get("schema") == CONFIG_SCHEMA else {}


def _entry_for(path: Path) -> tuple[str, dict[str, Any]]:
    relative = path.relative_to(CONFIGURED_DATA_ROOT)
    key = relative.as_posix()
    logical = Path(ROOTS["data"]) / relative
    entry: dict[str, Any] = {"path": logical.as_posix()}
    if path.is_symlink():
        raise RuntimeError(f"refusing external dataset symlink: {path}")
    entry["state"] = "local_directory"
    return key, entry


def build_config(output: Path = CONFIG_PATH) -> dict[str, Any]:
    previous = _load_previous(output)
    datasets: dict[str, dict[str, Any]] = {}
    for root_name in DATASET_SCAN_ROOTS:
        root = resolve_data_path(Path(Path(root_name).relative_to(ROOTS['data'])))
        if not root.is_dir():
            continue
        for path in sorted(root.iterdir()):
            if path.is_dir() or path.is_symlink():
                logical = (Path(ROOTS["data"]) / path.relative_to(CONFIGURED_DATA_ROOT)).as_posix()
                if logical in STRUCTURAL_PATHS:
                    continue
                key, entry = _entry_for(path)
                retained = dict(previous.get("datasets", {}).get(key, {}))
                retained.update(entry)
                entry = retained
                datasets[key] = entry

    special = resolve_data_path('ibkr_adr_home_fx_bbo_v1')
    if special.is_dir() or special.is_symlink():
        key, entry = _entry_for(special)
        retained = dict(previous.get("datasets", {}).get(key, {}))
        retained.update(entry)
        entry = retained
        datasets[key] = entry

    for key, entry in previous.get("datasets", {}).items():
        if key in datasets or entry.get("state") != "missing_external":
            continue
        retained = dict(entry)
        retained["state"] = "missing_external"
        retained["legacy_link_removed_by_local_centralization"] = True
        datasets[key] = retained

    state_counts = Counter(entry["state"] for entry in datasets.values())
    if not previous.get("external_storage") or not previous.get("data_root"):
        raise RuntimeError("existing v3 config is required to preserve external identity")
    return {
        "schema": CONFIG_SCHEMA,
        "data_root": previous["data_root"],
        "external_storage": previous["external_storage"],
        "path_policy": {
            "allow_absolute_paths": True,
            "allow_environment_override": False,
            "allow_symlinks": False,
            "configured_paths_must_be_below_data_root": True,
        },
        "roots": ROOTS,
        "dataset_scan_roots": list(DATASET_SCAN_ROOTS),
        "dataset_count": len(datasets),
        "dataset_state_counts": dict(sorted(state_counts.items())),
        "datasets": dict(sorted(datasets.items())),
        "migration": {
            "canonical_target": previous["data_root"],
            "missing_external_policy": "retain_config_entry_and_fail_before_data_read",
            "deferred_in_place": {
                ".runtime": "active collectors; migrate at controlled restart",
                "docs/research": "tracked or hash-bound research evidence; move only with retained-path versioning",
                "frozen_models_running": "frozen executable and model evidence; move only through a versioned successor",
                "logs": "active writers; migrate at controlled restart",
                "research/**/{*.npz,*.npy,*.jsonl}": "hash-bound or live experiment evidence; preserve exact paths until versioned",
                "runtime": "tracked frozen runtime evidence; requires a new retained-path release",
                "wave_decomposition_models/research/**/artifacts": "tracked result and fitted-model provenance; preserve exact paths until versioned",
                "research/**/.runtime": "embedded frozen or active evidence; migrate per trial version",
            },
        },
    }


def canonical_bytes(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode()


def create_configured_roots() -> int:
    """Create only the named structural roots; never dataset placeholders."""
    created = 0
    for value in ROOTS.values():
        path = resolve_data_path(Path(Path(value).relative_to(ROOTS['data'])))
        if path.is_symlink():
            raise RuntimeError(f"refusing configured root symlink: {value}")
        if not path.is_dir():
            path.mkdir(parents=True, exist_ok=True)
            created += 1
    return created


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=CONFIG_PATH)
    parser.add_argument("--check", action="store_true")
    parser.add_argument(
        "--create-roots",
        action="store_true",
        help="create configured structural roots, but never missing dataset directories",
    )
    args = parser.parse_args(argv)

    output = args.output if args.output.is_absolute() else REPO_ROOT / args.output
    created = create_configured_roots() if args.create_roots else 0
    payload = build_config(output)
    wanted = canonical_bytes(payload)
    if args.check:
        current = output.read_bytes() if output.is_file() else b""
        if current != wanted:
            print(f"stale data path config: {output}")
            return 1
        print(f"data path config is current: {output}")
        return 0

    temporary = output.with_suffix(output.suffix + f".tmp.{os.getpid()}")
    temporary.write_bytes(wanted)
    temporary.replace(output)
    print(
        f"wrote {output}: datasets={payload['dataset_count']} "
        f"states={payload['dataset_state_counts']} roots_created={created}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
