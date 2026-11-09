"""Small US-market trading-day helpers for frozen IBKR runtimes."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

NY_TZ = ZoneInfo("America/New_York")


def ny_now() -> datetime:
    return datetime.now(NY_TZ)


def ny_trading_date(now: datetime | None = None) -> date:
    """Return the current New York calendar date used for daily risk state."""
    current = now or ny_now()
    if current.tzinfo is None:
        current = current.replace(tzinfo=NY_TZ)
    return current.astimezone(NY_TZ).date()


def is_weekday(value: date) -> bool:
    return value.weekday() < 5


def _nth_weekday(year: int, month: int, weekday: int, occurrence: int) -> date:
    first = date(year, month, 1)
    delta = (weekday - first.weekday()) % 7
    return first + timedelta(days=delta + 7 * (occurrence - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    if month == 12:
        first_next = date(year + 1, 1, 1)
    else:
        first_next = date(year, month + 1, 1)
    current = first_next - timedelta(days=1)
    return current - timedelta(days=(current.weekday() - weekday) % 7)


def _observed(day: date) -> date:
    if day.weekday() == 5:
        return day - timedelta(days=1)
    if day.weekday() == 6:
        return day + timedelta(days=1)
    return day


def _easter_sunday(year: int) -> date:
    """Gregorian Easter (Meeus/Jones/Butcher), used for Good Friday."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    ell = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * ell) // 451
    month = (h + ell - 7 * m + 114) // 31
    day = (h + ell - 7 * m + 114) % 31 + 1
    return date(year, month, day)


def regular_nyse_holidays(year: int) -> set[date]:
    """Regular full-day NYSE holidays for modern US-equity calendars.

    Unscheduled exchange closures are intentionally not guessed; callers may
    supply them to :func:`next_nyse_session` when announced.
    """
    holidays = {
        _observed(date(year, 1, 1)),
        _nth_weekday(year, 1, 0, 3),       # Martin Luther King Jr. Day
        _nth_weekday(year, 2, 0, 3),       # Washington's Birthday
        _easter_sunday(year) - timedelta(days=2),
        _last_weekday(year, 5, 0),         # Memorial Day
        _observed(date(year, 7, 4)),
        _nth_weekday(year, 9, 0, 1),       # Labor Day
        _nth_weekday(year, 11, 3, 4),      # Thanksgiving
        _observed(date(year, 12, 25)),
    }
    if year >= 2022:
        holidays.add(_observed(date(year, 6, 19)))
    return holidays


def next_nyse_session(after: date, *, extra_closures: set[date] | None = None) -> date:
    """Return the next regular NYSE session after ``after``."""
    closures = set(extra_closures or ())
    current = after + timedelta(days=1)
    while True:
        if (
            current.weekday() < 5
            and current not in regular_nyse_holidays(current.year)
            and current not in closures
        ):
            return current
        current += timedelta(days=1)


def trading_days_between(start: date, end: date) -> int:
    """Count weekday trading dates after ``start`` through ``end``.

    This deliberately avoids treating weekends as stale-target days. It is a
    lightweight approximation; exchange holidays can be added later without
    changing callers.
    """
    if end <= start:
        return 0
    current = start + timedelta(days=1)
    count = 0
    while current <= end:
        if is_weekday(current):
            count += 1
        current += timedelta(days=1)
    return count


from datetime import timezone

def last_completed_session(now: datetime | None = None) -> str:
    """Last regular NYSE session whose close (16:10 ET buffer) has passed."""
    from zoneinfo import ZoneInfo
    from utils.trading.calendar import regular_nyse_holidays

    et = (now or datetime.now(timezone.utc)).astimezone(ZoneInfo("America/New_York"))
    d = et.date()
    if et.hour < 16 or (et.hour == 16 and et.minute < 10):
        d = date.fromordinal(d.toordinal() - 1)
    while d.weekday() >= 5 or d in regular_nyse_holidays(d.year):
        d = date.fromordinal(d.toordinal() - 1)
    return d.isoformat()
