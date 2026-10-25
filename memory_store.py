"""Persistent trade memory (broker-agnostic)."""
import json
import os
from datetime import datetime, timezone
import config

def _load_memory() -> list:
    if not os.path.exists(config.MEMORY_FILE):
        return []
    try:
        with open(config.MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def _save_memory(data: list):
    with open(config.MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)

def append_trade_memory(record: dict):
    memory = _load_memory()
    record["recorded_at"] = datetime.now(timezone.utc).isoformat()
    memory.append(record)
    _save_memory(memory)
    print(f"[LEARNING] Trade memory appended | ticket={record.get('ticket')}")

def load_trade_memory() -> list:
    return _load_memory()

def reconcile_closed_trades() -> int:
    """Pull recent fills from the active broker and mark closed trades."""
    try:
        from brokers import get_broker
        b = get_broker(config.ACTIVE_BROKER)
        fills = getattr(b, "get_fills", lambda: [])()
        if not fills:
            return 0
        memory = _load_memory()
        known = {str(m.get("deal")) for m in memory}
        added = 0
        for f in fills:
            did = str(f.get("deal"))
            if did and did not in known:
                f["recorded_at"] = datetime.now(timezone.utc).isoformat()
                f["status"] = "FILLED"
                memory.append(f)
                added += 1
        if added:
            _save_memory(memory)
            print(f"[RECONCILE] {added} new fills")
        return added
    except Exception as e:
        print(f"[RECONCILE] error: {e}")
        return 0
