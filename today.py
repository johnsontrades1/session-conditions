"""
Produce today's Session Conditions readout: docs/today.json + docs/index.html.

    python today.py                # forward pre-open read for the NEXT session
    python today.py --postopen     # optional 9:31 ET re-render: adds the real
                                    # gap/BIG_GAP if the open is in the data yet
    python today.py --prices synthetic_daily.csv

Renders a forward row dated for the next trading session, built from
completed-session data only (quick-260915-va7) — the historical backtest
(base rates, CIs, stability) is untouched and still comes from every real
completed session. gap_atr/BIG_GAP are absent from the default render (not
knowable pre-open) and only appear via --postopen once a real open exists.

The page shows: the label for the next session, why (feature values with 1y
percentile), the base rates for days like this vs. all days (with CIs), and
scheduled events. No forecasts anywhere.
"""
import argparse, json
from pathlib import Path
import numpy as np
import pandas as pd
from features import build, build_forward, load_prices, load_vix, resolve_price_source
from regime import label, modifiers, modifier_rates, base_rates, prob_at_least, OUTCOMES

ENV_OUTCOMES = ["out_up_exc", "out_dn_exc", "out_close_up"]  # range-envelope section
SLIDER_GRID_PTS = list(range(50, 601, 10))
from events import build_calendar, FULL_COVERAGE_START

SITE = Path(__file__).parent / "docs"
SITE.mkdir(exist_ok=True)
DATA = Path(__file__).parent / "data"

# Instrument settings for the point/dollar display translation. Internal stats
# stay percent-normalized (atr_pct × index level → points); only rendering uses this.
INSTRUMENT = dict(
    name="MNQ",
    dollars_per_point=2.0,          # MNQ multiplier
    index_file="ndx_daily.csv",     # ^NDX close = the level points are quoted on
)

DESCR = {  # primary regimes (mutually exclusive)
    "STRETCHED": "20-day move is extended (≥3 ATR) on a clean tape. Historically these sessions run QUIETER — smaller ranges, fewer trend days. Extension exhausts more often than it continues.",
    "COILED":   "Recent ranges are compressed vs. the 20-day norm. Volatility clusters — quiet tape tends to stay quiet near-term, so small-range days are MORE likely, not less. The 'coiled spring' pop is not the base case.",
    "EXPANDED": "Ranges have already expanded well above the 20-day norm. Volatility clusters — big-range days tend to stay elevated near-term. Don't fade range size early.",
    "HIGH_VOL": "VIX is elevated and/or term structure is inverted. Ranges are wider and directional days more common — size accordingly.",
    "NEUTRAL":  "Nothing in the pre-open regime data stands out. Treat base rates as unconditional.",
}
MOD_DESCR = {  # independent modifiers — may co-occur with any primary regime
    "BIG_GAP": "Opening gap is large (≥0.6 ATR). Same-day fill rate is low — arithmetic, not behavior: fill odds match what the gap distance and the day's range imply. Ranges run wider.",
    "EVENT":   "Scheduled macro event today (or FOMC tomorrow). Ranges run modestly wider and small-range days are less common — real but small (validated on the full 1999+ calendar).",
}
FEATS = {
    "gap_atr": "Opening gap (ATR units)", "range_5_20": "5d/20d range ratio", "prev_range_atr": "Yesterday's range (ATR)",
    "trend_20_atr": "20-day move (ATR)", "er_10": "Efficiency ratio (10d)", "pos_20d": "Position in 20d range",
    "vix": "VIX (prior close)", "vix_term": "VIX / VIX3M", "vix_rank_1y": "VIX 1y percentile", "rv5_rv20": "Realized vol 5d/20d",
}
OUT_NAMES = {
    "out_range_atr": "Session range (× ATR)", "out_eff": "Directional efficiency", "out_trend_day": "P(trend day)",
    "out_big_range": "P(range ≥ 1.3 ATR)", "out_small_range": "P(range ≤ 0.7 ATR)", "out_gap_filled": "P(gap filled)",
}


def pct_rank(series: pd.Series, value: float, window=252) -> float:
    s = series.dropna().tail(window)
    return float((s < value).mean()) if len(s) else np.nan


def _try_live_gap(prices_file: str, df_fwd: pd.DataFrame):
    """--postopen only. Reads the RAW price CSV directly (bypassing
    load_prices()'s dropna, which drops a partial current-day row before its
    close exists) looking for the forward date's own open. If found, computes
    gap_atr from it and returns df_fwd with that column added; otherwise
    returns None so the caller falls back to the pending-gap render. Never
    raises — the open genuinely may not exist yet (weekend re-run, market
    holiday, fetch hasn't happened)."""
    name, _ = resolve_price_source(prices_file)
    path = DATA / name
    if not path.exists():
        return None
    try:
        raw = pd.read_csv(path, parse_dates=["date"], index_col="date").sort_index()
    except Exception:
        return None
    fwd_date = df_fwd.index[-1]
    if fwd_date not in raw.index or "open" not in raw.columns:
        return None
    live_open = raw.loc[fwd_date, "open"]
    if pd.isna(live_open):
        return None
    prior_closes = raw.loc[:fwd_date].iloc[:-1]["close"].dropna() if "close" in raw.columns else pd.Series(dtype=float)
    if prior_closes.empty:
        return None
    prev_close = float(prior_closes.iloc[-1])
    atr20 = float(df_fwd["atr20"].iloc[-1])
    if not atr20:
        return None
    out = df_fwd.copy()
    out["gap_atr"] = abs(float(live_open) - prev_close) / atr20
    return out


