"""
Fetch NQ RTH daily bars from Databento (GLBX.MDP3) with true 9:30 ET opens.

Yahoo's NQ=F daily "open" is the Globex open (6pm ET prior day), which poisons
gap features — the day-1 backtest showed a 91% baseline "gap fill" rate because
overnight opens are nearly always inside yesterday's range. This script builds
data/nq_rth_daily.csv by aggregating 1-minute bars over 09:30-16:00 ET only.

    export DATABENTO_API_KEY=db-...   # databento.com signup, free $125 credit
    python fetch_databento.py

Incremental: resumes from the last date already in data/nq_rth_daily.csv.
Cost guard: aborts if Databento's metadata API projects the pull to cost > $20.

Symbology: NQ.c.0 — continuous front month, calendar roll. Calendar roll flips
to the next contract on a fixed schedule rather than volume crossover; fine for
daily RTH stats since roll-day distortion is one open out of ~63 per quarter.
"""
import os
import sys
import datetime as dt
from pathlib import Path

import pandas as pd

DATA = Path(__file__).parent / "data"
OUT = DATA / "nq_rth_daily.csv"

DATASET = "GLBX.MDP3"
SCHEMA = "ohlcv-1m"
SYMBOL = "NQ.c.0"
HISTORY_START = dt.date(2010, 6, 6)  # GLBX.MDP3 history begins here
COST_LIMIT_USD = 20.0
RTH_START = dt.time(9, 30)
RTH_END = dt.time(16, 0)  # exclusive


def aggregate_rth(df_1m: pd.DataFrame) -> pd.DataFrame:
    """Aggregate 1-minute bars to RTH (09:30 <= t < 16:00 ET) daily OHLCV.

    Expects a DataFrame with a UTC (or tz-aware) DatetimeIndex and columns
    open/high/low/close/volume. Returns daily bars indexed by ET session date.
    """
    if df_1m.empty:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    et = df_1m.tz_convert("America/New_York")
    t = et.index.time
    rth = et[(t >= RTH_START) & (t < RTH_END)]
    if rth.empty:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    daily = rth.groupby(rth.index.date).agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
    )
    daily.index = pd.to_datetime(daily.index)
    daily.index.name = "date"
    return daily


def resume_start(existing: pd.DataFrame | None) -> dt.date:
    """First date that still needs fetching."""
    if existing is None or existing.empty:
        return HISTORY_START
    return (existing.index.max() + pd.Timedelta(days=1)).date()


def last_completed_weekday(today: dt.date | None = None) -> dt.date:
    """Most recent weekday whose RTH session has already closed."""
    now = dt.datetime.now(dt.timezone.utc).astimezone()
    today = today or now.date()
    d = today
    # today's session only counts once past ~17:00 local (safely after 4pm ET close)
    if now.date() == d and now.hour < 17:
        d -= dt.timedelta(days=1)
    while d.weekday() >= 5:
        d -= dt.timedelta(days=1)
    return d


def load_existing() -> pd.DataFrame | None:
    if not OUT.exists():
        return None
    return pd.read_csv(OUT, parse_dates=["date"], index_col="date").sort_index()


def main() -> int:
    key = os.environ.get("DATABENTO_API_KEY")
    if not key:
        print(
            "DATABENTO_API_KEY not set.\n"
            "  1. Sign up at https://databento.com (free $125 credit)\n"
            "  2. export DATABENTO_API_KEY=db-...\n"
            "  3. Re-run: python fetch_databento.py",
            file=sys.stderr,
        )
        return 1

    existing = load_existing()
    start = resume_start(existing)
    end = last_completed_weekday()
    if start > end:
        print(f"nq_rth_daily.csv up to date (through {existing.index.max().date()}) — no API call.")
        return 0

    import databento as db

    client = db.Historical(key)
    req = dict(
        dataset=DATASET,
        symbols=[SYMBOL],
        stype_in="continuous",
        schema=SCHEMA,
        start=start.isoformat(),
        end=(end + dt.timedelta(days=1)).isoformat(),
    )

    cost = client.metadata.get_cost(**req)
    print(f"Projected cost: ${cost:.2f} for {start} → {end}")
    if cost > COST_LIMIT_USD:
        print(f"Abort: projected cost ${cost:.2f} exceeds ${COST_LIMIT_USD:.2f} guard.", file=sys.stderr)
        return 2

    bars = client.timeseries.get_range(**req).to_df()
    if bars.empty:
        print("No bars returned — nothing to do.")
        return 0
    daily = aggregate_rth(bars[["open", "high", "low", "close", "volume"]])

    if existing is not None:
        daily = pd.concat([existing, daily])
        daily = daily[~daily.index.duplicated(keep="last")].sort_index()
    daily.to_csv(OUT)
    print(f"{OUT.name}: {len(daily)} rows  {daily.index.min().date()} → {daily.index.max().date()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
