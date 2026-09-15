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