def main(prices_file: str, postopen: bool = False):
    _, data_source = resolve_price_source(prices_file)
    # Historical backtest path — UNCHANGED. Every base rate, CI, and stability
    # figure on the page comes from this, exactly as before. Nothing about the
    # same-day-read fix touches this.
    prices = load_prices(prices_file)
    vix = load_vix()
    df = build(prices, vix)
    labs = label(df)
    mods_hist = modifiers(df)
    df_stats, labs_stats = df, labs
    br = base_rates(df_stats, labs_stats, outcomes=OUTCOMES + ENV_OUTCOMES)

    # Live render row — a FORWARD pre-open row for the next session by default
    # (quick-260915-va7), not df's last row (which is always the prior,
    # already-closed session — that was the one-session-lag bug). gap_atr is
    # structurally absent here; BIG_GAP is a post-open-only modifier.
    df_fwd = build_forward(prices, vix)
    lab_fwd = label(df_fwd).iloc[-1]
    mods_fwd = modifiers(df_fwd)
    gap_known = False

    if postopen:
        gap_row = _try_live_gap(prices_file, df_fwd)
        if gap_row is not None:
            df_fwd = gap_row
            mods_fwd = modifiers(df_fwd)
            gap_known = True

    today = df_fwd.index[-1]
    row, lab = df_fwd.iloc[-1], lab_fwd

    # Active modifiers, each scored INDEPENDENTLY vs the unconditional baseline.
    # No intersection stats — n goes thin, deliberately out of scope.
    def pctf(x): return f"{x*100:.0f}%"
    active_mods = []
    for m in mods_fwd.columns:
        if not bool(mods_fwd[m].iloc[-1]):
            continue
        # coverage guard (dormant: FULL_COVERAGE_START predates the sample)
        d = df if not (m == "EVENT" and df.index[0] < pd.Timestamp(FULL_COVERAGE_START)) \
            else df[df.index >= FULL_COVERAGE_START]
        # Rate stats always come from the HISTORICAL mask (mods_hist) — only
        # "is this modifier active today" comes from the forward row.
        mr = modifier_rates(d, mods_hist[m].reindex(d.index), m)
        if m == "BIG_GAP":
            line = (f"{int(mr.loc[m,'n'])} days like this: P(gap filled) {pctf(mr.loc[m,'out_gap_filled'])} "
                    f"vs {pctf(mr.loc['ALL','out_gap_filled'])} all days · range {mr.loc[m,'out_range_atr']:.2f}×ATR "
                    f"vs {mr.loc['ALL','out_range_atr']:.2f}")
        else:
            line = (f"{int(mr.loc[m,'n'])} days like this: range {mr.loc[m,'out_range_atr']:.2f}×ATR "
                    f"vs {mr.loc['ALL','out_range_atr']:.2f} · P(range ≤ 0.7 ATR) {pctf(mr.loc[m,'out_small_range'])} "
                    f"vs {pctf(mr.loc['ALL','out_small_range'])}")
        active_mods.append({"name": m, "description": MOD_DESCR[m], "line": line})

    feats = []
    for k, name in FEATS.items():
        if k in row.index and not pd.isna(row[k]):
            feats.append({"key": k, "name": name, "value": round(float(row[k]), 3), "pct_1y": round(pct_rank(df[k], row[k]), 2)})

    # Point/dollar translation at today's index level — display only; the
    # historical finding is the ATR multiple.
    atr_points = ndx_level = None
    ndx_file = DATA / INSTRUMENT["index_file"]
    if ndx_file.exists() and "atr_pct" in row and not pd.isna(row["atr_pct"]):
        ndx = pd.read_csv(ndx_file, parse_dates=["date"], index_col="date")["close"].dropna()
        if len(ndx):
            ndx_level = float(ndx.iloc[-1])
            atr_points = float(row["atr_pct"]) * ndx_level

    # --- Range Envelope: excursion above/below the open, direction null,
    # and a "does today clear my bar" slider driven by real empirical odds.
    # 2026-09-16 pre-flight null-check on out_close_up across every primary
    # label + modifier came back flat everywhere except a marginal, decaying,
    # non-robust STRETCHED reading (see QQQ-BACKTEST.md) — ruled NULL. No
    # directional claim ships from this section; both excursion halves use
    # the identical color/geometry logic on purpose.
    def _cvt(atr_mult):
        return round(atr_mult * atr_points) if atr_points else None

    up_p = {q: float(br.loc[lab, f"out_up_exc_p{q}"]) for q in (10, 25, 50, 75, 90)}
    dn_p = {q: float(br.loc[lab, f"out_dn_exc_p{q}"]) for q in (10, 25, 50, 75, 90)}

    # Recent candles + a PROJECTED RANGE next to them — never a projected
    # candle. A candle body implies a direction (up close vs down close);
    # this project's honesty rule 5 forbids that for anything not yet
    # observed. The projected column reuses the envelope's own up/dn
    # percentiles (symmetric, single color, both directions styled
    # identically) anchored at the last real close, on the SAME price axis
    # as the real candles for visual scale comparison — not a forecast shape.
    CHART_N = 15
    recent = prices.tail(CHART_N)
    anchor_price = float(recent["close"].iloc[-1])
    atr20_price = float(row["atr20"]) if "atr20" in row.index and not pd.isna(row["atr20"]) else None
    chart = None
    if atr20_price:
        chart = {
            "candles": [
                {"date": str(d.date()), "open": float(o), "high": float(h), "low": float(l), "close": float(c)}
                for d, o, h, l, c in zip(recent.index, recent["open"], recent["high"], recent["low"], recent["close"])
            ],
            "anchor": anchor_price,
            "proj_date": str(today.date()),
            "proj_up": {str(q): anchor_price + up_p[q] * atr20_price for q in up_p},
            "proj_dn": {str(q): anchor_price - dn_p[q] * atr20_price for q in dn_p},
        }

    gap_info = None
    if bool(mods_fwd["BIG_GAP"].iloc[-1]):
        gap_mr = modifier_rates(df_stats, mods_hist["BIG_GAP"].reindex(df_stats.index), "BIG_GAP", outcomes=["out_gap_filled"])
        gap_feat = next((f for f in feats if f["key"] == "gap_atr"), None)
        gap_info = {
            "atr": gap_feat["value"] if gap_feat else None,
            "pct_1y": round(gap_feat["pct_1y"] * 100) if gap_feat else None,
            "fill_pct": round(float(gap_mr.loc["BIG_GAP", "out_gap_filled"]) * 100),
        }

    slider = None
    if atr_points:
        thresholds_atr = [g / atr_points for g in SLIDER_GRID_PTS]
        x_today = df_stats.loc[labs_stats == lab, "out_range_atr"].to_numpy(dtype=float)
        x_all = df_stats["out_range_atr"].to_numpy(dtype=float)
        p_today = prob_at_least(x_today, thresholds_atr)
        p_all = prob_at_least(x_all, thresholds_atr)
        slider = {
            "pts": SLIDER_GRID_PTS,
            "today": [round(p_today[t] * 100, 1) for t in thresholds_atr],
            "all": [round(p_all[t] * 100, 1) for t in thresholds_atr],
        }

    # Significance + materiality gating (quick-260915-v0k): the envelope's read
    # lines were narrating non-significant differences as findings while the
    # base-rate table correctly dims the same underlying stats as n.s. — same
    # numbers, two honesty standards. Reuse the table's own sig flags here,
    # and add a materiality floor on top: at n in the thousands a <5% relative
    # gap can clear a 95% CI without meaning anything to a trader sizing a
    # trade off it. MATERIALITY_FLOOR is a floor, not a second significance
    # test — sig=True AND rel>=floor are both required.
    MATERIALITY_FLOOR = 0.05
    size_today_atr, size_all_atr = float(br.loc[lab, "out_range_atr"]), float(br.loc["ALL", "out_range_atr"])
    big_range_raw, big_range_all_raw = float(br.loc[lab, "out_big_range"]), float(br.loc["ALL", "out_big_range"])
    big_range_today, big_range_all = round(big_range_raw * 100), round(big_range_all_raw * 100)
    size_sig = bool(br.loc[lab, "out_range_atr_sig"])
    size_rel = abs(size_today_atr / size_all_atr - 1) if size_all_atr else 0
    size_material = size_sig and size_rel >= MATERIALITY_FLOOR
    big_sig = bool(br.loc[lab, "out_big_range_sig"])
    # Relative diff computed on the RAW fraction, not the rounded display
    # percentage — rounding both sides to whole points before dividing can
    # over- or under-state the true relative gap for borderline cases.
    big_rel = abs(big_range_raw / big_range_all_raw - 1) if big_range_all_raw else 0
    big_material = big_sig and big_rel >= MATERIALITY_FLOOR

    envelope = {
        "n": int(br.loc[lab, "n"]),
        "up": {str(q): {"atr": round(v, 3), "pts": _cvt(v)} for q, v in up_p.items()},
        "dn": {str(q): {"atr": round(v, 3), "pts": _cvt(v)} for q, v in dn_p.items()},
        "close_up_pct": round(float(br.loc[lab, "out_close_up"]) * 100, 1),
        "close_up_lo": round(float(br.loc[lab, "out_close_up_lo"]) * 100, 1),
        "close_up_hi": round(float(br.loc[lab, "out_close_up_hi"]) * 100, 1),
        "big_range_today": big_range_today,
        "big_range_all": big_range_all,
        "big_material": big_material,
        "size_today_pts": _cvt(size_today_atr),
        "size_all_pts": _cvt(size_all_atr),
        "size_today_atr": round(size_today_atr, 2),
        "size_all_atr": round(size_all_atr, 2),
        "size_material": size_material,
        "size_p25_pts": _cvt(float(br.loc[lab, "out_range_atr_p25"])),
        "size_p75_pts": _cvt(float(br.loc[lab, "out_range_atr_p75"])),
        "materiality_floor": MATERIALITY_FLOOR,
        "gap": gap_info,
        "slider": slider,
    }

    rates = []
    for oc in OUTCOMES:
        r = {
            "key": oc, "name": OUT_NAMES[oc],
            "cond": round(float(br.loc[lab, oc]), 3), "lo": round(float(br.loc[lab, oc + "_lo"]), 3), "hi": round(float(br.loc[lab, oc + "_hi"]), 3),
            "all": round(float(br.loc["ALL", oc]), 3), "sig": bool(br.loc[lab, oc + "_sig"]),
        }
        # IQR only for continuous outcomes — the actual spread of days, which is
        # what sizing cares about. Meaningless for the P(...) binary rows.
        if not oc.startswith(("out_trend", "out_big", "out_small", "out_gap")):
            r["p25"] = round(float(br.loc[lab, oc + "_p25"]), 3)
            r["p75"] = round(float(br.loc[lab, oc + "_p75"]), 3)
        if oc == "out_range_atr" and atr_points:  # only ATR-multiple rows convert to points
            dpp = INSTRUMENT["dollars_per_point"]
            r["pts"] = round(r["cond"] * atr_points)
            r["pts_all"] = round(r["all"] * atr_points)
            r["pts_p25"], r["pts_p75"] = round(r["p25"] * atr_points), round(r["p75"] * atr_points)
            r["usd_p25"], r["usd_p75"] = round(r["pts_p25"] * dpp), round(r["pts_p75"] * dpp)
        rates.append(r)

    cal = build_calendar(str(today.date()), str((today + pd.Timedelta(days=10)).date()))
    events = [{"date": str(d.date()), "event": e} for d, e in zip(cal.date, cal.event)]

    # Staleness: business days between the page's data date and the real today.
    # quick-260915-va7: `today` is now the FORWARD (next-session) date, so on a
    # healthy schedule it equals the viewer's actual current trading day — the
    # old 1-business-day tolerance existed only to paper over the one-session
    # lag this change removes, and made a stalled pipeline invisible. Anything
    # older than the current trading day is stale now.
    now = pd.Timestamp.now().normalize()
    age_bdays = max(0, len(pd.bdate_range(today, now)) - 1)
    stale = age_bdays > 0

    payload = {
        "as_of": str(today.date()), "label": lab, "description": DESCR[lab],
        "n_days_like_this": int(br.loc[lab, "n"]), "n_all": int(br.loc["ALL", "n"]),
        "sample_start": str(df_stats.index[0].date()), "features": feats, "base_rates": rates, "events": events,
        "label_counts": labs.value_counts().to_dict(),
        "modifier_counts": {m: int(mods_hist[m].sum()) for m in mods_hist.columns},
        "modifiers": active_mods,
        "gap_known": gap_known,
        "data_source": data_source,
        "age_bdays_at_render": int(age_bdays), "stale_at_render": bool(stale),
        "instrument": INSTRUMENT["name"], "dollars_per_point": INSTRUMENT["dollars_per_point"],
        "ndx_level": round(ndx_level, 1) if ndx_level else None,
        "atr_points": round(atr_points, 1) if atr_points else None,
        "envelope": envelope,
        "chart": chart,
    }
    (SITE / "today.json").write_text(json.dumps(payload, indent=2))
    (SITE / "index.html").write_text(render(payload))
    print(f"{today.date()}  →  {lab}   ({payload['n_days_like_this']} similar sessions since {payload['sample_start']})")


