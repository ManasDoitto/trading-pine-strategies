"""Synthetic Dhan fills for tests. Never real account data."""
from datetime import datetime
from itertools import count

_ids = count(1)


def fill(time, side, qty, px, symbol="CRUDEOIL 17 AUG 7000 PUT", expiry="2026-08-17", strike=7000.0,
         right="PUT", order_id=None, brokerage=0.0, segment="MCX_COMM", instrument="OPTFUT", product="INTRADAY"):
    if isinstance(time, str):
        time = datetime.fromisoformat(time)
    return {
        "orderId": order_id or f"ORD{next(_ids)}",
        "exchangeTradeId": "0",
        "transactionType": side,
        "exchangeSegment": segment,
        "productType": product,
        "customSymbol": symbol,
        "securityId": "1",
        "tradedQuantity": qty,
        "tradedPrice": px,
        "instrument": instrument,
        "brokerageCharges": brokerage,
        "sebiTax": 0.0, "stt": 0.0, "serviceTax": 0.0, "exchangeTransactionCharges": 0.0, "stampDuty": 0.0,
        "exchangeTime": time.isoformat(),
        "drvExpiryDate": expiry,
        "drvOptionType": right,
        "drvStrikePrice": strike,
    }


RULES = dict(r1_min_gap_minutes=5, r1_min_drop_pct=0.0, r2_enabled=True, r3_expiry_days=2,
             r4_premium_stop_pct=30.0, r5_daily_loss_limit_inr=20000, r6_max_positions_per_day=10,
             r6_revenge_window_minutes=15, r6_revenge_loss_inr=5000, r7_max_strikes_otm=3)
