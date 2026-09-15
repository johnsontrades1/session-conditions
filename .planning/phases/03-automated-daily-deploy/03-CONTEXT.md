# Phase 3: Automated Daily Deploy - Context

**Gathered:** 2026-09-14
**Status:** Ready for planning
**Note:** Executed before Phase 2 (Phase 1 live + Phase 2 blocked on DATABENTO_API_KEY; deploy is unblocked).

<domain>
## Phase Boundary

Mac Mini renders and publishes the page before the open every weekday, zero manual
steps, failures impossible to miss. DEPLOY-01..03. No label logic, no data-source changes.

</domain>

<decisions>
## Implementation Decisions

### Deploy mechanics (accepted 2026-09-14)
- Run time: 7:40 AM CT (8:40 ET) weekdays via LaunchAgent — page ready ~50 min pre-open
- Publish: rename `site/` → `docs/`, GitHub Pages serves `main`/`docs`; no Actions, no extra branch
- Failure visibility: run log + page's data date (stale date = obvious failure)
- Bot auto-commits `docs/` only ("chore: daily page YYYY-MM-DD"); code never auto-pushed
- fetch_databento.py runs best-effort in the daily script — missing key logs a line and
  continues on yfinance fallback (exit 1 tolerated, cost-guard abort logged loudly)

### Claude's Discretion
- Script/log layout, plist details, Pages API enablement via gh CLI if authed

</decisions>

<code_context>
## Existing Code Insights

- `today.py` — SITE path constant at line 19 (`Path(__file__).parent / "site"`); single rename point
- Existing LaunchAgent patterns on this machine: com.johnsontrades.kalshi-scalper, com.johnsontrades.polymarket-proxy
- Repo pushed to github.com/johnsontrades1/session-conditions (main tracking set)

</code_context>

<specifics>
## Specific Ideas

- Page must show its data date prominently (DEPLOY-03)

</specifics>

<deferred>
## Deferred Ideas

- macOS notification on failure — extra; revisit if silent failures actually bite

</deferred>