def candle_chart_html(p: dict) -> str:
    """Recent real daily candles + a PROJECTED RANGE column, sharing one
    price axis. The projected column is never a candle shape (no implied
    open/close direction) — it's the same style as the Range Envelope:
    symmetric whisker (p10-p90) + shaded box (p25-p75) + median tick, single
    accent color both directions, anchored at the last real close (dashed
    reference line). Server-rendered SVG, no client JS."""
    chart = p.get("chart")
    if not chart:
        return ""
    candles, anchor = chart["candles"], chart["anchor"]
    up, dn = chart["proj_up"], chart["proj_dn"]

    all_prices = [anchor, up["90"], dn["90"]]
    for c in candles:
        all_prices += [c["high"], c["low"]]
    p_min, p_max = min(all_prices), max(all_prices)
    pad = (p_max - p_min) * 0.06 or 1.0
    p_min, p_max = p_min - pad, p_max + pad

    MARGIN_L, MARGIN_T, MARGIN_B = 44, 14, 26
    COL_W, CANDLE_W, PROJ_W = 20, 10, 16
    PLOT_H = 190
    n_cols = len(candles) + 1
    width = MARGIN_L + n_cols * COL_W + 20

    def y(price):
        return MARGIN_T + (p_max - price) / (p_max - p_min) * PLOT_H

    def x_center(i):
        return MARGIN_L + i * COL_W + COL_W / 2

    parts = []
    # y-axis gridlines + labels (min/mid/max only, keep it uncluttered)
    for frac, price in ((0.0, p_max), (0.5, (p_max + p_min) / 2), (1.0, p_min)):
        gy = MARGIN_T + frac * PLOT_H
        parts.append(f'<line x1="{MARGIN_L-4}" y1="{gy:.1f}" x2="{width-10}" y2="{gy:.1f}" stroke="#262a35" stroke-width="1"/>')
        parts.append(f'<text x="{MARGIN_L-8}" y="{gy+3:.1f}" fill="#8b93a7" font-family="IBM Plex Mono, monospace" font-size="9" text-anchor="end">{price:.1f}</text>')

    for i, c in enumerate(candles):
        cx = x_center(i)
        up_day = c["close"] >= c["open"]
        color = "#4fd1c5" if up_day else "#e0836b"
        y_hi, y_lo = y(c["high"]), y(c["low"])
        y_op, y_cl = y(c["open"]), y(c["close"])
        body_top, body_h = min(y_op, y_cl), max(abs(y_cl - y_op), 1.0)
        parts.append(f'<line x1="{cx:.1f}" y1="{y_hi:.1f}" x2="{cx:.1f}" y2="{y_lo:.1f}" stroke="{color}" stroke-width="1.2"/>')
        parts.append(f'<rect x="{cx-CANDLE_W/2:.1f}" y="{body_top:.1f}" width="{CANDLE_W}" height="{body_h:.1f}" fill="{color}"/>')

    # Projected column — range only, identical styling both directions.
    px = x_center(len(candles))
    y_anchor = y(anchor)
    y_u90, y_u75, y_u50, y_u25 = y(up["90"]), y(up["75"]), y(up["50"]), y(up["25"])
    y_d90, y_d75, y_d50, y_d25 = y(dn["90"]), y(dn["75"]), y(dn["50"]), y(dn["25"])
    parts.append(f'<line x1="{MARGIN_L-4}" y1="{y_anchor:.1f}" x2="{width-10}" y2="{y_anchor:.1f}" stroke="#e8eaf0" stroke-width="1" stroke-dasharray="4 3" opacity="0.6"/>')
    parts.append(f'<line x1="{px:.1f}" y1="{y_u90:.1f}" x2="{px:.1f}" y2="{y_d90:.1f}" stroke="#4fd1c5" stroke-width="1" opacity="0.5"/>')
    parts.append(f'<rect x="{px-PROJ_W/2:.1f}" y="{y_u25:.1f}" width="{PROJ_W}" height="{max(y_u75-y_u25,1):.1f}" fill="#4fd1c5" opacity="0.30"/>')
    parts.append(f'<rect x="{px-PROJ_W/2:.1f}" y="{y_d25:.1f}" width="{PROJ_W}" height="{max(y_d75-y_d25,1):.1f}" fill="#4fd1c5" opacity="0.30"/>')
    parts.append(f'<line x1="{px-PROJ_W/2:.1f}" y1="{y_u50:.1f}" x2="{px+PROJ_W/2:.1f}" y2="{y_u50:.1f}" stroke="#4fd1c5" stroke-width="2"/>')
    parts.append(f'<line x1="{px-PROJ_W/2:.1f}" y1="{y_d50:.1f}" x2="{px+PROJ_W/2:.1f}" y2="{y_d50:.1f}" stroke="#4fd1c5" stroke-width="2"/>')

    height = MARGIN_T + PLOT_H + MARGIN_B
    date_lo = candles[0]["date"] if candles else ""
    date_hi = candles[-1]["date"] if candles else ""
    svg = (f'<svg viewBox="0 0 {width} {height}" role="img" '
           f'aria-label="{len(candles)} recent daily candles from {date_lo} to {date_hi}, '
           f'plus a projected range for {chart["proj_date"]} anchored at {anchor:.1f} — '
           f'range only, no direction shown for the projection.">'
           + "".join(parts) +
           f'<text x="{x_center(len(candles)//2):.1f}" y="{height-8}" fill="#8b93a7" font-family="IBM Plex Sans, sans-serif" font-size="9" text-anchor="middle">{date_lo} → {date_hi}</text>'
           f'<text x="{px:.1f}" y="{height-8}" fill="#4fd1c5" font-family="IBM Plex Sans, sans-serif" font-size="9" text-anchor="middle">{chart["proj_date"]}</text>'
           '</svg>')
    return (f'<div class="card"><div class="section-head"><h2 style="font-size:16px;margin:0;font-weight:600">Recent sessions + projected range</h2></div>'
            f'<p class="sub" style="color:var(--muted);font-size:13px;margin:4px 0 12px">Real daily candles, then the next session\'s range — teal band, no implied direction. Not a projected candle.</p>'
            f'{svg}</div>')


