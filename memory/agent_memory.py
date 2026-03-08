"""Agent Memory — Stores decisions, outcomes, learns from history."""
import json
import time
import logging
from pathlib import Path
from typing import List, Dict
from collections import defaultdict

logger = logging.getLogger(__name__)
MEMORY_FILE = Path("data/agent_memory.json")

class AgentMemory:
    def __init__(self):
        self.decisions: List[Dict] = []
        self.market_snapshots: List[Dict] = []
        self.performance: Dict[str, float] = defaultdict(float)
        self._load()

    def record_decision(self, agent_id: str, decision: dict, result: dict):
        entry = {"timestamp": time.time(), "agent_id": agent_id,
                 "decision": decision, "result": result}
        self.decisions.append(entry)
        self.performance[f"{agent_id}_total"] += 1
        if result.get("success"):
            self.performance[f"{agent_id}_success"] += 1
        self._save()

    def record_snapshot(self, token_address: str, data: dict):
        self.market_snapshots.append({
            "timestamp": time.time(), "token": token_address, "data": data})
        if len(self.market_snapshots) > 10000:
            self.market_snapshots = self.market_snapshots[-10000:]

    def get_recent_decisions(self, agent_id: str, limit: int = 20) -> List[Dict]:
        return [d for d in self.decisions if d["agent_id"] == agent_id][-limit:]

    def get_win_rate(self, agent_id: str) -> float:
        total = self.performance.get(f"{agent_id}_total", 0)
        if total == 0: return 0.0
        return self.performance.get(f"{agent_id}_success", 0) / total

    def get_all_stats(self) -> Dict:
        return {
            "total_decisions": len(self.decisions),
            "total_snapshots": len(self.market_snapshots),
            "performance": dict(self.performance),
            "recent_decisions": self.decisions[-10:],
        }

    def _save(self):
        try:
            MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
            MEMORY_FILE.write_text(json.dumps({
                "decisions": self.decisions[-5000:],
                "snapshots": self.market_snapshots[-5000:],
                "performance": dict(self.performance),
            }, indent=2))
        except Exception as e:
            logger.error(f"Save error: {e}")

    def _load(self):
        try:
            if MEMORY_FILE.exists():
                data = json.loads(MEMORY_FILE.read_text())
                self.decisions = data.get("decisions", [])
                self.market_snapshots = data.get("snapshots", [])
                self.performance = defaultdict(float, data.get("performance", {}))
        except Exception as e:
            logger.error(f"Load error: {e}")

memory = AgentMemory()
