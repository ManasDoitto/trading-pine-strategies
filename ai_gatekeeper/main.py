from fastapi import FastAPI, Request, HTTPException
import logging
from dhan_broker import place_order
from ml_gatekeeper import check_regime

app = FastAPI()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@app.post("/webhook")
async def tradingview_webhook(request: Request):
    """
    Expects a JSON payload from TradingView like:
    {
        "passphrase": "your_secret_passphrase",
        "action": "BUY",
        "symbol": "BANKNIFTY",
        "quantity": 15,
        "price": 45000,
        "strategy": "v13-bear"
    }
    """
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # 1. Security Check
    if data.get("passphrase") != "my_secret_key_123":
        logger.warning("Unauthorized webhook access attempt.")
        raise HTTPException(status_code=401, detail="Unauthorized")

    logger.info(f"Received Signal: {data}")

    symbol = data.get("symbol")
    action = data.get("action")
    quantity = data.get("quantity")
    strategy = data.get("strategy")

    # 2. AI Gatekeeper Check
    # In a real system, you'd fetch the latest market features (volatility, VIX, trend) here.
    # For now, we simulate passing features to the model.
    current_market_features = [1.2, 0.5, 30.0, 1.0] # Dummy features (e.g., [ATR, Trend_Slope, RSI, ADX_Regime])
    
    is_safe_to_trade = check_regime(current_market_features, strategy)

    if not is_safe_to_trade:
        logger.warning(f"AI Gatekeeper BLOCKED {action} signal for {symbol}. Regime unfavorable.")
        return {"status": "blocked", "reason": "AI Gatekeeper determined unfavorable regime"}

    # 3. Order Execution via Dhan
    logger.info(f"AI Gatekeeper APPROVED {action} signal for {symbol}. Executing...")
    
    # We execute a simple market order as per user setup (no dynamic sizing)
    order_response = place_order(symbol=symbol, action=action, quantity=quantity)
    
    if order_response.get("status") == "success":
        return {"status": "executed", "order_id": order_response.get("order_id")}
    else:
        raise HTTPException(status_code=500, detail=f"Order execution failed: {order_response}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
