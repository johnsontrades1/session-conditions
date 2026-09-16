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
    """Primary regime (mutually exclusive). Order matters: first match wins.

    2026-09-15 taxonomy split: EVENT and BIG_GAP are no longer in this chain —
    they are independent modifiers (see modifiers()). The old priority chain hid
    real conditions: a 98th-percentile gap vanished because COILED won priority
    and BIG_GAP only claimed otherwise-NEUTRAL days.
    """
    lab = pd.Series("NEUTRAL", index=f.index)
    stress = (f.get("vix_term", pd.Series(0, index=f.index)) > p["vix_stress"]) | (f.get("vix_rank_1y", pd.Series(0, index=f.index)) > p["vix_hi"])
    trending = (f.trend_20_atr.abs() >= p["trend_atr"]) & (f.er_10 >= p["er"])
    coiled = f.range_5_20 <= p["compress"]
    expanded = f.range_5_20 >= p["expand"]

    lab[stress] = "HIGH_VOL"
    # STRETCHED (né TREND): ≥3 ATR of 20d movement on a clean tape. Both the NQ
    # (Globex) and QQQ (RTH) backtests show these days run QUIETER — less range,
    # lower efficiency, fewer trend days. Extension exhausts; it doesn't continue.
    lab[~stress & trending] = "STRETCHED"
    lab[~stress & ~trending & coiled] = "COILED"
    lab[~stress & ~trending & expanded] = "EXPANDED"
    return lab


def modifiers(f: pd.DataFrame, p: dict = P) -> pd.DataFrame:
    """Independent boolean modifiers — may co-occur with any primary regime.
    Each is scored on its own against the unconditional baseline; no
    intersection stats (n goes thin fast — deliberately out of scope)."""
    return pd.DataFrame({
        "BIG_GAP": f.gap_atr >= p["gap_big"],
        "EVENT": (f.event_day | f.pre_fomc).astype(bool),
    }, index=f.index)


def modifier_rates(df: pd.DataFrame, mask: pd.Series, name: str, outcomes=OUTCOMES) -> pd.DataFrame:
    """base_rates() for one boolean condition: rows ALL + <name> (mask==True)."""
    lab = pd.Series("other", index=df.index)
    lab[mask] = name
    br = base_rates(df, lab, outcomes)
    return br.loc[["ALL", name]]


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
    mods = modifiers(df)
    pd.set_option("display.width", 200)
    print(lab.value_counts())
    br = base_rates(df, lab)
    cols = [c for c in br.columns if not c.endswith(("_lo", "_hi"))]
    print(br[cols].round(3).to_string())
    print("\nStability (deviation from baseline, out_range_atr):")
    print(stability(df, lab, "out_range_atr").round(3))
    for m in mods.columns:
        mr = modifier_rates(df, mods[m], m)
        print(f"\nModifier {m} (n={int(mr.loc[m,'n'])}, independent of primary):")
        print(mr[cols].round(3).to_string())
        ml = pd.Series("other", index=df.index)
        ml[mods[m]] = m
        print(stability(df, ml, "out_range_atr").round(3).loc[[m]].to_string())
