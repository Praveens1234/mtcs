"""Settings API routes."""

import json
import logging
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.api.deps import app_state
from app.config import settings

logger = logging.getLogger("mtcs.api.settings")
router = APIRouter(prefix="/api/v1/settings", tags=["settings"])


@router.get("")
async def get_settings():
    """Get all application settings."""
    return JSONResponse(content={
        "theme": settings.THEME,
        "one_click_trading": settings.ONE_CLICK_TRADING,
        "pin_enabled": settings.PIN_ENABLED,
        "monitor_interval_ms": settings.MONITOR_INTERVAL_MS,
        "max_slippage": settings.MAX_SLIPPAGE_POINTS,
        "max_spread": settings.MAX_SPREAD_POINTS,
        "default_lot": settings.DEFAULT_LOT_SIZE,
        "max_watchlist": settings.MAX_WATCHLIST_SYMBOLS,
    })


@router.post("/update")
async def update_settings(request: Request):
    """Update application settings."""
    body = await request.json()

    for key, value in body.items():
        await app_state.db.execute(
            "INSERT OR REPLACE INTO system_config (key, value, updated_at) "
            "VALUES (?, ?, datetime('now'))",
            (key, json.dumps(value)),
        )

    await app_state.db.audit_log("settings_updated", json.dumps(body))
    return JSONResponse(content={"success": True, "settings": body})


@router.get("/watchlist")
async def get_watchlist():
    """Get watchlist symbols."""
    items = await app_state.db.fetch_all(
        "SELECT symbol, sort_order FROM watchlist ORDER BY sort_order"
    )
    return JSONResponse(content={"watchlist": items})


@router.post("/watchlist/add")
async def add_to_watchlist(request: Request):
    """Add a symbol to watchlist."""
    body = await request.json()
    symbol = body.get("symbol", "").upper()

    if not symbol:
        return JSONResponse(content={"success": False, "error": "Symbol required"}, status_code=400)

    count = await app_state.db.fetch_one("SELECT COUNT(*) as c FROM watchlist")
    if count and count["c"] >= settings.MAX_WATCHLIST_SYMBOLS:
        return JSONResponse(
            content={"success": False, "error": f"Max {settings.MAX_WATCHLIST_SYMBOLS} symbols"},
            status_code=400,
        )

    max_order = await app_state.db.fetch_one("SELECT MAX(sort_order) as m FROM watchlist")
    next_order = (max_order["m"] or 0) + 1 if max_order else 0

    await app_state.db.execute(
        "INSERT OR IGNORE INTO watchlist (symbol, sort_order) VALUES (?, ?)",
        (symbol, next_order),
    )
    return JSONResponse(content={"success": True, "symbol": symbol})


@router.post("/watchlist/remove")
async def remove_from_watchlist(request: Request):
    """Remove a symbol from watchlist."""
    body = await request.json()
    symbol = body.get("symbol", "").upper()
    await app_state.db.execute("DELETE FROM watchlist WHERE symbol = ?", (symbol,))
    return JSONResponse(content={"success": True})


@router.get("/system-info")
async def system_info():
    """Get system and network information."""
    workers_count = len(app_state.workers.get_all_workers()) if app_state.workers else 0
    return JSONResponse(content={
        "network": app_state.network_info,
        "system_status": app_state.system_status,
        "mt5_status": app_state.mt5_status,
        "mt5_available": app_state.workers.available if app_state.workers else False,
        "workers_active": workers_count,
        "version": "2.0.0",
    })
