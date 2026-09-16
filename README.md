# Session Conditions

Pre-open "what kind of day is today?" read for NQ day traders. Outputs a regime
label (STRETCHED / COILED / EXPANDED / HIGH_VOL / EVENT / BIG_GAP / NEUTRAL) and the
**backtested base rates** for days that looked like this before the open.
No forecasts — only historical frequencies with confidence intervals.

## Run it

```bash
pip install -r requirements.txt
python fetch_data.py        # pulls NQ, QQQ, VIX, VIX3M, VVIX, NDX, 60d of 5-min NQ  (needs internet)
python regime.py            # backtest: which labels actually discriminate, and are they stable?
python today.py             # writes docs/index.html + docs/today.json
open docs/index.html
```

The page renders from `data/qqq_daily.csv` (QQQ's open IS the true 9:30 ET RTH
open) rather than NQ futures — yfinance's NQ=F daily `open` is the Globex open,
not RTH, and contaminates gap stats. Tests: `python -m pytest tests/ -q`.

## Files

| file | job |
|---|---|
| `fetch_data.py` | data pull (Yahoo via yfinance), merge-don't-clobber guard, CBOE VIX3M supplement. |
| `events.py` | scheduled-event calendar: FOMC + CPI hardcoded, NFP/opex rule-generated. `data/events_override.csv` (date,event) adds/corrects. |
| `features.py` | pre-open features (strictly prior-day info + today's open) and same-day outcomes, kept separate. |
| `regime.py` | label rules (`P` dict), bootstrap base rates, feature quintile tables, first-half/second-half stability check. |
| `today.py` | renders the daily page. |

## Honesty rules baked in
- A label is only worth showing if its CI excludes the unconditional mean. The page dims rows that aren't.
- `stability()` splits the sample in half; if a label's effect flips sign, drop it.
- Thresholds in `regime.P` are deliberately few. Sweep them, but if you need >2 knobs to make a label "work," it doesn't.

## Known gaps
- Event Playbook tab (intraday move distributions around CPI/FOMC/NFP) needs multi-year 5-min data.
- FOMC/CPI calendars need refreshing periodically — `tests/test_events.py` fails once either runs under 60 days from its end.

## Daily automation

- LaunchAgent `com.johnsontrades.session-conditions` (copy in `deploy/`) runs
  `run_daily.sh` weekdays 7:40 AM CT: fetch → render → commit+push `docs/`.
- Page: https://johnsontrades1.github.io/session-conditions/ (Pages serves `main`/`docs`)
- Log: `logs/daily.log`. Stale date on the page = failed run — check the log.
- Manage: `launchctl unload/load ~/Library/LaunchAgents/com.johnsontrades.session-conditions.plist`
