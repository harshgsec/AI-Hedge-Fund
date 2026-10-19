"""DeepSeek AI decision engine with learned-rule injection."""
import json
import re
import requests
import config
from auditor import load_rules_document

def load_learned_rules(symbol: str) -> list:
    doc = load_rules_document()
    return [r for r in doc.get("rules", []) if r.get("affected_symbol") in (symbol, "ALL")]

def get_ai_decision(market_data: dict, symbol: str) -> dict:
    rules = load_learned_rules(symbol)
    rules_text = "\n".join(
        f"- {r.get('setup')} → reduce confidence by {r.get('confidence_reduction_points')} pts. Evidence: {r.get('evidence')}"
        for r in rules
    ) or "None"

    h1 = market_data.get("h1_data", {})
    d1 = market_data.get("daily_data", {})
    price = market_data.get("ask", 0)

    system = f"""You are the Senior Portfolio Manager of an institutional AI hedge fund.
You must be strictly risk-managed. Prefer high-confluence setups. When in doubt, return HOLD.

ACTIVE RISK AUDIT RULES (apply the confidence penalties when conditions match):
{rules_text}

Return ONLY valid JSON:
{{
  "signal": "BUY" | "SELL" | "HOLD",
  "confidence_score": integer 0-100,
  "stop_loss": float,
  "take_profit": float,
  "logic": "concise explanation including indicators and any learned-rule deductions"
}}

Geometric rules:
- BUY: stop_loss < price < take_profit
- SELL: take_profit < price < stop_loss
If you cannot produce valid geometry, still return the JSON; the system will correct it.
"""

    user = f"""Symbol: {symbol}
Ask: {market_data.get('ask')} Bid: {market_data.get('bid')} Spread: {market_data.get('spread')}

H1: EMA={h1.get('ema')} RSI={h1.get('rsi')} ATR={h1.get('atr')} RelVol={h1.get('rel_volume')} Trend={h1.get('trend')}
Daily: EMA={d1.get('ema')} RSI={d1.get('rsi')} ATR={d1.get('atr')} RelVol={d1.get('rel_volume')} Trend={d1.get('trend')}
"""

    resp = requests.post(
        f"{config.DEEPSEEK_API_BASE}/chat/completions",
        headers={"Authorization": f"Bearer {config.DEEPSEEK_API_KEY}", "Content-Type": "application/json"},
        json={
            "model": config.DEEPSEEK_MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.1,
            "max_tokens": 400,
            "response_format": {"type": "json_object"},
        },
        timeout=45,
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    decision = json.loads(content)

    if decision.get("confidence_score", 0) < config.CONFIDENCE_THRESHOLD:
        decision["signal"] = "HOLD"
        decision["logic"] = (decision.get("logic", "") + " [Forced HOLD: below confidence threshold]").strip()

    atr = h1.get("atr") or (price * 0.001)
    if decision["signal"] == "BUY":
        if not (decision.get("stop_loss", 0) < price < decision.get("take_profit", 0)):
            decision["stop_loss"] = round(price - 1.5 * atr, 5)
            decision["take_profit"] = round(price + 3.0 * atr, 5)
    elif decision["signal"] == "SELL":
        if not (decision.get("take_profit", 0) < price < decision.get("stop_loss", 0)):
            decision["stop_loss"] = round(price + 1.5 * atr, 5)
            decision["take_profit"] = round(price - 3.0 * atr, 5)

    print(f"[AI] {symbol} → {decision['signal']} ({decision.get('confidence_score')})")
    return decision
