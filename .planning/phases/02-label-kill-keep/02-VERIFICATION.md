---
status: passed
verified: 2026-09-14
score: 4/4 must-haves verified
---

# Phase 2 Verification — Label Kill/Keep

- [x] LABEL-01: every label re-scored on RTH data with CI + stability (QQQ-BACKTEST.md)
- [x] LABEL-02: TREND inversion resolved — replicated on clean data, renamed STRETCHED,
      copy fixed, rule untouched (no knob-fitting)
- [x] LABEL-03: BIG_GAP kept — strongest evidence in study
- [x] LABEL-04: sweeps documented, zero sign flips, knobs ≤2 per label
- [x] today.py renders with new labels; pytest 12/12

Note: RTH source is QQQ (real 9:30 opens) rather than NQ futures — Databento credits
exhausted. Regime-level conclusions replicated across both datasets; NQ re-validation
optional and unblocked by fetch_databento.py whenever funded.
