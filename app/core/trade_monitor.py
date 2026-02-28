"""Trade Monitor — continuously watches master account for trade changes."""

import asyncio
import logging
import time
import uuid
from typing import Callable, Optional

from app.core.mt5_bridge import MT5Bridge
from app.core.trade_types import MasterTrade, TradeAction, TradeDirection, TradeSnapshot

logger = logging.getLogger("mtcs.monitor")


class TradeMonitor:
    """Monitors the master account for new/closed/modified trades."""

    def __init__(self, bridge: MT5Bridge, interval_ms: int = 500):
        self.bridge = bridge
        self.interval = interval_ms / 1000.0
        self._running = False
        self._paused = False
        self._task: Optional[asyncio.Task] = None
        self._last_snapshot = TradeSnapshot()
        self._callbacks: list[Callable] = []
        self._trade_uuids: dict[int, str] = {}  # ticket -> UUID

    def on_trade_event(self, callback: Callable) -> None:
        """Register a callback for trade events."""
        self._callbacks.append(callback)

    async def _emit(self, event: MasterTrade) -> None:
        """Emit a trade event to all registered callbacks."""
        for cb in self._callbacks:
            try:
                if asyncio.iscoroutinefunction(cb):
                    await cb(event)
                else:
                    cb(event)
            except Exception as e:
                logger.error(f"Trade event callback error: {e}", exc_info=True)

    def _get_uuid(self, ticket: int) -> str:
        """Get or create UUID for a master ticket."""
        if ticket not in self._trade_uuids:
            self._trade_uuids[ticket] = str(uuid.uuid4())
        return self._trade_uuids[ticket]

    async def _take_snapshot(self) -> TradeSnapshot:
        """Take a snapshot of current positions and orders."""
        positions = await self.bridge.get_positions()
        orders = await self.bridge.get_orders()
        return TradeSnapshot(
            positions={p["ticket"]: p for p in positions},
            orders={o["ticket"]: o for o in orders},
            timestamp=time.time(),
        )

    async def _compare_snapshots(self, old: TradeSnapshot, new: TradeSnapshot) -> None:
        """Compare two snapshots and emit events for differences."""
        old_pos = set(old.positions.keys())
        new_pos = set(new.positions.keys())

        # New positions (opened)
        for ticket in new_pos - old_pos:
            pos = new.positions[ticket]
            trade = MasterTrade(
                uuid=self._get_uuid(ticket),
                ticket=ticket,
                symbol=pos["symbol"],
                direction=TradeDirection.BUY if pos["type"] == "buy" else TradeDirection.SELL,
                action=TradeAction.OPEN,
                volume=pos["volume"],
                price=pos["price_open"],
                sl=pos["sl"],
                tp=pos["tp"],
                comment=pos.get("comment", ""),
                magic=pos.get("magic", 0),
            )
            logger.info(f"New position detected: {trade.symbol} {trade.direction.value} {trade.volume} @ {trade.price} [ticket={ticket}]")
            await self._emit(trade)

        # Closed positions
        for ticket in old_pos - new_pos:
            pos = old.positions[ticket]
            trade_uuid = self._trade_uuids.pop(ticket, str(uuid.uuid4()))
            trade = MasterTrade(
                uuid=trade_uuid,
                ticket=ticket,
                symbol=pos["symbol"],
                direction=TradeDirection.BUY if pos["type"] == "buy" else TradeDirection.SELL,
                action=TradeAction.CLOSE,
                volume=pos["volume"],
                price=pos.get("price_current", 0),
                sl=pos["sl"],
                tp=pos["tp"],
            )
            logger.info(f"Position closed: {trade.symbol} [ticket={ticket}]")
            await self._emit(trade)

        # Modified positions (still open, but changed)
        for ticket in old_pos & new_pos:
            old_p = old.positions[ticket]
            new_p = new.positions[ticket]

            # Volume change = partial close
            if new_p["volume"] < old_p["volume"]:
                trade = MasterTrade(
                    uuid=self._get_uuid(ticket),
                    ticket=ticket,
                    symbol=new_p["symbol"],
                    direction=TradeDirection.BUY if new_p["type"] == "buy" else TradeDirection.SELL,
                    action=TradeAction.PARTIAL_CLOSE,
                    volume=old_p["volume"] - new_p["volume"],
                    price=new_p.get("price_current", 0),
                    sl=new_p["sl"],
                    tp=new_p["tp"],
                )
                logger.info(f"Partial close detected: {trade.symbol} vol change {old_p['volume']}->{new_p['volume']} [ticket={ticket}]")
                await self._emit(trade)

            # SL/TP modification
            elif old_p["sl"] != new_p["sl"] or old_p["tp"] != new_p["tp"]:
                trade = MasterTrade(
                    uuid=self._get_uuid(ticket),
                    ticket=ticket,
                    symbol=new_p["symbol"],
                    direction=TradeDirection.BUY if new_p["type"] == "buy" else TradeDirection.SELL,
                    action=TradeAction.MODIFY,
                    volume=new_p["volume"],
                    price=new_p.get("price_current", 0),
                    sl=new_p["sl"],
                    tp=new_p["tp"],
                )
                logger.info(f"SL/TP modified: {trade.symbol} SL={new_p['sl']} TP={new_p['tp']} [ticket={ticket}]")
                await self._emit(trade)

    async def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        logger.info(f"Trade monitor started (interval={self.interval}s)")
        self._last_snapshot = await self._take_snapshot()

        while self._running:
            try:
                if not self._paused:
                    new_snapshot = await self._take_snapshot()
                    await self._compare_snapshots(self._last_snapshot, new_snapshot)
                    self._last_snapshot = new_snapshot
                await asyncio.sleep(self.interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitor loop error: {e}", exc_info=True)
                await asyncio.sleep(self.interval * 2)

        logger.info("Trade monitor stopped")

    async def start(self) -> None:
        """Start the monitoring loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())

    async def stop(self) -> None:
        """Stop the monitoring loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    def pause(self) -> None:
        """Pause trade monitoring (preserves state)."""
        self._paused = True
        logger.info("Trade monitor paused")

    def resume(self) -> None:
        """Resume trade monitoring."""
        self._paused = False
        logger.info("Trade monitor resumed")

    @property
    def is_running(self) -> bool:
        return self._running and not self._paused

    @property
    def is_paused(self) -> bool:
        return self._paused
