"""
Regime labels + base-rate backtest.

Philosophy: a label is only allowed to exist if, in the backtest, it moves
the outcome distribution away from the unconditional one with a bootstrap
CI that excludes the baseline. Labels that don't discriminate get reported
as such — the tool never claims an edge it can't show.
"""
import numpy as np
import pandas as pd

OUTCOMES = ["out_range_atr", "out_eff", "out_trend_day", "out_big_range", "out_small_range", "out_gap_filled"]

# Rule thresholds — kept as a dict so backtest.py can sweep them.
P = dict(
    compress=0.85,     # range_5_20 below this = coiled
    expand=1.20,       # above this = already expanded
    trend_atr=3.0,     # |20d move| in ATR units to call it trending
    er=0.45,           # efficiency ratio above this = clean directional tape
    gap_big=0.6,       # gap in ATR units
    vix_stress=1.0,    # vix/vix3m above this = backwardation
    vix_hi=0.85,       # 1y pct-rank of VIX above this = high-vol regime
)


def label(f: pd.DataFrame, p: dict = P) -> pd.Series:
    """Pre-open regime label. Order matters: first match wins."""
    lab = pd.Series("NEUTRAL", index=f.index)
    stress = (f.get("vix_term", pd.Series(0, index=f.index)) > p["vix_stress"]) | (f.get("vix_rank_1y", pd.Series(0, index=f.index)) > p["vix_hi"])
    trending = (f.trend_20_atr.abs() >= p["trend_atr"]) & (f.er_10 >= p["er"])
    coiled = f.range_5_20 <= p["compress"]
    expanded = f.range_5_20 >= p["expand"]
    big_gap = f.gap_atr >= p["gap_big"]

    lab[stress] = "HIGH_VOL"
    lab[~stress & trending] = "TREND"
    lab[~stress & ~trending & coiled] = "COILED"
    lab[~stress & ~trending & expanded] = "EXPANDED"
    lab[f.event_day | f.pre_fomc] = "EVENT"      # overrides all
    lab[big_gap & (lab == "NEUTRAL")] = "BIG_GAP"
    return lab


def bootstrap_ci(x: np.ndarray, n=2000, q=(0.025, 0.975), seed=0):
    rng = np.random.default_rng(seed)
    x = x[~np.isnan(x)]
    if len(x) < 5:
        return np.nan, np.nan
    m = rng.choice(x, size=(n, len(x)), replace=True).mean(axis=1)
    return np.quantile(m, q[0]), np.quantile(m, q[1])


def base_rates(df: pd.DataFrame, labels: pd.Series, outcomes=OUTCOMES) -> pd.DataFrame:
    """Per-label mean of each outcome with 95% bootstrap CI and whether the CI
    excludes the unconditional mean ('sig')."""
    rows = []
    base = df[outcomes].mean()
    for lab in ["ALL"] + sorted(labels.unique()):
        sub = df if lab == "ALL" else df[labels == lab]
        r = {"label": lab, "n": len(sub), "share": len(sub) / len(df)}
        for oc in outcomes:
            x = sub[oc].to_numpy(dtype=float)
            lo, hi = bootstrap_ci(x)
            m = np.nanmean(x)
            r[oc] = m
            r[oc + "_lo"], r[oc + "_hi"] = lo, hi
            r[oc + "_sig"] = bool(lab != "ALL" and (hi < base[oc] or lo > base[oc]))
        rows.append(r)
    return pd.DataFrame(rows).set_index("label")


def feature_quintiles(df: pd.DataFrame, feature: str, outcome: str, q=5) -> pd.DataFrame:
    """Does this feature discriminate the outcome at all? Quintile table."""
    s = df[[feature, outcome]].dropna()
    s["bin"] = pd.qcut(s[feature], q, labels=False, duplicates="drop")
    g = s.groupby("bin")[outcome].agg(["mean", "count"])
    g["lo"], g["hi"] = zip(*[bootstrap_ci(s.loc[s.bin == b, outcome].to_numpy(float)) for b in g.index])
    g["feature_min"] = s.groupby("bin")[feature].min()
    g["feature_max"] = s.groupby("bin")[feature].max()
    return g


def stability(df: pd.DataFrame, labels: pd.Series, outcome: str) -> pd.DataFrame:
    """Same label stats in first half vs second half of the sample. If the
    sign of the effect flips, the label is noise."""
    mid = df.index[len(df) // 2]
    out = {}
    for name, sub in (("first_half", df.index < mid), ("second_half", df.index >= mid)):
        d, l = df[sub], labels[sub]
        base = d[outcome].mean()
        out[name] = d.groupby(l)[outcome].mean() - base
    return pd.DataFrame(out)


if __name__ == "__main__":
    from features import build, load_prices, load_vix
    df = build(load_prices(), load_vix())
    lab = label(df)
    pd.set_option("display.width", 200)
    print(lab.value_counts())
    br = base_rates(df, lab)
    cols = [c for c in br.columns if not c.endswith(("_lo", "_hi"))]
    print(br[cols].round(3).to_string())
    print("\nStability (deviation from baseline, out_range_atr):")
    print(stability(df, lab, "out_range_atr").round(3))
