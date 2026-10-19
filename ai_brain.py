"""AI decision engine with robust JSON parsing."""
import json
import re
import requests
import config
from auditor import load_rules_document


def _llm_endpoint_and_key():
    if config.OPENROUTER_API_KEY:
        return config.OPENROUTER_BASE, config.OPENROUTER_API_KEY, config.LLM_MODEL
    return config.DEEPSEEK_API_BASE, config.DEEPSEEK_API_KEY, config.DEEPSEEK_MODEL


def load_learned_rules(symbol: str) -> list:
    doc = load_rules_document()
    return [r for r in doc.get("rules", []) if r.get("affected_symbol") in (symbol, "ALL")]


def _extract_json(text: str) -> dict:
    if not text:
        raise ValueError("Empty LLM response")
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON object in response: {text[:200]}")
    raw = match.group(0)
    raw = re.sub(r",\s*}", "}", raw)
    raw = re.sub(r",\s*]", "]", raw)
    return json.loads(raw)


def get_ai_decision(market_data: dict, symbol: str) -> dict:
    rules = load_learned_rules(symbol)
    rules_text = "\n".join(
        f"- {r.get('setup')} → reduce confidence by {r.get('confidence_reduction_points')} pts. Evidence: {r.get('evidence')}"
        for r in rules
    ) or "None"

    h1 = market_data.get("h1_data", {})
    d1 = market_data.get("daily_data", {})
    price = market_data.get("ask") or 0

    system = f"""You are the Senior Portfolio Manager of an institutional AI hedge fund.
You must be strictly risk-managed. Prefer high-confluence setups. When in doubt, return HOLD.

ACTIVE RISK AUDIT RULES (apply the confidence penalties when conditions match):
{rules_text}

Return ONLY valid JSON with double quotes:
{{
  "signal": "BUY",
  "confidence_score": 75,
  "stop_loss": 0.0,
  "take_profit": 0.0,
  "logic": "concise explanation"
}}

signal must be one of: BUY, SELL, HOLD.
"""

    user = f"""Symbol: {symbol}
Ask: {market_data.get('ask')} Bid: {market_data.get('bid')} Spread: {market_data.get('spread')}

H1: EMA={h1.get('ema')} RSI={h1.get('rsi')} ATR={h1.get('atr')} Trend={h1.get('trend')}
Daily: EMA={d1.get('ema')} RSI={d1.get('rsi')} ATR={d1.get('atr')} Trend={d1.get('trend')}
"""

    base, key, model = _llm_endpoint_and_key()
    resp = requests.post(
        f"{base}/chat/completions",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.1,
            "max_tokens": 400,
        },
        timeout=45,
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    decision = _extract_json(content)

    decision.setdefault("signal", "HOLD")
    decision.setdefault("confidence_score", 0)
    decision.setdefault("logic", "")
    decision.setdefault("stop_loss", 0)
    decision.setdefault("take_profit", 0)

    if decision.get("confidence_score", 0) < config.CONFIDENCE_THRESHOLD:
        decision["signal"] = "HOLD"
        decision["logic"] = (decision.get("logic", "") + " [Forced HOLD: below confidence threshold]").strip()

    atr = h1.get("atr") or (price * 0.001 if price else 1)
    if decision["signal"] == "BUY" and price:
        if not (decision.get("stop_loss", 0) < price < decision.get("take_profit", 0)):
            decision["stop_loss"] = round(price - 1.5 * atr, 5)
            decision["take_profit"] = round(price + 3.0 * atr, 5)
    elif decision["signal"] == "SELL" and price:
        if not (decision.get("take_profit", 0) < price < decision.get("stop_loss", 0)):
            decision["stop_loss"] = round(price + 1.5 * atr, 5)
            decision["take_profit"] = round(price - 3.0 * atr, 5)

    print(f"[AI] {symbol} → {decision['signal']} ({decision.get('confidence_score')})")
    return decision
