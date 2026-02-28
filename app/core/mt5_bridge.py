"""MT5 Bridge — wrapper around the MetaTrader5 Python API.

All MT5 API calls are synchronous and single-threaded.
We use asyncio.to_thread() to avoid blocking the event loop.
Gracefully degrades when MT5 is not installed.
"""

import asyncio
import logging
import time
from typing import Optional

logger = logging.getLogger("mtcs.mt5_bridge")

# Try to import MT5 — graceful fallback if not installed
try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    mt5 = None
    MT5_AVAILABLE = False
    logger.warning("MetaTrader5 package not installed. Trading features disabled.")


class MT5Bridge:
    """Thread-safe wrapper for MetaTrader5 Python API."""

    def __init__(self, terminal_path: str = ""):
        self._initialized = False
        self._lock = asyncio.Lock()
        self._current_login: Optional[int] = None
        self._terminal_path = terminal_path

    @property
    def available(self) -> bool:
        return MT5_AVAILABLE

    @property
    def connected(self) -> bool:
        return self._initialized

    async def initialize(self) -> bool:
        """Initialize MT5 terminal connection."""
        if not MT5_AVAILABLE:
            logger.error("MT5 package not available")
            return False

        async with self._lock:
            if self._terminal_path:
                result = await asyncio.to_thread(mt5.initialize, self._terminal_path)
            else:
                result = await asyncio.to_thread(mt5.initialize)
            if result:
                self._initialized = True
                info = await asyncio.to_thread(mt5.terminal_info)
                if info:
                    logger.info(f"MT5 initialized: {info.name} build {info.build}")
            else:
                error = await asyncio.to_thread(mt5.last_error)
                logger.error(f"MT5 initialization failed: {error}")
            return result

    async def shutdown(self) -> None:
        """Shutdown MT5 connection."""
        if MT5_AVAILABLE and self._initialized:
            async with self._lock:
                await asyncio.to_thread(mt5.shutdown)
                self._initialized = False
                self._current_login = None
                logger.info("MT5 shutdown complete")

    async def login(self, login: int, password: str, server: str) -> dict:
        """
        Authenticate with MT5 using login, password, server.
        Returns dict with success status and account info.
        """
        if not MT5_AVAILABLE:
            return {"success": False, "error": "MT5 not available"}

        async with self._lock:
            # Initialize if needed
            if not self._initialized:
                if self._terminal_path:
                    init_result = await asyncio.to_thread(mt5.initialize, self._terminal_path)
                else:
                    init_result = await asyncio.to_thread(mt5.initialize)
                if not init_result:
                    error = await asyncio.to_thread(mt5.last_error)
                    return {"success": False, "error": f"MT5 init failed: {error}"}
                self._initialized = True

            # Login
            result = await asyncio.to_thread(
                mt5.login, login, password=password, server=server
            )

            if result:
                self._current_login = login
                info = await asyncio.to_thread(mt5.account_info)
                if info:
                    account_data = {
                        "success": True,
                        "login": info.login,
                        "server": info.server,
                        "balance": info.balance,
                        "equity": info.equity,
                        "profit": info.profit,
                        "margin": info.margin,
                        "margin_free": info.margin_free,
                        "currency": info.currency,
                        "leverage": info.leverage,
                        "name": info.name,
                    }
                    logger.info(f"Login successful: {login}@{server}")
                    return account_data
                return {"success": True, "login": login}
            else:
                error = await asyncio.to_thread(mt5.last_error)
                logger.error(f"Login failed for {login}@{server}: {error}")
                return {"success": False, "error": str(error)}

    async def get_account_info(self) -> dict | None:
        """Get current account info."""
        if not self._initialized:
            return None
        async with self._lock:
            info = await asyncio.to_thread(mt5.account_info)
            if info:
                return {
                    "login": info.login,
                    "server": info.server,
                    "balance": info.balance,
                    "equity": info.equity,
                    "profit": info.profit,
                    "margin": info.margin,
                    "margin_free": info.margin_free,
                    "currency": info.currency,
                    "leverage": info.leverage,
                    "name": info.name,
                }
            return None

    async def get_positions(self) -> list[dict]:
        """Get all open positions for current account."""
        if not self._initialized:
            return []
        async with self._lock:
            positions = await asyncio.to_thread(mt5.positions_get)
            if positions is None:
                return []
            return [
                {
                    "ticket": p.ticket,
                    "symbol": p.symbol,
                    "type": "buy" if p.type == 0 else "sell",
                    "volume": p.volume,
                    "price_open": p.price_open,
                    "price_current": p.price_current,
                    "sl": p.sl,
                    "tp": p.tp,
                    "profit": p.profit,
                    "swap": p.swap,
                    "commission": getattr(p, "commission", 0.0),
                    "magic": p.magic,
                    "comment": p.comment,
                    "time": p.time,
                    "identifier": p.identifier,
                }
                for p in positions
            ]

    async def get_orders(self) -> list[dict]:
        """Get all pending orders for current account."""
        if not self._initialized:
            return []
        async with self._lock:
            orders = await asyncio.to_thread(mt5.orders_get)
            if orders is None:
                return []
            type_map = {
                0: "buy_limit", 1: "sell_limit",
                2: "buy_stop", 3: "sell_stop",
                4: "buy_stop_limit", 5: "sell_stop_limit",
            }
            return [
                {
                    "ticket": o.ticket,
                    "symbol": o.symbol,
                    "type": type_map.get(o.type, str(o.type)),
                    "volume_initial": o.volume_initial,
                    "volume_current": o.volume_current,
                    "price_open": o.price_open,
                    "sl": o.sl,
                    "tp": o.tp,
                    "price_current": o.price_current,
                    "price_stoplimit": o.price_stoplimit,
                    "magic": o.magic,
                    "comment": o.comment,
                    "time_setup": o.time_setup,
                }
                for o in orders
            ]

    async def get_symbol_tick(self, symbol: str) -> dict | None:
        """Get last tick for a symbol."""
        if not self._initialized:
            return None
        async with self._lock:
            tick = await asyncio.to_thread(mt5.symbol_info_tick, symbol)
            if tick:
                return {
                    "symbol": symbol,
                    "bid": tick.bid,
                    "ask": tick.ask,
                    "last": tick.last,
                    "volume": tick.volume,
                    "time": tick.time,
                    "spread": round((tick.ask - tick.bid), 6),
                }
            return None

    async def get_symbol_info(self, symbol: str) -> dict | None:
        """Get symbol info (point, digits, trade sizes, etc)."""
        if not self._initialized:
            return None
        async with self._lock:
            info = await asyncio.to_thread(mt5.symbol_info, symbol)
            if info:
                return {
                    "symbol": info.name,
                    "point": info.point,
                    "digits": info.digits,
                    "volume_min": info.volume_min,
                    "volume_max": info.volume_max,
                    "volume_step": info.volume_step,
                    "trade_contract_size": info.trade_contract_size,
                    "spread": info.spread,
                    "ask": info.ask,
                    "bid": info.bid,
                }
            return None

    async def get_symbols(self) -> list[str]:
        """Get all available symbol names."""
        if not self._initialized:
            return []
        async with self._lock:
            symbols = await asyncio.to_thread(mt5.symbols_get)
            if symbols:
                return [s.name for s in symbols if s.visible]
            return []

    async def send_order(self, request: dict) -> dict:
        """
        Send a trade order. Request dict should contain:
        action, symbol, volume, type, price, sl, tp, deviation, magic, comment, type_filling
        """
        if not self._initialized:
            return {"success": False, "error": "MT5 not initialized"}

        async with self._lock:
            # First check the order
            check_result = await asyncio.to_thread(mt5.order_check, request)
            if check_result is None:
                error = await asyncio.to_thread(mt5.last_error)
                return {"success": False, "error": f"Order check failed: {error}"}

            if check_result.retcode != 0:
                return {
                    "success": False,
                    "error": f"Order check rejected: {check_result.comment}",
                    "retcode": check_result.retcode,
                }

            # Send the order
            result = await asyncio.to_thread(mt5.order_send, request)
            if result is None:
                error = await asyncio.to_thread(mt5.last_error)
                return {"success": False, "error": f"Order send failed: {error}"}

            success = result.retcode == mt5.TRADE_RETCODE_DONE
            response = {
                "success": success,
                "retcode": result.retcode,
                "comment": result.comment,
                "order": result.order,
                "deal": result.deal,
                "volume": result.volume,
                "price": result.price,
            }

            if success:
                logger.info(
                    f"Order executed: {request.get('symbol')} "
                    f"vol={result.volume} price={result.price} "
                    f"ticket={result.order}"
                )
            else:
                logger.error(
                    f"Order failed: {result.comment} (retcode={result.retcode})"
                )

            return response

    async def close_position(self, ticket: int, volume: float = None) -> dict:
        """Close a position by ticket. Partial close if volume specified."""
        if not self._initialized:
            return {"success": False, "error": "MT5 not initialized"}

        async with self._lock:
            # Get position info
            positions = await asyncio.to_thread(mt5.positions_get, ticket=ticket)
            if not positions:
                return {"success": False, "error": f"Position {ticket} not found"}

            pos = positions[0]
            close_volume = volume or pos.volume

            # Build close request
            close_type = mt5.ORDER_TYPE_SELL if pos.type == 0 else mt5.ORDER_TYPE_BUY
            tick = await asyncio.to_thread(mt5.symbol_info_tick, pos.symbol)
            if not tick:
                return {"success": False, "error": f"No tick data for {pos.symbol}"}

            price = tick.bid if pos.type == 0 else tick.ask

            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": pos.symbol,
                "volume": close_volume,
                "type": close_type,
                "position": ticket,
                "price": price,
                "deviation": 50,
                "magic": pos.magic,
                "comment": "MTCS close",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }

            result = await asyncio.to_thread(mt5.order_send, request)
            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                logger.info(f"Position {ticket} closed: vol={close_volume}")
                return {"success": True, "order": result.order, "deal": result.deal}
            else:
                error = result.comment if result else "Unknown error"
                logger.error(f"Failed to close position {ticket}: {error}")
                return {"success": False, "error": error}

    async def get_history_deals(self, from_ts: int, to_ts: int) -> list[dict]:
        """Get deal history in time range (unix timestamps)."""
        if not self._initialized:
            return []
        async with self._lock:
            from datetime import datetime
            from_dt = datetime.utcfromtimestamp(from_ts)
            to_dt = datetime.utcfromtimestamp(to_ts)
            deals = await asyncio.to_thread(mt5.history_deals_get, from_dt, to_dt)
            if deals is None:
                return []
            return [
                {
                    "ticket": d.ticket,
                    "order": d.order,
                    "symbol": d.symbol,
                    "type": d.type,
                    "volume": d.volume,
                    "price": d.price,
                    "profit": d.profit,
                    "commission": d.commission,
                    "swap": d.swap,
                    "time": d.time,
                    "comment": d.comment,
                    "position_id": d.position_id,
                }
                for d in deals
            ]
