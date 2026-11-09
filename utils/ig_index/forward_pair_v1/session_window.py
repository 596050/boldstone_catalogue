"""Published NYSE core-session schedule; no network request in the order path.

Source: https://www.nyse.com/trade/hours-calendars, read 2026-09-24.
This publication covers 2026-2028. Later years require a verified refresh.
Broker tradeability remains independently required for unscheduled closures.
"""
from datetime import datetime, time
from zoneinfo import ZoneInfo

NY = ZoneInfo('America/New_York')
FULL_CLOSURES = {
    2026: {'01-01', '01-19', '02-16', '04-03', '05-25', '06-19', '07-03', '09-07', '11-26', '12-25'},
    2027: {'01-01', '01-18', '02-15', '03-26', '05-31', '06-18', '07-05', '09-06', '11-25', '12-24'},
    2028: {'01-17', '02-21', '04-14', '05-29', '06-19', '07-04', '09-04', '11-23', '12-25'},
}
EARLY_CLOSES = {'2026-11-27', '2026-12-24', '2027-11-26', '2028-07-03', '2028-11-24'}


def bounds(day):
    if day.year not in FULL_CLOSURES:
        raise ValueError('execution calendar requires a verified published-year refresh')
    if day.weekday() >= 5 or day.strftime('%m-%d') in FULL_CLOSURES[day.year]:
        raise ValueError('outside declared regular-session execution window: exchange closed')
    closing = time(13) if day.isoformat() in EARLY_CLOSES else time(16)
    return datetime.combine(day, time(9, 30), NY), datetime.combine(day, closing, NY)
