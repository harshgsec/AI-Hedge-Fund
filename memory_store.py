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
    """
    Broker-agnostic stub.
    Full reconciliation requires broker-specific trade history.
    For now, mark nothing and return 0.
    Extend per broker when trade history endpoints are wired.
    """
    return 0
