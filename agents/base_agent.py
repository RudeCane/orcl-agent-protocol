"""Base Agent — Autonomous observe/decide/execute loop."""
import time
import logging
import threading
from typing import Optional, List
from core.observer import Observer, TokenSnapshot
from core.decision_engine import DecisionEngine, Decision
from core.executor import Executor, ExecutionResult
from memory.agent_memory import memory
from comms.communicator import AgentCommunicator

logger = logging.getLogger(__name__)

class BaseAgent:
    def __init__(self, agent_id: str, tokens: List[str], poll_interval: int = 15):
        self.agent_id = agent_id
        self.tokens = tokens
        self.poll_interval = poll_interval
        self.observer = Observer()
        self.engine = DecisionEngine()
        self.executor = Executor()
        self.running = False
        self._thread: Optional[threading.Thread] = None
        self.status = "idle"
        self.last_snapshot: Optional[TokenSnapshot] = None
        self.last_decision: Optional[Decision] = None
        self.last_result: Optional[ExecutionResult] = None
        self.cycle_count = 0
        self.errors: List[str] = []
        self.comms = AgentCommunicator(
            agent_id=self.agent_id,
            agent_type=self.agent_id.replace('_agent', ''),
            capabilities=['market_scan', 'price_track', 'execute_trade']
        )

    def start(self):
        if self.running: return
        self.running = True
        self.status = "running"
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info(f"Agent {self.agent_id} started — watching {len(self.tokens)} tokens")

    def stop(self):
        self.running = False
        self.status = "stopped"

    def _loop(self):
        while self.running:
            try:
                self.status = "observing"
                for token in self.tokens:
                    if not self.running: break
                    self._process_token(token)
                self.cycle_count += 1
                self.status = "waiting"
                time.sleep(self.poll_interval)
            except Exception as e:
                self.errors.append(str(e))
                if len(self.errors) > 100:
                    self.errors = self.errors[-100:]
                time.sleep(5)

    def _process_token(self, token_address: str):
        snapshot = self.observer.get_token_data(token_address)
        if not snapshot: return
        self.last_snapshot = snapshot
        memory.record_snapshot(token_address, {
            "price": snapshot.price_usd,
            "liquidity": snapshot.liquidity_usd,
            "volume": snapshot.volume_24h,
        })

        self.status = "analyzing"
        price_history = self.observer.get_price_history(token_address)
        decision = self.engine.analyze(snapshot, price_history)
        self.last_decision = decision
        logger.info(f"[{self.agent_id}] {snapshot.symbol}: ${snapshot.price_usd:.6f} -> "
                     f"{decision.signal.value} (conf:{decision.confidence:.2f})")

        self.status = "executing"
        result = self.executor.execute(decision)
        self.last_result = result

        self._broadcast_signals(snapshot, decision)
        memory.record_decision(self.agent_id,
            {"signal": decision.signal.value, "confidence": decision.confidence,
             "reason": decision.reason, "price": decision.price},
            {"success": result.success, "action": result.action, "error": result.error})

    def get_state(self) -> dict:
        return {
            "agent_id": self.agent_id, "status": self.status,
            "running": self.running, "tokens": self.tokens,
            "cycle_count": self.cycle_count,
            "win_rate": memory.get_win_rate(self.agent_id),
            "last_snapshot": {
                "symbol": self.last_snapshot.symbol,
                "price": self.last_snapshot.price_usd,
                "liquidity": self.last_snapshot.liquidity_usd,
                "volume_24h": self.last_snapshot.volume_24h,
                "change_1h": self.last_snapshot.price_change_1h,
            } if self.last_snapshot else None,
            "last_decision": {
                "signal": self.last_decision.signal.value,
                "confidence": self.last_decision.confidence,
                "reason": self.last_decision.reason,
            } if self.last_decision else None,
            "last_result": {
                "success": self.last_result.success,
                "action": self.last_result.action,
                "dry_run": self.last_result.dry_run,
                "error": self.last_result.error,
            } if self.last_result else None,
            "recent_errors": self.errors[-5:],
        }
