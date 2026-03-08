"""AI Agent Protocol — Main Entry Point"""
import uvicorn
from api.server import app
from config import config

if __name__ == "__main__":
    print(f"""
    ╔══════════════════════════════════════════╗
    ║     AI AGENT PROTOCOL v0.1              ║
    ║     Base Chain Autonomous Agent          ║
    ║                                          ║
    ║     Dashboard: http://localhost:8000      ║
    ║     API Docs:  http://localhost:8000/docs ║
    ╚══════════════════════════════════════════╝

    Chain:      {config.chain.name} (ID: {config.chain.chain_id})
    Dry Run:    {config.safety.dry_run}
    Max Trade:  ${config.safety.max_trade_size_usd}
    Loss Limit: ${config.safety.daily_loss_limit_usd}/day
    """)
    uvicorn.run("api.server:app", host=config.api.host, port=config.api.port, reload=True)
