---
name: journal
description: Build the option-buying trade journal for a day. It pulls Dhan fills read-only, computes FIFO P&L, flags rule violations (averaging down, overnight/expiry holds, premium stop, daily loss, revenge, deep OTM, sell-to-open), draws charts from Dhan bars, and writes the markdown journal. Use for /journal, "update my journal", "journal today", or as the first step of a session-close run.
---

# /journal [YYYY-MM-DD] [NSE|MCX|ALL]

Arguments are optional. Date defaults to today; session defaults to ALL (it only controls which underlyings get charted when you didn't trade).

1. **Build the facts and charts (deterministic, no LLM numbers).** From the repo root run:
   ```bash
   python -m trading_agents.facts.journal --date <date> --session <session>
   ```
   Useful flags:
   - `--no-pull` reuses stored fills (e.g. when re-running a past date).
   - `--offline` makes no Dhan calls at all, so no charts or live positions.

   If it fails with a Dhan auth error, tell the user their `DHAN_ACCESS_TOKEN` in `.env` has
   probably expired, and stop. Don't retry in a loop.

2. **Write the journal.** Spawn the `trade-journal-keeper` subagent with a prompt that gives it
   the facts path printed in step 1 (`journal_data/facts/<date>_journal.json`) and the date.
   It writes `journal_data/journal/<date>.md`.

3. **Supervise (optional but preferred).** Spawn the `supervisor-validator` subagent with the journal
   path (`journal_data/journal/<date>.md`), the facts path and kind `journal`. It checks that the
   journal's numbers match the facts and that violations aren't buried, then stamps a `## Supervisor`
   verdict. On FAIL, ask `trade-journal-keeper` to fix only those items once, then re-run it.

4. **Report back** in at most 5 lines:
   - journal path
   - today's realised net ₹
   - number of positions
   - violations by rule (call out any R1/R3/R8 explicitly)
   - anything still open at close

Everything under `journal_data/` is gitignored real account data. Never `git add` it.
