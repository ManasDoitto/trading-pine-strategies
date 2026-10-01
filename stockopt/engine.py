"""MA-Stack Pullback Continuation (MSPC) engine -- v3.

Mechanical translation of the 9EMA / 20SMA / 200SMA day-trading method:

  * only trade a stock with a catalyst           -> gap / opening-relative-volume day gate
  * only trade with the trend, never a flat tape -> 20SMA slope band, ATR-normalised
  * entry zone is between the 9EMA and 20SMA     -> pullback must tag 9EMA, hold the 20SMA
  * never buy an over-extended move              -> (close-20SMA)/ATR cap
  * confirm on a higher timeframe                -> 15m stack gate, completed bars only
  * enter on the break of the signal bar         -> stop order, stop under the swing low
  * 200SMA is support/resistance, not a trigger  -> overhead-room gate
  * two setups only                              -> pullback, base breakout

Every threshold is ATR- or percent-normalised, so one parameter set applies to a
Rs.90 stock and a Rs.9000 stock. The strategy is deliberately not tuned per script.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from numba import njit

TICK = 0.05
BARS_PER_DAY = 75  # 09:15 .. 15:25 on a 5m chart

ORVOL_BARS = 6  # opening relative volume measured over the first 30 minutes


# --------------------------------------------------------------------------- #
# indicators
# --------------------------------------------------------------------------- #
def _ema(a, n):
    return pd.Series(a).ewm(span=n, adjust=False).mean().to_numpy()


def _sma(a, n):
    return pd.Series(a).rolling(n).mean().to_numpy()


def _atr(h, l, c, n=14):
    pc = np.roll(c, 1)
    pc[0] = c[0]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    return pd.Series(tr).ewm(alpha=1.0 / n, adjust=False).mean().to_numpy()


INDEX_CSV = __import__("os").path.join(__import__("os").path.dirname(__import__("os").path.dirname(
    __import__("os").path.abspath(__file__))), "research_data", "bars", "DHAN_NIFTY_5m.csv")


def load_index(path: str = INDEX_CSV) -> pd.DataFrame:
    """NIFTY 5m bars (naive IST) with the since-open % return of each bar's close."""
    nf = pd.read_csv(path)
    nf["dt"] = pd.to_datetime(nf["time"], unit="s", utc=True).dt.tz_convert("Asia/Kolkata").dt.tz_localize(None)
    return index_returns(nf)


def index_returns(nf: pd.DataFrame) -> pd.DataFrame:
    nf = nf.sort_values("dt").reset_index(drop=True)
    day = nf["dt"].dt.normalize()
    dopen = nf.groupby(day)["open"].transform("first")
    return pd.DataFrame({"n_ret": (nf["close"] / dopen - 1.0) * 100.0}).set_index(nf["dt"])


