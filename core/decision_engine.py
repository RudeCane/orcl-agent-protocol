"""Decision Engine — Technical analysis + trade signals."""
import logging
from enum import Enum
from typing import List, Optional
from dataclasses import dataclass
from core.observer import TokenSnapshot
from config import config

logger = logging.getLogger(__name__)

class Signal(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    ADD_LIQUIDITY = "ADD_LIQUIDITY"
    REMOVE_LIQUIDITY = "REMOVE_LIQUIDITY"
    DANGER = "DANGER"

@dataclass
class Decision:
    signal: Signal
    confidence: float
    reason: str
    token_address: str
    price: float
    suggested_amount_usd: float = 0.0

class DecisionEngine:
    def __init__(self):
        self.cfg = config.strategy
        self.safety = config.safety

    def analyze(self, snapshot: TokenSnapshot, price_history: List[float]) -> Decision:
        # Safety check first
        if snapshot.liquidity_usd < self.safety.min_liquidity_usd:
            return Decision(Signal.DANGER, 0.9,
                f"Liquidity too low: ${snapshot.liquidity_usd:,.0f}",
                snapshot.token_address, snapshot.price_usd)

        if self.safety.require_whitelist:
            wl = [t.lower() for t in self.safety.whitelisted_tokens]
            if snapshot.token_address.lower() not in wl:
                return Decision(Signal.HOLD, 1.0, "Not in whitelist",
                    snapshot.token_address, snapshot.price_usd)

        signals = []
        s = self._sma_crossover(price_history)
        if s: signals.append(s)
        s = self._rsi_check(price_history)
        if s: signals.append(s)
        s = self._momentum_check(snapshot)
        if s: signals.append(s)
        s = self._liquidity_check(snapshot)
        if s: signals.append(s)

        return self._aggregate(signals, snapshot)

    def _sma_crossover(self, prices: List[float]) -> Optional[tuple]:
        if len(prices) < self.cfg.long_window:
            return None
        short_sma = sum(prices[-self.cfg.short_window:]) / self.cfg.short_window
        long_sma = sum(prices[-self.cfg.long_window:]) / self.cfg.long_window
        if short_sma > long_sma * 1.01:
            return (Signal.BUY, 0.6, "SMA crossover bullish")
        elif short_sma < long_sma * 0.99:
            return (Signal.SELL, 0.6, "SMA crossover bearish")
        return (Signal.HOLD, 0.3, "SMA neutral")

    def _rsi_check(self, prices: List[float]) -> Optional[tuple]:
        period = self.cfg.rsi_period
        if len(prices) < period + 1:
            return None
        deltas = [prices[i] - prices[i-1] for i in range(-period, 0)]
        gains = [d for d in deltas if d > 0]
        losses = [-d for d in deltas if d < 0]
        avg_gain = sum(gains) / period if gains else 0.0001
        avg_loss = sum(losses) / period if losses else 0.0001
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        if rsi < self.cfg.rsi_oversold:
            return (Signal.BUY, 0.7, f"RSI oversold ({rsi:.1f})")
        elif rsi > self.cfg.rsi_overbought:
            return (Signal.SELL, 0.7, f"RSI overbought ({rsi:.1f})")
        return (Signal.HOLD, 0.2, f"RSI neutral ({rsi:.1f})")

    def _momentum_check(self, snapshot: TokenSnapshot) -> Optional[tuple]:
        if snapshot.price_change_1h > 5.0:
            return (Signal.SELL, 0.5, f"1h pump +{snapshot.price_change_1h:.1f}%")
        elif snapshot.price_change_1h < -5.0:
            return (Signal.BUY, 0.4, f"1h dip {snapshot.price_change_1h:.1f}%")
        return None

    def _liquidity_check(self, snapshot: TokenSnapshot) -> Optional[tuple]:
        if snapshot.liquidity_usd < self.cfg.low_liquidity_usd:
            return (Signal.ADD_LIQUIDITY, 0.5, f"Low liq: ${snapshot.liquidity_usd:,.0f}")
        elif snapshot.liquidity_usd > self.cfg.high_liquidity_usd:
            return (Signal.REMOVE_LIQUIDITY, 0.4, f"High liq: ${snapshot.liquidity_usd:,.0f}")
        return None

    def _aggregate(self, signals: list, snapshot: TokenSnapshot) -> Decision:
        if not signals:
            return Decision(Signal.HOLD, 0.5, "Insufficient data",
                snapshot.token_address, snapshot.price_usd)

        buy_score = sum(c for s, c, _ in signals if s == Signal.BUY)
        sell_score = sum(c for s, c, _ in signals if s == Signal.SELL)
        reasons = " | ".join(r for _, _, r in signals)

        if buy_score > sell_score and buy_score > 0.5:
            return Decision(Signal.BUY, min(buy_score / len(signals), 1.0), reasons,
                snapshot.token_address, snapshot.price_usd,
                min(self.safety.max_trade_size_usd * buy_score / 2, self.safety.max_trade_size_usd))
        elif sell_score > buy_score and sell_score > 0.5:
            return Decision(Signal.SELL, min(sell_score / len(signals), 1.0), reasons,
                snapshot.token_address, snapshot.price_usd)
        return Decision(Signal.HOLD, 0.5, reasons, snapshot.token_address, snapshot.price_usd)
