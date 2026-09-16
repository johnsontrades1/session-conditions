---
quick_id: 260915-va7
status: complete
---

# Quick Task 260915-va7 — Summary

## What was done

**features.py** — `next_trading_date()` + `build_forward()`. Appends one
phantom row (NaN OHLC) dated for the next trading session, then reuses the
existing `build()` unchanged. Verified by hand-tracing every whitelisted
feature's dependency chain (atr20, range_5_20, prev_range_atr, trend_20_atr,
er_10, pos_20d, rv5_rv20, vix/vix_term/vix_rank_1y, event flags) — each one
already only reads `.shift(1)`'d or historically-windowed values, so the
forward row comes out correct with zero changes to any feature formula.
Included `atr_pct` beyond the original whitelist (needed by the existing
points/dollar display, forward-safe by the same argument).

**regime.py** — `modifiers()` now falls back to all-False for BIG_GAP when
`gap_atr` isn't in the frame (mirrors label()'s existing `f.get(...)`
pattern), instead of raising. This is what makes BIG_GAP structurally
post-open-only.

**today.py** — historical `df`/`labs`/`br` (backtest, base rates, CIs)
untouched. New `df_fwd = build_forward(prices, vix)` drives the live render:
`today`/`row`/`lab` now come from the forward row, so `as_of` is the NEXT
session by construction. `mods_hist` (historical) still feeds every rate
statistic; `mods_fwd` (single row) only answers "is this modifier active
right now." Added a "Gap: not yet known — updates after the open." note
(`.mod-pending` style) whenever the gap isn't known. Staleness threshold
tightened `age_bdays > 1` → `> 0` in both the Python payload flag and the
browser-side JS — the 1-day tolerance existed only to hide the lag this
fix removes. Added `--postopen`: reads the raw price CSV directly (bypassing
`load_prices()`'s dropna, which drops a partial current-day row before its
close exists), and if the forward date's real `open` is present, computes
`gap_atr` from it and re-runs `modifiers()` so BIG_GAP can fire — falls back
silently to the pending-gap render if the open isn't there yet.

**run_daily.sh / run_postopen.sh (new)** — commit messages now use the
rendered `as_of` date instead of the shell's `date +%F`, since those can
differ now that as_of is a forward date.

**deploy/com.johnsontrades.session-conditions-postopen.plist (new)** —
optional 9:31 ET (8:31 CT) LaunchAgent entry, its own Label (separate plist,
since the two runs need different scripts, not just different times on the
same one). NOT loaded — documented, user activates manually.

**README.md** — documented the forward-row behavior, `--postopen`, and the
new optional plist.

## Verification

- `build_forward()`: 1 row, dated after the last historical row, no
  gap/open/high/low/close columns, atr20 non-NaN
- `label()`/`modifiers()` on the forward row: valid regime (NEUTRAL),
  BIG_GAP False, EVENT True (real FOMC meeting the next day — confirms
  event_flags works correctly for a future date)
- `python today.py`: as_of = 2026-09-16 (the actual next session, one day
  ahead of the last row in data/qqq_daily.csv), no gap_atr feature, pending
  note present, EVENT modifier only
- `python today.py --postopen` with no live open available: falls back
  cleanly, no crash, gap_known=False
- `python today.py --postopen` against a synthetic CSV with a live partial
  row (real open, NaN close): correctly detected the open, computed
  gap_atr=1.72, fired BIG_GAP alongside EVENT
- pytest 11/11 green throughout
- `bash run_daily.sh` end-to-end: published to Pages, docs/today.json
  confirms as_of=2026-09-16 live on the site
- `plutil -lint` on the new plist: OK; `bash -n` on both scripts: OK;
  confirmed not loaded in `launchctl list`

## Deviation

Removed a duplicate `load_prices()`/`load_vix()` call in `main()` (df and
df_fwd were each independently reloading) — same disk read + duplicate "open
source" print twice per run. Passed the already-loaded `prices`/`vix`
objects to both `build()` and `build_forward()` instead. Also fixed the
commit-message date mismatch in run_daily.sh (noticed while testing that the
git commit says "2026-09-15" while the published as_of is "2026-09-16") —
applied the same fix to the new run_postopen.sh for consistency.

## Not implemented / known limitation

`next_trading_date()` is weekend-aware only, not market-holiday-aware —
matches this project's existing calendar precision level elsewhere (events.py
NFP generation has the same limitation). A market holiday will render a
forward row for a day the market is actually closed. Not fixed here; flagging
as a known gap, not a silent one.
