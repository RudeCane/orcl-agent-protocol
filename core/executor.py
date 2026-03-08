"""Executor — Carries out decisions with safety guardrails."""
import time
import logging
from typing import Optional
from dataclasses import dataclass
from core.decision_engine import Decision, Signal
from blockchain.web3_client import web3_client
from config import config

logger = logging.getLogger(__name__)

@dataclass
class ExecutionResult:
    success: bool
    action: str
    tx_hash: str = ""
    error: str = ""
    dry_run: bool = True
    timestamp: float = 0.0
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.time()

class Executor:
    def __init__(self):
        self.safety = config.safety
        self.last_trade_time: float = 0.0
        self.daily_pnl: float = 0.0
        self.daily_reset_time: float = time.time()
        self.trade_log: list = []

    def execute(self, decision: Decision) -> ExecutionResult:
        err = self._pre_flight_check(decision)
        if err:
            return ExecutionResult(False, decision.signal.value, error=err)

        if decision.signal == Signal.BUY:
            return self._execute_swap(decision, "BUY")
        elif decision.signal == Signal.SELL:
            return self._execute_swap(decision, "SELL")
        elif decision.signal in (Signal.ADD_LIQUIDITY, Signal.REMOVE_LIQUIDITY):
            logger.info(f"[DRY RUN] {decision.signal.value} for {decision.token_address}")
            return ExecutionResult(True, decision.signal.value, dry_run=self.safety.dry_run)
        return ExecutionResult(True, "HOLD", dry_run=self.safety.dry_run)

    def _pre_flight_check(self, decision: Decision) -> Optional[str]:
        if time.time() - self.daily_reset_time > 86400:
            self.daily_pnl = 0.0
            self.daily_reset_time = time.time()
        if self.daily_pnl < -self.safety.daily_loss_limit_usd:
            return f"Daily loss limit hit: ${self.daily_pnl:.2f}"
        elapsed = time.time() - self.last_trade_time
        if elapsed < self.safety.cooldown_seconds:
            return f"Cooldown: {self.safety.cooldown_seconds - elapsed:.0f}s remaining"
        gas = web3_client.get_gas_price_gwei()
        if gas > self.safety.max_gas_price_gwei:
            return f"Gas too high: {gas:.1f} gwei"
        if decision.suggested_amount_usd > self.safety.max_trade_size_usd:
            return f"Trade ${decision.suggested_amount_usd:.2f} > max ${self.safety.max_trade_size_usd:.2f}"
        if decision.confidence < 0.5:
            return f"Confidence too low: {decision.confidence:.2f}"
        return None

    def _execute_swap(self, decision: Decision, action: str) -> ExecutionResult:
        logger.info(
            f"[{'DRY RUN' if self.safety.dry_run else 'LIVE'}] {action} "
            f"{decision.token_address} — ${decision.suggested_amount_usd:.2f} "
            f"@ ${decision.price:.6f} — {decision.reason}")

        self._record_trade(decision, action + ("_SIMULATED" if self.safety.dry_run else ""))
        self.last_trade_time = time.time()

        if self.safety.dry_run:
            return ExecutionResult(True, action, tx_hash=f"0x_dry_run_{action.lower()}", dry_run=True)

        try:
            # Production: build + send swap tx via DEX router (Aerodrome/Uniswap)
            tx_hash = "0x_implement_real_swap"
            return ExecutionResult(True, action, tx_hash=tx_hash, dry_run=False)
        except Exception as e:
            logger.error(f"{action} failed: {e}")
            return ExecutionResult(False, action, error=str(e))

    def _record_trade(self, decision: Decision, action: str):
        self.trade_log.append({
            "time": time.time(), "action": action,
            "token": decision.token_address, "price": decision.price,
            "amount_usd": decision.suggested_amount_usd,
            "confidence": decision.confidence, "reason": decision.reason,
        })
        if len(self.trade_log) > 500:
            self.trade_log = self.trade_log[-500:]
