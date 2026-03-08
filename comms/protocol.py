"""
Agent Communication Protocol — Message Types & Formats
Defines how agents talk to each other.
"""

import time
import uuid
from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Optional, List


# ============================================================
# MESSAGE TYPES — What agents can say to each other
# ============================================================

class MessageType(str, Enum):
    # Signals & Alerts
    SIGNAL = "signal"               # "I spotted something"
    ALERT = "alert"                 # "Something urgent is happening"

    # Requests & Responses
    REQUEST = "request"             # "Can you do something for me?"
    RESPONSE = "response"           # "Here's what you asked for"

    # Data Sharing
    DATA_SHARE = "data_share"       # "Here's data you might need"
    PRICE_UPDATE = "price_update"   # "New price info"

    # Coordination
    TASK_DELEGATE = "task_delegate" # "I need you to handle this"
    TASK_ACCEPT = "task_accept"     # "I'll handle it"
    TASK_REJECT = "task_reject"     # "I can't handle that"
    TASK_COMPLETE = "task_complete" # "I finished the task"

    # Consensus
    VOTE_REQUEST = "vote_request"   # "Should we do this?"
    VOTE_CAST = "vote_cast"         # "Here's my vote"
    CONSENSUS = "consensus"         # "The group decided"

    # System
    HEARTBEAT = "heartbeat"         # "I'm still alive"
    REGISTER = "register"           # "I'm a new agent"
    SHUTDOWN = "shutdown"           # "I'm going offline"


class Priority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class SignalType(str, Enum):
    BUY_OPPORTUNITY = "buy_opportunity"
    SELL_SIGNAL = "sell_signal"
    LIQUIDITY_LOW = "liquidity_low"
    LIQUIDITY_HIGH = "liquidity_high"
    VOLUME_SPIKE = "volume_spike"
    PRICE_CRASH = "price_crash"
    PRICE_PUMP = "price_pump"
    WHALE_MOVEMENT = "whale_movement"
    NEW_TOKEN = "new_token"
    RISK_WARNING = "risk_warning"


# ============================================================
# MESSAGE FORMAT
# ============================================================

@dataclass
class AgentMessage:
    """Core message that agents send to each other."""
    msg_type: MessageType
    sender_id: str
    content: Dict[str, Any]
    receiver_id: Optional[str] = None      # None = broadcast to all
    priority: Priority = Priority.NORMAL
    msg_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    timestamp: float = field(default_factory=time.time)
    reply_to: Optional[str] = None         # ID of message this replies to
    ttl: int = 60                          # Time-to-live in seconds
    require_ack: bool = False              # Does sender need acknowledgment?

    def to_dict(self):
        d = asdict(self)
        d["msg_type"] = self.msg_type.value
        d["priority"] = self.priority.value
        return d

    @classmethod
    def from_dict(cls, data):
        data["msg_type"] = MessageType(data["msg_type"])
        data["priority"] = Priority(data["priority"])
        return cls(**data)

    def is_expired(self):
        return time.time() - self.timestamp > self.ttl

    def is_broadcast(self):
        return self.receiver_id is None


# ============================================================
# HELPER CONSTRUCTORS — Quick ways to build common messages
# ============================================================

def signal_message(sender_id, signal_type, token, data, priority=Priority.HIGH):
    """Create a market signal message."""
    return AgentMessage(
        msg_type=MessageType.SIGNAL,
        sender_id=sender_id,
        priority=priority,
        content={
            "signal_type": signal_type.value if isinstance(signal_type, SignalType) else signal_type,
            "token": token,
            **data,
        },
    )


def data_share_message(sender_id, receiver_id, data_type, data):
    """Share data with a specific agent."""
    return AgentMessage(
        msg_type=MessageType.DATA_SHARE,
        sender_id=sender_id,
        receiver_id=receiver_id,
        content={"data_type": data_type, **data},
    )


def task_delegate_message(sender_id, receiver_id, task, params):
    """Ask another agent to perform a task."""
    return AgentMessage(
        msg_type=MessageType.TASK_DELEGATE,
        sender_id=sender_id,
        receiver_id=receiver_id,
        priority=Priority.HIGH,
        require_ack=True,
        content={"task": task, "params": params},
    )


def vote_request_message(sender_id, proposal, options, deadline_seconds=30):
    """Ask all agents to vote on something."""
    return AgentMessage(
        msg_type=MessageType.VOTE_REQUEST,
        sender_id=sender_id,
        receiver_id=None,  # Broadcast
        priority=Priority.HIGH,
        ttl=deadline_seconds,
        content={
            "proposal": proposal,
            "options": options,
            "deadline": time.time() + deadline_seconds,
        },
    )