def envelope_svg(env: dict) -> str:
    """Range envelope: excursion above/below the open. Geometry scaled from
    the REAL p10/p25/p50/p75/p90 of this label's out_up_exc/out_dn_exc — not
    the mockup's fixed coordinates. Both halves use identical styling; this
    is a range display, never a directional one (see honesty rule 5)."""
    up, dn = env["up"], env["dn"]
    unit_pts = up["50"]["pts"] is not None
    def lbl(d, q): return f'{d[q]["pts"]}' if unit_pts else f'{d[q]["atr"]:.2f}×'
    def sign(v): return f"+{v}" if unit_pts else v

    OPEN_Y, MAX_PX = 150, 118
    max_extent = max(up["90"]["atr"], dn["90"]["atr"]) or 1.0
    def y_up(q): return OPEN_Y - (up[q]["atr"] / max_extent) * MAX_PX
    def y_dn(q): return OPEN_Y + (dn[q]["atr"] / max_extent) * MAX_PX

    u90, u75, u50, u25 = y_up("90"), y_up("75"), y_up("50"), y_up("25")
    d90, d75, d50, d25 = y_dn("90"), y_dn("75"), y_dn("50"), y_dn("25")
    # "HIGH REACHED" sits at u90-11; a 10px font's ascent needs more than the
    # 5px this margin used to leave above it, clipping glyph tops at any
    # rendered width (viewBox coordinates, not a phone-specific bug — just
    # most visible on a small screen). 24 leaves ~13px of clearance.
    top, bot = u90 - 24, d90 + 25

    return f"""<svg viewBox="0 0 340 {bot - top + 20:.0f}" role="img" aria-label="Range envelope: {env['n']} days like this reached a median of {sign(lbl(up,'50'))} above the open and {lbl(dn,'50')} below, middle 50% spanning {lbl(up,'25')}-{lbl(up,'75')} up and {lbl(dn,'25')}-{lbl(dn,'75')} down.">
  <g transform="translate(0,{-top:.0f})">
  <rect x="112" y="{u90:.1f}" width="96" height="{u25-u90:.1f}" fill="#4fd1c5" opacity="0.10"/>
  <rect x="112" y="{d25:.1f}" width="96" height="{d90-d25:.1f}" fill="#4fd1c5" opacity="0.10"/>
  <rect x="112" y="{u75:.1f}" width="96" height="{u25-u75:.1f}" fill="#4fd1c5" opacity="0.28"/>
  <rect x="112" y="{d25:.1f}" width="96" height="{d75-d25:.1f}" fill="#4fd1c5" opacity="0.28"/>
  <line x1="160" y1="{u90:.1f}" x2="160" y2="{d90:.1f}" stroke="#4fd1c5" stroke-width="1" opacity="0.45"/>
  <line x1="140" y1="{u90:.1f}" x2="180" y2="{u90:.1f}" stroke="#4fd1c5" stroke-width="1" opacity="0.5"/>
  <line x1="140" y1="{d90:.1f}" x2="180" y2="{d90:.1f}" stroke="#4fd1c5" stroke-width="1" opacity="0.5"/>
  <line x1="104" y1="{u50:.1f}" x2="216" y2="{u50:.1f}" stroke="#4fd1c5" stroke-width="2"/>
  <line x1="104" y1="{d50:.1f}" x2="216" y2="{d50:.1f}" stroke="#4fd1c5" stroke-width="2"/>
  <line x1="66" y1="{OPEN_Y}" x2="254" y2="{OPEN_Y}" stroke="#e8eaf0" stroke-width="1.5" stroke-dasharray="5 4"/>
  <text x="60" y="{OPEN_Y+4}" fill="#e8eaf0" font-family="IBM Plex Mono, monospace" font-size="10.5" text-anchor="end" letter-spacing="0.8">OPEN</text>
  <text x="226" y="{u90+4:.1f}" fill="#8b93a7" font-family="IBM Plex Mono, monospace" font-size="10.5">{sign(lbl(up,'90'))}</text>
  <text x="226" y="{u50+4:.1f}" fill="#e8eaf0" font-family="IBM Plex Mono, monospace" font-size="12" font-weight="500">{sign(lbl(up,'50'))}</text>
  <text x="226" y="{u25+4:.1f}" fill="#8b93a7" font-family="IBM Plex Mono, monospace" font-size="10.5">{sign(lbl(up,'25'))}</text>
  <text x="226" y="{d25+4:.1f}" fill="#8b93a7" font-family="IBM Plex Mono, monospace" font-size="10.5">-{lbl(dn,'25')}</text>
  <text x="226" y="{d50+4:.1f}" fill="#e8eaf0" font-family="IBM Plex Mono, monospace" font-size="12" font-weight="500">-{lbl(dn,'50')}</text>
  <text x="226" y="{d90+4:.1f}" fill="#8b93a7" font-family="IBM Plex Mono, monospace" font-size="10.5">-{lbl(dn,'90')}</text>
  <text x="104" y="{u90-11:.1f}" fill="#8b93a7" font-family="IBM Plex Sans, sans-serif" font-size="10" letter-spacing="1.1">HIGH REACHED</text>
  <text x="104" y="{d90+19:.1f}" fill="#8b93a7" font-family="IBM Plex Sans, sans-serif" font-size="10" letter-spacing="1.1">LOW REACHED</text>
  </g>
</svg>"""


