# Phase 1: RTH Data Pipeline - Context

**Gathered:** 2026-09-14
**Status:** Ready for planning
**Mode:** Smart discuss — infrastructure phase, minimal context

<domain>
## Phase Boundary

Gap and open features come from true 9:30 ET RTH opens (Databento GLBX.MDP3),
killing the Globex-open contamination, with a credit-efficient daily incremental pull.
Covers DATA-01..04. No label logic changes (Phase 2), no automation/scheduling (Phase 3).

</domain>

<decisions>
## Implementation Decisions

### From user (autonomous session)
- Data source: Databento (free $125 credit) — decided at project init
- **Build first, key later**: full pipeline written and unit-testable without a live
  Databento key. Live backfill + spot-check verification deferred until user provides
  `DATABENTO_API_KEY`. Code must fail with a clear message when key absent.
- Key handling: env var only (`DATABENTO_API_KEY`), never committed, `.env` in .gitignore.

### Claude's Discretion
All remaining implementation choices at Claude's discretion — pure infrastructure phase.
Notable defaults chosen:
- Symbology: NQ continuous front month (`NQ.c.0`, calendar roll) via GLBX.MDP3 parent symbology; document roll choice in code.
- RTH definition: 09:30–16:00 ET (CME equity index RTH), computed by aggregating 1-minute bars (`ohlcv-1m`) — GLBX daily bars are full-session and useless for RTH opens.
- Cost guard: estimate request cost via Databento metadata API before any pull; hard-abort if projected backfill cost exceeds $20 of credit.
- Incremental state: last-date check on `data/nq_rth_daily.csv` itself, no separate state file.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `fetch_data.py` — yfinance pull (NQ/QQQ/VIX/VIX3M/VVIX + 60d 5-min NQ); keep as-is for VIX complex + fallback
- `features.py` — 15 pre-open features; gap features currently read `open` column of `data/nq_daily.csv`
- venv at project root with pandas/numpy/yfinance

### Established Patterns
- Plain CSVs in `data/` with lowercase column names, `date` index
- Scripts are flat, no package structure, run from project root
- Honesty rules in CLAUDE.md are hard constraints

### Integration Points
- New `fetch_databento.py` writes `data/nq_rth_daily.csv` (+ optional `nq_rth_intraday.csv`)
- `features.py` prefers RTH open when `data/nq_rth_daily.csv` present, falls back to yfinance `nq_daily.csv`

</code_context>

<specifics>
## Specific Ideas

- Spot-check requirement (success criterion 1): compare a handful of RTH opens vs known
  9:30 ET prints once live data lands.

</specifics>

<deferred>
## Deferred Ideas

- Event Playbook intraday distributions (v2) — will reuse the same Databento intraday path later.

</deferred>
