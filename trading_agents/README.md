# trading_agents: AI assistants for option buying

Read-only AI agents for a discretionary **option buyer** on BANKNIFTY, CRUDEOIL, SILVER and SILVERM.
They run inside Claude Code: subagents in `.claude/agents/` and skills in `.claude/skills/`. The numbers
come from deterministic Python in this package. The agents interpret those numbers and never do
arithmetic of their own.

| Agent | Skill | Status |
|---|---|---|
| Trade journal keeper | `/journal` | **Stage 1: built** |
| Pre-market analyst | `/premarket` | Stage 2 |
| Session-close analyst | `/session-close` | Stage 3 |
| Supervisor / validator | wraps all of the above | Stage 4 |

## Safety
- `core/dhan_client.py` exposes an allowlist of read methods only. Order placement, modification,
  cancellation, kill-switch and position conversion are unreachable, and a test enforces it.
- The third-party `dhan-mcp-server/` (which can place orders) is **not** used.
- All output goes to `journal_data/`, which is gitignored because it holds real account data.
- Credentials come from the repo-root `.env` (`DHAN_CLIENT_ID`, `DHAN_ACCESS_TOKEN`), the same as the
  existing scripts. Dhan access tokens expire, so regenerate the token when a run reports an auth failure.

## Layout
```
config.toml        instruments, sessions, rule thresholds (tune these)
core/              dhan_client, instruments (scrip master), market_data, option_symbols,
                   trades (FIFO + position episodes + stats), rules (R1-R8), black76
facts/journal.py   fills -> journal facts JSON + trades.csv + episodes.csv
tests/             unittest, synthetic fixtures only
```

## Journal
```bash
python -m trading_agents.facts.journal                 # today (live, read-only pull)
python -m trading_agents.facts.journal --date 2026-09-09 --no-pull
```
Then `/journal` in Claude Code has the `trade-journal-keeper` subagent write
`journal_data/journal/<date>.md` and take TradingView snapshots in a separate tab.

Rules flagged (thresholds in `config.toml [rules]`):

| Rule | What it catches |
|---|---|
| R1 | Averaging down: re-buying the same option below the running average |
| R2 | A bought option carried overnight |
| R3 | A bought option held into the final days before expiry |
| R4 | Premium stop not respected (exit more than X% below entry) |
| R5 | Daily loss limit breached |
| R6 | Overtrading, or a revenge entry right after a big loss |
| R7 | Deep-OTM lottery buy (per-instrument strike threshold) |
| R8 | Sell-to-open, which isn't option buying |

## Tests
```bash
python -m unittest discover -s trading_agents/tests -t .
```
Dependencies are already installed globally: `dhanhq`, `pandas`, `python-dotenv`, `requests`.
Python 3.13 stdlib covers the rest (`tomllib`, `unittest`).
