# AI Hedge Fund — Multi-Broker

Autonomous AI trading system for Indian markets (Kite / FYERS) and crypto/RWA (Delta Exchange).

## Quick Start

```bash
cp .env.example .env
# Fill ACTIVE_BROKER and the matching credentials
pip install -r requirements.txt
uvicorn main:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000

## Brokers (production)

| Role | Broker | Status |
|------|--------|--------|
| **Primary** | Zerodha Kite | Production-ready path |
| **Backup** | FYERS | Available |
| **Crypto / RWA** | Delta Exchange | Available (run separately or switch) |
| Skipped | Dhan, INDmoney | Not supported |

## Notes

- Adapters fetch live quotes + historical candles and compute EMA/RSI/ATR.
- Position sizing is risk-percent based (refine per instrument).
- Self-learning auditor writes rules to `new_rules.json`.
- Test on demo / small size first.
