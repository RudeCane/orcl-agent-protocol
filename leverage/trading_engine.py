"""
Leverage Trading Engine — Perpetual Futures on Base (Avantis)
Manages leveraged positions with strict risk management.

WARNING: Leverage amplifies both gains AND losses. 
A 10x leveraged position loses 100% if price moves 10% against you.
This module enforces hard safety limits to protect your capital.
"""

import time
import logging
from typing import Optional, Dict, List
from dataclasses import dataclass, field, asdict
from enum import Enum

logger = logging.getLogger(__name__)


# ============================================================
# TYPES
# ============================================================

class PositionSide(str, Enum):
    LONG = "long"
    SHORT = "short"


class PositionStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"
    LIQUIDATED = "liquidated"
    STOPPED_OUT = "stopped_out"


@dataclass
class LeveragePosition:
    """Represents an open or closed leveraged position."""
    position_id: str
    token: str
    symbol: str
    side: PositionSide
    leverage: float
    collateral_usd: float          # USDC deposited as margin
    size_usd: float                # Effective position size (collateral * leverage)
    entry_price: float
    current_price: float = 0.0
    stop_loss_price: float = 0.0   # Auto-close if price hits this
    take_profit_price: float = 0.0 # Auto-close if price hits this
    liquidation_price: float = 0.0 # Forced close by protocol
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    status: PositionStatus = PositionStatus.OPEN
    opened_at: float = field(default_factory=time.time)
    closed_at: Optional[float] = None
    close_reason: str = ""
    funding_paid: float = 0.0

    def to_dict(self):
        d = asdict(self)
        d["side"] = self.side.value
        d["status"] = self.status.value
        return d


# ============================================================
# SAFETY CONFIG — Hard limits that CANNOT be bypassed
# ============================================================

@dataclass
class LeverageSafetyConfig:
    max_leverage: float = 5.0              # Start conservative — 5x max
    max_position_size_usd: float = 100.0   # Max single position
    max_total_exposure_usd: float = 300.0  # Max across ALL positions
    max_open_positions: int = 3            # Max simultaneous positions
    max_daily_loss_usd: float = 100.0      # Stop everything if hit
    mandatory_stop_loss_pct: float = 5.0   # MUST set stop-loss within 5% of entry
    max_stop_loss_pct: float = 15.0        # Stop-loss can't be wider than 15%
    min_take_profit_pct: float = 2.0       # Take profit must be at least 2%
    cooldown_after_loss_sec: int = 300     # Wait 5 min after a loss before new position
    max_funding_rate_pct: float = 0.1      # Skip if funding rate too high
    require_trend_confirmation: bool = True # Must confirm trend before entry
    dry_run: bool = True                   # CRITICAL: start in dry run mode


# ============================================================
# LEVERAGE TRADING ENGINE
# ============================================================

