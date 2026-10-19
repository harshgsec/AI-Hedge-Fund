"""Dhan adapter — not supported in production build."""
from .base import BrokerAdapter

class DhanAdapter(BrokerAdapter):
    def initialize(self) -> bool:
        print("[SYSTEM] Dhan is not supported in this production build")
        return False
    def fetch_market_data(self, symbol: str) -> dict:
        return {}
    def get_open_positions(self, symbol: str | None = None) -> list:
        return []
    def execute_trade(self, symbol: str, signal: str, stop_loss: float, take_profit: float, risk_percent: float) -> dict:
        raise RuntimeError("Dhan is not supported")
    def close_position(self, ticket) -> dict:
        return {"success": False}
    def get_account_equity(self) -> float:
        return 0.0
