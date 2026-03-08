"""
BLOFIN INTEGRATION — Adds BloFin CEX leverage trading.

Usage (PowerShell, from project root):
    pip install blofin
    python blofin_integration\integrate.py
"""

import os


def patch_server():
    server_path = os.path.join("api", "server.py")

    if not os.path.exists(server_path):
        print(f"ERROR: {server_path} not found. Run from project root.")
        return False

    with open(server_path, "r", encoding="utf-8") as f:
        content = f.read()

    if "BloFinAgent" in content:
        print("Server already has BloFin integration. Skipping.")
        return True

    # Add import
    if "from blofin_integration" not in content:
        marker = "from config import config"
        new_import = """from config import config
from blofin_integration.agent import BloFinAgent
from blofin_integration.client import BloFinTrader"""
        content = content.replace(marker, new_import)

    # Add BloFin to task endpoint
    old_else = """    else:
        return {"status": "unknown_task","""
    new_else = """    elif "blofin" in instruction or "cex" in instruction or "centralized" in instruction:
        pairs = []
        for p in ["btc", "eth", "sol", "bnb", "xrp", "doge", "ada", "avax", "link", "arb", "op", "sui"]:
            if p in instruction:
                pairs.append(f"{p.upper()}-USDT")
        if not pairs:
            pairs = ["BTC-USDT", "ETH-USDT"]
        agent = BloFinAgent(
            pairs=pairs,
            api_key=getattr(config, 'blofin_api_key', ''),
            api_secret=getattr(config, 'blofin_api_secret', ''),
            passphrase=getattr(config, 'blofin_passphrase', ''),
            dry_run=True,
        )
    else:
        return {"status": "unknown_task","""
    content = content.replace(old_else, new_else)

    # Add BloFin API routes before websocket
    blofin_routes = '''

# ── BLOFIN EXCHANGE ROUTES ────────────────────────────────────

@app.get("/api/blofin/status")
def get_blofin_status():
    """Get status of all BloFin agents."""
    blofin_agents = {}
    for aid, a in agents.items():
        if hasattr(a, 'trader') and hasattr(a, 'pairs'):
            blofin_agents[aid] = a.get_state()
    return blofin_agents

@app.get("/api/blofin/positions")
def get_blofin_positions():
    """Get all open BloFin positions."""
    positions = []
    for a in agents.values():
        if hasattr(a, 'trader') and hasattr(a, 'pairs'):
            status = a.trader.get_status()
            positions.extend(status.get("open_positions", []))
    return positions

@app.get("/api/blofin/ticker/{inst_id}")
def get_blofin_ticker(inst_id: str):
    """Get BloFin ticker for an instrument."""
    trader = BloFinTrader()
    return trader.get_ticker(inst_id) or {"error": "Not found"}

@app.get("/api/blofin/pairs")
def get_blofin_pairs():
    """Get popular BloFin trading pairs."""
    return BloFinTrader.POPULAR_PAIRS

@app.get("/api/blofin/trades")
def get_blofin_trades():
    """Get recent BloFin trades."""
    trades = []
    for a in agents.values():
        if hasattr(a, 'trader') and hasattr(a, 'pairs'):
            trades.extend(a.trader.trade_log)
    trades.sort(key=lambda t: t.get("time", 0), reverse=True)
    return trades[:50]

'''

    ws_marker = '@app.websocket("/ws")'
    if ws_marker in content:
        content = content.replace(ws_marker, blofin_routes + ws_marker)
    else:
        content += blofin_routes

    with open(server_path, "w", encoding="utf-8") as f:
        f.write(content)

    print("Patched api/server.py with BloFin routes.")
    return True


def patch_config():
    """Add BloFin config fields."""
    config_path = "config.py"
    if not os.path.exists(config_path):
        return

    with open(config_path, "r", encoding="utf-8") as f:
        content = f.read()

    if "blofin_api_key" in content:
        return

    # Add BloFin fields to Config class
    old_config_end = 'config = Config()'
    new_config_end = '''    # BloFin Exchange (get keys from https://blofin.com/en/account/apis)
    blofin_api_key: str = os.getenv("BLOFIN_API_KEY", "")
    blofin_api_secret: str = os.getenv("BLOFIN_API_SECRET", "")
    blofin_passphrase: str = os.getenv("BLOFIN_PASSPHRASE", "")

config = Config()'''

    content = content.replace(old_config_end, new_config_end)

    with open(config_path, "w", encoding="utf-8") as f:
        f.write(content)

    print("Added BloFin config fields to config.py")


def show_guide():
    print("""
============================================================
  BLOFIN EXCHANGE — INTEGRATION COMPLETE
============================================================

New API endpoints:
  GET /api/blofin/status           → BloFin agent status
  GET /api/blofin/positions        → Open positions
  GET /api/blofin/ticker/{pair}    → Price for a pair
  GET /api/blofin/pairs            → Available trading pairs
  GET /api/blofin/trades           → Trade history

How to use from the dashboard:
  "blofin trade BTC and ETH"
  "cex leverage BTC SOL"

To connect your BloFin account:
  1. Go to https://blofin.com/en/account/apis
  2. Create an API key with TRADE permission
  3. Set your keys in config.py or as environment variables:
     
     $env:BLOFIN_API_KEY = "your_key"
     $env:BLOFIN_API_SECRET = "your_secret"  
     $env:BLOFIN_PASSPHRASE = "your_passphrase"

Available pairs include:
  BTC-USDT, ETH-USDT, SOL-USDT, BNB-USDT, XRP-USDT,
  DOGE-USDT, ADA-USDT, AVAX-USDT, LINK-USDT, ARB-USDT,
  OP-USDT, SUI-USDT, and 200+ more

SAFETY DEFAULTS:
  - Max leverage: 5x
  - Position size: 0.1 contracts
  - Stop-loss: 3%
  - Take-profit: 6%
  - Max 3 open positions
  - DRY RUN MODE: ON

To install the BloFin SDK:
  pip install blofin

============================================================
""")


if __name__ == "__main__":
    print("Adding BloFin exchange integration...\n")
    if patch_server():
        patch_config()
        show_guide()
    else:
        print("Integration failed.")
