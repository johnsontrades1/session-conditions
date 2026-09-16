---
quick_id: 260915-v0k
status: complete
---

# Quick Task 260915-v0k — Summary

## What was done

`today.py`: the Range Envelope's "Size of day" and "Big-range odds" read lines
now reuse the exact same `sig` flags the base-rate table uses
(`out_range_atr_sig`, `out_big_range_sig` from `br`), plus a new 5%-relative
materiality floor on top (`MATERIALITY_FLOOR = 0.05`, computed on raw fractions,
not display-rounded percentages). A line only quantifies a difference when both
conditions hold; otherwise it renders "No different from a normal session." in
the table's muted/null-result style. When neither line clears the bar, both
collapse into one sentence: "Nothing about today's setup separates it from a
typical session." The materiality floor is disclosed in the section's own
subtitle so it's visible on the page, not just in code comments.

Direction row and the conditional BIG_GAP callout are unchanged, per instruction.

## Verification (three cases, all rendered and inspected)

- **NEUTRAL (2026-09-15, prod):** size non-material (rel 0.9%) → muted; big-range
  material (raw rel 9.6%, not the 6.7% the rounded display would suggest) → shown.
  Materiality-floor sentence present in the subtitle.
- **STRETCHED (2026-07-30, reconstructed):** size sig=True but rel=3.1% < floor,
  big-range sig=False → both non-material → collapsed to the single sentence.
  This is the exact "CI passes, floor catches it" case the task described.
- **COILED+BIG_GAP (2026-09-14, reconstructed):** both material (rel 15.4%,
  50.7%) → both lines render quantified and unchanged from before this fix.
  Confirms the fix doesn't over-mute real findings.

pytest 11/11 green. Prod render restored to 2026-09-15/NEUTRAL after each
reconstructed-day test.

## Deviation

Found and fixed a precision bug while implementing: the big-range relative-diff
check was initially computed off the already-rounded display percentages
(14 vs 15 → 6.7%) instead of the raw fractions (13.77% vs 15.24% → 9.6%). Didn't
change any verdict in this dataset (both clear the 5% floor either way) but
would misclassify a genuinely borderline case. Fixed to use raw floats before
committing.

## Not touched

Pre-existing ordinal-suffix bug in the gap-percentile line ("91th percentile")
noticed during testing — unrelated to this task, left alone.
