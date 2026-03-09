import os

# Create binance_integration folder
os.makedirs("binance_integration", exist_ok=True)

# __init__.py
with open("binance_integration/__init__.py", "w") as f:
    f.write("from binance_integration.client import BinanceClient, binance_client\nfrom binance_integration.agent import BinanceAgent\n")
print("Created __init__.py")

# client.py
with open("binance_integration/client.py", "w") as f:
    f.write('''import time, logging, requests
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
''')
print("Created client.py")

# agent.py
with open("binance_integration/agent.py", "w") as f:
    f.write('''import time, logging, threading
from typing import Optional, List, Dict
from binance_integration.client import BinanceClient
logger = logging.getLogger(__name__)

class BinanceAgent:
    """Autonomous agent that monitors Binance or Binance.US markets."""

    def __init__(self, pairs=None, use_us=False, poll_interval=15):
        self.agent_id = f"{'binance_us' if use_us else 'binance'}_{int(time.time()) % 10000}"
        self.pairs = pairs or ["BTCUSDT", "ETHUSDT"]
        self.client = BinanceClient(use_us=use_us)
        self.poll_interval = poll_interval
        self.running = False
        self.status = "idle"
        self.cycle_count = 0
        self._thread = None
        self.errors = []
        self.price_history = {}
        self.last_prices = {}
        self.last_signals = {}
        self.trade_log = []
        self.tokens = self.pairs  # compatibility with server

        # Communication
        self.comms = None
        try:
            from comms.communicator import AgentCommunicator
            self.comms = AgentCommunicator(
                agent_id=self.agent_id,
                agent_type=self.client.exchange,
                capabilities=["market_scan", "price_track", "orderbook_monitor"],
            )
            self.comms.on("signal", self._on_signal)
        except ImportError:
            pass

    def start(self):
        if self.running: return
        self.running = True
        self.status = "running"
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info(f"[{self.agent_id}] Started - watching {self.pairs}")

    def stop(self):
        self.running = False
        self.status = "stopped"

    def _loop(self):
        while self.running:
            try:
                self.status = "scanning"
                for pair in self.pairs:
                    if not self.running: break
                    self._process_pair(pair)
                self.cycle_count += 1
                self.status = "waiting"
                time.sleep(self.poll_interval)
            except Exception as e:
                self.errors.append(str(e))
                if len(self.errors) > 50: self.errors = self.errors[-50:]
                time.sleep(5)

    def _process_pair(self, pair):
        try:
            ticker = self.client.get_ticker(pair)
            if not ticker: return

            price = ticker["last"]
            self.last_prices[pair] = price

            if pair not in self.price_history:
                self.price_history[pair] = []
            self.price_history[pair].append({"price": price, "volume": ticker["volume_24h"], "timestamp": time.time()})
            self.price_history[pair] = self.price_history[pair][-100:]

            # Analyze
            if len(self.price_history[pair]) >= 5:
                signal = self._analyze(pair, ticker)
                if signal:
                    self.last_signals[pair] = signal
                    self.trade_log.append({
                        "action": signal["side"], "symbol": pair, "price": price,
                        "confidence": signal["confidence"], "reason": " | ".join(signal["reasons"]),
                        "exchange": self.client.exchange, "time": time.time(),
                    })
                    if len(self.trade_log) > 100: self.trade_log = self.trade_log[-100:]

                    if self.comms and signal["confidence"] > 0.7:
                        sig_type = "buy_opportunity" if signal["side"] == "long" else "sell_signal"
                        self.comms.broadcast_signal(sig_type, pair, {
                            "symbol": pair, "side": signal["side"],
                            "confidence": signal["confidence"],
                            "reasons": signal["reasons"],
                            "exchange": self.client.exchange,
                            "price": price,
                        })
        except Exception as e:
            logger.error(f"[{self.agent_id}] Error processing {pair}: {e}")

    def _analyze(self, pair, ticker):
        history = self.price_history[pair]
        prices = [h["price"] for h in history]
        if len(prices) < 5: return None

        short_ma = sum(prices[-5:]) / 5
        long_ma = sum(prices) / len(prices)
        ma_diff = ((short_ma - long_ma) / long_ma) * 100

        change = ticker.get("change_24h", 0)

        score = 0
        side = None
        reasons = []

        if ma_diff > 2.0:
            score += 20; side = "long"
            reasons.append(f"Uptrend (MA diff: {ma_diff:.1f}%)")
        elif ma_diff < -2.0:
            score += 20; side = "short"
            reasons.append(f"Downtrend (MA diff: {ma_diff:.1f}%)")

        if change > 3 and side == "long":
            score += 10; reasons.append(f"24h up {change:.1f}%")
        elif change < -3 and side == "short":
            score += 10; reasons.append(f"24h down {change:.1f}%")

        vol = ticker.get("quote_volume_24h", 0)
        if vol > 100000000:
            score += 5; reasons.append(f"High volume ${vol/1e6:.0f}M")

        if not side or score < 20: return None
        confidence = min(score / 40, 1.0)
        if confidence < 0.5: return None

        return {"side": side, "confidence": round(confidence, 2), "reasons": reasons, "price": prices[-1]}

    def _on_signal(self, message):
        content = message.content
        if content.get("confidence", 0) > 0.8:
            logger.info(f"[{self.agent_id}] Signal from {message.sender_id}: {content.get('signal_type')}")

    def get_state(self):
        return {
            "agent_id": self.agent_id,
            "agent_type": self.client.exchange,
            "status": self.status,
            "running": self.running,
            "exchange": self.client.name,
            "tokens": self.pairs,
            "pairs": self.pairs,
            "cycle_count": self.cycle_count,
            "last_prices": self.last_prices,
            "last_signals": self.last_signals,
            "recent_trades": self.trade_log[-10:],
            "errors": self.errors[-5:],
        }
''')
print("Created agent.py")

