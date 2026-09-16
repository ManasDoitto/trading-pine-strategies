"""Option-chain snapshot for an option BUYER: ATM premium/IV/greeks, straddle, theta cost,
OI walls, PCR, and hard data-quality gates.

Two Dhan traps seen on 2026-09-16 pre-market:
- The chain's underlying `last_price` can be stale: crude showed 9,706 vs a 10,215 futures close.
  Dhan's IV/greeks are computed off that stale price (CE IV ~140%, PE IV 0). When it disagrees with
  the futures close, ATM is re-centred on the close and IV/greeks come from Black-76 on the leg LTPs.
- Silver ATM strikes can be quoted but untradeable (OI in single digits, bid-ask spread >100%), so a
  wide spread is a hard gate.
"""
from datetime import datetime, time

from . import black76, instruments

HARD_FLAGS = ("missing", "no open interest", "no traded volume", "IV outside sane range", "stale last price",
              "wide bid-ask spread")


def _f(x):
    try:
        return None if x is None else float(x)
    except (TypeError, ValueError):
        return None


def parse_leg(raw):
    if not raw:
        return None
    g = raw.get("greeks") or {}
    bid, ask = _f(raw.get("top_bid_price")), _f(raw.get("top_ask_price"))
    mid = (bid + ask) / 2 if bid and ask else None
    return dict(
        ltp=_f(raw.get("last_price")), iv=_f(raw.get("implied_volatility")),
        delta=_f(g.get("delta")), theta=_f(g.get("theta")), gamma=_f(g.get("gamma")), vega=_f(g.get("vega")),
        oi=_f(raw.get("oi")), prev_oi=_f(raw.get("previous_oi")),
        volume=_f(raw.get("volume")), prev_volume=_f(raw.get("previous_volume")),
        prev_close=_f(raw.get("previous_close_price")), bid=bid, ask=ask,
        spread_pct=(ask - bid) / mid * 100 if mid else None,
        security_id=raw.get("security_id"),
    )


def leg_quality(leg, pcfg):
    """Returns a list of flags; any flag in HARD_FLAGS makes the leg unusable."""
    if leg is None:
        return ["missing"]
    flags = []
    if (leg["oi"] or 0) < pcfg["min_atm_oi"]:
        flags.append("no open interest")
    if max(leg["volume"] or 0, leg["prev_volume"] or 0) < pcfg["min_atm_volume"]:
        flags.append("no traded volume")
    lo, hi = pcfg["iv_sane_range"]
    if leg["iv"] is None or not lo <= leg["iv"] <= hi:
        flags.append("IV outside sane range")
    if not (leg["volume"] or 0) and leg["ltp"] is not None and leg["ltp"] == leg["prev_close"]:
        flags.append("stale last price")
    if leg["spread_pct"] is not None and leg["spread_pct"] > pcfg["max_spread_pct"]:
        flags.append("wide bid-ask spread")
    if str(leg.get("iv_source", "")).startswith("black76"):
        flags.append("Dhan IV/greeks replaced by Black-76")
    return flags


def _price_leg(leg, F, K, T, right, stale_under, pcfg):
    """Pick the IV/greeks to trust: Dhan's when sane and consistent, else Black-76 on the LTP."""
    r = pcfg["risk_free_rate"]
    lo, hi = pcfg["iv_sane_range"]
    model = black76.implied_vol(leg["ltp"], F, K, T, r, right)
    leg["b76_iv"] = model * 100 if model else None
    leg["dhan_iv"] = leg["iv"]
    dhan_ok = (not stale_under and leg["iv"] is not None and lo <= leg["iv"] <= hi
               and (leg["b76_iv"] is None or abs(leg["b76_iv"] - leg["iv"]) <= pcfg["max_iv_model_gap"]))
    if dhan_ok:
        leg["iv_source"] = "dhan"
    elif model:
        g = black76.greeks(F, K, T, model, r, right)
        leg.update(iv=model * 100, delta=g["delta"], theta=g["theta"], gamma=g["gamma"], vega=g["vega"],
                   iv_source="black76 (Dhan greeks inconsistent)" if not stale_under
                   else "black76 (chain underlying stale)")
    else:
        leg["iv_source"] = "dhan (unverified)"


def years_to_expiry(expiry, session_end, as_of_dt):
    hh, mm = (int(x) for x in session_end.split(":"))
    secs = (datetime.combine(expiry, time(hh, mm)) - as_of_dt).total_seconds()
    return max(secs, 3600) / (365 * 86400)


