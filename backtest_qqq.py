"""
Phase 2 kill/keep run: regime labels scored on QQQ daily bars.

QQQ's yfinance daily open IS the true 9:30 ET Nasdaq open, so gap features here
are real overnight gaps — unlike NQ=F whose yfinance "open" is the 6pm Globex
open. This is the clean-data replication test for the day-1 NQ findings.

    python backtest_qqq.py            # full report
    python backtest_qqq.py --sweep    # adds ±20% threshold robustness sweeps
"""
import argparse
import numpy as np
import pandas as pd

from features import build, load_prices, load_vix
from regime import P, label, base_rates, stability, OUTCOMES


def report(df, lab, outcomes=OUTCOMES):
    print(lab.value_counts().to_string())
    br = base_rates(df, lab, outcomes)
    cols = [c for c in br.columns if not c.endswith(("_lo", "_hi"))]
    print("\n" + br[cols].round(3).to_string())
    for oc in ("out_range_atr", "out_eff", "out_gap_filled"):
        print(f"\nStability ({oc}, deviation from baseline):")
        print(stability(df, lab, oc).round(3).to_string())
    return br


def sweep(df, knob, values):
    """Robustness: does each label's range effect keep its sign as one knob moves?"""
    rows = {}
    for v in values:
        p = dict(P, **{knob: v})
        lab = label(df, p)
        base = df["out_range_atr"].mean()
        dev = df.groupby(lab)["out_range_atr"].mean() - base
        n = lab.value_counts()
        rows[f"{v:g}"] = pd.Series({f"{k}": f"{dev[k]:+.3f}/n={n[k]}" for k in dev.index})
    return pd.DataFrame(rows)


def gap_bands(df, prices):
    """Same-day gap-fill by gap-size band vs a mechanical distance null.

    Null: P(fill) if the day's adverse excursion from the open were drawn from
    the unconditional excursion distribution — i.e., how much of the fill-rate
    decline is just 'bigger gap = longer way back'. Caveat: the null is not
    vol-matched, so a positive diff on big-gap days is at least partly their
    wider-than-average ranges, not behavior.
    """
    p = prices.loc[df.index]
    prev_close = p.close.shift(1).loc[df.index]
    up = p.open > prev_close
    exc = np.where(up, (p.open - p.low), (p.high - p.open)) / df.atr20
    exc_sorted = np.sort(exc[~np.isnan(exc)])
    p_mech = lambda g: 1.0 - np.searchsorted(exc_sorted, g, side="left") / len(exc_sorted)
    print(f"{'gap_atr band':>14} {'n':>6} {'actual fill':>12} {'mech null':>10} {'diff':>7}")
    for lo, hi in [(0.0, 0.1), (0.1, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 1.0), (1.0, np.inf)]:
        m = (df.gap_atr >= lo) & (df.gap_atr < hi) & ~np.isnan(exc)
        if m.sum() < 20:
            continue
        act = df.out_gap_filled[m].mean()
        mech = np.mean([p_mech(g) for g in df.gap_atr[m]])
        hi_s = "inf" if hi == np.inf else f"{hi:.1f}"
        print(f"[{lo:.1f},{hi_s}) {m.sum():>9} {act:>11.3f} {mech:>10.3f} {act - mech:>+7.3f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sweep", action="store_true")
    ap.add_argument("--gaps", action="store_true")
    args = ap.parse_args()

    prices = load_prices("qqq_daily.csv")
    df = build(prices, load_vix())
    print(f"QQQ RTH sample: {len(df)} days  {df.index.min().date()} → {df.index.max().date()}\n")
    lab = label(df)
    pd.set_option("display.width", 250)
    report(df, lab)

    # EVENT is definition-drifted across the sample (no events pre-2010, NFP-only
    # 2010-2014, +FOMC 2015, +CPI 2022). Full-sample EVENT rows above are invalid;
    # this is the only span where the label means what it means today.
    from events import FULL_COVERAGE_START
    cut = df.index >= FULL_COVERAGE_START
    print(f"\n=== EVENT re-score, {FULL_COVERAGE_START[:4]}+ only (full calendar coverage) ===")
    br22 = base_rates(df[cut], label(df[cut]))
    cols = [c for c in br22.columns if not c.endswith(("_lo", "_hi"))]
    print(br22.loc[["ALL", "EVENT"], cols].round(3).to_string())
    print("EVENT verdict: UNPROVEN — direction suggestive but one macro regime, small n.")

    if args.gaps:
        print("\n=== gap-fill by band vs mechanical distance null ===")
        gap_bands(df, prices)

    if args.sweep:
        grids = {
            "compress": [0.68, 0.77, 0.85, 0.94, 1.02],
            "expand": [0.96, 1.08, 1.20, 1.32, 1.44],
            "trend_atr": [2.4, 2.7, 3.0, 3.3, 3.6],
            "er": [0.36, 0.40, 0.45, 0.50, 0.54],
            "gap_big": [0.48, 0.54, 0.6, 0.66, 0.72],
            "vix_hi": [0.68, 0.77, 0.85, 0.94],
        }
        for knob, vals in grids.items():
            print(f"\n=== sweep {knob} (default {P[knob]}) — out_range_atr deviation / n ===")
            print(sweep(df, knob, vals).to_string())


if __name__ == "__main__":
    main()
