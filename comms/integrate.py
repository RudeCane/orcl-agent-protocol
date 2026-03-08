"""
INTEGRATION SCRIPT — Run this once to add multi-agent communication to your project.

Usage (in PowerShell, from your project root):
    python comms/integrate.py

This will:
1. Patch api/server.py with communication routes
2. Show you how to update your agents
"""

import os
import sys


def patch_server():
    """Add communication imports and routes to api/server.py."""
    
    server_path = os.path.join("api", "server.py")
    
    if not os.path.exists(server_path):
        print(f"ERROR: {server_path} not found. Run this from your project root.")
        return False
    
    with open(server_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Check if already patched
    if "comms.message_bus" in content:
        print("Server already has communication routes. Skipping.")
        return True
    
    # Add imports after existing imports
    import_line = "from config import config"
    new_imports = """from config import config
from comms.message_bus import message_bus
from comms.coordinator import coordinator
from comms.protocol import MessageType, SignalType"""
    
    content = content.replace(import_line, new_imports)
    
    # Add routes before the websocket endpoint
    new_routes = '''

# ── MULTI-AGENT COMMUNICATION ROUTES ──────────────────────────

@app.get("/api/comms/network")
def get_network():
    """Get the full agent network map."""
    return coordinator.get_network_map()

@app.get("/api/comms/messages")
def get_comms_messages(limit: int = 50):
    """Get message history between agents."""
    return message_bus.get_history(limit=limit)

@app.get("/api/comms/stats")
def get_comms_stats():
    """Get message bus statistics."""
    return message_bus.get_stats()

@app.get("/api/comms/coordinator")
def get_coordinator_status():
    """Get coordinator status — workflows, rules, activity."""
    return coordinator.get_status()

@app.get("/api/comms/agents")
def get_network_agents():
    """Get all agents with capabilities and subscriptions."""
    return message_bus.get_agents()

@app.post("/api/comms/analyze")
def request_analysis(token: str = ""):
    """Trigger multi-agent analysis of a token."""
    if not token:
        return {"error": "Provide a token address as query param"}
    return coordinator.run_analysis_workflow(token)

@app.get("/api/comms/votes")
def get_votes():
    """Get active votes."""
    results = {}
    for vote_id in message_bus.active_votes:
        results[vote_id] = message_bus.get_vote_result(vote_id)
    return results

'''
    
    # Insert before websocket
    ws_marker = '@app.websocket("/ws")'
    if ws_marker in content:
        content = content.replace(ws_marker, new_routes + ws_marker)
    else:
        # Append to end
        content += new_routes
    
    with open(server_path, "w", encoding="utf-8") as f:
        f.write(content)
    
    print(f"Patched {server_path} with communication routes.")
    return True


def show_agent_guide():
    """Show how to add communication to existing agents."""
    print("""
============================================================
  MULTI-AGENT COMMUNICATION — INTEGRATION COMPLETE
============================================================

Your server now has these new endpoints:
  GET  /api/comms/network      → Agent network map
  GET  /api/comms/messages     → Message history
  GET  /api/comms/stats        → Bus statistics  
  GET  /api/comms/coordinator  → Coordinator status
  GET  /api/comms/agents       → Registered agents
  POST /api/comms/analyze      → Multi-agent token analysis
  GET  /api/comms/votes        → Active votes

NEXT STEP — Add communication to your agents:

Open agents/specialized.py and add this to each agent class:

    from comms.communicator import AgentCommunicator

    class MarketAgent:
        def __init__(self, ...):
            # ...existing init code...
            
            # ADD THIS:
            self.comms = AgentCommunicator(
                agent_id=self.agent_id,
                agent_type="market",
                capabilities=["market_scan", "price_track"]
            )

        # In your analysis/cycle method, broadcast signals:
        def _analyze(self, data):
            # ...existing analysis...
            
            if data["price_change_1h"] < -10:
                self.comms.broadcast_signal(
                    "price_crash",
                    token_address,
                    {"change": data["price_change_1h"], "confidence": 0.85}
                )

For LiquidityAgent, use capabilities=["manage_liquidity", "execute_trade"]
For TreasuryAgent, use capabilities=["risk_management", "treasury"]

The coordinator will automatically route signals to the right agent.
============================================================
""")


if __name__ == "__main__":
    print("Patching your project with multi-agent communication...\n")
    
    if patch_server():
        show_agent_guide()
    else:
        print("Integration failed. Make sure you're running from your project root.")
