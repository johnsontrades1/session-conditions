# Session Conditions

## What This Is

Pre-open "what kind of day is today?" read for NQ day traders. Labels each session
(TREND / COILED / EXPANDED / HIGH_VOL / EVENT / BIG_GAP / NEUTRAL) from strictly
pre-open features and shows backtested base rates — historical frequencies with
bootstrap CIs, never forecasts. Built by and for Paytin's own NQ/MNQ prop trading.

## Core Value

Every number on the page is an honest, statistically defensible base rate — a label
only shows if its CI excludes the unconditional mean and it survives the stability check.

## Requirements

### Validated

- ✓ 15 pre-open features strictly separated from same-day outcomes (`features.py`) — day 1
- ✓ 7-label regime classifier with bootstrap CIs, quintile tables, half-split stability test (`regime.py`) — day 1
- ✓ Event calendar: FOMC/CPI hardcoded, NFP/opex/quad-witching rule-generated, override CSV (`events.py`) — day 1
- ✓ Daily page renderer (`today.py` → `site/`) — day 1
- ✓ Data pull via yfinance: NQ 2000→, QQQ 1999→, VIX 1990→, VIX3M/VVIX 2007→, 60d 5-min NQ — day 1
- ✓ First real backtest run (6,541 days): all labels stable-direction, HIGH_VOL strongest, TREND inverted, BIG_GAP suspect — 2026-09-14

### Active

- [ ] RTH data via Databento (GLBX.MDP3) — true 9:30 ET opens, kill Globex-open gap contamination
- [ ] Label kill/keep pass on RTH data — resolve TREND inversion, validate/kill BIG_GAP, sweeps within 2-knob limit
- [ ] Automated daily deploy — LaunchAgent pre-open run + GitHub Pages publish

### Out of Scope

- Event Playbook (intraday distributions around CPI/FOMC/NFP) — v2; needs multi-year intraday history first
- Forecasting / ML prediction — project exists to report base rates, not predictions
- Polymarket/Kalshi integration — separate projects
- Intraday live updates — page is a pre-open read, one render per day is the product

## Context

- Day 1 built in a claude.ai cloud session (GitHub-only sandbox); this Mac Mini is the
  data-capable environment. Full pipeline already ran here on real data 2026-09-14.
- Backtest findings driving v1: TREND label is significantly *anti*-trend (fade signal),
  COILED compression persists (no coiled-spring), BIG_GAP n=40 with 91% baseline gap-fill
  rate screaming Globex-open contamination, HIGH_VOL and EVENT are the cleanest labels.
- User trades NQ/MNQ on prop accounts (TopstepX/Apex), NY 7-10am ET primary kill zone.
- Databento chosen for RTH bars: free $125 credit, CME GLBX.MDP3.
- venv at project root has yfinance/pandas/numpy.

## Constraints

- **Honesty rules** (see CLAUDE.md): CI must exclude baseline; stability flip kills a label;
  max 2 knobs per label; feature/outcome separation is inviolable; no forecasts.
- **Tech stack**: Python + pandas, static HTML output — no server, no framework.
- **Budget**: Databento free credit only; GitHub Pages free tier.
- **Schedule**: daily pipeline must complete before ~9:15 ET so the page is ready pre-open.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Databento over ProjectX for RTH data | Free credit, proven CME history depth, stable API | — Pending |
| Local LaunchAgent + GitHub Pages deploy | Automation on Mac Mini, phone-viewable URL, zero cost | — Pending |
| Event Playbook deferred to v2 | Needs multi-year intraday data not yet acquired | — Pending |
| Roadmap/planning inline, no research agents | 6-file codebase fully known; agent spawns waste tokens | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-09-14 after initialization*
