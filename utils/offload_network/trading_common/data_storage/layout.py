"""Canonical data/work layout for the live IQFeed/EMD storage tree."""
from __future__ import annotations

import datetime as dt
import os
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EXTERNAL_ROOT = Path("/Volumes/Untitled/famous_model")
DEFAULT_DATA_ROOT = DEFAULT_EXTERNAL_ROOT / "live_data"
DEFAULT_WORK_ROOT = REPO_ROOT / ".data_work"


def configured_data_root() -> Path:
    """Return the canonical external data root.

    `FAMOUS_MODEL_DATA_ROOT` is the preferred name. `EXTERNAL_DRIVE` remains
    supported as the mounted-drive root because the live refresh scripts
    already use it. When only `EXTERNAL_DRIVE` is set, live data lives under
    `$EXTERNAL_DRIVE/live_data`.
    """
    explicit = os.environ.get("FAMOUS_MODEL_DATA_ROOT")
    if explicit:
        return Path(explicit)
    external = os.environ.get("EXTERNAL_DRIVE")
    if external:
        return Path(external) / "live_data"
    return DEFAULT_DATA_ROOT


def configured_work_root() -> Path:
    return Path(os.environ.get("FAMOUS_MODEL_WORK_ROOT", str(DEFAULT_WORK_ROOT)))


@dataclass(frozen=True)
class DataLayout:
    root: Path = field(default_factory=configured_data_root)
    repo_root: Path = REPO_ROOT
    work_root: Path = field(default_factory=configured_work_root)

    @property
    def iqfeed_data(self) -> Path:
        return self.root / "iqfeed_data"

    @property
    def c_emd_results(self) -> Path:
        return self.root / "c_emd" / "results"

    @property
    def ig_trading(self) -> Path:
        return self.c_emd_results / "ig_trading"

    @property
    def incremental_emd_caches(self) -> Path:
        return self.c_emd_results / "incremental_emd_caches"

    @property
    def manifests(self) -> Path:
        return self.root / "manifests"

    @property
    def quarantine(self) -> Path:
        return self.root / "quarantine"

    @property
    def corrupt_quarantine(self) -> Path:
        return self.quarantine / "corrupt_or_incomplete"

    @property
    def pre_prune_quarantine(self) -> Path:
        return self.quarantine / "pre_prune"

    @property
    def runs_work(self) -> Path:
        return self.work_root / "runs"

    @property
    def tmp_work(self) -> Path:
        return self.work_root / "tmp"

    def ensure_runtime_dirs(self) -> None:
        for path in (
            self.manifests,
            self.corrupt_quarantine,
            self.pre_prune_quarantine,
            self.runs_work,
            self.tmp_work,
        ):
            path.mkdir(parents=True, exist_ok=True)


def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def generation_id(prefix: str = "run") -> str:
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{prefix}_{stamp}"
