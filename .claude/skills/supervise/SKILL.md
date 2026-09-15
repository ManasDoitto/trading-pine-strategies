---
name: supervise
description: Audit an agent report (pre-market brief, session-close review or trade journal) against its facts before trusting it. Runs claims_check and house_rules, then the supervisor-validator subagent, and stamps a PASS / PASS-WITH-EDITS / FAIL verdict. Use for /supervise, "check that report", "is the brief right".
---

# /supervise [report path | YYYY-MM-DD premarket|session_close|journal]

1. **Resolve the paths.** Report `journal_data/reports/<date>_<kind>.md` (the journal lives at
   `journal_data/journal/<date>.md`) and facts `journal_data/facts/<date>_<kind>.json`. If either is
   missing, say which and stop.

2. **Spawn `supervisor-validator`** with the report path, facts path and kind. It runs the
   deterministic checks itself, judges the reasoning, and stamps a `## Supervisor` section.

3. **On FAIL, one fix pass.** Send the supervisor's errors to the analyst that wrote the report
   (SendMessage to its agent id if it's still in this session, otherwise spawn the matching analyst
   — `premarket-analyst`, `session-close-analyst` or `trade-journal-keeper` — with the errors and the
   same paths). Ask it to correct only those items. Then re-run step 2 once.

4. **If it still fails**, leave the FAIL stamp in place and tell the user plainly which numbers or
   claims are not trustworthy. Never edit the analyst's numbers yourself.

5. **Report back** in at most 5 lines: verdict, error count, the most important issue, and the path.

Everything under `journal_data/` is gitignored real account data. Never `git add` it.
