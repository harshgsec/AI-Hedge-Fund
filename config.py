"""Configuration for the Autonomous AI Hedge Fund."""
import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MEMORY_FILE = os.path.join(BASE_DIR, "memory.json")
RULES_FILE = os.path.join(BASE_DIR, "new_rules.json")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE = os.getenv("OPENROUTER_BASE", "https://openrouter.ai/api/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "minimax/minimax-m3.1-flash:free")

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_BASE = os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

ACTIVE_BROKER = os.getenv("ACTIVE_BROKER", "delta_demo").lower()

KITE_API_KEY = os.getenv("KITE_API_KEY", "")
KITE_ACCESS_TOKEN = os.getenv("KITE_ACCESS_TOKEN", "")
FYERS_CLIENT_ID = os.getenv("FYERS_CLIENT_ID", "")
FYERS_ACCESS_TOKEN = os.getenv("FYERS_ACCESS_TOKEN", "")
DHAN_CLIENT_ID = os.getenv("DHAN_CLIENT_ID", "")
DHAN_ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN", "")

DELTA_API_KEY = os.getenv("DELTA_API_KEY", "")
DELTA_API_SECRET = os.getenv("DELTA_API_SECRET", "")
DELTA_DEMO_API_KEY = os.getenv("DELTA_DEMO_API_KEY", "")
DELTA_DEMO_API_SECRET = os.getenv("DELTA_DEMO_API_SECRET", "")

DEFAULT_RISK_PERCENT = float(os.getenv("DEFAULT_RISK_PERCENT", "1.0"))
SCAN_INTERVAL_SECONDS = int(os.getenv("SCAN_INTERVAL_SECONDS", "30"))
CONFIDENCE_THRESHOLD = int(os.getenv("CONFIDENCE_THRESHOLD", "65"))

_raw = [s.strip() for s in os.getenv("SYMBOLS", "BTCUSD,ETHUSD,SOLUSD").split(",") if s.strip()]
SYMBOLS = [s for s in _raw if "_" not in s and not s.endswith("INR")]

TIMEFRAMES = {"H1": "60minute", "D1": "day"}
EMA_PERIOD = 200
RSI_PERIOD = 14
ATR_PERIOD = 14
VOL_MA_PERIOD = 20
AUDIT_TRADE_THRESHOLD = int(os.getenv("AUDIT_TRADE_THRESHOLD", "10"))
AUDIT_COOLDOWN_HOURS = int(os.getenv("AUDIT_COOLDOWN_HOURS", "12"))
