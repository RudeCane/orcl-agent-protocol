"""Observer Module — Collects market data from DexScreener + on-chain."""
import time
import logging
import requests
from typing import Dict, Optional, List
from dataclasses import dataclass, field
from config import config

logger = logging.getLogger(__name__)

@dataclass
class TokenSnapshot:
    token_address: str
    symbol: str = ""
    price_usd: float = 0.0
    liquidity_usd: float = 0.0
    volume_24h: float = 0.0
    price_change_5m: float = 0.0
    price_change_1h: float = 0.0
    price_change_24h: float = 0.0
    pair_address: str = ""
    dex_name: str = ""
    timestamp: float = field(default_factory=time.time)

class Observer:
    def __init__(self):
        self.base_url = config.observer.dexscreener_base_url
        self.price_history: Dict[str, List[float]] = {}
        self.max_history = config.observer.price_history_window
        self._session = requests.Session()
        self._session.headers.update({"Accept": "application/json"})

    def get_token_data(self, token_address: str) -> Optional[TokenSnapshot]:
        try:
            url = f"{self.base_url}/tokens/{token_address}"
            resp = self._session.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            pairs = data.get("pairs", [])
            if not pairs:
                logger.warning(f"No pairs found for {token_address}")
                return None

            base_pairs = [p for p in pairs if p.get("chainId") == "base"]
            if not base_pairs:
                base_pairs = pairs

            pair = max(base_pairs, key=lambda p: p.get("liquidity", {}).get("usd", 0))
            snapshot = TokenSnapshot(
                token_address=token_address,
                symbol=pair.get("baseToken", {}).get("symbol", "???"),
                price_usd=float(pair.get("priceUsd", 0)),
                liquidity_usd=float(pair.get("liquidity", {}).get("usd", 0)),
                volume_24h=float(pair.get("volume", {}).get("h24", 0)),
                price_change_5m=float(pair.get("priceChange", {}).get("m5", 0)),
                price_change_1h=float(pair.get("priceChange", {}).get("h1", 0)),
                price_change_24h=float(pair.get("priceChange", {}).get("h24", 0)),
                pair_address=pair.get("pairAddress", ""),
                dex_name=pair.get("dexId", ""),
            )
            self._record_price(token_address, snapshot.price_usd)
            return snapshot
        except requests.RequestException as e:
            logger.error(f"DexScreener API error: {e}")
            return None
        except (KeyError, IndexError, ValueError) as e:
            logger.error(f"Parse error: {e}")
            return None

    def get_trending_tokens(self, limit: int = 10) -> List[Dict]:
        try:
            url = f"{self.base_url}/search?q=base"
            resp = self._session.get(url, timeout=10)
            resp.raise_for_status()
            pairs = resp.json().get("pairs", [])
            base_pairs = [p for p in pairs if p.get("chainId") == "base"]
            sorted_pairs = sorted(base_pairs, key=lambda p: p.get("volume", {}).get("h24", 0), reverse=True)
            return [{
                "symbol": p.get("baseToken", {}).get("symbol", "???"),
                "address": p.get("baseToken", {}).get("address", ""),
                "price": p.get("priceUsd", "0"),
                "volume_24h": p.get("volume", {}).get("h24", 0),
                "liquidity": p.get("liquidity", {}).get("usd", 0),
            } for p in sorted_pairs[:limit]]
        except Exception as e:
            logger.error(f"Trending error: {e}")
            return []

    def get_price_history(self, token_address: str) -> List[float]:
        return self.price_history.get(token_address, [])

    def _record_price(self, token_address: str, price: float):
        if token_address not in self.price_history:
            self.price_history[token_address] = []
        h = self.price_history[token_address]
        h.append(price)
        if len(h) > self.max_history:
            self.price_history[token_address] = h[-self.max_history:]
