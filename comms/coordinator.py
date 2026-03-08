"""
Agent Coordinator — Multi-Agent Orchestration
Manages collaboration: signal routing, task delegation, consensus decisions.

This is what makes agents work TOGETHER instead of independently.
"""

import time
import threading
from collections import defaultdict
from typing import Dict, List, Optional
from comms.message_bus import message_bus
from comms.protocol import (
    AgentMessage, MessageType, Priority, SignalType,
    signal_message, task_delegate_message, vote_request_message,
)


class AgentCoordinator:
    """
    The coordinator sits above the message bus and implements higher-level
    collaboration patterns:
    
    1. SIGNAL ROUTING — Market agent spots opportunity → routes to best agent to act
    2. TASK DELEGATION — Break complex tasks into subtasks for different agents  
    3. CONSENSUS — Multiple agents vote before executing high-value trades
    4. CONFLICT RESOLUTION — When agents disagree, coordinator breaks the tie
    5. LOAD BALANCING — Distribute work across agents evenly
    """

    def __init__(self):
        self.bus = message_bus
        self.active_workflows: Dict[str, dict] = {}
        self.signal_rules: List[dict] = []
        self.collaboration_log: List[dict] = []
        self._setup_default_rules()

    # ============================================================
    # SIGNAL ROUTING — Auto-route signals to the right agent
    # ============================================================

    def _setup_default_rules(self):
        """Default rules for routing signals between agents."""
        self.signal_rules = [
            {
                "signal": SignalType.BUY_OPPORTUNITY,
                "route_to_capability": "execute_trade",
                "require_consensus": False,
                "min_confidence": 0.7,
            },
            {
                "signal": SignalType.SELL_SIGNAL,
                "route_to_capability": "execute_trade",
                "require_consensus": False,
                "min_confidence": 0.7,
            },
            {
                "signal": SignalType.LIQUIDITY_LOW,
                "route_to_capability": "manage_liquidity",
                "require_consensus": False,
                "min_confidence": 0.5,
            },
            {
                "signal": SignalType.PRICE_CRASH,
                "route_to_capability": "risk_management",
                "require_consensus": True,  # Multiple agents must agree before acting
                "min_confidence": 0.6,
            },
            {
                "signal": SignalType.WHALE_MOVEMENT,
                "route_to_capability": "market_scan",
                "require_consensus": False,
                "min_confidence": 0.5,
            },
        ]

    def handle_signal(self, message: AgentMessage):
        """
        Process a signal and route it according to rules.
        This is the main entry point for agent collaboration.
        """
        signal_type = message.content.get("signal_type", "")
        confidence = message.content.get("confidence", 0)

        # Find matching rule
        rule = None
        for r in self.signal_rules:
            if r["signal"].value == signal_type:
                rule = r
                break

        if not rule:
            self._log("No routing rule for signal: " + signal_type, "info")
            return {"status": "no_rule", "signal": signal_type}

        # Check confidence threshold
        if confidence < rule["min_confidence"]:
            self._log(f"Signal {signal_type} below confidence threshold ({confidence} < {rule['min_confidence']})", "skip")
            return {"status": "low_confidence", "confidence": confidence}

        # Find agents with the required capability
        capable_agents = self.bus.find_agent_by_capability(rule["route_to_capability"])

        if not capable_agents:
            self._log(f"No agents with capability: {rule['route_to_capability']}", "warn")
            return {"status": "no_capable_agent", "capability": rule["route_to_capability"]}

        # Route based on whether consensus is required
        if rule["require_consensus"]:
            return self._start_consensus_workflow(message, capable_agents)
        else:
            return self._delegate_to_best_agent(message, capable_agents)

    def _delegate_to_best_agent(self, signal_msg, capable_agents):
        """Pick the best agent and delegate the task."""
        # Simple strategy: pick the agent with fewest messages (least busy)
        best = min(capable_agents,
                  key=lambda a: self.bus.agents.get(a, {}).get("messages_received", 0))

        task_msg = task_delegate_message(
            sender_id="coordinator",
            receiver_id=best,
            task=f"act_on_{signal_msg.content.get('signal_type', 'signal')}",
            params={
                "original_signal": signal_msg.to_dict(),
                "token": signal_msg.content.get("token"),
                "delegated_at": time.time(),
            },
        )

        result = self.bus.publish(task_msg)

        self._log(f"Delegated {signal_msg.content.get('signal_type')} to {best}", "delegate")

        return {
            "status": "delegated",
            "agent": best,
            "task_id": task_msg.msg_id,
            **result,
        }

    # ============================================================
    # CONSENSUS — Multiple agents vote before acting
    # ============================================================

    def _start_consensus_workflow(self, signal_msg, voters):
        """Start a vote among agents before executing."""
        signal_type = signal_msg.content.get("signal_type", "unknown")
        token = signal_msg.content.get("token", "unknown")

        proposal = f"Execute {signal_type} on {token[:10]}...?"

        vote_msg = vote_request_message(
            sender_id="coordinator",
            proposal=proposal,
            options=["approve", "reject", "abstain"],
            deadline_seconds=15,
        )

        # Track the workflow
        workflow_id = vote_msg.msg_id
        self.active_workflows[workflow_id] = {
            "type": "consensus",
            "signal": signal_msg.to_dict(),
            "vote_id": workflow_id,
            "voters": voters,
            "started_at": time.time(),
            "status": "voting",
            "result": None,
        }

        # Start the vote
        self.bus.start_vote(vote_msg)

        # Schedule result check
        threading.Timer(16, self._resolve_vote, args=[workflow_id]).start()

        self._log(f"Consensus vote started: {proposal} ({len(voters)} voters)", "vote")

        return {
            "status": "voting",
            "workflow_id": workflow_id,
            "voters": voters,
            "deadline": vote_msg.content["deadline"],
        }

    def _resolve_vote(self, workflow_id):
        """Check vote results and act accordingly."""
        if workflow_id not in self.active_workflows:
            return

        workflow = self.active_workflows[workflow_id]
        vote_result = self.bus.get_vote_result(workflow["vote_id"])

        if not vote_result:
            workflow["status"] = "failed"
            self._log(f"Vote {workflow_id} failed — no results", "error")
            return

        votes = vote_result.get("votes", {})
        approvals = votes.get("approve", 0)
        rejections = votes.get("reject", 0)
        total = vote_result["total_votes"]

        if total == 0:
            workflow["status"] = "no_votes"
            self._log(f"Vote {workflow_id} — no agents voted", "warn")
            return

        approval_rate = approvals / total

        if approval_rate > 0.5:
            workflow["status"] = "approved"
            workflow["result"] = vote_result

            # Execute the original signal
            signal = AgentMessage.from_dict(workflow["signal"])
            capable = self.bus.find_agent_by_capability("execute_trade")
            if capable:
                self._delegate_to_best_agent(signal, capable)
                self._log(f"Consensus APPROVED ({approvals}/{total}) — executing", "success")
            else:
                self._log(f"Consensus approved but no executor available", "warn")
        else:
            workflow["status"] = "rejected"
            workflow["result"] = vote_result
            self._log(f"Consensus REJECTED ({rejections}/{total}) — no action", "reject")

    # ============================================================
    # COMPLEX WORKFLOWS — Multi-step agent collaboration
    # ============================================================

    def run_analysis_workflow(self, token, requester_id="dashboard"):
        """
        Multi-agent analysis: multiple agents analyze the same token,
        then coordinator synthesizes their findings.
        """
        workflow_id = f"analysis_{int(time.time())}"

        self.active_workflows[workflow_id] = {
            "type": "analysis",
            "token": token,
            "requester": requester_id,
            "started_at": time.time(),
            "status": "collecting",
            "responses": {},
        }

        # Ask all market-capable agents to analyze
        analysts = self.bus.find_agent_by_capability("market_scan")
        analysts += self.bus.find_agent_by_capability("manage_liquidity")

        for agent_id in set(analysts):
            msg = task_delegate_message(
                sender_id="coordinator",
                receiver_id=agent_id,
                task="analyze_token",
                params={"token": token, "workflow_id": workflow_id},
            )
            self.bus.publish(msg)

        self._log(f"Analysis workflow started for {token[:10]}... ({len(set(analysts))} agents)", "workflow")

        return {
            "status": "started",
            "workflow_id": workflow_id,
            "agents_asked": list(set(analysts)),
        }

    # ============================================================
    # STATUS & LOGGING
    # ============================================================

    def get_status(self):
        """Full coordinator status."""
        return {
            "active_workflows": {
                wid: {
                    "type": w["type"],
                    "status": w["status"],
                    "started_at": w["started_at"],
                }
                for wid, w in self.active_workflows.items()
            },
            "signal_rules": len(self.signal_rules),
            "recent_activity": self.collaboration_log[-20:],
            "bus_stats": self.bus.get_stats(),
        }

    def get_network_map(self):
        """
        Build a map of agent relationships for visualization.
        Shows who talks to whom and how much.
        """
        agents = self.bus.get_agents()
        connections = []

        # Build connections from message history
        history = self.bus.get_history(limit=200)
        conn_counts = defaultdict(int)

        for msg in history:
            sender = msg.get("sender_id", "")
            receiver = msg.get("receiver_id", "")
            if sender and receiver and sender != "bus" and receiver:
                key = tuple(sorted([sender, receiver]))
                conn_counts[key] += 1

        for (a, b), count in conn_counts.items():
            connections.append({
                "from": a,
                "to": b,
                "message_count": count,
                "strength": min(count / 10, 1.0),  # Normalize
            })

        return {
            "agents": {
                aid: {
                    "type": info.get("agent_type", "unknown"),
                    "capabilities": info.get("capabilities", []),
                    "status": info.get("status", "unknown"),
                    "messages_sent": info.get("messages_sent", 0),
                    "messages_received": info.get("messages_received", 0),
                }
                for aid, info in agents.items()
            },
            "connections": connections,
            "total_messages": self.bus.stats["total_messages"],
        }

    def _log(self, message, event_type="info"):
        self.collaboration_log.append({
            "message": message,
            "type": event_type,
            "timestamp": time.time(),
        })
        # Keep log bounded
        if len(self.collaboration_log) > 200:
            self.collaboration_log = self.collaboration_log[-200:]
        print(f"[COORDINATOR] [{event_type.upper()}] {message}")


# ============================================================
# GLOBAL INSTANCE
# ============================================================
coordinator = AgentCoordinator()
