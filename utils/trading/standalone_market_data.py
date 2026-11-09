# standalone_market_data.py
import logging
import math
import threading
import time
from typing import Dict, Iterable, Optional
from ib_insync import IB, Contract, Ticker
from utils.trading.shared_market_data import MarketDataStore, market_data_store

logger = logging.getLogger('StandaloneMarketData')


MARKET_DATA_PERMISSION_ERROR_CODES = frozenset({354, 10089, 10167, 10189, 10197})


class LiveMarketDataUnavailable(RuntimeError):
    """Raised before order startup when IBKR live quotes are unavailable."""


class StandaloneMarketData:
    """IBKR Level 1 adapter feeding the shared provider-aware quote store."""

    PROVIDER = "ibkr"
    PROVIDER_VERSION = "ibkr_l1_v1"

    def __init__(
        self,
        ib: IB,
        *,
        store: MarketDataStore = market_data_store,
        execution_adapter_id: Optional[str] = None,
        execution_adapter_version: Optional[str] = None,
    ):
        self.ib = ib
        self.store = store
        self.execution_adapter_id = execution_adapter_id
        self.execution_adapter_version = execution_adapter_version
        self.tickers: Dict[str, Ticker] = {}
        self.api_errors = []
        self._error_lock = threading.Lock()
        self.ib.pendingTickersEvent += self._on_pending_tickers
        self.ib.errorEvent += self._on_error
        self.store.set_provider_health(
            self.PROVIDER,
            connected=True,
            live=True,
            delayed=False,
            provider_version=self.PROVIDER_VERSION,
            execution_adapter_id=self.execution_adapter_id,
            execution_adapter_version=self.execution_adapter_version,
        )
        logger.info("StandaloneMarketData initialized")

    def _on_error(self, req_id, error_code, error_string, contract):
        try:
            code = int(error_code)
        except (TypeError, ValueError):
            return
        if code not in MARKET_DATA_PERMISSION_ERROR_CODES:
            return
        row = {
            "req_id": req_id,
            "code": code,
            "message": str(error_string),
            "symbol": getattr(contract, "symbol", None),
        }
        with self._error_lock:
            self.api_errors.append(row)
        self.store.set_provider_health(
            self.PROVIDER,
            live=False,
            last_error=row,
        )

    def _ticker_data(self, ticker: Ticker):
        market_data_type = int(getattr(ticker, "marketDataType", 0) or 0)
        return {
            "provider": self.PROVIDER,
            "provider_version": self.PROVIDER_VERSION,
            "execution_adapter_id": self.execution_adapter_id,
            "execution_adapter_version": self.execution_adapter_version,
            "bid": getattr(ticker, "bid", None),
            "ask": getattr(ticker, "ask", None),
            "bid_size": getattr(ticker, "bidSize", None),
            "ask_size": getattr(ticker, "askSize", None),
            "bid_market_center": getattr(ticker, "bidExchange", None),
            "ask_market_center": getattr(ticker, "askExchange", None),
            "last": getattr(ticker, "last", None),
            "volume": getattr(ticker, "volume", None),
            "high": getattr(ticker, "high", None),
            "low": getattr(ticker, "low", None),
            "close": getattr(ticker, "close", None),
            "source_time": getattr(ticker, "time", None),
            "market_data_type": market_data_type,
            "delay_minutes": None,
            "is_delayed": market_data_type in (3, 4),
        }

    def _store_ticker(self, ticker: Ticker):
        symbol = str(ticker.contract.symbol).upper()
        return self.store.update_data(symbol, self._ticker_data(ticker))

    def _on_pending_tickers(self, tickers):
        for ticker in tickers:
            self._store_ticker(ticker)

    def request_market_data(self, contract: Contract):
        symbol = contract.symbol
        if symbol not in self.tickers:
            ticker = self.ib.reqMktData(contract, '', False, False)
            self.tickers[symbol] = ticker
            # Fake/test clients and some already-warmed ib_insync ticker objects
            # can be populated synchronously.  Record that first observation
            # once; subsequent receipt timestamps come only from ticker events.
            bid = self._positive(getattr(ticker, "bid", None))
            ask = self._positive(getattr(ticker, "ask", None))
            if bid is not None and ask is not None and bid < ask:
                self._store_ticker(ticker)
            logger.info(f"Subscribed to market data for {symbol}")
        else:
            logger.warning(f"Already subscribed to {symbol}")

    @staticmethod
    def _positive(value):
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if math.isfinite(number) and number > 0.0 else None

    def require_live_quote(self, symbol: str, timeout_seconds: float = 5.0):
        """Wait for one verified live two-sided quote or fail before orders start."""

        symbol = str(symbol).upper()
        if symbol not in self.tickers:
            raise LiveMarketDataUnavailable(
                f"live market-data preflight has no subscription for {symbol}"
            )
        timeout_seconds = max(float(timeout_seconds), 0.0)
        deadline = time.monotonic() + timeout_seconds
        ticker = self.tickers[symbol]

        while True:
            with self._error_lock:
                permission_errors = [
                    row
                    for row in self.api_errors
                    if row["symbol"] in (None, symbol)
                ]
            if permission_errors:
                error = permission_errors[0]
                raise LiveMarketDataUnavailable(
                    f"IBKR live API market data is unavailable for {symbol}: "
                    f"error {error['code']} ({error['message']}). Enable/share the "
                    "required real-time market-data subscription with the paper "
                    "account; delayed data is not accepted for this runner."
                )

            market_data_type = int(getattr(ticker, "marketDataType", 0) or 0)
            bid = self._positive(getattr(ticker, "bid", None))
            ask = self._positive(getattr(ticker, "ask", None))
            if market_data_type == 1 and bid is not None and ask is not None and bid < ask:
                if self.store.get_data(symbol) is None:
                    self._store_ticker(ticker)
                self.store.set_provider_health(
                    self.PROVIDER,
                    connected=True,
                    live=True,
                    delayed=False,
                    provider_version=self.PROVIDER_VERSION,
                )
                logger.info(
                    "Verified live IBKR market data for %s: bid=%s ask=%s",
                    symbol,
                    bid,
                    ask,
                )
                return ticker

            remaining = deadline - time.monotonic()
            if remaining <= 0.0:
                type_name = {1: "LIVE", 2: "FROZEN", 3: "DELAYED", 4: "DELAYED-FROZEN"}.get(
                    market_data_type, f"UNKNOWN({market_data_type})"
                )
                raise LiveMarketDataUnavailable(
                    f"IBKR live market-data preflight timed out for {symbol}: "
                    f"marketDataType={type_name}, bid={getattr(ticker, 'bid', None)}, "
                    f"ask={getattr(ticker, 'ask', None)}. The order loop was not started."
                )
            self.ib.sleep(min(0.1, remaining))

    def require_live_quotes(
        self,
        symbols: Iterable[str],
        *,
        timeout_seconds: float = 10.0,
        max_age_seconds: float = 10.0,
    ):
        """Require fresh live two-sided IBKR quotes for the complete universe."""

        required = sorted({str(symbol).upper() for symbol in symbols})
        missing_subscriptions = [symbol for symbol in required if symbol not in self.tickers]
        if missing_subscriptions:
            raise LiveMarketDataUnavailable(
                "IBKR preflight has no subscription for: " + ", ".join(missing_subscriptions)
            )
        deadline = time.monotonic() + max(float(timeout_seconds), 0.0)
        last_coverage = None
        while True:
            with self._error_lock:
                permission_errors = list(self.api_errors)
            if permission_errors:
                first = permission_errors[0]
                raise LiveMarketDataUnavailable(
                    "IBKR live API market data is unavailable during all-symbol preflight: "
                    f"error {first['code']} ({first['message']})"
                )

            delayed_symbols = []
            for symbol in required:
                ticker = self.tickers[symbol]
                market_data_type = int(getattr(ticker, "marketDataType", 0) or 0)
                if market_data_type in (2, 3, 4):
                    delayed_symbols.append(symbol)
                # Only bootstrap a synchronously populated ticker when the
                # event callback has not stored it.  Never refresh receipt age
                # merely by polling the same cached object.
                if self.store.get_data(symbol) is None:
                    bid = self._positive(getattr(ticker, "bid", None))
                    ask = self._positive(getattr(ticker, "ask", None))
                    if market_data_type == 1 and bid is not None and ask is not None and bid < ask:
                        self._store_ticker(ticker)
            if delayed_symbols:
                self.store.set_provider_health(
                    self.PROVIDER,
                    live=False,
                    delayed=True,
                    delayed_symbols=delayed_symbols,
                )
                raise LiveMarketDataUnavailable(
                    "IBKR returned frozen or delayed data for: " + ", ".join(delayed_symbols)
                )

            last_coverage = self.store.coverage(
                required,
                provider=self.PROVIDER,
                max_age_seconds=max_age_seconds,
            )
            if last_coverage["passed"]:
                return last_coverage
            remaining = deadline - time.monotonic()
            if remaining <= 0.0:
                raise LiveMarketDataUnavailable(
                    "IBKR all-symbol live-quote preflight failed: "
                    f"valid={last_coverage['valid_count']}/{last_coverage['required_count']}; "
                    f"missing={last_coverage['missing_symbols']}; "
                    f"stale={last_coverage['stale_symbols']}; "
                    f"invalid={last_coverage['invalid_symbols']}"
                )
            self.ib.sleep(min(0.1, remaining))

    def cancel_market_data(self, symbol: str):
        if symbol in self.tickers:
            ticker = self.tickers[symbol]
            # ib_insync.cancelMktData requires the exact subscribed Contract,
            # not the returned Ticker object.
            self.ib.cancelMktData(ticker.contract)
            del self.tickers[symbol]
            logger.info(f"Unsubscribed from market data for {symbol}")
        else:
            logger.warning(f"Not subscribed to {symbol}")

    def shutdown(self):
        for symbol in list(self.tickers.keys()):
            self.cancel_market_data(symbol)
        try:
            self.ib.pendingTickersEvent -= self._on_pending_tickers
        except (AttributeError, ValueError):
            pass
        try:
            self.ib.errorEvent -= self._on_error
        except (AttributeError, ValueError):
            pass
        self.store.set_provider_health(
            self.PROVIDER,
            connected=False,
            live=False,
            disconnect_reason="adapter_shutdown",
        )
        logger.info("StandaloneMarketData shut down")
