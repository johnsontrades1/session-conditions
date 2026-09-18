"""
Scoreboard, not a controller. Records what the page predicted pre-open for
each session, and what actually happened once that session closed. Nothing
in this codebase reads this file back into regime.py or features.py — no
threshold moves because of it, nothing retrains on it. If a future change
here starts adjusting the model from this data, that's a violation of the
whole point of a scoreboard — stop and reconsider.

    python record_calibration.py

Two-phase, idempotent:
1. PREDICTIONS: walk every commit that ever touched docs/today.json and
   record each distinct as_of snapshot's published numbers, if not already
   recorded. Source of truth is what was ACTUALLY shown that day, not a
   recomputation with today's code/thresholds (which may have changed since).
2. REALIZATION: for any recorded row whose session has since closed (its
   date now exists in the real historical build()), fill in what actually
   happened.

Writes/appends to data/calibration.csv — small, meant to be committed.
"""
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

from features import build, load_prices, load_vix

ROOT = Path(__file__).parent
CAL_FILE = ROOT / "data" / "calibration.csv"
JSON_PATH = "docs/today.json"

COLUMNS = [
    "date", "label", "modifiers", "n",
    "pred_range_atr", "pred_range_atr_lo", "pred_range_atr_hi", "pred_range_atr_p25", "pred_range_atr_p75",
    "pred_close_up_pct", "pred_close_up_lo", "pred_close_up_hi",
    "pred_big_range_pct", "pred_small_range_pct",
    "real_range_atr", "real_up_exc", "real_dn_exc", "real_close_up",
]


def _git_show(rev: str, path: str) -> str | None:
    try:
        return subprocess.run(
            ["git", "show", f"{rev}:{path}"], cwd=ROOT, capture_output=True, text=True, check=True,
        ).stdout
    except subprocess.CalledProcessError:
        return None


def backfill_predictions(cal: pd.DataFrame) -> pd.DataFrame:
    result = subprocess.run(
        ["git", "log", "--format=%H", "--", JSON_PATH], cwd=ROOT, capture_output=True, text=True,
    )
    revs = [r for r in result.stdout.splitlines() if r]
    known_dates = set(cal["date"].astype(str)) if not cal.empty else set()
    new_rows = []
    for rev in revs:
        raw = _git_show(rev, JSON_PATH)
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        date = payload.get("as_of")
        if not date or date in known_dates:
            continue
        known_dates.add(date)
        br = {r["key"]: r for r in payload.get("base_rates", [])}
        rng = br.get("out_range_atr", {})
        big_range = br.get("out_big_range", {})
        small_range = br.get("out_small_range", {})
        env = payload.get("envelope", {})
        new_rows.append({
            "date": date,
            "label": payload.get("label"),
            "modifiers": ";".join(m["name"] for m in payload.get("modifiers", [])),
            "n": payload.get("n_days_like_this"),
            "pred_range_atr": rng.get("cond"), "pred_range_atr_lo": rng.get("lo"), "pred_range_atr_hi": rng.get("hi"),
            "pred_range_atr_p25": rng.get("p25"), "pred_range_atr_p75": rng.get("p75"),
            "pred_close_up_pct": env.get("close_up_pct"), "pred_close_up_lo": env.get("close_up_lo"), "pred_close_up_hi": env.get("close_up_hi"),
            "pred_big_range_pct": (big_range["cond"] * 100) if big_range.get("cond") is not None else None,
            "pred_small_range_pct": (small_range["cond"] * 100) if small_range.get("cond") is not None else None,
            "real_range_atr": None, "real_up_exc": None, "real_dn_exc": None, "real_close_up": None,
        })
    if not new_rows:
        return cal
    added = pd.DataFrame(new_rows, columns=COLUMNS)
    return pd.concat([cal, added], ignore_index=True) if not cal.empty else added


def fill_realized(cal: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Realized outcomes always come from the real historical build() — the
    same source of truth as the backtest — never from a live/forward row."""
    df = build(load_prices("qqq_daily.csv"), load_vix())
    filled = 0
    for i, row in cal.iterrows():
        if pd.notna(row.get("real_range_atr")):
            continue
        d = pd.Timestamp(row["date"])
        if d not in df.index:
            continue
        cal.at[i, "real_range_atr"] = float(df.loc[d, "out_range_atr"])
        cal.at[i, "real_up_exc"] = float(df.loc[d, "out_up_exc"])
        cal.at[i, "real_dn_exc"] = float(df.loc[d, "out_dn_exc"])
        cal.at[i, "real_close_up"] = int(df.loc[d, "out_close_up"])
        filled += 1
    return cal, filled


def main() -> int:
    cal = pd.read_csv(CAL_FILE) if CAL_FILE.exists() else pd.DataFrame(columns=COLUMNS)
    before = len(cal)
    cal = backfill_predictions(cal)
    added = len(cal) - before
    cal = cal.sort_values("date").reset_index(drop=True)
    cal, filled = fill_realized(cal)
    CAL_FILE.parent.mkdir(parents=True, exist_ok=True)
    cal.to_csv(CAL_FILE, index=False)
    print(f"calibration.csv: {added} new prediction rows, {filled} realized this run, {len(cal)} total")
    return 0


if __name__ == "__main__":
    sys.exit(main())
