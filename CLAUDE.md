# Session Conditions — honesty rules (non-negotiable)

This project exists to report **historical base rates**, not forecasts. Every change
must preserve these constraints. If a change makes a label "work" by violating one,
the label is wrong, not the rule.

## Hard rules

1. **CI must exclude the baseline.** A label's outcome stat is only reportable if its
   bootstrap 95% CI excludes the unconditional (ALL) mean. Never surface a
   non-significant row as if it means something; the page dims them for a reason.

2. **Stability check kills labels.** `stability()` splits the sample into halves.
   If a label's deviation from baseline flips sign between halves, the label dies.
   Do not rationalize a sign flip. Do not shrink the sample window until it passes.

3. **Max 2 knobs per label.** Thresholds live in `regime.P` and are deliberately few.
   Sweeping them is fine; if a label needs more than 2 tuned thresholds to become
   significant, it is overfit — delete it instead of tuning it.

4. **Pre-open features and same-day outcomes stay strictly separated.**
   `features.py` computes features from prior-day info + today's open only.
   Never let a same-day outcome leak into a feature. This is the whole ballgame.

5. **No forecasts.** Output is "days that looked like this did X% of the time,"
   with n and CI. Never phrase as prediction.

## Known data caveats

- yfinance NQ daily `open` = Globex open, not 9:30 ET RTH. Gap features are noisy
  until swapped to ProjectX/Databento RTH bars. Cross-check gap stats on QQQ.
- CPI dates 2025+ unverified against bls.gov/schedule.

## Failure mode to avoid

Long agentic sessions drift toward adding features/labels until something "works."
That is the exact failure this project is built to prevent. When in doubt: fewer
labels, fewer knobs, report the null result.
