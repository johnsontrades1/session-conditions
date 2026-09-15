# Requirements: Session Conditions

**Defined:** 2026-09-14
**Core Value:** Every number on the page is an honest, statistically defensible base rate.

## v1 Requirements

Requirements for v1.0 — Honest RTH Pipeline. Each maps to roadmap phases.

### Data (RTH via Databento)

- [ ] **DATA-01**: One-time backfill of NQ RTH daily bars (true 9:30 ET opens) from Databento GLBX.MDP3, saved to `data/nq_rth_daily.csv`
- [ ] **DATA-02**: `features.py` gap/open features computed from RTH open when RTH data present, with yfinance fallback preserved
- [ ] **DATA-03**: Daily incremental Databento pull appends latest session without re-downloading history (credit-efficient)
- [ ] **DATA-04**: VIX/VIX3M/VVIX daily refresh continues via yfinance alongside Databento equities data

### Labels (kill/keep on clean data)

- [ ] **LABEL-01**: Full regime backtest re-run on RTH data; every label re-scored with bootstrap CI + half-split stability
- [ ] **LABEL-02**: TREND label inversion resolved — either re-specified as explicit fade label or rule fixed, backed by RTH backtest
- [ ] **LABEL-03**: BIG_GAP verdict on RTH gaps — keep if CI excludes baseline and stable, kill otherwise
- [ ] **LABEL-04**: Threshold sweeps documented, each label ≤2 tuned knobs (honesty rule enforced)

### Deploy (automated daily page)

- [ ] **DEPLOY-01**: LaunchAgent runs fetch → regime → today pipeline on weekday pre-open schedule (done before 9:15 ET)
- [ ] **DEPLOY-02**: `site/` published to GitHub Pages automatically after each successful run
- [ ] **DEPLOY-03**: Failed or stale runs are visible — log file + date check on page (stale date = obvious)

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Event Playbook

- **EVENT-01**: Intraday move distributions around CPI/FOMC/NFP from multi-year intraday data
- **EVENT-02**: Event Playbook tab on the daily page

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Forecasting / ML prediction | Project reports base rates only — predictions violate core value |
| Intraday live page updates | Pre-open read is the product; one render per day |
| ProjectX data integration | Databento chosen; revisit only if credit runs out |
| Alerting (push/SMS) | Page is pull-based; alerts are a different product |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| DATA-01 | Phase 1 | Pending |
| DATA-02 | Phase 1 | Pending |
| DATA-03 | Phase 1 | Pending |
| DATA-04 | Phase 1 | Pending |
| LABEL-01 | Phase 2 | Pending |
| LABEL-02 | Phase 2 | Pending |
| LABEL-03 | Phase 2 | Pending |
| LABEL-04 | Phase 2 | Pending |
| DEPLOY-01 | Phase 3 | Pending |
| DEPLOY-02 | Phase 3 | Pending |
| DEPLOY-03 | Phase 3 | Pending |

**Coverage:**
- v1 requirements: 11 total
- Mapped to phases: 11
- Unmapped: 0 ✓

---
*Requirements defined: 2026-09-14*
*Last updated: 2026-09-14 after initial definition*
