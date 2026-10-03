#!/opt/trading/repo/.venv/bin/python
"""Read a Dhan JWT from stdin, validate it parses and isn't already expired, atomically rewrite only
the DHAN_ACCESS_TOKEN= line in .env. Run as: ssh trading-vm set-token  (paste the token, then Ctrl-D).
Never takes the token as an argv (that leaks into `ps` and shell history)."""
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, "/opt/trading/repo")
from trading_exec.health import token_expiry

ENV = Path("/opt/trading/repo/.env")


def main():
    token = sys.stdin.readline().strip()
    if not token:
        print("no token read from stdin", file=sys.stderr)
        return 1
    exp = token_expiry(token)
    if exp is None:
        print("doesn't parse as a JWT - not written", file=sys.stderr)
        return 1
    if exp <= datetime.now():
        print(f"already expired ({exp:%d-%b %H:%M}) - not written", file=sys.stderr)
        return 1
    lines = ENV.read_text(encoding="utf-8").splitlines()
    out, found = [], False
    for line in lines:
        if line.startswith("DHAN_ACCESS_TOKEN="):
            out.append(f"DHAN_ACCESS_TOKEN={token}")
            found = True
        else:
            out.append(line)
    if not found:
        out.append(f"DHAN_ACCESS_TOKEN={token}")
    tmp = ENV.with_suffix(".tmp")
    tmp.write_text("\n".join(out) + "\n", encoding="utf-8")
    os.chmod(tmp, 0o600)
    os.replace(tmp, ENV)
    print(f"token updated, expires {exp:%d-%b %H:%M} (the running loops pick it up within one tick, no restart needed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
