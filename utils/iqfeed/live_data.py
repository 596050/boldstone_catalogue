"""Production-facing IQFeed Level 1 adapter for frozen paper execution.

This is intentionally independent of the historical capture script.  It feeds
the same receipt-timestamped store used by execution, watches the complete
frozen universe, and exposes fail-closed connection/delay/coverage state.
"""

from __future__ import annotations

import csv
import hashlib
import logging
import math
import socket
import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable, Iterable, Optional

from utils.trading.shared_market_data import MarketDataStore, market_data_store

logger = logging.getLogger(__name__)


IQFEED_PROTOCOL = "6.2"
IQFEED_PROVIDER = "iqfeed"
IQFEED_PROVIDER_VERSION = "iqfeed_level1_tcp_v1"
IQFEED_UPDATE_FIELDS = (
    "Symbol",
    "Bid",
    "Ask",
    "Bid Size",
    "Ask Size",
    "Bid Time",
    "Ask Time",
    "Bid Market Center",
    "Ask Market Center",
    "Most Recent Trade",
    "Most Recent Trade Size",
    "Most Recent Trade Time",
    "Most Recent Trade Date",
    "Most Recent Trade Market Center",
    "Total Volume",
    "Delay",
    "Restricted Code",
    "Message Contents",
)


class IQFeedLiveDataUnavailable(RuntimeError):
    """Raised when IQFeed cannot prove complete fresh live coverage."""


