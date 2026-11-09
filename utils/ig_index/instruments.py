"""Load and validate the operator-verified IG instrument configuration.

An instrument is usable only when every dealing parameter is present AND the
operator has stamped `verified_at`. Anything short of that is inert: it appears
in preflight with a reason, and the order path refuses it.
"""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Mapping

import yaml

CONFIG_DIR = Path(__file__).resolve().parent / "config"
ACCOUNT_YAML = CONFIG_DIR / "account.yaml"
INSTRUMENTS_YAML = CONFIG_DIR / "instruments.yaml"
INSTRUMENT_TYPE = "spreadbet"
from utils.trading.calendar import ny_trading_date

# Verified, stable roster member used solely as the pricing source for the
# GBP->USD refresh below. Any verified name would do; pinned to one so the
# refresh is deterministic and doesn't depend on iteration order over the
# roster.
FX_REFERENCE_EPIC = "SA.D.ABT.DAILY.IP"

_FX_RATE_LINE_RE = re.compile(r"^(\s*USD:\s*)[0-9.]+(\s*)$", re.MULTILINE)
_FX_AS_OF_LINE_RE = re.compile(r'^(fx_rates_as_of:\s*")[0-9-]+(".*)$', re.MULTILINE)


REQUIRED_DEALING_FIELDS = (
    "epic",
    "point_size",
    "min_stake",
    "stake_increment",
    "stake_currency",
    "quote_currency",
)


class ConfigError(RuntimeError):
    """Raised when configuration is missing, malformed, or self-inconsistent."""


@dataclass(frozen=True)
class Instrument:
    symbol: str
    epic: str | None
    point_size: float | None
    min_stake: float | None
    stake_increment: float | None
    stake_currency: str
    quote_currency: str
    margin_pct: float | None
    verified_at: str | None
    verified_by: str | None

    @property
    def unverified_reason(self) -> str | None:
        """None when this instrument may be traded, else why it may not."""
        missing = [
            field
            for field in REQUIRED_DEALING_FIELDS
            if getattr(self, field) in (None, "")
        ]
        if missing:
            return f"missing dealing fields: {', '.join(missing)}"
        if not self.verified_at:
            return "not operator-verified (verified_at is unset)"
        for field in ("point_size", "min_stake", "stake_increment"):
            if float(getattr(self, field)) <= 0.0:
                return f"{field} must be positive"
        return None

    @property
    def is_tradable(self) -> bool:
        return self.unverified_reason is None


SIZING_MODES = ("proportional", "direction_only")


@dataclass(frozen=True)
class AccountConfig:
    dollars_per_symbol: float
    max_min_stake_fraction: float
    max_dropped_names: int
    instrument_type: str
    fx_rates: Mapping[str, Mapping[str, float | None]]
    fx_rates_as_of: str | None
    fx_max_age_days: int
    default_margin_pct: float
    overnight_funding_annual_pct: float | None
    sizing_mode: str = "proportional"

    @property
    def is_direction_only(self) -> bool:
        return self.sizing_mode == "direction_only"

    def fx(self, stake_currency: str, quote_currency: str) -> float:
        """Stake-currency -> quote-currency rate. Raises when unconfigured."""
        if stake_currency == quote_currency:
            return 1.0
        rate = (self.fx_rates.get(stake_currency) or {}).get(quote_currency)
        if rate is None:
            raise ConfigError(
                f"no FX rate configured for {stake_currency}->{quote_currency}; "
                "set it in config/account.yaml"
            )
        rate = float(rate)
        if rate <= 0.0:
            raise ConfigError(f"FX rate {stake_currency}->{quote_currency} must be positive")
        return rate

    def fx_age_days(self, today: date | None = None) -> int | None:
        if not self.fx_rates_as_of:
            return None
        stamped = date.fromisoformat(str(self.fx_rates_as_of))
        return ((today or date.today()) - stamped).days

    def fx_is_stale(self, today: date | None = None) -> bool:
        age = self.fx_age_days(today)
        return age is None or age < 0 or age > int(self.fx_max_age_days)


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ConfigError(f"missing configuration file: {path}")
    try:
        loaded = yaml.safe_load(path.read_text())
    except yaml.YAMLError as exc:
        raise ConfigError(f"{path} is not valid YAML: {exc}") from exc
    if not isinstance(loaded, dict):
        raise ConfigError(f"{path} must contain a mapping at the top level")
    return loaded


