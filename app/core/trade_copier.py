"""Trade Copier — executes slave orders based on master trade events.

Refactored for multi-process architecture:
- Orders are sent to slave workers via WorkerManager (parallel IPC)
- Each slave worker has its own permanent MT5 login (no switching)
- Lot sizing, dedup, and risk logic stay in the main process
"""

import asyncio
import json
import logging
from typing import Optional

from app.core.trade_types import (
    LotSizingMode, ExecutionPolicy, RiskConfig, TradeDirection,
)
from app.core.mt5_worker import TradeEvent
from app.persistence.database import Database

logger = logging.getLogger("mtcs.copier")

# MT5 constants
TRADE_ACTION_DEAL = 1
TRADE_ACTION_SLTP = 6
ORDER_TYPE_BUY = 0
ORDER_TYPE_SELL = 1
ORDER_FILLING_FOK = 0
ORDER_FILLING_IOC = 1
ORDER_TIME_GTC = 0


class TradeCopier:
    """Copies master trades to slave accounts via worker manager."""

    def __init__(self, worker_manager, db: Database, credentials=None):
        self._wm = worker_manager
        self.db = db
        self._credentials = credentials
        self._slave_configs: dict[int, RiskConfig] = {}
        self._paused = False

    def set_slave_config(self, slave_login: int, config: RiskConfig) -> None:
        self._slave_configs[slave_login] = config

    def compute_slave_lot(self, master_lot: float, config: RiskConfig,
                          symbol: str = "") -> float:
        if config.lot_mode == LotSizingMode.MULTIPLIER:
            return round(master_lot * config.lot_multiplier, 2)
        elif config.lot_mode == LotSizingMode.FIXED:
            return config.fixed_lot
        elif config.lot_mode == LotSizingMode.EQUITY_PERCENT:
            return max(config.fixed_lot, round(master_lot * config.equity_percent / 100, 2))
        elif config.lot_mode == LotSizingMode.CUSTOM_MAP:
            mapped = config.custom_lot_map.get(str(master_lot), master_lot)
            return round(float(mapped), 2)
        return master_lot

    def get_fill_type(self, config: RiskConfig) -> int:
        if config.execution_policy == ExecutionPolicy.FORCE_FOK:
            return ORDER_FILLING_FOK
        elif config.execution_policy == ExecutionPolicy.FORCE_IOC:
            return ORDER_FILLING_IOC
        return ORDER_FILLING_IOC

    async def _check_mapping_exists(self, master_uuid: str, slave_login: int) -> bool:
        row = await self.db.fetch_one(
            "SELECT id FROM trade_mappings WHERE master_uuid = ? AND slave_login = ? "
            "AND status NOT IN ('closed', 'failed')",
            (master_uuid, slave_login),
        )
        return row is not None

    async def _save_mapping(self, event_data: dict, slave_login: int,
                            slave_ticket: Optional[int], slave_lot: float,
                            status: str = "filled") -> None:
        await self.db.execute(
            "INSERT INTO trade_mappings "
            "(master_uuid, master_ticket, slave_ticket, slave_login, "
            "symbol, direction, master_lot, slave_lot, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (event_data.get("uuid"), event_data.get("ticket"),
             slave_ticket, slave_login,
             event_data.get("symbol"), event_data.get("direction"),
             event_data.get("volume"), slave_lot, status),
        )

    async def _save_history(self, event_data: dict, slave_login: int,
                            ticket: int, event: str, volume: float,
                            price: float = 0, profit: float = 0) -> None:
        await self.db.execute(
            "INSERT INTO trade_history "
            "(master_uuid, account_login, ticket, symbol, trade_type, "
            "direction, volume, open_price, profit, event) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (event_data.get("uuid"), slave_login, ticket,
             event_data.get("symbol"), "market",
             event_data.get("direction"), volume, price, profit, event),
        )

    async def handle_trade_event(self, trade_event: TradeEvent) -> None:
        """Handle a trade event from the master worker.
        Routes to the correct handler and fans out to all slaves IN PARALLEL.
        """
        if self._paused:
            logger.info(f"Copier paused — ignoring {trade_event.event_type}")
            return

        data = trade_event.data
        event_type = trade_event.event_type

        # Get all enabled slave accounts
        slaves = await self.db.fetch_all(
            "SELECT * FROM accounts WHERE role = 'slave' AND enabled = 1"
        )
        if not slaves:
            logger.debug("No enabled slaves — skipping copy")
            return

        # Fan out to all slaves IN PARALLEL
        tasks = []
        for slave in slaves:
            login = slave["login"]
            config = self._slave_configs.get(login, RiskConfig())
            if not config.enabled:
                continue

            # Check worker is alive
            worker = self._wm.get_worker(login)
            if not worker or not worker.alive:
                logger.warning(f"Slave worker {login} not alive — skipping")
                continue

            if event_type == "open":
                tasks.append(self._handle_open(data, login, config))
            elif event_type == "close":
                tasks.append(self._handle_close(data, login))
            elif event_type == "modify":
                tasks.append(self._handle_modify(data, login, config))
            elif event_type == "partial_close":
                tasks.append(self._handle_partial_close(data, login))

        if tasks:
            t0 = asyncio.get_event_loop().time()
            results = await asyncio.gather(*tasks, return_exceptions=True)
            elapsed = (asyncio.get_event_loop().time() - t0) * 1000
            logger.info(
                f"Copied {event_type} {data.get('symbol')} to {len(tasks)} slaves "
                f"in {elapsed:.1f}ms (parallel)"
            )
            for i, r in enumerate(results):
                if isinstance(r, Exception):
                    logger.error(f"Slave copy error: {r}")

    async def _handle_open(self, data: dict, slave_login: int, config: RiskConfig) -> None:
        """Open a position on a slave worker."""
        uuid = data.get("uuid", "")
        symbol = data.get("symbol", "")
        direction = data.get("direction", "buy")

        # Deduplication
        if await self._check_mapping_exists(uuid, slave_login):
            logger.warning(f"Duplicate trade {uuid} for slave {slave_login}")
            return

        master_lot = data.get("volume", 0.01)
        slave_lot = self.compute_slave_lot(master_lot, config, symbol)

        order_type = ORDER_TYPE_BUY if direction == "buy" else ORDER_TYPE_SELL
        fill_type = self.get_fill_type(config)

        sl = config.force_sl if config.force_sl else data.get("sl", 0)
        tp = config.force_tp if config.force_tp else data.get("tp", 0)

        # Get tick from slave worker (it has its own connection)
        tick = await self._wm.get_symbol_tick(symbol, login=slave_login)
        if not tick:
            logger.error(f"No tick for {symbol} on slave {slave_login}")
            await self._save_mapping(data, slave_login, None, slave_lot, "failed")
            return

        price = tick["ask"] if direction == "buy" else tick["bid"]

        # Spread check
        spread = tick.get("spread", 0)
        if config.max_spread and isinstance(spread, (int, float)) and spread > config.max_spread:
            logger.warning(f"Spread too high ({spread}) on slave {slave_login}")
            await self._save_mapping(data, slave_login, None, slave_lot, "failed")
            return

        request = {
            "action": TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": slave_lot,
            "type": order_type,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": config.max_slippage,
            "magic": 999000 + slave_login % 1000,
            "comment": f"MTCS:{uuid[:8]}",
            "type_time": ORDER_TIME_GTC,
            "type_filling": fill_type,
        }

        # Send order to slave worker (parallel — this goes to its own MT5 process)
        result = await self._wm.send_order(slave_login, request)

        if result.get("success"):
            slave_ticket = result.get("order", 0)
            await self._save_mapping(data, slave_login, slave_ticket, slave_lot, "filled")
            await self._save_history(data, slave_login, slave_ticket, "opened",
                                     slave_lot, result.get("price", 0))
            logger.info(f"Copied OPEN {symbol} {direction} {slave_lot} → slave {slave_login}")
        else:
            await self._save_mapping(data, slave_login, None, slave_lot, "failed")
            logger.error(f"Failed to copy to slave {slave_login}: {result.get('error')}")

            # FOK→IOC fallback
            if config.execution_policy == ExecutionPolicy.FOK_IOC_FALLBACK:
                request["type_filling"] = ORDER_FILLING_IOC
                result = await self._wm.send_order(slave_login, request)
                if result.get("success"):
                    slave_ticket = result.get("order", 0)
                    await self.db.execute(
                        "UPDATE trade_mappings SET slave_ticket=?, status='filled' "
                        "WHERE master_uuid=? AND slave_login=?",
                        (slave_ticket, uuid, slave_login),
                    )
                    logger.info(f"FOK→IOC fallback OK for slave {slave_login}")

    async def _handle_close(self, data: dict, slave_login: int) -> None:
        """Close corresponding slave position."""
        uuid = data.get("uuid", "")
        mappings = await self.db.fetch_all(
            "SELECT * FROM trade_mappings WHERE master_uuid = ? AND slave_login = ? "
            "AND status = 'filled'",
            (uuid, slave_login),
        )
        for mapping in mappings:
            if mapping["slave_ticket"]:
                result = await self._wm.close_position(slave_login, mapping["slave_ticket"])
                status = "closed" if result.get("success") else "failed"
                await self.db.execute(
                    "UPDATE trade_mappings SET status=?, updated_at=datetime('now') WHERE id=?",
                    (status, mapping["id"]),
                )
                await self._save_history(data, slave_login, mapping["slave_ticket"],
                                         "closed", mapping["slave_lot"] or 0)

    async def _handle_modify(self, data: dict, slave_login: int, config: RiskConfig) -> None:
        """Modify SL/TP on slave."""
        uuid = data.get("uuid", "")
        mappings = await self.db.fetch_all(
            "SELECT * FROM trade_mappings WHERE master_uuid = ? AND slave_login = ? "
            "AND status = 'filled'",
            (uuid, slave_login),
        )
        for mapping in mappings:
            if mapping["slave_ticket"]:
                sl = config.force_sl if config.force_sl else data.get("sl", 0)
                tp = config.force_tp if config.force_tp else data.get("tp", 0)
                request = {
                    "action": TRADE_ACTION_SLTP,
                    "symbol": data.get("symbol", ""),
                    "position": mapping["slave_ticket"],
                    "sl": sl,
                    "tp": tp,
                }
                result = await self._wm.send_order(slave_login, request)
                if result.get("success"):
                    await self._save_history(data, slave_login, mapping["slave_ticket"],
                                             "modified", mapping["slave_lot"] or 0)

    async def _handle_partial_close(self, data: dict, slave_login: int) -> None:
        """Handle proportional partial close on slave."""
        uuid = data.get("uuid", "")
        mappings = await self.db.fetch_all(
            "SELECT * FROM trade_mappings WHERE master_uuid = ? AND slave_login = ? "
            "AND status = 'filled'",
            (uuid, slave_login),
        )
        for mapping in mappings:
            if mapping["slave_ticket"] and mapping["slave_lot"]:
                vol_closed = data.get("volume", 0)
                remaining = data.get("remaining_volume", 0)
                total = vol_closed + remaining if remaining else mapping["master_lot"]
                ratio = vol_closed / total if total else 0.5
                close_vol = round(mapping["slave_lot"] * ratio, 2)
                close_vol = max(0.01, close_vol)

                result = await self._wm.close_position(
                    slave_login, mapping["slave_ticket"], volume=close_vol
                )
                if result.get("success"):
                    new_lot = round(mapping["slave_lot"] - close_vol, 2)
                    await self.db.execute(
                        "UPDATE trade_mappings SET slave_lot=?, status='partial', "
                        "updated_at=datetime('now') WHERE id=?",
                        (new_lot, mapping["id"]),
                    )
                    await self._save_history(data, slave_login, mapping["slave_ticket"],
                                             "partial_close", close_vol)

    def pause(self):
        self._paused = True
        logger.info("Trade copier paused")

    def resume(self):
        self._paused = False
        logger.info("Trade copier resumed")

    @property
    def is_paused(self) -> bool:
        return self._paused
