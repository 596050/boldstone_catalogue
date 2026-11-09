from datetime import date, datetime

import pytest

from .demo import validate_target_clock
from .session_window import bounds


def test_early_close_is_enforced_even_if_broker_offers_later_quotes():
    target = {'source_day': '2026-11-25', 'effective_session': '2026-11-27',
              'source_observed_at': '2026-11-25T21:15:00+00:00',
              'published_at': '2026-11-25T21:20:00+00:00',
              'not_before': '2026-11-27T14:30:00+00:00'}
    validate_target_clock(target, datetime.fromisoformat('2026-11-27T17:59:59+00:00'))
    with pytest.raises(ValueError, match='outside declared'):
        validate_target_clock(target, datetime.fromisoformat('2026-11-27T18:00:00+00:00'))


def test_published_calendar_full_closures_and_no_invented_new_year_observance():
    with pytest.raises(ValueError, match='exchange closed'):
        bounds(date(2027, 12, 24))
    assert bounds(date(2027, 12, 31))[1].hour == 16
    assert bounds(date(2028, 7, 3))[1].hour == 13
    with pytest.raises(ValueError, match='verified published-year refresh'):
        bounds(date(2029, 1, 2))
