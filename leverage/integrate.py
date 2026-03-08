"""
LEVERAGE INTEGRATION — Run this to add leverage trading to your project.

Usage (in PowerShell, from your project root):
    python leverage\integrate.py

This will:
1. Patch api/server.py with leverage API routes
2. Register the LeverageAgent as a new agent type
"""

import os


def patch_server():
    server_path = os.path.join("api", "server.py")

    if not os.path.exists(server_path):
        print(f"ERROR: {server_path} not found. Run from your project root.")
        return False

    with open(server_path, "r", encoding="utf-8") as f:
        content = f.read()

    if "leverage" in content.lower() and "LeverageAgent" in content:
        print("Server already has leverage routes. Skipping.")
        return True

    # Add import
    old_import = "from agents.specialized import LiquidityAgent, MarketAgent, TreasuryAgent"
    new_import = """from agents.specialized import LiquidityAgent, MarketAgent, TreasuryAgent
from leverage.leverage_agent import LeverageAgent
from leverage.trading_engine import LeverageSafetyConfig"""

    content = content.replace(old_import, new_import)

    # Add leverage to agent_map in create_agent
    old_map = '"treasury": TreasuryAgent}'
    new_map = '"treasury": TreasuryAgent, "leverage": None}'
    content = content.replace(old_map, new_map)

    # Add leverage to task endpoint
    old_task_else = '''    else:
        return {"status": "unknown_task",
                "message": "Try: \'monitor [token]\', \'manage liquidity\', \'watch treasury\'"}'''
    new_task_else = '''    elif "leverage" in instruction or "perp" in instruction or "long" in instruction or "short" in instruction:
        agent = LeverageAgent(tokens=req.tokens, collateral_per_trade=20.0)
    else:
        return {"status": "unknown_task",
                "message": "Try: 'monitor [token]', 'manage liquidity', 'watch treasury', 'leverage trade [token]'"}'''
    content = content.replace(old_task_else, new_task_else)

    # Add leverage-specific API routes before websocket
    leverage_routes = '''

# ── LEVERAGE TRADING ROUTES ───────────────────────────────────

@app.get("/api/leverage/status")
def get_leverage_status():
    """Get status of all leverage agents and positions."""
    leverage_agents = {aid: a.get_state() for aid, a in agents.items()
                       if hasattr(a, 'engine') and hasattr(a, 'strategy')}
    return {
        "agents": leverage_agents,
        "total_positions": sum(s.get("position_count", 0) for s in leverage_agents.values()),
        "total_pnl": sum(s.get("unrealized_pnl", 0) for s in leverage_agents.values()),
        "total_realized": sum(s.get("total_realized_pnl", 0) for s in leverage_agents.values()),
    }

@app.get("/api/leverage/positions")
def get_positions():
    """Get all open leveraged positions."""
    positions = []
    for a in agents.values():
        if hasattr(a, 'engine'):
            positions.extend(a.engine.get_status()["open_positions"])
    return positions

@app.get("/api/leverage/trades")
def get_leverage_trades():
    """Get recent leverage trade history."""
    trades = []
    for a in agents.values():
        if hasattr(a, 'engine'):
            trades.extend(a.engine.trade_log)
    trades.sort(key=lambda t: t.get("time", 0), reverse=True)
    return trades[:50]

@app.post("/api/leverage/close/{position_id}")
def close_leverage_position(position_id: str):
    """Manually close a leveraged position."""
    for a in agents.values():
        if hasattr(a, 'engine') and position_id in a.engine.positions:
            pos = a.engine.positions[position_id]
            result = a.engine.close_position(position_id, pos.current_price, "manual")
            return result
    return {"error": "Position not found"}

'''

    ws_marker = '@app.websocket("/ws")'
    if ws_marker in content:
        content = content.replace(ws_marker, leverage_routes + ws_marker)
    else:
        content += leverage_routes

    with open(server_path, "w", encoding="utf-8") as f:
        f.write(content)

    print("Patched api/server.py with leverage trading routes.")
    return True


def show_guide():
    print("""
============================================================
  LEVERAGE TRADING — INTEGRATION COMPLETE
============================================================

New API endpoints:
  GET  /api/leverage/status              → All leverage agents & positions
  GET  /api/leverage/positions           → Open positions
  GET  /api/leverage/trades              → Trade history
  POST /api/leverage/close/{position_id} → Manually close a position

How to create a leverage agent from the dashboard:
  Type: "leverage trade WETH" or "long ETH with leverage"
  
  The agent will:
  - Scan market data every 30 seconds
  - Look for trend + momentum + volume confirmation
  - Open positions with 2-5x leverage (based on confidence)
  - Set automatic stop-loss and take-profit
  - Close positions when targets are hit
  - Broadcast signals to other agents

SAFETY DEFAULTS (change in leverage/trading_engine.py):
  - Max leverage: 5x
  - Max position: $100
  - Max total exposure: $300
  - Max 3 open positions
  - Daily loss limit: $100
  - Mandatory stop-loss on every trade
  - 5-minute cooldown after losses
  - DRY RUN MODE: ON (no real trades until you disable it)

To enable LIVE trading (use at your own risk):
  1. Set your wallet in config.py
  2. In leverage/trading_engine.py, set dry_run=False
  3. Start with SMALL amounts and WATCH IT CLOSELY

============================================================
""")


if __name__ == "__main__":
    print("Adding leverage trading to your project...\n")
    if patch_server():
        show_guide()
    else:
        print("Integration failed.")
