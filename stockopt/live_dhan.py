"""The ONE place in this codebase allowed to construct a WRITE-enabled Dhan client.

Everywhere else (scan_live.py, capital_sync.py, position_calc.py, ...) uses
trading_agents.core.dhan_client.get_dhan_client(), which wraps the raw SDK in
ReadOnlyDhan -- order placement, modification and cancellation are unreachable through it
BY CONSTRUCTION, deliberately. This module is the one narrow, intentional exception: it
builds a raw dhanhq client with full access, used ONLY by stockopt/auto_order.py to place
and cancel the live orders a "Taking it" button tap authorizes. Every call still goes
through the same cross-process wait_for_slot() rate limiter as the read-only path (its own
"live_order" category), so it can't collide with the other live strategies sharing this
Dhan account.

IPv4 forced before the first live order call -- found 2026-10-01: Dhan's order-placement
API enforces IP whitelisting, but this machine has IPv6 connectivity and the OS prefers it
by default ("happy eyeballs"), so plain `requests` calls were reaching Dhan over IPv6 while
the user had whitelisted their IPv4 address -- every real order attempt was rejected
(DH-905 "Invalid IP") even after correctly whitelisting IPv4 and regenerating the token,
because the actual outbound connection was never using that address. The fix patches
urllib3's address-family selection, which is process-wide once applied (not scoped to this
module alone) -- harmless, since nothing else in this codebase depends on IPv6 and IPv4 has
worked for every other Dhan/Telegram call all session; it's just applied lazily, only when
a live order is actually about to be placed, rather than unconditionally at import time.
"""
from __future__ import annotations

import os
import socket

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_client = None
_ipv4_forced = False


def _force_ipv4():
    global _ipv4_forced
    if _ipv4_forced:
        return
    import urllib3.util.connection as urllib3_cn
    urllib3_cn.allowed_gai_family = lambda: socket.AF_INET
    _ipv4_forced = True


def get_live_client():
    global _client
    if _client is not None:
        return _client
    _force_ipv4()
    from dotenv import load_dotenv
    from dhanhq import DhanContext, dhanhq
    load_dotenv(os.path.join(ROOT, ".env"))
    client_id = os.getenv("DHAN_CLIENT_ID")
    access_token = os.getenv("DHAN_ACCESS_TOKEN")
    if not client_id or not access_token:
        raise RuntimeError("DHAN_CLIENT_ID / DHAN_ACCESS_TOKEN not set in .env")
    _client = dhanhq(DhanContext(client_id, access_token))
    return _client


def cancel_order(order_id):
    from trading_agents.core.dhan_client import wait_for_slot
    wait_for_slot("live_order")
    return get_live_client().cancel_order(order_id)
