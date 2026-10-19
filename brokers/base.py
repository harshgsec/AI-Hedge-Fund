"""Broker abstraction base class."""
from abc import ABC, abstractmethod
from typing import Any

class BrokerAdapter(ABC):
    @abstractmethod
    def initialize(self) -> bool:
        """Connect / authenticate. Return True on success."""
        pass

    @abstractmethod
    def fetch_market_data(self, symbol: str) -> dict:
        """Return dict with bid, ask, equity, h1_data, daily_data, etc."""
        pass

    @abstractmethod
    def get_open_positions(self, symbol: str | None = None) -> list:
        pass

    @abstractmethod
    def execute_trade(self, symbol: str, signal: str, stop_loss: float, take_profit: float, risk_percent: float) -> dict:
        pass

    @abstractmethod
    def close_position(self, ticket: Any) -> dict:
        pass

    def get_account_equity(self) -> float:
        return 0.0