def load_account(path: Path | None = None) -> AccountConfig:
    payload = _read_yaml(path or ACCOUNT_YAML)
    if payload.get("schema") != "carry_zrev_96_ig_spreadbet_account.v1":
        raise ConfigError("unexpected account config schema")
    if payload.get("instrument_type") != INSTRUMENT_TYPE:
        raise ConfigError(
            f"account instrument_type must be {INSTRUMENT_TYPE!r}; "
            f"got {payload.get('instrument_type')!r}"
        )
    for field in ("dollars_per_symbol", "max_min_stake_fraction", "max_dropped_names"):
        if payload.get(field) is None:
            raise ConfigError(f"account config is missing {field}")
    dollars = float(payload["dollars_per_symbol"])
    fraction = float(payload["max_min_stake_fraction"])
    if dollars <= 0.0:
        raise ConfigError("dollars_per_symbol must be positive")
    if not 0.0 < fraction <= 1.0:
        raise ConfigError("max_min_stake_fraction must lie in (0, 1]")
    sizing_mode = str(payload.get("sizing_mode") or "proportional")
    if sizing_mode not in SIZING_MODES:
        raise ConfigError(f"sizing_mode must be one of {SIZING_MODES}; got {sizing_mode!r}")
    return AccountConfig(
        sizing_mode=sizing_mode,
        dollars_per_symbol=dollars,
        max_min_stake_fraction=fraction,
        max_dropped_names=int(payload["max_dropped_names"]),
        instrument_type=str(payload["instrument_type"]),
        fx_rates=payload.get("fx_rates") or {},
        fx_rates_as_of=payload.get("fx_rates_as_of"),
        fx_max_age_days=int(payload.get("fx_max_age_days") or 7),
        default_margin_pct=float(payload.get("default_margin_pct") or 0.20),
        overnight_funding_annual_pct=(
            None
            if payload.get("overnight_funding_annual_pct") is None
            else float(payload["overnight_funding_annual_pct"])
        ),
    )


