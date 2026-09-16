"""
Produce today's Session Conditions readout: docs/today.json + docs/index.html.

    python today.py                # uses data/qqq_daily.csv (Phase 2 validated source)
    python today.py --prices synthetic_daily.csv

The page shows: today's regime label, why (feature values with 1y percentile),
the base rates for days like this vs. all days (with CIs), and scheduled
events. No forecasts anywhere.
"""
import argparse, json
from pathlib import Path
import numpy as np
import pandas as pd
from features import build, load_prices, load_vix, resolve_price_source
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


def main(prices_file: str):
    _, data_source = resolve_price_source(prices_file)
    df = build(load_prices(prices_file), load_vix())
    labs = label(df)
    mods = modifiers(df)
    today = df.index[-1]
    row, lab = df.iloc[-1], labs.iloc[-1]
    df_stats, labs_stats = df, labs
    br = base_rates(df_stats, labs_stats, outcomes=OUTCOMES + ENV_OUTCOMES)

    # Active modifiers, each scored INDEPENDENTLY vs the unconditional baseline.
    # No intersection stats — n goes thin, deliberately out of scope.
    def pctf(x): return f"{x*100:.0f}%"
    active_mods = []
    for m in mods.columns:
        if not bool(mods[m].iloc[-1]):
            continue
        # coverage guard (dormant: FULL_COVERAGE_START predates the sample)
        d = df if not (m == "EVENT" and df.index[0] < pd.Timestamp(FULL_COVERAGE_START)) \
            else df[df.index >= FULL_COVERAGE_START]
        mm = mods[m].reindex(d.index)
        mr = modifier_rates(d, mm, m)
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
        if k in df and not pd.isna(row[k]):
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
    gap_info = None
    if bool(mods["BIG_GAP"].iloc[-1]):
        gap_mr = modifier_rates(df_stats, mods["BIG_GAP"].reindex(df_stats.index), "BIG_GAP", outcomes=["out_gap_filled"])
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
    # 0-1 is normal (yesterday's completed session renders pre-open). More than
    # 1 means the pipeline failed or the data source stalled — say so loudly
    # instead of silently serving old numbers (which happened on 2026-09-14/15).
    now = pd.Timestamp.now().normalize()
    age_bdays = max(0, len(pd.bdate_range(today, now)) - 1)
    stale = age_bdays > 1

    payload = {
        "as_of": str(today.date()), "label": lab, "description": DESCR[lab],
        "n_days_like_this": int(br.loc[lab, "n"]), "n_all": int(br.loc["ALL", "n"]),
        "sample_start": str(df_stats.index[0].date()), "features": feats, "base_rates": rates, "events": events,
        "label_counts": labs.value_counts().to_dict(),
        "modifier_counts": {m: int(mods[m].sum()) for m in mods.columns},
        "modifiers": active_mods,
        "data_source": data_source,
        "age_bdays_at_render": int(age_bdays), "stale_at_render": bool(stale),
        "instrument": INSTRUMENT["name"], "dollars_per_point": INSTRUMENT["dollars_per_point"],
        "ndx_level": round(ndx_level, 1) if ndx_level else None,
        "atr_points": round(atr_points, 1) if atr_points else None,
        "envelope": envelope,
    }
    (SITE / "today.json").write_text(json.dumps(payload, indent=2))
    (SITE / "index.html").write_text(render(payload))
    print(f"{today.date()}  →  {lab}   ({payload['n_days_like_this']} similar sessions since {payload['sample_start']})")


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
    top, bot = u90 - 16, d90 + 25

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
(function() {{
  var asOf = new Date("{p["as_of"]}T00:00:00");
  var now = new Date(); now.setHours(0,0,0,0);
  var bdays = 0, d = new Date(asOf);
  while (d < now) {{ d.setDate(d.getDate() + 1); var w = d.getDay(); if (w !== 0 && w !== 6) bdays++; }}
  if (bdays > 1) {{
    var el = document.getElementById("stale");
    el.textContent = "⚠ STALE DATA — this page's data is from {p["as_of"]}, " + bdays +
      " trading days old. The daily pipeline likely failed; check logs/daily.log on the Mac Mini.";
    el.style.display = "block";
  }}
}})();
</script>
<div class="card"><div class="label">{p["label"]}</div><div>{p["description"]}</div>
<div class="muted" style="margin-top:8px">{p["n_days_like_this"]} sessions like this out of {p["n_all"]} since {p["sample_start"]}</div>
{"".join(f'<div class="mod"><div class="modname">+ {m["name"]}</div><div class="modcopy">{m["description"]}</div><div class="modline">{m["line"]}</div></div>' for m in p.get("modifiers", []))}</div>
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
    ap = argparse.ArgumentParser(); ap.add_argument("--prices", default="qqq_daily.csv")
    main(ap.parse_args().prices)
