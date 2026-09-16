"""
Accumulate NQ 5-minute intraday history beyond yfinance's rolling 60-day
window. Databento and ProjectX are both off the table (credits exhausted /
not integrated) — this scraper is the ONLY path to the intraday history the
Event Playbook and intraday base rates will eventually need. Run it daily;
every missed day is unrecoverable data, since yfinance only ever gives you
the trailing 60 days.

    python record_intraday.py

Writes/appends to data/intraday/NQ_5m.csv (gitignored — grows large).
Append-only: never overwrites. Same merge-don't-clobber discipline as
fetch_data.py — a truncated or empty yfinance response must not destroy
accumulated history. Dedupes on timestamp (keep-last) so re-runs are
idempotent; running this twice in one day is always safe.
"""
import sys
from pathlib import Path

import pandas as pd
import yfinance as yf

OUT_DIR = Path(__file__).parent / "data" / "intraday"
OUT_FILE = OUT_DIR / "NQ_5m.csv"
SYMBOL = "NQ=F"


def fetch_window() -> pd.DataFrame:
    df = yf.download(SYMBOL, period="60d", interval="5m", auto_adjust=False, progress=False)
    if df.empty:
        return df
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]
    df.columns = [c.lower() for c in df.columns]
    df.index.name = "datetime"
    return df[["open", "high", "low", "close", "volume"]]


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fresh = fetch_window()
    if fresh.empty:
        print("record_intraday: yfinance returned no rows — accumulated history untouched.", file=sys.stderr)
        return 0

    existing = None
    if OUT_FILE.exists():
        existing = pd.read_csv(OUT_FILE, parse_dates=["datetime"], index_col="datetime")

    before_n = 0 if existing is None else len(existing)
    combined = fresh if existing is None else pd.concat([existing, fresh])
    combined = combined[~combined.index.duplicated(keep="last")].sort_index()
    combined.to_csv(OUT_FILE)

    added = len(combined) - before_n
    print(f"NQ_5m.csv: {added} new rows added, {len(combined)} total, "
          f"{combined.index.min()} → {combined.index.max()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