def _number(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


class IQFeedLevel1MarketData:
    """IQFeed TCP Level 1 client that writes quotes into ``MarketDataStore``."""

    provider = IQFEED_PROVIDER
    provider_version = IQFEED_PROVIDER_VERSION

    def __init__(
        self,
        *,
        host: str = "127.0.0.1",
        port: int = 5009,
        store: MarketDataStore = market_data_store,
        execution_adapter_id: Optional[str] = None,
        execution_adapter_version: Optional[str] = None,
        progress_log_interval_seconds: float = 2.0,
        force_refresh_after_seconds: float = 5.0,
        force_refresh_min_interval_seconds: float = 2.0,
        maintenance_check_interval_seconds: float = 0.5,
        stream_heartbeat_max_age_seconds: float = 5.0,
        invalid_quote_log_interval_seconds: float = 5.0,
        socket_factory: Optional[Callable[..., Any]] = None,
    ):
        self.host = str(host)
        self.port = int(port)
        self.store = store
        self.execution_adapter_id = execution_adapter_id
        self.execution_adapter_version = execution_adapter_version
        self.progress_log_interval_seconds = max(
            float(progress_log_interval_seconds), 0.0
        )
        self.force_refresh_after_seconds = max(float(force_refresh_after_seconds), 0.01)
        self.force_refresh_min_interval_seconds = max(
            float(force_refresh_min_interval_seconds), 0.01
        )
        self.maintenance_check_interval_seconds = max(
            float(maintenance_check_interval_seconds), 0.01
        )
        self.stream_heartbeat_max_age_seconds = max(
            float(stream_heartbeat_max_age_seconds), 0.01
        )
        self.invalid_quote_log_interval_seconds = max(
            float(invalid_quote_log_interval_seconds), 0.0
        )
        self.socket_factory = socket_factory or socket.create_connection
        self._socket = None
        self._reader_thread: Optional[threading.Thread] = None
        self._maintenance_thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._condition = threading.Condition()
        self._send_lock = threading.Lock()
        self._watched: set[str] = set()
        self._last_error: Optional[str] = None
        self._connected = False
        self._health_failure_latched = False
        self._metrics_lock = threading.Lock()
        self._stream_started_at_epoch = time.time()
        self._stream_started_at_monotonic = time.monotonic()
        self._lines_received = 0
        self._quote_events_received = 0
        self._invalid_quote_events_received = 0
        self._last_invalid_quote: Optional[dict[str, Any]] = None
        self._last_invalid_quote_log_by_symbol: dict[str, float] = {}
        self._last_validation_error_by_symbol: dict[str, str] = {}
        self._suppressed_invalid_quote_logs_by_symbol: dict[str, int] = {}
        self._invalid_quote_logs_suppressed = 0
        self._symbol_quote_events: dict[str, int] = {}
        self._first_quote_at_epoch: Optional[float] = None
        self._last_quote_at_epoch: Optional[float] = None
        self._last_line_at_epoch: Optional[float] = None
        self._last_line_at_monotonic: Optional[float] = None
        self._force_refresh_requests_sent = 0
        self._force_refresh_responses_received = 0
        self._last_force_refresh_by_symbol: dict[str, float] = {}
        self._pending_force_refresh_by_symbol: dict[str, float] = {}
        self._maintenance_symbols: set[str] = set()
        self._maintenance_max_age_seconds: Optional[float] = None
        self._active_force_refresh_after_seconds: Optional[float] = None

    def descriptor(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "provider_version": self.provider_version,
            "host": self.host,
            "port": self.port,
            "execution_adapter_id": self.execution_adapter_id,
            "execution_adapter_version": self.execution_adapter_version,
            "delivery_mode": "push_event_driven",
            "cache_mode": "latest_quote_per_symbol_replace",
            "progress_log_interval_seconds": self.progress_log_interval_seconds,
            "freshness_mode": "force_refresh_then_fail_closed",
            "force_refresh_after_seconds": self.force_refresh_after_seconds,
            "force_refresh_min_interval_seconds": self.force_refresh_min_interval_seconds,
            "maintenance_check_interval_seconds": self.maintenance_check_interval_seconds,
            "stream_heartbeat_max_age_seconds": self.stream_heartbeat_max_age_seconds,
            "invalid_quote_log_interval_seconds": (
                self.invalid_quote_log_interval_seconds
            ),
        }

    @staticmethod
    def _iso(epoch: Optional[float]) -> Optional[str]:
        if epoch is None:
            return None
        return datetime.fromtimestamp(epoch, timezone.utc).isoformat()

    def stream_statistics(self) -> dict[str, Any]:
        """Return a thread-safe snapshot of receipt counts for logs/reports."""

        with self._metrics_lock:
            elapsed = max(time.monotonic() - self._stream_started_at_monotonic, 0.0)
            now_monotonic = time.monotonic()
            quote_events = self._quote_events_received
            return {
                "delivery_mode": "push_event_driven",
                "cache_mode": "latest_quote_per_symbol_replace",
                "connected": bool(self._connected),
                "watched_symbol_count": len(self._watched),
                "lines_received": self._lines_received,
                "quote_events_received": quote_events,
                "invalid_quote_events_received": self._invalid_quote_events_received,
                "last_invalid_quote": self._last_invalid_quote,
                "invalid_quote_logs_suppressed": self._invalid_quote_logs_suppressed,
                "unique_symbols_updated": len(self._symbol_quote_events),
                "quote_events_by_symbol": dict(sorted(self._symbol_quote_events.items())),
                "stream_elapsed_seconds": elapsed,
                "quote_events_per_second": quote_events / elapsed if elapsed > 0.0 else 0.0,
                "stream_started_at_epoch": self._stream_started_at_epoch,
                "stream_started_at_iso": self._iso(self._stream_started_at_epoch),
                "first_quote_at_epoch": self._first_quote_at_epoch,
                "first_quote_at_iso": self._iso(self._first_quote_at_epoch),
                "last_quote_at_epoch": self._last_quote_at_epoch,
                "last_quote_at_iso": self._iso(self._last_quote_at_epoch),
                "last_stream_line_at_epoch": self._last_line_at_epoch,
                "last_stream_line_at_iso": self._iso(self._last_line_at_epoch),
                "stream_heartbeat_age_seconds": (
                    None
                    if self._last_line_at_monotonic is None
                    else max(0.0, now_monotonic - self._last_line_at_monotonic)
                ),
                "force_refresh_requests_sent": self._force_refresh_requests_sent,
                "force_refresh_responses_received": self._force_refresh_responses_received,
                "force_refresh_pending_symbols": sorted(
                    self._pending_force_refresh_by_symbol
                ),
                "freshness_maintenance_enabled": bool(self._maintenance_symbols),
                "freshness_maintenance_symbol_count": len(self._maintenance_symbols),
                "freshness_maintenance_max_age_seconds": self._maintenance_max_age_seconds,
                "active_force_refresh_after_seconds": (
                    self._active_force_refresh_after_seconds
                ),
                "last_error": self._last_error,
            }

    def _record_line(self) -> None:
        now_epoch = time.time()
        now_monotonic = time.monotonic()
        with self._metrics_lock:
            self._lines_received += 1
            self._last_line_at_epoch = now_epoch
            self._last_line_at_monotonic = now_monotonic

    def _record_quote_event(self, symbol: str) -> int:
        now = time.time()
        with self._metrics_lock:
            self._quote_events_received += 1
            self._symbol_quote_events[symbol] = self._symbol_quote_events.get(symbol, 0) + 1
            if symbol in self._pending_force_refresh_by_symbol:
                self._pending_force_refresh_by_symbol.pop(symbol, None)
                self._force_refresh_responses_received += 1
            if self._first_quote_at_epoch is None:
                self._first_quote_at_epoch = now
            self._last_quote_at_epoch = now
            return self._quote_events_received

    def _record_invalid_quote_event(self, diagnostic: dict[str, Any]) -> None:
        with self._metrics_lock:
            self._invalid_quote_events_received += 1
            self._last_invalid_quote = dict(diagnostic)

    def connect(self, timeout_seconds: float = 5.0) -> None:
        if self._connected:
            return
        logger.info(
            "IQFeed Level 1 connecting: endpoint=%s:%d protocol=%s "
            "delivery=push-event-driven cache=latest-per-symbol-replace",
            self.host,
            self.port,
            IQFEED_PROTOCOL,
        )
        self.store.clear_provider(self.provider)
        try:
            try:
                sock = self.socket_factory((self.host, self.port), timeout=float(timeout_seconds))
            except TypeError:
                # Deliberately supports a small injected fake factory in tests.
                sock = self.socket_factory((self.host, self.port), float(timeout_seconds))
            if hasattr(sock, "settimeout"):
                sock.settimeout(1.0)
            self._socket = sock
            self._connected = True
            self._health_failure_latched = False
            self.store.set_provider_health(
                self.provider,
                connected=True,
                live=True,
                delayed=False,
                provider_version=self.provider_version,
                host=self.host,
                port=self.port,
                execution_adapter_id=self.execution_adapter_id,
                execution_adapter_version=self.execution_adapter_version,
            )
            self._reader_thread = threading.Thread(
                target=self._read_loop,
                name="iqfeed-level1-reader",
                daemon=True,
            )
            self._reader_thread.start()
            self._send(f"S,SET PROTOCOL,{IQFEED_PROTOCOL}")
            self._send("S,SELECT UPDATE FIELDS," + ",".join(IQFEED_UPDATE_FIELDS))
            logger.info(
                "IQFeed Level 1 connected; reader thread active and waiting for every P/Q update"
            )
        except Exception as exc:
            self._mark_disconnected(f"connect_failed:{type(exc).__name__}:{exc}")
            raise IQFeedLiveDataUnavailable(
                f"Could not connect to IQFeed Level 1 at {self.host}:{self.port}: {exc}"
            ) from exc

    def _send(self, line: str) -> None:
        sock = self._socket
        if sock is None or not self._connected:
            raise IQFeedLiveDataUnavailable("IQFeed Level 1 socket is disconnected")
        payload = (line + "\r\n").encode("ascii")
        with self._send_lock:
            sock.sendall(payload)

    def watch(self, symbols: Iterable[str], *, refresh: bool = False) -> None:
        requested = sorted(
            {str(item).strip().upper() for item in symbols if str(item).strip()}
        )
        new_count = 0
        refreshed_count = 0
        for symbol in requested:
            if symbol in self._watched:
                if not refresh:
                    continue
                self._send("r" + symbol)
                refreshed_count += 1
            else:
                new_count += 1
            self._send("w" + symbol)
            self._watched.add(symbol)
        logger.info(
            "IQFeed watch requests sent: requested=%d new=%d refreshed=%d total_watched=%d",
            len(requested),
            new_count,
            refreshed_count,
            len(self._watched),
        )

    def force_refresh(self, symbols: Iterable[str]) -> list[str]:
        """Request a fresh IQFeed summary without removing the active watch."""

        now = time.monotonic()
        requested = sorted(
            {
                str(item).strip().upper()
                for item in symbols
                if str(item).strip().upper() in self._watched
            }
        )
        sent: list[str] = []
        for symbol in requested:
            with self._metrics_lock:
                last_request = self._last_force_refresh_by_symbol.get(symbol)
                if (
                    last_request is not None
                    and now - last_request < self.force_refresh_min_interval_seconds
                ):
                    continue
                self._last_force_refresh_by_symbol[symbol] = now
                self._pending_force_refresh_by_symbol[symbol] = now
                self._force_refresh_requests_sent += 1
            try:
                # IQFeed's Level 1 fSYMBOL command returns a fresh P summary
                # while preserving the existing streaming watch.
                self._send("f" + symbol)
            except Exception as exc:
                with self._metrics_lock:
                    self._pending_force_refresh_by_symbol.pop(symbol, None)
                self._mark_disconnected(
                    f"force_refresh_failed:{symbol}:{type(exc).__name__}:{exc}"
                )
                raise
            sent.append(symbol)
        if sent:
            logger.info(
                "IQFeed forced-summary refresh requested: symbols=%d first=%s last=%s",
                len(sent),
                sent[0],
                sent[-1],
            )
        return sent

    def _freshness_maintenance_cycle(self) -> list[str]:
        if not self._maintenance_symbols or not self._connected:
            return []
        metrics = self.stream_statistics()
        heartbeat_age = metrics.get("stream_heartbeat_age_seconds")
        if (
            heartbeat_age is not None
            and heartbeat_age > self.stream_heartbeat_max_age_seconds
        ):
            self._mark_disconnected(
                f"stream_heartbeat_stale:{heartbeat_age:.3f}s>"
                f"{self.stream_heartbeat_max_age_seconds:.3f}s"
            )
            return []

        refresh_after = self._active_force_refresh_after_seconds
        if refresh_after is None:
            return []
        due = []
        for symbol in sorted(self._maintenance_symbols):
            snapshot = self.store.quote_snapshot(symbol, provider=self.provider)
            age = None if snapshot is None else snapshot.get("age_seconds")
            # An invalid book is never routeable, even when freshly received.
            # Refresh it immediately instead of waiting for the ordinary age
            # threshold (which can be longer than the execution guard's
            # invalid-book grace period).
            invalid = snapshot is not None and not snapshot.get("valid_two_sided", False)
            if invalid or age is None or float(age) >= refresh_after:
                due.append(symbol)
        return self.force_refresh(due)

    def _freshness_maintenance_loop(self) -> None:
        while not self._stop.wait(self.maintenance_check_interval_seconds):
            try:
                self._freshness_maintenance_cycle()
            except Exception as exc:  # pragma: no cover - live socket safety net
                if not self._stop.is_set() and self._connected:
                    self._mark_disconnected(
                        f"freshness_maintenance_failed:{type(exc).__name__}:{exc}"
                    )
                return

    def start_freshness_maintenance(
        self,
        symbols: Iterable[str],
        *,
        max_age_seconds: float,
    ) -> dict[str, Any]:
        """Keep unchanged quotes provably fresh using IQFeed forced summaries."""

        required = {
            str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()
        }
        missing_watches = sorted(required - self._watched)
        if missing_watches:
            raise IQFeedLiveDataUnavailable(
                "Cannot maintain IQFeed freshness without active watches: "
                + ", ".join(missing_watches)
            )
        max_age = float(max_age_seconds)
        if max_age <= 0.0:
            raise ValueError("max_age_seconds must be positive")
        self._maintenance_symbols = required
        self._maintenance_max_age_seconds = max_age
        self._active_force_refresh_after_seconds = min(
            self.force_refresh_after_seconds,
            max(max_age * 0.5, 0.01),
        )
        if self._maintenance_thread is None or not self._maintenance_thread.is_alive():
            self._maintenance_thread = threading.Thread(
                target=self._freshness_maintenance_loop,
                name="iqfeed-freshness-maintenance",
                daemon=True,
            )
            self._maintenance_thread.start()
        summary = {
            "enabled": True,
            "mode": "iqfeed_forced_summary_refresh",
            "symbol_count": len(required),
            "max_age_seconds": max_age,
            "force_refresh_after_seconds": self._active_force_refresh_after_seconds,
            "force_refresh_min_interval_seconds": self.force_refresh_min_interval_seconds,
            "maintenance_check_interval_seconds": self.maintenance_check_interval_seconds,
            "stream_heartbeat_max_age_seconds": self.stream_heartbeat_max_age_seconds,
        }
        logger.info("IQFeed freshness maintenance started: %s", summary)
        return summary

    def _read_loop(self) -> None:
        buffer = b""
        try:
            while not self._stop.is_set():
                try:
                    chunk = self._socket.recv(65536)
                except socket.timeout:
                    continue
                except TimeoutError:
                    continue
                if not chunk:
                    if self._stop.is_set():
                        return
                    self._mark_disconnected("socket_eof")
                    return
                buffer += chunk
                while b"\n" in buffer:
                    raw, buffer = buffer.split(b"\n", 1)
                    line = raw.rstrip(b"\r").decode("utf-8", errors="replace")
                    if line:
                        self.handle_line(line)
        except Exception as exc:  # pragma: no cover - safety net around live socket
            if self._stop.is_set():
                return
            self._mark_disconnected(f"reader_failed:{type(exc).__name__}:{exc}")

    def _mark_disconnected(self, reason: str) -> None:
        self._connected = False
        self._last_error = str(reason)
        if reason != "adapter_shutdown":
            self._health_failure_latched = True
        self.store.set_provider_health(
            self.provider,
            connected=False,
            live=False,
            disconnect_reason=str(reason),
            provider_version=self.provider_version,
        )
        with self._condition:
            self._condition.notify_all()
        if reason != "adapter_shutdown":
            logger.warning("IQFeed Level 1 marked disconnected: %s", reason)

    def handle_line(self, line: str) -> None:
        """Parse one IQFeed protocol line (also the deterministic test seam)."""

        self._record_line()
        try:
            parts = next(csv.reader([line]))
        except (csv.Error, StopIteration) as exc:
            self.store.set_provider_health(self.provider, last_parse_error=str(exc))
            return
        if not parts:
            return
        message_type = parts[0]
        if message_type == "S":
            upper = line.upper()
            if "SERVER DISCONNECTED" in upper:
                self._mark_disconnected("server_disconnected")
            elif "SERVER CONNECTED" in upper and not self._health_failure_latched:
                self._connected = True
                self.store.set_provider_health(self.provider, connected=True, live=True)
            return
        if message_type == "T":
            metrics = self.stream_statistics()
            self.store.set_provider_health(
                self.provider,
                last_stream_timestamp=parts[1] if len(parts) > 1 else None,
                last_stream_line_at_epoch=metrics.get("last_stream_line_at_epoch"),
            )
            return
        if message_type in {"E", "n"}:
            reason = ",".join(parts[1:]) or "IQFeed protocol error"
            self._last_error = reason
            self.store.set_provider_health(self.provider, live=False, last_error=reason)
            with self._condition:
                self._condition.notify_all()
            return
        if message_type not in {"P", "Q"}:
            return

        values = parts[1:]
        if len(values) < len(IQFEED_UPDATE_FIELDS):
            values.extend([""] * (len(IQFEED_UPDATE_FIELDS) - len(values)))
        fields = dict(zip(IQFEED_UPDATE_FIELDS, values))
        symbol = str(fields.get("Symbol") or "").strip().upper()
        if not symbol:
            return
        delay_minutes = _number(fields.get("Delay"))
        is_delayed = bool(delay_minutes is not None and delay_minutes > 0.0)
        row = {
            "provider": self.provider,
            "provider_version": self.provider_version,
            "execution_adapter_id": self.execution_adapter_id,
            "execution_adapter_version": self.execution_adapter_version,
            "bid": _number(fields.get("Bid")),
            "ask": _number(fields.get("Ask")),
            "bid_size": _number(fields.get("Bid Size")),
            "ask_size": _number(fields.get("Ask Size")),
            "bid_market_center": fields.get("Bid Market Center") or None,
            "ask_market_center": fields.get("Ask Market Center") or None,
            "source_bid_time": fields.get("Bid Time") or None,
            "source_ask_time": fields.get("Ask Time") or None,
            "last": _number(fields.get("Most Recent Trade")),
            "last_size": _number(fields.get("Most Recent Trade Size")),
            "source_trade_time": fields.get("Most Recent Trade Time") or None,
            "source_trade_date": fields.get("Most Recent Trade Date") or None,
            "last_market_center": fields.get("Most Recent Trade Market Center") or None,
            "volume": _number(fields.get("Total Volume")),
            "delay_minutes": delay_minutes,
            "is_delayed": is_delayed,
            "restricted_code": fields.get("Restricted Code") or None,
            "message_contents": fields.get("Message Contents") or None,
            "iqfeed_message_type": message_type,
            "iqfeed_message_sha256": hashlib.sha256(line.encode("utf-8")).hexdigest(),
        }
        bid = row["bid"]
        ask = row["ask"]
        if bid is None or ask is None:
            validation_error = "missing_or_nonfinite_side"
        elif bid <= 0.0 or ask <= 0.0:
            validation_error = "nonpositive_side"
        elif bid == ask:
            validation_error = "locked_book"
        elif bid > ask:
            validation_error = "crossed_book"
        else:
            validation_error = None
        row["quote_validation_error"] = validation_error
        self.store.update_data(symbol, row)
        event_number = self._record_quote_event(symbol)
        logger.debug(
            "IQFeed quote event stored: event=%d symbol=%s type=%s bid=%s ask=%s",
            event_number,
            symbol,
            message_type,
            row["bid"],
            row["ask"],
        )
        if validation_error is not None:
            diagnostic = {
                "symbol": symbol,
                "message_type": message_type,
                "validation_error": validation_error,
                "bid": bid,
                "ask": ask,
                "bid_size": row["bid_size"],
                "ask_size": row["ask_size"],
                "bid_market_center": row["bid_market_center"],
                "ask_market_center": row["ask_market_center"],
                "source_bid_time": row["source_bid_time"],
                "source_ask_time": row["source_ask_time"],
                "message_contents": row["message_contents"],
                "iqfeed_message_sha256": row["iqfeed_message_sha256"],
            }
            self._record_invalid_quote_event(diagnostic)
            # Locked/crossed consolidated books can update hundreds of times a
            # second. Logging every row blocks the single reader thread, which
            # in turn makes unrelated symbols look stale and can create a
            # self-inflicted fleet halt. Preserve every row and metric, but
            # rate-limit the human-readable warning per symbol/error class.
            now_monotonic = time.monotonic()
            last_log = self._last_invalid_quote_log_by_symbol.get(symbol)
            previous_error = self._last_validation_error_by_symbol.get(symbol)
            should_log = bool(
                previous_error != validation_error
                or last_log is None
                or now_monotonic - last_log
                >= self.invalid_quote_log_interval_seconds
            )
            if should_log:
                suppressed = self._suppressed_invalid_quote_logs_by_symbol.pop(
                    symbol, 0
                )
                if suppressed:
                    diagnostic["suppressed_since_last_log"] = suppressed
                logger.warning("IQFeed invalid quote received: %s", diagnostic)
                self._last_invalid_quote_log_by_symbol[symbol] = now_monotonic
            else:
                self._invalid_quote_logs_suppressed += 1
                self._suppressed_invalid_quote_logs_by_symbol[symbol] = (
                    self._suppressed_invalid_quote_logs_by_symbol.get(symbol, 0) + 1
                )
            self._last_validation_error_by_symbol[symbol] = validation_error
            # The cache deliberately retains the invalid book so routing stays
            # fail-closed.  A summary request is merely an immediate recovery
            # attempt and cannot authorize an order until a valid row arrives.
            if symbol in self._watched and self._connected and self._socket is not None:
                self.force_refresh([symbol])
        else:
            # A recovered book should make the next invalid episode visible
            # immediately, even when it begins inside the ordinary log interval.
            self._last_validation_error_by_symbol.pop(symbol, None)
        if is_delayed:
            self.store.set_provider_health(
                self.provider,
                live=False,
                delayed=True,
                delayed_symbol=symbol,
                delay_minutes=delay_minutes,
            )
        with self._condition:
            self._condition.notify_all()

    def require_live_quotes(
        self,
        symbols: Iterable[str],
        *,
        timeout_seconds: float = 15.0,
        max_age_seconds: float = 10.0,
    ) -> dict[str, Any]:
        required = sorted({str(symbol).strip().upper() for symbol in symbols})
        if not required:
            raise IQFeedLiveDataUnavailable("IQFeed preflight requires at least one symbol")
        self.connect(timeout_seconds=min(max(float(timeout_seconds), 0.1), 5.0))
        # A watch request produces a fresh summary.  Discard any earlier probe
        # rows so every preflight pass proves receipt during this pass.
        self.store.remove_symbols(required, provider=self.provider)
        self.watch(required, refresh=True)
        phase_started_at = time.monotonic()
        phase_start_events = self.stream_statistics()["quote_events_received"]
        logger.info(
            "IQFeed fresh-quote gate started: required=%d timeout=%.1fs max_age=%.1fs; "
            "cached rows for this gate were cleared first",
            len(required),
            float(timeout_seconds),
            float(max_age_seconds),
        )
        deadline = time.monotonic() + max(float(timeout_seconds), 0.0)
        last_coverage = None
        next_progress_log = phase_started_at
        while True:
            last_coverage = self.store.coverage(
                required,
                provider=self.provider,
                max_age_seconds=max_age_seconds,
            )
            if last_coverage["passed"]:
                self.store.set_provider_health(
                    self.provider,
                    connected=True,
                    live=True,
                    delayed=False,
                    coverage_count=len(required),
                )
                final_coverage = self.store.coverage(
                    required,
                    provider=self.provider,
                    max_age_seconds=max_age_seconds,
                )
                metrics = self.stream_statistics()
                phase_elapsed = max(time.monotonic() - phase_started_at, 0.0)
                phase_events = metrics["quote_events_received"] - phase_start_events
                logger.info(
                    "IQFeed fresh-quote gate passed: valid=%d/%d quote_events=%d "
                    "elapsed=%.3fs event_rate=%.1f/s",
                    final_coverage["valid_count"],
                    final_coverage["required_count"],
                    phase_events,
                    phase_elapsed,
                    phase_events / phase_elapsed if phase_elapsed > 0.0 else 0.0,
                )
                return final_coverage
            health = last_coverage.get("provider_health") or {}
            if not health.get("connected"):
                raise IQFeedLiveDataUnavailable(
                    "IQFeed disconnected during preflight: "
                    + str(health.get("disconnect_reason") or self._last_error or "unknown")
                )
            if health.get("live") is False and self._last_error:
                raise IQFeedLiveDataUnavailable(
                    "IQFeed reported a protocol/entitlement error during preflight: "
                    + self._last_error
                )
            if last_coverage["delayed_symbols"] or health.get("delayed"):
                raise IQFeedLiveDataUnavailable(
                    "IQFeed returned delayed quotes; frozen execution requires live data: "
                    + ", ".join(last_coverage["delayed_symbols"] or [str(health.get("delayed_symbol"))])
                )
            now = time.monotonic()
            if (
                self.progress_log_interval_seconds > 0.0
                and now >= next_progress_log
            ):
                metrics = self.stream_statistics()
                phase_events = metrics["quote_events_received"] - phase_start_events
                phase_elapsed = max(now - phase_started_at, 0.0)
                logger.info(
                    "IQFeed coverage progress: valid=%d/%d missing=%d stale=%d "
                    "delayed=%d invalid=%d quote_events=%d event_rate=%.1f/s",
                    last_coverage["valid_count"],
                    last_coverage["required_count"],
                    len(last_coverage["missing_symbols"]),
                    len(last_coverage["stale_symbols"]),
                    len(last_coverage["delayed_symbols"]),
                    len(last_coverage["invalid_symbols"]),
                    phase_events,
                    phase_events / phase_elapsed if phase_elapsed > 0.0 else 0.0,
                )
                next_progress_log = now + self.progress_log_interval_seconds
            remaining = deadline - time.monotonic()
            if remaining <= 0.0:
                raise IQFeedLiveDataUnavailable(
                    "IQFeed all-symbol entitlement/live-quote preflight failed: "
                    f"valid={last_coverage['valid_count']}/{last_coverage['required_count']}; "
                    f"missing={last_coverage['missing_symbols']}; "
                    f"stale={last_coverage['stale_symbols']}; "
                    f"invalid={last_coverage['invalid_symbols']}; "
                    f"last_error={self._last_error}"
                )
            with self._condition:
                self._condition.wait(timeout=min(0.1, remaining))

    def shutdown(self) -> None:
        self._stop.set()
        if (
            self._maintenance_thread
            and self._maintenance_thread is not threading.current_thread()
        ):
            self._maintenance_thread.join(timeout=2.0)
        sock = self._socket
        if sock is not None:
            for symbol in sorted(self._watched):
                try:
                    self._send("r" + symbol)
                except Exception:
                    break
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                sock.close()
            except Exception:
                pass
        if self._reader_thread and self._reader_thread is not threading.current_thread():
            self._reader_thread.join(timeout=2.0)
        self._socket = None
        metrics = self.stream_statistics()
        logger.info(
            "IQFeed Level 1 stopped: quote_events=%d unique_symbols=%d "
            "forced_refreshes=%d confirmed_refreshes=%d stream_elapsed=%.3fs "
            "average_event_rate=%.1f/s",
            metrics["quote_events_received"],
            metrics["unique_symbols_updated"],
            metrics["force_refresh_requests_sent"],
            metrics["force_refresh_responses_received"],
            metrics["stream_elapsed_seconds"],
            metrics["quote_events_per_second"],
        )
        self._mark_disconnected("adapter_shutdown")