def envelope_html(p: dict) -> str:
    env = p.get("envelope")
    if not env:
        return ""
    unit = "pts" if env["up"]["50"]["pts"] is not None else "× ATR"
    def sz(v_pts, v_atr): return f'{v_pts} pts' if v_pts is not None else f'{v_atr:.2f}× ATR'
    mods_stamp = " + ".join([p["label"]] + [m["name"] for m in p.get("modifiers", [])])

    gap_row = ""
    if env.get("gap"):
        g = env["gap"]
        gap_row = (f'<div class="read-item"><span class="read-label">The gap</span>'
                   f'<span class="read-value">Today opened <span class="num">{g["atr"]:.2f} ATR</span> away '
                   f'— {g["pct_1y"]}th percentile (trailing year). Gaps like this closed back to the prior '
                   f'session <span class="num">{g["fill_pct"]}%</span> of the time.</span></div>')

    size_pct = (env["size_today_pts"]/env["size_all_pts"] - 1)*100 if env["size_today_pts"] else \
               (env["size_today_atr"]/env["size_all_atr"] - 1)*100
    size_word = "smaller" if size_pct < 0 else "bigger"

    # Significance + materiality gating (quick-260915-v0k): the table dims
    # out_range_atr/out_big_range as n.s. for this label — the envelope must
    # apply the identical standard, not narrate the same non-difference as a
    # finding. size_material/big_material come from main() using the table's
    # own sig fields plus a 5% relative floor.
    if not env["size_material"] and not env["big_material"]:
        size_row = ('<div class="read-item"><span class="read-label">Size &amp; range odds</span>'
                    '<span class="read-value null-result">Nothing about today\'s setup separates it from '
                    'a typical session.</span></div>')
        big_row = ""
    else:
        if env["size_material"]:
            size_row = (f'<div class="read-item"><span class="read-label">Size of day</span>'
                        f'<span class="read-value"><span class="num">{sz(env["size_today_pts"], env["size_today_atr"])}</span> typical, vs '
                        f'<span class="num">{sz(env["size_all_pts"], env["size_all_atr"])}</span> on all days — about '
                        f'<b>{abs(size_pct):.0f}% {size_word}</b>.</span></div>')
        else:
            size_row = ('<div class="read-item"><span class="read-label">Size of day</span>'
                        '<span class="read-value null-result">No different from a normal session.</span></div>')
        if env["big_material"]:
            big_row = (f'<div class="read-item"><span class="read-label">Big-range odds</span>'
                       f'<span class="read-value">Only <span class="num">{env["big_range_today"]}%</span> ran &ge;1.3&times; ATR, '
                       f'against <span class="num">{env["big_range_all"]}%</span> normally.</span></div>')
        else:
            big_row = ('<div class="read-item"><span class="read-label">Big-range odds</span>'
                       '<span class="read-value null-result">No different from a normal session.</span></div>')

    slider_html = ""
    if env.get("slider"):
        default_i = len(env["slider"]["pts"]) // 4
        slider_html = f"""<div class="odds">
      <div class="odds-head"><h3>Does today clear your bar?</h3><span>Set the range your setup needs to work.</span></div>
      <div class="slider-row"><label for="needpts">Minimum session range</label>
        <input type="range" id="needpts" min="0" max="{len(env['slider']['pts'])-1}" step="1" value="{default_i}">
        <span class="pts" id="ptsout">{env['slider']['pts'][default_i]} pts</span></div>
      <div class="bars">
        <div class="bar-row"><span class="bar-name is-today">Days like today</span>
          <span class="track"><span class="fill is-today" id="fillA"></span></span><span class="bar-pct" id="pctA"></span></div>
        <div class="bar-row"><span class="bar-name">All days</span>
          <span class="track"><span class="fill" id="fillB"></span></span><span class="bar-pct" id="pctB"></span></div>
      </div>
      <p class="verdict" id="verdict"></p>
    </div>
    <script>
    (function(){{
      var PTS={env['slider']['pts']}, TODAY={env['slider']['today']}, ALL={env['slider']['all']};
      var slider=document.getElementById('needpts'), ptsout=document.getElementById('ptsout'),
          fillA=document.getElementById('fillA'), fillB=document.getElementById('fillB'),
          pctA=document.getElementById('pctA'), pctB=document.getElementById('pctB'), verdict=document.getElementById('verdict');
      function render(){{
        var i=Number(slider.value), pts=PTS[i], a=TODAY[i], b=ALL[i];
        ptsout.textContent=pts+' pts'; fillA.style.width=a+'%'; fillB.style.width=b+'%';
        pctA.textContent=a+'%'; pctB.textContent=b+'%';
        var diff=a-b, shape = diff<=-7 ? 'Meaningfully worse odds than a normal session.'
                    : diff>=7 ? 'Better odds than a normal session.' : 'About the same odds as a normal session.';
        verdict.innerHTML='<b>'+a+'% of days like this</b> gave at least '+pts+' points of range, against '+b+'% of all days. '+shape+' What that\\u2019s worth is your call.';
      }}
      slider.addEventListener('input', render); render();
    }})();
    </script>"""

    return f"""<div class="card">
    <div class="section-head"><h2 style="font-size:16px;margin:0;font-weight:600">Range envelope</h2>
      <span class="stamp">{mods_stamp} · n={env['n']:,}</span></div>
    <p class="sub" style="color:var(--muted);font-size:13px;margin:4px 0 18px">Excursion from the open on the {env['n']:,} past sessions that looked like this one. Range only — never direction. Differences under {env['materiality_floor']*100:.0f}% are called "no different," even when the CI clears — a materiality floor on top of the significance test, because at n={env['n']:,} a small gap can pass a CI check without meaning anything to a trader.</p>
    <div class="split">
      <div>{envelope_svg(env)}
        <p class="cap">Solid line = median · shaded = middle 50% · outer = 10th-90th{' · points at NDX level' if unit=='pts' else ''}</p>
      </div>
      <div class="read">
        {size_row}
        <div class="read-item"><span class="read-label">Direction</span>
          <span class="read-value null-result">No edge. Days like this closed above the open <span class="num">{env['close_up_pct']:.0f}%</span>
          of the time <span class="ci">[{env['close_up_lo']:.0f}-{env['close_up_hi']:.0f}%]</span> — a coin flip, and the page won't pretend otherwise.</span></div>
        {big_row}
        {gap_row}
      </div>
    </div>
    {slider_html}
  </div>"""