def refresh_fx_rate_if_stale(
    account: AccountConfig,
    *,
    session: Any = None,
    path: Path | None = None,
    reference_epic: str = FX_REFERENCE_EPIC,
) -> AccountConfig:
    """If `account`'s pinned GBP->USD rate is stale, pull the current one from
    IG's own live API (`instrument.currencies[USD].baseExchangeRate`, the same
    source account.yaml's own header documents) and persist it back to the
    config file in place, preserving every comment and unrelated line — this
    does a targeted two-line text substitution, not a YAML parse-and-dump
    round-trip, which would silently strip all of account.yaml's documentation.

    Fails soft: on any error (network, auth, IG API shape change, no session
    available) this prints a warning and returns `account` unchanged, so the
    existing `AccountConfig.fx_is_stale()` gate downstream still fails closed
    exactly as it did before this existed. It never raises.

    `session` may be a pre-authenticated IGSession to reuse; if omitted, a
    short-lived one is created and logged in solely for this refresh (IG login
    itself is not rate-limited, see ig_session.py — only one extra throttled
    market_details call is spent).
    """
    if not account.fx_is_stale():
        return account

    target_path = path or ACCOUNT_YAML
    owns_session = session is None
    try:
        if owns_session:
            from . import session as _ig_session

            session = _ig_session.connect(demo=True)
        details = session.market_details(reference_epic)
        currencies = details.get("instrument", {}).get("currencies", [])
        usd_rate = next(
            (c.get("baseExchangeRate") for c in currencies if c.get("code") == "USD"),
            None,
        )
        if usd_rate is None or not (float(usd_rate) > 0.0):
            raise ConfigError(
                f"IG market_details for {reference_epic} returned no usable "
                "USD baseExchangeRate"
            )
        usd_rate = float(usd_rate)

        text = target_path.read_text()
        new_text, rate_subs = _FX_RATE_LINE_RE.subn(
            lambda m: f"{m.group(1)}{usd_rate}{m.group(2)}", text, count=1
        )
        today = ny_trading_date().isoformat()
        new_text, date_subs = _FX_AS_OF_LINE_RE.subn(
            lambda m: f'{m.group(1)}{today}{m.group(2)}', new_text, count=1
        )
        if rate_subs != 1 or date_subs != 1:
            raise ConfigError(
                f"{target_path} does not match the expected fx_rates.GBP.USD / "
                "fx_rates_as_of line format; refusing to edit it blind"
            )
        temp = target_path.with_name(
            f".{target_path.name}.{os.getpid()}.{time.time_ns()}.tmp"
        )
        try:
            temp.write_text(new_text)
            # Parse and validate the complete candidate before it can replace
            # the last known-good operational configuration.
            load_account(temp)
            temp.replace(target_path)
        finally:
            temp.unlink(missing_ok=True)
        print(
            f"auto-refreshed FX rate: GBP->USD {usd_rate} as of {today} "
            f"(was {account.fx_rates.get('GBP', {}).get('USD')} as of "
            f"{account.fx_rates_as_of}), source epic {reference_epic}"
        )
    except Exception as exc:  # noqa: BLE001
        print(
            f"WARNING: automatic FX rate refresh failed ({type(exc).__name__}: {exc}); "
            "falling back to the pinned account.yaml value",
        )
        return account

    return load_account(target_path)


def load_instruments(path: Path | None = None) -> dict[str, Instrument]:
    payload = _read_yaml(path or INSTRUMENTS_YAML)
    if payload.get("schema") != "carry_zrev_96_ig_spreadbet_instruments.v1":
        raise ConfigError("unexpected instruments config schema")
    rows = payload.get("instruments")
    if not isinstance(rows, dict) or not rows:
        raise ConfigError("instruments config contains no instruments mapping")

    out: dict[str, Instrument] = {}
    for symbol, row in rows.items():
        if not isinstance(row, dict):
            raise ConfigError(f"instrument {symbol} must be a mapping")
        unknown = set(row) - {
            *REQUIRED_DEALING_FIELDS,
            "margin_pct",
            "verified_at",
            "verified_by",
        }
        if unknown:
            raise ConfigError(
                f"instrument {symbol} has unknown fields: {', '.join(sorted(unknown))}"
            )
        out[str(symbol)] = Instrument(
            symbol=str(symbol),
            epic=row.get("epic"),
            point_size=_opt_float(row.get("point_size"), symbol, "point_size"),
            min_stake=_opt_float(row.get("min_stake"), symbol, "min_stake"),
            stake_increment=_opt_float(row.get("stake_increment"), symbol, "stake_increment"),
            stake_currency=str(row.get("stake_currency") or "GBP"),
            quote_currency=str(row.get("quote_currency") or "USD"),
            margin_pct=_opt_float(row.get("margin_pct"), symbol, "margin_pct"),
            verified_at=row.get("verified_at"),
            verified_by=row.get("verified_by"),
        )
    return out


def _opt_float(value: Any, symbol: str, field: str) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"instrument {symbol} field {field} is not numeric: {value!r}") from exc


def require_tradable(instrument: Instrument) -> None:
    """Raise unless this instrument may be sent to the venue."""
    reason = instrument.unverified_reason
    if reason is not None:
        raise ConfigError(f"refusing to trade {instrument.symbol}: {reason}")


__all__ = [
    "AccountConfig",
    "ConfigError",
    "Instrument",
    "load_account",
    "load_instruments",
    "require_tradable",
]
