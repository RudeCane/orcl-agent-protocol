"""
MULTI-CHAIN INTEGRATION — Adds Ethereum & BNB Chain support.

Usage (PowerShell, from project root):
    python multichain\integrate.py
"""

import os


def patch_server():
    server_path = os.path.join("api", "server.py")

    if not os.path.exists(server_path):
        print(f"ERROR: {server_path} not found. Run from project root.")
        return False

    with open(server_path, "r", encoding="utf-8") as f:
        content = f.read()

    if "multichain" in content:
        print("Server already has multi-chain routes. Skipping.")
        return True

    # Add imports at top (after existing imports)
    marker = "from config import config"
    new_imports = """from config import config
from multichain.client import multichain_client
from multichain.chains import CHAINS, get_chain, get_all_chains
from multichain.observer import get_token_data_multichain, scan_chain_tokens"""

    if "from multichain" not in content:
        content = content.replace(marker, new_imports)

    # Add startup code to connect all chains
    # Find the app creation and add after it
    app_line = 'app = FastAPI(title="AI Agent Protocol", version="0.1.0")'
    startup_code = '''app = FastAPI(title="AI Agent Protocol", version="0.1.0")

# Connect to all chains on startup
@app.on_event("startup")
def startup_connect_chains():
    results = multichain_client.connect_all()
    for chain, connected in results.items():
        status = "CONNECTED" if connected else "FAILED"
        print(f"  [{chain.upper()}] {status}")
'''
    content = content.replace(app_line, startup_code)

    # Add multi-chain API routes before websocket
    multichain_routes = '''

# ── MULTI-CHAIN ROUTES ────────────────────────────────────────

@app.get("/api/chains")
def get_chains():
    """Get all supported chains and their connection status."""
    return multichain_client.get_status()

@app.get("/api/chains/{chain_key}/tokens")
def get_chain_tokens(chain_key: str, limit: int = 10):
    """Get trending tokens on a specific chain."""
    return scan_chain_tokens(chain_key, limit)

@app.get("/api/chains/{chain_key}/token/{token_address}")
def get_token_on_chain(chain_key: str, token_address: str):
    """Get token data on a specific chain."""
    data = get_token_data_multichain(token_address, chain_key)
    if not data:
        return {"error": "Token not found"}
    return data

@app.get("/api/chains/{chain_key}/gas")
def get_gas_price(chain_key: str):
    """Get current gas price on a chain."""
    return {"chain": chain_key, "gas_gwei": multichain_client.get_gas_price(chain_key)}

@app.get("/api/chains/{chain_key}/balance/{address}")
def get_chain_balance(chain_key: str, address: str):
    """Get native token balance on a chain."""
    return {
        "chain": chain_key,
        "address": address,
        "balance": multichain_client.get_native_balance(chain_key, address),
    }

'''

    ws_marker = '@app.websocket("/ws")'
    if ws_marker in content:
        content = content.replace(ws_marker, multichain_routes + ws_marker)
    else:
        content += multichain_routes

    # Update the task endpoint to parse chain from instruction
    old_task_market = 'agent = MarketAgent(tokens=req.tokens, poll_interval=15)'
    new_task_market = '''# Detect chain from instruction
        chain = "base"
        for c in ["ethereum", "eth", "bnb", "bsc", "binance"]:
            if c in instruction:
                chain = c
                break
        chain_config = get_chain(chain)
        tokens = req.tokens
        if not tokens and chain_config:
            tokens = chain_config.get("default_tokens", [])
        agent = MarketAgent(tokens=tokens, poll_interval=15)'''
    content = content.replace(old_task_market, new_task_market)

    with open(server_path, "w", encoding="utf-8") as f:
        f.write(content)

    print("Patched api/server.py with multi-chain routes.")
    return True


def show_guide():
    print("""
============================================================
  MULTI-CHAIN SUPPORT — INTEGRATION COMPLETE
============================================================

Your agent now supports:
  - Base      (chain_id: 8453)  — Avantis for perps
  - Ethereum  (chain_id: 1)     — Hyperliquid for perps
  - BNB Chain (chain_id: 56)    — Aster for perps

New API endpoints:
  GET /api/chains                            → All chains + status
  GET /api/chains/{chain}/tokens             → Trending tokens
  GET /api/chains/{chain}/token/{address}    → Token data
  GET /api/chains/{chain}/gas                → Gas price
  GET /api/chains/{chain}/balance/{address}  → Wallet balance

How to use from the dashboard:
  "monitor WETH on ethereum"
  "watch BNB on bnb chain"
  "leverage trade ETH on base"

The agent auto-detects the chain from your instruction and
uses the right RPC + tokens for that chain.

============================================================
""")


if __name__ == "__main__":
    print("Adding multi-chain support...\n")
    if patch_server():
        show_guide()
    else:
        print("Integration failed.")
