---
status: human_needed
verified: 2026-09-14
score: 3/4 must-have truths machine-verified
---

# Phase 1 Verification — RTH Data Pipeline

## Machine-verified ✓

- [x] RTH aggregation correct (12 pytest cases incl. DST week, 9:30 open exactness, 16:00 exclusion)
- [x] Incremental resume logic — second same-day run makes zero API calls (unit-tested)
- [x] Missing key → clear actionable error, exit 1 (observed)
- [x] features.py source preference + fallback (unit-tested; regime.py fallback reproduces day-1 output)
- [x] DATA-04: VIX complex refresh unchanged via fetch_data.py

## human_verification

1 item — blocked on user-provided `DATABENTO_API_KEY`:

1. **Live backfill + spot-check (DATA-01)**: run `fetch_databento.py` with key,
   confirm `data/nq_rth_daily.csv` opens match known 9:30 ET prints on a few dates,
   confirm second run prints "up to date — no API call".
