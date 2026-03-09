import os

def patch_server():
    sp = os.path.join("api", "server.py")
    if not os.path.exists(sp):
        print("ERROR: api/server.py not found")
        return False
    with open(sp, "r", encoding="utf-8") as fh:
        content = fh.read()
    if "BinanceAgent" in content:
        print("Already patched.")
        return True

    # Add import
    marker = "from config import config"
    if "from binance_integration" not in content:
        content = content.replace(marker, marker + """
from binance_integration.client import binance_client, binance_us_client, BinanceClient
from binance_integration.agent import BinanceAgent""")

    # Add to task endpoint
    old = """    else:
        return {"status": "unknown_task","""
    new = """    elif "binance us" in instruction or "binance.us" in instruction:
        pairs = []
        for p in ["btc", "eth", "sol", "bnb", "xrp", "doge", "ada", "avax", "link", "arb", "op", "sui"]:
            if p in instruction:
                pairs.append(f"{p.upper()}USDT")
        if not pairs:
            pairs = ["BTCUSDT", "ETHUSDT"]
        agent = BinanceAgent(pairs=pairs, use_us=True)
    elif "binance" in instruction:
        pairs = []
        for p in ["btc", "eth", "sol", "bnb", "xrp", "doge", "ada", "avax", "link", "arb", "op", "sui"]:
            if p in instruction:
                pairs.append(f"{p.upper()}USDT")
        if not pairs:
            pairs = ["BTCUSDT", "ETHUSDT"]
        agent = BinanceAgent(pairs=pairs, use_us=False)
    else:
        return {"status": "unknown_task","""
    content = content.replace(old, new)

    # Add routes
    routes = """

@app.get("/api/binance/ticker/{symbol}")
def get_binance_ticker(symbol: str, us: bool = False):
    client = binance_us_client if us else binance_client
    return client.get_ticker(symbol) or {"error": "Not found"}

@app.get("/api/binance/orderbook/{symbol}")
def get_binance_orderbook(symbol: str, limit: int = 20, us: bool = False):
    client = binance_us_client if us else binance_client
    return client.get_orderbook(symbol, limit) or {"error": "Not found"}

@app.get("/api/binance/candles/{symbol}")
def get_binance_candles(symbol: str, interval: str = "5m", limit: int = 100, us: bool = False):
    client = binance_us_client if us else binance_client
    return client.get_klines(symbol, interval, limit)

@app.get("/api/binance/pairs")
def get_binance_pairs(us: bool = False):
    client = binance_us_client if us else binance_client
    return client.POPULAR_PAIRS

@app.get("/api/binance/status")
def get_binance_status():
    agents = {}
    for aid, a in globals().get("agents", {}).items():
        if hasattr(a, "client") and hasattr(a.client, "exchange"):
            if "binance" in a.client.exchange:
                agents[aid] = a.get_state()
    return agents

"""
    ws_marker = '@app.websocket("/ws")'
    if ws_marker in content:
        content = content.replace(ws_marker, routes + ws_marker)
    else:
        content += routes

    with open(sp, "w", encoding="utf-8") as fh:
        fh.write(content)
    print("Patched api/server.py with Binance routes.")
    return True

if __name__ == "__main__":
    print("Adding Binance + Binance.US support...")
    if patch_server():
        print("Done!")
        print("")
        print("From the dashboard, try:")
        print('  "binance monitor BTC and ETH"')
        print('  "binance us watch SOL"')
        print("")
        print("New endpoints:")
        print("  GET /api/binance/ticker/BTCUSDT")
        print("  GET /api/binance/orderbook/BTCUSDT")
        print("  GET /api/binance/candles/BTCUSDT?interval=5m")
        print("  GET /api/binance/pairs")
