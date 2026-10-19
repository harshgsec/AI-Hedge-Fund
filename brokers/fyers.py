"""FYERS adapter — backup broker."""
from .base import BrokerAdapter

class FyersAdapter(BrokerAdapter):
    def initialize(self) -> bool:
        print("[SYSTEM] FYERS adapter loaded (backup)")
        return True
    def fetch_market_data(self, symbol: str) -> dict:
        return {"symbol": symbol, "bid": 0, "ask": 0, "spread": 0, "equity": 0, "h1_data": {}, "daily_data": {}}
    def get_open_positions(self, symbol: str | None = None) -> list:
        return []
    def execute_trade(self, symbol: str, signal: str, stop_loss: float, take_profit: float, risk_percent: float) -> dict:
        raise RuntimeError("FYERS adapter is backup; switch ACTIVE_BROKER=fyers and complete credentials")
    def close_position(self, ticket) -> dict:
        return {"success": False, "error": "Not implemented"}
    def get_account_equity(self) -> float:
        return 0.0
