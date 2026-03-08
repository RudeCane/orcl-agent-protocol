"""
Agent Communicator — Mixin to add communication to any agent.

Drop this into your existing agents to give them the ability to
send signals, receive tasks, vote, and collaborate.

Usage:
    from comms.communicator import AgentCommunicator
    
    class MyAgent:
        def __init__(self):
            self.comms = AgentCommunicator(
                agent_id="my_agent_01",
                agent_type="market",
                capabilities=["market_scan", "price_track"]
            )
            
        def on_market_data(self, data):
            # Spot something interesting → tell other agents
            if data["price_change_1h"] < -10:
                self.comms.broadcast_signal("price_crash", data["token"], {
                    "change": data["price_change_1h"],
                    "confidence": 0.85
                })
"""

import time
import threading
from typing import Callable, Dict, List, Optional
from comms.message_bus import message_bus
from comms.coordinator import coordinator
from comms.protocol import (
    AgentMessage, MessageType, Priority, SignalType,
    signal_message, data_share_message, task_delegate_message,
)


class AgentCommunicator:
    """
    Communication interface for an agent.
    Handles registration, sending, receiving, and collaboration.
    """

    def __init__(self, agent_id, agent_type="generic", capabilities=None):
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.capabilities = capabilities or []
        self.inbox: List[dict] = []
        self.handlers: Dict[str, Callable] = {}
        self._max_inbox = 100

        # Register on the bus
        message_bus.register_agent(
            agent_id=self.agent_id,
            capabilities=self.capabilities,
            agent_type=self.agent_type,
        )

        # Subscribe to relevant message types
        self._setup_subscriptions()

    # ============================================================
    # SETUP
    # ============================================================

    def _setup_subscriptions(self):
        """Subscribe to message types this agent cares about."""
        # Every agent listens for:
        message_bus.subscribe(self.agent_id, MessageType.SIGNAL, self._on_message)
        message_bus.subscribe(self.agent_id, MessageType.ALERT, self._on_message)
        message_bus.subscribe(self.agent_id, MessageType.TASK_DELEGATE, self._on_message)
        message_bus.subscribe(self.agent_id, MessageType.DATA_SHARE, self._on_message)
        message_bus.subscribe(self.agent_id, MessageType.VOTE_REQUEST, self._on_message)
        message_bus.subscribe(self.agent_id, MessageType.CONSENSUS, self._on_message)

    def on(self, event_name, handler):
        """
        Register a handler for a specific event.
        
        agent.comms.on("signal", my_signal_handler)
        agent.comms.on("task", my_task_handler)
        agent.comms.on("vote", my_vote_handler)
        """
        self.handlers[event_name] = handler

    # ============================================================
    # SENDING — Ways to communicate with other agents
    # ============================================================

    def broadcast_signal(self, signal_type, token, data, priority=Priority.HIGH):
        """
        Broadcast a market signal to all agents.
        The coordinator will route it to the right agent.
        """
        msg = signal_message(
            sender_id=self.agent_id,
            signal_type=signal_type,
            token=token,
            data=data,
            priority=priority,
        )

        # Publish to bus
        result = message_bus.publish(msg)

        # Also notify coordinator for smart routing
        coordinator.handle_signal(msg)

        return result

    def send_data(self, receiver_id, data_type, data):
        """Share data with a specific agent."""
        msg = data_share_message(
            sender_id=self.agent_id,
            receiver_id=receiver_id,
            data_type=data_type,
            data=data,
        )
        return message_bus.publish(msg)

    def delegate_task(self, receiver_id, task, params):
        """Ask another agent to do something."""
        msg = task_delegate_message(
            sender_id=self.agent_id,
            receiver_id=receiver_id,
            task=task,
            params=params,
        )
        return message_bus.publish(msg)

    def respond(self, original_msg_id, content, receiver_id=None):
        """Reply to a message."""
        msg = AgentMessage(
            msg_type=MessageType.RESPONSE,
            sender_id=self.agent_id,
            receiver_id=receiver_id,
            reply_to=original_msg_id,
            content=content,
        )
        return message_bus.publish(msg)

    def vote(self, vote_msg_id, choice):
        """Cast a vote."""
        msg = AgentMessage(
            msg_type=MessageType.VOTE_CAST,
            sender_id=self.agent_id,
            reply_to=vote_msg_id,
            content={"vote": choice},
        )
        return message_bus.publish(msg)

    def heartbeat(self):
        """Send a heartbeat to show this agent is alive."""
        msg = AgentMessage(
            msg_type=MessageType.HEARTBEAT,
            sender_id=self.agent_id,
            content={"alive": True},
        )
        return message_bus.publish(msg)

    # ============================================================
    # RECEIVING — Handle incoming messages
    # ============================================================

    def _on_message(self, message: AgentMessage):
        """Internal handler — routes incoming messages."""
        # Store in inbox
        self.inbox.append(message.to_dict())
        if len(self.inbox) > self._max_inbox:
            self.inbox = self.inbox[-self._max_inbox:]

        # Route to specific handlers
        msg_type = message.msg_type

        if msg_type == MessageType.SIGNAL and "signal" in self.handlers:
            self.handlers["signal"](message)

        elif msg_type == MessageType.TASK_DELEGATE and "task" in self.handlers:
            self.handlers["task"](message)

        elif msg_type == MessageType.VOTE_REQUEST and "vote" in self.handlers:
            self.handlers["vote"](message)

        elif msg_type == MessageType.DATA_SHARE and "data" in self.handlers:
            self.handlers["data"](message)

        elif msg_type == MessageType.ALERT and "alert" in self.handlers:
            self.handlers["alert"](message)

        # Generic catch-all handler
        if "any" in self.handlers:
            self.handlers["any"](message)

    def get_inbox(self, limit=20):
        """Get recent messages received."""
        return self.inbox[-limit:]

    # ============================================================
    # CLEANUP
    # ============================================================

    def shutdown(self):
        """Unregister from the bus."""
        msg = AgentMessage(
            msg_type=MessageType.SHUTDOWN,
            sender_id=self.agent_id,
            content={"reason": "agent_shutdown"},
        )
        message_bus.publish(msg)
        message_bus.unregister_agent(self.agent_id)