def summarize_chain(inner, underlying, expiry, as_of_dt, pcfg, ref_close=None):
    """Pure function over Dhan's option_chain payload (data.data) -> facts dict."""
    cfg = instruments.instrument_cfg(underlying)
    chain_price = _f(inner.get("last_price"))
    oc = inner.get("oc") or {}
    strikes = sorted(float(k) for k in oc)
    if not (chain_price or ref_close) or not strikes:
        return dict(expiry=expiry, usable=False, flags=["empty option chain"])
    gap_pct = abs(chain_price / ref_close - 1) * 100 if chain_price and ref_close else None
    stale_under = gap_pct is not None and gap_pct > pcfg["max_underlying_gap_pct"]
    F = ref_close if (stale_under or not chain_price) else chain_price
    by_strike = {float(k): v for k, v in oc.items()}
    atm = min(strikes, key=lambda k: abs(k - F))
    T = years_to_expiry(expiry, cfg["session"][1], as_of_dt)

    legs = {}
    for right, key in (("CE", "ce"), ("PE", "pe")):
        leg = parse_leg(by_strike[atm].get(key))
        if leg and leg["ltp"]:
            _price_leg(leg, F, atm, T, right, stale_under, pcfg)
            leg["theta_pct_of_premium"] = abs(leg["theta"]) / leg["ltp"] * 100 if leg["theta"] is not None else None
            leg["move_to_cover_1d_theta_pts"] = (abs(leg["theta"]) / abs(leg["delta"])
                                                 if leg["theta"] is not None and leg["delta"] else None)
            leg["breakeven_at_expiry"] = atm + leg["ltp"] if right == "CE" else atm - leg["ltp"]
        if leg is not None:
            leg["flags"] = leg_quality(leg, pcfg)
        legs[right] = leg

    flags = sorted({f for leg in legs.values() for f in (leg["flags"] if leg else ["missing"])})
    if stale_under:
        flags.append("chain underlying price stale vs futures close; ATM and IV/greeks recomputed from the close")
    usable = not any(f in HARD_FLAGS for f in flags)

    idx = strikes.index(atm)
    n = pcfg["oi_strikes_each_side"]
    window = strikes[max(0, idx - n): idx + n + 1]
    ce = {k: parse_leg(by_strike[k].get("ce")) for k in window}
    pe = {k: parse_leg(by_strike[k].get("pe")) for k in window}
    ce_oi = {k: (v["oi"] or 0) for k, v in ce.items() if v}
    pe_oi = {k: (v["oi"] or 0) for k, v in pe.items() if v}
    ce_add = {k: (v["oi"] or 0) - (v["prev_oi"] or 0) for k, v in ce.items() if v}
    pe_add = {k: (v["oi"] or 0) - (v["prev_oi"] or 0) for k, v in pe.items() if v}

    def top_liquid(side):
        rows = [(k, v) for k, v in side.items() if v and max(v["volume"] or 0, v["prev_volume"] or 0) > 0]
        rows.sort(key=lambda kv: -max(kv[1]["volume"] or 0, kv[1]["prev_volume"] or 0))
        return [dict(strike=k, ltp=v["ltp"], volume=max(v["volume"] or 0, v["prev_volume"] or 0), oi=v["oi"])
                for k, v in rows[:3]]

    ce_leg, pe_leg = legs["CE"], legs["PE"]
    straddle = ce_leg["ltp"] + pe_leg["ltp"] if ce_leg and pe_leg and ce_leg["ltp"] and pe_leg["ltp"] else None
    ivs = [l["iv"] for l in (ce_leg, pe_leg) if l and l["iv"] and "IV outside sane range" not in l["flags"]]
    total_ce, total_pe = sum(ce_oi.values()), sum(pe_oi.values())
    return dict(
        expiry=expiry,
        dte=(expiry - as_of_dt.date()).days,
        underlying_price=F,
        underlying_price_source="futures close" if F == ref_close else "option chain",
        chain_underlying_price=chain_price,
        underlying_gap_vs_futures_pct=gap_pct,
        strike_step=(strikes[idx + 1] - strikes[idx]) if idx + 1 < len(strikes) else None,
        atm_strike=atm,
        atm=dict(ce=ce_leg, pe=pe_leg),
        atm_iv=sum(ivs) / len(ivs) if ivs else None,
        straddle=straddle,
        straddle_pct_of_underlying=straddle / F * 100 if straddle else None,
        oi_window_strikes=[window[0], window[-1]],
        max_ce_oi_strike=max(ce_oi, key=ce_oi.get) if total_ce else None,
        max_pe_oi_strike=max(pe_oi, key=pe_oi.get) if total_pe else None,
        max_ce_oi_add_strike=max(ce_add, key=ce_add.get) if ce_add and max(ce_add.values()) > 0 else None,
        max_pe_oi_add_strike=max(pe_add, key=pe_add.get) if pe_add and max(pe_add.values()) > 0 else None,
        pcr_oi=total_pe / total_ce if total_ce else None,
        most_liquid_ce=top_liquid(ce),
        most_liquid_pe=top_liquid(pe),
        usable=usable,
        flags=flags,
    )


def chain_snapshot(client, underlying, expiry, as_of_dt, pcfg, ref_close=None):
    cfg = instruments.instrument_cfg(underlying)
    ref = instruments.reference_series(underlying, expiry)
    if ref is None:
        return dict(expiry=expiry, usable=False, flags=["no underlying contract to query the chain"])
    r = client.option_chain(under_security_id=int(ref["security_id"]), under_exchange_segment=cfg["chain_segment"],
                            expiry=f"{expiry:%Y-%m-%d}")
    data = (r.get("data") or {}) if isinstance(r, dict) else {}
    inner = data.get("data", data) if isinstance(data, dict) else {}
    if not isinstance(inner, dict) or not inner.get("oc"):
        return dict(expiry=expiry, usable=False, flags=[f"option chain unavailable: {str(r)[:120]}"])
    return summarize_chain(inner, underlying, expiry, as_of_dt, pcfg, ref_close)
