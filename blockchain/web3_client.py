"""Blockchain connection layer for Base chain."""
import logging
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
from config import config

logger = logging.getLogger(__name__)

class Web3Client:
    def __init__(self):
        self.w3 = Web3(Web3.HTTPProvider(config.chain.rpc_url))
        self.w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
        self.chain_id = config.chain.chain_id

    @property
    def is_connected(self) -> bool:
        try:
            return self.w3.is_connected()
        except Exception:
            return False

    def get_eth_balance(self, address: str) -> float:
        try:
            bal = self.w3.eth.get_balance(Web3.to_checksum_address(address))
            return float(self.w3.from_wei(bal, "ether"))
        except Exception as e:
            logger.error(f"Balance error: {e}")
            return 0.0

    def get_token_balance(self, token_address: str, wallet_address: str) -> float:
        abi = [
            {"constant":True,"inputs":[{"name":"_owner","type":"address"}],
             "name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"},
            {"constant":True,"inputs":[],"name":"decimals",
             "outputs":[{"name":"","type":"uint8"}],"type":"function"},
        ]
        try:
            c = self.w3.eth.contract(address=Web3.to_checksum_address(token_address), abi=abi)
            decimals = c.functions.decimals().call()
            raw = c.functions.balanceOf(Web3.to_checksum_address(wallet_address)).call()
            return raw / (10 ** decimals)
        except Exception as e:
            logger.error(f"Token balance error: {e}")
            return 0.0

    def get_gas_price_gwei(self) -> float:
        try:
            return float(self.w3.from_wei(self.w3.eth.gas_price, "gwei"))
        except Exception:
            return 999.0

    def send_transaction(self, tx: dict) -> str:
        if config.safety.dry_run:
            logger.info(f"[DRY RUN] Would send tx: {tx}")
            return "0x_dry_run_" + "0" * 60
        signed = self.w3.eth.account.sign_transaction(tx, config.private_key)
        tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        return self.w3.to_hex(tx_hash)

    def wait_for_receipt(self, tx_hash: str, timeout: int = 120):
        if config.safety.dry_run:
            return {"status": 1, "transactionHash": tx_hash}
        return self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=timeout)

web3_client = Web3Client()
