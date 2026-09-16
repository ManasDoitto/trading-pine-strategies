"""Minimal SVG candlestick charts drawn from Dhan bars (no plotting library needed).

Journal charts come from here instead of TradingView screenshots, so a run never
touches the trader's TradingView tabs or layouts.
"""
import bisect
import math
from html import escape

UP, DOWN, BUY, SELL, GRID, TEXT, FRAME = "#1a9850", "#d73027", "#2166ac", "#b2182b", "#e8e8e8", "#333333", "#bbbbbb"


def _nice_ticks(lo, hi, n=5):
    span = (hi - lo) or abs(hi) or 1.0
    raw = span / n
    mag = 10 ** math.floor(math.log10(raw))
    step = next(m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw)
    t, ticks = math.ceil(lo / step) * step, []
    while t <= hi + step * 1e-9:
        ticks.append(t)
        t += step
    return ticks


def _fmt(v):
    return f"{v:,.0f}" if abs(v) >= 1000 else f"{v:,.2f}".rstrip("0").rstrip(".")


def candles_svg(bars, title, markers=(), vlines=(), width=960, height=380, interval_minutes=5):
    """bars: DataFrame or list of dicts with time/open/high/low/close.
    markers: dicts(time, price, side BUY|SELL, label) -- drawn at the exact price (option fills).
    vlines:  dicts(time, side, label) -- dashed vertical lines (fill times on the underlying).
    Returns the SVG as a string, or None when there are no bars."""
    rows = bars.to_dict("records") if hasattr(bars, "to_dict") else list(bars)
    if not rows:
        return None
    times = [r["time"] for r in rows]
    left, right, top, bottom = 10, 80, 40, 36
    pw, ph = width - left - right, height - top - bottom
    n = len(rows)
    step = pw / n

    prices = [r["high"] for r in rows] + [r["low"] for r in rows] + [m["price"] for m in markers]
    lo, hi = min(prices), max(prices)
    pad = (hi - lo) * 0.08 or max(abs(hi) * 0.01, 0.5)
    lo, hi = lo - pad, hi + pad

    def y(p):
        return top + (hi - p) / (hi - lo) * ph

    def x_at(t):
        i = min(max(bisect.bisect_right(times, t) - 1, 0), n - 1)
        return left + (i + 0.5) * step

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" '
           f'height="{height}" font-family="Segoe UI, Arial, sans-serif" font-size="11">',
           f'<rect width="{width}" height="{height}" fill="#ffffff"/>',
           f'<text x="{left}" y="24" font-size="14" font-weight="600" fill="{TEXT}">{escape(title)}</text>']

    for t in _nice_ticks(lo, hi):
        yy = y(t)
        out.append(f'<line x1="{left}" x2="{left + pw}" y1="{yy:.1f}" y2="{yy:.1f}" stroke="{GRID}"/>')
        out.append(f'<text x="{left + pw + 6}" y="{yy + 4:.1f}" fill="{TEXT}">{_fmt(t)}</text>')

    every = max(1, round(60 / interval_minutes)) if n > 24 else max(1, n // 6)
    for i in range(0, n, every):
        out.append(f'<text x="{left + (i + 0.5) * step:.1f}" y="{height - 12}" text-anchor="middle" '
                   f'fill="{TEXT}">{times[i]:%H:%M}</text>')

    bw = max(1.0, step * 0.6)
    for i, r in enumerate(rows):
        xx = left + (i + 0.5) * step
        c = UP if r["close"] >= r["open"] else DOWN
        y1, y2 = sorted((y(r["open"]), y(r["close"])))
        out.append(f'<line x1="{xx:.1f}" x2="{xx:.1f}" y1="{y(r["high"]):.1f}" y2="{y(r["low"]):.1f}" stroke="{c}"/>')
        out.append(f'<rect class="candle" x="{xx - bw / 2:.1f}" y="{y1:.1f}" width="{bw:.1f}" '
                   f'height="{max(y2 - y1, 1):.1f}" fill="{c}"/>')

    for k, v in enumerate(vlines):
        xx, c = x_at(v["time"]), BUY if v["side"] == "BUY" else SELL
        out.append(f'<line class="fill-line" x1="{xx:.1f}" x2="{xx:.1f}" y1="{top}" y2="{top + ph}" '
                   f'stroke="{c}" stroke-dasharray="4 3"/>')
        out.append(f'<text x="{xx + 3:.1f}" y="{top + 11 + (k % 4) * 12}" fill="{c}">{escape(v["label"])}</text>')

    for m in markers:
        xx, yy = x_at(m["time"]), y(m["price"])
        if m["side"] == "BUY":
            pts, ty, c = f"{xx:.1f},{yy:.1f} {xx - 6:.1f},{yy + 10:.1f} {xx + 6:.1f},{yy + 10:.1f}", yy + 22, BUY
        else:
            pts, ty, c = f"{xx:.1f},{yy:.1f} {xx - 6:.1f},{yy - 10:.1f} {xx + 6:.1f},{yy - 10:.1f}", yy - 14, SELL
        out.append(f'<polygon class="marker" points="{pts}" fill="{c}"/>')
        out.append(f'<text x="{xx:.1f}" y="{ty:.1f}" text-anchor="middle" fill="{c}" font-weight="600">'
                   f'{escape(m["label"])}</text>')

    out.append(f'<rect x="{left}" y="{top}" width="{pw}" height="{ph}" fill="none" stroke="{FRAME}"/>')
    out.append("</svg>")
    return "\n".join(out)
