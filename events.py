"""
Scheduled-event calendar. Every date here is a *known* scheduled event, never
a prediction. FOMC and CPI are hardcoded from the Fed / BLS schedules; NFP and
opex are rule-generated (first Friday / third Friday) with holiday adjustments.

To extend or correct: edit data/events_override.csv (date,event) — it wins.
"""
import pandas as pd
from pathlib import Path

DATA = Path(__file__).parent / "data"

# FOMC decision days (second day of the meeting). Includes 2020 emergency cuts.
FOMC = """
2015-01-28 2015-03-18 2015-04-29 2015-06-17 2015-07-29 2015-09-17 2015-10-28 2015-12-16
2016-01-27 2016-03-16 2016-04-27 2016-06-15 2016-07-27 2016-09-21 2016-11-02 2016-12-14
2017-02-01 2017-03-15 2017-05-03 2017-06-14 2017-07-26 2017-09-20 2017-11-01 2017-12-13
2018-01-31 2018-03-21 2018-05-02 2018-06-13 2018-08-01 2018-09-26 2018-11-08 2018-12-19
2019-01-30 2019-03-20 2019-05-01 2019-06-19 2019-07-31 2019-09-18 2019-10-30 2019-12-11
2020-01-29 2020-03-03 2020-04-29 2020-06-10 2020-07-29 2020-09-16 2020-11-05 2020-12-16
2021-01-27 2021-03-17 2021-04-28 2021-06-16 2021-07-28 2021-09-22 2021-11-03 2021-12-15
2022-01-26 2022-03-16 2022-05-04 2022-06-15 2022-07-27 2022-09-21 2022-11-02 2022-12-14
2023-02-01 2023-03-22 2023-05-03 2023-06-14 2023-07-26 2023-09-20 2023-11-01 2023-12-13
2024-01-31 2024-03-20 2024-05-01 2024-06-12 2024-07-31 2024-09-18 2024-11-07 2024-12-18
2025-01-29 2025-03-19 2025-05-07 2025-06-18 2025-07-30 2025-09-17 2025-10-29 2025-12-10
2026-01-28 2026-03-18 2026-04-29 2026-06-17 2026-07-29 2026-09-16 2026-10-28 2026-12-09
""".split()

# CPI release days (BLS, 8:30 ET). 2022-2024 verified from BLS schedule;
# 2025+ should be re-checked against bls.gov/schedule before trusting stats.
CPI = """
2022-01-12 2022-02-10 2022-03-10 2022-04-12 2022-05-11 2022-06-10 2022-07-13 2022-08-10 2022-09-13 2022-10-13 2022-11-10 2022-12-13
2023-01-12 2023-02-14 2023-03-14 2023-04-12 2023-05-10 2023-06-13 2023-07-12 2023-08-10 2023-09-13 2023-10-12 2023-11-14 2023-12-12
2024-01-11 2024-02-13 2024-03-12 2024-04-10 2024-05-15 2024-06-12 2024-07-11 2024-08-14 2024-09-11 2024-10-10 2024-11-13 2024-12-11
2025-01-15 2025-02-12 2025-03-12 2025-04-10 2025-05-13 2025-06-11 2025-07-15 2025-08-12 2025-09-11
""".split()

US_HOLIDAYS_FIRST_FRIDAY_SHIFT = {  # NFP moved when first Friday is a holiday
    "2015-07-03": "2015-07-02", "2020-07-03": "2020-07-02", "2026-07-03": "2026-07-02",
    "2021-01-01": "2021-01-08", "2016-01-01": "2016-01-08",
}


def _nth_weekday(year, month, weekday, n):
    d = pd.Timestamp(year=year, month=month, day=1)
    off = (weekday - d.weekday()) % 7
    return d + pd.Timedelta(days=off + 7 * (n - 1))


def build_calendar(start="2010-01-01", end="2027-12-31") -> pd.DataFrame:
    rows = []
    for d in FOMC:
        rows.append((pd.Timestamp(d), "FOMC"))
    for d in CPI:
        rows.append((pd.Timestamp(d), "CPI"))
    for y in range(int(start[:4]), int(end[:4]) + 1):
        for m in range(1, 13):
            nfp = _nth_weekday(y, m, 4, 1)
            nfp = pd.Timestamp(US_HOLIDAYS_FIRST_FRIDAY_SHIFT.get(str(nfp.date()), nfp))
            rows.append((nfp, "NFP"))
            opx = _nth_weekday(y, m, 4, 3)
            rows.append((opx, "OPEX"))
            if m in (3, 6, 9, 12):
                rows.append((opx, "QUAD_WITCH"))
    cal = pd.DataFrame(rows, columns=["date", "event"])
    ov = DATA / "events_override.csv"
    if ov.exists():
        extra = pd.read_csv(ov, parse_dates=["date"])
        cal = pd.concat([cal, extra], ignore_index=True)
    cal = cal.drop_duplicates().sort_values("date")
    return cal[(cal.date >= start) & (cal.date <= end)].reset_index(drop=True)


def event_flags(index: pd.DatetimeIndex) -> pd.DataFrame:
    """One boolean column per event type plus a combined 'event_day' and a
    'pre_fomc' flag (day before an FOMC decision)."""
    cal = build_calendar()
    out = pd.DataFrame(index=index)
    for ev in sorted(cal.event.unique()):
        out[f"ev_{ev.lower()}"] = index.isin(cal.loc[cal.event == ev, "date"])
    major = ["ev_fomc", "ev_cpi", "ev_nfp"]
    out["event_day"] = out[[c for c in major if c in out]].any(axis=1)
    fomc_dates = pd.DatetimeIndex(cal.loc[cal.event == "FOMC", "date"])
    # trading day immediately before FOMC decision
    prev = {d: i for i, d in enumerate(index)}
    pre = set()
    for f in fomc_dates:
        pos = index.searchsorted(f)
        if 0 < pos <= len(index) and pos - 1 >= 0 and (pos == len(index) or index[pos] == f):
            pre.add(index[pos - 1])
    out["pre_fomc"] = index.isin(list(pre))
    return out


if __name__ == "__main__":
    c = build_calendar("2026-01-01", "2026-12-31")
    print(c.to_string())
