Set-Content README.md @'
# ORCL — Autonomous AI Agent Protocol

Autonomous AI agents for crypto — observe, analyze, execute, communicate.

Multi-chain (Base, Ethereum, BNB) + Multi-exchange (Binance, Binance.US, BloFin).

---

## Quick Start
git clone https://github.com/RudeCane/orcl-agent-protocol.git
cd orcl-agent-protocol
pip install -r requirements.txt
cp .env.example .env   # edit with your RPC URL + wallet keys
python main.py         # starts at http://localhost:8000

Open `dashboard.html` in Chrome. Type a command and click EXECUTE.

---

## Architecture
OBSERVER  →  DECISION ENGINE  →  EXECUTOR
(DexScreener     (SMA / RSI /        (Safety gates

Binance)       Momentum)            + tx signing)
└──────────── MEMORY ──────────────┘
│
MESSAGE BUS
(agent coordination)


---

## Safety (ships in DRY RUN mode)

| Guard | Default |
|-------|---------|
| Max trade | $100 |
| Daily loss limit | $250 |
| Max slippage | 2% |
| Min liquidity | $50k |
| Gas ceiling | 5 gwei |
| Cooldown | 30s |
| Max leverage | 5x |
| Max positions | 3 |
| Mandatory stop-loss | 5% |
| Token whitelist | USDC, WETH, DAI |

Set `dry_run = False` in `config.py` to go live.

---

## Dashboard Commands

| Command | What It Does |
|---------|-------------|
| `monitor WETH on base` | Market agent on Base |
| `monitor WETH on ethereum` | Market agent on Ethereum |
| `watch liquidity on bnb` | Liquidity agent on BNB |
| `leverage trade ETH on base` | Leverage perps via Avantis |
| `blofin trade BTC and SOL` | BloFin CEX leverage |
| `binance monitor BTC and ETH` | Monitor on Binance |
| `binance us watch SOL` | Monitor on Binance.US |

Voice: click the mic and speak naturally. Say "status report" to hear a full update.

---

## Trading View

Open `trading.html` for:
- Live candlestick charts (1m, 5m, 15m, 1H, 4H, 1D)
- Real-time Binance WebSocket order book (100ms updates)
- Depth chart + buy/sell wall detection
- Switch between Binance, Binance.US, BloFin

---

## Supported Platforms

| Platform | Type | Pairs | Features |
|----------|------|-------|----------|
| Base | DEX | Any | Swap, monitor, leverage (Avantis) |
| Ethereum | DEX | Any | Swap, monitor |
| BNB Chain | DEX | Any | Swap, monitor |
| Binance | CEX | 500+ | Monitor, order book, charts |
| Binance.US | CEX | 150+ | Monitor, order book, charts |
| BloFin | CEX | 200+ | Monitor, leverage trading |

---

## API

| Method | Endpoint | Description |
|--------|---------|-------------|
| GET | `/api/status` | System overview |
| POST | `/api/agents/create` | Create agent |
| POST | `/api/task` | Natural language task |
| GET | `/api/agents` | List agents |
| GET | `/api/trades` | Trade history |
| GET | `/api/wallet` | Balances |
| GET | `/api/chains` | Chain connections |
| GET | `/api/binance/ticker/{symbol}` | Binance price |
| GET | `/api/binance/orderbook/{symbol}` | Binance order book |
| GET | `/api/binance/candles/{symbol}` | Binance candles |
| GET | `/api/blofin/status` | BloFin status |
| GET | `/api/leverage/positions` | Open positions |
| GET | `/api/comms/network` | Agent network map |
| WS | `/ws` | Real-time updates |

API docs at `http://localhost:8000/docs`

---

## Project Structure
agents/base_agent.py          — Core autonomous loop
agents/specialized.py         — Liquidity, Market, Treasury agents
core/observer.py              — Market data from DexScreener
core/decision_engine.py       — SMA crossover, RSI, momentum signals
core/executor.py              — Trade execution + safety gates
blockchain/web3_client.py     — Base chain Web3 connection
memory/agent_memory.py        — Decision history + learning
comms/message_bus.py          — Agent-to-agent communication hub
comms/coordinator.py          — Smart signal routing + consensus
leverage/trading_engine.py    — Perpetual futures + risk management
leverage/leverage_agent.py    — Autonomous perp trader
binance_integration/client.py — Binance + Binance.US client
binance_integration/agent.py  — Binance monitoring agent
blofin_integration/client.py  — BloFin API wrapper
blofin_integration/agent.py   — BloFin leverage agent
multichain/chains.py          — Chain configs (Base, ETH, BNB)
multichain/client.py          — Multi-chain Web3 connections
orderbook/fetcher.py          — Order book depth + analysis
api/server.py                 — FastAPI REST + WebSocket
dashboard.html                — Main control dashboard
trading.html                  — TradingView charts + order book
network.html                  — Agent network visualization
config.py                     — All configuration + safety

---

## Installation Details

### Windows

1. Install Python 3.10+ from [python.org](https://python.org/downloads) — **check "Add to PATH"**
2. Install Git from [git-scm.com](https://git-scm.com/downloads)
3. Open PowerShell:
git clone https://github.com/RudeCane/orcl-agent-protocol.git
cd orcl-agent-protocol
pip install -r requirements.txt
python main.py

4. Open `dashboard.html` in Chrome

### Mac / Linux
```bash
git clone https://github.com/RudeCane/orcl-agent-protocol.git
cd orcl-agent-protocol
pip3 install -r requirements.txt
python3 main.py
```

### API Keys (optional — only for live trading)
```powershell
$env:WALLET_ADDRESS = "0x..."
$env:PRIVATE_KEY = "..."
$env:BLOFIN_API_KEY = "..."
$env:BLOFIN_API_SECRET = "..."
$env:BLOFIN_PASSPHRASE = "..."
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `pip not recognized` | Reinstall Python, check "Add to PATH" |
| `git not recognized` | Reopen PowerShell after installing Git |
| Dashboard shows Offline | Make sure `python main.py` is running |
| Ethereum FAILED | Edit `multichain/chains.py`, use `https://rpc.ankr.com/eth` |
| Port 8000 in use | Change port in `config.py` |

---

## Risk Disclaimer

**ORCL is experimental.** Crypto + leverage = high risk. Agents make autonomous decisions that can lose money. Never trade funds you can't afford to lose. Always start in dry run. Not financial advice.

---

## Links

- [Landing Page](https://rudecane.github.io/orcl-agent-protocol)
- [Documentation](https://rudecanes-organization.gitbook.io/orcl-documentation/)
- [GitHub](https://github.com/RudeCane/orcl-agent-protocol)

## License

MIT
'@
