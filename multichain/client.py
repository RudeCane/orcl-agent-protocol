"""
Multi-Chain Web3 Client — Connect to Base, Ethereum, and BNB Chain simultaneously.
Each chain gets its own Web3 instance and can be queried independently.
"""

import logging
from typing import Dict, Optional
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
from multichain.chains import CHAINS, get_chain

logger = logging.getLogger(__name__)

ERC20_ABI = [
    {"constant": True, "inputs": [{"name": "_owner", "type": "address"}],
     "name": "balanceOf", "outputs": [{"name": "balance", "type": "uint256"}], "type": "function"},
    {"constant": True, "inputs": [], "name": "decimals",
     "outputs": [{"name": "", "type": "uint8"}], "type": "function"},
    {"constant": True, "inputs": [], "name": "symbol",
     "outputs": [{"name": "", "type": "string"}], "type": "function"},
]


class ChainConnection:
    """Single chain connection."""

    def __init__(self, chain_key, chain_config):
        self.chain_key = chain_key
        self.config = chain_config
        self.w3 = Web3(Web3.HTTPProvider(chain_config["rpc_url"]))

        # PoA middleware for Base and BNB
        if chain_key in ("base", "bnb"):
            self.w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

    @property
    def is_connected(self):
        try:
            return self.w3.is_connected()
        except Exception:
            return False

    @property
    def block_number(self):
        try:
            return self.w3.eth.block_number
        except Exception:
            return 0

    def get_native_balance(self, address):
        try:
            bal = self.w3.eth.get_balance(Web3.to_checksum_address(address))
            return float(self.w3.from_wei(bal, "ether"))
        except Exception as e:
            logger.error(f"[{self.config['name']}] Balance error: {e}")
            return 0.0

    def get_token_balance(self, token_address, wallet_address):
        try:
            contract = self.w3.eth.contract(
                address=Web3.to_checksum_address(token_address), abi=ERC20_ABI
            )
            raw = contract.functions.balanceOf(Web3.to_checksum_address(wallet_address)).call()
            decimals = contract.functions.decimals().call()
            return raw / (10 ** decimals)
        except Exception as e:
            logger.error(f"[{self.config['name']}] Token balance error: {e}")
            return 0.0

    def get_gas_price_gwei(self):
        try:
            return float(self.w3.from_wei(self.w3.eth.gas_price, "gwei"))
        except Exception:
            return 999.0


class MultiChainClient:
    """
    Manages connections to multiple chains.
    
    Usage:
        client = MultiChainClient()
        client.connect("base")
        client.connect("ethereum")
        client.connect("bnb")
        
        bal = client.get_native_balance("ethereum", "0x...")
    """

    def __init__(self):
        self.connections: Dict[str, ChainConnection] = {}

    def connect(self, chain_key):
        """Connect to a chain."""
        config = get_chain(chain_key)
        if not config:
            logger.error(f"Unknown chain: {chain_key}")
            return False

        key = chain_key.lower()
        # Normalize aliases
        for k, v in CHAINS.items():
            if v == config:
                key = k
                break

        conn = ChainConnection(key, config)
        self.connections[key] = conn

        status = "CONNECTED" if conn.is_connected else "FAILED"
        logger.info(f"[MULTICHAIN] {config['name']}: {status} (block: {conn.block_number})")
        return conn.is_connected

    def connect_all(self):
        """Connect to all supported chains."""
        results = {}
        for chain_key in CHAINS:
            results[chain_key] = self.connect(chain_key)
        return results

    def get_connection(self, chain_key) -> Optional[ChainConnection]:
        """Get a chain connection."""
        key = chain_key.lower()
        aliases = {"eth": "ethereum", "bsc": "bnb", "binance": "bnb"}
        key = aliases.get(key, key)
        return self.connections.get(key)

    def get_native_balance(self, chain_key, address):
        conn = self.get_connection(chain_key)
        if not conn:
            return 0.0
        return conn.get_native_balance(address)

    def get_token_balance(self, chain_key, token_address, wallet_address):
        conn = self.get_connection(chain_key)
        if not conn:
            return 0.0
        return conn.get_token_balance(token_address, wallet_address)

    def get_gas_price(self, chain_key):
        conn = self.get_connection(chain_key)
        if not conn:
            return 999.0
        return conn.get_gas_price_gwei()

    def get_status(self):
        """Status of all chain connections."""
        status = {}
        for key, conn in self.connections.items():
            status[key] = {
                "name": conn.config["name"],
                "chain_id": conn.config["chain_id"],
                "connected": conn.is_connected,
                "block": conn.block_number,
                "gas_gwei": round(conn.get_gas_price_gwei(), 2),
                "native_token": conn.config["native_token"],
                "perp_dex": conn.config.get("perp_dex", "none"),
            }
        return status

    def get_connected_chains(self):
        """List connected chain keys."""
        return [k for k, c in self.connections.items() if c.is_connected]


# Global instance
multichain_client = MultiChainClient()
