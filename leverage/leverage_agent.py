"""
Leverage Agent — Autonomous Perpetual Futures Trader
Watches market data, identifies high-confidence setups, and opens leveraged positions.

This agent:
1. Receives market data from the observer
2. Runs its own leverage-specific analysis (trend + momentum + volume)
3. Opens positions with strict risk management
4. Monitors and auto-closes positions (stop-loss, take-profit)
5. Communicates with other agents via the message bus
"""

import time
import logging
import threading
from typing import Optional, List, Dict
from leverage.trading_engine import LeverageTradingEngine, LeverageSafetyConfig, PositionSide

logger = logging.getLogger(__name__)


class LeverageStrategy:
    """
    Determines WHEN and HOW to enter leveraged trades.
    Uses trend confirmation + momentum + volume analysis.
    """

    def __init__(self):
        self.min_trend_strength = 3.0    # Min % move to confirm trend
        self.min_volume_ratio = 0.5      # Min volume/liquidity ratio
        self.min_confidence = 0.65       # Don't trade below this
        self.rsi_oversold = 30
        self.rsi_overbought = 70

    def evaluate(self, snapshot, price_history, indicators=None):
        """
        Analyze market data and return a trade signal if conditions are met.
        Returns None if no trade, or a dict with trade params.
        """
        if not snapshot or not price_history or len(price_history) < 5:
            return None

        price = snapshot.get("price_usd") or snapshot.get("price", 0)
        change_1h = snapshot.get("price_change_1h") or snapshot.get("change_1h", 0)
        change_24h = snapshot.get("price_change_24h") or snapshot.get("change_24h", 0)
        volume = snapshot.get("volume_24h") or snapshot.get("volume", 0)
        liquidity = snapshot.get("liquidity_usd") or snapshot.get("liquidity", 0)

        if not price or price <= 0:
            return None

        # ── Score the setup ──
        score = 0
        reasons = []
        side = None

        # Trend analysis from price history
        prices = [p.get("price", p.get("price_usd", 0)) for p in price_history[-20:] if p]
        prices = [p for p in prices if p > 0]

        if len(prices) >= 5:
            short_ma = sum(prices[-5:]) / 5
            long_ma = sum(prices) / len(prices)
            ma_diff_pct = ((short_ma - long_ma) / long_ma) * 100

            if ma_diff_pct > self.min_trend_strength:
                score += 20
                side = "long"
                reasons.append(f"Uptrend confirmed (MA diff: {ma_diff_pct:.1f}%)")
            elif ma_diff_pct < -self.min_trend_strength:
                score += 20
                side = "short"
                reasons.append(f"Downtrend confirmed (MA diff: {ma_diff_pct:.1f}%)")

        # Momentum from 1h change
        if change_1h:
            if change_1h > 3 and side == "long":
                score += 15
                reasons.append(f"Strong 1h momentum ({change_1h:.1f}%)")
            elif change_1h < -3 and side == "short":
                score += 15
                reasons.append(f"Strong 1h sell pressure ({change_1h:.1f}%)")
            elif abs(change_1h) > 8:
                score -= 10  # Too volatile, might be a spike
                reasons.append(f"Excessive 1h move ({change_1h:.1f}%) — caution")

        # Volume confirmation
        if volume and liquidity and liquidity > 0:
            vol_ratio = volume / liquidity
            if vol_ratio > self.min_volume_ratio:
                score += 10
                reasons.append(f"Volume confirms (vol/liq: {vol_ratio:.2f}x)")
            else:
                score -= 5
                reasons.append(f"Low volume (vol/liq: {vol_ratio:.2f}x)")

        # Liquidity check — don't trade illiquid markets
        if liquidity and liquidity < 50000:
            score -= 30
            reasons.append(f"Insufficient liquidity (${liquidity:,.0f})")

        # RSI approximation from recent prices
        if len(prices) >= 14:
            rsi = self._calc_rsi(prices[-14:])
            if rsi < self.rsi_oversold and side != "short":
                score += 15
                side = "long"
                reasons.append(f"RSI oversold ({rsi:.0f})")
            elif rsi > self.rsi_overbought and side != "long":
                score += 15
                side = "short"
                reasons.append(f"RSI overbought ({rsi:.0f})")

        # ── DECIDE ──
        if not side or score < 25:
            return None

        confidence = min(score / 60, 1.0)

        if confidence < self.min_confidence:
            return None

        # Calculate leverage based on confidence (higher confidence = more leverage)
        if confidence >= 0.9:
            leverage = 5.0
        elif confidence >= 0.8:
            leverage = 4.0
        elif confidence >= 0.7:
            leverage = 3.0
        else:
            leverage = 2.0

        # Stop-loss based on volatility
        if len(prices) >= 5:
            recent_changes = [abs(prices[i] - prices[i-1]) / prices[i-1] * 100
                            for i in range(1, min(6, len(prices)))]
            avg_volatility = sum(recent_changes) / len(recent_changes) if recent_changes else 2.0
            stop_loss_pct = max(avg_volatility * 2, 3.0)  # At least 3%
            stop_loss_pct = min(stop_loss_pct, 10.0)       # At most 10%
        else:
            stop_loss_pct = 5.0

        return {
            "side": side,
            "leverage": leverage,
            "confidence": round(confidence, 2),
            "stop_loss_pct": round(stop_loss_pct, 1),
            "take_profit_pct": round(stop_loss_pct * 2, 1),  # 2:1 reward/risk
            "reasons": reasons,
            "entry_price": price,
        }

    def _calc_rsi(self, prices):
        """Simple RSI calculation."""
        gains, losses = [], []
        for i in range(1, len(prices)):
            diff = prices[i] - prices[i-1]
            if diff > 0:
                gains.append(diff)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(diff))

        avg_gain = sum(gains) / len(gains) if gains else 0
        avg_loss = sum(losses) / len(losses) if losses else 0

        if avg_loss == 0:
            return 100
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))


