---
name: session-close
description: Run the end-of-session review for option buying: update the journal from Dhan fills, build session facts (OHLC vs this morning's levels, v4.0 signals, ATM premium paths, your trades), grade this morning's pre-market call on the scorecard, write the review and machine-check it. Use for /session-close, "session close", "end of day review", "how did today go".
---

# /session-close [NSE|MCX|ALL] [YYYY-MM-DD]

Session defaults to ALL; date defaults to today. Use `NSE` after 15:30 IST (BANKNIFTY) and `MCX`
after 23:30 IST (CRUDEOIL, SILVER, SILVERM).

1. **Journal first** (so the review sees today's fills). Run the `/journal` skill's step 1:
   ```bash
   python -m trading_agents.facts.journal --date <date> --session <session>
   ```
   Then spawn `trade-journal-keeper` for the journal markdown as that skill describes. If the Dhan
   token has expired, say so and stop.

2. **Session facts.**
   ```bash
   python -m trading_agents.facts.session_close --date <date> --session <session>
   ```

3. **Scorecard.** Grades this morning's bias against the session and merges itself into the facts:
   ```bash
   python -m trading_agents.validate.scorecard --date <date>
   ```
   It's fine if there was no pre-market report; the scorecard records that as a note.

4. **Review.** Spawn the `session-close-analyst` subagent with the facts path
   (`journal_data/facts/<date>_session_close.json`) and the output path
   (`journal_data/reports/<date>_session_close.md`).

5. **Check.**
   ```bash
   python -m trading_agents.validate.claims_check journal_data/reports/<date>_session_close.md journal_data/facts/<date>_session_close.json --kind session_close --stamp
   ```
   On FAIL, send the errors back to the same analyst once (SendMessage to its agent id), ask it to fix
   only those items, and re-run. Never edit its numbers yourself.

6. **Supervise.** Spawn the `supervisor-validator` subagent with the review path, the facts path and
   kind `session_close`. It judges the reasoning (invented signals, unusable chains quoted, buried
   violations, scorecard honesty) and stamps a `## Supervisor` verdict. On FAIL, do one analyst fix
   pass as in step 5, then re-run the supervisor once.

7. **Report back** in at most 6 lines: review path, claims_check + supervisor verdicts, per-instrument
   one-liner, whether this morning's call was right, and anything of yours still open.

Everything under `journal_data/` is gitignored real account data. Never `git add` it.