def render(p: dict) -> str:
    def pct(x): return f"{x*100:.0f}%"
    def fmt(r):
        prob = r["key"].startswith(("out_trend", "out_big", "out_small", "out_gap"))
        f = pct if prob else (lambda x: f"{x:.2f}")
        has_pts = "pts" in r  # points/dollar translation available (out_range_atr only)
        if has_pts:
            pct_vs_typical = (r["cond"] / r["all"] - 1) * 100 if r["all"] else 0
            cond_disp = f'{r["pts"]} pts <span class="muted">({r["cond"]:.2f}× ATR, {pct_vs_typical:+.0f}% vs typical)</span>'
            all_disp = f'{r["pts_all"]} pts <span class="muted">({r["all"]:.2f}× ATR)</span>'
        else:
            cond_disp, all_disp = f(r["cond"]), f(r["all"])
        arrow = "▲" if r["cond"] > r["all"] else "▼"
        cls = "sig" if r["sig"] else "ns"
        row = (f'<tr class="{cls}"><td>{r["name"]}</td><td class="num">{cond_disp} '
               f'<span class="ci">[{f(r["lo"])}–{f(r["hi"])}]</span></td><td class="num muted">{all_disp}</td>'
               f'<td class="num">{arrow} {"" if r["sig"] else "n.s."}</td></tr>')
        # IQR line: the actual spread of days like this — visually primary over
        # the CI, which only describes uncertainty about the average. Points +
        # dollars when the NDX conversion is available, ATR multiple otherwise.
        if "p25" in r:
            if has_pts:
                iqr_text = (f'Middle 50% of days like this: {r["pts_p25"]}–{r["pts_p75"]} pts '
                            f'<span class="muted">(~${r["usd_p25"]}–${r["usd_p75"]} per {p["instrument"]})</span>')
            else:
                iqr_text = f'Middle 50% of days like this: {r["p25"]:.2f} – {r["p75"]:.2f}'
            row += f'<tr class="{cls}"><td colspan="4" class="iqr">{iqr_text}</td></tr>'
        return row
    feat_rows = "".join(f'<tr><td>{x["name"]}</td><td class="num">{x["value"]}</td><td class="num muted">{pct(x["pct_1y"])} pct</td></tr>' for x in p["features"])
    ev_rows = "".join(f'<li><b>{e["date"]}</b> {e["event"]}</li>' for e in p["events"]) or "<li>None in the next 10 days</li>"
    return f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Session Conditions</title>
