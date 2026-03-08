"""
Message Bus — Central Communication Hub
Routes messages between agents, handles subscriptions, and logs everything.
"""

import time
import threading
from collections import defaultdict
from typing import Callable, Dict, List, Optional
from comms.protocol import AgentMessage, MessageType, Priority


class MessageBus:
    """
    The central nervous system of the agent network.
    
    Agents register here, subscribe to message types, and send/receive messages.
    The bus handles routing, broadcasting, filtering, and message history.
    
    Usage:
        bus = MessageBus()
        bus.register_agent("market_01", capabilities=["market_scan", "price_track"])
        bus.subscribe("market_01", MessageType.SIGNAL, my_handler)
        bus.publish(some_message)
    """

    def __init__(self, max_history=500):
        # Registered agents: {agent_id: {"capabilities": [...], "status": str, "registered_at": float}}
        self.agents: Dict[str, dict] = {}

        # Subscriptions: {MessageType: {agent_id: callback_fn}}
        self.subscriptions: Dict[MessageType, Dict[str, Callable]] = defaultdict(dict)

        # Message history (most recent)
        self.history: List[dict] = []
        self.max_history = max_history

        # Pending acknowledgments: {msg_id: {"message": msg, "sent_at": float, "acked": bool}}
        self.pending_acks: Dict[str, dict] = {}

        # Votes: {msg_id: {"proposal": str, "votes": {agent_id: vote}, "deadline": float}}
        self.active_votes: Dict[str, dict] = {}

        # Stats
        self.stats = {
            "total_messages": 0,
            "messages_by_type": defaultdict(int),
            "messages_by_agent": defaultdict(int),
            "broadcasts": 0,
            "direct_messages": 0,
            "expired_messages": 0,
        }

        self._lock = threading.Lock()

    # ============================================================
    # AGENT REGISTRATION
    # ============================================================

    def register_agent(self, agent_id, capabilities=None, agent_type="generic"):
        """Register an agent on the bus."""
        with self._lock:
            self.agents[agent_id] = {
                "capabilities": capabilities or [],
                "agent_type": agent_type,
                "status": "active",
                "registered_at": time.time(),
                "last_heartbeat": time.time(),
                "messages_sent": 0,
                "messages_received": 0,
            }

            # Log registration
            self._log_event("register", agent_id, f"Agent registered: type={agent_type}")
            return True

    def unregister_agent(self, agent_id):
        """Remove an agent from the bus."""
        with self._lock:
            if agent_id in self.agents:
                # Remove all subscriptions
                for msg_type in self.subscriptions:
                    self.subscriptions[msg_type].pop(agent_id, None)
                del self.agents[agent_id]
                self._log_event("unregister", agent_id, "Agent removed")
                return True
            return False

    def get_agents(self):
        """List all registered agents."""
        return {
            aid: {**info, "subscriptions": self._get_agent_subscriptions(aid)}
            for aid, info in self.agents.items()
        }

    def find_agent_by_capability(self, capability):
        """Find agents that have a specific capability."""
        return [
            aid for aid, info in self.agents.items()
            if capability in info.get("capabilities", []) and info["status"] == "active"
        ]

    # ============================================================
    # SUBSCRIPTIONS
    # ============================================================

    def subscribe(self, agent_id, msg_type, callback):
        """
        Subscribe an agent to a message type.
        callback(message: AgentMessage) will be called when a matching message arrives.
        """
        if agent_id not in self.agents:
            return False

        with self._lock:
            self.subscriptions[msg_type][agent_id] = callback
        return True

    def subscribe_all(self, agent_id, callback):
        """Subscribe an agent to ALL message types."""
        for msg_type in MessageType:
            self.subscribe(agent_id, msg_type, callback)

    def unsubscribe(self, agent_id, msg_type):
        """Remove a subscription."""
        with self._lock:
            self.subscriptions[msg_type].pop(agent_id, None)

    # ============================================================
    # PUBLISH — Send a message through the bus
    # ============================================================

    def publish(self, message: AgentMessage):
        """
        Publish a message to the bus.
        Routes to specific agent or broadcasts to all subscribers.
        """
        with self._lock:
            # Skip expired messages
            if message.is_expired():
                self.stats["expired_messages"] += 1
                return {"delivered": 0, "status": "expired"}

            # Update stats
            self.stats["total_messages"] += 1
            self.stats["messages_by_type"][message.msg_type.value] += 1
            self.stats["messages_by_agent"][message.sender_id] += 1

            if message.sender_id in self.agents:
                self.agents[message.sender_id]["messages_sent"] += 1

            # Track in history
            self._add_to_history(message)

            # Handle special message types
            if message.msg_type == MessageType.HEARTBEAT:
                self._handle_heartbeat(message)
                return {"delivered": 0, "status": "heartbeat_recorded"}

            if message.msg_type == MessageType.VOTE_CAST:
                self._handle_vote(message)

            # Route the message
            delivered = 0

            if message.is_broadcast():
                # Broadcast to all subscribers of this type
                self.stats["broadcasts"] += 1
                subscribers = self.subscriptions.get(message.msg_type, {})

                for agent_id, callback in subscribers.items():
                    if agent_id != message.sender_id:  # Don't send to self
                        try:
                            callback(message)
                            delivered += 1
                            if agent_id in self.agents:
                                self.agents[agent_id]["messages_received"] += 1
                        except Exception as e:
                            self._log_event("error", message.sender_id,
                                          f"Delivery to {agent_id} failed: {e}")

            else:
                # Direct message to specific agent
                self.stats["direct_messages"] += 1
                subscribers = self.subscriptions.get(message.msg_type, {})

                if message.receiver_id in subscribers:
                    try:
                        subscribers[message.receiver_id](message)
                        delivered = 1
                        if message.receiver_id in self.agents:
                            self.agents[message.receiver_id]["messages_received"] += 1
                    except Exception as e:
                        self._log_event("error", message.sender_id,
                                      f"Delivery to {message.receiver_id} failed: {e}")

            # Track ack if needed
            if message.require_ack:
                self.pending_acks[message.msg_id] = {
                    "message": message.to_dict(),
                    "sent_at": time.time(),
                    "acked": False,
                    "delivered_to": delivered,
                }

            return {"delivered": delivered, "status": "sent", "msg_id": message.msg_id}

    # ============================================================
    # VOTING SYSTEM
    # ============================================================

    def start_vote(self, message: AgentMessage):
        """Initialize a vote from a vote_request message."""
        self.active_votes[message.msg_id] = {
            "proposal": message.content.get("proposal", ""),
            "options": message.content.get("options", ["yes", "no"]),
            "votes": {},
            "deadline": message.content.get("deadline", time.time() + 30),
            "initiator": message.sender_id,
        }
        # Broadcast the vote request
        return self.publish(message)

    def _handle_vote(self, message: AgentMessage):
        """Process an incoming vote."""
        vote_id = message.reply_to
        if vote_id and vote_id in self.active_votes:
            vote = self.active_votes[vote_id]
            if time.time() <= vote["deadline"]:
                vote["votes"][message.sender_id] = message.content.get("vote")

    def get_vote_result(self, vote_id):
        """Get the result of a vote."""
        if vote_id not in self.active_votes:
            return None

        vote = self.active_votes[vote_id]
        vote_counts = defaultdict(int)
        for v in vote["votes"].values():
            vote_counts[v] += 1

        total = len(vote["votes"])
        eligible = len(self.agents) - 1  # Minus the initiator

        return {
            "proposal": vote["proposal"],
            "votes": dict(vote_counts),
            "total_votes": total,
            "eligible_voters": eligible,
            "participation": total / eligible if eligible > 0 else 0,
            "deadline": vote["deadline"],
            "expired": time.time() > vote["deadline"],
        }

    # ============================================================
    # HISTORY & STATS
    # ============================================================

    def get_history(self, limit=50, msg_type=None, agent_id=None):
        """Get message history with optional filters."""
        filtered = self.history

        if msg_type:
            filtered = [m for m in filtered if m["msg_type"] == msg_type]

        if agent_id:
            filtered = [m for m in filtered
                       if m["sender_id"] == agent_id or m.get("receiver_id") == agent_id]

        return filtered[-limit:]

    def get_stats(self):
        """Get bus statistics."""
        return {
            **self.stats,
            "messages_by_type": dict(self.stats["messages_by_type"]),
            "messages_by_agent": dict(self.stats["messages_by_agent"]),
            "registered_agents": len(self.agents),
            "active_agents": sum(1 for a in self.agents.values() if a["status"] == "active"),
            "total_subscriptions": sum(len(s) for s in self.subscriptions.values()),
            "active_votes": len(self.active_votes),
            "pending_acks": len([a for a in self.pending_acks.values() if not a["acked"]]),
        }

    # ============================================================
    # INTERNALS
    # ============================================================

    def _handle_heartbeat(self, message):
        if message.sender_id in self.agents:
            self.agents[message.sender_id]["last_heartbeat"] = time.time()
            self.agents[message.sender_id]["status"] = "active"

    def _add_to_history(self, message: AgentMessage):
        entry = message.to_dict()
        self.history.append(entry)
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]

    def _get_agent_subscriptions(self, agent_id):
        subs = []
        for msg_type, subscribers in self.subscriptions.items():
            if agent_id in subscribers:
                subs.append(msg_type.value)
        return subs

    def _log_event(self, event_type, agent_id, details):
        self.history.append({
            "msg_type": f"system_{event_type}",
            "sender_id": "bus",
            "receiver_id": agent_id,
            "content": {"details": details},
            "timestamp": time.time(),
            "priority": "normal",
        })


# ============================================================
# GLOBAL BUS INSTANCE
# ============================================================
message_bus = MessageBus()
