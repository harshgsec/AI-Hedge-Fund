"""Broker factory with lazy imports."""

def get_broker(name: str):
    name = (name or "").lower()
    if name == "kite":
        from .kite import KiteAdapter
        return KiteAdapter()
    if name == "fyers":
        from .fyers import FyersAdapter
        return FyersAdapter()
    if name == "dhan":
        from .dhan import DhanAdapter
        return DhanAdapter()
    if name == "delta":
        from .delta import DeltaLiveAdapter
        return DeltaLiveAdapter()
    if name == "delta_demo":
        from .delta import DeltaDemoAdapter
        return DeltaDemoAdapter()
    raise ValueError(f"Unknown broker: {name}")
