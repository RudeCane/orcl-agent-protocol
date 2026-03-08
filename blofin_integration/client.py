"""
BloFin Exchange Client — Perpetual Futures Trading
Handles authentication, placing orders, managing positions, and account queries.

Setup:
    pip install blofin

    Get API keys from: https://blofin.com/en/account/apis
    - Create key with TRADE permission
    - Bind to your IP for security

Usage:
    from blofin_integration.client import BloFinTrader
    
    trader = BloFinTrader(
        api_key="your_key",
        api_secret="your_secret",
        passphrase="your_passphrase"
    )
    trader.open_long("BTC-USDT", leverage=5, size=0.1, stop_loss_pct=3)
"""

import time
import logging
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)


class BloFinTrader:
    """
    BloFin perpetual futures trader.
    Wraps the BloFin SDK with safety checks and simplified interface.
    """

    def __init__(
        self,
        api_key: str = "",
        api_secret: str = "",
        passphrase: str = "",
        dry_run: bool = True,
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.passphrase = passphrase
        self.dry_run = dry_run
        self.client = None
        self.connected = False
        self.trade_log: List[dict] = []

        if api_key and api_secret and passphrase:
            self._connect()

    def _connect(self):
        """Initialize BloFin SDK client."""
        try:
            from blofin import BloFinClient
            self.client = BloFinClient(
                api_key=self.api_key,
                api_secret=self.api_secret,
                passphrase=self.passphrase,
                use_server_time=True,
            )
            # Test connection
            balance = self.client.account.get_balance(account_type="futures")
            self.connected = True
            logger.info("[BLOFIN] Connected successfully")
        except ImportError:
            logger.error("[BLOFIN] SDK not installed. Run: pip install blofin")
            self.connected = False
        except Exception as e:
            logger.error(f"[BLOFIN] Connection failed: {e}")
            self.connected = False

    # ============================================================
    # ACCOUNT
    # ============================================================

    def get_balance(self):
        """Get futures account balance."""
        if not self.client:
            return {"error": "Not connected"}
        try:
            result = self.client.account.get_balance(account_type="futures")
            return result
        except Exception as e:
            logger.error(f"[BLOFIN] Balance error: {e}")
            return {"error": str(e)}

    def get_positions(self):
        """Get all open positions."""
        if not self.client:
            return []
        try:
            result = self.client.account.get_positions()
            return result if result else []
        except Exception as e:
            logger.error(f"[BLOFIN] Positions error: {e}")
            return []

    def get_ticker(self, inst_id="BTC-USDT"):
        """Get current price for an instrument."""
        try:
            if self.client:
                result = self.client.public.get_tickers(inst_id=inst_id)
                if result and "data" in result:
                    data = result["data"]
                    if isinstance(data, list) and len(data) > 0:
                        return {
                            "inst_id": inst_id,
                            "last": float(data[0].get("last", 0)),
                            "bid": float(data[0].get("bidPx", 0)),
                            "ask": float(data[0].get("askPx", 0)),
                            "volume_24h": float(data[0].get("vol24h", 0)),
                            "change_24h": float(data[0].get("changePercent24h", 0)),
                        }
            # Fallback: use public API without auth
            import requests
            resp = requests.get(
                f"https://openapi.blofin.com/api/v1/market/tickers?instId={inst_id}",
                timeout=10,
            )
            data = resp.json().get("data", [])
            if data:
                return {
                    "inst_id": inst_id,
                    "last": float(data[0].get("last", 0)),
                    "bid": float(data[0].get("bidPx", 0)),
                    "ask": float(data[0].get("askPx", 0)),
                    "volume_24h": float(data[0].get("vol24h", 0)),
                    "change_24h": float(data[0].get("changePercent24h", 0)),
                }
        except Exception as e:
            logger.error(f"[BLOFIN] Ticker error: {e}")
        return None

    def get_instruments(self):
        """Get available trading instruments."""
        try:
            if self.client:
                return self.client.public.get_instruments(inst_type="SWAP")
            import requests
            resp = requests.get(
                "https://openapi.blofin.com/api/v1/market/instruments?instType=SWAP",
                timeout=10,
            )
            return resp.json()
        except Exception as e:
            logger.error(f"[BLOFIN] Instruments error: {e}")
            return []

    # ============================================================
    # TRADING
    # ============================================================

    def set_leverage(self, inst_id, leverage, margin_mode="isolated"):
        """Set leverage for an instrument."""
        if not self.client or self.dry_run:
            self._log("SET_LEVERAGE", inst_id, f"{leverage}x {margin_mode}")
            return {"status": "dry_run", "leverage": leverage}
        try:
            result = self.client.account.set_leverage(
                inst_id=inst_id,
                leverage=str(leverage),
                margin_mode=margin_mode,
            )
            self._log("SET_LEVERAGE", inst_id, f"{leverage}x — {result}")
            return result
        except Exception as e:
            logger.error(f"[BLOFIN] Set leverage error: {e}")
            return {"error": str(e)}

    def open_long(
        self,
        inst_id: str,
        size: float,
        leverage: int = 5,
        margin_mode: str = "isolated",
        stop_loss_pct: Optional[float] = None,
        take_profit_pct: Optional[float] = None,
    ):
        """
        Open a long position.
        
        Args:
            inst_id: Trading pair (e.g., "BTC-USDT")
            size: Position size in contracts (min 0.1 for BTC)
            leverage: Leverage multiplier
            margin_mode: "isolated" or "cross"
            stop_loss_pct: Stop-loss percentage below entry
            take_profit_pct: Take-profit percentage above entry
        """
        return self._open_position(
            inst_id=inst_id,
            side="buy",
            size=size,
            leverage=leverage,
            margin_mode=margin_mode,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
        )

    def open_short(
        self,
        inst_id: str,
        size: float,
        leverage: int = 5,
        margin_mode: str = "isolated",
        stop_loss_pct: Optional[float] = None,
        take_profit_pct: Optional[float] = None,
    ):
        """Open a short position."""
        return self._open_position(
            inst_id=inst_id,
            side="sell",
            size=size,
            leverage=leverage,
            margin_mode=margin_mode,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
        )

    def _open_position(
        self, inst_id, side, size, leverage, margin_mode, stop_loss_pct, take_profit_pct
    ):
        """Internal: open a position with safety checks."""
        ticker = self.get_ticker(inst_id)
        entry_price = ticker["last"] if ticker else 0

        # Build order params
        order = {
            "instId": inst_id,
            "marginMode": margin_mode,
            "side": side,
            "orderType": "market",
            "size": str(size),
        }

        # Add TP/SL if specified
        if stop_loss_pct and entry_price:
            if side == "buy":
                sl_price = entry_price * (1 - stop_loss_pct / 100)
            else:
                sl_price = entry_price * (1 + stop_loss_pct / 100)
            order["slTriggerPrice"] = str(round(sl_price, 2))
            order["slOrderPrice"] = "-1"  # Market order for SL

        if take_profit_pct and entry_price:
            if side == "buy":
                tp_price = entry_price * (1 + take_profit_pct / 100)
            else:
                tp_price = entry_price * (1 - take_profit_pct / 100)
            order["tpTriggerPrice"] = str(round(tp_price, 2))
            order["tpOrderPrice"] = "-1"  # Market order for TP

        # Log the trade
        trade_record = {
            "action": "open",
            "inst_id": inst_id,
            "side": side,
            "size": size,
            "leverage": leverage,
            "entry_price": entry_price,
            "stop_loss_pct": stop_loss_pct,
            "take_profit_pct": take_profit_pct,
            "margin_mode": margin_mode,
            "dry_run": self.dry_run,
            "time": time.time(),
        }

        if self.dry_run:
            trade_record["status"] = "dry_run"
            trade_record["order_id"] = f"dry_{int(time.time())}"
            self.trade_log.append(trade_record)
            self._log("OPEN (DRY)", inst_id,
                     f"{side.upper()} {size} @ ${entry_price:.2f} | {leverage}x {margin_mode}")
            return {"status": "dry_run", "order": order, "trade": trade_record}

        if not self.client:
            return {"error": "Not connected to BloFin"}

        try:
            # Set leverage first
            self.set_leverage(inst_id, leverage, margin_mode)

            # Place order
            result = self.client.trade.place_order(**order)

            trade_record["status"] = "placed"
            trade_record["result"] = result
            trade_record["order_id"] = result.get("data", {}).get("orderId", "")
            self.trade_log.append(trade_record)

            self._log("OPEN", inst_id,
                     f"{side.upper()} {size} @ ${entry_price:.2f} | {leverage}x | "
                     f"Order: {trade_record['order_id']}")
            return {"status": "placed", "result": result, "trade": trade_record}

        except Exception as e:
            trade_record["status"] = "error"
            trade_record["error"] = str(e)
            self.trade_log.append(trade_record)
            logger.error(f"[BLOFIN] Order error: {e}")
            return {"error": str(e)}

    def close_position(self, inst_id, side=None):
        """
        Close a position.
        side: "buy" to close short, "sell" to close long. Auto-detects if None.
        """
        if self.dry_run:
            self._log("CLOSE (DRY)", inst_id, f"Close {side or 'auto'}")
            self.trade_log.append({
                "action": "close", "inst_id": inst_id, "side": side,
                "dry_run": True, "time": time.time(),
            })
            return {"status": "dry_run"}

        if not self.client:
            return {"error": "Not connected"}

        try:
            # Get current position to determine size and side
            positions = self.get_positions()
            pos = None
            for p in positions:
                if isinstance(p, dict) and p.get("instId") == inst_id:
                    pos = p
                    break

            if not pos:
                return {"error": f"No position found for {inst_id}"}

            pos_side = pos.get("side", "")
            pos_size = pos.get("positions", pos.get("pos", "0"))
            close_side = "sell" if pos_side == "long" else "buy"

            result = self.client.trade.place_order(
                instId=inst_id,
                marginMode=pos.get("marginMode", "isolated"),
                side=close_side,
                orderType="market",
                size=str(pos_size),
            )

            self.trade_log.append({
                "action": "close", "inst_id": inst_id, "side": close_side,
                "size": pos_size, "dry_run": False, "result": result,
                "time": time.time(),
            })

            self._log("CLOSE", inst_id, f"{close_side} {pos_size}")
            return {"status": "closed", "result": result}

        except Exception as e:
            logger.error(f"[BLOFIN] Close error: {e}")
            return {"error": str(e)}

    def close_all(self):
        """Close all open positions."""
        positions = self.get_positions()
        results = []
        for pos in positions:
            if isinstance(pos, dict):
                inst_id = pos.get("instId", "")
                if inst_id:
                    result = self.close_position(inst_id)
                    results.append(result)
        return results

    # ============================================================
    # STATUS
    # ============================================================

    def get_status(self):
        """Full trader status."""
        positions = self.get_positions()
        open_positions = []
        for p in positions:
            if isinstance(p, dict) and float(p.get("positions", p.get("pos", 0))) != 0:
                open_positions.append({
                    "inst_id": p.get("instId", ""),
                    "side": p.get("side", ""),
                    "size": p.get("positions", p.get("pos", "")),
                    "leverage": p.get("lever", ""),
                    "entry_price": p.get("avgPx", ""),
                    "unrealized_pnl": p.get("upl", ""),
                    "margin": p.get("margin", ""),
                    "liquidation_price": p.get("liqPx", ""),
                })

        return {
            "connected": self.connected,
            "dry_run": self.dry_run,
            "open_positions": open_positions,
            "position_count": len(open_positions),
            "recent_trades": self.trade_log[-20:],
        }

    # ============================================================
    # AVAILABLE PAIRS
    # ============================================================

    POPULAR_PAIRS = [
        "BTC-USDT", "ETH-USDT", "SOL-USDT", "BNB-USDT",
        "XRP-USDT", "DOGE-USDT", "ADA-USDT", "AVAX-USDT",
        "LINK-USDT", "DOT-USDT", "MATIC-USDT", "UNI-USDT",
        "ARB-USDT", "OP-USDT", "APT-USDT", "SUI-USDT",
    ]

    # ============================================================
    # LOGGING
    # ============================================================

    def _log(self, action, inst_id, details):
        dry = "[DRY] " if self.dry_run else ""
        logger.info(f"[BLOFIN] {dry}{action} {inst_id}: {details}")
        print(f"  [BLOFIN] {dry}{action} {inst_id}: {details}")
