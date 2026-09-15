---
name: premarket
description: Build the pre-market brief for option buying on BANKNIFTY / CRUDEOIL / SILVER / SILVERM. It covers levels, ATR regime, v4.0 strategy state, ATM premium/IV/theta, straddle, OI walls and PCR (with data-quality gates), plus the trader's own risk reminders. Every number in the brief is machine-checked against the facts. Use for /premarket, "pre-market brief", "morning analysis".
---

# /premarket [YYYY-MM-DD] [--only CRUDEOIL,BANKNIFTY]

1. **Facts (deterministic).** From the repo root:
   ```bash
   python -m trading_agents.facts.premarket --date <date> [--only ...]
   ```
   If it fails with a Dhan auth error, tell the user `DHAN_ACCESS_TOKEN` in `.env` has probably
   expired, and stop. For fresh risk reminders, run `/journal` first if today's or yesterday's
   journal facts are missing. This is optional; the brief notes when they're absent.

2. **Brief.** Spawn the `premarket-analyst` subagent. Give it the facts path
   (`journal_data/facts/<date>_premarket.json`) and the output path
   (`journal_data/reports/<date>_premarket.md`).

3. **Check.** Run:
   ```bash
   python -m trading_agents.validate.claims_check journal_data/reports/<date>_premarket.md journal_data/facts/<date>_premarket.json --kind premarket --stamp
   ```
   This appends a `## Validation` section to the report.

4. **One fix pass on FAIL.** Send the error list back to the same analyst (SendMessage to its
   agent id) and ask it to correct only those items. Then re-run step 3. If it still fails, leave
   the FAIL stamp in place. Never hand-edit the analyst's numbers yourself.

5. **Supervise.** Spawn the `supervisor-validator` subagent with the report path, the facts path and
   kind `premarket`. It re-runs the deterministic checks, judges the reasoning (bias vs evidence,
   invented signals, unusable chains quoted, buried violations) and stamps a `## Supervisor` verdict.
   On FAIL, do one analyst fix pass as in step 4, then re-run the supervisor once.

6. **Report back** in at most 6 lines:
   - report path
   - claims_check + supervisor verdicts
   - one line per instrument: bias + key fact

Everything under `journal_data/` is gitignored real account data. Never `git add` it.
