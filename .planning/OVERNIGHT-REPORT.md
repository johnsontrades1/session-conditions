# Overnight Report — 2026-09-18

Read order: failures/pushback first, then what shipped, then verification detail.

## ⚠ Failures / things that did NOT get done

**None of the 3 tasks were skipped.** All three shipped and were verified. But
two things are worth your attention as near-misses, not clean passes:

1. **`data/calibration.csv` almost didn't get committed.** The broad
   `data/*.csv` gitignore rule (correctly added a few tasks ago to keep the
   OHLC caches out of git) also caught the one CSV you explicitly asked to
   commit. Caught it on the first commit attempt (git refused, told me why),
   added a `!data/calibration.csv` negation exception. Flagging because it's
   the kind of thing that fails silently if the negation exception itself
   gets pruned later — if calibration.csv ever stops showing up in `git log`,
   check `.gitignore` first.
2. **Pre-2026-09-14T22:47 calibration rows are source-mismatched.** The
   calibration backfill always scores realized outcomes against the QQQ
   historical build(), but the earliest 1-2 committed `today.json` snapshots
   were rendered from NQ Globex data (before the QQQ pivot). Those rows exist
   in `data/calibration.csv` but compare a Globex-based prediction to a
   QQQ-based realization. Documented in the commit message, not fixed —
   fixing it means hardcoding a source-cutover date into a scoreboard script,
   which felt like more complexity than a 1-2 row cosmetic issue warranted.
   Your call if you want it cleaned up later.

Nothing was judged too risky to attempt and skipped. If I'd hit that, this
section would say so explicitly.

## ✅ Hard constraint: the unattended fire

**This already happened, three times, before tonight started.** Checked
`logs/daily.log` before touching anything: 2026-09-16, 2026-09-17, and
2026-09-18's 7:40 CT fires all completed with `=== run ok ===` and zero
`FATAL` entries. The 09-16 log line even shows the exact mechanism working —
it correctly computed `2026-09-16 → NEUTRAL` (the forward date) and then
logged "docs/ unchanged — nothing to publish" because that content was
already live from a manual test the night before. That's correct behavior,
not a bug. The fear behind the hard constraint — "has never survived an
unattended fire" — was accurate when you wrote it and is no longer true.

I still treated every touch to `today.py` tonight as if the constraint were
live (rendered + checked `as_of` after every change, per your rule), because
my OWN changes could break something even though the pipeline was healthy
going in. Final state after tonight's SVG fix: `python today.py` → `as_of:
2026-09-21` (correctly the next trading day after Friday 09-18, weekend
skipped), 11/11 tests green, full `run_daily.sh` executed end-to-end and
published.

## Task 1 — the two recorders

**`record_intraday.py`** (commit `7dc1366`) — accumulates NQ 5m bars into
`data/intraday/NQ_5m.csv` (gitignored) beyond yfinance's rolling 60-day
window. Merge-don't-clobber, dedupe on timestamp keep-last. Verified:
first run added 13,658 rows; immediate re-run added 0 (idempotent); simulated
an empty yfinance response and confirmed the 13,658 accumulated rows survived
untouched (exit 0, no data loss). First real run through `run_daily.sh`
tonight added 758 new rows.

**`record_calibration.py`** (commit `dd988ad`) — backfilled 5 rows from
every commit that ever touched `docs/today.json`, then filled realized
outcomes for the 4 that have since closed straight from the same historical
`build()` the backtest uses. Idempotent (verified: re-run added 0/0).
**It is a scoreboard.** Nothing reads it back into `regime.py` or
`features.py`; I did not write, and would not write, any code that adjusts
a threshold or label from this file — per your explicit instruction, that
would be the one thing not to do here.

**Wired into `run_daily.sh`** (commit `dd988ad`'s sibling in the run script,
folded into the alerting commit `55e55c2` for the actual wiring — see diff)
as non-fatal: both run between `fetch_data.py` and `today.py`, failures log
a `WARN` and the script continues. Verified live: full `run_daily.sh` run
tonight executed both recorders, then rendered, then published — all in one
real pass, not just a unit test.

## Task 2 — failure alerting

`run_daily.sh` and `run_postopen.sh` (commit `55e55c2`) now fire an
`osascript` notification on every `FATAL` before exiting. Tested `osascript`
directly on this machine — it fires, exit 0.

**Did not touch sudo/pmset**, per your instruction. Wrote `SETUP.md` with
both options and a recommendation: disable sleep entirely
(`sudo pmset -a sleep 0 disablesleep 1`), because this Mac Mini already runs
multiple always-on LaunchAgents (Kalshi bot, Polymarket proxy, this
pipeline) — it's a dedicated automation box, not something being conserved
for battery. Checked current state before recommending: `pmset -g` shows
`SleepDisabled: 0`, and the current `sleep 0` line is only held up by
transient app assertions (Claude, caffeinate, etc. running right now) — not
a durable setting. That's real diagnostic evidence, not a guess, that
machine sleep is a live risk and needs your manual fix.

## Task 3 — SVG clipping fix

Commit `e4abd93`. Root cause: `top = u90 - 16` left ~5px between the "HIGH
REACHED" label's text baseline and the viewBox edge, not enough for a 10px
font's ascent (~8px) — glyph tops clipped. **This is a viewBox-coordinate
bug, not a phone-width-specific one** — the SVG scales uniformly
(`width:100%; height:auto`, aspect ratio locked by viewBox), so it clipped
identically at every rendered width; a phone screen just made it visible
first. Widened the margin to 24. Verified numerically (not visually — no
browser available): "HIGH REACHED" baseline now sits at y=13.1 within the
288-unit-tall viewBox, leaving ~5px of clearance above the glyph tops after
accounting for ascent. Since the fix is in viewBox-space, that clearance
holds at 400px, 800px, or any width — I did not screenshot it at 400px
specifically, and want to be upfront that "checked at 400px" means "did the
math that makes width irrelevant," not "looked at a phone-sized render."
If you want an actual visual confirmation, that's the one thing here I'd
suggest you glance at yourself.

## State of the tree

All 6 commits pushed: `7dcc5aa`(prior)…`7dc1366`, `dd988ad`, `55e55c2`,
`e4abd93`, plus two `chore: daily page` auto-publishes from the pipeline
itself firing during testing (`0467440`, `f8a2773`, `3bbc81d` — these are
real, not test artifacts; the live page actually advanced through 09-17,
09-18, and 09-21 while I worked). STATE.md updated with a factual summary,
not a milestone re-audit or re-close.

## Pushback

- You asked for "no analysis, no model retraining" — noted and respected,
  but flagging that `data/calibration.csv` now has enough rows (5, growing
  by 1/day) that in a few weeks it'll be tempting to eyeball whether the
  published probabilities are tracking realized outcomes. That's a fine
  thing to DO by hand later; just naming that the temptation will exist so
  it doesn't sneak in as an unplanned addition to some future task.
- The Mac Mini sleep issue is the actual root cause of "silently broken for
  two days," and it's the one piece of tonight's work I can't finish for
  you — it needs your password. Everything else is done; this one is on you.