<style>
:root{{--bg:#0f1115;--card:#171a21;--fg:#e8eaf0;--muted:#8b93a7;--acc:#4fd1c5;--line:#262a35}}
body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 -apple-system,Inter,system-ui,sans-serif;padding:24px 16px;max-width:860px;margin:auto}}
h1{{font-size:20px;margin:0 0 4px}} .sub{{color:var(--muted);margin-bottom:24px}}
.label{{display:inline-block;font-size:34px;font-weight:700;letter-spacing:.02em;color:var(--acc);margin:6px 0}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px;margin:14px 0}}
table{{width:100%;border-collapse:collapse}} td{{padding:7px 4px;border-top:1px solid var(--line)}} tr:first-child td{{border-top:0}}
.num{{text-align:right;font-variant-numeric:tabular-nums}} .muted{{color:var(--muted)}} .ci{{color:var(--muted);font-size:12px}}
tr.ns td{{opacity:.55}} th{{text-align:left;color:var(--muted);font-weight:500;font-size:12px;padding:0 4px 6px}}
.foot{{color:var(--muted);font-size:12px;margin-top:24px}} ul{{margin:0;padding-left:18px}}
.iqr{{color:var(--fg);font-size:13px;padding-top:0 !important;border-top:0 !important;padding-bottom:10px}}
.mod{{border-left:3px solid var(--line);padding:8px 0 8px 12px;margin-top:14px}}
.modname{{font-size:15px;font-weight:600;color:var(--fg)}}
.modcopy{{font-size:13px;color:var(--muted);margin-top:2px}}
.modline{{font-size:13px;margin-top:4px;font-variant-numeric:tabular-nums}}
.mod-pending{{border-left:3px dashed var(--line);padding:8px 0 8px 12px;margin-top:14px;color:var(--muted);font-size:13px;font-style:italic}}
.stale{{display:none;background:#3a1d1d;border:1px solid #7a2e2e;color:#ffb4b4;border-radius:10px;padding:12px 14px;margin-bottom:16px;font-weight:600}}
.section-head{{display:flex;align-items:baseline;justify-content:space-between;gap:12px;flex-wrap:wrap}}
.stamp{{font-family:var(--mono,ui-monospace);font-size:11px;color:var(--muted);border:1px solid var(--line);border-radius:999px;padding:3px 9px}}
.split{{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:22px;align-items:start;margin-top:14px}}
@media (max-width:640px){{.split{{grid-template-columns:1fr;gap:18px}}}}
.split svg{{display:block;width:100%;max-width:100%;height:auto}}
.cap{{font-size:11.5px;color:var(--muted);text-align:center;margin:6px 0 0}}
.read{{display:flex;flex-direction:column;gap:14px}}
.read-item{{display:flex;flex-direction:column;gap:2px}}
.read-label{{font-size:10.5px;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);font-weight:600}}
.read-value{{font-size:14.5px}} .read-value.null-result{{color:var(--muted)}}
.odds{{margin-top:20px;padding-top:18px;border-top:1px solid var(--line)}}
.odds-head{{display:flex;align-items:baseline;justify-content:space-between;gap:10px;flex-wrap:wrap;margin-bottom:12px}}
.odds-head h3{{font-size:13px;margin:0;font-weight:600}} .odds-head span{{font-size:12px;color:var(--muted)}}
.slider-row{{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:16px}}
.slider-row label{{font-size:13px;color:var(--muted);flex:1 1 auto;min-width:170px}}
input[type=range]{{flex:2 1 220px;min-width:0;accent-color:var(--acc);height:22px;cursor:pointer}}
.pts{{font-family:var(--mono,ui-monospace);font-weight:600;color:var(--acc);font-size:15px;min-width:74px;text-align:right}}
.bars{{display:flex;flex-direction:column;gap:9px}}
.bar-row{{display:grid;grid-template-columns:118px minmax(0,1fr) 46px;gap:10px;align-items:center}}
.bar-name{{font-size:12.5px;color:var(--muted)}} .bar-name.is-today{{color:var(--fg);font-weight:500}}
.track{{display:block;background:#1d212a;border-radius:3px;height:9px;overflow:hidden}}
.fill{{display:block;height:100%;background:#2a7c76;border-radius:3px;transition:width .12s ease-out;width:0}}
.fill.is-today{{background:var(--acc)}}
.bar-pct{{font-family:var(--mono,ui-monospace);font-size:13px;text-align:right;font-variant-numeric:tabular-nums}}
.verdict{{margin-top:14px;font-size:13.5px;color:var(--muted)}} .verdict b{{color:var(--fg);font-weight:600}}
</style></head><body>
<div id="stale" class="stale"></div>
<h1>Session Conditions</h1><div class="sub">Pre-open read for {p["as_of"]}. Base rates, not forecasts. Data: {p["data_source"]}</div>
<script>
// Staleness computed in the BROWSER, not at render time — a dead pipeline
// never re-renders, so only the viewer's clock can catch a frozen page.
// quick-260915-va7: as_of is now the FORWARD (next-session) date, so on a
// healthy schedule it equals today — any lag at all means the pipeline
// didn't run. The old >1 tolerance existed only to hide that lag.
(function() {{
  var asOf = new Date("{p["as_of"]}T00:00:00");
  var now = new Date(); now.setHours(0,0,0,0);
  var bdays = 0, d = new Date(asOf);
  while (d < now) {{ d.setDate(d.getDate() + 1); var w = d.getDay(); if (w !== 0 && w !== 6) bdays++; }}
  if (bdays > 0) {{
    var el = document.getElementById("stale");
    el.textContent = "⚠ STALE DATA — this page's data is from {p["as_of"]}, " + bdays +
      " trading days old. The daily pipeline likely failed; check logs/daily.log on the Mac Mini.";
    el.style.display = "block";
  }}
}})();
</script>
<div class="card"><div class="label">{p["label"]}</div><div>{p["description"]}</div>
<div class="muted" style="margin-top:8px">{p["n_days_like_this"]} sessions like this out of {p["n_all"]} since {p["sample_start"]}</div>
{"".join(f'<div class="mod"><div class="modname">+ {m["name"]}</div><div class="modcopy">{m["description"]}</div><div class="modline">{m["line"]}</div></div>' for m in p.get("modifiers", []))}
{'<div class="mod-pending">Gap: not yet known — updates after the open.</div>' if not p.get("gap_known") else ""}</div>
{candle_chart_html(p)}
{envelope_html(p)}
<div class="card"><table><tr><th>What days like this did</th><th class="num">Days like this <span class="ci">[95% CI]</span></th><th class="num">All days</th><th class="num"></th></tr>
{"".join(fmt(r) for r in p["base_rates"])}</table>
<div class="muted" style="font-size:12px;margin-top:8px">Rows dimmed as "n.s." are not statistically different from all days — don't trade them as if they were.</div></div>
<div class="card"><table><tr><th>Why</th><th class="num">Value</th><th class="num">1y percentile</th></tr>{feat_rows}</table></div>
<div class="card"><b>Scheduled events, next 10 days</b><ul style="margin-top:8px">{ev_rows}</ul></div>
<div class="foot">Every number is a historical frequency conditioned on information available before the open, computed from: {p["data_source"]}. Nothing here predicts direction. Not financial advice.
{f' Point/dollar figures ({p["instrument"]}, ${p["dollars_per_point"]:.0f}/pt) are today\'s translation of the historical ATR-percent finding at the current index level (NDX {p["ndx_level"]:,.0f}) — they shift as the index does; the ATR multiple is the stable finding.' if p.get("ndx_level") else ""}</div>
</body></html>"""


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--prices", default="qqq_daily.csv")
    ap.add_argument("--postopen", action="store_true",
                     help="Optional 9:31 ET re-render: use the real open if available (adds gap/BIG_GAP); "
                          "falls back to the pre-open forward render if the open isn't in the data yet.")
    args = ap.parse_args()
    main(args.prices, postopen=args.postopen)
