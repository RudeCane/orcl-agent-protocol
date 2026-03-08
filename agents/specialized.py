"""Specialized Agents — Liquidity, Market, Treasury."""
from agents.base_agent import BaseAgent

class LiquidityAgent(BaseAgent):
    def __init__(self, tokens: list, poll_interval: int = 30):
        super().__init__("liquidity_agent", tokens, poll_interval)

class MarketAgent(BaseAgent):
    def __init__(self, tokens: list, poll_interval: int = 15):
        super().__init__("market_agent", tokens, poll_interval)

class TreasuryAgent(BaseAgent):
    def __init__(self, tokens: list, poll_interval: int = 60):
        super().__init__("treasury_agent", tokens, poll_interval)