def prepare(df: pd.DataFrame, fast=9, mid=20, long=200, atr_n=14, htf="15min", base=None,
            index: pd.DataFrame | None = None, final_day_complete: bool = True) -> dict:
    """final_day_complete: whether the array's LAST row is genuinely the end of that calendar
    day's session (true for any full historical harvest -- default, matches all prior/reported
    backtest behavior exactly) vs a live caller that just truncated mid-session (pass False, or
    the EOD-flatten fires the instant you fetch data, closing anything open at whatever time
    "now" happens to be -- found via run_with_open() 2026-09-30, before it shipped)."""
    """base=None keeps the native 5m bars; base="15min" resamples first (htf should then be 60min)."""
    d = df.sort_values("dt").reset_index(drop=True)
    if base is not None:
        d = (d.set_index("dt").resample(base, label="left", closed="left")
             .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
             .dropna().reset_index())
    bar_min = int(round((d["dt"].diff().dropna().dt.total_seconds().mode().iloc[0]) / 60.0))
    o, h, l, c, v = (d[k].to_numpy(np.float64) for k in ("open", "high", "low", "close", "volume"))

    ema_f = _ema(c, fast)
    sma_m = _sma(c, mid)
    sma_l = _sma(c, long)
    atr = _atr(h, l, c, atr_n)

    s = d.set_index("dt")

    # ---- 15m higher timeframe, completed bars only ----
    agg = s.resample(htf, label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    hf_c = agg["close"].to_numpy(np.float64)
    hf = pd.DataFrame({"hf_close": hf_c, "hf_ema": _ema(hf_c, fast), "hf_sma": _sma(hf_c, mid)},
                      index=agg.index).shift(1)
    mapped = hf.reindex(s.index, method="ffill")

    # ---- daily context, previous session only ----
    dly = s.resample("1D").agg({"open": "first", "high": "max", "low": "min",
                                "close": "last", "volume": "sum"}).dropna()
    d_c = dly["close"].to_numpy(np.float64)
    dctx = pd.DataFrame({
        "d_sma20": _sma(d_c, 20),
        "d_sma200": _sma(d_c, 200),
        "d_close": d_c,
        "d_high": dly["high"].to_numpy(np.float64),
        "d_low": dly["low"].to_numpy(np.float64),
    }, index=dly.index).shift(1)
    dmap = dctx.reindex(s.index, method="ffill")

    dates = d["dt"].dt.date
    day_code = pd.factorize(dates)[0].astype(np.int64)
    bod = d.groupby(dates).cumcount().to_numpy(np.int64)
    # True on the last bar Dhan actually has for that calendar day. A normal day's last bar
    # opens ~15:25 (mod~370), comfortably past eod_min(360) -- but Dhan's recent-day data can
    # lag and stop as early as ~15:10 (mod 355), which NEVER reaches eod_min, silently letting
    # a position roll into the next day instead of being forced flat (found 2026-09-29: 5.4% of
    # A+ v1 OOS trades were multi-day holds, all from the last ~2 months of harvested data,
    # where Dhan's own live feed -- confirmed with a fresh pull, not a stale cache -- still
    # truncates before 15:25). last_of_day is the robust fallback: force flat here regardless
    # of whether mod[] ever reaches eod_min that day.
    last_of_day = np.r_[day_code[1:] != day_code[:-1], final_day_complete]

    # ---- day-level catalyst features (all knowable in real time) ----
    g = d.groupby(day_code)
    day_open = g["open"].transform("first").to_numpy(np.float64)
    prev_close = dmap["d_close"].to_numpy(np.float64)
    with np.errstate(divide="ignore", invalid="ignore"):
        gap = np.where(prev_close > 0, (day_open - prev_close) / prev_close * 100.0, 0.0)

    # opening volume of this session vs the 20-session average opening volume
    mod = ((d["dt"].dt.hour * 60 + d["dt"].dt.minute) - (9 * 60 + 15)).to_numpy(np.int64)
    open_mask = mod < 30  # first 30 minutes, whatever the bar size
    ov = pd.Series(np.where(open_mask, v, 0.0)).groupby(day_code).transform("sum").to_numpy(np.float64)
    per_day_ov = pd.Series(ov).groupby(day_code).first()
    base_ov = per_day_ov.shift(1).rolling(20, min_periods=5).mean()
    base_map = pd.Series(day_code).map(base_ov).to_numpy(np.float64)
    with np.errstate(divide="ignore", invalid="ignore"):
        orvol = np.where(base_map > 0, ov / base_map, 1.0)

    # same-slot relative volume (bar level)
    vol = pd.Series(v)
    slot = pd.Series(bod)
    sbase = vol.groupby(slot).transform(lambda x: x.shift(1).rolling(20, min_periods=5).mean())
    rvol = (vol / sbase).to_numpy(np.float64)

    with np.errstate(divide="ignore", invalid="ignore"):
        atr_pct = np.where(c > 0, atr / c * 100.0, 0.0)

    turnover = float(np.nanmedian((dly["close"] * dly["volume"]).to_numpy()))

    # NIFTY since-open return on the same (completed) 5m bar -> relative strength
    if index is not None:
        naive = d["dt"].dt.tz_localize(None) if d["dt"].dt.tz is not None else d["dt"]
        n_ret = index["n_ret"].reindex(pd.DatetimeIndex(naive), method="ffill").to_numpy(np.float64)
    else:
        n_ret = np.zeros(len(d))

    fix = lambda a, x=0.0: np.nan_to_num(a, nan=x, posinf=x, neginf=x)  # noqa: E731
    return dict(
        o=o, h=h, l=l, c=c, v=v,
        ema_f=fix(ema_f), sma_m=fix(sma_m), sma_l=fix(sma_l), atr=fix(atr),
        atr_pct=fix(atr_pct),
        hf_close=fix(mapped["hf_close"].to_numpy(np.float64)),
        hf_ema=fix(mapped["hf_ema"].to_numpy(np.float64)),
        hf_sma=fix(mapped["hf_sma"].to_numpy(np.float64)),
        d_sma20=fix(dmap["d_sma20"].to_numpy(np.float64)),
        d_sma200=fix(dmap["d_sma200"].to_numpy(np.float64)),
        d_close=fix(dmap["d_close"].to_numpy(np.float64)),
        d_high=fix(dmap["d_high"].to_numpy(np.float64)),
        d_low=fix(dmap["d_low"].to_numpy(np.float64)),
        day_open=fix(day_open), gap=fix(gap), orvol=fix(orvol, 1.0), rvol=fix(rvol, 1.0),
        n_ret=fix(n_ret),
        day=day_code, bod=bod, mod=mod, bar_min=bar_min, last_of_day=last_of_day,
        warm=max(long, atr_n) + 5,
        dt=d["dt"].dt.tz_localize(None).to_numpy().astype("datetime64[ns]"),  # naive IST
        turnover=turnover,
    )


# --------------------------------------------------------------------------- #
# kernel
# --------------------------------------------------------------------------- #
# trade state vector
S_POS, S_ENTRY, S_STOP, S_TARG, S_RISK, S_MFE, S_BE, S_PART, S_BOOK, S_EI, S_SETUP = range(11)


@njit(cache=True)
def _step(i, st, o, h, l, c, ema_f, sma_m, a, mod, last_of_day, full,
          rr, part_R, part_frac, be_at, trail_after, trail_buf, trail_mode,
          exit_ma_break, hold_min, bar_min, eod_min):
    """Advance one open position through bar i -> (exited, effective exit price, reason).

    Intrabar order is conservative: the stop live at the bar's open is checked first,
    then the partial level, then the target. On the fill bar (full=False) only
    price-level exits are evaluated.
    """
    pos = st[S_POS]
    entry = st[S_ENTRY]
    risk = st[S_RISK]
    stop = st[S_STOP]
    targ = st[S_TARG]
    exited = False
    xp = 0.0
    reason = 0

    if pos > 0:
        ex = (h[i] - entry) / risk
    else:
        ex = (entry - l[i]) / risk
    if ex > st[S_MFE]:
        st[S_MFE] = ex

    if (pos > 0 and l[i] <= stop) or (pos < 0 and h[i] >= stop):
        if pos > 0:
            xp = stop if o[i] > stop else o[i]
        else:
            xp = stop if o[i] < stop else o[i]
        exited = True
        reason = 1
    else:
        if part_R > 0.0 and st[S_PART] == 0.0:
            lvl = entry + part_R * risk if pos > 0 else entry - part_R * risk
            if (pos > 0 and h[i] >= lvl) or (pos < 0 and l[i] <= lvl):
                st[S_PART] = 1.0
                st[S_BOOK] = part_frac * part_R * risk
                if pos > 0 and stop < entry:
                    st[S_STOP] = entry
                elif pos < 0 and stop > entry:
                    st[S_STOP] = entry
        if (pos > 0 and h[i] >= targ) or (pos < 0 and l[i] <= targ):
            if pos > 0:
                xp = targ if o[i] < targ else o[i]
            else:
                xp = targ if o[i] > targ else o[i]
            exited = True
            reason = 2

    if (not exited) and full:
        mfe = st[S_MFE]
        if be_at > 0.0 and st[S_BE] == 0.0 and mfe >= be_at:
            if pos > 0 and st[S_STOP] < entry:
                st[S_STOP] = entry
            elif pos < 0 and st[S_STOP] > entry:
                st[S_STOP] = entry
            st[S_BE] = 1.0
        if trail_after > 0.0 and mfe >= trail_after:
            ref = ema_f[i] if trail_mode == 0 else sma_m[i]
            if pos > 0:
                cand = ref - trail_buf * a
                if cand > st[S_STOP]:
                    st[S_STOP] = cand
            else:
                cand = ref + trail_buf * a
                if cand < st[S_STOP]:
                    st[S_STOP] = cand
        if exit_ma_break == 1:
            if (pos > 0 and c[i] < sma_m[i]) or (pos < 0 and c[i] > sma_m[i]):
                xp = c[i]
                exited = True
                reason = 3
        if not exited:
            held = (i - int(st[S_EI])) * bar_min
            if mod[i] >= eod_min or last_of_day[i]:
                xp = c[i]
                exited = True
                reason = 4
            elif hold_min > 0 and held >= hold_min:
                xp = c[i]
                exited = True
                reason = 5

    if exited:
        rem = 1.0 - part_frac if st[S_PART] == 1.0 else 1.0
        if pos > 0:
            xp = entry + st[S_BOOK] + rem * (xp - entry)
        else:
            xp = entry - st[S_BOOK] - rem * (entry - xp)
    return exited, xp, reason


@njit(cache=True)
def simulate(
    o, h, l, c, ema_f, sma_m, sma_l, atr, atr_pct,
    hf_close, hf_ema, hf_sma,
    d_sma20, d_sma200, d_close, d_high, d_low,
    day_open, gap, orvol, rvol, n_ret, day, mod, last_of_day, warm, bar_min,
    # day gate
    gate_mode, gap_min, orvol_min, dir_from_gap, atrp_min, atrp_max,
    # trend gates
    slope_lb, slope_min, slope_max, ext_max, min_run,
    use_htf, use_daily, use_200_room, room_min, use_rvol, rvol_min,
    req_above_open, req_pd_break, rs_min,
    # touches of the 9/20 zone within the current trend leg
    touch_gap, min_touch, max_touch,
    # setups
    pb_on, pb_lb, pb_below, pb_swing, sigq,
    bo_on, bo_n, bo_tight, bo_zone,
    # risk / exits
    stop_buf, min_risk_atr, max_risk_atr, rr, part_R, part_frac, be_at,
    trail_after, trail_buf, trail_mode, exit_ma_break, hold_min, arm_bars,
    # session, minutes after 09:15
    entry_from, entry_to, eod_min, max_trades_day, allow_long, allow_short,
):
    n = c.shape[0]
    MAXT = 300000
    t_dir = np.zeros(MAXT, np.int64)
    t_ei = np.zeros(MAXT, np.int64)
    t_xi = np.zeros(MAXT, np.int64)
    t_ep = np.zeros(MAXT, np.float64)
    t_xp = np.zeros(MAXT, np.float64)
    t_risk = np.zeros(MAXT, np.float64)
    t_setup = np.zeros(MAXT, np.int64)
    t_reason = np.zeros(MAXT, np.int64)
    t_mfe = np.zeros(MAXT, np.float64)
    t_touch = np.zeros(MAXT, np.int64)
    nt = 0

    st = np.zeros(11, np.float64)
    arm = 0
    arm_px = 0.0
    arm_stop = 0.0
    arm_exp = -1
    arm_setup = 0
    arm_touch = 0
    cur_touch = 0
    trades_today = 0
    cur_day = -1

    reg_l = False
    reg_s = False
    tl = 0
    ts = 0
    last_tl = -100000
    last_ts = -100000
    ep_l = -1
    ep_s = -1

    for i in range(warm, n):
        if day[i] != cur_day:
            cur_day = day[i]
            trades_today = 0
            arm = 0
        a = atr[i]
        if a <= 0.0:
            continue

        # ---------- zone touches within the current leg, tracked on every bar ----------
        nl = ema_f[i] > sma_m[i]
        if nl != reg_l:
            reg_l = nl
            tl = 0
            last_tl = -100000
            ep_l = -1
        ns = ema_f[i] < sma_m[i]
        if ns != reg_s:
            reg_s = ns
            ts = 0
            last_ts = -100000
            ep_s = -1
        if reg_l and l[i] <= ema_f[i] and l[i] >= sma_m[i] - 0.5 * a:
            if i - last_tl > touch_gap:
                ep_l = tl
                tl += 1
            last_tl = i
        if reg_s and h[i] >= ema_f[i] and h[i] <= sma_m[i] + 0.5 * a:
            if i - last_ts > touch_gap:
                ep_s = ts
                ts += 1
            last_ts = i

        # ---------- open position ----------
        if st[S_POS] != 0.0:
            exited, xp, reason = _step(i, st, o, h, l, c, ema_f, sma_m, a, mod, last_of_day, True,
                                       rr, part_R, part_frac, be_at, trail_after, trail_buf,
                                       trail_mode, exit_ma_break, hold_min, bar_min, eod_min)
            if exited:
                t_dir[nt] = int(st[S_POS])
                t_ei[nt] = int(st[S_EI])
                t_xi[nt] = i
                t_ep[nt] = st[S_ENTRY]
                t_xp[nt] = xp
                t_risk[nt] = st[S_RISK]
                t_setup[nt] = int(st[S_SETUP])
                t_reason[nt] = reason
                t_mfe[nt] = st[S_MFE]
                t_touch[nt] = cur_touch
                nt += 1
                st[S_POS] = 0.0
                if nt >= MAXT:
                    break
            continue

        # ---------- armed stop order ----------
        if arm != 0:
            if i > arm_exp or trades_today >= max_trades_day or mod[i] > entry_to:
                arm = 0
            else:
                hit = (arm == 1 and h[i] >= arm_px) or (arm == -1 and l[i] <= arm_px)
                if hit:
                    if arm == 1:
                        fill = arm_px if o[i] < arm_px else o[i]
                        r = fill - arm_stop
                    else:
                        fill = arm_px if o[i] > arm_px else o[i]
                        r = arm_stop - fill
                    d_ = arm
                    arm = 0
                    if r > 0.0:
                        st[S_POS] = d_
                        st[S_ENTRY] = fill
                        st[S_STOP] = arm_stop
                        st[S_RISK] = r
                        st[S_TARG] = fill + rr * r if d_ == 1 else fill - rr * r
                        st[S_MFE] = 0.0
                        st[S_BE] = 0.0
                        st[S_PART] = 0.0
                        st[S_BOOK] = 0.0
                        st[S_EI] = i
                        st[S_SETUP] = arm_setup
                        cur_touch = arm_touch
                        trades_today += 1
                        exited, xp, reason = _step(i, st, o, h, l, c, ema_f, sma_m, a, mod,
                                                   last_of_day, False,
                                                   rr, part_R, part_frac, be_at, trail_after,
                                                   trail_buf, trail_mode, exit_ma_break, hold_min,
                                                   bar_min, eod_min)
                        if exited:
                            t_dir[nt] = d_
                            t_ei[nt] = i
                            t_xi[nt] = i
                            t_ep[nt] = st[S_ENTRY]
                            t_xp[nt] = xp
                            t_risk[nt] = st[S_RISK]
                            t_setup[nt] = int(st[S_SETUP])
                            t_reason[nt] = reason
                            t_mfe[nt] = st[S_MFE]
                            t_touch[nt] = cur_touch
                            nt += 1
                            st[S_POS] = 0.0
                        continue

        # ---------- new setup at this bar's close ----------
        if trades_today >= max_trades_day:
            continue
        if mod[i] < entry_from or mod[i] > entry_to:
            continue
        if atrp_min > 0.0 and atr_pct[i] < atrp_min:
            continue
        if atrp_max > 0.0 and atr_pct[i] > atrp_max:
            continue

        gp = gap[i]
        agp = gp if gp >= 0.0 else -gp
        ok_gap = agp >= gap_min
        ok_ov = orvol[i] >= orvol_min
        if gate_mode == 1 and not ok_gap:
            continue
        if gate_mode == 2 and not ok_ov:
            continue
        if gate_mode == 3 and not (ok_gap or ok_ov):
            continue
        if gate_mode == 4 and not (ok_gap and ok_ov):
            continue

        al = allow_long == 1
        ash = allow_short == 1
        if dir_from_gap == 1:
            if gp > 0.0:
                ash = False
            elif gp < 0.0:
                al = False
        elif dir_from_gap == -1:
            if gp > 0.0:
                al = False
            elif gp < 0.0:
                ash = False

        slope = (sma_m[i] - sma_m[i - slope_lb]) / a
        L = al and ema_f[i] > sma_m[i] and slope >= slope_min and slope <= slope_max
        Sh = ash and ema_f[i] < sma_m[i] and slope <= -slope_min and slope >= -slope_max
        if use_htf == 1:
            L = L and hf_close[i] > hf_sma[i] and hf_ema[i] > hf_sma[i]
            Sh = Sh and hf_close[i] < hf_sma[i] and hf_ema[i] < hf_sma[i]
        if use_daily == 1:
            L = L and d_close[i] > d_sma20[i]
            Sh = Sh and d_close[i] < d_sma20[i]
        if use_rvol == 1:
            L = L and rvol[i] >= rvol_min
            Sh = Sh and rvol[i] >= rvol_min
        if req_above_open == 1:
            L = L and c[i] > day_open[i]
            Sh = Sh and c[i] < day_open[i]
        if req_pd_break == 1:
            L = L and c[i] > d_high[i]
            Sh = Sh and c[i] < d_low[i]
        ext = (c[i] - sma_m[i]) / a
        if ext > ext_max:
            L = False
        if -ext > ext_max:
            Sh = False
        if rs_min > -50.0:  # relative strength vs NIFTY since the open, in the trade direction
            rsv = (c[i] / day_open[i] - 1.0) * 100.0 - n_ret[i]
            if rsv < rs_min:
                L = False
            if -rsv < rs_min:
                Sh = False
        if use_200_room == 1:
            if L and d_sma200[i] > c[i] and (d_sma200[i] - c[i]) < room_min * a:
                L = False
            if Sh and d_sma200[i] < c[i] and (c[i] - d_sma200[i]) < room_min * a:
                Sh = False
        if not (L or Sh):
            continue

        rng = h[i] - l[i]
        armed = False
        # ---------- pullback into the 9/20 zone ----------
        if pb_on == 1:
            if L and last_tl == i and ep_l >= min_touch and (max_touch < 0 or ep_l <= max_touch):
                run_hi = h[i]
                for k in range(i - pb_lb + 1, i + 1):
                    if h[k] > run_hi:
                        run_hi = h[k]
                floor = sma_m[i] - pb_below * a
                q_ok = sigq <= 0.0 or (rng > 0.0 and (c[i] - l[i]) / rng >= sigq)
                if l[i] >= floor and c[i] >= floor and (run_hi - sma_m[i]) >= min_run * a and q_ok:
                    sw = l[i]
                    for k in range(i - pb_swing + 1, i + 1):
                        if l[k] < sw:
                            sw = l[k]
                    px = h[i] + TICK
                    stp = sw - stop_buf * a
                    if px - stp < min_risk_atr * a:
                        stp = px - min_risk_atr * a
                    if max_risk_atr <= 0.0 or (px - stp) <= max_risk_atr * a:
                        arm = 1
                        arm_px = px
                        arm_stop = stp
                        arm_exp = i + arm_bars
                        arm_setup = 1
                        arm_touch = ep_l
                        armed = True
            if (not armed) and Sh and last_ts == i and ep_s >= min_touch and (max_touch < 0 or ep_s <= max_touch):
                run_lo = l[i]
                for k in range(i - pb_lb + 1, i + 1):
                    if l[k] < run_lo:
                        run_lo = l[k]
                ceil_ = sma_m[i] + pb_below * a
                q_ok = sigq <= 0.0 or (rng > 0.0 and (h[i] - c[i]) / rng >= sigq)
                if h[i] <= ceil_ and c[i] <= ceil_ and (sma_m[i] - run_lo) >= min_run * a and q_ok:
                    sw = h[i]
                    for k in range(i - pb_swing + 1, i + 1):
                        if h[k] > sw:
                            sw = h[k]
                    px = l[i] - TICK
                    stp = sw + stop_buf * a
                    if stp - px < min_risk_atr * a:
                        stp = px + min_risk_atr * a
                    if max_risk_atr <= 0.0 or (stp - px) <= max_risk_atr * a:
                        arm = -1
                        arm_px = px
                        arm_stop = stp
                        arm_exp = i + arm_bars
                        arm_setup = 1
                        arm_touch = ep_s
                        armed = True
        if armed:
            continue

        # ---------- base breakout ----------
        if bo_on == 1:
            bh = h[i]
            bl = l[i]
            for k in range(i - bo_n + 1, i + 1):
                if h[k] > bh:
                    bh = h[k]
                if l[k] < bl:
                    bl = l[k]
            if (bh - bl) <= bo_tight * a:
                if L and bl <= ema_f[i] + bo_zone * a and bh >= sma_m[i]:
                    px = bh + TICK
                    stp = bl - stop_buf * a
                    if px - stp < min_risk_atr * a:
                        stp = px - min_risk_atr * a
                    if max_risk_atr <= 0.0 or (px - stp) <= max_risk_atr * a:
                        arm = 1
                        arm_px = px
                        arm_stop = stp
                        arm_exp = i + arm_bars
                        arm_setup = 2
                        arm_touch = tl
                elif Sh and bh >= ema_f[i] - bo_zone * a and bl <= sma_m[i]:
                    px = bl - TICK
                    stp = bh + stop_buf * a
                    if stp - px < min_risk_atr * a:
                        stp = px + min_risk_atr * a
                    if max_risk_atr <= 0.0 or (stp - px) <= max_risk_atr * a:
                        arm = -1
                        arm_px = px
                        arm_stop = stp
                        arm_exp = i + arm_bars
                        arm_setup = 2
                        arm_touch = ts

    open_flag = 1 if st[S_POS] != 0.0 else 0
    return (t_dir[:nt], t_ei[:nt], t_xi[:nt], t_ep[:nt], t_xp[:nt],
            t_risk[:nt], t_setup[:nt], t_reason[:nt], t_mfe[:nt], t_touch[:nt],
            open_flag, st[S_POS], st[S_ENTRY], st[S_STOP], st[S_TARG], st[S_RISK],
            int(st[S_EI]), int(st[S_SETUP]), int(cur_touch))


# --------------------------------------------------------------------------- #
DEFAULTS = dict(
    gate_mode=4, gap_min=1.0, orvol_min=1.5, dir_from_gap=0, atrp_min=0.0, atrp_max=0.0,
    slope_lb=10, slope_min=0.15, slope_max=2.5, ext_max=1.5, min_run=1.0,
    use_htf=1, use_daily=1, use_200_room=0, room_min=1.0, use_rvol=0, rvol_min=1.0,
    req_above_open=0, req_pd_break=0, rs_min=-99.0,
    touch_gap=3, min_touch=0, max_touch=-1,
    pb_on=1, pb_lb=12, pb_below=0.25, pb_swing=3, sigq=0.0,
    bo_on=1, bo_n=6, bo_tight=1.5, bo_zone=0.5,
    stop_buf=0.15, min_risk_atr=0.8, max_risk_atr=0.0, rr=4.0, part_R=0.0, part_frac=0.5,
    be_at=0.0, trail_after=1.0, trail_buf=0.5, trail_mode=0, exit_ma_break=0,
    hold_min=0, arm_bars=3,
    entry_from=30, entry_to=330, eod_min=360, max_trades_day=2,
    allow_long=1, allow_short=1,
)

_ORDER = [
    "gate_mode", "gap_min", "orvol_min", "dir_from_gap", "atrp_min", "atrp_max",
    "slope_lb", "slope_min", "slope_max", "ext_max", "min_run",
    "use_htf", "use_daily", "use_200_room", "room_min", "use_rvol", "rvol_min",
    "req_above_open", "req_pd_break", "rs_min",
    "touch_gap", "min_touch", "max_touch",
    "pb_on", "pb_lb", "pb_below", "pb_swing", "sigq",
    "bo_on", "bo_n", "bo_tight", "bo_zone",
    "stop_buf", "min_risk_atr", "max_risk_atr", "rr", "part_R", "part_frac", "be_at",
    "trail_after", "trail_buf", "trail_mode", "exit_ma_break", "hold_min", "arm_bars",
    "entry_from", "entry_to", "eod_min", "max_trades_day", "allow_long", "allow_short",
]
_INT = {
    "gate_mode", "dir_from_gap", "slope_lb", "use_htf", "use_daily", "use_200_room",
    "use_rvol", "req_above_open", "req_pd_break", "touch_gap", "min_touch", "max_touch",
    "pb_on", "pb_lb", "pb_swing", "bo_on", "bo_n", "trail_mode", "exit_ma_break",
    "hold_min", "arm_bars", "entry_from", "entry_to", "eod_min", "max_trades_day",
    "allow_long", "allow_short",
}
_ARRS = ["o", "h", "l", "c", "ema_f", "sma_m", "sma_l", "atr", "atr_pct",
         "hf_close", "hf_ema", "hf_sma", "d_sma20", "d_sma200", "d_close", "d_high", "d_low",
         "day_open", "gap", "orvol", "rvol", "n_ret", "day", "mod", "last_of_day"]


def _simulate_call(prep, over):
    p = dict(DEFAULTS)
    p.update(over)
    args = [int(p[k]) if k in _INT else float(p[k]) for k in _ORDER]
    return simulate(*[prep[k] for k in _ARRS], int(prep["warm"]), int(prep["bar_min"]), *args)


def run(prep: dict, **over) -> pd.DataFrame:
    d, ei, xi, ep, xp, risk, setup, reason, mfe, touch, *_open = _simulate_call(prep, over)
    pts = np.where(d == 1, xp - ep, ep - xp)
    return pd.DataFrame({
        "dir": d,
        "entry_dt": prep["dt"][ei], "exit_dt": prep["dt"][xi],
        "entry": ep, "exit": xp, "risk": risk,
        "points": pts,
        "R": np.where(risk > 0, pts / risk, 0.0),
        "pct": np.where(ep > 0, pts / ep * 100.0, 0.0),
        "risk_pct": np.where(ep > 0, risk / ep * 100.0, 0.0),
        "bars": xi - ei, "setup": setup, "reason": reason, "mfe_R": mfe, "touch": touch,
        # day-level context at entry, used for exact post-filtering of whole days
        "gap": prep["gap"][ei], "orvol": prep["orvol"][ei], "atr_pct": prep["atr_pct"][ei],
        "day": prep["day"][ei],
    })


def run_with_open(prep: dict, **over):
    """Same as run(), plus whatever position is STILL OPEN at the end of the data (or None).
    For live shadow tracking: run this on data through the latest completed bar and read
    `open_position` to know what to mark, rather than reimplementing fill/exit detection
    separately from the tested kernel."""
    res = _simulate_call(prep, over)
    trades = run(prep, **over)
    (open_flag, pos, entry, stop, targ, risk, ei, setup, touch) = res[10:]
    if not open_flag:
        return trades, None
    i = len(prep["c"]) - 1  # data ends at the last bar; that's "now" for a live caller
    open_position = dict(
        dir=int(pos), entry=float(entry), stop=float(stop), target=float(targ),
        risk=float(risk), entry_dt=prep["dt"][ei], entry_i=int(ei), setup=int(setup), touch=int(touch),
        as_of_dt=prep["dt"][i],
    )
    return trades, open_position
