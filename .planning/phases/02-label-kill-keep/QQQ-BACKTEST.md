# Phase 2 Kill/Keep — QQQ RTH Backtest Report

**Run:** 2026-09-14 | **Sample:** 6,901 days, 1999-04-08 → 2026-09-14
**Data:** QQQ daily via yfinance — opens are true 9:30 ET Nasdaq opens (real overnight gaps)
**Replication target:** day-1 NQ=F backtest (6,541 days, Globex opens)

## Headline: Globex contamination confirmed

Baseline same-day gap-fill rate: **91.1% on NQ Globex opens → 67.4% on QQQ RTH opens**.
The day-1 suspicion was right — Globex "gaps" are overnight drift, not gaps.

## Verdicts

| Label | Verdict | Evidence |
|-------|---------|----------|
| HIGH_VOL | **KEEP** | Sig on range (1.026), eff, trend_day, big_range, small_range. Stability +0.041/+0.154 same sign. Effect strengthens monotonically as vix_hi rises (sweep). |
| EXPANDED | **KEEP (upgraded)** | Strongest range effect (+0.172/+0.157 both halves, most stable label). Now sig on eff + trend_day too. Expansion persists — deviation grows monotonically with threshold (sweep 0.96→1.44: +0.051→+0.249). |
| COILED | **KEEP** | Compression persists: small_range 48.1% vs 31.9% base, big_range 7.6% vs 15.2%, all sig. Stability -0.114/-0.172. Monotone in sweep (tighter compress → stronger effect). "Coiled spring" folklore dead on both datasets. |
| BIG_GAP | **KEEP (new confidence)** | n 40→271. Real gaps DON'T fill: 25.1% vs 67.4% base, sig, stability -0.459/-0.385 — biggest effect in the whole study. Range 1.074 sig. Monotone in gap_big sweep (+0.092→+0.172). |
| EVENT | **KEEP** | Weaker on QQQ than NQ but sig on range, small_range, gap_filled; stability +0.046/+0.081 consistent. NQ day-1 showed the same direction stronger. |
| TREND | **RENAME → STRETCHED** | Inversion REPLICATES on clean data: range 0.903 (sig low), eff 0.454 (sig low), trend_day 0.323 (sig low), small_range 0.373 (sig high). Stability consistent (range -0.010/-0.046, eff -0.009/-0.026). ≥3 ATR 20d move + clean tape → next day QUIETER. Extension exhausts. Rule unchanged; name + page copy now match behavior. |
| NEUTRAL | keep (bucket) | Tracks baseline as designed. |

## Robustness sweeps (LABEL-04)

±20% neighborhoods, 3–5 points per knob, metric = out_range_atr deviation from baseline:

- **Every label keeps its sign at every point of every sweep.** Zero knife-edges.
- Monotone in the economically sensible direction: compress↓ → COILED stronger;
  expand↑ → EXPANDED stronger; gap_big↑ → BIG_GAP stronger; vix_hi↑ → HIGH_VOL stronger.
- trend_atr / er sweeps barely move STRETCHED (-0.021…-0.039) — inversion is not
  threshold-dependent.

## Knob audit (LABEL-04)

| Label | Knobs | Count |
|-------|-------|-------|
| STRETCHED | trend_atr, er | 2 ✓ |
| HIGH_VOL | vix_stress, vix_hi | 2 ✓ |
| COILED | compress | 1 ✓ |
| EXPANDED | expand | 1 ✓ |
| BIG_GAP | gap_big | 1 ✓ |
| EVENT | none (calendar) | 0 ✓ |

## Page copy corrections applied

Three DESCR strings contradicted the evidence and were rewritten:
- TREND→STRETCHED: "skew toward continuation" → runs quieter, extension exhausts
- COILED: "range expansion tends to follow" → compression persists
- EXPANDED: "mean reversion in range size is the base case" → expansion persists
- BIG_GAP: neutral copy → gaps don't fill same-day (25% vs 67%)

## Caveats

- QQQ ≠ NQ: cash ETF vs futures; levels/ATR differ, but regime-level effects replicated
  across both datasets and 27 years. NQ-specific re-validation optional via
  fetch_databento.py when user funds a pull (~$2-10 estimated, cost-guarded).
- EVENT label strength differs NQ vs QQQ — futures react to macro harder. Keep watching.

## Requirement mapping

- LABEL-01 ✓ full re-score with CI + stability on RTH data (this report)
- LABEL-02 ✓ TREND inversion resolved — renamed STRETCHED, copy fixed, rule untouched
- LABEL-03 ✓ BIG_GAP kept with strong evidence
- LABEL-04 ✓ sweeps + knob audit above
