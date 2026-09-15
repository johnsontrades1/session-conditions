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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sweep", action="store_true")
    args = ap.parse_args()

    df = build(load_prices("qqq_daily.csv"), load_vix())
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
