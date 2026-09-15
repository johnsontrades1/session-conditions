# Session Conditions

Pre-open "what kind of day is today?" read for NQ day traders. Outputs a regime
label (TREND / COILED / EXPANDED / HIGH_VOL / EVENT / BIG_GAP / NEUTRAL) and the
**backtested base rates** for days that looked like this before the open.
No forecasts — only historical frequencies with confidence intervals.

## Run it

```bash
pip install -r requirements.txt
python fetch_data.py        # pulls NQ, QQQ, VIX, VIX3M, VVIX, 60d of 5-min NQ  (needs internet)
export DATABENTO_API_KEY=db-...   # databento.com signup, free $125 credit
python fetch_databento.py   # NQ RTH daily bars (true 9:30 ET opens) — incremental, cost-guarded
python regime.py            # backtest: which labels actually discriminate, and are they stable?
python today.py             # writes site/index.html + site/today.json
open site/index.html
```

`features.py` automatically prefers `data/nq_rth_daily.csv` (RTH opens) when it
exists and falls back to yfinance's `nq_daily.csv` (Globex opens) otherwise —
each run prints which source is active. Tests: `python -m pytest tests/ -q`
(no API key needed).

## Files

| file | job |
|---|---|
| `fetch_data.py` | data pull (Yahoo via yfinance). Swap in Databento/ProjectX later for true RTH opens and long intraday history. |
| `events.py` | scheduled-event calendar: FOMC + CPI hardcoded, NFP/opex rule-generated. `data/events_override.csv` (date,event) adds/corrects. |
| `features.py` | pre-open features (strictly prior-day info + today's open) and same-day outcomes, kept separate. |
| `regime.py` | label rules (`P` dict), bootstrap base rates, feature quintile tables, first-half/second-half stability check. |
| `today.py` | renders the daily page. |

## Honesty rules baked in
- A label is only worth showing if its CI excludes the unconditional mean. The page dims rows that aren't.
- `stability()` splits the sample in half; if a label's effect flips sign, drop it.
- Thresholds in `regime.P` are deliberately few. Sweep them, but if you need >2 knobs to make a label "work," it doesn't.

## Known gaps (day 2+)
- ~~yfinance's NQ daily `open` is the Globex open, not 9:30 RTH.~~ Resolved by
  `fetch_databento.py` once the first live backfill runs (needs `DATABENTO_API_KEY`).
  First-run spot-check: compare a few `nq_rth_daily.csv` opens vs known 9:30 ET prints.
- CPI dates for 2025+ need checking against bls.gov/schedule.
- Event Playbook tab (intraday move distributions around CPI/FOMC/NFP) needs multi-year 5-min data — Bloomberg (SCSU) or Databento's free credit.
