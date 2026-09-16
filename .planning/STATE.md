---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: Honest RTH Pipeline
status: complete
last_updated: "2026-09-14"
progress:
  total_phases: 3
  completed_phases: 3
  total_plans: 3
  completed_plans: 3
  percent: 100
---

# STATE.md — Session Conditions Project Memory

## Project Reference

See: .planning/PROJECT.md (updated 2026-09-14)

**Core value:** Every number on the page is an honest, statistically defensible base rate.
**Current focus:** v1.0 complete + post-milestone integrity fixes applied. Next: v2 (event calendar backfill, Event Playbook, optional NQ pull).

## Phase Progress

- Phase 1 (RTH Data Pipeline): ✅ Complete — Databento code ready + tested; DATA-01 (NQ backfill) descoped to v2; QQQ RTH is the active validated source
- Phase 2 (Label Kill/Keep on Clean Data): ✅ Complete, one verdict corrected post-milestone (see below)
- Phase 3 (Automated Daily Deploy): ✅ Complete — LaunchAgent weekdays 7:40 CT, GitHub Pages live

## Post-milestone corrections (2026-09-14, same day)

User-directed integrity pass, all committed individually:

1. **pre_fomc bug fixed** (events.py) — every future FOMC meeting flagged the dataset's
   last row; 2026-09-14 was mislabeled EVENT. Now requires ≤4 days AND weekend-only gap.
   5 regression tests.
2. **Page now renders from QQQ RTH** (the Phase 2 validated source) — it had been
   publishing NQ Globex numbers (91.4% gap fill) under QQQ-derived copy (~25%).
   Data source now printed on page + in today.json; can't silently desync again.
3. **EVENT verdict REVERSED to UNPROVEN** — event calendar is definition-drifted
   (no events pre-2010, NFP-only 2010-2014, +FOMC 2015, +CPI 2022); the full-sample
   stability check compared different label definitions. EVENT stats now restricted
   to 2022+ (n=169, direction suggestive, one macro regime) with UNPROVEN warning on page.
4. **BIG_GAP claim corrected** — band decomposition shows fill-rate decline is mostly
   fill-distance arithmetic (actual ≈ mechanical null per band; big gaps fill slightly
   MORE than distance implies). "Gaps DON'T fill" rewritten. COILED/EXPANDED reframed
   as vol clustering, not discovery.

## Label verdicts (current)

| Label | Verdict |
|---|---|
| STRETCHED (né TREND) | KEEP — inversion replicated; runs quieter |
| HIGH_VOL | KEEP |
| EXPANDED | KEEP — vol clustering, most stable label |
| COILED | KEEP — vol clustering, low-vol side |
| BIG_GAP | KEEP — low fill odds mostly mechanical; copy says so |
| EVENT | **UNPROVEN** — 2022+ only, small n, one regime |

## Last Action

2026-09-14 — Post-milestone integrity fixes complete (5 commits): pre_fomc bug,
QQQ source switch + page source stamp, EVENT→UNPROVEN, BIG_GAP/COILED/EXPANDED
claim corrections, STATE sync. Page relabeled 2026-09-14 EVENT→COILED.

## Key Context

- Live page: https://johnsontrades1.github.io/session-conditions/ — LaunchAgent
  `com.johnsontrades.session-conditions` weekdays 7:40 AM CT; log logs/daily.log;
  stale page date = failed run
- Data: QQQ RTH (yfinance) validated source; NQ Globex kept as cross-check only;
  fetch_databento.py ready when funded (~$2-10, $20 cost guard)
- Honesty rules in CLAUDE.md are hard constraints; if a fix kills a label, report
  the null — never tune it back

## Blockers/Concerns

- First unattended LaunchAgent fire: next weekday 7:40 AM CT — verify page date + log
- v2 candidates: FOMC/CPI calendar backfill (federalreserve.gov, bls.gov) to make
  EVENT provable; Event Playbook; NQ Databento pull

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 260915-v0k | range-envelope significance gating | 2026-09-16 | 075391b | [260915-v0k-range-envelope-significance-gating](./quick/260915-v0k-range-envelope-significance-gating/) |

Last activity: 2026-09-16 - Completed quick task 260915-v0k: range-envelope significance gating
