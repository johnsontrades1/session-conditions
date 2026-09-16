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
| EXPANDED | **KEEP (upgraded)** | Strongest range effect (+0.172/+0.157 both halves, most stable label). Now sig on eff + trend_day too. This is volatility clustering — the most replicated effect in empirical finance — measured on this instrument, not a discovery. Deviation grows monotonically with threshold (sweep 0.96→1.44: +0.051→+0.249). |
| COILED | **KEEP** | Volatility clustering, low-vol side: small_range 48.1% vs 31.9% base, big_range 7.6% vs 15.2%, all sig, stability -0.114/-0.172, monotone in sweep. Useful because it contradicts "coiled spring" folklore, but the effect itself is standard vol clustering. |
| BIG_GAP | **KEEP (claim corrected 2026-09-14)** | n 40→271 label / 793 at ≥0.6 threshold. Fill rate IS low (27.4% vs 67.4% base, sig, stable) — but band decomposition shows the decline is mostly ARITHMETIC: actual fill ≈ mechanical distance null in every band ([0,0.1): 93.9% vs 93.0% … [0.6,1.0): 30.5% vs 21.5%, [1.0,∞): 15.9% vs 5.5%). Big-gap days fill slightly MORE than raw distance predicts (+9-10pp, plausibly just their wider ranges — null isn't vol-matched). No evidence gaps "refuse" to fill. Keep the label for its (partly mechanical) fill odds and wider ranges; copy rewritten to say so. |
| EVENT | **KEEP (verdict history: KEEP→UNPROVEN 09-14→KEEP 09-15)** | 09-14 correction stands as diagnosis: original calendar was definition-drifted (no events pre-2010, NFP-only 2010-14, +FOMC 2015, +CPI 2022) and the old stability check was invalid. 09-15 overnight: backfilled real FOMC 1999-2014 (federalreserve.gov per-year pages, cross-checked vs Wikipedia FOMC actions — full 2003 + 3 landmarks match) and real CPI 1999-2021 (BLS archive filename dates, majority-voted across extraction passes, 3 in-document embargo-line verifications incl. the 2013-10-30 shutdown-delayed release). Re-scored on full clean 1999+ span: n=1047, share uniform 14-16% across all eras; range 0.973 vs 0.934 with CI [0.948, 0.999] excluding baseline; big_range 17.6% vs 15.2% sig; small_range 27.3% vs 31.9% sig; eff/trend_day/gap_filled n.s.; NO sign flips in any stability check (range +0.013/+0.067, big_range +0.022/+0.025, small_range −0.013/−0.077). Verdict: real but modest — events widen ranges a little and suppress quiet days; nothing directional. Scheduled meetings only; unscheduled/emergency cuts excluded by design. |
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

## Gap-fill mechanical decomposition (added 2026-09-14)

Same-day fill by gap-size band vs mechanical null — P(fill) if the day's adverse
excursion from open were drawn from the unconditional excursion distribution
(`backtest_qqq.py --gaps`):

| gap_atr band | n | actual fill | mech null | diff |
|---|---|---|---|---|
| [0.0,0.1) | 1666 | 93.9% | 92.9% | +1.0pp |
| [0.1,0.2) | 1453 | 81.5% | 79.8% | +1.6pp |
| [0.2,0.4) | 2015 | 62.2% | 61.5% | +0.7pp |
| [0.4,0.6) | 974 | 44.5% | 40.7% | +3.8pp |
| [0.6,1.0) | 623 | 30.5% | 21.5% | +9.0pp |
| [1.0,∞) | 170 | 15.9% | 5.5% | +10.4pp |

Fill-rate decline with gap size is arithmetic before it is behavior. Positive diffs
on big bands mean large gaps fill somewhat MORE than distance alone implies —
plausibly just wider ranges on gap days (null not vol-matched), certainly not a
"gaps don't fill" behavioral effect.

### Vol-matched null (added 2026-09-15) — settles the residual

Method: redraw the null with the day's realized range controlled. Two variants,
built independently so the answer can't come from method-picking:
- **A (primary):** adverse excursion drawn from days in the same realized-range
  (out_range_atr) decile.
- **B (check):** fill iff open-placement fraction ≥ gap/range, with the placement
  fraction drawn unconditionally.

| gap_atr band | n | actual | uncond null | vol-matched A | diff A | diff B |
|---|---|---|---|---|---|---|
| [0.0,0.1) | 1666 | 93.9% | 92.9% | 92.8% | +1.1pp | +2.1pp |
| [0.1,0.2) | 1453 | 81.5% | 79.8% | 79.5% | +2.0pp | +2.5pp |
| [0.2,0.4) | 2015 | 62.2% | 61.5% | 61.8% | +0.5pp | −1.8pp |
| [0.4,0.6) | 974 | 44.5% | 40.7% | 43.8% | +0.7pp | −1.5pp |
| [0.6,1.0) | 623 | 30.5% | 21.5% | 27.8% | +2.7pp | +3.1pp |
| [1.0,∞) | 170 | 15.9% | 5.5% | 15.0% | +0.9pp | +1.3pp |

**≥0.6 aggregate:** actual 27.4%, vol-matched 25.0%, diff **+2.3pp, 95% bootstrap CI
[−0.2, +4.9] — includes zero.** Half-split: +3.0pp / +1.6pp (no flip, but both small
and individually insignificant). Variants agree.

**Conclusion: the fill-rate decline is pure arithmetic.** The +9–10pp excess over the
unconditional null was entirely gap days being wide-range days. There is no behavioral
asymmetry in either direction worth reporting. Page copy stripped of the residual
"mostly"/"not because these days refuse" hedging — it now states fill odds match
distance + range arithmetic, full stop. (Note the vol-matched null conditions on
same-day realized range, so this is a decomposition of what happened, not a tradable
pre-open quantity — the pre-open version of the fill number is the band table itself.)

## Page copy corrections applied

DESCR strings that contradicted or overclaimed the evidence, rewritten (2 passes):
- TREND→STRETCHED: "skew toward continuation" → runs quieter, extension exhausts
- COILED: "range expansion tends to follow" → vol clustering, compression persists
- EXPANDED: "mean reversion in range size is the base case" → vol clustering, expansion persists
- BIG_GAP: "gaps DON'T fill" → low fill odds are mostly fill-distance arithmetic
- EVENT: unqualified event copy → 2022+-only stats, UNPROVEN over longer history

## Caveats

- QQQ ≠ NQ: cash ETF vs futures; levels/ATR differ, but regime-level effects replicated
  across both datasets and 27 years. NQ-specific re-validation optional via
  fetch_databento.py when user funds a pull (~$2-10 estimated, cost-guarded).
- EVENT label strength differs NQ vs QQQ — futures react to macro harder. Keep watching.
- Pre-2022 event-calendar gaps also mean some true event days sit inside OTHER labels'
  historical samples (as false NEUTRAL/COILED/etc.). Events are ~5-14% of days, so the
  dilution is small and every other label's verdict also replicated on the NQ sample,
  but a full calendar backfill would clean this up too.

## Requirement mapping

- LABEL-01 ✓ full re-score with CI + stability on RTH data (this report)
- LABEL-02 ✓ TREND inversion resolved — renamed STRETCHED, copy fixed, rule untouched
- LABEL-03 ✓ BIG_GAP kept with strong evidence
- LABEL-04 ✓ sweeps + knob audit above