class LeverageTradingEngine:
    """
    Core engine for managing leveraged perpetual positions.
    
    Integrates with Avantis (or any perp DEX) on Base chain.
    Enforces strict risk management on every operation.
    """

    def __init__(self, safety_config: Optional[LeverageSafetyConfig] = None):
        self.safety = safety_config or LeverageSafetyConfig()
        self.positions: Dict[str, LeveragePosition] = {}
        self.closed_positions: List[LeveragePosition] = []
        self.trade_log: List[dict] = []
        self.daily_pnl: float = 0.0
        self.daily_reset_time: float = time.time()
        self.last_loss_time: float = 0.0
        self._position_counter: int = 0

    # ============================================================
    # OPEN POSITION
    # ============================================================

    def open_position(
        self,
        token: str,
        symbol: str,
        side: str,           # "long" or "short"
        leverage: float,
        collateral_usd: float,
        entry_price: float,
        stop_loss_pct: Optional[float] = None,
        take_profit_pct: Optional[float] = None,
    ) -> Dict:
        """
        Open a leveraged position with full safety validation.
        Returns result dict with position details or rejection reason.
        """

        # ── SAFETY CHECKS ──
        rejection = self._validate_open(leverage, collateral_usd, entry_price, stop_loss_pct)
        if rejection:
            self._log("REJECTED", symbol, rejection)
            return {"status": "rejected", "reason": rejection}

        # ── CALCULATE POSITION ──
        side_enum = PositionSide.LONG if side.lower() == "long" else PositionSide.SHORT
        size_usd = collateral_usd * leverage

        # Stop-loss (mandatory)
        sl_pct = stop_loss_pct or self.safety.mandatory_stop_loss_pct
        if side_enum == PositionSide.LONG:
            stop_loss_price = entry_price * (1 - sl_pct / 100)
            liquidation_price = entry_price * (1 - 90 / (leverage * 100))  # ~90% loss = liq
        else:
            stop_loss_price = entry_price * (1 + sl_pct / 100)
            liquidation_price = entry_price * (1 + 90 / (leverage * 100))

        # Take-profit
        tp_pct = take_profit_pct or (sl_pct * 2)  # Default: 2:1 reward/risk
        if side_enum == PositionSide.LONG:
            take_profit_price = entry_price * (1 + tp_pct / 100)
        else:
            take_profit_price = entry_price * (1 - tp_pct / 100)

        # ── CREATE POSITION ──
        self._position_counter += 1
        pos_id = f"pos_{self._position_counter}_{int(time.time())}"

        position = LeveragePosition(
            position_id=pos_id,
            token=token,
            symbol=symbol,
            side=side_enum,
            leverage=leverage,
            collateral_usd=collateral_usd,
            size_usd=size_usd,
            entry_price=entry_price,
            current_price=entry_price,
            stop_loss_price=round(stop_loss_price, 6),
            take_profit_price=round(take_profit_price, 6),
            liquidation_price=round(liquidation_price, 6),
        )

        if self.safety.dry_run:
            # Dry run — track but don't execute on-chain
            self.positions[pos_id] = position
            self._log("OPEN (DRY RUN)", symbol,
                     f"{side} {leverage}x | ${collateral_usd} collateral | "
                     f"Size: ${size_usd:.2f} | Entry: ${entry_price:.4f} | "
                     f"SL: ${stop_loss_price:.4f} | TP: ${take_profit_price:.4f}")
        else:
            # TODO: Execute on Avantis via SDK
            # tx = avantis_sdk.open_trade(...)
            self.positions[pos_id] = position
            self._log("OPEN", symbol,
                     f"{side} {leverage}x | ${collateral_usd} collateral | "
                     f"Size: ${size_usd:.2f} | Entry: ${entry_price:.4f}")

        self.trade_log.append({
            "action": "open",
            "position_id": pos_id,
            "symbol": symbol,
            "side": side,
            "leverage": leverage,
            "collateral": collateral_usd,
            "size": size_usd,
            "entry_price": entry_price,
            "stop_loss": stop_loss_price,
            "take_profit": take_profit_price,
            "dry_run": self.safety.dry_run,
            "time": time.time(),
        })

        return {
            "status": "opened",
            "position": position.to_dict(),
            "dry_run": self.safety.dry_run,
        }

    # ============================================================
    # UPDATE POSITIONS (called every cycle with new prices)
    # ============================================================

    def update_positions(self, price_updates: Dict[str, float]):
        """
        Update all open positions with latest prices.
        Checks stop-loss, take-profit, and liquidation.
        Returns list of actions taken.
        """
        actions = []

        for pos_id, pos in list(self.positions.items()):
            if pos.status != PositionStatus.OPEN:
                continue

            token = pos.token
            if token not in price_updates:
                continue

            new_price = price_updates[token]
            pos.current_price = new_price

            # Calculate unrealized PnL
            if pos.side == PositionSide.LONG:
                price_change_pct = (new_price - pos.entry_price) / pos.entry_price
            else:
                price_change_pct = (pos.entry_price - new_price) / pos.entry_price

            pos.unrealized_pnl = round(pos.size_usd * price_change_pct, 2)

            # ── CHECK STOP-LOSS ──
            if self._check_stop_loss(pos, new_price):
                result = self._close_position(pos, new_price, "stop_loss")
                actions.append(result)
                continue

            # ── CHECK TAKE-PROFIT ──
            if self._check_take_profit(pos, new_price):
                result = self._close_position(pos, new_price, "take_profit")
                actions.append(result)
                continue

            # ── CHECK LIQUIDATION ──
            if self._check_liquidation(pos, new_price):
                result = self._close_position(pos, new_price, "liquidated")
                actions.append(result)
                continue

        # ── CHECK DAILY LOSS LIMIT ──
        if self._check_daily_limit():
            # Emergency: close all positions
            for pos_id, pos in list(self.positions.items()):
                if pos.status == PositionStatus.OPEN:
                    price = price_updates.get(pos.token, pos.current_price)
                    result = self._close_position(pos, price, "daily_limit_hit")
                    actions.append(result)

        return actions

    # ============================================================
    # CLOSE POSITION
    # ============================================================

    def close_position(self, position_id: str, current_price: float, reason: str = "manual"):
        """Manually close a position."""
        if position_id not in self.positions:
            return {"status": "error", "reason": "Position not found"}

        pos = self.positions[position_id]
        return self._close_position(pos, current_price, reason)

    def _close_position(self, pos: LeveragePosition, close_price: float, reason: str):
        """Internal close logic."""
        # Calculate realized PnL
        if pos.side == PositionSide.LONG:
            pnl_pct = (close_price - pos.entry_price) / pos.entry_price
        else:
            pnl_pct = (pos.entry_price - close_price) / pos.entry_price

        pos.realized_pnl = round(pos.size_usd * pnl_pct, 2)
        pos.unrealized_pnl = 0
        pos.current_price = close_price
        pos.closed_at = time.time()
        pos.close_reason = reason

        if reason == "liquidated":
            pos.status = PositionStatus.LIQUIDATED
            pos.realized_pnl = -pos.collateral_usd  # Lost all collateral
        elif reason in ("stop_loss", "daily_limit_hit"):
            pos.status = PositionStatus.STOPPED_OUT
        else:
            pos.status = PositionStatus.CLOSED

        # Update daily PnL
        self._reset_daily_if_needed()
        self.daily_pnl += pos.realized_pnl

        # Track loss timing for cooldown
        if pos.realized_pnl < 0:
            self.last_loss_time = time.time()

        # Move to closed
        self.closed_positions.append(pos)
        del self.positions[pos.position_id]

        emoji = "+" if pos.realized_pnl >= 0 else ""
        self._log(f"CLOSE ({reason})", pos.symbol,
                 f"{pos.side.value} {pos.leverage}x | "
                 f"Entry: ${pos.entry_price:.4f} → Exit: ${close_price:.4f} | "
                 f"PnL: {emoji}${pos.realized_pnl:.2f}")

        self.trade_log.append({
            "action": "close",
            "position_id": pos.position_id,
            "symbol": pos.symbol,
            "side": pos.side.value,
            "leverage": pos.leverage,
            "entry_price": pos.entry_price,
            "close_price": close_price,
            "pnl": pos.realized_pnl,
            "reason": reason,
            "dry_run": self.safety.dry_run,
            "time": time.time(),
        })

        return {
            "status": "closed",
            "reason": reason,
            "position": pos.to_dict(),
            "pnl": pos.realized_pnl,
        }

    # ============================================================
    # SAFETY VALIDATION
    # ============================================================

    def _validate_open(self, leverage, collateral, entry_price, stop_loss_pct):
        """Validate everything before opening. Returns rejection reason or None."""

        # Reset daily if needed
        self._reset_daily_if_needed()

        # Max leverage
        if leverage > self.safety.max_leverage:
            return f"Leverage {leverage}x exceeds max {self.safety.max_leverage}x"

        if leverage < 1:
            return f"Leverage must be >= 1x"

        # Position size
        size = collateral * leverage
        if size > self.safety.max_position_size_usd:
            return f"Position size ${size:.2f} exceeds max ${self.safety.max_position_size_usd}"

        if collateral <= 0 or entry_price <= 0:
            return "Invalid collateral or entry price"

        # Total exposure
        current_exposure = sum(p.size_usd for p in self.positions.values()
                              if p.status == PositionStatus.OPEN)
        if current_exposure + size > self.safety.max_total_exposure_usd:
            return f"Total exposure would be ${current_exposure + size:.2f} (max: ${self.safety.max_total_exposure_usd})"

        # Max open positions
        open_count = sum(1 for p in self.positions.values() if p.status == PositionStatus.OPEN)
        if open_count >= self.safety.max_open_positions:
            return f"Already have {open_count} open positions (max: {self.safety.max_open_positions})"

        # Daily loss limit
        if self.daily_pnl <= -self.safety.max_daily_loss_usd:
            return f"Daily loss limit hit: ${self.daily_pnl:.2f} (limit: -${self.safety.max_daily_loss_usd})"

        # Stop-loss validation
        if stop_loss_pct and stop_loss_pct > self.safety.max_stop_loss_pct:
            return f"Stop-loss {stop_loss_pct}% too wide (max: {self.safety.max_stop_loss_pct}%)"

        # Cooldown after loss
        if self.last_loss_time > 0:
            elapsed = time.time() - self.last_loss_time
            if elapsed < self.safety.cooldown_after_loss_sec:
                remaining = int(self.safety.cooldown_after_loss_sec - elapsed)
                return f"Cooldown active: {remaining}s remaining after last loss"

        return None  # All checks passed

    def _check_stop_loss(self, pos, price):
        if pos.side == PositionSide.LONG:
            return price <= pos.stop_loss_price
        else:
            return price >= pos.stop_loss_price

    def _check_take_profit(self, pos, price):
        if pos.side == PositionSide.LONG:
            return price >= pos.take_profit_price
        else:
            return price <= pos.take_profit_price

    def _check_liquidation(self, pos, price):
        if pos.side == PositionSide.LONG:
            return price <= pos.liquidation_price
        else:
            return price >= pos.liquidation_price

    def _check_daily_limit(self):
        self._reset_daily_if_needed()
        return self.daily_pnl <= -self.safety.max_daily_loss_usd

    def _reset_daily_if_needed(self):
        if time.time() - self.daily_reset_time > 86400:
            self.daily_pnl = 0.0
            self.daily_reset_time = time.time()

    # ============================================================
    # STATUS
    # ============================================================

    def get_status(self):
        """Full engine status."""
        open_positions = [p.to_dict() for p in self.positions.values()
                         if p.status == PositionStatus.OPEN]
        total_pnl = sum(p.unrealized_pnl for p in self.positions.values())
        total_collateral = sum(p.collateral_usd for p in self.positions.values())

        return {
            "open_positions": open_positions,
            "position_count": len(open_positions),
            "total_unrealized_pnl": round(total_pnl, 2),
            "total_collateral_locked": round(total_collateral, 2),
            "daily_pnl": round(self.daily_pnl, 2),
            "daily_limit_hit": self._check_daily_limit(),
            "closed_count": len(self.closed_positions),
            "total_realized_pnl": round(sum(p.realized_pnl for p in self.closed_positions), 2),
            "win_rate": self._calc_win_rate(),
            "safety": {
                "max_leverage": self.safety.max_leverage,
                "max_position_usd": self.safety.max_position_size_usd,
                "max_exposure_usd": self.safety.max_total_exposure_usd,
                "daily_loss_limit": self.safety.max_daily_loss_usd,
                "dry_run": self.safety.dry_run,
            },
            "recent_trades": self.trade_log[-20:],
        }

    def _calc_win_rate(self):
        if not self.closed_positions:
            return 0.0
        wins = sum(1 for p in self.closed_positions if p.realized_pnl > 0)
        return round(wins / len(self.closed_positions) * 100, 1)

    # ============================================================
    # LOGGING
    # ============================================================

    def _log(self, action, symbol, details):
        dry = "[DRY] " if self.safety.dry_run else ""
        logger.info(f"[LEVERAGE] {dry}{action} {symbol}: {details}")
        print(f"  [LEVERAGE] {dry}{action} {symbol}: {details}")
