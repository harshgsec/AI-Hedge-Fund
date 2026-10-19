"""Zerodha Kite Connect adapter — full implementation."""
from datetime import datetime, timedelta
from kiteconnect import KiteConnect
import pandas as pd
import pandas_ta as ta
import config
from .base import BrokerAdapter

class KiteAdapter(BrokerAdapter):
    def __init__(self):
        self.kite = None
        self._instrument_cache = {}

    def initialize(self) -> bool:
        if not config.KITE_API_KEY or not config.KITE_ACCESS_TOKEN:
            print("[SYSTEM] Kite credentials missing")
            return False
        self.kite = KiteConnect(api_key=config.KITE_API_KEY)
        self.kite.set_access_token(config.KITE_ACCESS_TOKEN)
        try:
            profile = self.kite.profile()
            print(f"[SYSTEM] Kite connected | User: {profile.get('user_name')}")
            return True
        except Exception as e:
            print(f"[SYSTEM] Kite init failed: {e}")
            return False

    def _resolve_instrument(self, symbol: str) -> dict:
        if symbol in self._instrument_cache:
            return self._instrument_cache[symbol]
        for exchange in ("NSE", "NFO", "MCX"):
            try:
                instruments = self.kite.instruments(exchange)
                for inst in instruments:
                    if inst.get("tradingsymbol") == symbol:
                        self._instrument_cache[symbol] = inst
                        return inst
            except Exception:
                continue
        return {"tradingsymbol": symbol, "exchange": "NSE", "instrument_token": None}

    def _historical_df(self, instrument_token: int, interval: str, days: int) -> pd.DataFrame:
        if not instrument_token:
            return pd.DataFrame()
        to_date = datetime.now()
        from_date = to_date - timedelta(days=days)
        try:
            data = self.kite.historical_data(instrument_token, from_date, to_date, interval)
            if not data:
                return pd.DataFrame()
            df = pd.DataFrame(data)
            df.rename(columns={"date": "time"}, inplace=True)
            return df
        except Exception as e:
            print(f"[SYSTEM] Historical fetch failed: {e}")
            return pd.DataFrame()

    def _calc_indicators(self, df: pd.DataFrame) -> dict:
        if df is None or len(df) < 30:
            return {}
        df = df.copy()
        df["ema"] = ta.ema(df["close"], length=min(200, len(df) - 1))
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
        inst = self._resolve_instrument(symbol)
        exchange = inst.get("exchange", "NSE")
        quote_key = f"{exchange}:{symbol}"
        try:
            quote = self.kite.quote([quote_key])
            q = quote.get(quote_key, {})
            ltp = float(q.get("last_price", 0))
        except Exception:
            ltp = 0.0

        token = inst.get("instrument_token")
        h1_df = self._historical_df(token, "60minute", 30)
        d1_df = self._historical_df(token, "day", 250)

        return {
            "symbol": symbol,
            "bid": ltp,
            "ask": ltp,
            "spread": 0.0,
            "equity": self.get_account_equity(),
            "h1_data": self._calc_indicators(h1_df),
            "daily_data": self._calc_indicators(d1_df),
        }

    def get_account_equity(self) -> float:
        try:
            margins = self.kite.margins()
            return float(margins.get("equity", {}).get("net", 0))
        except Exception:
            return 0.0

    def get_open_positions(self, symbol: str | None = None) -> list:
        try:
            positions = self.kite.positions().get("net", [])
            if symbol:
                positions = [p for p in positions if p.get("tradingsymbol") == symbol]
            return [
                {
                    "ticket": p.get("tradingsymbol"),
                    "symbol": p.get("tradingsymbol"),
                    "type": "BUY" if p.get("quantity", 0) > 0 else "SELL",
                    "volume": abs(p.get("quantity", 0)),
                    "price_open": p.get("average_price", 0),
                    "sl": 0,
                    "tp": 0,
                    "profit": p.get("pnl", 0),
                }
                for p in positions if p.get("quantity", 0) != 0
            ]
        except Exception:
            return []

    def _calc_qty(self, symbol: str, sl_price: float, risk_percent: float, equity: float) -> int:
        if equity <= 0 or sl_price <= 0:
            return 1
        risk_amount = equity * (risk_percent / 100.0)
        price = self.fetch_market_data(symbol).get("ask", 0)
        distance = max(abs(price - sl_price), 0.01)
        qty = int(risk_amount / distance)
        return max(1, min(qty, 1000))

    def execute_trade(self, symbol: str, signal: str, stop_loss: float, take_profit: float, risk_percent: float) -> dict:
        inst = self._resolve_instrument(symbol)
        exchange = inst.get("exchange", "NSE")
        equity = self.get_account_equity()
        qty = self._calc_qty(symbol, stop_loss, risk_percent, equity)
        transaction_type = "BUY" if signal == "BUY" else "SELL"
        try:
            order_id = self.kite.place_order(
                variety="regular",
                exchange=exchange,
                tradingsymbol=symbol,
                transaction_type=transaction_type,
                quantity=qty,
                product="MIS",
                order_type="MARKET",
            )
            import time
            time.sleep(1)
            orders = self.kite.orders()
            filled = next((o for o in orders if o.get("order_id") == order_id), {})
            avg_price = filled.get("average_price", 0)
            status = filled.get("status", "UNKNOWN")
            print(f"[TRADE] Kite {signal} {symbol} qty={qty} order_id={order_id} status={status}")
            return {
                "order": order_id,
                "price": avg_price,
                "volume": qty,
                "sl": stop_loss,
                "tp": take_profit,
                "deal": order_id,
                "status": status,
            }
        except Exception as e:
            raise RuntimeError(f"Kite order failed: {e}")

    def close_position(self, ticket) -> dict:
        try:
            positions = self.kite.positions().get("net", [])
            for p in positions:
                if p.get("tradingsymbol") == ticket and p.get("quantity", 0) != 0:
                    qty = abs(p["quantity"])
                    side = "SELL" if p["quantity"] > 0 else "BUY"
                    order_id = self.kite.place_order(
                        variety="regular",
                        exchange=p.get("exchange", "NSE"),
                        tradingsymbol=ticket,
                        transaction_type=side,
                        quantity=qty,
                        product=p.get("product", "MIS"),
                        order_type="MARKET",
                    )
                    print(f"[TRADE] Closed {ticket} order_id={order_id}")
                    return {"success": True, "ticket": ticket, "order": order_id}
            return {"success": False, "error": "Position not found"}
        except Exception as e:
            return {"success": False, "error": str(e)}