class LeverageAgent:
    """
    Autonomous leverage trading agent.
    
    Usage:
        agent = LeverageAgent(
            tokens=["0x4200..."],  # Tokens to trade
            collateral_per_trade=20.0,  # $20 USDC per trade
        )
        agent.start()
    """

    def __init__(
        self,
        tokens: List[str],
        collateral_per_trade: float = 20.0,
        poll_interval: int = 30,
        safety_config: Optional[LeverageSafetyConfig] = None,
    ):
        self.agent_id = f"leverage_{int(time.time()) % 10000}"
        self.tokens = tokens
        self.collateral_per_trade = collateral_per_trade
        self.poll_interval = poll_interval

        # Core components
        self.engine = LeverageTradingEngine(safety_config)
        self.strategy = LeverageStrategy()

        # State
        self.running = False
        self.status = "idle"
        self.cycle_count = 0
        self._thread: Optional[threading.Thread] = None
        self.errors: List[str] = []

        # Price history tracking
        self.price_history: Dict[str, List[dict]] = {}

        # Communication (optional — connect if comms module exists)
        self.comms = None
        try:
            from comms.communicator import AgentCommunicator
            self.comms = AgentCommunicator(
                agent_id=self.agent_id,
                agent_type="leverage",
                capabilities=["leverage_trade", "perp_trading", "execute_trade"],
            )
            # Listen for signals from other agents
            self.comms.on("signal", self._on_signal)
            logger.info(f"[{self.agent_id}] Connected to message bus")
        except ImportError:
            logger.info(f"[{self.agent_id}] Running without comms (comms module not found)")

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
        logger.info(f"[{self.agent_id}] Started — watching {len(self.tokens)} tokens | "
                    f"Dry run: {self.engine.safety.dry_run}")

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

                for token in self.tokens:
                    if not self.running:
                        break
                    self._process_token(token)

                # Update existing positions with latest prices
                self._update_positions()

                self.cycle_count += 1
                self.status = "waiting"
                time.sleep(self.poll_interval)

            except Exception as e:
                logger.error(f"[{self.agent_id}] Cycle error: {e}")
                self.errors.append(str(e))
                if len(self.errors) > 50:
                    self.errors = self.errors[-50:]
                time.sleep(10)

    def _process_token(self, token):
        """Observe → Analyze → Maybe open a position."""
        try:
            # Import observer
            from core.observer import Observer
            observer = Observer()
            snapshot = observer.get_token_data(token)

            if not snapshot:
                return

            # Convert snapshot to dict
            snap_dict = {
                "price_usd": snapshot.price_usd,
                "price_change_1h": snapshot.price_change_1h,
                "price_change_24h": getattr(snapshot, 'price_change_24h', 0),
                "volume_24h": snapshot.volume_24h,
                "liquidity_usd": snapshot.liquidity_usd,
                "symbol": snapshot.symbol,
            }

            # Track price history
            if token not in self.price_history:
                self.price_history[token] = []
            self.price_history[token].append({
                "price": snapshot.price_usd,
                "price_usd": snapshot.price_usd,
                "timestamp": time.time(),
            })
            # Keep last 100 snapshots
            self.price_history[token] = self.price_history[token][-100:]

            # Run leverage strategy
            signal = self.strategy.evaluate(snap_dict, self.price_history[token])

            if signal:
                logger.info(f"[{self.agent_id}] Signal: {signal['side'].upper()} "
                          f"{snapshot.symbol} @ ${snapshot.price_usd:.4f} "
                          f"(conf: {signal['confidence']}, lev: {signal['leverage']}x)")

                # Open the position
                result = self.engine.open_position(
                    token=token,
                    symbol=snapshot.symbol,
                    side=signal["side"],
                    leverage=signal["leverage"],
                    collateral_usd=self.collateral_per_trade,
                    entry_price=snapshot.price_usd,
                    stop_loss_pct=signal["stop_loss_pct"],
                    take_profit_pct=signal["take_profit_pct"],
                )

                # Broadcast to other agents
                if self.comms and result["status"] == "opened":
                    self.comms.broadcast_signal(
                        "buy_opportunity" if signal["side"] == "long" else "sell_signal",
                        token,
                        {
                            "symbol": snapshot.symbol,
                            "side": signal["side"],
                            "leverage": signal["leverage"],
                            "confidence": signal["confidence"],
                            "reasons": signal["reasons"],
                            "source": "leverage_agent",
                        },
                    )

        except Exception as e:
            logger.error(f"[{self.agent_id}] Process error for {token[:10]}: {e}")

    def _update_positions(self):
        """Update all open positions with latest prices."""
        price_updates = {}
        for token, history in self.price_history.items():
            if history:
                price_updates[token] = history[-1]["price"]

        if price_updates:
            actions = self.engine.update_positions(price_updates)
            for action in actions:
                if self.comms:
                    pos = action.get("position", {})
                    self.comms.broadcast_signal(
                        "sell_signal" if action.get("pnl", 0) < 0 else "buy_opportunity",
                        pos.get("token", ""),
                        {
                            "event": f"position_{action.get('reason', 'closed')}",
                            "pnl": action.get("pnl", 0),
                            "symbol": pos.get("symbol", ""),
                            "source": "leverage_agent",
                        },
                    )

    # ============================================================
    # SIGNAL HANDLER — React to other agents' signals
    # ============================================================

    def _on_signal(self, message):
        """Handle signals from other agents."""
        content = message.content
        signal_type = content.get("signal_type", "")
        token = content.get("token", "")
        confidence = content.get("confidence", 0)

        # Only act on high-confidence signals from other agents
        if confidence < 0.8:
            return

        logger.info(f"[{self.agent_id}] Received signal: {signal_type} for {token[:10]}...")

        # If another agent detected a crash, consider shorting
        if signal_type == "price_crash" and token in self.tokens:
            # Check if we already have a position
            has_position = any(
                p.token == token for p in self.engine.positions.values()
            )
            if not has_position:
                logger.info(f"[{self.agent_id}] Acting on crash signal — evaluating short")

    # ============================================================
    # STATUS
    # ============================================================

    def get_state(self):
        """Full agent state for API/dashboard."""
        engine_status = self.engine.get_status()
        return {
            "agent_id": self.agent_id,
            "agent_type": "leverage",
            "status": self.status,
            "running": self.running,
            "tokens": self.tokens,
            "cycle_count": self.cycle_count,
            "collateral_per_trade": self.collateral_per_trade,
            "positions": engine_status["open_positions"],
            "position_count": engine_status["position_count"],
            "unrealized_pnl": engine_status["total_unrealized_pnl"],
            "daily_pnl": engine_status["daily_pnl"],
            "total_realized_pnl": engine_status["total_realized_pnl"],
            "win_rate": engine_status["win_rate"],
            "safety": engine_status["safety"],
            "recent_trades": engine_status["recent_trades"][-10:],
            "errors": self.errors[-5:],
        }
