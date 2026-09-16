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
from regime import P, label, modifiers, modifier_rates, base_rates, stability, OUTCOMES


def report(df, lab, outcomes=OUTCOMES):
    print(lab.value_counts().to_string())
    br = base_rates(df, lab, outcomes)
    cols = [c for c in br.columns if not c.endswith(("_lo", "_hi", "_p25", "_p75"))]
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
    """Same-day gap-fill by gap-size band vs two mechanical nulls.

    Unconditional null: adverse excursion (in ATR) drawn from all days — asks how
    much of the fill decline is 'bigger gap = longer way back'.
    Vol-matched null: excursion drawn from days in the same realized-range decile —
    additionally controls for gap days being wide-range days. The 2026-09-15 run
    showed vol-matching collapses the big-gap excess to +2.3pp, 95% CI [-0.2,+4.9]:
    fill odds are what distance + that day's range imply, nothing behavioral.
    """
    p = prices.loc[df.index]
    prev_close = p.close.shift(1).loc[df.index]
    up = (p.open > prev_close).to_numpy()
    atr = df.atr20.to_numpy()
    exc = np.where(up, (p.open - p.low).to_numpy(), (p.high - p.open).to_numpy()) / atr
    gap = df.gap_atr.to_numpy()
    rng_atr = df.out_range_atr.to_numpy()
    filled = df.out_gap_filled.to_numpy().astype(float)
    ok = ~(np.isnan(exc) | np.isnan(gap) | np.isnan(rng_atr))
    exc, gap, rng_atr, filled = exc[ok], gap[ok], rng_atr[ok], filled[ok]

    exc_sorted = np.sort(exc)
    p_uncond = lambda g: 1.0 - np.searchsorted(exc_sorted, g, side="left") / len(exc_sorted)
    dec = pd.qcut(rng_atr, 10, labels=False)
    bucket = {b: np.sort(exc[dec == b]) for b in range(10)}

    def p_vol(i):
        e = bucket[dec[i]]
        return 1.0 - np.searchsorted(e, gap[i], side="left") / len(e)

    print(f"{'gap_atr band':>14} {'n':>6} {'actual':>8} {'uncond':>8} {'vol-matched':>12} {'diff':>7}")
    for lo, hi in [(0.0, 0.1), (0.1, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 1.0), (1.0, np.inf)]:
        m = (gap >= lo) & (gap < hi)
        if m.sum() < 20:
            continue
        ii = np.where(m)[0]
        act = filled[m].mean()
        u = np.mean([p_uncond(g) for g in gap[m]])
        v = np.mean([p_vol(i) for i in ii])
        hi_s = "inf" if hi == np.inf else f"{hi:.1f}"
        print(f"[{lo:.1f},{hi_s}) {m.sum():>9} {act:>8.3f} {u:>8.3f} {v:>12.3f} {act - v:>+7.3f}")


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

    # Modifiers (taxonomy split 2026-09-15): BIG_GAP and EVENT are independent
    # booleans scored on their own vs the unconditional baseline. EVENT calendar
    # is complete from 1999 (FOMC federalreserve.gov, CPI BLS archives).
    mods = modifiers(df)
    cols = None
    for m in mods.columns:
        mr = modifier_rates(df, mods[m], m)
        cols = [c for c in mr.columns if not c.endswith(("_lo", "_hi", "_p25", "_p75"))]
        print(f"\n=== modifier {m} (independent of primary) ===")
        print(mr[cols].round(3).to_string())
        ml = pd.Series("other", index=df.index)
        ml[mods[m]] = m
        st = stability(df, ml, "out_range_atr").loc[m]
        print(f"stability (out_range_atr): {st.first_half:+.3f} / {st.second_half:+.3f}")
    print("\nEVENT verdict: KEEP (2026-09-15, full 1999+ calendar) — modest but real: "
          "range CI excludes baseline, big/small-range sig, no stability flips, n=1047.")
    print("BIG_GAP (as modifier, n=793): range 1.142 sig, fill 27.4% vs 67.4% sig, "
          "no stability flips — passes independently.")

    if args.gaps:
        print("\n=== gap-fill by band vs mechanical distance null ===")
        gap_bands(df, prices)

    if args.sweep:
        grids = {
            "compress": [0.68, 0.77, 0.85, 0.94, 1.02],
            "expand": [0.96, 1.08, 1.20, 1.32, 1.44],
            "trend_atr": [2.4, 2.7, 3.0, 3.3, 3.6],
            "er": [0.36, 0.40, 0.45, 0.50, 0.54],
            # gap_big removed: BIG_GAP is a modifier since the taxonomy split —
            # it no longer affects the primary chain that sweep() re-labels.
            "vix_hi": [0.68, 0.77, 0.85, 0.94],
        }
        for knob, vals in grids.items():
            print(f"\n=== sweep {knob} (default {P[knob]}) — out_range_atr deviation / n ===")
            print(sweep(df, knob, vals).to_string())


if __name__ == "__main__":
    main()
