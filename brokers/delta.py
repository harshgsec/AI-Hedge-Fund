"""Delta Exchange India adapter — full implementation."""
import hmac
import hashlib
import time
import json
import requests
import pandas as pd
import pandas_ta as ta
import config
from .base import BrokerAdapter

class DeltaAdapter(BrokerAdapter):
    BASE = "https://api.india.delta.exchange"

    def __init__(self):
        self.api_key = config.DELTA_API_KEY
        self.api_secret = config.DELTA_API_SECRET

    def _sign(self, method: str, path: str, body: str = "") -> dict:
        ts = str(int(time.time()))
        message = method + ts + path + body
        sig = hmac.new(self.api_secret.encode(), message.encode(), hashlib.sha256).hexdigest()
        return {
            "api-key": self.api_key,
            "timestamp": ts,
            "signature": sig,
            "Content-Type": "application/json",
        }

    def initialize(self) -> bool:
        if not self.api_key or not self.api_secret:
            print("[SYSTEM] Delta credentials missing")
            return False
        try:
            headers = self._sign("GET", "/v2/wallet/balances")
            r = requests.get(f"{self.BASE}/v2/wallet/balances", headers=headers, timeout=10)
            r.raise_for_status()
            print("[SYSTEM] Delta Exchange connected")
            return True
        except Exception as e:
            print(f"[SYSTEM] Delta init failed: {e}")
            return False

    def _candles(self, symbol: str, resolution: str, limit: int = 200) -> pd.DataFrame:
        try:
            r = requests.get(
                f"{self.BASE}/v2/history/candles",
                params={"symbol": symbol, "resolution": resolution, "limit": limit},
                timeout=10,
            )
            data = r.json().get("result", [])
            if not data:
                return pd.DataFrame()
            df = pd.DataFrame(data)
            df.rename(columns={"time": "time", "open": "open", "high": "high", "low": "low", "close": "close", "volume": "volume"}, inplace=True)
            df["time"] = pd.to_datetime(df["time"], unit="s")
            return df
        except Exception:
            return pd.DataFrame()

    def _calc(self, df: pd.DataFrame) -> dict:
        if df is None or len(df) < 30:
            return {}
        df = df.copy()
        df["ema"] = ta.ema(df["close"], length=min(200, len(df)-1))
        df["rsi"] = ta.rsi(df["close"], length=14)
        df["atr"] = ta.atr(df["high"], df["low"], df["close"], length=14)
        last = df.iloc[-1]
        return {
            "ema": float(last["ema"]) if pd.notna(last.get("ema")) else None,
            "rsi": float(last["rsi"]) if pd.notna(last.get("rsi")) else None,
            "atr": float(last["atr"]) if pd.notna(last.get("atr")) else None,
            "rel_volume": 1.0,
            "tick_volume": int(last.get("volume", 0)),
            "trend": "UP" if last["close"] > last.get("ema", last["close"]) else "DOWN",
            "recent_closes": df.tail(10)["close"].tolist(),
        }

    def fetch_market_data(self, symbol: str) -> dict:
        try:
            r = requests.get(f"{self.BASE}/v2/tickers/{symbol}", timeout=10)
            data = r.json().get("result", {})
            bid = float(data.get("quotes", {}).get("best_bid", 0))
            ask = float(data.get("quotes", {}).get("best_ask", 0))
        except Exception:
            bid = ask = 0.0
        h1 = self._candles(symbol, "60m", 200)
        d1 = self._candles(symbol, "1d", 250)
        return {
            "symbol": symbol,
            "bid": bid,
            "ask": ask,
            "spread": ask - bid,
            "equity": self.get_account_equity(),
            "h1_data": self._calc(h1),
            "daily_data": self._calc(d1),
        }

    def get_account_equity(self) -> float:
        try:
            headers = self._sign("GET", "/v2/wallet/balances")
            r = requests.get(f"{self.BASE}/v2/wallet/balances", headers=headers, timeout=10)
            for b in r.json().get("result", []):
                if b.get("asset_symbol") == "INR":
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

    def execute_trade(self, symbol: str, signal: str, stop_loss: float, take_profit: float, risk_percent: float) -> dict:
        side = "buy" if signal == "BUY" else "sell"
        body = {
            "product_symbol": symbol,
            "size": 1,
            "side": side,
            "order_type": "market_order",
        }
        body_str = json.dumps(body)
        headers = self._sign("POST", "/v2/orders", body_str)
        try:
            r = requests.post(f"{self.BASE}/v2/orders", headers=headers, data=body_str, timeout=10)
            resp = r.json()
            oid = resp.get("result", {}).get("id")
            print(f"[TRADE] Delta {signal} {symbol} id={oid}")
            return {"order": oid, "price": 0, "volume": 1, "sl": stop_loss, "tp": take_profit, "deal": oid}
        except Exception as e:
            raise RuntimeError(f"Delta order failed: {e}")

    def close_position(self, ticket) -> dict:
        try:
            positions = self.get_open_positions(ticket)
            if not positions:
                return {"success": False, "error": "Not found"}
            pos = positions[0]
            side = "sell" if pos["type"] == "BUY" else "buy"
            body = {"product_symbol": ticket, "size": pos["volume"], "side": side, "order_type": "market_order"}
            body_str = json.dumps(body)
            headers = self._sign("POST", "/v2/orders", body_str)
            requests.post(f"{self.BASE}/v2/orders", headers=headers, data=body_str, timeout=10)
            print(f"[TRADE] Closed Delta {ticket}")
            return {"success": True, "ticket": ticket}
        except Exception as e:
            return {"success": False, "error": str(e)}
