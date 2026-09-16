"""
Fetch all market data Session Conditions needs. Run this on a machine with
normal internet (your Mac Mini) — Yahoo is blocked from the cloud sandbox.

    pip install yfinance pandas
    python fetch_data.py

Writes to ./data/:
    nq_daily.csv      NQ=F continuous front-month daily OHLCV (yfinance, ~2000→)
    qqq_daily.csv     QQQ daily OHLCV (1999→), used as a long-history cross-check
    vix.csv           ^VIX daily OHLC
    vix3m.csv         ^VIX3M daily close (term structure)
    vvix.csv          ^VVIX daily close
    nq_intraday.csv   NQ=F 5-minute bars, last 60 days (Yahoo's intraday limit)
"""
import sys
import pandas as pd
import yfinance as yf
from pathlib import Path

OUT = Path(__file__).parent / "data"
OUT.mkdir(exist_ok=True)


def flat(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]
    df.columns = [c.lower() for c in df.columns]
    df.index.name = "date"
    return df


def merge_save(df: pd.DataFrame, name: str):
    """Merge new rows into the existing CSV instead of clobbering it.

    yfinance sometimes returns a truncated history (2026-09-15: ^VIX3M came back
    ending two months early and the daily run silently overwrote good data).
    Never let a shorter pull destroy rows we already have; warn when the fresh
    pull's end lags what's on disk.
    """
    out = OUT / name
    if out.exists():
        old = pd.read_csv(out, parse_dates=["date"], index_col="date").sort_index()
        if df.index.max() < old.index.max():
            print(f"!! {name}: fresh pull ends {df.index.max().date()} but disk has "
                  f"{old.index.max().date()} — keeping existing rows", file=sys.stderr)
        df = pd.concat([old, df])
        df = df[~df.index.duplicated(keep="last")].sort_index()
    df.to_csv(out)
    print(f"{name}: {len(df)} rows  {df.index.min().date()} → {df.index.max().date()}")


def daily(ticker: str, start: str, name: str, cols=None):
    df = flat(yf.download(ticker, start=start, auto_adjust=False, progress=False))
    if df.empty:
        print(f"!! {ticker}: no data", file=sys.stderr)
        return
    if cols:
        df = df[cols]
    merge_save(df, name)


def vix3m_cboe():
    """Supplement ^VIX3M with CBOE's official history — yfinance's feed for it
    is unreliable (see merge_save note)."""
    url = "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX3M_History.csv"
    try:
        df = pd.read_csv(url, parse_dates=["DATE"]).rename(columns=str.lower)
        df = df.set_index("date")[["close"]].sort_index()
        df.index.name = "date"
        merge_save(df, "vix3m.csv")
    except Exception as e:  # noqa: BLE001 — network supplement, never fatal
        print(f"!! vix3m CBOE supplement failed: {e}", file=sys.stderr)


daily("NQ=F", "2000-01-01", "nq_daily.csv", ["open", "high", "low", "close", "volume"])
daily("QQQ", "1999-03-10", "qqq_daily.csv", ["open", "high", "low", "close", "volume"])
daily("^VIX", "1990-01-01", "vix.csv", ["open", "high", "low", "close"])
daily("^VIX3M", "2007-01-01", "vix3m.csv", ["close"])
vix3m_cboe()
daily("^VVIX", "2007-01-01", "vvix.csv", ["close"])

intra = flat(yf.download("NQ=F", period="60d", interval="5m", auto_adjust=False, progress=False))
if not intra.empty:
    intra.index.name = "datetime"
    intra[["open", "high", "low", "close", "volume"]].to_csv(OUT / "nq_intraday.csv")
    print(f"nq_intraday.csv: {len(intra)} bars")
