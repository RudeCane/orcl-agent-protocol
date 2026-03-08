"""API Server — FastAPI backend for the web dashboard."""
import asyncio
import json
import time
import logging
from typing import Dict, List
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from agents.specialized import LiquidityAgent, MarketAgent, TreasuryAgent
from leverage.leverage_agent import LeverageAgent
from leverage.trading_engine import LeverageSafetyConfig
from memory.agent_memory import memory
from blockchain.web3_client import web3_client
from config import config
from blofin_integration.agent import BloFinAgent
from blofin_integration.client import BloFinTrader
from multichain.client import multichain_client
from multichain.chains import CHAINS, get_chain, get_all_chains
from multichain.observer import get_token_data_multichain, scan_chain_tokens
from comms.message_bus import message_bus
from comms.coordinator import coordinator
from comms.protocol import MessageType, SignalType

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="AI Agent Protocol", version="0.1.0")

# Connect to all chains on startup
@app.on_event("startup")
def startup_connect_chains():
    results = multichain_client.connect_all()
    for chain, connected in results.items():
        status = "CONNECTED" if connected else "FAILED"
        print(f"  [{chain.upper()}] {status}")

app.add_middleware(CORSMiddleware, allow_origins=config.api.cors_origins,
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

agents: Dict[str, object] = {}

class AgentCreateRequest(BaseModel):
    agent_type: str
    tokens: List[str]
    poll_interval: int = 15

class TaskRequest(BaseModel):
    instruction: str
    tokens: List[str] = []

@app.get("/api/status")
def get_status():
    return {
        "blockchain": {"connected": web3_client.is_connected,
                       "chain": config.chain.name, "chain_id": config.chain.chain_id},
        "agents": {aid: a.get_state() for aid, a in agents.items()},
        "safety": {"dry_run": config.safety.dry_run,
                   "max_trade_usd": config.safety.max_trade_size_usd,
                   "daily_loss_limit": config.safety.daily_loss_limit_usd},
        "memory": memory.get_all_stats(),
    }

@app.post("/api/agents/create")
def create_agent(req: AgentCreateRequest):
    agent_map = {"liquidity": LiquidityAgent, "market": MarketAgent, "treasury": TreasuryAgent, "leverage": None}
    if req.agent_type not in agent_map:
        return {"error": f"Unknown type: {req.agent_type}"}
    agent = agent_map[req.agent_type](tokens=req.tokens, poll_interval=req.poll_interval)
    agent.start()
    agents[agent.agent_id] = agent
    return {"status": "created", "agent_id": agent.agent_id}

@app.post("/api/agents/{agent_id}/stop")
def stop_agent(agent_id: str):
    if agent_id not in agents: return {"error": "Not found"}
    agents[agent_id].stop()
    return {"status": "stopped"}

@app.post("/api/agents/{agent_id}/start")
def start_agent(agent_id: str):
    if agent_id not in agents: return {"error": "Not found"}
    agents[agent_id].start()
    return {"status": "started"}

@app.delete("/api/agents/{agent_id}")
def delete_agent(agent_id: str):
    if agent_id not in agents: return {"error": "Not found"}
    agents[agent_id].stop()
    del agents[agent_id]
    return {"status": "deleted"}

@app.get("/api/agents/{agent_id}")
def get_agent(agent_id: str):
    if agent_id not in agents: return {"error": "Not found"}
    return agents[agent_id].get_state()

@app.get("/api/agents")
def list_agents():
    return {aid: a.get_state() for aid, a in agents.items()}

@app.get("/api/memory")
def get_memory():
    return memory.get_all_stats()

@app.get("/api/trades")
def get_trades():
    all_trades = []
    for a in agents.values():
        all_trades.extend(getattr(a, "executor", getattr(a, "engine", None)) and getattr(a.executor if hasattr(a, "executor") else a.engine, "trade_log", []) or [])
    all_trades.sort(key=lambda t: t["time"], reverse=True)
    return all_trades[:100]

@app.get("/api/wallet")
def get_wallet():
    addr = config.wallet_address
    if not addr: return {"error": "No wallet configured"}
    return {
        "address": addr,
        "eth_balance": web3_client.get_eth_balance(addr),
        "usdc_balance": web3_client.get_token_balance(config.chain.usdc_address, addr),
    }



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

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            state = {"type": "state_update",
                     "agents": {aid: a.get_state() for aid, a in agents.items()},
                     "timestamp": time.time()}
            await ws.send_text(json.dumps(state, default=str))
            await asyncio.sleep(3)
    except WebSocketDisconnect:
        pass

@app.post("/api/task")
def submit_task(req: TaskRequest):
    instruction = req.instruction.lower()
    if "monitor" in instruction or "watch" in instruction:
        # Detect chain from instruction
        chain = "base"
        for c in ["ethereum", "eth", "bnb", "bsc", "binance"]:
            if c in instruction:
                chain = c
                break
        chain_config = get_chain(chain)
        tokens = req.tokens
        if not tokens and chain_config:
            tokens = chain_config.get("default_tokens", [])
        agent = MarketAgent(tokens=tokens, poll_interval=15)
    elif "liquidity" in instruction:
        agent = LiquidityAgent(tokens=req.tokens, poll_interval=30)
    elif "treasury" in instruction or "balance" in instruction:
        agent = TreasuryAgent(tokens=req.tokens, poll_interval=60)
    elif "leverage" in instruction or "perp" in instruction or "long" in instruction or "short" in instruction:
        agent = LeverageAgent(tokens=req.tokens, collateral_per_trade=20.0)
    elif "blofin" in instruction or "cex" in instruction or "centralized" in instruction:
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
        return {"status": "unknown_task",
                "message": "Try: 'monitor [token]', 'manage liquidity', 'watch treasury', 'leverage trade [token]'"}
    agent.start()
    agents[agent.agent_id] = agent
    return {"status": "started", "agent_id": agent.agent_id, "task": req.instruction}

