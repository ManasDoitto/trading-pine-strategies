"""Answers Telegram bot commands around the clock - started by telegram-daemon.service, which has
no trading-hours gate, unlike trading-watcher.service.

Exists because every bot command used to only work inside trade_watch's run_loop, which only runs
08:51-23:59 IST on weekdays (see trading-watcher.service). /vmhealth needs to answer at 3am on a
Sunday too, so this is a second, much lighter loop whose only job is telegram_bot.poll_and_handle().
telegram_bot's own file lock keeps it from double-handling a command on top of trading-watcher
during the hours both are running.

    python -m trading_exec.telegram_daemon
"""
import time

from .health import fresh_client, token_from_env_file
from .notify import notify
from .telegram_bot import poll_and_handle

POLL_SECONDS = 30


def run_loop(sleep=None, max_ticks=None):
    sleep = sleep or time.sleep
    client, token = None, None
    notify("[telegram daemon started]", ["answering bot commands around the clock",
                                          f"polling every {POLL_SECONDS}s"], "info")
    down = False
    while True:
        try:
            fresh = token_from_env_file()
            if client is None or fresh != token:
                client, token = fresh_client(), fresh
            handled = poll_and_handle(client)
            if handled:
                print(f"{time.strftime('%H:%M:%S')} bot command(s): {handled}")
            if down:
                notify("[telegram daemon recovered]", [], "info")
                down = False
        except Exception as e:
            if not down:
                notify("[telegram daemon error] bot commands may not be answered",
                       [f"{type(e).__name__}: {e}", "It retries every poll."], "error")
                down = True
            print(f"{time.strftime('%H:%M:%S')} error: {type(e).__name__}: {e}")
        if max_ticks is not None:
            max_ticks -= 1
            if max_ticks <= 0:
                return 0
        sleep(POLL_SECONDS)


def main():
    try:
        return run_loop()
    except KeyboardInterrupt:
        print("stopped.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
