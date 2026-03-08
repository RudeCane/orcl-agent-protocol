# AI Agent Protocol v0.1

Autonomous AI agent for Base chain — observe, analyze, execute, communicate.

## Quick Start

```bash
pip install -r requirements.txt
cp .env.example .env   # edit with your RPC URL + wallet
python main.py         # starts at http://localhost:8000
```

## Architecture

```
OBSERVER  →  DECISION ENGINE  →  EXECUTOR
(DexScreener)  (SMA/RSI/Momentum)  (Safety gates + tx)
       └──────── MEMORY ──────────┘
```

## Safety (ships in DRY RUN mode)

- Max trade: $100 | Daily loss limit: $250
- Max slippage: 2% | Min liquidity: $50k
- Gas ceiling: 5 gwei | 30s cooldown
- Token whitelist: USDC, WETH, DAI
- Set `dry_run = False` in config.py to go live

## API

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/status | System overview |
| POST | /api/agents/create | Create agent |
| POST | /api/task | Natural language task |
| GET | /api/trades | Trade history |
| GET | /api/wallet | Balances |
| WS | /ws | Real-time updates |

API docs at http://localhost:8000/docs

## Project Structure

```
agents/base_agent.py      — Core autonomous loop
agents/specialized.py     — Liquidity, Market, Treasury agents
core/observer.py          — Market data from DexScreener
core/decision_engine.py   — SMA crossover, RSI, momentum signals
core/executor.py          — Trade execution + safety gates
blockchain/web3_client.py — Base chain Web3 connection
memory/agent_memory.py    — Decision history + learning
api/server.py             — FastAPI REST + WebSocket
```
