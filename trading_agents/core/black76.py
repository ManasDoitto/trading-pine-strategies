"""Black-76 pricing, greeks and implied volatility (options on futures / forwards).

Used for MCX options on futures and as a cross-check on Dhan's option-chain greeks.
T is in years, r is the annual continuously-compounded rate, theta is per calendar day.
"""
import math


def _n(x):
    return math.exp(-0.5 * x * x) / math.sqrt(2 * math.pi)


def _N(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def _d1d2(F, K, T, sigma):
    v = sigma * math.sqrt(T)
    d1 = (math.log(F / K) + 0.5 * v * v) / v
    return d1, d1 - v


def price(F, K, T, sigma, r, right):
    if T <= 0 or sigma <= 0:
        intrinsic = max(F - K, 0.0) if right == "CE" else max(K - F, 0.0)
        return intrinsic * math.exp(-r * max(T, 0))
    d1, d2 = _d1d2(F, K, T, sigma)
    df = math.exp(-r * T)
    if right == "CE":
        return df * (F * _N(d1) - K * _N(d2))
    return df * (K * _N(-d2) - F * _N(-d1))


def greeks(F, K, T, sigma, r, right):
    d1, d2 = _d1d2(F, K, T, sigma)
    df = math.exp(-r * T)
    p = price(F, K, T, sigma, r, right)
    delta = df * _N(d1) if right == "CE" else -df * _N(-d1)
    gamma = df * _n(d1) / (F * sigma * math.sqrt(T))
    vega = F * df * _n(d1) * math.sqrt(T) / 100            # per 1 vol point
    theta_year = r * p - df * F * _n(d1) * sigma / (2 * math.sqrt(T))
    return dict(price=p, delta=delta, gamma=gamma, vega=vega, theta=theta_year / 365)


def implied_vol(target, F, K, T, r, right, lo=1e-4, hi=5.0, tol=1e-6, max_iter=200):
    """Bisection IV. Returns None if the price is outside the no-arbitrage range."""
    if T <= 0 or target <= 0:
        return None
    if not (price(F, K, T, lo, r, right) - tol <= target <= price(F, K, T, hi, r, right) + tol):
        return None
    for _ in range(max_iter):
        mid = (lo + hi) / 2
        if price(F, K, T, mid, r, right) < target:
            lo = mid
        else:
            hi = mid
        if hi - lo < tol:
            break
    return (lo + hi) / 2
