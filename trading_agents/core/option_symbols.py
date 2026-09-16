"""Identify the option contract behind a Dhan fill."""
import re
from dataclasses import dataclass
from datetime import date, datetime

_MONTHS = {m: i for i, m in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], 1)}
# Dhan trade-book / positions format: CRUDEOIL-17Sep2026-9900-PE, or BANKNIFTY-Sep2026-55800-CE (no day)
_TRADING_RE = re.compile(
    r"^(?P<u>[A-Z0-9&]+)-(?P<d>\d{1,2})?(?P<m>[A-Za-z]{3})(?P<y>\d{4})-(?P<k>\d+(?:\.\d+)?)-(?P<r>CE|PE)$")
_CUSTOM_RE = re.compile(
    r"^(?P<u>[A-Z0-9&-]+)\s+(?P<d>\d{1,2})\s+(?P<m>[A-Z]{3})\s+(?P<k>\d+(?:\.\d+)?)\s+(?P<r>CALL|PUT)$")


@dataclass(frozen=True)
class OptionContract:
    underlying: str
    expiry: date
    strike: float
    right: str          # "CE" or "PE"

    @property
    def label(self):
        return f"{self.underlying} {self.expiry:%d%b%y}".upper() + f" {self.strike:g} {self.right}"


def _right(s):
    s = (s or "").upper()
    if s in ("CALL", "CE"):
        return "CE"
    if s in ("PUT", "PE"):
        return "PE"
    return None


def parse_custom_symbol(symbol, ref_date):
    """'CRUDEOIL 17 SEP 8000 PUT' -> OptionContract. The year is not in the symbol,
    so the expiry is the first matching day/month on or after ref_date."""
    m = _CUSTOM_RE.match((symbol or "").strip().upper())
    if not m:
        return None
    day, month = int(m["d"]), _MONTHS.get(m["m"])
    if month is None:
        return None
    expiry = date(ref_date.year, month, day)
    if expiry < ref_date:
        expiry = date(ref_date.year + 1, month, day)
    return OptionContract(m["u"], expiry, float(m["k"]), _right(m["r"]))


def parse_trading_symbol(symbol):
    """'CRUDEOIL-17Sep2026-9900-PE' -> OptionContract. The trade book uses this format, with
    drvOptionType "NA". Expiry is None when the symbol carries no day (BANKNIFTY monthly)."""
    m = _TRADING_RE.match((symbol or "").strip())
    if not m:
        return None
    month = _MONTHS.get(m["m"].upper())
    if month is None:
        return None
    expiry = date(int(m["y"]), month, int(m["d"])) if m["d"] else None
    return OptionContract(m["u"].upper(), expiry, float(m["k"]), m["r"])


def display(contract):
    """One canonical label per contract, so history rows (customSymbol) and trade-book rows
    (tradingSymbol) for the same option group together in FIFO and episodes."""
    c = contract
    right = "CALL" if c.right == "CE" else "PUT"
    if c.expiry is None:
        return f"{c.underlying} {c.strike:g} {right}"
    mon = [k for k, v in _MONTHS.items() if v == c.expiry.month][0]
    return f"{c.underlying} {c.expiry.day:02d} {mon} {c.expiry.year} {c.strike:g} {right}"


def underlying_of(symbol):
    return (symbol or "").strip().split(" ")[0].split("-")[0].upper()


def from_fill(raw, trade_time=None):
    """Prefer Dhan's structured drv* fields; fall back to parsing customSymbol."""
    symbol = raw.get("customSymbol") or raw.get("tradingSymbol") or ""
    ts = parse_trading_symbol(raw.get("tradingSymbol")) or parse_trading_symbol(symbol)
    # the trade book sends drvOptionType "NA": take the right from the symbol suffix instead
    right = _right(raw.get("drvOptionType")) or (ts.right if ts else None)
    exp = raw.get("drvExpiryDate")
    strike = raw.get("drvStrikePrice")
    if right and exp and exp != "NA" and strike:
        try:
            expiry = datetime.fromisoformat(str(exp)[:10]).date()
            return OptionContract(underlying_of(symbol), expiry, float(strike), right)
        except ValueError:
            pass
    if ts and ts.expiry:
        return ts
    ref = (trade_time or datetime.now()).date()
    return parse_custom_symbol(symbol, ref)
