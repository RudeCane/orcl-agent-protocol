"""
Multi-Chain Configuration — Base, Ethereum, BNB Chain
Defines RPC endpoints, contract addresses, and DEX routers for each chain.
"""

CHAINS = {
    "base": {
        "name": "Base",
        "chain_id": 8453,
        "rpc_url": "https://mainnet.base.org",
        "explorer": "https://basescan.org",
        "native_token": "ETH",
        "wrapped_native": "0x4200000000000000000000000000000000000006",
        "usdc": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        "usdt": "",
        "dai": "0x50c5725949A6F0c72E6C4a641F24049A917DB0Cb",
        "dex_screener_chain": "base",
        "perp_dex": "avantis",
        "perp_dex_url": "https://www.avantisfi.com",
        "default_tokens": [
            "0x4200000000000000000000000000000000000006",  # WETH
            "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",  # USDC
        ],
    },
    "ethereum": {
        "name": "Ethereum",
        "chain_id": 1,
        "rpc_url": "https://eth.llamarpc.com",
        "explorer": "https://etherscan.io",
        "native_token": "ETH",
        "wrapped_native": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
        "usdc": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
        "usdt": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
        "dai": "0x6B175474E89094C44Da98b954EedeAC495271d0F",
        "dex_screener_chain": "ethereum",
        "perp_dex": "hyperliquid",
        "perp_dex_url": "https://app.hyperliquid.xyz",
        "default_tokens": [
            "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",  # WETH
            "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",  # USDC
        ],
    },
    "bnb": {
        "name": "BNB Chain",
        "chain_id": 56,
        "rpc_url": "https://bsc-dataseed1.binance.org",
        "explorer": "https://bscscan.com",
        "native_token": "BNB",
        "wrapped_native": "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",
        "usdc": "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d",
        "usdt": "0x55d398326f99059fF775485246999027B3197955",
        "dai": "0x1AF3F329e8BE154074D8769D1FFa4eE058B1DBc3",
        "dex_screener_chain": "bsc",
        "perp_dex": "aster",
        "perp_dex_url": "https://aster.finance",
        "default_tokens": [
            "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",  # WBNB
            "0x55d398326f99059fF775485246999027B3197955",  # USDT
        ],
    },
}


def get_chain(chain_name):
    """Get chain config by name."""
    key = chain_name.lower().strip()
    # Handle aliases
    aliases = {
        "eth": "ethereum",
        "mainnet": "ethereum",
        "bsc": "bnb",
        "binance": "bnb",
        "bnb chain": "bnb",
        "bnb smart chain": "bnb",
    }
    key = aliases.get(key, key)
    return CHAINS.get(key)


def get_all_chains():
    """Get all supported chains."""
    return {k: v["name"] for k, v in CHAINS.items()}
