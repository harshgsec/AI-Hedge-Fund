"""Delta Exchange India — live and demo adapters."""
import hmac
import hashlib
import time
import json
import requests
import pandas as pd
import pandas_ta as ta
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

    def _candles(self, symbol: str, resolution: str, days: int = 30) -> pd.DataFrame:
        try:
            end = int(time.time())
            start = end - days * 86400
            r = requests.get(
                f"{self.BASE}/v2/history/candles",
                params={"symbol": symbol, "resolution": resolution, "start": start, "end": end},
                timeout=15,
            )
            data = r.json().get("result", [])
            if not data:
                return pd.DataFrame()
            df = pd.DataFrame(data)
            for col in ("open", "high", "low", "close", "volume"):
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            return df
        except Exception as e:
            print(f"[SYSTEM] Candles failed for {symbol}: {e}")
            return pd.DataFrame()

    def _indicators(self, df: pd.DataFrame) -> dict:
        if df is None or len(df) < 20:
            return {}
        df = df.copy()
        df["ema"] = ta.ema(df["close"], length=min(200, max(10, len(df) - 1)))
        df["rsi"] = ta.rsi(df["close"], length=14)
        df["atr"] = ta.atr(df["high"], df["low"], df["close"], length=14)
        last = df.iloc[-1]
        return {
            "ema": float(last["ema"]) if pd.notna(last.get("ema")) else None,
            "rsi": float(last["rsi"]) if pd.notna(last.get("rsi")) else None,
            "atr": float(last["atr"]) if pd.notna(last.get("atr")) else None,
            "rel_volume": 1.0,
            "tick_volume": int(last.get("volume", 0) or 0),
            "trend": "UP" if last["close"] > (last.get("ema") or last["close"]) else "DOWN",
            "recent_closes": df.tail(10)["close"].tolist(),
        }

    def fetch_market_data(self, symbol: str) -> dict:
        bid = ask = 0.0
        try:
            r = requests.get(f"{self.BASE}/v2/tickers/{symbol}", timeout=10)
            data = r.json().get("result", {})
            quotes = data.get("quotes", {})
            bid = float(quotes.get("best_bid") or data.get("mark_price") or data.get("close") or 0)
            ask = float(quotes.get("best_ask") or data.get("mark_price") or data.get("close") or 0)
        except Exception as e:
            print(f"[SYSTEM] Ticker failed for {symbol}: {e}")

        h1 = self._indicators(self._candles(symbol, "1h", 14))
        d1 = self._indicators(self._candles(symbol, "1d", 250))
        print(f"[DATA] {symbol} bid={bid} ask={ask} h1={bool(h1)} d1={bool(d1)}")

        return {
            "symbol": symbol,
            "bid": bid,
            "ask": ask,
            "spread": max(ask - bid, 0),
            "equity": self.get_account_equity(),
            "h1_data": h1,
            "daily_data": d1,
        }

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
        equity = self.get_account_equity() or 1000
        atr = 100
        try:
            m = self.fetch_market_data(symbol)
            atr = m.get("h1_data", {}).get("atr") or 100
        except Exception:
            atr = 100
        risk_amount = equity * (risk_percent / 100.0)
        size = max(1, int(risk_amount / max(atr, 1)))
        body = {"product_symbol": symbol, "size": size, "side": side, "order_type": "market_order"}
        body_str = json.dumps(body)
        headers = self._sign("POST", "/v2/orders", "", body_str)
        try:
            r = requests.post(f"{self.BASE}/v2/orders", headers=headers, data=body_str, timeout=10)
            resp = r.json()
            oid = resp.get("result", {}).get("id")
            print(f"[TRADE] {self.__class__.__name__} {signal} {symbol} size={size} id={oid}")
            return {"order": oid, "price": 0, "volume": size, "sl": stop_loss, "tp": take_profit, "deal": oid}
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
            headers = self._sign("POST", "/v2/orders", "", body_str)
            requests.post(f"{self.BASE}/v2/orders", headers=headers, data=body_str, timeout=10)
            return {"success": True, "ticket": ticket}
        except Exception as e:
            return {"success": False, "error": str(e)}

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
