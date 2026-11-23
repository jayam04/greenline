import datetime

from services.networth.app.services.snapshot_engine import iter_snapshot_dates


def test_daily_snapshot_dates_cover_every_calendar_day_inclusive():
    assert list(iter_snapshot_dates(
        datetime.date(2025, 4, 3), datetime.date(2025, 4, 6), cadence="daily"
    )) == [
        datetime.date(2025, 4, 3),
        datetime.date(2025, 4, 4),
        datetime.date(2025, 4, 5),
        datetime.date(2025, 4, 6),
    ]


def test_weekly_snapshot_dates_preserve_existing_sunday_cadence():
    assert list(iter_snapshot_dates(
        datetime.date(2025, 4, 3), datetime.date(2025, 4, 13), cadence="weekly"
    )) == [datetime.date(2025, 4, 6), datetime.date(2025, 4, 13)]
