"""Thread-safe, provider-aware Level 1 market-data ledger.

The legacy store only cached the latest dictionary for each symbol.  Frozen
execution needs stronger semantics: local receipt time (independent of an
exchange clock), explicit provider identity, feed health, freshness/coverage
queries, and immutable quote snapshot identifiers that can be linked to orders
and fills.

``get_data`` remains backwards compatible for the generic/legacy market maker.
Frozen runners should use ``quote_snapshot`` and ``coverage``.
"""

from __future__ import annotations

import hashlib
import json
import math
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional


QUOTE_SNAPSHOT_SCHEMA = "market_data_quote_snapshot.v1"
PROVIDER_HEALTH_SCHEMA = "market_data_provider_health.v1"


def _finite_number(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _positive_number(value: Any) -> Optional[float]:
    number = _finite_number(value)
    return number if number is not None and number > 0.0 else None


def _json_safe(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return str(value)


class MarketDataStore:
    """Latest-quote store with process-local receipt and feed-health state."""

    def __init__(self):
        self.data: Dict[str, Dict[str, Any]] = {}
        self.lock = threading.RLock()
        self._provider_health: Dict[str, Dict[str, Any]] = {}
        self._sequence = 0

    @staticmethod
    def _symbol(symbol: str) -> str:
        return str(symbol).strip().upper()

    @staticmethod
    def _provider(provider: Optional[str]) -> Optional[str]:
        if provider is None:
            return None
        normalized = str(provider).strip().lower()
        return normalized or None

    def clear(self) -> None:
        """Clear quotes and provider health (primarily for controlled tests)."""

        with self.lock:
            self.data.clear()
            self._provider_health.clear()
            self._sequence = 0

    def clear_provider(self, provider: str) -> None:
        """Remove cached rows and health belonging to one provider session."""

        key = self._provider(provider)
        if key is None:
            raise ValueError("market-data provider cannot be blank")
        with self.lock:
            self.data = {
                symbol: row
                for symbol, row in self.data.items()
                if self._provider(row.get("provider")) != key
            }
            self._provider_health.pop(key, None)

    def remove_symbols(self, symbols: Iterable[str], *, provider: Optional[str] = None) -> None:
        """Remove selected cached quotes, optionally only from one provider."""

        required_provider = self._provider(provider)
        keys = {self._symbol(symbol) for symbol in symbols}
        with self.lock:
            for key in keys:
                row = self.data.get(key)
                if row is None:
                    continue
                if required_provider is None or self._provider(row.get("provider")) == required_provider:
                    self.data.pop(key, None)

    def update_data(
        self,
        symbol: str,
        data: Dict[str, Any],
        *,
        merge: bool = False,
        received_at_epoch: Optional[float] = None,
        received_at_monotonic: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Store a quote and stamp when this process actually received it.

        Callers cannot smuggle a stale receipt time inside ``data``: receipt
        fields are always overwritten.  Explicit timestamp keyword arguments
        exist for deterministic replay/tests and should not be populated from
        an upstream exchange timestamp.
        """

        key = self._symbol(symbol)
        now_epoch = time.time() if received_at_epoch is None else float(received_at_epoch)
        now_monotonic = (
            time.monotonic() if received_at_monotonic is None else float(received_at_monotonic)
        )
        with self.lock:
            row = dict(self.data.get(key, {})) if merge else {}
            row.update(dict(data))
            provider = self._provider(row.get("provider"))
            if provider is not None:
                row["provider"] = provider
            row.update(
                {
                    "symbol": key,
                    "received_at_epoch": now_epoch,
                    "received_at_monotonic": now_monotonic,
                    "received_at_iso": datetime.fromtimestamp(now_epoch, timezone.utc).isoformat(),
                    "receipt_sequence": self._sequence,
                }
            )
            self._sequence += 1
            self.data[key] = row
            return dict(row)

    def get_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Return a copy of the latest raw row for backwards compatibility."""

        with self.lock:
            row = self.data.get(self._symbol(symbol))
            return dict(row) if row is not None else None

    def get_symbols(self) -> list[str]:
        with self.lock:
            return sorted(self.data)

    def set_provider_health(self, provider: str, **status: Any) -> Dict[str, Any]:
        """Update explicit feed health without erasing prior diagnostic fields."""

        key = self._provider(provider)
        if key is None:
            raise ValueError("market-data provider cannot be blank")
        now_epoch = time.time()
        with self.lock:
            row = dict(self._provider_health.get(key, {}))
            row.update(status)
            row.update(
                {
                    "schema": PROVIDER_HEALTH_SCHEMA,
                    "provider": key,
                    "updated_at_epoch": now_epoch,
                    "updated_at_iso": datetime.fromtimestamp(now_epoch, timezone.utc).isoformat(),
                }
            )
            self._provider_health[key] = row
            return _json_safe(dict(row))

    def get_provider_health(self, provider: str) -> Optional[Dict[str, Any]]:
        key = self._provider(provider)
        if key is None:
            return None
        with self.lock:
            row = self._provider_health.get(key)
            return _json_safe(dict(row)) if row is not None else None

    def quote_snapshot(
        self,
        symbol: str,
        *,
        provider: Optional[str] = None,
        max_age_seconds: Optional[float] = None,
        require_fresh: bool = False,
        now_monotonic: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        """Return a JSON-safe immutable description of the current quote.

        The hash covers the stored quote and original receipt metadata.  The
        computed ``age_seconds``/``fresh`` fields are observations made when the
        snapshot is requested and are deliberately excluded from the ID.
        """

        expected_provider = self._provider(provider)
        key = self._symbol(symbol)
        with self.lock:
            source = self.data.get(key)
            row = dict(source) if source is not None else None
        if row is None:
            return None

        receipt_monotonic = _finite_number(row.get("received_at_monotonic"))
        observed_monotonic = time.monotonic() if now_monotonic is None else float(now_monotonic)
        age_seconds = (
            max(0.0, observed_monotonic - receipt_monotonic)
            if receipt_monotonic is not None
            else None
        )
        actual_provider = self._provider(row.get("provider"))
        provider_matches = expected_provider is None or actual_provider == expected_provider
        bid = _positive_number(row.get("bid"))
        ask = _positive_number(row.get("ask"))
        valid_two_sided = bid is not None and ask is not None and bid < ask
        delay_minutes = _finite_number(row.get("delay_minutes"))
        delayed = bool(row.get("is_delayed")) or (
            delay_minutes is not None and delay_minutes > 0.0
        )
        fresh = (
            age_seconds is not None
            and (max_age_seconds is None or age_seconds <= float(max_age_seconds))
        )

        immutable = {
            "schema": QUOTE_SNAPSHOT_SCHEMA,
            **_json_safe(row),
            "provider": actual_provider,
            "bid": bid,
            "ask": ask,
            "bid_size": _positive_number(row.get("bid_size")),
            "ask_size": _positive_number(row.get("ask_size")),
            "delay_minutes": delay_minutes,
            "is_delayed": delayed,
        }
        # Monotonic values are meaningful only inside this process and should
        # not be emitted as externally comparable provenance.
        immutable.pop("received_at_monotonic", None)
        canonical = json.dumps(immutable, sort_keys=True, separators=(",", ":"), allow_nan=False)
        snapshot_id = "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        snapshot = {
            **immutable,
            "quote_snapshot_id": snapshot_id,
            "observed_at_epoch": time.time(),
            "observed_at_iso": datetime.now(timezone.utc).isoformat(),
            "age_seconds": age_seconds,
            "max_age_seconds": max_age_seconds,
            "fresh": fresh,
            "valid_two_sided": valid_two_sided,
            "provider_matches": provider_matches,
        }
        if require_fresh and not (fresh and valid_two_sided and provider_matches and not delayed):
            return None
        return snapshot

    def coverage(
        self,
        symbols: Iterable[str],
        *,
        provider: str,
        max_age_seconds: float,
        now_monotonic: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Evaluate complete, live, fresh two-sided coverage for a universe."""

        expected_provider = self._provider(provider)
        if expected_provider is None:
            raise ValueError("coverage requires an explicit provider")
        required = sorted({self._symbol(symbol) for symbol in symbols})
        valid: list[str] = []
        missing: list[str] = []
        stale: list[str] = []
        delayed: list[str] = []
        invalid: list[str] = []
        invalid_quote_snapshots: Dict[str, Dict[str, Any]] = {}
        provider_mismatch: list[str] = []
        ages: Dict[str, Optional[float]] = {}
        for symbol in required:
            snapshot = self.quote_snapshot(
                symbol,
                provider=expected_provider,
                max_age_seconds=max_age_seconds,
                now_monotonic=now_monotonic,
            )
            if snapshot is None:
                missing.append(symbol)
                continue
            ages[symbol] = snapshot.get("age_seconds")
            failed = False
            if not snapshot["provider_matches"]:
                provider_mismatch.append(symbol)
                failed = True
            if snapshot["is_delayed"]:
                delayed.append(symbol)
                failed = True
            if not snapshot["valid_two_sided"]:
                invalid.append(symbol)
                # Retain the exact bad book that caused the decision.  Older
                # coverage reports named the symbol but discarded bid/ask and
                # protocol provenance, which made a zero, locked, crossed, or
                # parsing failure indistinguishable after the fact.
                invalid_quote_snapshots[symbol] = snapshot
                failed = True
            if not snapshot["fresh"]:
                stale.append(symbol)
                failed = True
            if not failed:
                valid.append(symbol)

        health = self.get_provider_health(expected_provider)
        provider_connected = bool(health and health.get("connected"))
        provider_live = bool(health and health.get("live", True))
        provider_delayed = bool(health and health.get("delayed"))
        passed = bool(
            required
            and len(valid) == len(required)
            and provider_connected
            and provider_live
            and not provider_delayed
        )
        return {
            "provider": expected_provider,
            "max_age_seconds": float(max_age_seconds),
            "required_count": len(required),
            "valid_count": len(valid),
            "required_symbols": required,
            "valid_symbols": valid,
            "missing_symbols": missing,
            "stale_symbols": stale,
            "delayed_symbols": delayed,
            "invalid_symbols": invalid,
            "invalid_quote_snapshots": invalid_quote_snapshots,
            "provider_mismatch_symbols": provider_mismatch,
            "age_seconds_by_symbol": ages,
            "provider_health": health,
            "passed": passed,
        }


market_data_store = MarketDataStore()
