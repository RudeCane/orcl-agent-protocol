"""
Communication API Routes
Add these to your existing FastAPI server (api/server.py).

Copy the routes below into your server.py, or import this file.
"""

# ============================================================
# ADD THESE IMPORTS to the top of api/server.py:
# ============================================================
# from comms.message_bus import message_bus
# from comms.coordinator import coordinator
# from comms.protocol import MessageType, SignalType

# ============================================================
# ADD THESE ROUTES to api/server.py:
# ============================================================

ROUTES_CODE = """

# ── COMMUNICATION ROUTES ──────────────────────────────────────

@app.get("/api/comms/network")
def get_network():
    \"\"\"Get the full agent network map — agents, connections, message flow.\"\"\"
    return coordinator.get_network_map()

@app.get("/api/comms/messages")
def get_messages(limit: int = 50, msg_type: str = None, agent_id: str = None):
    \"\"\"Get message history.\"\"\"
    return message_bus.get_history(limit=limit, msg_type=msg_type, agent_id=agent_id)

@app.get("/api/comms/stats")
def get_comms_stats():
    \"\"\"Get message bus statistics.\"\"\"
    return message_bus.get_stats()

@app.get("/api/comms/coordinator")
def get_coordinator_status():
    \"\"\"Get coordinator status — workflows, rules, activity.\"\"\"
    return coordinator.get_status()

@app.get("/api/comms/agents")
def get_network_agents():
    \"\"\"Get all registered agents with their capabilities and subscriptions.\"\"\"
    return message_bus.get_agents()

@app.post("/api/comms/analyze")
def request_analysis(token: str):
    \"\"\"Trigger a multi-agent analysis of a token.\"\"\"
    result = coordinator.run_analysis_workflow(token)
    return result

@app.get("/api/comms/votes")
def get_votes():
    \"\"\"Get active and past votes.\"\"\"
    results = {}
    for vote_id in message_bus.active_votes:
        results[vote_id] = message_bus.get_vote_result(vote_id)
    return results

"""

# ============================================================
# QUICK INTEGRATION GUIDE:
# ============================================================
# 
# 1. Copy the comms/ folder into your project root
#
# 2. Add to api/server.py at the top:
#    from comms.message_bus import message_bus
#    from comms.coordinator import coordinator
#
# 3. Copy the routes above into api/server.py
#
# 4. In your agent classes (agents/specialized.py), add communication:
#
#    from comms.communicator import AgentCommunicator
#
#    class MarketAgent:
#        def __init__(self, ...):
#            ...existing code...
#            self.comms = AgentCommunicator(
#                agent_id=self.agent_id,
#                agent_type="market",
#                capabilities=["market_scan", "price_track"]
#            )
#
#        def on_cycle(self, market_data):
#            ...existing analysis...
#
#            # When you spot something, broadcast to other agents:
#            if price_change < -10:
#                self.comms.broadcast_signal(
#                    "price_crash", 
#                    token_address,
#                    {"change": price_change, "confidence": 0.85}
#                )
#
# 5. That's it — agents now talk to each other through the bus.
#    The coordinator auto-routes signals to the right agent.
# ============================================================

print("Communication routes ready. See integration guide above.")
