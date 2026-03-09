import time, logging, requests
from typing import Dict, List, Optional
logger = logging.getLogger(__name__)
BLOFIN_API = "https://openapi.blofin.com/api/v1"

class OrderBook:
    def __init__(self, inst_id, bids, asks, timestamp=None):
        self.inst_id = inst_id
        self.bids = bids
        self.asks = asks
        self.timestamp = timestamp or time.time()
    @property
    def best_bid(self): return float(self.bids[0][0]) if self.bids else 0
    @property
    def best_ask(self): return float(self.asks[0][0]) if self.asks else 0
    @property
    def spread(self): return self.best_ask - self.best_bid if self.best_bid and self.best_ask else 0
    @property
    def spread_pct(self): return (self.spread / self.best_ask) * 100 if self.best_ask else 0
    @property
    def mid_price(self): return (self.best_bid + self.best_ask) / 2 if self.best_bid and self.best_ask else 0
    def bid_depth(self, levels=None):
        entries = self.bids[:levels] if levels else self.bids
        return sum(float(b[0]) * float(b[1]) for b in entries)
    def ask_depth(self, levels=None):
        entries = self.asks[:levels] if levels else self.asks
        return sum(float(a[0]) * float(a[1]) for a in entries)
    def imbalance(self, levels=10):
        bid_vol = self.bid_depth(levels)
        ask_vol = self.ask_depth(levels)
        total = bid_vol + ask_vol
        return (bid_vol - ask_vol) / total if total else 0
    def wall_detection(self, threshold_mult=3.0):
        walls = {"bids": [], "asks": []}
        if self.bids:
            avg = sum(float(b[1]) for b in self.bids) / len(self.bids)
            for b in self.bids:
                if float(b[1]) > avg * threshold_mult:
                    walls["bids"].append({"price": float(b[0]), "size": float(b[1]), "usd": float(b[0]) * float(b[1])})
        if self.asks:
            avg = sum(float(a[1]) for a in self.asks) / len(self.asks)
            for a in self.asks:
                if float(a[1]) > avg * threshold_mult:
                    walls["asks"].append({"price": float(a[0]), "size": float(a[1]), "usd": float(a[0]) * float(a[1])})
        return walls
    def support_resistance(self, levels=20):
        support, resistance = [], []
        if self.bids:
            for b in sorted(self.bids[:levels], key=lambda x: float(x[1]), reverse=True)[:3]:
                support.append({"price": float(b[0]), "size": float(b[1])})
        if self.asks:
            for a in sorted(self.asks[:levels], key=lambda x: float(x[1]), reverse=True)[:3]:
                resistance.append({"price": float(a[0]), "size": float(a[1])})
        return {"support": support, "resistance": resistance}
    def to_dict(self):
        return {"inst_id": self.inst_id, "best_bid": self.best_bid, "best_ask": self.best_ask,
            "spread": round(self.spread, 6), "spread_pct": round(self.spread_pct, 4),
            "mid_price": round(self.mid_price, 6), "bid_depth_usd": round(self.bid_depth(), 2),
            "ask_depth_usd": round(self.ask_depth(), 2), "imbalance": round(self.imbalance(), 4),
            "walls": self.wall_detection(), "support_resistance": self.support_resistance(),
            "bid_levels": len(self.bids), "ask_levels": len(self.asks), "timestamp": self.timestamp,
            "signals": []}
    def chart_data(self):
        return {"bids": [[float(b[0]), float(b[1])] for b in self.bids],
            "asks": [[float(a[0]), float(a[1])] for a in self.asks], "mid_price": self.mid_price}

class OrderBookFetcher:
    def __init__(self):
        self.cache = {}
        self.cache_ttl = 15
        self.history = {}
    def get_blofin_orderbook(self, inst_id="BTC-USDT", depth=20):
        ck = f"blofin_{inst_id}"
        if ck in self.cache and time.time() - self.cache[ck].timestamp < self.cache_ttl:
            return self.cache[ck]
        try:
            resp = requests.get(f"{BLOFIN_API}/market/books", params={"instId": inst_id, "size": depth}, timeout=5)
            data = resp.json()
            if data.get("code") != "0" or not data.get("data"): return None
            bd = data["data"][0] if isinstance(data["data"], list) else data["data"]
            ob = OrderBook(inst_id=inst_id, bids=bd.get("bids", []), asks=bd.get("asks", []))
            self.cache[ck] = ob
            return ob
        except Exception as e:
            logger.error(f"OrderBook fetch error: {e}")
            return None
    def get_dex_orderbook(self, token_address, chain="base"):
        try:
            resp = requests.get(f"https://api.dexscreener.com/latest/dex/tokens/{token_address}", timeout=5)
            data = resp.json()
            if not data.get("pairs"): return None
            pair = max(data["pairs"], key=lambda p: float(p.get("liquidity", {}).get("usd", 0)))
            price = float(pair.get("priceUsd", 0))
            liq = float(pair.get("liquidity", {}).get("usd", 0))
            if not price or not liq: return None
            bids, asks = [], []
            pool = liq / 2
            for i in range(20):
                pct = (i + 1) * 0.1
                bp = price * (1 - pct / 100)
                ap = price * (1 + pct / 100)
                d = pool * (0.15 / (i + 1))
                bids.append([str(round(bp, 8)), str(round(d / bp, 6))])
                asks.append([str(round(ap, 8)), str(round(d / ap, 6))])
            sym = pair.get("baseToken", {}).get("symbol", "???")
            return OrderBook(inst_id=f"{sym}/USD", bids=bids, asks=asks)
        except Exception as e:
            logger.error(f"DEX OB error: {e}")
            return None
    def analyze(self, inst_id=None, token_address=None, chain="base"):
        ob = None
        if inst_id and "-USDT" in inst_id: ob = self.get_blofin_orderbook(inst_id)
        elif token_address: ob = self.get_dex_orderbook(token_address, chain)
        if not ob: return None
        analysis = ob.to_dict()
        imb = ob.imbalance()
        walls = ob.wall_detection()
        signals = []
        if imb > 0.3: signals.append({"type": "bullish_imbalance", "strength": imb})
        elif imb < -0.3: signals.append({"type": "bearish_imbalance", "strength": abs(imb)})
        if walls["bids"]: signals.append({"type": "buy_wall", "count": len(walls["bids"]), "largest": max(w["usd"] for w in walls["bids"])})
        if walls["asks"]: signals.append({"type": "sell_wall", "count": len(walls["asks"]), "largest": max(w["usd"] for w in walls["asks"])})
        analysis["signals"] = signals
        return analysis
    def get_history(self, key, limit=50):
        return self.history.get(key, [])[-limit:]

orderbook_fetcher = OrderBookFetcher()
