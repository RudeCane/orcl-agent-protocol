"""
BloFin Leverage Agent — Autonomous perpetual futures trader on BloFin.
Uses BloFin's API to trade 200+ pairs with up to 150x leverage.

This agent:
1. Monitors price action on BloFin pairs
2. Uses the same strategy engine as the on-chain leverage agent
3. Opens/closes positions via BloFin API
4. Manages risk with stop-loss, take-profit, and position limits
5. Communicates with other agents via the message bus
"""

import time
import logging
import threading
from typing import Optional, List, Dict
from blofin_integration.client import BloFinTrader

logger = logging.getLogger(__name__)


class BloFinAgent:
    """
    Autonomous BloFin leverage trading agent.
    
    Usage:
        agent = BloFinAgent(
            pairs=["BTC-USDT", "ETH-USDT"],
            api_key="...", api_secret="...", passphrase="...",
            max_leverage=5,
            size_per_trade=0.1,
        )
        agent.start()
    """

    def __init__(
        self,
        pairs: List[str] = None,
        api_key: str = "",
        api_secret: str = "",
        passphrase: str = "",
        max_leverage: int = 5,
        size_per_trade: float = 0.1,
        stop_loss_pct: float = 3.0,
        take_profit_pct: float = 6.0,
        max_positions: int = 3,
        poll_interval: int = 30,
        dry_run: bool = True,
    ):
        self.agent_id = f"blofin_{int(time.time()) % 10000}"
        self.pairs = pairs or ["BTC-USDT", "ETH-USDT"]
        self.max_leverage = max_leverage
        self.size_per_trade = size_per_trade
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.max_positions = max_positions
        self.poll_interval = poll_interval

        # BloFin trader
        self.trader = BloFinTrader(
            api_key=api_key,
            api_secret=api_secret,
            passphrase=passphrase,
            dry_run=dry_run,
        )

        # Price tracking
        self.price_history: Dict[str, List[dict]] = {}
        self.last_prices: Dict[str, float] = {}

        # State
        self.running = False
        self.status = "idle"
        self.cycle_count = 0
        self._thread: Optional[threading.Thread] = None
        self.errors: List[str] = []

        # Communication
        self.comms = None
        try:
            from comms.communicator import AgentCommunicator
            self.comms = AgentCommunicator(
                agent_id=self.agent_id,
                agent_type="blofin_leverage",
                capabilities=["leverage_trade", "perp_trading", "cex_trading"],
            )
            self.comms.on("signal", self._on_signal)
            logger.info(f"[{self.agent_id}] Connected to message bus")
        except ImportError:
            pass

    # ============================================================
    # START / STOP
    # ============================================================

    def start(self):
        if self.running:
            return
        self.running = True
        self.status = "running"
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info(f"[{self.agent_id}] Started — watching {self.pairs} | "
                    f"Dry run: {self.trader.dry_run}")

    def stop(self):
        self.running = False
        self.status = "stopped"

    # ============================================================
    # MAIN LOOP
    # ============================================================

    def _loop(self):
        while self.running:
            try:
                self.status = "scanning"

                for pair in self.pairs:
                    if not self.running:
                        break
                    self._process_pair(pair)

                self.cycle_count += 1
                self.status = "waiting"
                time.sleep(self.poll_interval)

            except Exception as e:
                logger.error(f"[{self.agent_id}] Cycle error: {e}")
                self.errors.append(str(e))
                if len(self.errors) > 50:
                    self.errors = self.errors[-50:]
                time.sleep(10)

    def _process_pair(self, pair):
        """Fetch price → analyze → maybe trade."""
        try:
            ticker = self.trader.get_ticker(pair)
            if not ticker or not ticker.get("last"):
                return

            price = ticker["last"]
            self.last_prices[pair] = price

            # Track history
            if pair not in self.price_history:
                self.price_history[pair] = []
            self.price_history[pair].append({
                "price": price,
                "volume": ticker.get("volume_24h", 0),
                "change_24h": ticker.get("change_24h", 0),
                "timestamp": time.time(),
            })
            self.price_history[pair] = self.price_history[pair][-100:]

            # Need at least 10 data points
            if len(self.price_history[pair]) < 10:
                return

            # Analyze
            signal = self._analyze(pair, ticker)

            if signal:
                self._execute_signal(pair, signal)

        except Exception as e:
            logger.error(f"[{self.agent_id}] Process error for {pair}: {e}")

    def _analyze(self, pair, ticker):
        """Simple trend + momentum analysis."""
        history = self.price_history[pair]
        prices = [h["price"] for h in history]

        if len(prices) < 10:
            return None

        # Moving averages
        short_ma = sum(prices[-5:]) / 5
        long_ma = sum(prices[-20:]) / min(20, len(prices))
        ma_diff_pct = ((short_ma - long_ma) / long_ma) * 100

        # Momentum
        recent_change = ((prices[-1] - prices[-5]) / prices[-5]) * 100

        # RSI
        rsi = self._calc_rsi(prices[-14:]) if len(prices) >= 14 else 50

        # Volatility
        changes = [abs(prices[i] - prices[i-1]) / prices[i-1] * 100
                   for i in range(max(1, len(prices)-10), len(prices))]
        volatility = sum(changes) / len(changes) if changes else 0

        score = 0
        side = None
        reasons = []

        # Trend
        if ma_diff_pct > 2.0:
            score += 20
            side = "long"
            reasons.append(f"Uptrend (MA diff: {ma_diff_pct:.1f}%)")
        elif ma_diff_pct < -2.0:
            score += 20
            side = "short"
            reasons.append(f"Downtrend (MA diff: {ma_diff_pct:.1f}%)")

        # Momentum confirmation
        if side == "long" and recent_change > 1:
            score += 15
            reasons.append(f"Bullish momentum ({recent_change:.1f}%)")
        elif side == "short" and recent_change < -1:
            score += 15
            reasons.append(f"Bearish momentum ({recent_change:.1f}%)")

        # RSI
        if rsi < 30 and side != "short":
            score += 15
            side = "long"
            reasons.append(f"RSI oversold ({rsi:.0f})")
        elif rsi > 70 and side != "long":
            score += 15
            side = "short"
            reasons.append(f"RSI overbought ({rsi:.0f})")

        # Too volatile = skip
        if volatility > 5:
            score -= 20
            reasons.append(f"High volatility ({volatility:.1f}%)")

        if not side or score < 25:
            return None

        confidence = min(score / 50, 1.0)
        if confidence < 0.6:
            return None

        # Scale leverage to confidence
        leverage = min(int(confidence * self.max_leverage) + 1, self.max_leverage)

        return {
            "side": side,
            "leverage": leverage,
            "confidence": round(confidence, 2),
            "reasons": reasons,
            "price": prices[-1],
        }

    def _execute_signal(self, pair, signal):
        """Execute a trading signal on BloFin."""
        # Check position limit
        positions = self.trader.get_positions()
        open_count = 0
        already_has = False
        for p in positions:
            if isinstance(p, dict) and float(p.get("positions", p.get("pos", 0))) != 0:
                open_count += 1
                if p.get("instId") == pair:
                    already_has = True

        if already_has:
            return  # Don't double up

        if open_count >= self.max_positions:
            logger.info(f"[{self.agent_id}] Max positions reached ({open_count})")
            return

        # Execute
        if signal["side"] == "long":
            result = self.trader.open_long(
                inst_id=pair,
                size=self.size_per_trade,
                leverage=signal["leverage"],
                stop_loss_pct=self.stop_loss_pct,
                take_profit_pct=self.take_profit_pct,
            )
        else:
            result = self.trader.open_short(
                inst_id=pair,
                size=self.size_per_trade,
                leverage=signal["leverage"],
                stop_loss_pct=self.stop_loss_pct,
                take_profit_pct=self.take_profit_pct,
            )

        # Broadcast to other agents
        if self.comms:
            self.comms.broadcast_signal(
                "buy_opportunity" if signal["side"] == "long" else "sell_signal",
                pair,
                {
                    "symbol": pair,
                    "side": signal["side"],
                    "leverage": signal["leverage"],
                    "confidence": signal["confidence"],
                    "reasons": signal["reasons"],
                    "source": "blofin_agent",
                    "exchange": "blofin",
                },
            )

    def _on_signal(self, message):
        """Handle signals from other agents."""
        content = message.content
        confidence = content.get("confidence", 0)
        if confidence < 0.85:
            return
        logger.info(f"[{self.agent_id}] Received signal: {content.get('signal_type')} "
                    f"conf={confidence}")

    def _calc_rsi(self, prices):
        gains, losses = [], []
        for i in range(1, len(prices)):
            diff = prices[i] - prices[i-1]
            gains.append(max(diff, 0))
            losses.append(max(-diff, 0))
        avg_gain = sum(gains) / len(gains) if gains else 0
        avg_loss = sum(losses) / len(losses) if losses else 0
        if avg_loss == 0:
            return 100
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    # ============================================================
    # STATUS
    # ============================================================

    def get_state(self):
        trader_status = self.trader.get_status()
        return {
            "agent_id": self.agent_id,
            "agent_type": "blofin_leverage",
            "status": self.status,
            "running": self.running,
            "exchange": "BloFin",
            "pairs": self.pairs,
            "cycle_count": self.cycle_count,
            "connected": self.trader.connected,
            "dry_run": self.trader.dry_run,
            "max_leverage": self.max_leverage,
            "size_per_trade": self.size_per_trade,
            "positions": trader_status["open_positions"],
            "position_count": trader_status["position_count"],
            "last_prices": self.last_prices,
            "recent_trades": trader_status["recent_trades"][-10:],
            "errors": self.errors[-5:],
        }
