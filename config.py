"""Configuration for the Autonomous AI Hedge Fund."""
import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MEMORY_FILE = os.path.join(BASE_DIR, "memory.json")
RULES_FILE = os.path.join(BASE_DIR, "new_rules.json")

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_BASE = os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# Active broker: kite (primary) | fyers (backup) | delta (crypto/RWA)
# Dhan and INDmoney are not supported in this production build.
ACTIVE_BROKER = os.getenv("ACTIVE_BROKER", "kite").lower()

# Kite
KITE_API_KEY = os.getenv("KITE_API_KEY", "")
KITE_ACCESS_TOKEN = os.getenv("KITE_ACCESS_TOKEN", "")

# FYERS
FYERS_CLIENT_ID = os.getenv("FYERS_CLIENT_ID", "")
FYERS_ACCESS_TOKEN = os.getenv("FYERS_ACCESS_TOKEN", "")

# Dhan
DHAN_CLIENT_ID = os.getenv("DHAN_CLIENT_ID", "")
DHAN_ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN", "")

# Delta Exchange
DELTA_API_KEY = os.getenv("DELTA_API_KEY", "")
DELTA_API_SECRET = os.getenv("DELTA_API_SECRET", "")

DEFAULT_RISK_PERCENT = float(os.getenv("DEFAULT_RISK_PERCENT", "1.0"))
SCAN_INTERVAL_SECONDS = int(os.getenv("SCAN_INTERVAL_SECONDS", "30"))
CONFIDENCE_THRESHOLD = int(os.getenv("CONFIDENCE_THRESHOLD", "65"))

SYMBOLS = [s.strip() for s in os.getenv(
    "SYMBOLS",
    # USA indices
    "US30,US500,NAS100,"
    # India indices
    "NIFTY,BANKNIFTY,FINNIFTY,SENSEX,"
    # Major FX influencing USA & India
    "EURUSD,GBPUSD,USDJPY,USDCHF,USDCAD,AUDUSD,NZDUSD,USDINR,"
    # Commodities — full MCX set + international equivalents
    "GOLD,GOLDM,GOLDGUINEA,GOLDPETAL,"
    "SILVER,SILVERM,SILVERMIC,"
    "COPPER,ZINC,ALUMINIUM,LEAD,NICKEL,"
    "CRUDEOIL,CRUDEOILM,NATURALGAS,"
    "MENTHAOIL,COTTON,CARDAMOM,"
    "XAUUSD,XAGUSD,USOIL,UKOIL,NGAS,PALLADIUM,PLATINUM"
).split(",") if s.strip()]

TIMEFRAMES = {"H1": "60minute", "D1": "day"}

EMA_PERIOD = 200
RSI_PERIOD = 14
ATR_PERIOD = 14
VOL_MA_PERIOD = 20

AUDIT_TRADE_THRESHOLD = int(os.getenv("AUDIT_TRADE_THRESHOLD", "10"))
AUDIT_COOLDOWN_HOURS = int(os.getenv("AUDIT_COOLDOWN_HOURS", "12"))
