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
from regime import label, base_rates, OUTCOMES
from events import build_calendar

SITE = Path(__file__).parent / "docs"
SITE.mkdir(exist_ok=True)

DESCR = {
    "STRETCHED": "20-day move is extended (≥3 ATR) on a clean tape. Historically these sessions run QUIETER — smaller ranges, fewer trend days. Extension exhausts more often than it continues.",
    "COILED":   "Recent ranges are compressed vs. the 20-day norm. Historically compression PERSISTS — small-range days are more likely, not less. The spring stays coiled longer than folklore says.",
    "EXPANDED": "Ranges have already expanded well above the 20-day norm. Historically expansion persists — big-range days stay elevated. Don't fade range size early.",
    "HIGH_VOL": "VIX is elevated and/or term structure is inverted. Ranges are wider and directional days more common — size accordingly.",
    "EVENT":    "Scheduled macro event today (or FOMC tomorrow). Pre-event drift and post-release reversal patterns dominate.",
    "BIG_GAP":  "Opening gap is large in ATR terms. Historically these gaps DON'T fill same-day (~25% vs ~67% baseline on QQQ RTH) and ranges run wider.",
    "NEUTRAL":  "Nothing in the pre-open data stands out. Treat base rates as unconditional.",
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
    br = base_rates(df, labs)
    today = df.index[-1]
    row, lab = df.iloc[-1], labs.iloc[-1]

    feats = []
    for k, name in FEATS.items():
        if k in df and not pd.isna(row[k]):
            feats.append({"key": k, "name": name, "value": round(float(row[k]), 3), "pct_1y": round(pct_rank(df[k], row[k]), 2)})

    rates = []
    for oc in OUTCOMES:
        rates.append({
            "key": oc, "name": OUT_NAMES[oc],
            "cond": round(float(br.loc[lab, oc]), 3), "lo": round(float(br.loc[lab, oc + "_lo"]), 3), "hi": round(float(br.loc[lab, oc + "_hi"]), 3),
            "all": round(float(br.loc["ALL", oc]), 3), "sig": bool(br.loc[lab, oc + "_sig"]),
        })

    cal = build_calendar(str(today.date()), str((today + pd.Timedelta(days=10)).date()))
    events = [{"date": str(d.date()), "event": e} for d, e in zip(cal.date, cal.event)]

    payload = {
        "as_of": str(today.date()), "label": lab, "description": DESCR[lab],
        "n_days_like_this": int(br.loc[lab, "n"]), "n_all": int(br.loc["ALL", "n"]),
        "sample_start": str(df.index[0].date()), "features": feats, "base_rates": rates, "events": events,
        "label_counts": labs.value_counts().to_dict(),
        "data_source": data_source,
    }
    (SITE / "today.json").write_text(json.dumps(payload, indent=2))
    (SITE / "index.html").write_text(render(payload))
    print(f"{today.date()}  →  {lab}   ({payload['n_days_like_this']} similar sessions since {payload['sample_start']})")


def render(p: dict) -> str:
    def pct(x): return f"{x*100:.0f}%"
    def fmt(r):
        prob = r["key"].startswith(("out_trend", "out_big", "out_small", "out_gap"))
        f = pct if prob else (lambda x: f"{x:.2f}")
        arrow = "▲" if r["cond"] > r["all"] else "▼"
        cls = "sig" if r["sig"] else "ns"
        return (f'<tr class="{cls}"><td>{r["name"]}</td><td class="num">{f(r["cond"])} '
                f'<span class="ci">[{f(r["lo"])}–{f(r["hi"])}]</span></td><td class="num muted">{f(r["all"])}</td>'
                f'<td class="num">{arrow} {"" if r["sig"] else "n.s."}</td></tr>')
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
</style></head><body>
<h1>Session Conditions</h1><div class="sub">Pre-open read for {p["as_of"]}. Base rates, not forecasts. Data: {p["data_source"]}</div>
<div class="card"><div class="label">{p["label"]}</div><div>{p["description"]}</div>
<div class="muted" style="margin-top:8px">{p["n_days_like_this"]} sessions like this out of {p["n_all"]} since {p["sample_start"]}</div></div>
<div class="card"><table><tr><th>What days like this did</th><th class="num">Days like this <span class="ci">[95% CI]</span></th><th class="num">All days</th><th class="num"></th></tr>
{"".join(fmt(r) for r in p["base_rates"])}</table>
<div class="muted" style="font-size:12px;margin-top:8px">Rows dimmed as "n.s." are not statistically different from all days — don't trade them as if they were.</div></div>
<div class="card"><table><tr><th>Why</th><th class="num">Value</th><th class="num">1y percentile</th></tr>{feat_rows}</table></div>
<div class="card"><b>Scheduled events, next 10 days</b><ul style="margin-top:8px">{ev_rows}</ul></div>
<div class="foot">Every number is a historical frequency conditioned on information available before the open, computed from: {p["data_source"]}. Nothing here predicts direction. Not financial advice.</div>
</body></html>"""


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--prices", default="qqq_daily.csv")
    main(ap.parse_args().prices)
