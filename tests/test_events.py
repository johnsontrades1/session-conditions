"""Regression tests for the pre_fomc flag (events.py)."""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from events import event_flags


def bdays(end, periods):
    return pd.bdate_range(end=end, periods=periods)


class TestPreFomc:
    def test_future_fomc_does_not_flag_last_row(self):
        # Data ends 2026-08-14; next FOMC is 2026-09-16, a month away.
        # The old code flagged the dataset's final row for every future meeting.
        idx = bdays("2026-08-14", 60)
        flags = event_flags(idx)
        assert not flags["pre_fomc"].iloc[-1]

    def test_data_ending_two_days_before_meeting_not_flagged(self):
        # Data ends Monday 2026-09-14; FOMC is Wednesday 2026-09-16. The real
        # pre-FOMC day is Tuesday 9/15, which doesn't exist in the data yet —
        # Monday must NOT be flagged.
        idx = bdays("2026-09-14", 60)
        flags = event_flags(idx)
        assert not flags["pre_fomc"].iloc[-1]

    def test_true_prior_trading_day_flagged(self):
        # Data includes Tuesday 2026-09-15, the trading day before the 9/16 decision.
        idx = bdays("2026-09-15", 60)
        flags = event_flags(idx)
        assert flags["pre_fomc"].loc["2026-09-15"]
        assert flags["pre_fomc"].sum() >= 1

    def test_historical_pre_fomc_days(self):
        # 2024-06-12 FOMC → 2024-06-11 (Tue) is pre-FOMC.
        idx = pd.bdate_range("2024-05-01", "2024-07-01")
        flags = event_flags(idx)
        assert flags["pre_fomc"].loc["2024-06-11"]
        assert not flags["pre_fomc"].loc["2024-06-12"]

    def test_weekend_gap_still_flags_friday(self):
        # 2020-03-03 was an emergency Tuesday decision; Monday 2020-03-02 is the
        # prior trading day (adjacent, no gap).
        idx = pd.bdate_range("2020-02-03", "2020-03-31")
        flags = event_flags(idx)
        assert flags["pre_fomc"].loc["2020-03-02"]


class TestCalendarCoverage:
    def test_fomc_eight_per_year_1999_2019(self):
        from events import build_calendar
        cal = build_calendar("1999-01-01", "2019-12-31")
        per_year = cal[cal.event == "FOMC"].date.dt.year.value_counts()
        for y in range(1999, 2020):
            assert per_year.get(y, 0) == 8, f"{y}: {per_year.get(y, 0)} FOMC dates"

    def test_cpi_twelve_per_year_1999_2024(self):
        from events import build_calendar
        cal = build_calendar("1999-01-01", "2024-12-31")
        per_year = cal[cal.event == "CPI"].date.dt.year.value_counts()
        for y in range(1999, 2025):
            assert per_year.get(y, 0) == 12, f"{y}: {per_year.get(y, 0)} CPI dates"

    def test_full_coverage_start_predates_qqq_sample(self):
        import pandas as pd
        from events import FULL_COVERAGE_START
        assert pd.Timestamp(FULL_COVERAGE_START) <= pd.Timestamp("1999-04-08")

    def test_shutdown_delayed_cpi_present(self):
        from events import CPI
        assert "2013-10-30" in CPI


class TestCalendarFreshness:
    """Fails when the hardcoded calendars near their end — the reminder to
    refresh from bls.gov / federalreserve.gov before EVENT silently under-flags."""

    def test_cpi_calendar_extends_60_days_out(self):
        import datetime as dt
        from events import CPI
        last = max(dt.date.fromisoformat(d) for d in CPI)
        assert last >= dt.date.today() + dt.timedelta(days=60), (
            f"CPI calendar ends {last} — refresh from bls.gov/schedule/news_release/cpi.htm")

    def test_fomc_calendar_extends_60_days_out(self):
        import datetime as dt
        from events import FOMC
        last = max(dt.date.fromisoformat(d) for d in FOMC)
        assert last >= dt.date.today() + dt.timedelta(days=60), (
            f"FOMC calendar ends {last} — refresh from federalreserve.gov/monetarypolicy/fomccalendars.htm")
