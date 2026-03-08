"""AI Agent Protocol — Configuration for Base Chain"""
import os
from dataclasses import dataclass, field
from typing import List

@dataclass
class ChainConfig:
    name: str = "Base"
    chain_id: int = 8453
    rpc_url: str = os.getenv("BASE_RPC_URL", "https://mainnet.base.org")
    explorer_url: str = "https://basescan.org"
    native_token: str = "ETH"
    wrapped_native: str = "0x4200000000000000000000000000000000000006"
    usdc_address: str = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"

@dataclass
class SafetyConfig:
    max_trade_size_usd: float = 100.0
    daily_loss_limit_usd: float = 250.0
    max_slippage_percent: float = 2.0
    min_liquidity_usd: float = 50000.0
    max_gas_price_gwei: float = 5.0
    cooldown_seconds: int = 30
    whitelisted_tokens: List[str] = field(default_factory=lambda: [
        "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        "0x4200000000000000000000000000000000000006",
        "0x50c5725949A6F0c72E6C4a641F24049A917DB0Cb",
    ])
    require_whitelist: bool = True
    dry_run: bool = True

@dataclass
class ObserverConfig:
    poll_interval_seconds: int = 15
    dexscreener_base_url: str = "https://api.dexscreener.com/latest/dex"
    price_history_window: int = 50

@dataclass
class StrategyConfig:
    short_window: int = 5
    long_window: int = 20
    rsi_period: int = 14
    rsi_overbought: float = 70.0
    rsi_oversold: float = 30.0
    low_liquidity_usd: float = 50000.0
    high_liquidity_usd: float = 500000.0

@dataclass
class APIConfig:
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: List[str] = field(default_factory=lambda: [
        "*"
    ])

@dataclass
class Config:
    chain: ChainConfig = field(default_factory=ChainConfig)
    safety: SafetyConfig = field(default_factory=SafetyConfig)
    observer: ObserverConfig = field(default_factory=ObserverConfig)
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    api: APIConfig = field(default_factory=APIConfig)
    wallet_address: str = os.getenv("WALLET_ADDRESS", "")
    private_key: str = os.getenv("PRIVATE_KEY", "")

    # BloFin Exchange (get keys from https://blofin.com/en/account/apis)
    blofin_api_key: str = os.getenv("BLOFIN_API_KEY", "")
    blofin_api_secret: str = os.getenv("BLOFIN_API_SECRET", "")
    blofin_passphrase: str = os.getenv("BLOFIN_PASSPHRASE", "")

config = Config()
