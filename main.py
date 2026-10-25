"""FastAPI server and autonomous trading engine."""
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from brokers import get_broker
import config

broker = None

def get_active_broker():
    global broker
    if broker is None:
        broker = get_broker(config.ACTIVE_BROKER)
        if not broker.initialize():
            raise RuntimeError(f"Failed to initialize broker: {config.ACTIVE_BROKER}")
    return broker
from memory_store import append_trade_memory, reconcile_closed_trades, load_trade_memory
from auditor import run_audit, load_rules_document

templates = Jinja2Templates(directory="templates")

bot_state: dict[str, Any] = {
    "is_running": False,
    "interval": config.SCAN_INTERVAL_SECONDS,
    "risk_percent": config.DEFAULT_RISK_PERCENT,
    "equity": 0.0,
    "last_logic": "",
    "last_confidence": 0,
    "last_signal": "HOLD",
    "last_entry_price": None,
    "last_stop_loss": None,
    "last_take_profit": None,
    "trade_history": load_trade_memory(),
    "open_positions": [],
    "learned_rules": [],
    "last_audit_at": None,
}

_cycle_lock = asyncio.Lock()

class ControlRequest(BaseModel):
    action: str | None = None
    interval: int | None = None
    risk_percent: float | None = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[SYSTEM] Starting AI Hedge Fund server...")
    try:
        get_active_broker()
        print(f"[SYSTEM] Broker {config.ACTIVE_BROKER} ready")
    except Exception as e:
        print(f"[SYSTEM] Broker init warning: {e}")
    task = asyncio.create_task(trading_loop())
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

app = FastAPI(title="AI Hedge Fund Terminal", version="2.0.0", lifespan=lifespan)

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return FileResponse("templates/index.html")

@app.get("/api/status")
async def get_status():
    try:
        b = get_active_broker()
        bot_state["equity"] = b.get_account_equity()
        bot_state["open_positions"] = b.get_open_positions()
        fills = getattr(b, "get_fills", lambda: [])()
        if fills:
            existing = {str(t.get("deal")) for t in bot_state["trade_history"]}
            for f in fills:
                if str(f.get("deal")) not in existing:
                    bot_state["trade_history"].append(f)
    except Exception as e:
        print(f"[SYSTEM] Status error: {e}")
    rules = load_rules_document()
    bot_state["learned_rules"] = rules.get("rules", [])
    bot_state["last_audit_at"] = rules.get("last_audit_at")
    bot_state["broker"] = config.ACTIVE_BROKER
    return dict(bot_state)

@app.post("/api/control")
async def control(req: ControlRequest):
    if req.action == "start":
        bot_state["is_running"] = True
    elif req.action == "stop":
        bot_state["is_running"] = False
    if req.interval is not None:
        bot_state["interval"] = max(10, req.interval)
    if req.risk_percent is not None:
        bot_state["risk_percent"] = max(0.1, min(5.0, req.risk_percent))
    return dict(bot_state)

@app.post("/api/close")
async def close_pos(ticket: str):
    try:
        b = get_active_broker()
        return b.close_position(ticket)
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/api/audit")
async def trigger_audit(force: bool = False):
    result = run_audit(force=force)
    rules = load_rules_document()
    bot_state["learned_rules"] = rules.get("rules", [])
    bot_state["last_audit_at"] = rules.get("last_audit_at")
    return result

@app.get("/api/rules")
async def get_rules():
    return load_rules_document()

async def trading_loop():
    while True:
        if bot_state["is_running"]:
            async with _cycle_lock:
                for symbol in config.SYMBOLS:
                    if not bot_state["is_running"]:
                        break
                    try:
                        b = get_active_broker()
                        market = await asyncio.to_thread(b.fetch_market_data, symbol)
                        decision = await asyncio.to_thread(get_ai_decision, market, symbol)
                        bot_state["last_signal"] = decision["signal"]
                        bot_state["last_confidence"] = decision["confidence_score"]
                        bot_state["last_logic"] = decision["logic"]
                        bot_state["last_entry_price"] = market.get("ask")
                        bot_state["last_stop_loss"] = decision.get("stop_loss")
                        bot_state["last_take_profit"] = decision.get("take_profit")

                        if decision["signal"] in ("BUY", "SELL"):
                            positions = b.get_open_positions(symbol)
                            same_dir = [p for p in positions if p.get("type") == decision["signal"]]
                            opposite = [p for p in positions if p.get("type") != decision["signal"]]
                            if same_dir:
                                print(f"[DUPLICATE PREVENTED] {symbol} already has {decision['signal']}")
                                continue
                            for pos in opposite:
                                print(f"[REVERSAL] Closing opposite position {pos.get('ticket')} on {symbol}")
                                b.close_position(pos.get("ticket"))
                            result = await asyncio.to_thread(
                                b.execute_trade, symbol, decision["signal"],
                                decision["stop_loss"], decision["take_profit"], bot_state["risk_percent"],
                            )
                            record = {
                                "symbol": symbol, "signal": decision["signal"],
                                "ticket": result.get("order"), "entry_price": result.get("price"),
                                "sl": result.get("sl"), "tp": result.get("tp"),
                                "volume": result.get("volume"), "status": "CONFIRMED",
                                "deal": result.get("deal"),
                            }
                            append_trade_memory(record)
                            bot_state["trade_history"].append({
                                "time": datetime.now(timezone.utc).isoformat(),
                                "symbol": symbol, "signal": decision["signal"],
                                "fill": result.get("price"), "sl": result.get("sl"),
                                "tp": result.get("tp"), "volume": result.get("volume"),
                                "risk_percent": bot_state["risk_percent"],
                                "deal": result.get("deal"), "order": result.get("order"),
                                "status": "CONFIRMED",
                            })
                    except Exception as e:
                        err = str(e)
                        print(f"[SYSTEM] Error on {symbol}: {err}")
                        bot_state["trade_history"].append({
                            "time": datetime.now(timezone.utc).isoformat(),
                            "symbol": symbol,
                            "signal": decision.get("signal") if "decision" in dir() else "?",
                            "fill": 0,
                            "status": f"FAILED: {err[:80]}",
                        })
                        if "429" in err or "Too Many Requests" in err:
                            print("[SYSTEM] Rate limited, pausing 60s")
                            await asyncio.sleep(60)
                    await asyncio.sleep(1)
                newly = reconcile_closed_trades()
                if newly >= config.AUDIT_TRADE_THRESHOLD:
                    print("[AUDITOR] Threshold reached, running audit...")
                    run_audit(force=False)
        await asyncio.sleep(bot_state["interval"])
