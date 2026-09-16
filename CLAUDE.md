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

- yfinance NQ daily `open` = Globex open, not 9:30 ET RTH — the live page renders
  from `qqq_daily.csv` instead (QQQ's open is the true RTH open). Never use
  `nq_daily.csv` for gap stats.
- FOMC/CPI calendars in `events.py` need periodic refresh — `tests/test_events.py`
  fails once either runs under 60 days from its end.

## Failure mode to avoid

Long agentic sessions drift toward adding features/labels until something "works."
That is the exact failure this project is built to prevent. When in doubt: fewer
labels, fewer knobs, report the null result.

<!-- GSD:project-start source:PROJECT.md -->
## Project

**Session Conditions**

Pre-open "what kind of day is today?" read for NQ day traders. Labels each session
(TREND / COILED / EXPANDED / HIGH_VOL / EVENT / BIG_GAP / NEUTRAL) from strictly
pre-open features and shows backtested base rates — historical frequencies with
bootstrap CIs, never forecasts. Built by and for Paytin's own NQ/MNQ prop trading.

**Core Value:** Every number on the page is an honest, statistically defensible base rate — a label
only shows if its CI excludes the unconditional mean and it survives the stability check.

### Constraints

- **Honesty rules** (see CLAUDE.md): CI must exclude baseline; stability flip kills a label;
  max 2 knobs per label; feature/outcome separation is inviolable; no forecasts.
- **Tech stack**: Python + pandas, static HTML output — no server, no framework.
- **Budget**: free-tier data only (yfinance, CBOE public CSV); GitHub Pages free tier.
- **Schedule**: daily pipeline must complete before ~9:15 ET so the page is ready pre-open.
<!-- GSD:project-end -->

<!-- GSD:stack-start source:STACK.md -->
## Technology Stack

Technology stack not yet documented. Will populate after codebase mapping or first phase.
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
