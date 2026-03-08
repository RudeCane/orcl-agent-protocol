"""
Multi-Chain Observer — Fetch market data from Base, Ethereum, and BNB Chain.
Uses DexScreener API which supports all three chains.
"""

import time
import logging
import requests
from multichain.chains import CHAINS, get_chain

logger = logging.getLogger(__name__)

DEXSCREENER_BASE = "https://api.dexscreener.com/latest/dex"


def get_token_data_multichain(token_address, chain_key=None):
    """
    Fetch token data from DexScreener.
    If chain_key is provided, filters to that chain.
    If not, returns the highest-liquidity pair across all chains.
    """
    url = f"{DEXSCREENER_BASE}/tokens/{token_address}"

    for attempt in range(3):
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            if not data.get("pairs"):
                return None

            pairs = data["pairs"]

            # Filter by chain if specified
            if chain_key:
                config = get_chain(chain_key)
                if config:
                    chain_filter = config["dex_screener_chain"]
                    filtered = [p for p in pairs if p.get("chainId") == chain_filter]
                    if filtered:
                        pairs = filtered

            # Pick highest liquidity pair
            pair = max(pairs, key=lambda p: float(p.get("liquidity", {}).get("usd", 0)))

            return {
                "token": token_address,
                "chain": pair.get("chainId", "unknown"),
                "symbol": pair.get("baseToken", {}).get("symbol", "???"),
                "price_usd": float(pair.get("priceUsd", 0)),
                "price_change_1h": float(pair.get("priceChange", {}).get("h1", 0)),
                "price_change_24h": float(pair.get("priceChange", {}).get("h24", 0)),
                "liquidity_usd": float(pair.get("liquidity", {}).get("usd", 0)),
                "volume_24h": float(pair.get("volume", {}).get("h24", 0)),
                "buys_24h": int(pair.get("txns", {}).get("h24", {}).get("buys", 0)),
                "sells_24h": int(pair.get("txns", {}).get("h24", {}).get("sells", 0)),
                "pair_address": pair.get("pairAddress", ""),
                "dex": pair.get("dexId", "unknown"),
                "timestamp": time.time(),
            }

        except requests.RequestException as e:
            logger.warning(f"[OBSERVER] API error (attempt {attempt + 1}): {e}")
            time.sleep(2 ** attempt)

    return None


def scan_chain_tokens(chain_key, limit=10):
    """
    Scan trending tokens on a specific chain.
    Returns top tokens by volume.
    """
    config = get_chain(chain_key)
    if not config:
        return []

    chain_id = config["dex_screener_chain"]
    url = f"https://api.dexscreener.com/latest/dex/search?q={chain_id}"

    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        pairs = data.get("pairs", [])

        # Filter to this chain and sort by volume
        chain_pairs = [p for p in pairs if p.get("chainId") == chain_id]
        chain_pairs.sort(key=lambda p: float(p.get("volume", {}).get("h24", 0)), reverse=True)

        results = []
        seen = set()
        for p in chain_pairs[:limit * 2]:
            addr = p.get("baseToken", {}).get("address", "")
            if addr in seen:
                continue
            seen.add(addr)
            results.append({
                "token": addr,
                "symbol": p.get("baseToken", {}).get("symbol", "???"),
                "price_usd": float(p.get("priceUsd", 0)),
                "volume_24h": float(p.get("volume", {}).get("h24", 0)),
                "liquidity_usd": float(p.get("liquidity", {}).get("usd", 0)),
                "chain": chain_id,
            })
            if len(results) >= limit:
                break

        return results

    except Exception as e:
        logger.error(f"[OBSERVER] Scan error for {chain_key}: {e}")
        return []
