"""Tests for the Databento RTH pipeline — all runnable without an API key."""
import datetime as dt
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from fetch_databento import aggregate_rth, resume_start, last_completed_weekday, HISTORY_START


def make_1m(day: str, start="00:00", end="23:59", tz="America/New_York") -> pd.DataFrame:
    """Synthetic 1-minute bars for one calendar day, price = minute-of-day."""
    idx = pd.date_range(f"{day} {start}", f"{day} {end}", freq="1min", tz=tz)
    base = np.arange(len(idx), dtype=float) + 100.0
    return pd.DataFrame(
        {"open": base, "high": base + 1, "low": base - 1, "close": base + 0.5, "volume": 10.0},
        index=idx,
    ).tz_convert("UTC")


class TestAggregateRTH:
    def test_excludes_bars_outside_rth(self):
        bars = make_1m("2026-09-10")  # full 24h of bars
        daily = aggregate_rth(bars)
        assert len(daily) == 1
        # 390 RTH minutes * 10 volume each
        assert daily.iloc[0]["volume"] == 390 * 10

    def test_open_is_exactly_930_bar(self):
        bars = make_1m("2026-09-10")
        daily = aggregate_rth(bars)
        et = bars.tz_convert("America/New_York")
        bar_930 = et[et.index.time == dt.time(9, 30)]
        assert daily.iloc[0]["open"] == bar_930.iloc[0]["open"]

    def test_1600_bar_excluded(self):
        bars = make_1m("2026-09-10")
        daily = aggregate_rth(bars)
        et = bars.tz_convert("America/New_York")
        rth = et[(et.index.time >= dt.time(9, 30)) & (et.index.time < dt.time(16, 0))]
        assert daily.iloc[0]["close"] == rth.iloc[-1]["close"]
        assert daily.iloc[0]["high"] == rth["high"].max()

    def test_dst_transition_week(self):
        # US DST began 2026-03-08; ET switched EST->EDT. Both days must still
        # aggregate exactly 390 RTH minutes when built in wall-clock ET.
        for day in ("2026-03-06", "2026-03-09"):
            daily = aggregate_rth(make_1m(day))
            assert len(daily) == 1, day
            assert daily.iloc[0]["volume"] == 390 * 10, day

    def test_empty_input(self):
        out = aggregate_rth(pd.DataFrame(columns=["open", "high", "low", "close", "volume"]))
        assert out.empty


class TestIncremental:
    def test_no_existing_starts_at_history(self):
        assert resume_start(None) == HISTORY_START

    def test_resumes_day_after_last(self):
        existing = pd.DataFrame(
            {"open": [1.0]}, index=pd.DatetimeIndex([pd.Timestamp("2026-09-10")], name="date")
        )
        assert resume_start(existing) == dt.date(2026, 9, 11)

    def test_up_to_date_skips_pull(self):
        last = last_completed_weekday()
        existing = pd.DataFrame(
            {"open": [1.0]}, index=pd.DatetimeIndex([pd.Timestamp(last)], name="date")
        )
        assert resume_start(existing) > last  # main() exits before any API call

    def test_last_completed_weekday_is_weekday(self):
        assert last_completed_weekday().weekday() < 5


class TestFeatureSourcePreference:
    def make_daily_csv(self, path: Path, days=60, open_offset=0.0):
        idx = pd.bdate_range("2026-01-02", periods=days)
        close = np.linspace(100, 120, days)
        df = pd.DataFrame(
            {"open": close + open_offset, "high": close + 2, "low": close - 2,
             "close": close, "volume": 1000},
            index=pd.DatetimeIndex(idx, name="date"),
        )
        df.to_csv(path)

    def test_prefers_rth_when_present(self, tmp_path, monkeypatch):
        import features
        monkeypatch.setattr(features, "DATA", tmp_path)
        self.make_daily_csv(tmp_path / "nq_daily.csv", open_offset=5.0)
        self.make_daily_csv(tmp_path / "nq_rth_daily.csv", open_offset=-3.0)
        df = features.load_prices()
        assert (df["open"] - df["close"]).iloc[0] == pytest.approx(-3.0)

    def test_falls_back_to_yfinance(self, tmp_path, monkeypatch):
        import features
        monkeypatch.setattr(features, "DATA", tmp_path)
        self.make_daily_csv(tmp_path / "nq_daily.csv", open_offset=5.0)
        df = features.load_prices()
        assert (df["open"] - df["close"]).iloc[0] == pytest.approx(5.0)

    def test_explicit_name_not_overridden(self, tmp_path, monkeypatch):
        import features
        monkeypatch.setattr(features, "DATA", tmp_path)
        self.make_daily_csv(tmp_path / "qqq_daily.csv", open_offset=7.0)
        self.make_daily_csv(tmp_path / "nq_rth_daily.csv", open_offset=-3.0)
        df = features.load_prices("qqq_daily.csv")
        assert (df["open"] - df["close"]).iloc[0] == pytest.approx(7.0)
