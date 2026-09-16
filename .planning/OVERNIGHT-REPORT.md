# Overnight Report — 2026-09-15/16

Read order: failures first, then what shipped, then what's uncommitted and why.

## ⚠ Failures / things you should know

1. **The morning LaunchAgent run silently destroyed data.** The 7:40 AM pull got a
   truncated ^VIX3M history from yfinance (ended 2026-07-17) and `fetch_data.py`
   overwrote the good file (which had been current through 09-14). `vix_term` — a
   HIGH_VOL input — was ffilled from July for the whole day. I wrote a
   merge-don't-clobber guard + CBOE official-history supplement and verified all five
   series current through 09-15, **but you rejected that commit and then scoped the
   night to two other tasks, so the fix sits UNCOMMITTED in the working tree**
   (`fetch_data.py`, plus a stale-caveat edit to `QQQ-BACKTEST.md`). The healed CSVs
   are on disk either way (data/ is gitignored). Decide with coffee: `git add
   fetch_data.py .planning/phases/02-label-kill-keep/QQQ-BACKTEST.md && git commit`,
   or `git checkout fetch_data.py` and it re-breaks on the next yfinance flake.
2. **Page-date semantics are unresolved (judgment call, parked per your rules).**
   The QQQ switch means the page labels the last COMPLETED session — Tuesday
   morning's page says "read for Monday." NQ Globex data gave a same-day open
   pre-open; QQQ can't. Options: (a) accept and relabel copy "conditions entering
   [next session]" — honest, zero code; (b) hybrid: today's gap from NQ Globex quote
   at 7:40, everything else QQQ — reintroduces the contaminated source for one
   feature; (c) render at 9:31 ET instead of 7:40 — true same-day RTH open, but page
   lands after your kill-zone prep. My recommendation: (a) now, (c) later if wanted.
   Not implemented — it changes what the tool claims.
3. **Could not verify page at 400px visually** — no browser extension connected
   overnight. Structure is single-column, all-relative widths, modifiers are stacked
   divs; should be fine, but eyeball it on your phone.
4. **CPI backfill trust level:** majority-voted across 5 extraction passes of the BLS
   archive index (the fetch summarizer made errors — first pass had two fabricated
   codes I discarded), then 3 releases verified against in-document embargo lines
   (2001-01-17, 2010-01-15, shutdown-delayed 2013-10-30) and 2022-01-12 matches your
   previously hardcoded schedule. FOMC verified against per-year Fed pages + Wikipedia
   actions table (full 2003 + 3 landmarks). I'd call it solid; it is still scraped.

## ✅ Unattended run verified (the v1.0 open item)

LaunchAgent fired 07:40:05, full pipeline, `=== run ok ===`, page current. That was
the last unverified piece of v1.0. (It also caused failure #1 above — a productive
failure.)

## ✅ Task: vol-matched gap-fill null → pure arithmetic

Two independent nulls conditioned on realized range (same-range-decile excursion
draw; open-placement-fraction). The +9–10pp big-gap excess over the unconditional
null **collapses to +2.3pp, 95% CI [−0.2, +4.9]** — includes zero, both variants
agree, half-split consistent (+3.0/+1.6). Fill decline is distance + that day's
range, nothing behavioral, in either direction. BIG_GAP copy stripped of hedging;
method + table in QQQ-BACKTEST.md. Commit e9fcc57.

## ✅ Task: event calendar backfill → EVENT verdict KEEP

- FOMC 1999–2014 from federalreserve.gov (scheduled decision days only; emergency
  calls excluded by design). CPI 1999–2021 from BLS archives. NFP holiday shifts
  extended. `FULL_COVERAGE_START` 2022→1999. 4 new calendar tests.
- Worse than diagnosed: `build_calendar()` started at 2010 — 1999–2009 had ZERO
  events. Four different label definitions across the sample.
- Full clean-span re-score: n=1047, share uniform 14–16% in every era, range CI
  [0.948, 0.999] excludes baseline, big/small-range sig, zero stability flips.
  **EVENT: UNPROVEN → KEEP.** Modest effect, honestly earned. Commit a813128.

## ✅ Task: taxonomy split (your scope message)

`label()` = primary only (HIGH_VOL/STRETCHED/COILED/EXPANDED/NEUTRAL);
`modifiers()` = independent BIG_GAP + EVENT booleans. Each modifier scored alone vs
baseline — both pass CI + stability as modifiers (BIG_GAP n=793: range 1.142 sig,
fill 27.4% vs 67.4% sig, no flips; EVENT n=1047 identical mask to KEEP verdict).
No intersection stats, per scope. Page: primary prominent, modifiers as secondary
rows with own copy + one base-rate line. **2026-09-14 now renders COILED + BIG_GAP —
the 1.468 ATR gap the old priority chain swallowed.** Commit 3346681.

## ✅ Task: loud staleness (your scope message)

Banner computes in the BROWSER (business days from as_of to viewer's date, >1 →
red banner naming data date, age, and logs/daily.log). Client-side because a dead
pipeline never re-renders — render-time flags can't catch a frozen page. Weekend-
aware (Fri data on Mon = no banner). Render-time age also in today.json. Edge cases
unit-checked. Commit 09706ea.

## State of the tree

- Pushed: e9fcc57, a813128, 3346681, 09706ea (+ docs re-renders).
- Uncommitted: `fetch_data.py` (merge guard + CBOE VIX3M), `QQQ-BACKTEST.md`
  (one stale caveat block rewritten). Your call.
- Not touched: milestone status, STATE.md, audits — per your rules.
- Tomorrow 7:40 AM: pipeline pulls 9/15's completed QQQ row (tonight it was
  NaN-close partial, correctly dropped) and the page shows 9/15 with the new
  modifier layout. Glance at the Pages URL + logs/daily.log.

## Pushback

- The EVENT effect is real but small (range 0.973 vs 0.934). It earns its page row;
  it does not earn position sizing. Don't let the label name do more work than the CI.
- The uncommitted fetch guard is the most operationally important change of the
  night — a repeat yfinance flake without it re-poisons vix_term silently. If you
  keep only one thing from the rejected commit, keep `merge_save()`.
