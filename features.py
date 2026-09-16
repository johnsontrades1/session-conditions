"""
Daily feature engineering. Every *feature* uses only information available
before the regular-session open (prior closes, prior ranges, today's open,
yesterday's VIX). Every *outcome* describes what today's session then did.
Keeping those two sets separate is what makes the base rates honest.
"""
import numpy as np
import pandas as pd
from pathlib import Path
from events import event_flags

DATA = Path(__file__).parent / "data"


def resolve_price_source(name="nq_daily.csv") -> tuple[str, str]:
    """Return (actual filename, human-readable open-source description).

    NQ default upgrades to true RTH bars when fetch_databento.py has produced
    them; explicit filenames are never overridden. The description string goes
    on the published page so the data source and the page copy can't silently
    desync (that already happened once — NQ Globex numbers under QQQ copy).
    """
    if name == "nq_daily.csv" and (DATA / "nq_rth_daily.csv").exists():
        return "nq_rth_daily.csv", "NQ futures, RTH 9:30 ET opens (Databento)"
    if name == "nq_daily.csv":
        return "nq_daily.csv", "NQ futures, Globex opens (yfinance) — gap stats contaminated"
    if name == "qqq_daily.csv":
        return "qqq_daily.csv", "QQQ, RTH 9:30 ET opens (yfinance)"
    return name, name


def load_prices(name="nq_daily.csv") -> pd.DataFrame:
    name, source = resolve_price_source(name)
    print(f"open source: {source}")
    df = pd.read_csv(DATA / name, parse_dates=["date"], index_col="date").sort_index()
    df = df[["open", "high", "low", "close"]].astype(float).dropna()
    df = df[(df.high >= df.low) & (df.high > 0)]
    return df


def load_vix() -> pd.DataFrame:
    v = pd.read_csv(DATA / "vix.csv", parse_dates=[0], index_col=0).sort_index()
    v.columns = [c.lower() for c in v.columns]
    v = v[["close"]].rename(columns={"close": "vix"})
    p3 = DATA / "vix3m.csv"
    if p3.exists():
        v3 = pd.read_csv(p3, parse_dates=[0], index_col=0).sort_index()
        v3.columns = [c.lower() for c in v3.columns]
        v["vix3m"] = v3["close"]
    return v


def efficiency_ratio(close: pd.Series, n: int) -> pd.Series:
    change = (close - close.shift(n)).abs()
    path = close.diff().abs().rolling(n).sum()
    return change / path


def build(prices: pd.DataFrame, vix: pd.DataFrame | None = None) -> pd.DataFrame:
    p = prices.copy()
    prev_close = p.close.shift(1)
    tr = pd.concat([p.high - p.low, (p.high - prev_close).abs(), (p.low - prev_close).abs()], axis=1).max(axis=1)
    rng = p.high - p.low

    f = pd.DataFrame(index=p.index)
    # --- pre-open features -------------------------------------------------
    f["atr20"] = tr.rolling(20).mean().shift(1)              # excludes today
    f["atr_pct"] = f.atr20 / prev_close                       # instrument-agnostic ATR (display conversions)
    f["prev_range_atr"] = (rng / f.atr20).shift(1)             # yesterday's range in ATR
    f["range_5_20"] = (rng.rolling(5).mean() / rng.rolling(20).mean()).shift(1)  # compression < 1
    f["gap"] = p.open / prev_close - 1
    f["gap_atr"] = (p.open - prev_close).abs() / f.atr20
    f["ret_1d"] = prev_close.pct_change()                      # yesterday's return
    f["ret_5d"] = (prev_close / prev_close.shift(5) - 1)
    f["trend_20_atr"] = (prev_close - prev_close.shift(20)) / f.atr20
    f["er_10"] = efficiency_ratio(prev_close, 10)             # Kaufman efficiency, 0=chop 1=straight line
    lo20, hi20 = p.low.rolling(20).min().shift(1), p.high.rolling(20).max().shift(1)
    f["pos_20d"] = (prev_close - lo20) / (hi20 - lo20)
    f["above_20ma"] = (prev_close > prev_close.rolling(20).mean()).astype(int)
    f["rv5_rv20"] = (prev_close.pct_change().rolling(5).std() / prev_close.pct_change().rolling(20).std())
    f["dow"] = p.index.dayofweek
    f["month"] = p.index.month

    if vix is not None:
        v = vix.reindex(p.index).ffill().shift(1)              # yesterday's VIX close
        f["vix"] = v.vix
        f["vix_5d_chg"] = v.vix / v.vix.shift(5) - 1
        f["vix_rank_1y"] = v.vix.rolling(252).rank(pct=True)
        if "vix3m" in v:
            f["vix_term"] = v.vix / v.vix3m                    # >1 = backwardation (stress)

    f = f.join(event_flags(p.index))

    # --- same-day outcomes (never used as inputs) --------------------------
    o = pd.DataFrame(index=p.index)
    o["out_range_atr"] = rng / f.atr20
    o["out_eff"] = (p.close - p.open).abs() / rng.replace(0, np.nan)   # 1 = pure trend day
    o["out_ret"] = p.close / p.open - 1
    o["out_ret_atr"] = (p.close - p.open) / f.atr20
    o["out_close_loc"] = (p.close - p.low) / rng.replace(0, np.nan)
    o["out_gap_filled"] = ((p.low <= prev_close) & (p.high >= prev_close)).astype(int)
    o["out_trend_day"] = (o.out_eff >= 0.6).astype(int)
    o["out_big_range"] = (o.out_range_atr >= 1.3).astype(int)
    o["out_small_range"] = (o.out_range_atr <= 0.7).astype(int)
    o["out_next_ret"] = p.close.shift(-1) / p.close - 1       # for pullback base rates
    o["out_next5_ret"] = p.close.shift(-5) / p.close - 1
    return f.join(o).dropna(subset=["atr20"])


if __name__ == "__main__":
    df = build(load_prices(), load_vix())
    print(df.tail(3).T)
    print(len(df), "rows")
