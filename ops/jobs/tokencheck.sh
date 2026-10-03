#!/bin/bash
cd /opt/trading/repo
export PYTHONPATH=/opt/trading/repo
.venv/bin/python - <<'PY'
from datetime import datetime, time
from trading_exec import health
from trading_exec.notify import notify
expiry = health.token_expiry(health.token_from_env_file())
status = health.token_status(expiry, datetime.now(), time(23, 30))
if status != "ok":
    exp_txt = expiry.strftime("%d-%b %H:%M") if expiry else "unknown"
    notify(f"[token check] status: {status}", [
        f"expiry: {exp_txt}",
        "fix: ssh trading-vm set-token, paste the new JWT, Ctrl-D",
    ], "warning")
else:
    print(f"token ok, expires {expiry:%d-%b %H:%M}")
PY
