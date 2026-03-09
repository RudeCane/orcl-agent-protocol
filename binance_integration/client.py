import time, logging, requests
from typing import Dict, List, Optional
logger = logging.getLogger(__name__)

BINANCE_API = "https://api.binance.com/api/v3"
BINANCE_US_API = "https://api.binance.us/api/v3"
BINANCE_WS = "wss://stream.binance.com:9443/ws"
BINANCE_US_WS = "wss://stream.binance.us:9443/ws"

class BinanceClient:
    """Binance and Binance.US market data client. No API key needed for public data."""

    def __init__(self, use_us=False):
        self.base_url = BINANCE_US_API if use_us else BINANCE_API
        self.ws_url = BINANCE_US_WS if use_us else BINANCE_WS
        self.exchange = "binance_us" if use_us else "binance"
        self.name = "Binance.US" if use_us else "Binance"
        self.cache = {}
        self.cache_ttl = 3
        self.trade_log = []

    def get_ticker(self, symbol="BTCUSDT"):
        ck = f"ticker_{symbol}"
        if ck in self.cache and time.time() - self.cache[ck]["t"] < self.cache_ttl:
            return self.cache[ck]["d"]
        try:
            resp = requests.get(f"{self.base_url}/ticker/24hr", params={"symbol": symbol}, timeout=5)
            data = resp.json()
            result = {
                "symbol": symbol,
                "exchange": self.exchange,
                "last": float(data.get("lastPrice", 0)),
                "bid": float(data.get("bidPrice", 0)),
                "ask": float(data.get("askPrice", 0)),
                "high_24h": float(data.get("highPrice", 0)),
                "low_24h": float(data.get("lowPrice", 0)),
                "volume_24h": float(data.get("volume", 0)),
                "quote_volume_24h": float(data.get("quoteVolume", 0)),
                "change_24h": float(data.get("priceChangePercent", 0)),
                "trades_24h": int(data.get("count", 0)),
            }
            self.cache[ck] = {"d": result, "t": time.time()}
            return result
        except Exception as e:
            logger.error(f"[{self.name}] Ticker error: {e}")
            return None

    def get_orderbook(self, symbol="BTCUSDT", limit=20):
        try:
            resp = requests.get(f"{self.base_url}/depth", params={"symbol": symbol, "limit": limit}, timeout=5)
            data = resp.json()
            return {
                "symbol": symbol,
                "exchange": self.exchange,
                "bids": [[float(b[0]), float(b[1])] for b in data.get("bids", [])],
                "asks": [[float(a[0]), float(a[1])] for a in data.get("asks", [])],
                "timestamp": time.time(),
            }
        except Exception as e:
            logger.error(f"[{self.name}] Orderbook error: {e}")
            return None

    def get_klines(self, symbol="BTCUSDT", interval="5m", limit=100):
        try:
            resp = requests.get(f"{self.base_url}/klines", params={"symbol": symbol, "interval": interval, "limit": limit}, timeout=5)
            data = resp.json()
            return [{"time": int(c[0]) // 1000, "open": float(c[1]), "high": float(c[2]),
                     "low": float(c[3]), "close": float(c[4]), "volume": float(c[5])} for c in data]
        except Exception as e:
            logger.error(f"[{self.name}] Klines error: {e}")
            return []

    def get_all_tickers(self):
        try:
            resp = requests.get(f"{self.base_url}/ticker/price", timeout=5)
            return resp.json()
        except Exception as e:
            logger.error(f"[{self.name}] All tickers error: {e}")
            return []

    def get_exchange_info(self):
        try:
            resp = requests.get(f"{self.base_url}/exchangeInfo", timeout=5)
            data = resp.json()
            symbols = [s["symbol"] for s in data.get("symbols", []) if s.get("status") == "TRADING" and s["symbol"].endswith("USDT")]
            return symbols[:50]
        except Exception as e:
            logger.error(f"[{self.name}] Exchange info error: {e}")
            return []

    POPULAR_PAIRS = [
        "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
        "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "LINKUSDT", "DOTUSDT",
        "MATICUSDT", "UNIUSDT", "ARBUSDT", "OPUSDT", "APTUSDT", "SUIUSDT",
    ]

binance_client = BinanceClient(use_us=False)
binance_us_client = BinanceClient(use_us=True)
