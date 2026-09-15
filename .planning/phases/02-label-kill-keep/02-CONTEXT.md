# Phase 2: Label Kill/Keep on Clean Data - Context

**Gathered:** 2026-09-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Re-score every regime label on true RTH opens; resolve TREND inversion; BIG_GAP verdict;
knob audit + robustness sweeps. LABEL-01..04.

</domain>

<decisions>
## Implementation Decisions

### Data source pivot (user, 2026-09-14)
- Databento credits exhausted, March files expired/deleted. **QQQ via yfinance is the
  RTH source for Phase 2** — QQQ daily opens are true 9:30 ET Nasdaq opens, 1999→now.
- NQ Databento pull remains optional future work (fetch_databento.py ready, cost-guarded);
  re-validation on NQ deferred, not blocking.

### Analysis rules
- Sweeps are robustness checks (±20% threshold neighborhoods, sign/significance must hold),
  never optimization. Honesty rules from CLAUDE.md govern all verdicts.
- TREND: if inversion replicates on QQQ RTH → re-specify as fade-type label (rename +
  page description), don't contort the rule to force trend-following behavior.
- BIG_GAP: real verdict now possible — QQQ gaps are genuine overnight gaps.

### Claude's Discretion
- Script layout for the backtest report, label naming, page copy.

</decisions>

<code_context>
## Existing Code Insights

- regime.py: P dict 7 thresholds; per-label knob count already ≤2 (TREND: trend_atr+er;
  HIGH_VOL: vix_stress+vix_hi; COILED/EXPANDED/BIG_GAP: 1 each). LABEL-04 = document + sweep.
- label() priority: stress > trending > coiled > expanded, EVENT overrides all,
  BIG_GAP only claims NEUTRAL days.
- load_prices("qqq_daily.csv") explicit name — RTH preference logic won't intercept.
- data/qqq_daily.csv: 6,921 rows 1999-03-10 → 2026-09-14 already on disk.

</code_context>

<specifics>
## Specific Ideas

- Day-1 NQ findings to test for replication: TREND inversion, COILED persistence,
  HIGH_VOL strength, EVENT stability, BIG_GAP gap-fill rate (expect ≪91% on real gaps).

</specifics>

<deferred>
## Deferred Ideas

- NQ Databento re-validation once user decides to spend on ohlcv-1m pull.

</deferred>
