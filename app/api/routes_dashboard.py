"""Dashboard metrics API routes.

Refactored for multi-process: gets data from individual workers (no login switching).
"""

import logging
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.api.deps import app_state

logger = logging.getLogger("mtcs.api.dashboard")
router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


@router.get("")
async def dashboard_data():
    """Get aggregated dashboard data from all workers."""
    data = {
        "system_status": app_state.system_status,
        "mt5_status": app_state.mt5_status,
        "copy_active": app_state.copy_active,
        "master": None,
        "slaves": [],
        "total_equity": 0,
        "total_profit": 0,
        "open_positions": 0,
        "pending_orders": 0,
    }

    if not app_state.workers:
        return JSONResponse(content=data)

    # Master account — get data from master worker
    master = await app_state.recovery.get_master_account()
    if master:
        master_worker = app_state.workers.get_worker(master["login"])
        if master_worker and master_worker.alive:
            try:
                info = await app_state.workers.get_account_info(login=master["login"])
                if info:
                    data["master"] = {
                        "login": master["login"],
                        "server": master["server"],
                        "balance": info.get("balance", 0),
                        "equity": info.get("equity", 0),
                        "profit": info.get("profit", 0),
                        "margin": info.get("margin", 0),
                        "margin_free": info.get("margin_free", 0),
                        "trade_allowed": info.get("trade_allowed", False),
                    }
                    data["total_equity"] += info.get("equity", 0)
                    data["total_profit"] += info.get("profit", 0)

                positions = await app_state.workers.get_positions(login=master["login"])
                orders = await app_state.workers.get_orders(login=master["login"])
                data["open_positions"] += len(positions)
                data["pending_orders"] += len(orders)
            except Exception as e:
                logger.error(f"Dashboard master error: {e}")

    # Slave accounts — get data from each slave worker
    slaves = await app_state.recovery.get_slave_accounts()
    for slave in slaves:
        slave_data = {
            "login": slave["login"],
            "server": slave["server"],
            "enabled": bool(slave.get("enabled", False)),
            "balance": 0,
            "equity": 0,
            "profit": 0,
            "currency": "USD",
            "trade_allowed": False,
            "mt5_connected": False,
            "worker_alive": False,
            "worker_pid": 0,
        }

        worker = app_state.workers.get_worker(slave["login"])
        if worker and worker.alive:
            slave_data["worker_alive"] = True
            slave_data["worker_pid"] = worker.pid
            try:
                info = await app_state.workers.get_account_info(login=slave["login"])
                if info:
                    slave_data["balance"] = info.get("balance", 0)
                    slave_data["equity"] = info.get("equity", 0)
                    slave_data["profit"] = info.get("profit", 0)
                    slave_data["currency"] = info.get("currency", "USD")
                    slave_data["trade_allowed"] = info.get("trade_allowed", False)
                    slave_data["mt5_connected"] = True
                    data["total_equity"] += info.get("equity", 0)
                    data["total_profit"] += info.get("profit", 0)

                positions = await app_state.workers.get_positions(login=slave["login"])
                orders = await app_state.workers.get_orders(login=slave["login"])
                data["open_positions"] += len(positions)
                data["pending_orders"] += len(orders)
            except Exception as e:
                logger.error(f"Dashboard slave {slave['login']} error: {e}")

        data["slaves"].append(slave_data)

    return JSONResponse(content=data)


@router.get("/quotes")
async def get_quotes(active_symbol: str = None):
    """Get watchlist quotes from the master worker, plus an optionally specified active symbol."""
    watchlist = await app_state.db.fetch_all(
        "SELECT symbol FROM watchlist ORDER BY sort_order"
    )
    
    symbols_to_fetch = [item["symbol"] for item in watchlist]
    if active_symbol and active_symbol not in symbols_to_fetch:
        symbols_to_fetch.append(active_symbol)

    quotes = []
    for symbol in symbols_to_fetch:
        tick = None
        if app_state.workers and app_state.workers.connected:
            tick = await app_state.workers.get_symbol_tick(symbol)

        if tick:
            quotes.append({
                "symbol": symbol,
                "bid": tick.get("bid", 0),
                "ask": tick.get("ask", 0),
                "spread": tick.get("spread", 0),
                "last": tick.get("last", 0),
                "volume": tick.get("volume", 0),
            })
        else:
            quotes.append({
                "symbol": symbol,
                "bid": 0, "ask": 0, "spread": 0,
                "last": 0, "volume": 0,
            })

    return JSONResponse(content={"quotes": quotes})
