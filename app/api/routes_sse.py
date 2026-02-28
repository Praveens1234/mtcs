"""SSE (Server-Sent Events) streaming routes."""

import asyncio
import json
import logging
from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

from app.api.deps import app_state
from app.config import settings

logger = logging.getLogger("mtcs.api.sse")
router = APIRouter(prefix="/api/v1/sse", tags=["sse"])


async def _dashboard_stream(request: Request):
    """Generate dashboard update events."""
    while True:
        if await request.is_disconnected():
            break

        # Build dashboard snapshot
        data = {
            "system_status": app_state.system_status,
            "mt5_status": app_state.mt5_status,
            "copy_active": app_state.copy_active,
            "positions_count": 0,
            "orders_count": 0,
            "master_equity": 0,
            "master_profit": 0,
        }

        if app_state.workers and app_state.workers.connected:
            try:
                positions = await app_state.workers.get_positions()
                orders = await app_state.workers.get_orders()
                data["positions_count"] = len(positions)
                data["orders_count"] = len(orders)

                info = await app_state.workers.get_account_info()
                if info:
                    data["master_equity"] = info.get("equity", 0)
                    data["master_profit"] = info.get("profit", 0)
            except Exception:
                pass

        yield {
            "event": "dashboard",
            "data": json.dumps(data),
            "retry": settings.SSE_RETRY_MS,
        }
        await asyncio.sleep(settings.SSE_KEEPALIVE_S)


async def _positions_stream(request: Request):
    """Stream position updates."""
    while True:
        if await request.is_disconnected():
            break

        positions = []
        if app_state.workers and app_state.workers.connected:
            try:
                positions = await app_state.workers.get_positions()
            except Exception:
                pass

        yield {
            "event": "positions",
            "data": json.dumps({"positions": positions}),
            "retry": settings.SSE_RETRY_MS,
        }
        await asyncio.sleep(2)


async def _quotes_stream(request: Request):
    """Stream watchlist quote updates."""
    while True:
        if await request.is_disconnected():
            break

        quotes = []
        if app_state.workers and app_state.workers.connected:
            watchlist = await app_state.db.fetch_all(
                "SELECT symbol FROM watchlist ORDER BY sort_order"
            )
            for item in watchlist:
                tick = await app_state.workers.get_symbol_tick(item["symbol"])
                if tick:
                    quotes.append(tick)

        yield {
            "event": "quotes",
            "data": json.dumps({"quotes": quotes}),
            "retry": settings.SSE_RETRY_MS,
        }
        await asyncio.sleep(1)


async def _events_stream(request: Request):
    """Stream general events via queue-based pub/sub."""
    queue = app_state.sse_subscribe()
    try:
        while True:
            if await request.is_disconnected():
                break
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=settings.SSE_KEEPALIVE_S)
                yield {
                    "event": msg["event"],
                    "data": json.dumps(msg["data"]),
                    "retry": settings.SSE_RETRY_MS,
                }
            except asyncio.TimeoutError:
                # Send keepalive
                yield {"event": "keepalive", "data": "{}", "retry": settings.SSE_RETRY_MS}
    finally:
        app_state.sse_unsubscribe(queue)


@router.get("/dashboard")
async def sse_dashboard(request: Request):
    """SSE stream for dashboard updates."""
    return EventSourceResponse(_dashboard_stream(request))


@router.get("/positions")
async def sse_positions(request: Request):
    """SSE stream for position updates."""
    return EventSourceResponse(_positions_stream(request))


@router.get("/quotes")
async def sse_quotes(request: Request):
    """SSE stream for quote updates."""
    return EventSourceResponse(_quotes_stream(request))


@router.get("/events")
async def sse_events(request: Request):
    """SSE stream for general events."""
    return EventSourceResponse(_events_stream(request))
