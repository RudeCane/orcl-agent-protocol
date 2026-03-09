import os

def patch_server():
    sp = os.path.join("api", "server.py")
    if not os.path.exists(sp):
        print("ERROR: api/server.py not found")
        return False
    with open(sp, "r", encoding="utf-8") as fh:
        content = fh.read()
    if "orderbook_fetcher" in content:
        print("Already patched.")
        return True
    marker = "from config import config"
    if "from orderbook" not in content:
        content = content.replace(marker, marker + "\nfrom orderbook.fetcher import orderbook_fetcher")

    routes = '''

@app.get("/api/orderbook/blofin/{inst_id}")
def get_blofin_orderbook(inst_id: str, depth: int = 20):
    ob = orderbook_fetcher.get_blofin_orderbook(inst_id, depth)
    if not ob: return {"error": f"No order book for {inst_id}"}
    return ob.to_dict()

@app.get("/api/orderbook/blofin/{inst_id}/chart")
def get_blofin_orderbook_chart(inst_id: str, depth: int = 20):
    ob = orderbook_fetcher.get_blofin_orderbook(inst_id, depth)
    if not ob: return {"error": f"No order book for {inst_id}"}
    return ob.chart_data()

@app.get("/api/orderbook/dex/{token_address}")
def get_dex_orderbook(token_address: str, chain: str = "base"):
    ob = orderbook_fetcher.get_dex_orderbook(token_address, chain)
    if not ob: return {"error": "No data found"}
    return ob.to_dict()

@app.get("/api/orderbook/analyze/{inst_id}")
def analyze_orderbook(inst_id: str):
    if "-USDT" in inst_id: result = orderbook_fetcher.analyze(inst_id=inst_id)
    else: result = orderbook_fetcher.analyze(token_address=inst_id)
    if not result: return {"error": "No data"}
    return result

@app.get("/api/candles/{inst_id}")
def get_candles(inst_id: str, bar: str = "1m", limit: int = 100):
    import requests as req
    try:
        resp = req.get("https://openapi.blofin.com/api/v1/market/candles", params={"instId": inst_id, "bar": bar, "limit": limit}, timeout=10)
        data = resp.json()
        if data.get("code") == "0" and data.get("data"):
            candles = [{"time": int(c[0]) // 1000, "open": float(c[1]), "high": float(c[2]), "low": float(c[3]), "close": float(c[4]), "volume": float(c[5])} for c in data["data"]]
            candles.reverse()
            return candles
        return []
    except Exception as e:
        return {"error": str(e)}

'''
    ws_marker = '@app.websocket("/ws")'
    if ws_marker in content:
        content = content.replace(ws_marker, routes + ws_marker)
    else:
        content += routes
    with open(sp, "w", encoding="utf-8") as fh:
        fh.write(content)
    print("Patched api/server.py with order book and candle routes.")
    return True

if __name__ == "__main__":
    print("Adding order book support...")
    if patch_server():
        print("Done!")