# integrate.py
with open("binance_integration/integrate.py", "w") as f:
    f.write('''import os

def patch_server():
    sp = os.path.join("api", "server.py")
    if not os.path.exists(sp):
        print("ERROR: api/server.py not found")
        return False
    with open(sp, "r", encoding="utf-8") as fh:
        content = fh.read()
    if "BinanceAgent" in content:
        print("Already patched.")
        return True

    # Add import
    marker = "from config import config"
    if "from binance_integration" not in content:
        content = content.replace(marker, marker + """
from binance_integration.client import binance_client, binance_us_client, BinanceClient
from binance_integration.agent import BinanceAgent""")

    # Add to task endpoint
    old = """    else:
        return {"status": "unknown_task","""
    new = """    elif "binance us" in instruction or "binance.us" in instruction:
        pairs = []
        for p in ["btc", "eth", "sol", "bnb", "xrp", "doge", "ada", "avax", "link", "arb", "op", "sui"]:
            if p in instruction:
                pairs.append(f"{p.upper()}USDT")
        if not pairs:
            pairs = ["BTCUSDT", "ETHUSDT"]
        agent = BinanceAgent(pairs=pairs, use_us=True)
    elif "binance" in instruction:
        pairs = []
        for p in ["btc", "eth", "sol", "bnb", "xrp", "doge", "ada", "avax", "link", "arb", "op", "sui"]:
            if p in instruction:
                pairs.append(f"{p.upper()}USDT")
        if not pairs:
            pairs = ["BTCUSDT", "ETHUSDT"]
        agent = BinanceAgent(pairs=pairs, use_us=False)
    else:
        return {"status": "unknown_task","""
    content = content.replace(old, new)

    # Add routes
    routes = """

@app.get("/api/binance/ticker/{symbol}")
def get_binance_ticker(symbol: str, us: bool = False):
    client = binance_us_client if us else binance_client
    return client.get_ticker(symbol) or {"error": "Not found"}

@app.get("/api/binance/orderbook/{symbol}")
def get_binance_orderbook(symbol: str, limit: int = 20, us: bool = False):
    client = binance_us_client if us else binance_client
    return client.get_orderbook(symbol, limit) or {"error": "Not found"}

@app.get("/api/binance/candles/{symbol}")
def get_binance_candles(symbol: str, interval: str = "5m", limit: int = 100, us: bool = False):
    client = binance_us_client if us else binance_client
    return client.get_klines(symbol, interval, limit)

@app.get("/api/binance/pairs")
def get_binance_pairs(us: bool = False):
    client = binance_us_client if us else binance_client
    return client.POPULAR_PAIRS

@app.get("/api/binance/status")
def get_binance_status():
    agents = {}
    for aid, a in globals().get("agents", {}).items():
        if hasattr(a, "client") and hasattr(a.client, "exchange"):
            if "binance" in a.client.exchange:
                agents[aid] = a.get_state()
    return agents

"""
    ws_marker = '@app.websocket("/ws")'
    if ws_marker in content:
        content = content.replace(ws_marker, routes + ws_marker)
    else:
        content += routes

    with open(sp, "w", encoding="utf-8") as fh:
        fh.write(content)
    print("Patched api/server.py with Binance routes.")
    return True

if __name__ == "__main__":
    print("Adding Binance + Binance.US support...")
    if patch_server():
        print("Done!")
        print("")
        print("From the dashboard, try:")
        print('  "binance monitor BTC and ETH"')
        print('  "binance us watch SOL"')
        print("")
        print("New endpoints:")
        print("  GET /api/binance/ticker/BTCUSDT")
        print("  GET /api/binance/orderbook/BTCUSDT")
        print("  GET /api/binance/candles/BTCUSDT?interval=5m")
        print("  GET /api/binance/pairs")
''')
print("Created integrate.py")
print("")
print("All done! Now run: python binance_integration\\integrate.py")
