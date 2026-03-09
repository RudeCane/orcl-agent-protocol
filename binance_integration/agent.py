import time, logging, threading
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
