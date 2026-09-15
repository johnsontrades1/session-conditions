# ROADMAP.md — Session Conditions v1.0

## Milestone: v1.0 — Honest RTH Pipeline

**Goal:** Daily pre-open page driven by true RTH data, with every label re-validated
on clean opens and the whole pipeline running unattended on the Mac Mini.

## Phases

### Phase 1 — RTH Data Pipeline

**Goal:** Gap and open features come from true 9:30 ET RTH opens (Databento GLBX.MDP3),
killing the Globex-open contamination, with a credit-efficient daily incremental pull.

**Requirements:** DATA-01, DATA-02, DATA-03, DATA-04

**Success criteria:**
1. `data/nq_rth_daily.csv` exists with RTH opens; spot-check vs known 9:30 ET prints passes
2. `features.py` gap features use RTH open when present; yfinance path still works without it
3. Running the daily fetch twice on the same day downloads only the missing session (no full re-pull)
4. VIX complex still refreshes via yfinance in the same run

**Status:** 🟡 Code complete — live backfill awaits API key

### Phase 2 — Label Kill/Keep on Clean Data

**Goal:** Every regime label re-scored on RTH data; TREND inversion resolved, BIG_GAP
gets a verdict, all surviving labels honest (CI excludes baseline, stable, ≤2 knobs).

**Requirements:** LABEL-01, LABEL-02, LABEL-03, LABEL-04

**Success criteria:**
1. Backtest output on RTH data shows per-label CI + stability results committed to repo
2. TREND either renamed/re-specified as fade with significant stable stats, or rule fixed
3. BIG_GAP explicitly kept or killed with documented evidence
4. No label carries more than 2 tuned thresholds in `regime.P`

**Status:** ⬜ Not started

### Phase 3 — Automated Daily Deploy

**Goal:** Mac Mini renders and publishes the page before the open every weekday with
zero manual steps, and failures are impossible to miss.

**Requirements:** DEPLOY-01, DEPLOY-02, DEPLOY-03

**Success criteria:**
1. LaunchAgent fires weekday pre-open; fetch → regime → today completes before 9:15 ET
2. GitHub Pages URL shows today's date after the run
3. A failed run leaves an error in the log and the page's date visibly stale

**Status:** ⬜ Not started

## Success Criteria (Milestone Complete When)

- [ ] All 11 v1 requirements checked off in REQUIREMENTS.md
- [ ] Page publishes automatically with RTH-clean stats for 1 full trading day unattended
- [ ] Every surviving label passes CI + stability on RTH data

---
*Created: 2026-09-14*
