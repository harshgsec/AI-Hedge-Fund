"""Self-learning auditor that analyzes losses and writes rules."""
import json
import os
from datetime import datetime, timezone, timedelta
import requests
import config
from memory_store import load_trade_memory, reconcile_closed_trades

def _llm_endpoint_and_key():
    if config.OPENROUTER_API_KEY:
        return config.OPENROUTER_BASE, config.OPENROUTER_API_KEY, config.LLM_MODEL
    return config.DEEPSEEK_API_BASE, config.DEEPSEEK_API_KEY, config.DEEPSEEK_MODEL

def load_rules_document() -> dict:
    if not os.path.exists(config.RULES_FILE):
        return {"rules": [], "last_audit_at": None, "trades_analyzed": 0}
    try:
        with open(config.RULES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"rules": [], "last_audit_at": None, "trades_analyzed": 0}

def save_rules_document(doc: dict):
    with open(config.RULES_FILE, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2, default=str)

def run_audit(force: bool = False) -> dict:
    reconcile_closed_trades()
    memory = load_trade_memory()
    closed = [t for t in memory if t.get("status") == "CLOSED" and "realized_pl" in t]
    if len(closed) < 3:
        return {"status": "insufficient_trades", "count": len(closed)}

    doc = load_rules_document()
    if not force and doc.get("last_audit_at"):
        last = datetime.fromisoformat(doc["last_audit_at"])
        if datetime.now(timezone.utc) - last < timedelta(hours=config.AUDIT_COOLDOWN_HOURS):
            return {"status": "cooldown", "last_audit_at": doc["last_audit_at"]}

    losses = [t for t in closed[-50:] if t.get("outcome") == "LOSS"]
    if not losses:
        return {"status": "no_losses"}

    summary_lines = []
    for t in losses:
        ctx = t.get("market_context", {})
        summary_lines.append(
            f"Symbol:{t.get('symbol')} Side:{t.get('signal')} "
            f"P/L:{t.get('realized_pl')} H1_ATR:{ctx.get('h1', {}).get('atr')} "
            f"H1_RelVol:{ctx.get('h1', {}).get('rel_volume')} D1_ATR:{ctx.get('daily', {}).get('atr')}"
        )
    loss_text = "\n".join(summary_lines)

    prompt = f"""You are the Chief Risk Officer and Quantitative Auditor of an institutional hedge fund.

Analyze the following recent losing trades and identify recurring loss patterns.

Recent losses:
{loss_text}

Return ONLY a JSON array of rules. Each rule must have:
affected_symbol (string or \"ALL\"), setup (string), confidence_reduction_points (integer 15-30), sample_size (integer), evidence (string).
"""

    try:
        base, key, model = _llm_endpoint_and_key()
        resp = requests.post(
            f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 800,
                "response_format": {"type": "json_object"},
            },
            timeout=60,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        new_rules = parsed if isinstance(parsed, list) else parsed.get("rules", [])
    except Exception as e:
        print(f"[AUDITOR] Audit LLM failed: {e}")
        return {"status": "error", "message": str(e)}

    doc["rules"].extend(new_rules)
    doc["last_audit_at"] = datetime.now(timezone.utc).isoformat()
    doc["trades_analyzed"] = len(closed)
    save_rules_document(doc)
    print(f"[AUDITOR] Audit complete. Added {len(new_rules)} rules.")
    return {"status": "success", "new_rules": len(new_rules), "total_rules": len(doc["rules"])}
