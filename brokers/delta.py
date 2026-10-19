"""Delta Exchange India — live and demo adapters."""
import hmac
import hashlib
import time
import json
import requests
import config
from .base import BrokerAdapter

class _DeltaBase(BrokerAdapter):
    BASE = ""

    def __init__(self):
        self.api_key = ""
        self.api_secret = ""

    def _sign(self, method: str, path: str, query: str = "", body: str = "") -> dict:
        ts = str(int(time.time()))
        message = method + ts + path + query + body
        sig = hmac.new(self.api_secret.encode(), message.encode(), hashlib.sha256).hexdigest()
        return {
            "api-key": self.api_key,
            "timestamp": ts,
            "signature": sig,
            "User-Agent": "python-rest-client",
            "Content-Type": "application/json",
        }

    def initialize(self) -> bool:
        if not self.api_key or not self.api_secret:
            print(f"[SYSTEM] {self.__class__.__name__} credentials missing")
            return False
        try:
            headers = self._sign("GET", "/v2/wallet/balances")
            r = requests.get(f"{self.BASE}/v2/wallet/balances", headers=headers, timeout=10)
            r.raise_for_status()
            print(f"[SYSTEM] {self.__class__.__name__} connected")
            return True
        except Exception as e:
            print(f"[SYSTEM] {self.__class__.__name__} init failed: {e}")
            return False

    def get_account_equity(self) -> float:
        try:
            headers = self._sign("GET", "/v2/wallet/balances")
            r = requests.get(f"{self.BASE}/v2/wallet/balances", headers=headers, timeout=10)
            for b in r.json().get("result", []):
                if b.get("asset_symbol") in ("INR", "USDT", "USD"):
                    return float(b.get("balance", 0))
        except Exception:
            pass
        return 0.0

    def get_open_positions(self, symbol: str | None = None) -> list:
        try:
            headers = self._sign("GET", "/v2/positions")
            r = requests.get(f"{self.BASE}/v2/positions", headers=headers, timeout=10)
            positions = r.json().get("result", [])
            out = []
            for p in positions:
                if symbol and p.get("product_symbol") != symbol:
                    continue
                size = float(p.get("size", 0))
                if size == 0:
                    continue
                out.append({
                    "ticket": p.get("product_symbol"),
                    "symbol": p.get("product_symbol"),
                    "type": "BUY" if size > 0 else "SELL",
                    "volume": abs(size),
                    "price_open": float(p.get("entry_price", 0)),
                    "sl": 0,
                    "tp": 0,
                    "profit": float(p.get("unrealized_pnl", 0)),
                })
            return out
        except Exception:
            return []

    def fetch_market_data(self, symbol: str) -> dict:
        return {
            "symbol": symbol,
            "bid": 0,
            "ask": 0,
            "spread": 0,
            "equity": self.get_account_equity(),
            "h1_data": {},
            "daily_data": {},
        }

    def execute_trade(self, symbol: str, signal: str, stop_loss: float, take_profit: float, risk_percent: float) -> dict:
        side = "buy" if signal == "BUY" else "sell"
        body = {"product_symbol": symbol, "size": 1, "side": side, "order_type": "market_order"}
        body_str = json.dumps(body)
        headers = self._sign("POST", "/v2/orders", "", body_str)
        try:
            r = requests.post(f"{self.BASE}/v2/orders", headers=headers, data=body_str, timeout=10)
            resp = r.json()
            oid = resp.get("result", {}).get("id")
            return {"order": oid, "price": 0, "volume": 1, "sl": stop_loss, "tp": take_profit, "deal": oid}
        except Exception as e:
            raise RuntimeError(f"Delta order failed: {e}")

    def close_position(self, ticket) -> dict:
        return {"success": False, "error": "Use opposite market order"}

class DeltaLiveAdapter(_DeltaBase):
    """Live Delta Exchange India."""
    BASE = "https://api.india.delta.exchange"

    def __init__(self):
        self.api_key = config.DELTA_API_KEY
        self.api_secret = config.DELTA_API_SECRET

class DeltaDemoAdapter(_DeltaBase):
    """Delta Exchange India testnet / demo."""
    BASE = "https://cdn-ind.testnet.deltaex.org"

    def __init__(self):
        self.api_key = config.DELTA_DEMO_API_KEY
        self.api_secret = config.DELTA_DEMO_API_SECRET
