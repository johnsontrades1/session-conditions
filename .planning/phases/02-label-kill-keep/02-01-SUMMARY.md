# Phase 2 / Plan 01 — Summary

**Completed:** 2026-09-14

## What was done

- `backtest_qqq.py` — full label re-score on 6,901 QQQ RTH days (1999→2026) + ±20%
  robustness sweeps on 6 knobs
- Verdicts: 5 KEEP (HIGH_VOL, EXPANDED, COILED, BIG_GAP, EVENT), 1 RENAME
  (TREND → STRETCHED — inversion replicated on clean data), NEUTRAL bucket unchanged
- Page copy rewritten where it contradicted evidence (TREND/COILED/EXPANDED/BIG_GAP)
- Evidence report: QQQ-BACKTEST.md

## Key findings

- Gap-fill baseline 91% (NQ Globex) → 67% (QQQ RTH): contamination thesis confirmed
- BIG_GAP strongest effect in study: 25% same-day fill vs 67% base, n=271, stable
- Zero knife-edge thresholds; all effects monotone in sensible directions

## Verification

- pytest 12/12; today.py renders; no stray TREND references

## Deferred

- NQ-specific re-validation via fetch_databento.py — optional, needs funded pull (~$2-10)
