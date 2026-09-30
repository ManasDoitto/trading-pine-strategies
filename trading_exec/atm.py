"""Resolve the ATM option a signal would actually buy, at real prices.

Reuses the tested pieces in trading_agents: expiry/strike/contract/lot resolution and the
option-chain quality gates. Those gates are what stop us "buying" the big SILVER ATM, which had
OI 8 and a 168% spread on 2026-09-16, when the liquid silver chain is SILVERM.
"""
from trading_agents.core import instruments, options
from trading_agents.core.config import load_config as agents_config

from .config import instrument_cfg


def resolve(client, instrument, right, as_of_dt, underlying_price=None, force_nearest=False):
    """right: 'CE' for a long signal, 'PE' for a short.

    force_nearest=True takes the nearest listed expiry even when it sits below the DTE floor, for
    OBSERVATIONAL shadow records: it answers "what would that trade have done" without ever being
    tradeable. Note the floor usually does not BLOCK - it silently selects a further expiry, which
    near expiry can be the illiquid one. `nearest_below_floor` says when that is happening.

    Returns a dict; `usable` says whether a buyer could sensibly take it, `reasons` says why not.
    """
    icfg = instrument_cfg(instrument)
    out = dict(instrument=instrument, right=right, usable=False, reasons=[])
    day = as_of_dt.date()

    expiries = instruments.option_expiries(instrument, day)
    if not expiries:
        out["reasons"].append("no listed option expiries")
        return out
    nearest = expiries[0]
    nearest_dte = (nearest - day).days
    out.update(nearest_expiry=nearest, nearest_dte=nearest_dte,
               nearest_below_floor=nearest_dte < icfg["min_dte"])
    expiry = nearest if force_nearest else next((e for e in expiries if (e - day).days >= icfg["min_dte"]), None)
    if expiry is None:
        out["reasons"].append(f"nearest expiry is {nearest_dte}d out, floor is {icfg['min_dte']}d")
        return out

    if underlying_price is None:
        underlying_price = underlying_ltp(client, instrument, expiry)
    chain = options.chain_snapshot(client, instrument, expiry, as_of_dt,
                                   agents_config()["premarket"], underlying_price)
    leg = (chain.get("atm") or {}).get(right.lower()) or {}
    lot = instruments.lot_size(instrument)
    contract = (instruments.option_contract(instrument, expiry, chain["atm_strike"], right)
                if chain.get("atm_strike") else None)

    ask, bid, ltp = leg.get("ask"), leg.get("bid"), leg.get("ltp")
    entry_premium = ask or ltp                      # a buyer pays the ask
    out.update(
        expiry=expiry, dte=chain.get("dte"), strike=chain.get("atm_strike"),
        underlying_price=chain.get("underlying_price"),
        underlying_price_source=chain.get("underlying_price_source"),
        symbol=contract["label"] if contract else None,
        security_id=contract["security_id"] if contract else None,
        segment=contract["segment"] if contract else None,
        instrument_type=contract["instrument"] if contract else None,
        lots=icfg["lots"], lot_size=lot, qty_units=(icfg["lots"] * lot) if lot else None,
        bid=bid, ask=ask, ltp=ltp, entry_premium=entry_premium,
        spread_pct=leg.get("spread_pct"), iv=leg.get("iv"), iv_source=leg.get("iv_source"),
        delta=leg.get("delta"), theta=leg.get("theta"),
        theta_pct_of_premium=leg.get("theta_pct_of_premium"),
        chain_usable=chain.get("usable"), chain_flags=chain.get("flags", []),
    )

    if not chain.get("usable"):
        out["reasons"].append("chain not usable: " + (", ".join(chain.get("flags", [])) or "unknown"))
    if not contract:
        out["reasons"].append("ATM contract not found in the scrip master")
    if not entry_premium:
        out["reasons"].append("no ask or LTP for the ATM leg")
    spread = leg.get("spread_pct")
    if spread is not None and spread > icfg["max_spread_pct"]:
        out["reasons"].append(f"spread {spread:.1f}% over the {icfg['max_spread_pct']:g}% cap")
    if not lot:
        out["reasons"].append("lot size unknown")
    out["usable"] = not out["reasons"]
    return out


def underlying_ltp(client, instrument, expiry):
    """Live price of the contract THIS option expiry is written on.

    Never pass the signal's own price here: near rollover (crude Oct options while the chart is on
    the Sep future) or if a future instrument's signal_from ever points at a different contract, it
    is a different contract, and chain_snapshot would re-centre the ATM strike on the wrong level."""
    ref = instruments.reference_series(instrument, expiry)
    if ref is None:
        return None
    try:
        r = client.ticker_data({ref["segment"]: [int(ref["security_id"])]})
        return float(r["data"]["data"][ref["segment"]][str(ref["security_id"])]["last_price"])
    except Exception:
        return None


def premium_targets(atm, signal, ref_rr=None):
    """Translate the strategy's underlying SL/target into approximate premium terms via delta.

    Approximate on purpose, since delta moves. Used for display and for the shadow record, never
    as an exit trigger: shadow exits track the underlying, exactly as the strategy does.

    ref_rr: for a strategy with no fixed target (reversal_exit), an INFORMATIONAL reference multiple
    of risk (e.g. the backtest's avg win / avg risk) to show as a rough glance-at-your-phone target.
    Never used as an exit trigger - only the real target (when there is one) or the reversal itself
    closes the trade. Ignored when the signal already has a real target.
    """
    delta = abs(atm.get("delta") or 0)
    premium = atm.get("entry_premium")
    qty = atm.get("qty_units") or 0
    if not delta or not premium:
        return dict(available=False)
    risk = signal.risk_pts * delta
    has_target = getattr(signal, "target", None) is not None
    reward = signal.risk_pts * signal.rr * delta if has_target else None
    out = dict(
        available=True, delta=round(delta, 4),
        risk_premium_pts=round(risk, 2),
        approx_sl_premium=round(max(premium - risk, 0), 2),
        risk_inr=round(risk * qty, 2),
        cost_inr=round(premium * qty, 2),
    )
    if has_target:
        out.update(reward_premium_pts=round(reward, 2), approx_target_premium=round(premium + reward, 2),
                    reward_inr=round(reward * qty, 2))
    elif ref_rr:
        ref_reward = signal.risk_pts * ref_rr * delta
        out.update(ref_rr=ref_rr, approx_ref_target_premium=round(premium + ref_reward, 2))
    return out
